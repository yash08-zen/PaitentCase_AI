"""
routers/ai_analysis.py
----------------------
Endpoints for the AI Clinical Insights layer:
  - POST /api/analysis/{encounter_id}/run    : queue the analysis background job (doctor/admin)
  - GET  /api/analysis/{encounter_id}        : insights, scores, trends, flags, job status (doctor/admin)
  - PUT  /api/insights/{id}/decision         : Accept / Edit / Reject an AI item (doctor/admin)
  - GET  /api/analysis/guidelines            : guideline library, read-only (doctor/admin)
  - GET  /api/analysis/trend-rules           : trend rule configuration, read-only (doctor/admin)

AI output is visible to doctors (and admins) only. Patients and staff get 403.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.dependencies import require_roles
from app.engines.med_reconciliation import reconcile_medications
from app.engines.trend_calculator import load_trend_rules
from app.models import (
    AIInsight, AIInsightStatus, AuditEvent, Conflict, Document, DocumentEntity, Encounter,
    EncounterStatus, GuidelinePassage, JobStatus, LabResult, LLMJob, Patient, Response, ReviewFlag,
    RiskScore, TrendFlag, User,
)
from app.services.clinical_analysis import ClinicalAnalysisService, NO_ANSWERS
from app.services.guidelines import SAMPLE_LABEL, seed_guideline_passages
from app.services.llm.manager import llm_service

router = APIRouter(tags=["AI Clinical Insights"])

NOTICE = ("PatientCase AI provides source-cited, AI-generated suggestions for clinician review. "
          "It makes no autonomous decisions. All AI output is unverified until a licensed clinician accepts it.")
ENGINE_RULES = ("RULE-ALLERGY-CONFLICT", "RULE-INTERACTION", "RULE-LAB-ABNORMAL",
                "RULE-DIAGNOSIS-DENIAL", "RULE-WRONG-PATIENT")


def _utcnow():
    return datetime.now(timezone.utc)


def _role(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def _enum(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


class DecisionPayload(BaseModel):
    decision: str = Field(..., description="'accepted' | 'edited' | 'rejected'")
    doctor_edits: Optional[Dict[str, Any]] = None
    doctor_notes: Optional[str] = None


async def _run_job(job_id: int, encounter_id: int, summary_language: str, actor: Dict[str, Any]) -> None:
    """Background worker: own DB session; never raises into the event loop."""
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


@router.post("/api/analysis/{encounter_id}/run", status_code=status.HTTP_202_ACCEPTED)
async def run_clinical_analysis(
    encounter_id: int,
    background_tasks: BackgroundTasks,
    summary_language: str = Query("en", pattern="^(en|hi|mr)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """Queue the AI analysis job. Poll GET /api/analysis/{id} for job status."""
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if enc.status == EncounterStatus.reviewed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case is finalized and locked. Analysis cannot be re-run on a finalized encounter.",
        )
    active = await db.scalar(select(LLMJob).where(
        LLMJob.encounter_id == encounter_id, LLMJob.status.in_((JobStatus.pending, JobStatus.running))))
    if active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"An analysis job (#{active.id}) is already running for this encounter.")

    job = LLMJob(encounter_id=encounter_id, job_type="full_clinical_analysis",
                 status=JobStatus.pending, progress=0.0)
    db.add(job)
    await db.flush()
    db.add(AuditEvent(
        actor_id=current_user.id, actor_username=current_user.username, actor_role=_role(current_user),
        action="AI_ANALYSIS_STARTED", resource_type="encounter", resource_id=str(encounter_id),
        change_summary=f"Clinician queued AI analysis for encounter {encounter_id} (job {job.id}, provider {llm_service.mode})",
    ))
    await db.commit()

    actor = {"id": current_user.id, "username": current_user.username, "role": _role(current_user)}
    background_tasks.add_task(_run_job, job.id, encounter_id, summary_language, actor)
    return {"status": "queued", "job_id": job.id, "encounter_id": encounter_id, "provider_mode": llm_service.mode}


@router.get("/api/analysis/guidelines")
async def list_guidelines(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("doctor", "admin")),
):
    """Guideline passages in the local reference library (read-only)."""
    await seed_guideline_passages(db)
    passages = (await db.scalars(select(GuidelinePassage).order_by(GuidelinePassage.id.asc()))).all()
    return [
        {
            "id": p.id, "source": p.source, "version_date": p.version_date,
            "condition_or_topic": p.condition_or_topic, "section": p.section,
            "passage_text": p.passage_text, "citations": p.citations or [], "is_sample": p.is_sample,
            "warning": SAMPLE_LABEL if p.is_sample else None,
        }
        for p in passages
    ]


@router.get("/api/analysis/trend-rules")
async def get_trend_rules_config(_=Depends(require_roles("doctor", "admin"))):
    """Configured trend thresholds (read-only)."""
    config = load_trend_rules()
    return {
        "disclaimer": config.get("disclaimer", "RESEARCH PROTOTYPE ONLY - REQUIRES CLINICIAN REVIEW BEFORE REAL USE"),
        "version": config.get("version"),
        "rules": config.get("rules", {}),
    }


def _insight_out(i: AIInsight) -> Dict[str, Any]:
    return {
        "id": i.id, "type": i.insight_type, "content": i.content, "evidence": i.evidence,
        "status": _enum(i.status), "provenance": i.provenance, "model_name": i.model_name,
        "prompt_version": i.prompt_version, "created_at": i.created_at, "decided_by": i.decided_by,
        "decided_at": i.decided_at, "doctor_edits": i.doctor_edits,
    }


def _entity_out(e: DocumentEntity) -> Dict[str, Any]:
    return {
        "id": e.id, "document_id": e.document_id, "type": e.entity_type, "value": e.value,
        "raw_text": e.raw_text, "source_span": e.source_span, "grounded": e.grounded,
        "confidence": e.confidence, "provenance": e.provenance, "review_status": e.review_status,
    }


def _interview_medications(answers: Dict[str, str]) -> Optional[List[str]]:
    """None when the interview did not answer; [] when the patient said none."""
    if (answers.get("current_medications") or "").strip().lower() in NO_ANSWERS:
        return []
    details = answers.get("medication_details")
    if not details:
        return None
    import re
    return [p.strip() for p in re.split(r",|;|\band\b|\n", details) if p.strip()]


@router.get("/api/analysis/{encounter_id}")
async def get_clinical_analysis(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """AI insights, labs, trends, scores, flags and job status for one encounter."""
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    patient = await db.get(Patient, enc.patient_id)

    insights = (await db.scalars(
        select(AIInsight).where(AIInsight.encounter_id == encounter_id).order_by(AIInsight.id.asc()))).all()
    by_type: Dict[str, List[Dict[str, Any]]] = {}
    for i in insights:
        by_type.setdefault(i.insight_type, []).append(_insight_out(i))

    entities = (await db.scalars(
        select(DocumentEntity).where(DocumentEntity.encounter_id == encounter_id).order_by(DocumentEntity.id))).all()
    ents = [_entity_out(e) for e in entities]

    labs = (await db.scalars(
        select(LabResult).where(LabResult.encounter_id == encounter_id).order_by(LabResult.id.asc()))).all()
    all_labs = [{
        "id": l.id, "document_id": l.document_id, "test_name": l.test_name, "normalized_test": l.normalized_test,
        "value": l.value, "unit": l.unit, "ref_low": l.ref_low, "ref_high": l.ref_high, "flag": l.flag,
        "test_date": l.test_date, "source_span": l.source_span,
    } for l in labs]

    trends = (await db.scalars(select(TrendFlag).where(TrendFlag.encounter_id == encounter_id))).all()
    scores = (await db.scalars(select(RiskScore).where(RiskScore.encounter_id == encounter_id))).all()
    flags = (await db.scalars(select(ReviewFlag).where(
        ReviewFlag.encounter_id == encounter_id,
        ReviewFlag.flag_type.in_(("red_flag", "document_quality"))))).all()
    red_flags = [{"id": f.id, "description": f.description, "status": _enum(f.status)}
                 for f in flags if f.flag_type == "red_flag"]
    overall = "ROUTINE"
    if any(f["description"].startswith("[EMERGENCY]") for f in red_flags):
        overall = "EMERGENCY"
    elif any(f["description"].startswith("[URGENT]") for f in red_flags):
        overall = "URGENT"

    conflicts = (await db.scalars(select(Conflict).where(
        Conflict.encounter_id == encounter_id, Conflict.rule_id.in_(ENGINE_RULES)))).all()

    docs = (await db.scalars(
        select(Document).where(Document.encounter_id == encounter_id).order_by(Document.uploaded_at.asc()))).all()
    from app.engines.trend_calculator import parse_date
    import re
    timeline = []
    for d in docs:
        dates = [e["value"].get("value") for e in ents if e["document_id"] == d.id and e["type"] == "date" and e["grounded"]]
        m = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})\b", d.extracted_text or "")
        doc_date = dates[0] if dates else (m.group(1) if m else None)
        fields = d.extracted_fields or {}
        timeline.append({
            "id": d.id, "filename": d.original_filename, "document_type": d.document_type or "unclassified",
            "document_date": doc_date, "uploaded_at": d.uploaded_at, "status": _enum(d.status),
            "confidence": d.extraction_confidence, "is_verified": d.is_verified,
            "mime_type": d.mime_type, "file_url": f"/api/documents/{d.id}/file",
            "extraction_method": fields.get("extraction_method", "ocr"),
            "read_from_handwriting": fields.get("extraction_method") == "vision_fallback",
            "extracted_text": d.extracted_text or "",
        })
    timeline.sort(key=lambda t: (parse_date(t["document_date"]) is None,
                                 parse_date(t["document_date"]) or datetime.min.date(), t["id"]))

    answers = {r.question_key: (r.answer or "").strip() for r in (await db.scalars(
        select(Response).where(Response.encounter_id == encounter_id))).all()}
    doc_dates = {t["id"]: t["document_date"] for t in timeline}
    med_sources = []
    for d in docs:
        meds = [e["value"] for e in ents if e["document_id"] == d.id and e["type"] == "medication" and e["grounded"]]
        if meds:
            med_sources.append({"source": f"doc:{d.id} ({d.original_filename})", "date": doc_dates.get(d.id),
                                "medications": meds})
    reconciliation = reconcile_medications(med_sources, _interview_medications(answers))

    job = await db.scalar(select(LLMJob).where(LLMJob.encounter_id == encounter_id).order_by(desc(LLMJob.id)).limit(1))
    llm_status = await llm_service.get_status()

    return {
        "encounter_id": encounter_id,
        "patient_id": enc.patient_id,
        "patient_name": patient.full_name if patient else "",
        "notice": NOTICE,
        "overall_urgency": overall,
        "has_red_flags": bool(red_flags),
        "red_flags": red_flags,
        "document_quality": [{"id": f.id, "description": f.description} for f in flags if f.flag_type == "document_quality"],
        "documented_diagnoses": [e for e in ents if e["type"] == "diagnosis"],
        "possible_diagnoses": by_type.get("disease_consideration", []),
        "extracted_entities": [e for e in ents if e["type"] not in ("extraction_disagreement",)],
        "extracted_medications": [e for e in ents if e["type"] == "medication"],
        "extraction_disagreements": [e for e in ents if e["type"] == "extraction_disagreement"],
        "entities_needing_review": [e for e in ents if e["review_status"] in ("needs_review", "read_from_handwriting_verify", "regex_disagreement")],
        "all_labs": all_labs,
        "abnormal_labs": [l for l in all_labs if l["flag"] not in ("normal", None)],
        "computed_trends": [{
            "id": t.id, "test_name": t.test_name, "previous_value": t.previous_value, "current_value": t.current_value,
            "unit": t.unit, "delta": t.delta, "percent_change": t.percent_change, "direction": t.direction,
            "time_span_days": t.time_span_days, "rule_matched": t.rule_matched, "clinical_label": t.clinical_label,
        } for t in trends],
        "trend_interpretations": by_type.get("trend_interpretation", []),
        "risk_scores": [{
            "id": s.id, "score_name": s.score_name, "score_value": s.score_value, "status": s.status,
            "inputs": s.inputs, "missing_inputs": s.missing_inputs, "formula_version": s.formula_version,
            "interpretation": s.interpretation,
        } for s in scores],
        "rule_conflicts": [{
            "id": c.id, "rule_id": c.rule_id, "field": c.field, "value_a": c.value_a, "value_b": c.value_b,
            "description": c.description, "status": _enum(c.status),
        } for c in conflicts],
        "medication_reconciliation": reconciliation,
        "treatment_references": by_type.get("treatment_reference", []),
        "treatment_reference_status": (job.notes or {}).get("treatment_reference") if job else None,
        "case_summary": (by_type.get("case_summary") or [None])[-1],
        "questions_to_ask": by_type.get("questions_to_ask", []),
        "document_timeline": timeline,
        "is_case_locked": enc.status == EncounterStatus.reviewed,
        "job": {
            "id": job.id, "status": _enum(job.status), "progress": job.progress, "error": job.error_message,
            "started_at": job.started_at, "finished_at": job.finished_at, "usage": job.usage, "notes": job.notes,
        } if job else None,
        "job_status": _enum(job.status) if job else "none",
        "job_progress": job.progress if job else 0.0,
        "provider_mode": llm_service.mode,
        "llm_status": {k: llm_status[k] for k in ("active_mode", "processing_label", "available", "state",
                                                  "capability", "vision_available", "summary_languages",
                                                  "consent_statement")},
    }


@router.put("/api/insights/{id}/decision")
async def decide_insight(
    id: int,
    payload: DecisionPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """Accept / Edit / Reject one AI item. Accepted or edited items become doctor_verified."""
    insight = await db.get(AIInsight, id)
    if not insight:
        raise HTTPException(status_code=404, detail="AI Insight not found")
    enc = await db.get(Encounter, insight.encounter_id)
    if enc and enc.status == EncounterStatus.reviewed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter has been finalized and locked by clinician review. Decisions cannot be modified.",
        )

    decision = payload.decision.lower().strip()
    if decision not in ("accepted", "edited", "rejected"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Decision must be 'accepted', 'edited', or 'rejected'")
    if decision == "edited" and not payload.doctor_edits:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="An 'edited' decision requires doctor_edits")

    if decision == "accepted":
        insight.status = AIInsightStatus.accepted
        insight.provenance = "doctor_verified"
    elif decision == "edited":
        insight.status = AIInsightStatus.edited
        insight.provenance = "doctor_verified"
        insight.doctor_edits = payload.doctor_edits
    else:
        insight.status = AIInsightStatus.rejected
        insight.provenance = "ai_generated_rejected"
    insight.decided_by = current_user.id
    insight.decided_at = _utcnow()

    note = f" Note: {payload.doctor_notes}" if payload.doctor_notes else ""
    db.add(AuditEvent(
        actor_id=current_user.id, actor_username=current_user.username, actor_role=_role(current_user),
        action="AI_INSIGHT_DECISION", resource_type="ai_insight", resource_id=str(id),
        change_summary=f"Insight {id} ({insight.insight_type}) marked as {decision} by {current_user.username}.{note}",
    ))
    await db.commit()
    await db.refresh(insight)
    return {
        "id": insight.id, "encounter_id": insight.encounter_id, "status": _enum(insight.status),
        "provenance": insight.provenance, "decided_by": insight.decided_by, "decided_at": insight.decided_at,
        "doctor_edits": insight.doctor_edits,
    }
