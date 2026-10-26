"""
routers/encounters.py
---------------------
Encounter lifecycle management: create, list, retrieve, update.
Role permissions:
  - list all: staff, doctor, admin
  - create, get: staff, doctor, admin, patient
  - update: staff, doctor, admin
"""
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Encounter, Patient, User, EncounterStatus, CaseSummary
from app.schemas import (
    EncounterCreate, EncounterOut, EncounterUpdate, ConsentRequest,
    DoctorNotesRequest, FinalizeCaseRequest, FinalizeCaseOut
)
from app.dependencies import get_current_user, require_roles
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/encounters", tags=["Encounters"])


@router.post("", response_model=EncounterOut, status_code=status.HTTP_201_CREATED)
async def create_encounter(
    payload: EncounterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin", "patient")),
):
    patient = await db.get(Patient, payload.patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        if patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only create encounters for their own record",
            )

    # Idempotency / duplicate submission protection (e.g. double-click)
    fifteen_sec_ago = datetime.now(timezone.utc) - timedelta(seconds=15)
    recent_enc = await db.scalar(
        select(Encounter).where(
            Encounter.patient_id == payload.patient_id,
            Encounter.chief_complaint == payload.chief_complaint,
            Encounter.created_at >= fifteen_sec_ago,
        )
    )
    if recent_enc:
        return recent_enc

    enc_dict = payload.model_dump()
    if payload.consent_given:
        enc_dict["consent_given"] = True
        enc_dict["consent_timestamp"] = datetime.now(timezone.utc)

    encounter = Encounter(**enc_dict)
    db.add(encounter)
    await db.commit()
    await db.refresh(encounter)

    await log_audit_event(
        db,
        action="ENCOUNTER_CREATED",
        actor=current_user,
        resource_type="encounter",
        resource_id=str(encounter.id),
        change_summary=f"Encounter created for patient {patient.full_name}",
    )
    return encounter


@router.get("", response_model=List[EncounterOut])
async def list_encounters(
    patient_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin", "patient")),
):
    query = select(Encounter).order_by(Encounter.created_at.desc())
    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        query = query.join(Patient, Encounter.patient_id == Patient.id).where(Patient.user_id == current_user.id)
    else:
        if patient_id:
            query = query.where(Encounter.patient_id == patient_id)
    if status:
        query = query.where(Encounter.status == status)
    return (await db.scalars(query)).all()


@router.get("/{encounter_id}", response_model=EncounterOut)
async def get_encounter(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin", "patient")),
):
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        patient = await db.get(Patient, enc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only access their own encounters",
            )
    return enc


@router.put("/{encounter_id}", response_model=EncounterOut)
async def update_encounter(
    encounter_id: int,
    payload: EncounterUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin")),
):
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(enc, field, value)
    await db.commit()
    await db.refresh(enc)

    await log_audit_event(
        db,
        action="ENCOUNTER_UPDATED",
        actor=current_user,
        resource_type="encounter",
        resource_id=str(enc.id),
        change_summary=f"Encounter {enc.id} updated to status {enc.status}",
    )
    return enc



@router.post("/{encounter_id}/consent", response_model=EncounterOut)
async def record_consent(
    encounter_id: int,
    payload: ConsentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin", "patient")),
):
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        patient = await db.get(Patient, enc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only record consent for their own encounters",
            )

    enc.consent_given = payload.consent_given
    enc.consent_timestamp = datetime.now(timezone.utc) if payload.consent_given else None
    await db.commit()
    await db.refresh(enc)

    await log_audit_event(
        db,
        action="CONSENT_RECORDED",
        actor=current_user,
        resource_type="encounter",
        resource_id=str(enc.id),
        change_summary=f"Consent {'granted' if payload.consent_given else 'revoked'} for encounter {enc.id}",
    )
    return enc


@router.put("/{encounter_id}/notes", response_model=EncounterOut)
async def update_doctor_notes(
    encounter_id: int,
    payload: DoctorNotesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """
    Clinician records/updates observations, corrections, and review notes for an encounter.
    Audited with DOCTOR_NOTES_UPDATED.
    """
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    enc.doctor_notes = payload.doctor_notes

    # Mirror notes to CaseSummary if existing or create
    cs = await db.scalar(select(CaseSummary).where(CaseSummary.encounter_id == encounter_id))
    if cs:
        cs.doctor_notes = payload.doctor_notes
    else:
        cs = CaseSummary(
            encounter_id=encounter_id,
            doctor_notes=payload.doctor_notes,
            review_status="pending",
        )
        db.add(cs)

    await db.commit()
    await db.refresh(enc)

    await log_audit_event(
        db,
        action="DOCTOR_NOTES_UPDATED",
        actor=current_user,
        resource_type="encounter",
        resource_id=str(enc.id),
        change_summary=f"Doctor notes updated for encounter {enc.id} by {current_user.username}",
    )
    return enc


@router.get("/{encounter_id}/notes")
async def get_doctor_notes(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "staff", "admin", "patient")),
):
    """Retrieve clinician review notes for an encounter."""
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        patient = await db.get(Patient, enc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only access notes for their own encounters",
            )

    return {
        "encounter_id": enc.id,
        "doctor_notes": enc.doctor_notes,
        "reviewed_at": enc.reviewed_at,
        "reviewed_by": enc.reviewed_by,
        "status": enc.status.value if hasattr(enc.status, "value") else str(enc.status),
    }


@router.post("/{encounter_id}/finalize", response_model=FinalizeCaseOut)
async def finalize_encounter(
    encounter_id: int,
    payload: Optional[FinalizeCaseRequest] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """
    Clinician finalizes review of an intake case.
    Transitions encounter status to 'reviewed', sets reviewed_at & reviewed_by,
    and locks interview responses from further patient edits.
    Audited with CASE_FINALIZED.
    """
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    now = datetime.now(timezone.utc)
    enc.status = EncounterStatus.reviewed
    enc.reviewed_at = now
    enc.reviewed_by = current_user.id
    if not enc.completed_at:
        enc.completed_at = now
    if payload and payload.doctor_notes:
        enc.doctor_notes = payload.doctor_notes

    # Mirror to CaseSummary
    cs = await db.scalar(select(CaseSummary).where(CaseSummary.encounter_id == encounter_id))
    if cs:
        cs.review_status = "reviewed"
        cs.reviewed_at = now
        cs.reviewed_by = current_user.id
        if payload and payload.doctor_notes:
            cs.doctor_notes = payload.doctor_notes
    else:
        cs = CaseSummary(
            encounter_id=encounter_id,
            review_status="reviewed",
            reviewed_at=now,
            reviewed_by=current_user.id,
            doctor_notes=payload.doctor_notes if payload else None,
        )
        db.add(cs)

    await db.commit()
    await db.refresh(enc)

    await log_audit_event(
        db,
        action="CASE_FINALIZED",
        actor=current_user,
        resource_type="encounter",
        resource_id=str(enc.id),
        change_summary=f"Case finalized for encounter {enc.id} by Dr. {current_user.username}",
    )

    return FinalizeCaseOut(
        encounter_id=enc.id,
        status="reviewed",
        review_status="reviewed",
        doctor_notes=enc.doctor_notes,
        reviewed_at=now,
        reviewed_by=current_user.id,
    )

