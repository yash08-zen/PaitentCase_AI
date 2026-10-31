"""
models.py
---------
SQLAlchemy ORM models for every entity in the system.
All tables use integer surrogate PKs for simplicity; UUIDs can be added later.
Timestamps default to the current UTC time at row creation.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, String, Text, Float, JSON
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


def _now():
    return datetime.now(timezone.utc)


# ── Enumerations ──────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    patient = "patient"
    staff = "staff"
    doctor = "doctor"
    admin = "admin"


class EncounterStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    needs_review = "needs_review"
    reviewed = "reviewed"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    uploaded = "uploaded"
    processing = "processing"
    processed = "processed"
    completed = "completed"
    needs_review = "needs_review"
    failed = "failed"
    reviewed = "reviewed"


class ConflictStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"
    dismissed = "dismissed"


class FlagStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"


class AIInsightStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    edited = "edited"
    rejected = "rejected"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    unavailable = "unavailable"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.staff, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    patient = relationship("Patient", back_populates="user", uselist=False)


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(String(20), nullable=True)   # stored as ISO date string
    age = Column(Integer, nullable=True)
    gender = Column(String(50), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    contact_email = Column(String(255), nullable=True)
    preferred_language = Column(String(50), default="English")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    user = relationship("User", back_populates="patient")
    encounters = relationship("Encounter", back_populates="patient", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="patient", cascade="all, delete-orphan")


class Encounter(Base):
    __tablename__ = "encounters"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    chief_complaint = Column(Text, nullable=True)
    status = Column(Enum(EncounterStatus), default=EncounterStatus.pending)
    consent_given = Column(Boolean, default=False, nullable=False)
    consent_timestamp = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), default=_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    doctor_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    patient = relationship("Patient", back_populates="encounters")
    responses = relationship("Response", back_populates="encounter", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="encounter")
    conflicts = relationship("Conflict", back_populates="encounter", cascade="all, delete-orphan")
    review_flags = relationship("ReviewFlag", back_populates="encounter", cascade="all, delete-orphan")
    case_summary = relationship("CaseSummary", back_populates="encounter", uselist=False, cascade="all, delete-orphan")

    # AI Clinical Insights Layer additions
    ai_insights = relationship("AIInsight", back_populates="encounter", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="encounter", cascade="all, delete-orphan")
    document_entities = relationship("DocumentEntity", back_populates="encounter", cascade="all, delete-orphan")
    trend_flags = relationship("TrendFlag", back_populates="encounter", cascade="all, delete-orphan")
    risk_scores = relationship("RiskScore", back_populates="encounter", cascade="all, delete-orphan")
    llm_jobs = relationship("LLMJob", back_populates="encounter", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)   # machine-readable identifier
    label = Column(String(100), nullable=True)                # short display label
    section = Column(String(100), nullable=True)              # display section (e.g. Symptoms, Medication)
    text = Column(Text, nullable=False)                       # patient-facing text
    placeholder = Column(String(200), nullable=True)          # input placeholder
    help = Column(Text, nullable=True)                        # patient help hint
    answer_type = Column(String(30), nullable=False)          # text | choice | multi | scale | number | date
    choices = Column(JSON, nullable=True)                     # list of choice strings for choice/multi
    order = Column(Integer, default=0)                        # display order within a group
    group = Column(String(100), nullable=True)                # logical group (e.g. symptoms, history)
    is_required = Column(Boolean, default=True)
    branching_rules = Column(JSON, nullable=True)             # list of rule dicts (see adaptive_engine)
    conditions = Column(JSON, nullable=True)                  # conditions under which this Q is shown
    because = Column(Text, nullable=True)                     # why follow-up was triggered
    skip_why = Column(Text, nullable=True)                    # why question was skipped
    created_at = Column(DateTime(timezone=True), default=_now)

    responses = relationship("Response", back_populates="question")


class Response(Base):
    __tablename__ = "responses"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    question_key = Column(String(100), nullable=False)
    answer = Column(Text, nullable=True)
    source = Column(String(50), default="patient_reported", nullable=False)
    confirmation_status = Column(String(50), default="confirmed", nullable=False)
    answered_at = Column(DateTime(timezone=True), default=_now)

    encounter = relationship("Encounter", back_populates="responses")
    question = relationship("Question", back_populates="responses")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=True)
    document_type = Column(String(50), nullable=True)       # prescription | lab_report | discharge_summary | imaging_report | other
    original_filename = Column(String(255), nullable=False)
    stored_path = Column(String(500), nullable=False)        # relative path under UPLOAD_DIR
    file_size_bytes = Column(Integer, nullable=True)
    mime_type = Column(String(100), nullable=True)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.uploaded)
    extracted_text = Column(Text, nullable=True)
    extracted_fields = Column(JSON, nullable=True)           # structured extraction results
    extraction_confidence = Column(Float, nullable=True)
    is_verified = Column(Boolean, default=False)
    uploaded_at = Column(DateTime(timezone=True), default=_now)
    processed_at = Column(DateTime(timezone=True), nullable=True)

    patient = relationship("Patient", back_populates="documents")
    encounter = relationship("Encounter", back_populates="documents")
    entities = relationship("DocumentEntity", back_populates="document", cascade="all, delete-orphan")
    lab_results = relationship("LabResult", back_populates="document", cascade="all, delete-orphan")


class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False)
    rule_id = Column(String(50), nullable=True)              # e.g. "RULE-MED-DENIAL", "RULE-ALLERGY-CONFLICT", "RULE-INTERACTION", "RULE-LAB-ABNORMAL", "RULE-DIAGNOSIS-DENIAL", "RULE-WRONG-PATIENT"
    field = Column(String(100), nullable=False)              # which data field conflicts
    source_a = Column(String(100), nullable=False)           # e.g. "patient_reported"
    value_a = Column(Text, nullable=True)
    source_b = Column(String(100), nullable=False)           # e.g. "document_extracted_unverified"
    value_b = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    status = Column(Enum(ConflictStatus), default=ConflictStatus.open)
    resolution_note = Column(Text, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    encounter = relationship("Encounter", back_populates="conflicts")
    resolver = relationship("User", foreign_keys=[resolved_by])


class ReviewFlag(Base):
    __tablename__ = "review_flags"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False)
    flag_type = Column(String(50), nullable=False)           # missing | conflict | unverified | red_flag | other
    description = Column(Text, nullable=False)
    status = Column(Enum(FlagStatus), default=FlagStatus.open)
    created_at = Column(DateTime(timezone=True), default=_now)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    encounter = relationship("Encounter", back_populates="review_flags")


class CaseSummary(Base):
    __tablename__ = "case_summaries"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), unique=True, nullable=False)
    summary_text = Column(Text, nullable=True)
    readiness_score = Column(Float, nullable=True)           # 0.0 – 1.0
    readiness_factors = Column(JSON, nullable=True)
    review_status = Column(String(30), default="pending")    # pending | reviewed | approved
    generated_at = Column(DateTime(timezone=True), default=_now)
    doctor_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    encounter = relationship("Encounter", back_populates="case_summary")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_username = Column(String(100), nullable=True)
    actor_role = Column(String(50), nullable=True)
    action = Column(String(100), nullable=False)          # e.g. LOGIN_SUCCESS, AI_ANALYSIS_STARTED, AI_INSIGHT_ACCEPTED, etc.
    resource_type = Column(String(100), nullable=True)    # e.g. auth, patient, encounter, document, ai_insight
    resource_id = Column(String(100), nullable=True)
    change_summary = Column(Text, nullable=True)
    ip_address = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_now)


# ── AI Clinical Insights Layer Tables ──────────────────────────────────────────

class AIInsight(Base):
    """
    Stores individual AI proposals (disease considerations, treatment references,
    summary suggestions, trend interpretations, follow-ups).
    Provenance starts as 'ai_generated_unverified' and transitions to 'doctor_verified'
    only after clinician Accept / Edit.
    """
    __tablename__ = "ai_insights"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False, index=True)
    insight_type = Column(String(100), nullable=False)  # disease_consideration | treatment_reference | trend_interpretation | case_summary | questions_to_ask | risk_score_interpretation
    content = Column(JSON, nullable=False)              # Structured insight data
    evidence = Column(JSON, nullable=True)              # Source citations, spans, question keys
    status = Column(Enum(AIInsightStatus), default=AIInsightStatus.pending, nullable=False)
    provenance = Column(String(100), default="ai_generated_unverified", nullable=False)
    model_name = Column(String(100), nullable=True)
    prompt_version = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    decided_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    doctor_edits = Column(JSON, nullable=True)

    encounter = relationship("Encounter", back_populates="ai_insights")
    decider = relationship("User", foreign_keys=[decided_by])


class LabResult(Base):
    """
    Structured laboratory rows extracted from lab documents and flagged deterministically.
    """
    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)
    test_name = Column(String(150), nullable=False)
    normalized_test = Column(String(150), nullable=False, index=True)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    ref_low = Column(Float, nullable=True)
    ref_high = Column(Float, nullable=True)
    flag = Column(String(50), nullable=True)  # normal | low | high | critical_low | critical_high | range_not_available
    test_date = Column(String(50), nullable=True)
    source_span = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    encounter = relationship("Encounter", back_populates="lab_results")
    document = relationship("Document", back_populates="lab_results")


class DocumentEntity(Base):
    """
    Grounding-validated entity extracted from medical documents.
    """
    __tablename__ = "document_entities"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # diagnosis | medication | procedure | date | doctor | facility
    value = Column(JSON, nullable=False)
    raw_text = Column(Text, nullable=True)
    source_span = Column(String(255), nullable=True)
    grounded = Column(Boolean, default=True, nullable=False)
    confidence = Column(Float, nullable=True)
    provenance = Column(String(50), default="document_extracted_unverified", nullable=False)
    review_status = Column(String(50), nullable=True)  # grounded | needs_review | read_from_handwriting_verify | regex_disagreement
    created_at = Column(DateTime(timezone=True), default=_now)

    document = relationship("Document", back_populates="entities")
    encounter = relationship("Encounter", back_populates="document_entities")


class TrendFlag(Base):
    """
    Computed clinical lab trend across historical dates.
    """
    __tablename__ = "trend_flags"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False, index=True)
    test_name = Column(String(150), nullable=False)
    previous_value = Column(Float, nullable=False)
    current_value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    delta = Column(Float, nullable=False)
    percent_change = Column(Float, nullable=False)
    direction = Column(String(20), nullable=False)  # rising | falling | stable
    time_span_days = Column(Integer, nullable=True)
    rule_matched = Column(String(100), nullable=True)
    clinical_label = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    encounter = relationship("Encounter", back_populates="trend_flags")


class RiskScore(Base):
    """
    Deterministically calculated clinical risk and severity scores (qSOFA, CURB-65, NEWS2, CHA2DS2-VASc).
    """
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False, index=True)
    score_name = Column(String(100), nullable=False)
    score_value = Column(Float, nullable=True)
    status = Column(String(50), default="calculated", nullable=False)  # calculated | not_calculable
    inputs = Column(JSON, nullable=True)
    missing_inputs = Column(JSON, nullable=True)
    formula_version = Column(String(50), nullable=False)
    interpretation = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    encounter = relationship("Encounter", back_populates="risk_scores")


class GuidelinePassage(Base):
    """
    Local reference library for treatment guidelines.
    Only retrieved passages may be quoted for dosage guidance.
    """
    __tablename__ = "guideline_passages"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(255), nullable=False)
    version_date = Column(String(50), nullable=False)
    condition_or_topic = Column(String(150), nullable=False, index=True)
    section = Column(String(150), nullable=False)
    passage_text = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)
    is_sample = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)


class LLMJob(Base):
    """
    Background job tracker for asynchronous AI inference workflows.
    """
    __tablename__ = "llm_jobs"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False, index=True)
    job_type = Column(String(100), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.pending, nullable=False)
    progress = Column(Float, default=0.0, nullable=False)
    error_message = Column(Text, nullable=True)
    usage = Column(JSON, nullable=True)   # per-call provider/model/tokens/latency (no clinical text)
    notes = Column(JSON, nullable=True)   # validation and degradation notes
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    encounter = relationship("Encounter", back_populates="llm_jobs")
