"""
tests/test_roles_and_audit.py
-----------------------------
Milestone M2 tests:
  - Role-based authorization boundaries (admin, doctor, staff, patient)
  - 401 on unauthenticated access
  - 403 on role mismatch (direct API calls)
  - Audit logging for LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT
  - Password hashing verification
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models import AuditEvent, User


async def get_token_for(client: AsyncClient, username: str, password: str) -> str:
    r = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, f"Failed to login as {username}: {r.text}"
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_passwords_are_hashed_in_db(client: AsyncClient):
    """Verify that plaintext passwords are never stored in the database."""
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        users = (await db.scalars(select(User))).all()
        assert len(users) >= 4
        for u in users:
            assert u.password_hash != "Admin@1234"
            assert u.password_hash != "Doctor@1234"
            assert u.password_hash != "Staff@1234"
            assert u.password_hash != "Patient@1234"
            assert u.password_hash.startswith("$2b$") or u.password_hash.startswith("$2a$")


@pytest.mark.asyncio
async def test_unauthenticated_request_returns_401(client: AsyncClient):
    """Protected endpoints must reject requests with no token."""
    r = await client.get("/api/patients")
    assert r.status_code == 401
    assert "detail" in r.json()


@pytest.mark.asyncio
async def test_invalid_token_returns_401(client: AsyncClient):
    """Malformed or invalid Bearer tokens must return 401."""
    headers = {"Authorization": "Bearer invalid.garbage.token"}
    r = await client.get("/api/patients", headers=headers)
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_login_failed_records_audit_event(client: AsyncClient):
    """Failed login attempt must record LOGIN_FAILED audit event."""
    r = await client.post("/api/auth/login", json={"username": "doctor", "password": "WrongPassword!"})
    assert r.status_code == 401

    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        failed_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "LOGIN_FAILED", AuditEvent.actor_username == "doctor")
            .order_by(AuditEvent.timestamp.desc())
        )
        assert failed_event is not None
        assert "Failed login attempt" in failed_event.change_summary


@pytest.mark.asyncio
async def test_login_success_and_logout_records_audit_events(client: AsyncClient):
    """Successful login and logout must record audit events."""
    r = await client.post("/api/auth/login", json={"username": "doctor", "password": "Doctor@1234"})
    assert r.status_code == 200
    token = r.json()["access_token"]

    # Logout
    r_logout = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r_logout.status_code == 200
    assert r_logout.json()["message"] == "Logged out successfully"

    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        login_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "LOGIN_SUCCESS", AuditEvent.actor_username == "doctor")
            .order_by(AuditEvent.timestamp.desc())
        )
        assert login_event is not None
        assert login_event.actor_role == "doctor"

        logout_event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "LOGOUT", AuditEvent.actor_username == "doctor")
            .order_by(AuditEvent.timestamp.desc())
        )
        assert logout_event is not None
        assert logout_event.actor_role == "doctor"


@pytest.mark.asyncio
async def test_role_boundary_patient_forbidden_on_dashboard(client: AsyncClient):
    """Patient role must receive 403 on clinical dashboard endpoints."""
    patient_token = await get_token_for(client, "patient", "Patient@1234")
    headers = {"Authorization": f"Bearer {patient_token}"}

    r = await client.get("/api/dashboard/summary", headers=headers)
    assert r.status_code == 403
    assert "Forbidden" in r.json()["detail"]


@pytest.mark.asyncio
async def test_role_boundary_patient_forbidden_on_listing_all_patients(client: AsyncClient):
    """Patient role must receive 403 when trying to list all patient records."""
    patient_token = await get_token_for(client, "patient", "Patient@1234")
    headers = {"Authorization": f"Bearer {patient_token}"}

    r = await client.get("/api/patients", headers=headers)
    assert r.status_code == 403
    assert "Forbidden" in r.json()["detail"]


@pytest.mark.asyncio
async def test_role_boundary_staff_forbidden_on_document_review(client: AsyncClient):
    """Staff role cannot perform doctor reviews (403). Only doctor and admin can."""
    staff_token = await get_token_for(client, "staff", "Staff@1234")
    headers = {"Authorization": f"Bearer {staff_token}"}

    r = await client.post("/api/documents/1/review", headers=headers)
    assert r.status_code == 403
    assert "Forbidden" in r.json()["detail"]


@pytest.mark.asyncio
async def test_role_boundary_staff_and_doctor_forbidden_on_audit_logs(client: AsyncClient):
    """Only admin can view the audit log; doctor and staff receive 403."""
    doc_token = await get_token_for(client, "doctor", "Doctor@1234")
    r_doc = await client.get("/api/auth/audit", headers={"Authorization": f"Bearer {doc_token}"})
    assert r_doc.status_code == 403

    staff_token = await get_token_for(client, "staff", "Staff@1234")
    r_staff = await client.get("/api/auth/audit", headers={"Authorization": f"Bearer {staff_token}"})
    assert r_staff.status_code == 403

    admin_token = await get_token_for(client, "admin", "Admin@1234")
    r_admin = await client.get("/api/auth/audit", headers={"Authorization": f"Bearer {admin_token}"})
    assert r_admin.status_code == 200
    audit_list = r_admin.json()
    assert isinstance(audit_list, list)
    assert len(audit_list) > 0


@pytest.mark.asyncio
async def test_record_level_access_patient_can_only_access_own_record_and_encounter(client: AsyncClient, auth_headers):
    """Patient can access their own record and encounters, but receives 403 on other patients."""
    from app.database import AsyncSessionLocal
    from app.models import Patient, Encounter

    # Fetch patient user id
    async with AsyncSessionLocal() as db:
        patient_user = await db.scalar(select(User).where(User.username == "patient"))
        assert patient_user is not None
        patient_user_id = patient_user.id

        # Create Patient A (owned by patient user)
        p_own = Patient(full_name="Own Patient", user_id=patient_user_id)
        db.add(p_own)
        # Create Patient B (belonging to another or unlinked)
        p_other = Patient(full_name="Other Patient", user_id=None)
        db.add(p_other)
        await db.commit()
        await db.refresh(p_own)
        await db.refresh(p_other)

        enc_own = Encounter(patient_id=p_own.id, chief_complaint="Own symptom")
        enc_other = Encounter(patient_id=p_other.id, chief_complaint="Other symptom")
        db.add(enc_own)
        db.add(enc_other)
        await db.commit()
        await db.refresh(enc_own)
        await db.refresh(enc_other)

        own_p_id = p_own.id
        other_p_id = p_other.id
        own_enc_id = enc_own.id
        other_enc_id = enc_other.id

    patient_token = await get_token_for(client, "patient", "Patient@1234")
    p_headers = {"Authorization": f"Bearer {patient_token}"}

    # 1. Access own patient record -> 200
    r_own = await client.get(f"/api/patients/{own_p_id}", headers=p_headers)
    assert r_own.status_code == 200
    assert r_own.json()["full_name"] == "Own Patient"

    # 2. Access other patient record -> 403
    r_other = await client.get(f"/api/patients/{other_p_id}", headers=p_headers)
    assert r_other.status_code == 403
    assert "Forbidden" in r_other.json()["detail"]

    # 3. Access own encounter -> 200
    r_enc_own = await client.get(f"/api/encounters/{own_enc_id}", headers=p_headers)
    assert r_enc_own.status_code == 200

    # 4. Access other encounter -> 403
    r_enc_other = await client.get(f"/api/encounters/{other_enc_id}", headers=p_headers)
    assert r_enc_other.status_code == 403
    assert "Forbidden" in r_enc_other.json()["detail"]

    # 5. List encounters as patient -> returns only own encounter
    r_list = await client.get("/api/encounters", headers=p_headers)
    assert r_list.status_code == 200
    enc_ids = [e["id"] for e in r_list.json()]
    assert own_enc_id in enc_ids
    assert other_enc_id not in enc_ids

    # 6. Patient cannot create encounter for other patient -> 403
    r_bad_create = await client.post(
        "/api/encounters",
        json={"patient_id": other_p_id, "chief_complaint": "Hack attempt"},
        headers=p_headers,
    )
    assert r_bad_create.status_code == 403

    # 7. Patient cannot access other patient interview -> 403
    r_bad_interview = await client.get(f"/api/interviews/{other_enc_id}/next-question", headers=p_headers)
    assert r_bad_interview.status_code == 403


@pytest.mark.asyncio
async def test_admin_only_user_registration(client: AsyncClient):
    """Non-admin roles cannot register users (403); Admin can register users (201)."""
    doc_token = await get_token_for(client, "doctor", "Doctor@1234")
    r_doc = await client.post(
        "/api/auth/register",
        json={"username": "newuser1", "password": "Test@1234", "role": "staff"},
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert r_doc.status_code == 403

    admin_token = await get_token_for(client, "admin", "Admin@1234")
    r_admin = await client.post(
        "/api/auth/register",
        json={"username": "newuser1", "password": "Test@1234", "role": "staff"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r_admin.status_code == 201
    assert r_admin.json()["username"] == "newuser1"
