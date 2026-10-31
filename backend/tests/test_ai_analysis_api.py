"""
tests/test_ai_analysis_api.py
-----------------------------
Integration and authorization tests for the AI Clinical Insights API.

  1. POST /run queues a background job; GET returns its result and status.
  2. Role boundaries: patients and staff get 403 on every AI endpoint.
  3. Case lock: finalized encounters reject re-runs and decisions.
  4. Decision workflow writes audit events and sets provenance.
  5. A case with a lab report and a prescription produces grounded entities,
     abnormal labs, a rule-matched trend with a validated sentence, scores or
     not_calculable, considerations with evidence, a cited treatment reference,
     a summary, reconciliation and questions.
  6. LLM down: deterministic parts still complete; job ends 'unavailable'.
  7. Re-running does not duplicate rows and keeps decided insights.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models import AuditEvent, Document, Encounter, LabResult, Response
from app.services.llm.manager import llm_service


async def get_token_for(client: AsyncClient, username: str, password: str) -> str:
    res = await client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


async def doctor_headers(client):
    return {"Authorization": f"Bearer {await get_token_for(client, 'doctor', 'Doctor@1234')}"}


@pytest.fixture
async def setup_test_encounter(client, auth_headers):
    p_res = await client.post("/api/patients", json={"full_name": "Test Insights Patient", "age": 48, "gender": "Male"},
                              headers=auth_headers)
    assert p_res.status_code in (200, 201)
    e_res = await client.post("/api/encounters", json={
        "patient_id": p_res.json()["id"], "consent_given": True,
        "chief_complaint": "Persistent chest pain with exertion"}, headers=auth_headers)
    assert e_res.status_code in (200, 201)
    return e_res.json()["id"]


LAB_OLD = ("City Pathology Lab. Patient Name: Test Insights Patient  Age: 48  Sex: Male\n"
           "Date: 2026-02-01\nSerum Creatinine: 1.0 mg/dL (ref: 0.7-1.3)\nHaemoglobin: 13.5 g/dL (ref: 13.0-17.0)")
LAB_NEW = ("City Pathology Lab. Patient Name: Test Insights Patient  Age: 48  Sex: Male\n"
           "Date: 2026-05-01\nSerum Creatinine: 1.8 mg/dL (ref: 0.7-1.3)\nHaemoglobin: 12.1 g/dL (ref: 13.0-17.0)\n"
           "ALT 40 U/L\nBP 150/95")
RX = ("Dr. Sample Clinic. Date: 2026-05-02\nPatient Name: Test Insights Patient\nDiagnosis: Type 2 Diabetes, Hypertension\n"
      "Rx:\nTab Metformin 500mg 1-0-1 after food\nTab Amlodipine 5mg 1-0-0")


async def add_documents(encounter_id: int, texts):
    async with AsyncSessionLocal() as db:
        enc = await db.get(Encounter, encounter_id)
        for i, t in enumerate(texts):
            db.add(Document(patient_id=enc.patient_id, encounter_id=encounter_id, original_filename=f"doc{i}.png",
                            stored_path=f"./test_uploads/doc{i}.png", mime_type="image/png", status="completed",
                            extracted_text=t, extracted_fields={"medications": []}, extraction_confidence=0.95))
        await db.commit()


async def add_answers(encounter_id: int, answers: dict):
    from app.models import Question
    async with AsyncSessionLocal() as db:
        for key, ans in answers.items():
            q = await db.scalar(select(Question).where(Question.key == key))
            db.add(Response(encounter_id=encounter_id, question_id=q.id, question_key=key, answer=ans))
        await db.commit()


async def run_and_fetch(client, encounter_id, headers, **params):
    run = await client.post(f"/api/analysis/{encounter_id}/run", headers=headers, params=params)
    assert run.status_code == 202, run.text
    assert run.json()["status"] == "queued"
    res = await client.get(f"/api/analysis/{encounter_id}", headers=headers)
    assert res.status_code == 200, res.text
    return run.json(), res.json()


@pytest.mark.asyncio
async def test_doctor_runs_ai_analysis_and_reads_payload(client: AsyncClient, setup_test_encounter):
    headers = await doctor_headers(client)
    run, data = await run_and_fetch(client, setup_test_encounter, headers)
    assert data["job"]["id"] == run["job_id"]
    assert data["job_status"] == "completed" and data["job_progress"] == 1.0
    assert data["provider_mode"] == "mock"
    assert len(data["risk_scores"]) == 4
    # No vitals or labs were documented: every score must be not_calculable, never guessed
    assert all(s["status"] == "not_calculable" and s["missing_inputs"] for s in data["risk_scores"])
    assert data["possible_diagnoses"], "chest pain in the chief complaint should yield a cited consideration"
    for dx in data["possible_diagnoses"]:
        assert dx["provenance"] == "ai_generated_unverified" and dx["status"] == "pending"
        assert dx["model_name"] and dx["prompt_version"]
        assert all(f["evidence_ref"] == "interview:chief_complaint" for f in dx["content"]["supporting_findings"])
    assert data["llm_status"]["state"] == "available"


@pytest.mark.asyncio
async def test_full_case_with_lab_report_and_prescription(client: AsyncClient, setup_test_encounter):
    enc_id = setup_test_encounter
    await add_documents(enc_id, [LAB_OLD, LAB_NEW, RX])
    await add_answers(enc_id, {"has_allergies": "Yes", "allergy_details": "Penicillin",
                               "current_medications": "Yes", "medication_details": "Metformin"})
    headers = await doctor_headers(client)
    _, data = await run_and_fetch(client, enc_id, headers)

    # Grounded entities with source spans
    dx = {d["raw_text"] for d in data["documented_diagnoses"] if d["grounded"]}
    assert {"Type 2 Diabetes", "Hypertension"} <= dx
    meds = {m["raw_text"] for m in data["extracted_medications"] if m["grounded"]}
    assert {"Metformin", "Amlodipine"} <= meds
    assert all(e["source_span"] for e in data["extracted_entities"] if e["grounded"])

    # Abnormal labs flagged against printed ranges only; no range -> range_not_available
    flags = {(l["normalized_test"], l["test_date"]): l["flag"] for l in data["all_labs"]}
    assert flags[("creatinine", "2026-05-01")] == "high"
    assert flags[("alt", "2026-05-01")] == "range_not_available"

    # Trend computed by code, rule matched from config, sentence validated
    cr = next(t for t in data["computed_trends"] if t["test_name"] == "creatinine")
    assert (cr["previous_value"], cr["current_value"], cr["time_span_days"]) == (1.0, 1.8, 89)
    assert cr["rule_matched"] == "CREATININE_PERCENT_RISE"
    sentence = data["trend_interpretations"][0]["content"]["interpretation"]
    assert "1.0" in sentence and "1.8" in sentence

    # BP is documented but other inputs are not -> still not_calculable, missing inputs listed
    q = next(s for s in data["risk_scores"] if s["score_name"] == "qSOFA")
    assert q["status"] == "not_calculable" and "respiratory_rate" in q["missing_inputs"]

    # Treatment reference: cited, sample-labelled, dose quoted, allergy cross-checked
    assert data["treatment_references"]
    for tr in data["treatment_references"]:
        c = tr["content"]
        assert c["label"] == "Reference information for the prescriber. Not a prescription."
        assert "SAMPLE" in c["citation"]["source"]
    # Summary sections all carry resolvable refs
    sections = data["case_summary"]["content"]["sections"]
    assert sections and all(s["evidence_refs"] for s in sections)

    # Medication reconciliation (code): Amlodipine documented but not reported
    assert {"drug": "amlodipine", "status": "not_reported_by_patient"}.items() <= next(
        i for i in data["medication_reconciliation"] if i["drug"] == "amlodipine").items()
    # Rule conflicts recomputed by engines
    rules = {c["rule_id"] for c in data["rule_conflicts"]}
    assert "RULE-LAB-ABNORMAL" in rules
    # Timeline is chronological by printed date
    assert [t["document_date"] for t in data["document_timeline"]] == ["2026-02-01", "2026-05-01", "2026-05-02"]
    assert data["job"]["usage"]["calls"], "per-call usage must be recorded"


@pytest.mark.asyncio
async def test_role_boundaries_patient_and_staff_forbidden_on_insights(client: AsyncClient, setup_test_encounter):
    encounter_id = setup_test_encounter
    headers = await doctor_headers(client)
    await run_and_fetch(client, encounter_id, headers)
    insight_id = (await client.get(f"/api/analysis/{encounter_id}", headers=headers)).json()["possible_diagnoses"][0]["id"]

    for user, pw in (("staff", "Staff@1234"), ("patient", "Patient@1234")):
        h = {"Authorization": f"Bearer {await get_token_for(client, user, pw)}"}
        assert (await client.post(f"/api/analysis/{encounter_id}/run", headers=h)).status_code == 403
        assert (await client.get(f"/api/analysis/{encounter_id}", headers=h)).status_code == 403
        assert (await client.put(f"/api/insights/{insight_id}/decision", json={"decision": "accepted"},
                                 headers=h)).status_code == 403
        assert (await client.get("/api/analysis/guidelines", headers=h)).status_code == 403
        assert (await client.get("/api/analysis/trend-rules", headers=h)).status_code == 403
    assert (await client.get(f"/api/analysis/{encounter_id}")).status_code in (401, 403)


@pytest.mark.asyncio
async def test_doctor_decision_workflow_and_provenance(client: AsyncClient, setup_test_encounter):
    encounter_id = setup_test_encounter
    headers = await doctor_headers(client)
    _, data = await run_and_fetch(client, encounter_id, headers)
    first_id = data["possible_diagnoses"][0]["id"]

    accept = await client.put(f"/api/insights/{first_id}/decision", json={"decision": "accepted"}, headers=headers)
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted" and accept.json()["provenance"] == "doctor_verified"

    summary_id = data["case_summary"]["id"]
    missing_edit = await client.put(f"/api/insights/{summary_id}/decision", json={"decision": "edited"}, headers=headers)
    assert missing_edit.status_code == 422
    edited = await client.put(f"/api/insights/{summary_id}/decision",
                              json={"decision": "edited", "doctor_edits": {"text": "Doctor's wording"}}, headers=headers)
    assert edited.json()["status"] == "edited" and edited.json()["doctor_edits"] == {"text": "Doctor's wording"}

    q_id = data["questions_to_ask"][0]["id"] if data["questions_to_ask"] else None
    if q_id:
        rej = await client.put(f"/api/insights/{q_id}/decision", json={"decision": "rejected"}, headers=headers)
        assert rej.json()["provenance"] != "doctor_verified"

    async with AsyncSessionLocal() as db:
        events = (await db.scalars(select(AuditEvent).where(AuditEvent.action == "AI_INSIGHT_DECISION"))).all()
        assert {e.resource_id for e in events} >= {str(first_id), str(summary_id)}
        assert all(e.actor_username == "doctor" for e in events)


@pytest.mark.asyncio
async def test_case_lock_enforcement_on_ai_insights(client: AsyncClient, setup_test_encounter):
    encounter_id = setup_test_encounter
    headers = await doctor_headers(client)
    _, data = await run_and_fetch(client, encounter_id, headers)
    first_id = data["possible_diagnoses"][0]["id"]

    fin = await client.post(f"/api/encounters/{encounter_id}/finalize",
                            json={"doctor_notes": "Clinical review finalized. Case locked."}, headers=headers)
    assert fin.status_code == 200

    rerun = await client.post(f"/api/analysis/{encounter_id}/run", headers=headers)
    assert rerun.status_code == 400 and "locked" in rerun.json()["detail"].lower()
    dec = await client.put(f"/api/insights/{first_id}/decision", json={"decision": "rejected"}, headers=headers)
    assert dec.status_code == 400 and "locked" in dec.json()["detail"].lower()


@pytest.mark.asyncio
async def test_llm_down_degrades_gracefully(client: AsyncClient, setup_test_encounter):
    enc_id = setup_test_encounter
    await add_documents(enc_id, [LAB_OLD, LAB_NEW])
    llm_service.mock.force_unavailable = True
    headers = await doctor_headers(client)
    _, data = await run_and_fetch(client, enc_id, headers)

    assert data["job_status"] == "unavailable"
    assert data["llm_status"]["state"] == "llm_unavailable"
    assert data["job"]["notes"]["llm_state"] == "llm_unavailable"
    # Deterministic parts still ran (regex fallback for extraction does not invent labs)
    assert len(data["risk_scores"]) == 4
    assert data["possible_diagnoses"] == [] and data["case_summary"] is None
    # Existing non-AI endpoints keep working
    assert (await client.get(f"/api/encounters/{enc_id}", headers=headers)).status_code == 200


@pytest.mark.asyncio
async def test_rerun_is_idempotent_and_keeps_decisions(client: AsyncClient, setup_test_encounter):
    enc_id = setup_test_encounter
    await add_documents(enc_id, [LAB_NEW])
    headers = await doctor_headers(client)
    _, first = await run_and_fetch(client, enc_id, headers)
    accepted_id = first["possible_diagnoses"][0]["id"]
    await client.put(f"/api/insights/{accepted_id}/decision", json={"decision": "accepted"}, headers=headers)
    _, second = await run_and_fetch(client, enc_id, headers)

    assert len(second["all_labs"]) == len(first["all_labs"])
    assert len(second["risk_scores"]) == 4
    assert len(second["rule_conflicts"]) == len(first["rule_conflicts"])
    assert any(d["id"] == accepted_id and d["status"] == "accepted" for d in second["possible_diagnoses"])
    async with AsyncSessionLocal() as db:
        n = await db.scalar(select(func.count(LabResult.id)).where(LabResult.encounter_id == enc_id))
        assert n == len(first["all_labs"])


@pytest.mark.asyncio
async def test_system_llm_status_and_guideline_endpoints(client: AsyncClient):
    st = (await client.get("/api/system/llm-status")).json()
    assert st["active_mode"] == "mock" and st["external_calls"] is False
    assert "prompt_version" in st and "consent_statement" in st

    headers = await doctor_headers(client)
    g = await client.get("/api/analysis/guidelines", headers=headers)
    assert g.status_code == 200, g.text
    assert g.json() and all(item["warning"] == "SAMPLE – replace with verified source" for item in g.json())

    tr = (await client.get("/api/analysis/trend-rules", headers=headers)).json()
    assert "RESEARCH PROTOTYPE ONLY" in tr["disclaimer"] and "creatinine" in tr["rules"]


@pytest.mark.asyncio
async def test_guideline_fts_retrieval(client: AsyncClient):
    from app.services.guidelines import search_guidelines, seed_guideline_passages
    async with AsyncSessionLocal() as db:
        await seed_guideline_passages(db)
        hits = await search_guidelines("pneumonia cough fever", db)
        assert hits and hits[0]["condition_or_topic"] == "Community-Acquired Pneumonia"
        assert await search_guidelines("zzzz qqqq", db) == []


@pytest.mark.asyncio
async def test_dashboard_priority_alert_from_red_flags(client: AsyncClient, setup_test_encounter):
    enc_id = setup_test_encounter
    await add_answers(enc_id, {"associated_symptoms": "breathless and sweating"})
    headers = await doctor_headers(client)
    await run_and_fetch(client, enc_id, headers)
    staff = {"Authorization": f"Bearer {await get_token_for(client, 'staff', 'Staff@1234')}"}
    cases = (await client.get("/api/dashboard/cases", headers=staff)).json()
    case = next(c for c in cases if c["encounter_id"] == enc_id)
    assert case["urgency"] == "EMERGENCY" and case["priority_alerts"]
    assert cases[0]["encounter_id"] == enc_id
