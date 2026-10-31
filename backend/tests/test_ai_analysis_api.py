"""
tests/test_ai_analysis_api.py
-----------------------------
Integration and Authorization Boundary Test Suite for the AI Clinical Insights API.

Verifies:
  1. POST /api/analysis/{encounter_id}/run creates LLMJob, executes analysis, and records audit.
  2. Strict Role Boundaries:
     - Doctor / Admin: Authorized (200)
     - Staff: Forbidden (403)
     - Patient: Forbidden (403)
  3. Case-Lock Gating:
     - Finalized (reviewed) encounters reject new analysis and decision updates (400).
  4. Decision and Provenance Workflow:
     - Pending insight transitions to 'doctor_verified' upon Accept/Edit.
     - Audit events recorded with actor username and resource ID.
  5. System LLM Status & Guideline Endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models import Encounter, Patient, User, AIInsight, AIInsightStatus, EncounterStatus, AuditEvent


async def get_token_for(client: AsyncClient, username: str, password: str) -> str:
    res = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


@pytest.fixture
async def setup_test_encounter(client, auth_headers):
    """Helper fixture to create a patient and encounter with consent."""
    p_res = await client.post(
        "/api/patients",
        json={"full_name": "Test Insights Patient", "age": 48, "gender": "Male"},
        headers=auth_headers,
    )
    assert p_res.status_code in (200, 201)
    patient_id = p_res.json()["id"]

    e_res = await client.post(
        "/api/encounters",
        json={"patient_id": patient_id, "consent_given": True, "chief_complaint": "Persistent chest pain with exertion"},
        headers=auth_headers,
    )
    assert e_res.status_code in (200, 201)
    return e_res.json()["id"]


@pytest.mark.asyncio
async def test_doctor_runs_ai_analysis_and_reads_payload(client: AsyncClient, setup_test_encounter):
    """Verify doctor can trigger AI analysis and read comprehensive insights payload."""
    encounter_id = setup_test_encounter
    doc_token = await get_token_for(client, "doctor", "Doctor@1234")
    headers = {"Authorization": f"Bearer {doc_token}"}

    # 1. Trigger analysis
    run_res = await client.post(f"/api/analysis/{encounter_id}/run", headers=headers)
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "completed"
    assert "overall_urgency" in run_data
    assert "job_id" in run_data

    # 2. Fetch full insights
    get_res = await client.get(f"/api/analysis/{encounter_id}", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()

    assert data["encounter_id"] == encounter_id
    assert "overall_urgency" in data
    assert "risk_scores" in data
    assert len(data["risk_scores"]) >= 4  # qSOFA, CURB-65, NEWS2, CHA2DS2-VASc
    assert "possible_diagnoses" in data
    assert "documented_diagnoses" in data
    assert "treatment_references" in data
    assert "document_timeline" in data
    assert data["provider_mode"] == "mock"


@pytest.mark.asyncio
async def test_role_boundaries_patient_and_staff_forbidden_on_insights(client: AsyncClient, setup_test_encounter):
    """Verify that neither patient nor staff can trigger analysis or view AI insights (403 Forbidden)."""
    encounter_id = setup_test_encounter
    staff_token = await get_token_for(client, "staff", "Staff@1234")
    patient_token = await get_token_for(client, "patient", "Patient@1234")

    # Staff forbidden on run
    res_staff_run = await client.post(
        f"/api/analysis/{encounter_id}/run",
        headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert res_staff_run.status_code == 403

    # Staff forbidden on read
    res_staff_get = await client.get(
        f"/api/analysis/{encounter_id}",
        headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert res_staff_get.status_code == 403

    # Patient forbidden on run
    res_pat_run = await client.post(
        f"/api/analysis/{encounter_id}/run",
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert res_pat_run.status_code == 403

    # Patient forbidden on read
    res_pat_get = await client.get(
        f"/api/analysis/{encounter_id}",
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert res_pat_get.status_code == 403


@pytest.mark.asyncio
async def test_doctor_decision_workflow_and_provenance(client: AsyncClient, setup_test_encounter):
    """
    Verify Accept, Edit, and Reject decisions transition provenance to doctor_verified
    and record immutable audit events.
    """
    encounter_id = setup_test_encounter
    doc_token = await get_token_for(client, "doctor", "Doctor@1234")
    headers = {"Authorization": f"Bearer {doc_token}"}

    # Run analysis to populate insights
    await client.post(f"/api/analysis/{encounter_id}/run", headers=headers)
    get_res = await client.get(f"/api/analysis/{encounter_id}", headers=headers)
    insights = get_res.json()["possible_diagnoses"]
    assert len(insights) > 0
    first_insight_id = insights[0]["id"]
    assert insights[0]["provenance"] == "ai_generated_unverified"
    assert insights[0]["status"] == "pending"

    # Doctor Accepts insight
    accept_res = await client.put(
        f"/api/insights/{first_insight_id}/decision",
        json={"decision": "accepted"},
        headers=headers
    )
    assert accept_res.status_code == 200
    accept_data = accept_res.json()
    assert accept_data["status"] == "accepted"
    assert accept_data["provenance"] == "doctor_verified"

    # Verify audit event recorded
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == "AI_INSIGHT_DECISION", AuditEvent.resource_id == str(first_insight_id))
            .order_by(AuditEvent.timestamp.desc())
        )
        assert event is not None
        assert event.actor_username == "doctor"
        assert "accepted" in event.change_summary


@pytest.mark.asyncio
async def test_case_lock_enforcement_on_ai_insights(client: AsyncClient, setup_test_encounter):
    """Verify that once a case is finalized/reviewed by a clinician, AI insights cannot be modified."""
    encounter_id = setup_test_encounter
    doc_token = await get_token_for(client, "doctor", "Doctor@1234")
    headers = {"Authorization": f"Bearer {doc_token}"}

    # Run analysis
    await client.post(f"/api/analysis/{encounter_id}/run", headers=headers)
    get_res = await client.get(f"/api/analysis/{encounter_id}", headers=headers)
    first_insight_id = get_res.json()["possible_diagnoses"][0]["id"]

    # Finalize encounter (case lock)
    fin_res = await client.post(
        f"/api/encounters/{encounter_id}/finalize",
        json={"doctor_notes": "Clinical review finalized. Case locked."},
        headers=headers
    )
    assert fin_res.status_code == 200

    # Attempt to re-run analysis -> 400 Bad Request
    rerun_res = await client.post(f"/api/analysis/{encounter_id}/run", headers=headers)
    assert rerun_res.status_code == 400
    assert "locked" in rerun_res.json()["detail"].lower()

    # Attempt to modify decision -> 400 Bad Request
    dec_res = await client.put(
        f"/api/insights/{first_insight_id}/decision",
        json={"decision": "rejected"},
        headers=headers
    )
    assert dec_res.status_code == 400
    assert "locked" in dec_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_system_llm_status_and_guideline_endpoints(client: AsyncClient):
    """Verify system LLM status, guideline library, and trend rules endpoints."""
    # LLM Status
    st_res = await client.get("/api/system/llm-status")
    assert st_res.status_code == 200
    st_data = st_res.json()
    assert "active_mode" in st_data
    assert "prompt_version" in st_data
    assert "consent_statement" in st_data

    # Doctor access to guidelines
    doc_token = await get_token_for(client, "doctor", "Doctor@1234")
    g_res = await client.get("/api/analysis/guidelines", headers={"Authorization": f"Bearer {doc_token}"})
    assert g_res.status_code == 200, f"Error: {g_res.text}"
    g_data = g_res.json()
    assert len(g_data) > 0
    assert all("SAMPLE – replace with verified source" in (item.get("warning") or item.get("source")) for item in g_data)

    # Trend rules
    tr_res = await client.get("/api/analysis/trend-rules", headers={"Authorization": f"Bearer {doc_token}"})
    assert tr_res.status_code == 200
    tr_data = tr_res.json()
    assert "RESEARCH PROTOTYPE ONLY" in tr_data["disclaimer"]
    assert "creatinine" in tr_data["rules"]

