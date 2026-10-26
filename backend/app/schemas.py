"""
schemas.py
----------
Pydantic v2 request/response schemas.
Kept separate from ORM models so the API contract can evolve independently.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, EmailStr, field_validator, Field
import enum


# ── Shared ────────────────────────────────────────────────────────────────────

class OkResponse(BaseModel):
    ok: bool = True
    message: str = "success"


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    patient = "patient"
    staff = "staff"
    doctor = "doctor"
    admin = "admin"


class UserCreate(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    role: UserRole = UserRole.staff


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Patients ──────────────────────────────────────────────────────────────────

class PatientCreate(BaseModel):
    full_name: str
    user_id: Optional[int] = None
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    preferred_language: str = "English"

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("full_name must not be blank")
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("full_name must be at least 2 characters long")
        if len(clean) > 100:
            raise ValueError("full_name must not exceed 100 characters")
        return clean

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 125):
            raise ValueError("age must be between 0 and 125")
        return v

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            clean = v.strip()
            digits = "".join(ch for ch in clean if ch.isdigit())
            if len(digits) < 7 or len(digits) > 15:
                raise ValueError("contact_phone must contain between 7 and 15 digits")
            return clean
        return None


class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    preferred_language: Optional[str] = None


class PatientOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    full_name: str
    date_of_birth: Optional[str]
    age: Optional[int]
    gender: Optional[str]
    contact_phone: Optional[str]
    contact_email: Optional[str]
    preferred_language: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PatientListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[PatientOut]


# ── Encounters ────────────────────────────────────────────────────────────────

class EncounterStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    needs_review = "needs_review"
    reviewed = "reviewed"


class EncounterCreate(BaseModel):
    patient_id: int
    chief_complaint: Optional[str] = None
    consent_given: bool = False


class ConsentRequest(BaseModel):
    consent_given: bool = True


class EncounterUpdate(BaseModel):
    chief_complaint: Optional[str] = None
    status: Optional[EncounterStatus] = None
    consent_given: Optional[bool] = None
    consent_timestamp: Optional[datetime] = None


class EncounterOut(BaseModel):
    id: int
    patient_id: int
    chief_complaint: Optional[str]
    status: EncounterStatus
    consent_given: bool = False
    consent_timestamp: Optional[datetime] = None
    started_at: datetime
    completed_at: Optional[datetime]
    doctor_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PatientSelfRegisterRequest(BaseModel):
    full_name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    contact_phone: Optional[str] = None
    preferred_language: str = "English"
    chief_complaint: Optional[str] = None
    consent_given: bool = True

    @field_validator("full_name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("full_name must not be blank")
        clean = v.strip()
        if len(clean) < 2:
            raise ValueError("full_name must be at least 2 characters long")
        if len(clean) > 100:
            raise ValueError("full_name must not exceed 100 characters")
        return clean

    @field_validator("age")
    @classmethod
    def validate_age(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 125):
            raise ValueError("age must be between 0 and 125")
        return v

    @field_validator("contact_phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v.strip():
            clean = v.strip()
            digits = "".join(ch for ch in clean if ch.isdigit())
            if len(digits) < 7 or len(digits) > 15:
                raise ValueError("contact_phone must contain between 7 and 15 digits")
            return clean
        return None

    @field_validator("consent_given")
    @classmethod
    def validate_consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Informed consent is required for patient intake")
        return v


class PatientSelfRegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
    patient: PatientOut
    encounter: EncounterOut
    # Generated credentials, returned once so the patient can sign in again later
    username: str
    temporary_password: str


# ── Interview ─────────────────────────────────────────────────────────────────

class QuestionOut(BaseModel):
    id: int
    key: str
    label: Optional[str] = None
    section: Optional[str] = None
    text: str
    placeholder: Optional[str] = None
    help: Optional[str] = None
    answer_type: str
    choices: Optional[List[str]] = None
    group: Optional[str] = None
    is_required: bool = True
    order: int = 0
    because: Optional[str] = None
    skip_why: Optional[str] = None

    model_config = {"from_attributes": True}


class NextQuestionResponse(BaseModel):
    question: Optional[QuestionOut] = None
    progress: float           # 0.0 – 1.0
    is_complete: bool = False
    adaptive_note: Optional[str] = None
    answered_count: int = 0
    total_applicable: int = 0
    can_go_back: bool = False


class SubmitResponseRequest(BaseModel):
    question_key: str
    answer: str
    source: Optional[str] = "patient_reported"
    confirmation_status: Optional[str] = "confirmed"


class ResponseOut(BaseModel):
    id: int
    encounter_id: int
    question_key: str
    answer: Optional[str] = None
    source: str = "patient_reported"
    confirmation_status: str = "confirmed"
    answered_at: datetime

    model_config = {"from_attributes": True}


class ActivePathItem(BaseModel):
    key: str
    label: Optional[str] = None
    section: Optional[str] = None
    value: Optional[str] = None
    is_answered: bool = False
    because: Optional[str] = None


class SkippedPathItem(BaseModel):
    key: str
    label: Optional[str] = None
    skip_why: Optional[str] = None


class InterviewProgressOut(BaseModel):
    encounter_id: int
    total_questions: int
    answered_questions: int
    progress_percent: float
    is_complete: bool
    answered_keys: List[str]
    active_path: Optional[List[ActivePathItem]] = None
    skipped_questions: Optional[List[SkippedPathItem]] = None


class ReviewAnswerOut(BaseModel):
    question_key: str
    label: Optional[str] = None
    section: Optional[str] = None
    text: str
    answer: Optional[str] = None
    source: str = "patient_reported"
    confirmation_status: str = "confirmed"
    answered_at: datetime


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentStatus(str, enum.Enum):
    pending = "pending"
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    completed = "completed"
    needs_review = "needs_review"
    failed = "failed"
    reviewed = "reviewed"


class DocumentOut(BaseModel):
    id: int
    patient_id: int
    encounter_id: Optional[int]
    document_type: Optional[str]
    original_filename: str
    file_size_bytes: Optional[int]
    mime_type: Optional[str]
    status: DocumentStatus
    extracted_text: Optional[str] = None
    extracted_fields: Optional[Dict[str, Any]] = None
    extraction_confidence: Optional[float] = None
    is_verified: bool
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DocumentExtractionOut(BaseModel):
    document_id: int
    status: Optional[str] = "completed"
    extracted_text: Optional[str] = None
    extracted_fields: Optional[Dict[str, Any]] = None
    extraction_confidence: Optional[float] = None
    is_verified: bool = False
    processing_time_seconds: Optional[float] = None
    provenance_label: str = "document_extracted_unverified"

    model_config = {"from_attributes": True}



# ── Case Analysis ─────────────────────────────────────────────────────────────

class MissingField(BaseModel):
    field: str
    label: Optional[str] = None
    section: Optional[str] = None
    reason: str
    is_critical: bool
    status: str = "Not provided / unknown"


class SummaryFieldOut(BaseModel):
    key: str
    label: str
    value: str
    source: str = "patient_reported"
    source_label: str = "Patient reported"
    is_missing: bool = False
    details: Optional[str] = None


class SummarySectionOut(BaseModel):
    id: str
    title: str
    fields: List[SummaryFieldOut]


class MissingInformationOut(BaseModel):
    encounter_id: int
    missing_fields: List[MissingField]
    total_missing: int


class ConflictOut(BaseModel):
    id: int
    encounter_id: int
    rule_id: Optional[str] = None
    field: str
    source_a: str
    value_a: Optional[str]
    source_b: str
    value_b: Optional[str]
    description: Optional[str]
    status: str
    resolution_note: Optional[str] = None
    resolved_by: Optional[int] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ConflictResolveRequest(BaseModel):
    status: str = Field(..., pattern="^(resolved|dismissed)$")
    resolution_note: str = Field(..., min_length=2, max_length=1000)


class ReadinessOut(BaseModel):
    encounter_id: int
    score: float               # 0.0 – 1.0
    label: str                 # Not Ready | Partially Ready | Ready for Review
    factors: Dict[str, Any]
    disclaimer: str = (
        "This score reflects case data completeness only. "
        "It is NOT a measure of diagnostic accuracy or patient health."
    )


class CaseSummaryOut(BaseModel):
    encounter_id: int
    summary_text: Optional[str]
    sections: Optional[List[SummarySectionOut]] = None
    structured_findings: Optional[List[SummaryFieldOut]] = None
    readiness_score: Optional[float] = None
    readiness_factors: Optional[Dict[str, Any]] = None
    missing_fields: Optional[List[MissingField]] = None
    review_status: str
    doctor_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    generated_at: datetime

    model_config = {"from_attributes": True}


class DoctorNotesRequest(BaseModel):
    doctor_notes: str = Field(..., max_length=10000, description="Clinician review notes and observations")


class FinalizeCaseRequest(BaseModel):
    doctor_notes: Optional[str] = Field(None, max_length=10000, description="Optional clinician review notes to save on finalization")


class FinalizeCaseOut(BaseModel):
    encounter_id: int
    status: str
    review_status: str
    doctor_notes: Optional[str] = None
    reviewed_at: datetime
    reviewed_by: Optional[int] = None


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardSummaryOut(BaseModel):
    total_patients: int
    active_encounters: int
    completed_cases: int
    cases_needing_review: int


class DashboardCaseOut(BaseModel):
    encounter_id: int
    patient_name: str
    chief_complaint: Optional[str]
    status: str
    started_at: datetime
    open_flags: int
    open_conflicts: int
    patient_id: Optional[int] = None
    readiness_score: Optional[float] = None
    doctor_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None


class AuditEventOut(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_username: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    change_summary: Optional[str] = None
    ip_address: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}
