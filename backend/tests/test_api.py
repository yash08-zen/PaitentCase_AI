"""
tests/test_api.py
-----------------
Automated backend tests using pytest + httpx AsyncClient.

Covers:
  - Health endpoint
  - Patient CRUD with valid and invalid input
  - Encounter creation
  - Adaptive question branching
  - Response persistence and interview resumption
  - Missing-information detection
  - Contradiction detection (patient denies meds, document contains meds)
  - Case readiness calculation
  - File upload validation
  - Authentication and unauthorized access
  - Case summary source traceability
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

# Use an in-memory DB for tests so they don't pollute the dev database
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["APP_SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["UPLOAD_DIR"] = "./test_uploads"

from app.main import app, init_db, seed_questions, ensure_default_admin


# Fixtures imported from conftest.py


# â”€â”€ Health â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_root(client):
    r = await client.get("/")
    assert r.status_code == 200
    assert "PatientCase AI" in r.json()["name"]


@pytest.mark.asyncio
async def test_health(client):
    for endpoint in ("/health", "/api/health"):
        r = await client.get(endpoint)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert data["app"] == "healthy"
        assert data["database"] == "connected"


# â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_login_valid(client):
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_login_invalid(client):
    r = await client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    r = await client.get("/api/patients")
    assert r.status_code == 401  # Unauthenticated requests return 401


# â”€â”€ Patients â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_create_patient_valid(client, auth_headers):
    r = await client.post(
        "/api/patients",
        json={"full_name": "Test Patient", "age": 35, "gender": "Male", "preferred_language": "English"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["full_name"] == "Test Patient"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_patient_blank_name(client, auth_headers):
    r = await client.post(
        "/api/patients",
        json={"full_name": "   ", "age": 30},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_patients(client, auth_headers):
    await client.post("/api/patients", json={"full_name": "Test Listed Patient", "age": 40}, headers=auth_headers)
    r = await client.get("/api/patients", headers=auth_headers)
    assert r.status_code == 200
    assert "items" in r.json()
    assert r.json()["total"] >= 1


@pytest.mark.asyncio
async def test_get_patient_not_found(client, auth_headers):
    r = await client.get("/api/patients/99999", headers=auth_headers)
    assert r.status_code == 404


# â”€â”€ Encounters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_create_encounter(client, auth_headers):
    # First create a patient
    p = await client.post(
        "/api/patients",
        json={"full_name": "Encounter Patient", "age": 45},
        headers=auth_headers,
    )
    patient_id = p.json()["id"]

    r = await client.post(
        "/api/encounters",
        json={"patient_id": patient_id, "chief_complaint": "Severe headache"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    assert r.json()["chief_complaint"] == "Severe headache"


# â”€â”€ Adaptive Interview â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_next_question_first(client, auth_headers):
    """First question should always be chief_complaint."""
    p = await client.post("/api/patients", json={"full_name": "Interview Patient"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    r = await client.get(f"/api/interviews/{enc_id}/next-question", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["question"]["key"] == "chief_complaint"
    assert data["is_complete"] is False


@pytest.mark.asyncio
async def test_submit_response_and_branching(client, auth_headers):
    """
    Branching test: answering has_chronic_conditions=Yes should unlock
    chronic_conditions_detail question.
    """
    p = await client.post("/api/patients", json={"full_name": "Branch Patient"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    # Answer all questions up to has_chronic_conditions
    questions_to_skip = [
        ("chief_complaint", "Chest pain"),
        ("symptom_duration", "1–3 days"),
        ("symptom_severity", "7"),
        ("pain_location", "Left chest"),
        ("worse_with_activity", "Yes"),
        ("symptom_frequency", "Constant"),
        ("associated_symptoms", "Shortness of breath"),
        ("has_fever", "No"),
        ("has_chronic_conditions", "Yes"),
    ]
    for key, answer in questions_to_skip:
        await client.post(
            f"/api/interviews/{enc_id}/responses",
            json={"question_key": key, "answer": answer},
            headers=auth_headers,
        )

    r = await client.get(f"/api/interviews/{enc_id}/next-question", headers=auth_headers)
    assert r.status_code == 200
    # chronic_conditions_detail should now be next (condition: has_chronic_conditions contains yes)
    assert r.json()["question"]["key"] == "chronic_conditions_detail"


@pytest.mark.asyncio
async def test_interview_progress(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Progress Patient"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    # Answer chief complaint only
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Fever"},
        headers=auth_headers,
    )

    r = await client.get(f"/api/interviews/{enc_id}/progress", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["answered_questions"] >= 1
    assert data["progress_percent"] > 0
    assert data["is_complete"] is False


@pytest.mark.asyncio
async def test_interview_resume(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Resume Patient"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    # Answer one question then resume
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Backache"},
        headers=auth_headers,
    )
    r = await client.post(f"/api/interviews/{enc_id}/resume", headers=auth_headers)
    assert r.status_code == 200
    # Should resume from symptom_duration, not chief_complaint
    assert r.json()["question"]["key"] != "chief_complaint"


# â”€â”€ Missing Information â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_missing_information_all_missing(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Missing Patient"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    r = await client.get(f"/api/encounters/{enc_id}/missing-information", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    # All required fields should be missing initially
    assert data["total_missing"] == 6  # 6 required fields defined


@pytest.mark.asyncio
async def test_missing_information_reduces_after_answers(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Partial Patient"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Headache"},
        headers=auth_headers,
    )

    r = await client.get(f"/api/encounters/{enc_id}/missing-information", headers=auth_headers)
    assert r.json()["total_missing"] == 5  # One less than before


# â”€â”€ Contradiction Detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_contradiction_medication_denial(client, auth_headers):
    """
    End-to-end scenario from PRD:
    Patient denies taking medication â†’ document contains medication â†’ conflict flagged.
    Neither source is overwritten.
    """
    p = await client.post("/api/patients", json={"full_name": "Contradiction Patient"}, headers=auth_headers)
    patient_id = p.json()["id"]
    e = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    # Patient says: no medications
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "current_medications", "answer": "No"},
        headers=auth_headers,
    )

    # Simulate a processed document with medications extracted
    from app.database import AsyncSessionLocal
    from app.models import Document
    from datetime import datetime, timezone
    async with AsyncSessionLocal() as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=enc_id,
            document_type="prescription",
            original_filename="test_prescription.jpg",
            stored_path="./test_uploads/test_prescription.jpg",
            mime_type="image/jpeg",
            status="processed",
            extracted_fields={"medications": ["Metformin 500mg"], "allergies": []},
            is_verified=False,
        )
        db.add(doc)
        await db.commit()

    # Run contradiction detection
    r = await client.get(f"/api/encounters/{enc_id}/contradictions", headers=auth_headers)
    assert r.status_code == 200
    conflicts = r.json()
    assert len(conflicts) >= 1

    conflict = next(c for c in conflicts if c["field"] == "current_medications")
    assert "patient" in conflict["source_a"]
    assert "document" in conflict["source_b"]
    assert conflict["status"] == "open"  # Neither value was auto-resolved


# â”€â”€ Case Readiness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_readiness_empty_encounter(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Readiness Patient"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    r = await client.get(f"/api/encounters/{enc_id}/readiness", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["score"] < 0.5
    assert data["label"] == "Not Ready"
    assert "disclaimer" in data


# â”€â”€ Case Summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_case_summary_source_traceability(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Summary Patient", "age": 50, "gender": "Female"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "chief_complaint": "Fatigue", "consent_given": True}, headers=auth_headers)
    enc_id = e.json()["id"]

    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Persistent fatigue for 2 weeks"},
        headers=auth_headers,
    )

    r = await client.get(f"/api/encounters/{enc_id}/summary", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    summary = data["summary_text"]

    # Source traceability checks
    assert "patient response" in summary.lower() or "Source: patient response" in summary
    assert "Summary Patient" in summary
    assert "Persistent fatigue for 2 weeks" in summary
    assert "NOT a diagnosis" in summary or "does not replace" in summary.lower()


# â”€â”€ Upload Validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.mark.asyncio
async def test_upload_invalid_file_type(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Upload Patient"}, headers=auth_headers)
    patient_id = p.json()["id"]

    r = await client.post(
        f"/api/documents/upload/{patient_id}",
        files={"file": ("malware.exe", b"MZ\x90\x00", "application/octet-stream")},
        data={"document_type": "other"},
        headers=auth_headers,
    )
    assert r.status_code == 415



