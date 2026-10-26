"""
routers/encounters_analysis.py (registered under /api/encounters)
-------------------------------------------------------------------
Case analysis endpoints: structured summary, missing information, readiness, contradictions.
All endpoints enforce least-privilege role boundaries and patient record-level access.
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Encounter, Conflict, CaseSummary, Patient, User, Response
from app.schemas import (
    MissingInformationOut,
    MissingField,
    ConflictOut,
    ReadinessOut,
    CaseSummaryOut,
)
from app.services.missing_information import detect_missing
from app.services.contradiction_detection import detect_contradictions
from app.services.case_readiness import calculate_readiness
from app.services.case_summary import build_structured_summary
from app.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/api/encounters", tags=["Case Analysis"])


async def _require_encounter_and_authorize(
    encounter_id: int,
    db: AsyncSession,
    current_user: User,
) -> Encounter:
    """Retrieve encounter and verify role boundaries and patient record-level access."""
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        patient = await db.get(Patient, enc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only access their own encounter information",
            )
    return enc


@router.get("/{encounter_id}/missing", response_model=MissingInformationOut)
@router.get("/{encounter_id}/missing-information", response_model=MissingInformationOut)
async def get_missing_information(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "staff", "admin", "patient")),
):
    """
    Returns required clinical fields that are missing/unknown.
    Treats blanks and skips as 'Not provided / unknown' (never as negative/No).
    """
    await _require_encounter_and_authorize(encounter_id, db, current_user)
    responses = (
        await db.scalars(select(Response).where(Response.encounter_id == encounter_id))
    ).all()
    answered = {r.question_key: (r.answer or "").strip() for r in responses}
    missing = detect_missing(answered)
    return MissingInformationOut(
        encounter_id=encounter_id,
        missing_fields=missing,
        total_missing=len(missing),
    )


@router.get("/{encounter_id}/readiness", response_model=ReadinessOut)
async def get_readiness(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "staff", "admin", "patient")),
):
    """
    Calculates deterministic case completeness indicator.
    Does NOT output medical risk, urgency, or disease probability.
    """
    await _require_encounter_and_authorize(encounter_id, db, current_user)
    data = await calculate_readiness(encounter_id, db)
    return ReadinessOut(
        encounter_id=encounter_id,
        score=data["score"],
        label=data["label"],
        factors=data["factors"],
    )


@router.get("/{encounter_id}/contradictions", response_model=List[ConflictOut])
async def get_contradictions(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "staff", "admin")),
):
    """Detect and return information discrepancies between patient reports and document extractions."""
    await _require_encounter_and_authorize(encounter_id, db, current_user)
    await detect_contradictions(encounter_id, db)
    conflicts = (
        await db.scalars(select(Conflict).where(Conflict.encounter_id == encounter_id))
    ).all()
    return list(conflicts)


@router.get("/{encounter_id}/summary", response_model=CaseSummaryOut)
async def get_case_summary(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "staff", "admin", "patient")),
):
    """
    Builds structured case summary grouped by sections with explicit source labels
    (patient_reported, document_extracted_unverified, doctor_verified, missing_unknown).
    Updates database snapshot on each invocation to ensure updates are reflected.
    """
    await _require_encounter_and_authorize(encounter_id, db, current_user)

    # Build structured summary & text
    summary_data = await build_structured_summary(encounter_id, db)
    readiness_data = await calculate_readiness(encounter_id, db)

    # Get missing fields
    responses = (
        await db.scalars(select(Response).where(Response.encounter_id == encounter_id))
    ).all()
    answered = {r.question_key: (r.answer or "").strip() for r in responses}
    missing = detect_missing(answered)

    # Cache / persist summary to case_summaries table
    existing = await db.scalar(
        select(CaseSummary).where(CaseSummary.encounter_id == encounter_id)
    )

    if existing:
        existing.summary_text = summary_data["summary_text"]
        existing.readiness_score = readiness_data["score"]
        existing.readiness_factors = readiness_data["factors"]
        existing.generated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(existing)
        review_status = existing.review_status
        active_cs = existing
    else:
        active_cs = CaseSummary(
            encounter_id=encounter_id,
            summary_text=summary_data["summary_text"],
            readiness_score=readiness_data["score"],
            readiness_factors=readiness_data["factors"],
            review_status="pending",
        )
        db.add(active_cs)
        await db.commit()
        await db.refresh(active_cs)
        review_status = active_cs.review_status
    return CaseSummaryOut(
        encounter_id=encounter_id,
        summary_text=summary_data["summary_text"],
        sections=summary_data["sections"],
        structured_findings=summary_data["findings"],
        readiness_score=readiness_data["score"],
        readiness_factors=readiness_data["factors"],
        missing_fields=missing,
        review_status=review_status,
        doctor_notes=active_cs.doctor_notes if active_cs else None,
        reviewed_at=active_cs.reviewed_at if active_cs else None,
        reviewed_by=active_cs.reviewed_by if active_cs else None,
        generated_at=datetime.now(timezone.utc),
    )
