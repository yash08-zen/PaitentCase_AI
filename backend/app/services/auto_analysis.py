"""
services/auto_analysis.py
-------------------------
Runs the clinical analysis automatically, so the doctor does not have to press
"Run AI Analysis".

Triggers (see routers/interviews.py, routers/patients.py, document_processing.py):
  - an interview answer is saved     -> debounced (AUTO_ANALYSIS_DEBOUNCE_SECONDS)
  - the interview is completed        -> immediately
  - an uploaded document finished OCR -> immediately

Per encounter there is at most one scheduled-or-running analysis. A request that
arrives while one is waiting pushes its start time back (debounce); a request
that arrives while one is running schedules exactly one more run afterwards.
Finalized (locked) encounters and encounters without consent are never analysed.
Results are the same doctor-only AI insights as a manual run.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.models import AuditEvent, Encounter, EncounterStatus, JobStatus, LLMJob

logger = logging.getLogger("app.services.auto_analysis")

SYSTEM_ACTOR = {"id": None, "username": "system", "role": "system"}

_tasks: Dict[int, asyncio.Task] = {}
_due: Dict[int, float] = {}
_reason: Dict[int, str] = {}
_rerun: Dict[int, bool] = {}
_locks: Dict[int, asyncio.Lock] = {}


def _run_lock() -> asyncio.Lock:
    """One automatic analysis at a time (SQLite writes, small local models)."""
    loop = asyncio.get_running_loop()
    lock = _locks.get(id(loop))
    if lock is None:
        _locks.clear()
        lock = _locks[id(loop)] = asyncio.Lock()
    return lock


def _utcnow():
    return datetime.now(timezone.utc)


async def run_job(job_id: int, encounter_id: int, summary_language: str, actor: Dict[str, Any]) -> None:
    """Execute one analysis job with its own DB session; never raises."""
    from app.services.clinical_analysis import ClinicalAnalysisService

    async with AsyncSessionLocal() as db:
        try:
            await ClinicalAnalysisService.run_analysis(
                encounter_id, db, job_id=job_id, summary_language=summary_language, actor=actor)
        except Exception as exc:
            await db.rollback()
            job = await db.get(LLMJob, job_id)
            if job:
                job.status = JobStatus.failed
                job.error_message = f"{type(exc).__name__}: {exc}"[:500]
                job.finished_at = _utcnow()
                await db.commit()


async def run_job_serialized(job_id: int, encounter_id: int, summary_language: str, actor: Dict[str, Any]) -> None:
    """Manual runs share the same one-at-a-time lock as automatic runs."""
    async with _run_lock():
        await run_job(job_id, encounter_id, summary_language, actor)


def request_analysis(encounter_id: Optional[int], reason: str, delay: Optional[float] = None) -> None:
    """Schedule an automatic analysis for an encounter (debounced, coalesced)."""
    if not encounter_id or not settings.AUTO_ANALYSIS_ENABLED:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    wait = settings.AUTO_ANALYSIS_DEBOUNCE_SECONDS if delay is None else delay
    _reason[encounter_id] = reason
    task = _tasks.get(encounter_id)
    if task and not task.done():
        if _due.get(encounter_id) is not None:
            # Still waiting: an immediate trigger should not wait longer than it asked
            _due[encounter_id] = min(_due[encounter_id], loop.time() + wait) if wait == 0 else loop.time() + wait
        else:
            _rerun[encounter_id] = True  # running now: run once more afterwards
        return
    _due[encounter_id] = loop.time() + wait
    _tasks[encounter_id] = loop.create_task(_runner(encounter_id))


async def _runner(encounter_id: int) -> None:
    loop = asyncio.get_running_loop()
    try:
        while True:
            while True:
                remaining = _due.get(encounter_id, 0) - loop.time()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(remaining, 1.0))
            _due.pop(encounter_id, None)
            _rerun.pop(encounter_id, None)
            async with _run_lock():
                busy = await _run_once(encounter_id, _reason.get(encounter_id, "auto"))
            if busy:
                # A manual run is in progress: try again shortly
                _due[encounter_id] = loop.time() + 2.0
                continue
            if not _rerun.pop(encounter_id, False):
                break
            _due[encounter_id] = loop.time() + min(settings.AUTO_ANALYSIS_DEBOUNCE_SECONDS, 2.0)
    except Exception:
        logger.exception("Automatic analysis failed for encounter %s", encounter_id)
    finally:
        _due.pop(encounter_id, None)
        if _tasks.get(encounter_id) is asyncio.current_task():
            _tasks.pop(encounter_id, None)


async def _run_once(encounter_id: int, reason: str) -> bool:
    """Create and run one job. Returns True if another job is already active."""
    async with AsyncSessionLocal() as db:
        enc = await db.get(Encounter, encounter_id)
        if not enc or enc.status == EncounterStatus.reviewed or not enc.consent_given:
            return False
        active = await db.scalar(select(LLMJob.id).where(
            LLMJob.encounter_id == encounter_id, LLMJob.status.in_((JobStatus.pending, JobStatus.running))))
        if active:
            return True
        job = LLMJob(encounter_id=encounter_id, job_type=f"auto:{reason}", status=JobStatus.pending, progress=0.0)
        db.add(job)
        await db.flush()
        db.add(AuditEvent(
            actor_username="system", actor_role="system", action="AI_ANALYSIS_AUTO_STARTED",
            resource_type="encounter", resource_id=str(encounter_id),
            change_summary=f"Automatic AI analysis for encounter {encounter_id} (job {job.id}, trigger: {reason})",
        ))
        await db.commit()
        job_id = job.id
    await run_job(job_id, encounter_id, "en", SYSTEM_ACTOR)
    return False


def pending_encounters() -> Dict[int, str]:
    """Encounters with a scheduled or running automatic analysis (for status display)."""
    return {eid: _reason.get(eid, "auto") for eid, t in _tasks.items() if not t.done()}


async def wait_idle(timeout: float = 60.0) -> None:
    """Wait until no automatic analysis is scheduled or running (tests, shutdown)."""
    end = asyncio.get_running_loop().time() + timeout
    while any(not t.done() for t in _tasks.values()):
        if asyncio.get_running_loop().time() > end:
            raise TimeoutError("automatic analysis did not finish in time")
        await asyncio.sleep(0.05)
