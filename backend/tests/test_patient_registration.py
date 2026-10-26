"""
tests/test_patient_registration.py
----------------------------------
Milestone M3 tests:
  - Patient registration with unique ID and persistence
  - Linked encounter creation and consent capture with timestamp
  - Interview blocked if consent is missing (400)
  - Duplicate prevention on rapid submissions (idempotency)
  - Server-side input validation for invalid payloads (422)
  - Role-based scoping (patients cannot list all patients)
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select, func
from app.models import Patient, Encounter


async def get_token_for(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Failed to login as {username}: {r.text}"
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_patient_registration_persists_with_unique_id(client: AsyncClient, auth_headers):
    """Registering a patient stores all fields and generates a unique ID."""
    payload = {
        "full_name": "Aarav Deshmukh",
        "age": 38,
        "gender": "Male",
        "contact_phone": "9820011223",
        "contact_email": "aarav.deshmukh@example.com",
        "preferred_language": "Marathi",
    }
    r = await client.post("/api/patients", json=payload, headers=auth_headers)
    assert r.status_code == 201
    p_data = r.json()
    assert p_data["id"] is not None
    assert p_data["full_name"] == "Aarav Deshmukh"
    assert p_data["preferred_language"] == "Marathi"

    # Verify directly in DB
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        p_db = await db.get(Patient, p_data["id"])
        assert p_db is not None
        assert p_db.full_name == "Aarav Deshmukh"
        assert p_db.age == 38
        assert p_db.gender == "Male"
        assert p_db.contact_phone == "9820011223"


@pytest.mark.asyncio
async def test_encounter_creation_linked_to_patient_with_consent(client: AsyncClient, auth_headers):
    """Encounter creation links to patient ID, stores consent and timestamp."""
    p_res = await client.post(
        "/api/patients",
        json={"full_name": "Kavita Rao", "age": 29, "gender": "Female"},
        headers=auth_headers,
    )
    p_id = p_res.json()["id"]

    e_res = await client.post(
        "/api/encounters",
        json={
            "patient_id": p_id,
            "chief_complaint": "Acute abdominal pain for 2 days",
            "consent_given": True,
        },
        headers=auth_headers,
    )
    assert e_res.status_code == 201
    e_data = e_res.json()
    assert e_data["id"] is not None
    assert e_data["patient_id"] == p_id
    assert e_data["consent_given"] is True
    assert e_data["consent_timestamp"] is not None
    assert e_data["status"] == "pending"


@pytest.mark.asyncio
async def test_interview_blocked_without_consent(client: AsyncClient, auth_headers):
    """Interview cannot start if consent_given is False; starts after recording consent."""
    p_res = await client.post("/api/patients", json={"full_name": "Sunil Varma", "age": 50}, headers=auth_headers)
    p_id = p_res.json()["id"]

    # Create encounter with consent_given=False
    e_res = await client.post(
        "/api/encounters",
        json={"patient_id": p_id, "chief_complaint": "Persistent cough", "consent_given": False},
        headers=auth_headers,
    )
    enc_id = e_res.json()["id"]
    assert e_res.json()["consent_given"] is False

    # 1. Try to start interview -> 400
    r_start = await client.get(f"/api/interviews/{enc_id}/next-question", headers=auth_headers)
    assert r_start.status_code == 400
    assert "consent" in r_start.json()["detail"].lower()

    # 2. Record consent via consent endpoint
    r_consent = await client.post(
        f"/api/encounters/{enc_id}/consent",
        json={"consent_given": True},
        headers=auth_headers,
    )
    assert r_consent.status_code == 200
    assert r_consent.json()["consent_given"] is True
    assert r_consent.json()["consent_timestamp"] is not None

    # 3. Try to start interview now -> 200 OK
    r_start_ok = await client.get(f"/api/interviews/{enc_id}/next-question", headers=auth_headers)
    assert r_start_ok.status_code == 200
    assert r_start_ok.json()["question"]["key"] == "chief_complaint"


@pytest.mark.asyncio
async def test_prevent_duplicate_accidental_submissions(client: AsyncClient, auth_headers):
    """Rapid double-submissions return existing record and prevent duplicate DB entries."""
    payload = {"full_name": "Double Submit Patient", "age": 42, "contact_phone": "9812345678"}

    # Rapid double submission for patient
    r1 = await client.post("/api/patients", json=payload, headers=auth_headers)
    r2 = await client.post("/api/patients", json=payload, headers=auth_headers)

    assert r1.status_code in (200, 201)
    assert r2.status_code in (200, 201)
    assert r1.json()["id"] == r2.json()["id"]

    # Verify only 1 patient exists in DB with this name
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        count = await db.scalar(
            select(func.count(Patient.id)).where(Patient.full_name == "Double Submit Patient")
        )
        assert count == 1

        # Rapid double submission for encounter
        p_id = r1.json()["id"]
        e_payload = {"patient_id": p_id, "chief_complaint": "Double submit complaint", "consent_given": True}
        e1 = await client.post("/api/encounters", json=e_payload, headers=auth_headers)
        e2 = await client.post("/api/encounters", json=e_payload, headers=auth_headers)

        assert e1.json()["id"] == e2.json()["id"]
        enc_count = await db.scalar(
            select(func.count(Encounter.id)).where(Encounter.patient_id == p_id)
        )
        assert enc_count == 1


@pytest.mark.asyncio
async def test_validation_errors_for_invalid_patient_payloads(client: AsyncClient, auth_headers):
    """Server-side schema validation rejects invalid data with 422."""
    # Blank name
    r_blank = await client.post("/api/patients", json={"full_name": "   ", "age": 30}, headers=auth_headers)
    assert r_blank.status_code == 422

    # Negative age
    r_neg_age = await client.post("/api/patients", json={"full_name": "Valid Name", "age": -5}, headers=auth_headers)
    assert r_neg_age.status_code == 422

    # Age > 125
    r_high_age = await client.post("/api/patients", json={"full_name": "Valid Name", "age": 140}, headers=auth_headers)
    assert r_high_age.status_code == 422

    # Invalid phone format (not enough digits)
    r_bad_phone = await client.post("/api/patients", json={"full_name": "Valid Name", "contact_phone": "123"}, headers=auth_headers)
    assert r_bad_phone.status_code == 422


@pytest.mark.asyncio
async def test_role_scoping_patient_cannot_list_or_create_patients(client: AsyncClient):
    """Authenticated user with patient role cannot list all patients or register patients."""
    patient_token = await get_token_for(client, "patient", "Patient@1234")
    p_headers = {"Authorization": f"Bearer {patient_token}"}

    # 1. Listing all patients -> 403
    r_list = await client.get("/api/patients", headers=p_headers)
    assert r_list.status_code == 403

    # 2. Creating patients -> 403
    r_create = await client.post(
        "/api/patients",
        json={"full_name": "Unauthorized Patient", "age": 25},
        headers=p_headers,
    )
    assert r_create.status_code == 403


@pytest.mark.asyncio
async def test_get_my_patient_profile(client: AsyncClient):
    """Authenticated patient user can retrieve their own profile via GET /api/patients/me."""
    patient_token = await get_token_for(client, "patient", "Patient@1234")
    p_headers = {"Authorization": f"Bearer {patient_token}"}

    res = await client.get("/api/patients/me", headers=p_headers)
    assert res.status_code == 200
    data = res.json()
    assert "id" in data
    assert data["full_name"] == "Ramesh Kumar (Demo Patient)"
    assert data["preferred_language"] == "English"

