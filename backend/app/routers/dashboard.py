"""
routers/dashboard.py
--------------------
Dashboard statistics and clinician review queue endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import Patient, Encounter, ReviewFlag, Conflict, CaseSummary, EncounterStatus
from app.schemas import DashboardSummaryOut, DashboardCaseOut
from app.dependencies import get_current_user, require_roles

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
async def dashboard_summary(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles('doctor', 'staff', 'admin')),
):
    total_patients = await db.scalar(select(func.count(Patient.id))) or 0
    active_encounters = await db.scalar(
        select(func.count(Encounter.id)).where(Encounter.status.in_(["pending", "in_progress"]))
    ) or 0
    completed_cases = await db.scalar(
        select(func.count(Encounter.id)).where(Encounter.status.in_(["completed", "reviewed"]))
    ) or 0
    # Cases needing review = encounters not yet reviewed that have open flags, open conflicts, or are completed
    cases_needing_review = await db.scalar(
        select(func.count(func.distinct(Encounter.id)))
        .outerjoin(ReviewFlag, ReviewFlag.encounter_id == Encounter.id)
        .outerjoin(Conflict, Conflict.encounter_id == Encounter.id)
        .where(
            (Encounter.status != EncounterStatus.reviewed) & (
                (ReviewFlag.status == "open") |
                (Conflict.status == "open") |
                (Encounter.status.in_([EncounterStatus.completed, EncounterStatus.needs_review]))
            )
        )
    ) or 0

    return DashboardSummaryOut(
        total_patients=total_patients,
        active_encounters=active_encounters,
        completed_cases=completed_cases,
        cases_needing_review=cases_needing_review,
    )


@router.get("/cases", response_model=List[DashboardCaseOut])
async def cases_needing_review(
    status: Optional[str] = Query(None, description="Filter by status: 'needs_review', 'all', 'reviewed', 'active'"),
    search: Optional[str] = Query(None, description="Search by patient name or complaint"),
    db: AsyncSession = Depends(get_db),
    _=Depends(require_roles('doctor', 'staff', 'admin')),
):
    if status == "all":
        query = select(Encounter).order_by(Encounter.created_at.desc())
    elif status == "reviewed":
        query = select(Encounter).where(Encounter.status == EncounterStatus.reviewed).order_by(Encounter.created_at.desc())
    elif status == "active":
        query = select(Encounter).where(Encounter.status.in_([EncounterStatus.pending, EncounterStatus.in_progress])).order_by(Encounter.created_at.desc())
    else:
        # Default: cases needing review (open flags OR open conflicts OR completed awaiting review)
        query = (
            select(Encounter)
            .outerjoin(ReviewFlag, ReviewFlag.encounter_id == Encounter.id)
            .outerjoin(Conflict, Conflict.encounter_id == Encounter.id)
            .where(
                (Encounter.status != EncounterStatus.reviewed) & (
                    (ReviewFlag.status == "open") |
                    (Conflict.status == "open") |
                    (Encounter.status.in_([EncounterStatus.completed, EncounterStatus.needs_review]))
                )
            )
            .distinct()
            .order_by(Encounter.created_at.desc())
        )

    enc_rows = (await db.scalars(query)).all()

    result = []
    for enc in enc_rows:
        patient = await db.get(Patient, enc.patient_id)
        patient_name = patient.full_name if patient else "Unknown"

        # Optional search filtering
        if search:
            s_lower = search.lower()
            match_name = patient_name and s_lower in patient_name.lower()
            match_complaint = enc.chief_complaint and s_lower in enc.chief_complaint.lower()
            if not (match_name or match_complaint):
                continue

        open_flags = await db.scalar(
            select(func.count(ReviewFlag.id)).where(
                ReviewFlag.encounter_id == enc.id, ReviewFlag.status == "open"
            )
        ) or 0
        open_conflicts = await db.scalar(
            select(func.count(Conflict.id)).where(
                Conflict.encounter_id == enc.id, Conflict.status == "open"
            )
        ) or 0
        summary = await db.scalar(
            select(CaseSummary).where(CaseSummary.encounter_id == enc.id)
        )
        readiness_score = summary.readiness_score if summary else None

        result.append(
            DashboardCaseOut(
                encounter_id=enc.id,
                patient_id=enc.patient_id,
                patient_name=patient_name,
                chief_complaint=enc.chief_complaint,
                status=enc.status.value if hasattr(enc.status, "value") else str(enc.status),
                started_at=enc.started_at,
                open_flags=open_flags,
                open_conflicts=open_conflicts,
                readiness_score=readiness_score,
                doctor_notes=enc.doctor_notes,
                reviewed_at=enc.reviewed_at,
            )
        )
    return result

