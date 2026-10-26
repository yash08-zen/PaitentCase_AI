"""
scripts/seed_demo_e2e.py
------------------------
Deterministic seed script for the End-to-End Demo (Milestone M10 / FR-15).
Seeds 4 realistic, distinct demo clinical intake scenarios:
  1. Case 1 (Active Interview): In-progress interview with partial branch responses.
  2. Case 2 (Missing Info): Complete intake with missing allergy item flagged (Missing != Negative).
  3. Case 3 (OCR & Discrepancy): Complete intake with prescription OCR scan and active discrepancy.
  4. Case 4 (Finalized & Locked): Completed case with clinician review notes, locked against patient edit.

Also seeds core role accounts:
  - Doctor: doctor@patientcase.local / Doctor@1234
  - Patient: patient@patientcase.local / Patient@1234 (linked to Case 1)
  - Staff: staff@patientcase.local / Staff@1234
  - Admin: admin@patientcase.local / Admin@1234
"""
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from app.database import init_db, AsyncSessionLocal
from app.models import (
    User, Patient, Encounter, Question, Response, Document,
    Conflict, ReviewFlag, CaseSummary, UserRole, EncounterStatus,
    DocumentStatus, ConflictStatus, FlagStatus
)
from app.core.security import hash_password
from app.services.adaptive_engine import QUESTION_BANK


DEMO_USERS = [
    {"username": "admin", "email": "admin@patientcase.local", "password": "Admin@1234", "role": UserRole.admin},
    {"username": "doctor", "email": "doctor@patientcase.local", "password": "Doctor@1234", "role": UserRole.doctor},
    {"username": "staff", "email": "staff@patientcase.local", "password": "Staff@1234", "role": UserRole.staff},
    {"username": "patient", "email": "patient@patientcase.local", "password": "Patient@1234", "role": UserRole.patient},
]


async def seed_demo():
    print("=" * 60)
    print("PATIENTCASE AI — SEEDING DETERMINISTIC END-TO-END DEMO DATA")
    print("=" * 60)

    await init_db()

    async with AsyncSessionLocal() as db:
        # 1. Sync Question Bank
        q_map = {}
        for q_data in QUESTION_BANK:
            q = await db.scalar(select(Question).where(Question.key == q_data["key"]))
            if not q:
                q = Question(
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
                db.add(q)
                await db.flush()
            q_map[q.key] = q
        await db.commit()
        print(f"[Seed] Synchronized {len(q_map)} adaptive interview questions.")

        # 2. Seed Users
        user_map = {}
        for u in DEMO_USERS:
            user = await db.scalar(select(User).where(User.username == u["username"]))
            if not user:
                user = User(
                    username=u["username"],
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    role=u["role"],
                )
                db.add(user)
                await db.flush()
            user_map[u["username"]] = user
        await db.commit()
        print(f"[Seed] Verified demo users: {list(user_map.keys())}")

        now = datetime.now(timezone.utc)
        doctor_user = user_map["doctor"]
        patient_user = user_map["patient"]

        # -------------------------------------------------------------
        # DEMO CASE 1: Active In-Progress Interview
        # -------------------------------------------------------------
        p1 = await db.scalar(select(Patient).where(Patient.full_name == "Aarav Sharma (Demo)"))
        if not p1:
            p1 = Patient(
                user_id=patient_user.id,
                full_name="Aarav Sharma (Demo)",
                age=28,
                gender="Male",
                contact_phone="9876543210",
                contact_email="aarav.sharma@example.com",
                preferred_language="English",
            )
            db.add(p1)
            await db.flush()

            enc1 = Encounter(
                patient_id=p1.id,
                chief_complaint="Persistent severe headache and photophobia for 2 days",
                status=EncounterStatus.in_progress,
                consent_given=True,
                consent_timestamp=now - timedelta(hours=2),
                started_at=now - timedelta(hours=2),
            )
            db.add(enc1)
            await db.flush()

            # Partial answers
            r1 = Response(
                encounter_id=enc1.id,
                question_id=q_map["chief_complaint"].id,
                question_key="chief_complaint",
                answer="Headache",
                source="patient_reported",
                answered_at=now - timedelta(minutes=90),
            )
            r2 = Response(
                encounter_id=enc1.id,
                question_id=q_map["symptom_duration"].id,
                question_key="symptom_duration",
                answer="1 to 3 days",
                source="patient_reported",
                answered_at=now - timedelta(minutes=80),
            )
            r3 = Response(
                encounter_id=enc1.id,
                question_id=q_map["symptom_severity"].id,
                question_key="symptom_severity",
                answer="8",
                source="patient_reported",
                answered_at=now - timedelta(minutes=70),
            )
            db.add_all([r1, r2, r3])
            print(f"[Seed] Case 1 (In-Progress) created: Patient {p1.full_name}, Encounter #{enc1.id}")

        # -------------------------------------------------------------
        # DEMO CASE 2: Complete Intake with Missing Info Flagged (Missing != Negative)
        # -------------------------------------------------------------
        p2 = await db.scalar(select(Patient).where(Patient.full_name == "Sunita Patil (Demo)"))
        if not p2:
            p2 = Patient(
                full_name="Sunita Patil (Demo)",
                age=45,
                gender="Female",
                contact_phone="9823456789",
                contact_email="sunita.patil@example.com",
                preferred_language="Hindi",
            )
            db.add(p2)
            await db.flush()

            enc2 = Encounter(
                patient_id=p2.id,
                chief_complaint="Recurrent sore throat and dry cough in evenings",
                status=EncounterStatus.completed,
                consent_given=True,
                consent_timestamp=now - timedelta(hours=5),
                started_at=now - timedelta(hours=5),
                completed_at=now - timedelta(hours=4),
            )
            db.add(enc2)
            await db.flush()

            # Completed symptom questions, answered current_medications=No, but intentionally skipped has_allergies
            responses_case2 = [
                Response(encounter_id=enc2.id, question_id=q_map["chief_complaint"].id, question_key="chief_complaint", answer="Cough"),
                Response(encounter_id=enc2.id, question_id=q_map["symptom_duration"].id, question_key="symptom_duration", answer="More than a week"),
                Response(encounter_id=enc2.id, question_id=q_map["has_fever"].id, question_key="has_fever", answer="Yes"),
                Response(encounter_id=enc2.id, question_id=q_map["current_medications"].id, question_key="current_medications", answer="No"),
            ]
            db.add_all(responses_case2)

            flag2 = ReviewFlag(
                encounter_id=enc2.id,
                flag_type="missing",
                description="Missing required intake: Known Allergies status has not been confirmed by patient.",
                status=FlagStatus.open,
            )
            db.add(flag2)

            sum2 = CaseSummary(
                encounter_id=enc2.id,
                summary_text=(
                    "Patient reports more than a week of recurrent dry cough with evening fevers. "
                    "Patient denies taking current medications. Allergy status is unknown / unverified "
                    "(Missing != Negative). Clinical confirmation required."
                ),
                readiness_score=0.75,
                readiness_factors={"chief_complaint": 1.0, "symptoms_characterized": 1.0, "medications_reconciled": 1.0, "allergies_verified": 0.0},
                review_status="pending",
            )
            db.add(sum2)
            print(f"[Seed] Case 2 (Missing Info) created: Patient {p2.full_name}, Encounter #{enc2.id}")

        # -------------------------------------------------------------
        # DEMO CASE 3: Complete Intake with Prescription OCR & Active Discrepancy
        # -------------------------------------------------------------
        p3 = await db.scalar(select(Patient).where(Patient.full_name == "Vikram Malhotra (Demo)"))
        if not p3:
            p3 = Patient(
                full_name="Vikram Malhotra (Demo)",
                age=62,
                gender="Male",
                contact_phone="9811223344",
                contact_email="vikram.malhotra@example.com",
                preferred_language="English",
            )
            db.add(p3)
            await db.flush()

            enc3 = Encounter(
                patient_id=p3.id,
                chief_complaint="Exertional chest tightness and shortness of breath",
                status=EncounterStatus.completed,
                consent_given=True,
                consent_timestamp=now - timedelta(hours=6),
                started_at=now - timedelta(hours=6),
                completed_at=now - timedelta(hours=5),
            )
            db.add(enc3)
            await db.flush()

            # Patient reported: current_medications = "No"
            responses_case3 = [
                Response(encounter_id=enc3.id, question_id=q_map["chief_complaint"].id, question_key="chief_complaint", answer="Chest discomfort"),
                Response(encounter_id=enc3.id, question_id=q_map["symptom_duration"].id, question_key="symptom_duration", answer="More than a week"),
                Response(encounter_id=enc3.id, question_id=q_map["current_medications"].id, question_key="current_medications", answer="No"),
                Response(encounter_id=enc3.id, question_id=q_map["has_allergies"].id, question_key="has_allergies", answer="No"),
            ]
            db.add_all(responses_case3)

            # Uploaded prescription document with OCR extraction
            doc3 = Document(
                patient_id=p3.id,
                encounter_id=enc3.id,
                document_type="prescription",
                original_filename="rx_sample_1_amoxicillin.png",
                stored_path="test_uploads/rx_sample_1_amoxicillin.png",
                file_size_bytes=16319,
                mime_type="image/png",
                status=DocumentStatus.processed,
                extracted_text="Rx: Amoxicillin 500mg capsules TID x 7 days. Disp: #21. Dr. R. Sharma, MD.",
                extracted_fields={
                    "medications": [
                        {"name": "Amoxicillin", "dose": "500mg", "frequency": "TID", "confidence": 0.94}
                    ]
                },
                extraction_confidence=0.94,
                is_verified=False,
                uploaded_at=now - timedelta(hours=5, minutes=30),
                processed_at=now - timedelta(hours=5, minutes=28),
            )
            db.add(doc3)

            # Contradiction flagged: patient said No, document has Amoxicillin 500mg
            conflict3 = Conflict(
                encounter_id=enc3.id,
                rule_id="RULE-MED-NAME-MISMATCH",
                field="medication",
                source_a="patient_reported",
                value_a="None (Patient denied taking current medications)",
                source_b="document_extracted_unverified",
                value_b="Amoxicillin 500mg (from uploaded prescription)",
                description="Patient reported taking no medications, but prescription OCR extracted active medication Amoxicillin 500mg.",
                status=ConflictStatus.open,
            )
            db.add(conflict3)

            flag3 = ReviewFlag(
                encounter_id=enc3.id,
                flag_type="conflict",
                description="Active medication discrepancy detected: patient denies meds, prescription indicates Amoxicillin 500mg.",
                status=FlagStatus.open,
            )
            db.add(flag3)

            sum3 = CaseSummary(
                encounter_id=enc3.id,
                summary_text=(
                    "Patient reports exertional chest tightness. "
                    "Patient stated no current medications; however, uploaded prescription contains "
                    "Amoxicillin 500mg TID. Medication discrepancy requires doctor reconciliation."
                ),
                readiness_score=0.65,
                readiness_factors={"chief_complaint": 1.0, "symptoms_characterized": 1.0, "medications_reconciled": 0.0, "allergies_verified": 1.0},
                review_status="pending",
            )
            db.add(sum3)
            print(f"[Seed] Case 3 (OCR & Discrepancy) created: Patient {p3.full_name}, Encounter #{enc3.id}")

        # -------------------------------------------------------------
        # DEMO CASE 4: Finalized Case with Doctor Review Notes (Locked)
        # -------------------------------------------------------------
        p4 = await db.scalar(select(Patient).where(Patient.full_name == "Meera Nair (Demo)"))
        if not p4:
            p4 = Patient(
                full_name="Meera Nair (Demo)",
                age=38,
                gender="Female",
                contact_phone="9833445566",
                contact_email="meera.nair@example.com",
                preferred_language="English",
            )
            db.add(p4)
            await db.flush()

            enc4 = Encounter(
                patient_id=p4.id,
                chief_complaint="Acute right lower quadrant abdominal pain with nausea",
                status=EncounterStatus.completed,
                consent_given=True,
                consent_timestamp=now - timedelta(hours=10),
                started_at=now - timedelta(hours=10),
                completed_at=now - timedelta(hours=9),
                doctor_notes=(
                    "Case reviewed in detail by Dr. Mehta. Presentation consistent with acute appendicitis "
                    "rule-out. Immediate abdominal ultrasound and surgical consultation requested. "
                    "Penicillin allergy noted in chart. Non-diagnostic intake finalized."
                ),
                reviewed_at=now - timedelta(hours=8),
                reviewed_by=doctor_user.id,
            )
            db.add(enc4)
            await db.flush()

            responses_case4 = [
                Response(encounter_id=enc4.id, question_id=q_map["chief_complaint"].id, question_key="chief_complaint", answer="Abdominal pain"),
                Response(encounter_id=enc4.id, question_id=q_map["symptom_duration"].id, question_key="symptom_duration", answer="Less than a day"),
                Response(encounter_id=enc4.id, question_id=q_map["symptom_severity"].id, question_key="symptom_severity", answer="9"),
                Response(encounter_id=enc4.id, question_id=q_map["current_medications"].id, question_key="current_medications", answer="No"),
                Response(encounter_id=enc4.id, question_id=q_map["has_allergies"].id, question_key="has_allergies", answer="Yes"),
                Response(encounter_id=enc4.id, question_id=q_map["allergy_details"].id, question_key="allergy_details", answer="Penicillin"),
                Response(encounter_id=enc4.id, question_id=q_map["allergy_reaction"].id, question_key="allergy_reaction", answer="Skin rash / Hives"),
            ]
            db.add_all(responses_case4)

            sum4 = CaseSummary(
                encounter_id=enc4.id,
                summary_text=(
                    "Acute RLQ abdominal pain for 12 hours, pain severity 9/10, with nausea. "
                    "Penicillin allergy confirmed (Skin rash / Hives). Denies current medications. Intake finalized by clinician."
                ),
                readiness_score=1.0,
                readiness_factors={"chief_complaint": 1.0, "symptoms_characterized": 1.0, "medications_reconciled": 1.0, "allergies_verified": 1.0},
                review_status="reviewed",
                doctor_notes=enc4.doctor_notes,
                reviewed_at=enc4.reviewed_at,
                reviewed_by=doctor_user.id,
            )
            db.add(sum4)
            print(f"[Seed] Case 4 (Finalized & Locked) created: Patient {p4.full_name}, Encounter #{enc4.id}")

        await db.commit()
        print("=" * 60)
        print("DEMO DATA SEEDING COMPLETE SUCCESSFULLY")
        print("Demo accounts:")
        print("  Doctor:  doctor / Doctor@1234")
        print("  Patient: patient / Patient@1234 (linked to Aarav Sharma)")
        print("  Staff:   staff / Staff@1234")
        print("  Admin:   admin / Admin@1234")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_demo())
