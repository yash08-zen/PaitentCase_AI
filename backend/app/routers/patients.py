"""
routers/patients.py
-------------------
CRUD endpoints for patient records.
List supports basic search by name and pagination.
Role permissions:
  - list, create, update: staff, doctor, admin
  - get: staff, doctor, admin, patient
"""
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import uuid
from app.database import get_db
from app.models import Patient, User, Encounter, EncounterStatus, UserRole
from app.schemas import (
    PatientCreate, PatientOut, PatientUpdate, PatientListOut,
    PatientSelfRegisterRequest, PatientSelfRegisterResponse,
    EncounterOut, UserOut
)
from app.core.security import hash_password, create_access_token
from app.dependencies import get_current_user, require_roles
from app.services.audit import log_audit_event

router = APIRouter(prefix="/api/patients", tags=["Patients"])


@router.post("/self-register", response_model=PatientSelfRegisterResponse, status_code=status.HTTP_201_CREATED)
async def self_register_patient(
    payload: PatientSelfRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public self-registration endpoint for new hospital patients.
    1. Provisions a dedicated patient user account
    2. Creates patient record with demographics, contact, and language preference
    3. Initiates an encounter with consent timestamp and chief complaint
    4. Issues a JWT access token for immediate adaptive interview & document upload access
    """
    if not payload.consent_given:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informed consent is required before registering as a new patient.",
        )

    # 1. Create a unique patient user account
    username_suffix = uuid.uuid4().hex[:8]
    unique_username = f"patient_{username_suffix}"
    temp_password = f"Patient@{username_suffix}"

    user = User(
        username=unique_username,
        email=None,
        password_hash=hash_password(temp_password),
        role=UserRole.patient,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    # 2. Create Patient profile linked to this user
    patient = Patient(
        user_id=user.id,
        full_name=payload.full_name,
        age=payload.age,
        gender=payload.gender,
        contact_phone=payload.contact_phone,
        preferred_language=payload.preferred_language or "English",
    )
    db.add(patient)
    await db.flush()

    # 3. Create initial intake encounter with informed consent
    now = datetime.now(timezone.utc)
    encounter = Encounter(
        patient_id=patient.id,
        chief_complaint=payload.chief_complaint,
        status=EncounterStatus.in_progress,
        consent_given=True,
        consent_timestamp=now,
        started_at=now,
    )
    db.add(encounter)
    await db.commit()
    await db.refresh(user)
    await db.refresh(patient)
    await db.refresh(encounter)

    # 4. Generate JWT access token with role 'patient'
    # "sub" must be the numeric user id, matching /api/auth/login and get_current_user()
    token = create_access_token({"sub": str(user.id), "role": user.role.value})

    await log_audit_event(
        db,
        action="PATIENT_SELF_REGISTERED",
        actor=user,
        resource_type="patient",
        resource_id=str(patient.id),
        change_summary=f"New patient self-registered: {patient.full_name} (Encounter #{encounter.id})",
    )

    return PatientSelfRegisterResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
        patient=PatientOut.model_validate(patient),
        encounter=EncounterOut.model_validate(encounter),
        username=unique_username,
        temporary_password=temp_password,
    )


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
async def create_patient(
    payload: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin")),
):
    # Idempotency / duplicate submission protection (e.g. double-click)
    fifteen_sec_ago = datetime.now(timezone.utc) - timedelta(seconds=15)
    recent_dup = await db.scalar(
        select(Patient).where(
            Patient.full_name == payload.full_name,
            Patient.created_at >= fifteen_sec_ago,
        )
    )
    if recent_dup:
        return recent_dup

    patient = Patient(**payload.model_dump())
    db.add(patient)
    await db.commit()
    await db.refresh(patient)

    await log_audit_event(
        db,
        action="PATIENT_CREATED",
        actor=current_user,
        resource_type="patient",
        resource_id=str(patient.id),
        change_summary=f"Patient registered: {patient.full_name}",
    )
    return patient


@router.get("/me", response_model=PatientOut)
async def get_my_patient_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("patient")),
):
    """Retrieve current logged in patient's profile."""
    patient = await db.scalar(select(Patient).where(Patient.user_id == current_user.id))
    if not patient:
        raise HTTPException(status_code=404, detail="Patient profile not found for current user")
    return patient


@router.get("", response_model=PatientListOut)
async def list_patients(
    search: Optional[str] = Query(None, description="Filter by name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin")),
):
    query = select(Patient)
    if search:
        query = query.where(Patient.full_name.ilike(f"%{search}%"))

    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    patients = (
        await db.scalars(
            query.offset((page - 1) * page_size).limit(page_size).order_by(Patient.created_at.desc())
        )
    ).all()

    return PatientListOut(total=total or 0, page=page, page_size=page_size, items=list(patients))


@router.get("/{patient_id}", response_model=PatientOut)
async def get_patient(
    patient_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin", "patient")),
):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Record-level access: patient can only view their own record
    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        if patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only access their own record",
            )
    return patient


@router.put("/{patient_id}", response_model=PatientOut)
async def update_patient(
    patient_id: int,
    payload: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("staff", "doctor", "admin")),
):
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)
    await db.commit()
    await db.refresh(patient)

    await log_audit_event(
        db,
        action="PATIENT_UPDATED",
        actor=current_user,
        resource_type="patient",
        resource_id=str(patient.id),
        change_summary=f"Patient details updated for {patient.full_name}",
    )
    return patient
