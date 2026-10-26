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
    document_type = Column(String(50), nullable=True)       # prescription | report | other
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


class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(Integer, primary_key=True, index=True)
    encounter_id = Column(Integer, ForeignKey("encounters.id"), nullable=False)
    rule_id = Column(String(50), nullable=True)              # e.g. "RULE-MED-DENIAL", "RULE-ALLERGY-CONFLICT"
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
    flag_type = Column(String(50), nullable=False)           # missing | conflict | unverified | other
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
    action = Column(String(100), nullable=False)          # e.g. LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT, ACCESS_DENIED
    resource_type = Column(String(100), nullable=True)    # e.g. auth, patient, encounter, document
    resource_id = Column(String(100), nullable=True)
    change_summary = Column(Text, nullable=True)
    ip_address = Column(String(100), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=_now)
