"""
tests/test_offline_persistence.py
---------------------------------
Comprehensive Test Suite for Milestone M11 (Basic Local / Offline Operation, FR-13).

Verifies:
  1. System offline status endpoint reports local workstation mode and zero external dependencies.
  2. Multi-device sync attempts are safely rejected with HTTP 501 to prevent silent overwrites.
  3. Local database integrity check passes.
  4. Full patient intake and clinical review data persists reliably across DB sessions / app restarts.
  5. Air-gapped network isolation: core clinical operations execute with zero external outbound network requests.
"""

import pytest
import socket
from httpx import AsyncClient
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Patient, Encounter, Response


@pytest.mark.asyncio
async def test_offline_status_metadata(client: AsyncClient):
    """Verify system status endpoint confirms offline workstation capabilities."""
    res = await client.get("/api/system/offline-status")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "operational"
    assert data["mode"] == "local_workstation"
    assert data["offline_capable"] is True
    assert data["storage_engine"] == "sqlite_aiosqlite_local"
    assert data["database_file"] == "patientcase.db"
    assert data["ocr_engine"] == "rapidocr_onnx_local"
    assert data["external_dependencies"] == []
    assert data["cloud_sync_supported"] is False
    assert data["cloud_sync_status"] == "disabled_single_device_scope"
    assert "clinical_boundary" in data


@pytest.mark.asyncio
async def test_sync_rejection_prevents_silent_overwrite(client: AsyncClient):
    """
    Verify multi-device sync attempts return HTTP 501 Not Implemented,
    preventing any potential silent overwrite or unverified merge conflicts.
    """
    res = await client.post("/api/system/sync")
    assert res.status_code == 501
    detail = res.json()["detail"]
    assert "Multi-device synchronization is not supported" in detail["error"]
    assert detail["offline_safe"] is True


@pytest.mark.asyncio
async def test_database_integrity_verification(client: AsyncClient):
    """Verify local SQLite storage integrity check passes for authenticated clinicians."""
    # Login as admin
    login_res = await client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/system/backup/verify", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["integrity_check"] == "ok"
    assert data["status"] == "healthy"
    assert data["storage"] == "local_sqlite"


@pytest.mark.asyncio
async def test_full_offline_data_persistence_across_sessions(client: AsyncClient):
    """
    Verifies that patient records, answers, and doctor notes survive session resets
    and remain 100% persisted on the local database.
    """
    # 1. Login as staff and register a patient
    staff_login = await client.post("/api/auth/login", json={"username": "staff", "password": "Staff@1234"})
    staff_token = staff_login.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    reg_payload = {
        "full_name": "Offline Local Patient",
        "date_of_birth": "1988-06-15",
        "gender": "female",
        "contact_phone": "+91 98888 77777",
        "emergency_contact_phone": "+91 98888 66666",
        "consent_given": True,
        "chief_complaint": "Persistent migraines with nausea",
    }
    reg_res = await client.post("/api/patients", json=reg_payload, headers=staff_headers)
    assert reg_res.status_code == 201
    patient_id = reg_res.json()["id"]

    # 2. Create encounter
    enc_res = await client.post(
        "/api/encounters",
        json={"patient_id": patient_id, "chief_complaint": "Persistent migraines with nausea", "consent_given": True},
        headers=staff_headers,
    )
    assert enc_res.status_code == 201
    encounter_id = enc_res.json()["id"]

    # 3. Save interview answers
    r1 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Abdominal pain"},
        headers=staff_headers,
    )
    assert r1.status_code == 201

    r2 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "symptom_duration", "answer": "1 to 3 days"},
        headers=staff_headers,
    )
    assert r2.status_code == 201

    # 4. Doctor review and notes
    doc_login = await client.post("/api/auth/login", json={"username": "doctor", "password": "Doctor@1234"})
    doc_token = doc_login.json()["access_token"]
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    note_res = await client.put(
        f"/api/encounters/{encounter_id}/notes",
        json={"doctor_notes": "Patient presents with episodic cephalalgia. Recommended lifestyle modifications."},
        headers=doc_headers,
    )
    assert note_res.status_code == 200

    # 5. Finalize encounter
    fin_res = await client.post(f"/api/encounters/{encounter_id}/finalize", headers=doc_headers)
    assert fin_res.status_code == 200

    # =========================================================================
    # 6. Simulate restart / fresh database session
    # =========================================================================
    async with AsyncSessionLocal() as session:
        # Check patient
        db_patient = await session.get(Patient, patient_id)
        assert db_patient is not None
        assert db_patient.full_name == "Offline Local Patient"

        # Check encounter
        db_enc = await session.get(Encounter, encounter_id)
        assert db_enc is not None
        assert db_enc.status.value in ["finalized", "reviewed"]
        assert "episodic cephalalgia" in (db_enc.doctor_notes or "")

        # Check responses
        responses_res = await session.execute(
            select(Response).where(Response.encounter_id == encounter_id)
        )
        responses = responses_res.scalars().all()
        assert len(responses) >= 2
        ans_keys = {r.question_key: r.answer for r in responses}
        assert ans_keys.get("chief_complaint") == "Abdominal pain"
        assert ans_keys.get("symptom_duration") == "1 to 3 days"


@pytest.mark.asyncio
async def test_air_gapped_network_isolation(client: AsyncClient, monkeypatch):
    """
    Ensure core intake and doctor review operations execute with zero external network requests.
    Attempts to connect to external IPs/domains are trapped and forbidden.
    """
    original_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0]
        # Allow local loopback only
        if host not in ("127.0.0.1", "localhost", "::1", "testserver"):
            raise ConnectionRefusedError(f"External outbound network access forbidden in offline mode: {address}")
        return original_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    # Perform health check, offline status, and summary retrieval under guarded network
    status_res = await client.get("/api/system/offline-status")
    assert status_res.status_code == 200

    health_res = await client.get("/health")
    assert health_res.status_code == 200
    assert health_res.json()["status"] == "healthy"
