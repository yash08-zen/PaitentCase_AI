"""
main.py
-------
FastAPI application entry point.

Startup sequence:
  1. Create all DB tables.
  2. Seed the question bank (idempotent).
  3. Create a default admin account if none exists.

All business logic lives in routers/ and services/.
"""
from datetime import datetime, timezone
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database import init_db, AsyncSessionLocal, get_db
from app.models import Question, User, Patient, Encounter, EncounterStatus
from app.core.security import hash_password
from app.services.adaptive_engine import QUESTION_BANK
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.logging_config import RequestLoggingMiddleware
from app.core.error_handlers import register_error_handlers

from app.routers import auth, patients, encounters, interviews, documents, dashboard, encounters_analysis, conflicts, system, voice


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    await init_db()
    await seed_questions()
    await ensure_default_admin()
    yield
    # Shutdown (nothing to clean up for SQLite)


async def seed_questions():
    """Insert or update question-bank entries from canonical configuration (idempotent)."""
    async with AsyncSessionLocal() as db:
        for q_data in QUESTION_BANK:
            exists = await db.scalar(select(Question).where(Question.key == q_data["key"]))
            if not exists:
                question = Question(
                    key=q_data["key"],
                    label=q_data.get("label"),
                    section=q_data.get("section"),
                    text=q_data["text"],
                    placeholder=q_data.get("placeholder"),
                    help=q_data.get("help"),
                    answer_type=q_data["answer_type"],
                    choices=q_data.get("choices"),
                    order=q_data.get("order", 0),
                    group=q_data.get("group"),
                    is_required=q_data.get("is_required", True),
                    branching_rules=q_data.get("branching_rules"),
                    conditions=q_data.get("conditions"),
                    because=q_data.get("because"),
                    skip_why=q_data.get("skip_why"),
                )
                db.add(question)
            else:
                exists.label = q_data.get("label")
                exists.section = q_data.get("section")
                exists.text = q_data["text"]
                exists.placeholder = q_data.get("placeholder")
                exists.help = q_data.get("help")
                exists.answer_type = q_data["answer_type"]
                exists.choices = q_data.get("choices")
                exists.order = q_data.get("order", 0)
                exists.group = q_data.get("group")
                exists.is_required = q_data.get("is_required", True)
                exists.branching_rules = q_data.get("branching_rules")
                exists.conditions = q_data.get("conditions")
                exists.because = q_data.get("because")
                exists.skip_why = q_data.get("skip_why")
        await db.commit()
    print(f"[startup] Question bank synchronized ({len(QUESTION_BANK)} questions).")


async def ensure_default_admin():
    """Create a default admin account for first-run development use.
    IMPORTANT: Change the password immediately in any shared environment.
    """
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.username == "admin"))
        if not existing:
            admin = User(
                username="admin",
                email="admin@patientcase.local",
                password_hash=hash_password("Admin@1234"),
                role="admin",
            )
            db.add(admin)
            await db.commit()
            print("[startup] Default admin user created (username: admin, password: Admin@1234).")
        # Also seed a demo doctor account
        doctor = await db.scalar(select(User).where(User.username == "doctor"))
        if not doctor:
            doc_user = User(
                username="doctor",
                email="doctor@patientcase.local",
                password_hash=hash_password("Doctor@1234"),
                role="doctor",
            )
            db.add(doc_user)
            # Seed a demo staff account
            staff = User(
                username="staff",
                email="staff@patientcase.local",
                password_hash=hash_password("Staff@1234"),
                role="staff",
            )
            db.add(staff)
            await db.commit()

        # Seed a demo patient account
        patient_user = await db.scalar(select(User).where(User.username == "patient"))
        if not patient_user:
            patient_user = User(
                username="patient",
                email="patient@patientcase.local",
                password_hash=hash_password("Patient@1234"),
                role="patient",
            )
            db.add(patient_user)
            await db.commit()
            await db.refresh(patient_user)

        demo_patient = await db.scalar(select(Patient).where(Patient.user_id == patient_user.id))
        if not demo_patient:
            demo_patient = Patient(
                user_id=patient_user.id,
                full_name="Ramesh Kumar (Demo Patient)",
                age=54,
                gender="Male",
                contact_phone="9876543210",
                preferred_language="English",
            )
            db.add(demo_patient)
            await db.flush()
            demo_enc = Encounter(
                patient_id=demo_patient.id,
                chief_complaint="Severe headache and occasional dizziness for 3 days",
                status=EncounterStatus.in_progress,
                consent_given=True,
                consent_timestamp=datetime.now(timezone.utc),
            )
            db.add(demo_enc)
            await db.commit()
            print("[startup] Demo patient record and encounter linked to user 'patient'.")
        print("[startup] Demo accounts verified (admin, doctor, staff, patient).")


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="PatientCase AI",
    description=(
        "Adaptive Patient Case-Taking and Clinical Handoff System. "
        "This system assists with information collection and organization. "
        "It does NOT diagnose diseases, prescribe medicines, or replace clinical judgment."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Centralized exception handlers (safe 500s, structured 422s)
register_error_handlers(app)

# Defensive security headers
app.add_middleware(SecurityHeadersMiddleware)

# Structured request logger with PII masking
app.add_middleware(RequestLoggingMiddleware)

# Restricted CORS policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "X-Test-Bypass-Rate-Limit"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(encounters.router)
app.include_router(encounters_analysis.router)
app.include_router(interviews.router)
app.include_router(documents.router)
app.include_router(dashboard.router)
app.include_router(conflicts.router)
app.include_router(system.router)
app.include_router(voice.router)


# ── Root endpoints ────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {
        "name": "PatientCase AI API",
        "version": "1.0.0",
        "description": "Adaptive patient case-taking and clinical handoff system",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", tags=["Root"])
@app.get("/api/health", tags=["Root"])
async def health(db: AsyncSession = Depends(get_db)):
    db_status = "connected"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unreachable: {str(exc)}"

    is_healthy = db_status == "connected"
    return {
        "status": "healthy" if is_healthy else "degraded",
        "app": "healthy",
        "database": db_status,
        "service": "PatientCase AI",
        "environment": settings.APP_ENV,
    }

