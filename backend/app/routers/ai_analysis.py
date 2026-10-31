"""
routers/ai_analysis.py
----------------------
Doctor-only endpoints for the AI Clinical Insights layer:
  - POST /api/analysis/{encounter_id}/run    : Launch clinical analysis pipeline
  - GET  /api/analysis/{encounter_id}        : Retrieve comprehensive AI insights, labs, trends, scores
  - PUT  /api/insights/{id}/decision         : Clinician Accept / Edit / Reject decision gating
  - GET  /api/analysis/guidelines            : Read guideline reference library
  - GET  /api/analysis/trend-rules           : Read trend interpretation rules configuration

STRICT ACCESS CONTROL:
  AI insights are visible to licensed clinicians only (doctor/admin).
  Access attempts by patient or staff roles return HTTP 403 Forbidden.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.models import (
    Encounter, Patient, Document, Conflict, ReviewFlag,
    AIInsight, LabResult, DocumentEntity, TrendFlag, RiskScore,
    GuidelinePassage, LLMJob, User, AuditEvent,
    AIInsightStatus, JobStatus, EncounterStatus
)
from app.dependencies import get_current_user, require_roles
from app.services.clinical_analysis import ClinicalAnalysisService
from app.services.guidelines import seed_guideline_passages
from app.engines.trend_calculator import load_trend_rules
from app.core.config import settings

router = APIRouter(tags=["AI Clinical Insights"])


def _utcnow():
    return datetime.now(timezone.utc)


class DecisionPayload(BaseModel):
    decision: str = Field(..., description="'accepted' | 'edited' | 'rejected'")
    doctor_edits: Optional[Dict[str, Any]] = None
    doctor_notes: Optional[str] = None


@router.post("/api/analysis/{encounter_id}/run")
async def run_clinical_analysis(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """
    Trigger end-to-end AI clinical analysis pipeline for an encounter.
    Strictly doctor-gated.
    """
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    if enc.status == EncounterStatus.reviewed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Case is finalized and locked. Analysis cannot be re-run on a finalized encounter."
        )

    # Create job tracking entry
    job = LLMJob(
        encounter_id=encounter_id,
        job_type="full_clinical_analysis",
        status=JobStatus.running,
        progress=0.05,
        started_at=_utcnow()
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Record audit event
    db.add(AuditEvent(
        actor_id=current_user.id,
        actor_username=current_user.username,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        action="AI_ANALYSIS_STARTED",
        resource_type="encounter",
        resource_id=str(encounter_id),
        change_summary=f"Clinician triggered AI Clinical Analysis for encounter {encounter_id} (job {job.id})"
    ))
    await db.commit()

    # Run analysis
    try:
        result = await ClinicalAnalysisService.run_analysis(encounter_id, db, job_id=job.id)
        return {
            "status": "completed",
            "job_id": job.id,
            "encounter_id": encounter_id,
            "overall_urgency": result["overall_urgency"],
            "red_flags_count": len(result["red_flags"])
        }
    except Exception as e:
        job.status = JobStatus.failed
        job.error_message = str(e)
        job.finished_at = _utcnow()
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Clinical analysis pipeline error: {str(e)}")


@router.get("/api/analysis/guidelines")
async def list_guidelines(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles("doctor", "admin", "staff")),
):
    """List available guideline passages from the local reference library."""
    try:
        await seed_guideline_passages(db)
        passages = (await db.scalars(select(GuidelinePassage).order_by(GuidelinePassage.id.asc()))).all()
        return [
            {
                "id": p.id,
                "source": p.source,
                "version_date": p.version_date,
                "condition_or_topic": p.condition_or_topic,
                "section": p.section,
                "passage_text": p.passage_text,
                "is_sample": p.is_sample,
                "warning": "SAMPLE – replace with verified source" if p.is_sample else None
            }
            for p in passages
        ]
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/analysis/trend-rules")
async def get_trend_rules_config(
    _=Depends(require_roles("doctor", "admin", "staff")),
):
    """Retrieve configurable clinical trend threshold rules."""
    config = load_trend_rules()
    return {
        "disclaimer": config.get("disclaimer", "RESEARCH PROTOTYPE ONLY - REQUIRES CLINICIAN REVIEW BEFORE REAL USE"),
        "version": config.get("version", "2026.10.1"),
        "rules": config.get("rules", {})
    }


@router.get("/api/analysis/{encounter_id}")
async def get_clinical_analysis(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """
    Retrieve comprehensive AI insights, lab results, trends, and risk scores.
    Strictly doctor/admin only. Patients and staff receive 403 Forbidden.
    """
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    patient = await db.get(Patient, enc.patient_id)

    # 1. Gather all AI Insights
    insights = (await db.scalars(
        select(AIInsight).where(AIInsight.encounter_id == encounter_id).order_by(AIInsight.id.asc())
    )).all()

    possible_diagnoses = [
        {
            "id": i.id,
            "type": i.insight_type,
            "content": i.content,
            "evidence": i.evidence,
            "status": i.status.value if hasattr(i.status, "value") else str(i.status),
            "provenance": i.provenance,
            "model_name": i.model_name,
            "prompt_version": i.prompt_version,
            "decided_by": i.decided_by,
            "decided_at": i.decided_at,
            "doctor_edits": i.doctor_edits
        }
        for i in insights if i.insight_type == "disease_consideration"
    ]

    treatment_references = [
        {
            "id": i.id,
            "type": i.insight_type,
            "content": i.content,
            "evidence": i.evidence,
            "status": i.status.value if hasattr(i.status, "value") else str(i.status),
            "provenance": i.provenance,
            "model_name": i.model_name,
            "prompt_version": i.prompt_version,
            "decided_by": i.decided_by,
            "decided_at": i.decided_at,
            "doctor_edits": i.doctor_edits
        }
        for i in insights if i.insight_type == "treatment_reference"
    ]

    trend_interpretations = [
        {
            "id": i.id,
            "type": i.insight_type,
            "content": i.content,
            "evidence": i.evidence,
            "status": i.status.value if hasattr(i.status, "value") else str(i.status),
            "provenance": i.provenance,
            "model_name": i.model_name,
            "prompt_version": i.prompt_version,
            "decided_by": i.decided_by,
            "decided_at": i.decided_at
        }
        for i in insights if i.insight_type == "trend_interpretation"
    ]

    case_summary = next((
        {
            "id": i.id,
            "type": i.insight_type,
            "content": i.content,
            "evidence": i.evidence,
            "status": i.status.value if hasattr(i.status, "value") else str(i.status),
            "provenance": i.provenance,
            "model_name": i.model_name,
            "prompt_version": i.prompt_version,
            "decided_by": i.decided_by,
            "decided_at": i.decided_at,
            "doctor_edits": i.doctor_edits
        }
        for i in insights if i.insight_type == "case_summary"
    ), None)

    questions_to_ask = [
        {
            "id": i.id,
            "type": i.insight_type,
            "content": i.content,
            "evidence": i.evidence,
            "status": i.status.value if hasattr(i.status, "value") else str(i.status),
            "provenance": i.provenance
        }
        for i in insights if i.insight_type == "questions_to_ask"
    ]

    # 2. Documented diagnoses from DocumentEntities
    doc_entities = (await db.scalars(
        select(DocumentEntity).where(DocumentEntity.encounter_id == encounter_id)
    )).all()

    documented_diagnoses = [
        {
            "id": e.id,
            "document_id": e.document_id,
            "name": e.value.get("name") if isinstance(e.value, dict) else e.raw_text,
            "raw_text": e.raw_text,
            "source_span": e.source_span,
            "grounded": e.grounded,
            "confidence": e.confidence
        }
        for e in doc_entities if e.entity_type == "diagnosis"
    ]

    extracted_medications = [
        {
            "id": e.id,
            "document_id": e.document_id,
            "details": e.value,
            "source_span": e.source_span,
            "grounded": e.grounded
        }
        for e in doc_entities if e.entity_type == "medication"
    ]

    # 3. Lab Results
    labs = (await db.scalars(
        select(LabResult).where(LabResult.encounter_id == encounter_id).order_by(LabResult.id.asc())
    )).all()
    all_labs = [
        {
            "id": l.id,
            "document_id": l.document_id,
            "test_name": l.test_name,
            "normalized_test": l.normalized_test,
            "value": l.value,
            "unit": l.unit,
            "ref_low": l.ref_low,
            "ref_high": l.ref_high,
            "flag": l.flag,
            "test_date": l.test_date,
            "source_span": l.source_span
        }
        for l in labs
    ]
    abnormal_labs = [l for l in all_labs if l["flag"] not in ("normal", None)]

    # 4. Computed Trends
    trends = (await db.scalars(
        select(TrendFlag).where(TrendFlag.encounter_id == encounter_id)
    )).all()
    computed_trends = [
        {
            "id": t.id,
            "test_name": t.test_name,
            "previous_value": t.previous_value,
            "current_value": t.current_value,
            "unit": t.unit,
            "delta": t.delta,
            "percent_change": t.percent_change,
            "direction": t.direction,
            "time_span_days": t.time_span_days,
            "rule_matched": t.rule_matched,
            "clinical_label": t.clinical_label
        }
        for t in trends
    ]

    # 5. Published Risk Scores
    scores = (await db.scalars(
        select(RiskScore).where(RiskScore.encounter_id == encounter_id)
    )).all()
    risk_scores = [
        {
            "id": s.id,
            "score_name": s.score_name,
            "score_value": s.score_value,
            "status": s.status,
            "inputs": s.inputs,
            "missing_inputs": s.missing_inputs,
            "formula_version": s.formula_version,
            "interpretation": s.interpretation
        }
        for s in scores
    ]

    # 6. Red Flags
    flags = (await db.scalars(
        select(ReviewFlag).where(ReviewFlag.encounter_id == encounter_id, ReviewFlag.flag_type == "red_flag")
    )).all()
    red_flags = [{"id": f.id, "description": f.description, "status": f.status.value} for f in flags]

    # Determine overall urgency
    overall_urgency = "ROUTINE"
    if any("[EMERGENCY]" in f.description for f in flags):
        overall_urgency = "EMERGENCY"
    elif any("[URGENT]" in f.description for f in flags):
        overall_urgency = "URGENT"

    # 7. Document Chronological Timeline
    docs = (await db.scalars(
        select(Document).where(Document.encounter_id == encounter_id).order_by(Document.uploaded_at.asc())
    )).all()
    timeline = [
        {
            "id": d.id,
            "filename": d.original_filename,
            "document_type": d.document_type or "unclassified",
            "uploaded_at": d.uploaded_at,
            "status": d.status.value if hasattr(d.status, "value") else str(d.status),
            "confidence": d.extraction_confidence,
            "is_verified": d.is_verified,
            "extracted_text_preview": (d.extracted_text[:120] + "...") if d.extracted_text else ""
        }
        for d in docs
    ]

    # 8. Latest Job Status
    latest_job = await db.scalar(
        select(LLMJob).where(LLMJob.encounter_id == encounter_id).order_by(desc(LLMJob.id)).limit(1)
    )

    return {
        "encounter_id": encounter_id,
        "patient_id": enc.patient_id,
        "patient_name": patient.full_name if patient else "",
        "overall_urgency": overall_urgency,
        "has_red_flags": len(red_flags) > 0,
        "red_flags": red_flags,
        "documented_diagnoses": documented_diagnoses,
        "possible_diagnoses": possible_diagnoses,
        "abnormal_labs": abnormal_labs,
        "all_labs": all_labs,
        "computed_trends": computed_trends,
        "trend_interpretations": trend_interpretations,
        "risk_scores": risk_scores,
        "treatment_references": treatment_references,
        "case_summary": case_summary,
        "questions_to_ask": questions_to_ask,
        "extracted_medications": extracted_medications,
        "document_timeline": timeline,
        "is_case_locked": (enc.status == EncounterStatus.reviewed),
        "job_status": latest_job.status.value if latest_job else "none",
        "job_progress": latest_job.progress if latest_job else 0.0,
        "provider_mode": settings.LLM_PROVIDER,
        "notice": "PatientCase AI provides source-cited, AI-generated suggestions for clinician review. It makes no autonomous decisions."
    }


@router.put("/api/insights/{id}/decision")
async def decide_insight(
    id: int,
    payload: DecisionPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """
    Clinician Accept, Edit, or Reject decision for an AI proposal.
    Transitions provenance from 'ai_generated_unverified' to 'doctor_verified' on Accept/Edit.
    Enforces case-lock if encounter is already finalized.
    """
    insight = await db.get(AIInsight, id)
    if not insight:
        raise HTTPException(status_code=404, detail="AI Insight not found")

    enc = await db.get(Encounter, insight.encounter_id)
    if enc and enc.status == EncounterStatus.reviewed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Encounter has been finalized and locked by clinician review. Decisions cannot be modified."
        )

    decision_norm = payload.decision.lower().strip()
    if decision_norm not in ("accepted", "edited", "rejected"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Decision must be 'accepted', 'edited', or 'rejected'"
        )

    if decision_norm == "accepted":
        insight.status = AIInsightStatus.accepted
        insight.provenance = "doctor_verified"
    elif decision_norm == "edited":
        insight.status = AIInsightStatus.edited
        insight.provenance = "doctor_verified"
        if payload.doctor_edits:
            insight.doctor_edits = payload.doctor_edits
    elif decision_norm == "rejected":
        insight.status = AIInsightStatus.rejected

    insight.decided_by = current_user.id
    insight.decided_at = _utcnow()

    # Record audit event
    db.add(AuditEvent(
        actor_id=current_user.id,
        actor_username=current_user.username,
        actor_role=current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
        action="AI_INSIGHT_DECISION",
        resource_type="ai_insight",
        resource_id=str(id),
        change_summary=f"Insight {id} ({insight.insight_type}) marked as {decision_norm} by Dr. {current_user.username}"
    ))

    await db.commit()
    await db.refresh(insight)

    return {
        "id": insight.id,
        "encounter_id": insight.encounter_id,
        "status": insight.status.value,
        "provenance": insight.provenance,
        "decided_by": insight.decided_by,
        "decided_at": insight.decided_at
    }
