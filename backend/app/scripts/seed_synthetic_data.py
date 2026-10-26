"""
scripts/seed_synthetic_data.py
------------------------------
Idempotent script to seed synthetic data for development and testing:
  - Users: admin, doctor, staff
  - Questions: 16 adaptive questions
  - Synthetic patients with realistic encounters and sample responses
"""
import asyncio
from sqlalchemy import select
from app.database import init_db, AsyncSessionLocal
from app.models import User, Patient, Encounter, Question, Response, UserRole, EncounterStatus
from app.core.security import hash_password
from app.services.adaptive_engine import QUESTION_BANK


DEMO_USERS = [
    {"username": "admin", "email": "admin@patientcase.local", "password": "Admin@1234", "role": UserRole.admin},
    {"username": "doctor", "email": "doctor@patientcase.local", "password": "Doctor@1234", "role": UserRole.doctor},
    {"username": "staff", "email": "staff@patientcase.local", "password": "Staff@1234", "role": UserRole.staff},
    {"username": "patient", "email": "patient@patientcase.local", "password": "Patient@1234", "role": UserRole.patient},
]

SYNTHETIC_PATIENTS = [
    {
        "full_name": "Ramesh Kumar",
        "age": 54,
        "gender": "Male",
        "contact_phone": "9876543210",
        "contact_email": "ramesh.kumar@example.com",
        "preferred_language": "English",
        "encounter": {
            "chief_complaint": "Severe headache and occasional dizziness for 3 days",
            "status": EncounterStatus.in_progress,
        },
        "responses": [
            {"key": "chief_complaint", "answer": "Severe headache and occasional dizziness for 3 days"},
            {"key": "symptom_duration", "answer": "3 days"},
            {"key": "pain_severity", "answer": "7"},
        ]
    },
    {
        "full_name": "Sunita Patil",
        "age": 42,
        "gender": "Female",
        "contact_phone": "9823456789",
        "contact_email": "sunita.patil@example.com",
        "preferred_language": "Hindi",
        "encounter": {
            "chief_complaint": "Persistent dry cough and mild fever in evenings",
            "status": EncounterStatus.completed,
        },
        "responses": [
            {"key": "chief_complaint", "answer": "Persistent dry cough and mild evening fever"},
            {"key": "symptom_duration", "answer": "1 week"},
            {"key": "fever_present", "answer": "Yes"},
            {"key": "current_medications", "answer": "None"},
            {"key": "known_allergies", "answer": "Penicillin"},
        ]
    },
    {
        "full_name": "Rajesh Sharma",
        "age": 36,
        "gender": "Male",
        "contact_phone": "9811223344",
        "contact_email": "rajesh.sharma@example.com",
        "preferred_language": "English",
        "encounter": {
            "chief_complaint": "Chest tightness and shortness of breath after brisk walking",
            "status": EncounterStatus.pending,
        },
        "responses": []
    }
]


async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:
        # 1. Seed Questions
        q_count = 0
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
                q_count += 1
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
        print(f"[seed] Questions seeded & synchronized: {len(QUESTION_BANK)} total in bank")

        # 2. Seed Users
        u_count = 0
        for u in DEMO_USERS:
            exists = await db.scalar(select(User).where(User.username == u["username"]))
            if not exists:
                user = User(
                    username=u["username"],
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                )
                db.add(user)
                u_count += 1
        await db.commit()
        print(f"[seed] Users seeded: {u_count} new")

        # 3. Seed Synthetic Patients & Encounters
        p_count = 0
        for p_data in SYNTHETIC_PATIENTS:
            exists = await db.scalar(select(Patient).where(Patient.full_name == p_data["full_name"]))
            if not exists:
                patient = Patient(
                    full_name=p_data["full_name"],
                    age=p_data["age"],
                    gender=p_data["gender"],
                    contact_phone=p_data["contact_phone"],
                    contact_email=p_data["contact_email"],
                    preferred_language=p_data["preferred_language"],
                )
                db.add(patient)
                await db.flush()

                enc_data = p_data["encounter"]
                encounter = Encounter(
                    patient_id=patient.id,
                    chief_complaint=enc_data["chief_complaint"],
                    status=enc_data["status"],
                    consent_given=True,
                )
                db.add(encounter)
                await db.flush()

                for r in p_data["responses"]:
                    q = await db.scalar(select(Question).where(Question.key == r["key"]))
                    if q:
                        resp = Response(
                            encounter_id=encounter.id,
                            question_id=q.id,
                            question_key=r["key"],
                            answer=r["answer"],
                        )
                        db.add(resp)
                p_count += 1

        await db.commit()
        print(f"[seed] Synthetic patients and encounters seeded: {p_count} new")

        # Ensure all seeded encounters have consent_given=True
        encs = (await db.scalars(select(Encounter))).all()
        for e in encs:
            if not e.consent_given:
                e.consent_given = True
        await db.commit()

        # Ensure demo patient user is linked to Rajesh Sharma for record-level testing
        patient_user = await db.scalar(select(User).where(User.username == "patient"))
        if patient_user:
            rajesh = await db.scalar(select(Patient).where(Patient.full_name == "Rajesh Sharma"))
            if rajesh and rajesh.user_id != patient_user.id:
                rajesh.user_id = patient_user.id
                await db.commit()
                print(f"[seed] Linked patient user {patient_user.username} to patient ID {rajesh.id} ({rajesh.full_name})")


if __name__ == "__main__":
    asyncio.run(seed())
