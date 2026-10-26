"""
tests/test_doctor_dashboard_and_review.py
-----------------------------------------
Milestone 8 verification suite:
- Clinician review notes persistence (PUT & GET /api/encounters/{id}/notes)
- Case finalization & status transition (POST /api/encounters/{id}/finalize)
- Immutable audit event logging (DOCTOR_NOTES_UPDATED, CASE_FINALIZED)
- Encounter locking against subsequent patient interview modifications (HTTP 400)
- Role-based access control (least-privilege boundaries: patients forbidden from doctor review actions)
- Dashboard statistics & clinical review queue querying with filters and search
"""
import pytest
from httpx import AsyncClient
from app.models import Encounter, Patient, User, UserRole, EncounterStatus
from app.database import AsyncSessionLocal
from sqlalchemy import select


async def get_token(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Login failed for {username}: {r.text}"
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_doctor_notes_persistence_and_audit(client: AsyncClient):
    """Doctor can save and retrieve clinical notes, generating immutable audit logs."""
    doc_token = await get_token(client, "doctor", "Doctor@1234")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Register patient and encounter
    p_res = await client.post(
        "/api/patients",
        headers=doc_headers,
        json={"full_name": "Review Test Patient", "date_of_birth": "1988-06-15", "gender": "female"},
    )
    assert p_res.status_code == 201
    patient_id = p_res.json()["id"]

    e_res = await client.post(
        "/api/encounters",
        headers=doc_headers,
        json={"patient_id": patient_id, "chief_complaint": "Persistent migraines", "consent_given": True},
    )
    assert e_res.status_code == 201
    encounter_id = e_res.json()["id"]

    # Put clinician notes
    notes_text = "Verified patient headache onset. Prescribed prophylactic therapy and advised hydration."
    notes_res = await client.put(
        f"/api/encounters/{encounter_id}/notes",
        headers=doc_headers,
        json={"doctor_notes": notes_text},
    )
    assert notes_res.status_code == 200
    assert notes_res.json()["doctor_notes"] == notes_text

    # Retrieve notes via GET /api/encounters/{id}/notes
    get_res = await client.get(f"/api/encounters/{encounter_id}/notes", headers=doc_headers)
    assert get_res.status_code == 200
    assert get_res.json()["doctor_notes"] == notes_text
    assert get_res.json()["encounter_id"] == encounter_id

    # Verify audit event logged (admin role required to read audit log)
    admin_token = await get_token(client, "admin", "Admin@1234")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    audit_res = await client.get("/api/auth/audit", headers=admin_headers)
    assert audit_res.status_code == 200
    events = audit_res.json()
    note_event = next(
        (e for e in events if e["action"] == "DOCTOR_NOTES_UPDATED" and e["resource_id"] == str(encounter_id)),
        None,
    )
    assert note_event is not None
    assert note_event["actor_username"] == "doctor"


@pytest.mark.asyncio
async def test_patient_forbidden_from_editing_doctor_notes(client: AsyncClient):
    """Patient role must be rejected with 403 Forbidden when attempting to record doctor notes."""
    patient_token = await get_token(client, "patient", "Patient@1234")
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    r = await client.put(
        "/api/encounters/1/notes",
        headers=patient_headers,
        json={"doctor_notes": "Attempted unauthorized note insertion"},
    )
    assert r.status_code == 403
    assert "Forbidden" in r.json()["detail"]


@pytest.mark.asyncio
async def test_doctor_finalizes_case_and_locks_interview(client: AsyncClient):
    """
    Finalizing an intake case sets reviewed status & timestamps, records audit trail,
    and locks encounter against further response modifications.
    """
    doc_token = await get_token(client, "doctor", "Doctor@1234")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Register patient & encounter
    p_res = await client.post(
        "/api/patients",
        headers=doc_headers,
        json={"full_name": "Locking Test Patient", "date_of_birth": "1992-04-10", "gender": "male"},
    )
    patient_id = p_res.json()["id"]

    e_res = await client.post(
        "/api/encounters",
        headers=doc_headers,
        json={"patient_id": patient_id, "chief_complaint": "Acute abdominal pain", "consent_given": True},
    )
    encounter_id = e_res.json()["id"]

    # Initial response submission succeeds
    resp1 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        headers=doc_headers,
        json={"question_key": "chief_complaint", "answer": "Acute lower right quadrant pain"},
    )
    assert resp1.status_code == 201

    # Doctor finalizes the case
    final_res = await client.post(
        f"/api/encounters/{encounter_id}/finalize",
        headers=doc_headers,
        json={"doctor_notes": "Clinical assessment complete. Referred for ultrasound evaluation."},
    )
    assert final_res.status_code == 200
    data = final_res.json()
    assert data["status"] == "reviewed"
    assert data["review_status"] == "reviewed"
    assert data["reviewed_at"] is not None
    assert "ultrasound" in data["doctor_notes"]

    # Subsequent submission to locked encounter MUST fail with HTTP 400
    locked_resp = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        headers=doc_headers,
        json={"question_key": "symptom_duration", "answer": "Changed mind, 5 days"},
    )
    assert locked_resp.status_code == 400
    assert "Cannot modify responses for a finalized encounter" in locked_resp.json()["detail"]

    # Subsequent back-navigation to locked encounter MUST also fail with HTTP 400
    locked_back = await client.post(
        f"/api/interviews/{encounter_id}/back",
        headers=doc_headers,
    )
    assert locked_back.status_code == 400
    assert "Cannot modify responses for a finalized encounter" in locked_back.json()["detail"]

    # Verify CASE_FINALIZED audit log (admin role required)
    admin_token = await get_token(client, "admin", "Admin@1234")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    audit_res = await client.get("/api/auth/audit", headers=admin_headers)
    assert audit_res.status_code == 200
    final_event = next(
        (e for e in audit_res.json() if e["action"] == "CASE_FINALIZED" and e["resource_id"] == str(encounter_id)),
        None,
    )
    assert final_event is not None
    assert final_event["actor_username"] == "doctor"


@pytest.mark.asyncio
async def test_patient_forbidden_from_finalizing_case(client: AsyncClient):
    """Patient role must receive 403 Forbidden when trying to finalize an encounter."""
    patient_token = await get_token(client, "patient", "Patient@1234")
    patient_headers = {"Authorization": f"Bearer {patient_token}"}

    r = await client.post(
        "/api/encounters/1/finalize",
        headers=patient_headers,
        json={"doctor_notes": "Malicious finalization attempt"},
    )
    assert r.status_code == 403
    assert "Forbidden" in r.json()["detail"]


@pytest.mark.asyncio
async def test_dashboard_summary_and_cases_queue(client: AsyncClient):
    """Dashboard summary and cases queue reflect real intake volume and support filters."""
    doc_token = await get_token(client, "doctor", "Doctor@1234")
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    # Register a patient and encounter so summary and cases queue have data
    p_res = await client.post(
        "/api/patients",
        headers=doc_headers,
        json={"full_name": "Dashboard Test Patient", "date_of_birth": "1990-01-01", "gender": "other"},
    )
    assert p_res.status_code == 201
    pat_id = p_res.json()["id"]

    e_res = await client.post(
        "/api/encounters",
        headers=doc_headers,
        json={"patient_id": pat_id, "chief_complaint": "Test chief complaint", "consent_given": True},
    )
    assert e_res.status_code == 201

    # Summary endpoint
    sum_res = await client.get("/api/dashboard/summary", headers=doc_headers)
    assert sum_res.status_code == 200
    sum_data = sum_res.json()
    assert sum_data["total_patients"] >= 1
    assert "cases_needing_review" in sum_data
    assert "active_encounters" in sum_data

    # Cases queue endpoint
    cases_res = await client.get("/api/dashboard/cases", headers=doc_headers)
    assert cases_res.status_code == 200
    cases_data = cases_res.json()
    assert isinstance(cases_data, list)

    # Filter status=all
    all_res = await client.get("/api/dashboard/cases?status=all", headers=doc_headers)
    assert all_res.status_code == 200
    assert isinstance(all_res.json(), list)

    # Filter with search term
    search_res = await client.get("/api/dashboard/cases?status=all&search=Test", headers=doc_headers)
    assert search_res.status_code == 200
    for c in search_res.json():
        assert "test" in c["patient_name"].lower() or (c["chief_complaint"] and "test" in c["chief_complaint"].lower())
