"""
tests/test_auto_analysis.py
---------------------------
Automatic analysis and the Analyzed Conclusion:
  1. Answers trigger a debounced automatic run; the doctor never presses a button.
  2. A burst of answers is coalesced into a single run.
  3. Completing the interview and processing a document trigger immediately.
  4. The Analyzed Conclusion is validated, cites evidence, and lists only the
     validated considerations; it is doctor-only.
  5. Finalized cases are never auto-analysed.
  6. The dashboard overview endpoint is doctor/admin only and shows state.
"""
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.database import AsyncSessionLocal
from app.models import AuditEvent, LLMJob
from app.services import auto_analysis
from app.services.llm.manager import llm_service


async def token(client, user, pw):
    r = await client.post("/api/auth/login", json={"username": user, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
async def encounter(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Auto Case", "age": 55, "gender": "Male"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
    return e.json()["id"]


@pytest.fixture
def auto_on():
    with patch.object(settings, "AUTO_ANALYSIS_ENABLED", True), \
            patch.object(settings, "AUTO_ANALYSIS_DEBOUNCE_SECONDS", 0.2):
        yield


async def answer(client, headers, enc, key, ans):
    r = await client.post(f"/api/interviews/{enc}/responses", json={"question_key": key, "answer": ans}, headers=headers)
    assert r.status_code == 201, r.text


async def job_count(enc):
    async with AsyncSessionLocal() as db:
        return await db.scalar(select(func.count(LLMJob.id)).where(LLMJob.encounter_id == enc))


@pytest.mark.asyncio
async def test_answers_trigger_automatic_analysis_with_conclusion(client, auth_headers, encounter, auto_on):
    for key, ans in (("chief_complaint", "Chest pain when walking, with sweating"),
                     ("symptom_duration", "1 to 3 days"),
                     ("chest_symptoms", "Shortness of breath, Sweating"),
                     ("has_allergies", "No")):
        await answer(client, auth_headers, encounter, key, ans)
    await auto_analysis.wait_idle()

    assert await job_count(encounter) == 1, "a burst of answers must be coalesced into one run"
    doctor = await token(client, "doctor", "Doctor@1234")
    data = (await client.get(f"/api/analysis/{encounter}", headers=doctor)).json()
    assert data["analysis_state"] == "ready" and data["last_trigger"] == "interview_answer"
    assert data["overall_urgency"] == "EMERGENCY"

    concl = data["analyzed_conclusion"]
    assert concl["provenance"] == "ai_generated_unverified" and concl["status"] == "pending"
    c = concl["content"]
    assert "Chest pain when walking" in c["conclusion"]
    assert c["urgency"] == "EMERGENCY"
    assert [x["name"] for x in c["possible_considerations"]] == [d["content"]["name"] for d in data["possible_diagnoses"]]
    assert c["key_findings"] and all(f["evidence_ref"] for f in c["key_findings"])
    assert data["overview"]["reason_for_visit"] == "Chest pain when walking, with sweating"

    async with AsyncSessionLocal() as db:
        audit = await db.scalar(select(AuditEvent).where(AuditEvent.action == "AI_ANALYSIS_AUTO_STARTED"))
        assert audit is not None and audit.actor_username == "system"


@pytest.mark.asyncio
async def test_complete_and_new_answer_rerun_once(client, auth_headers, encounter, auto_on):
    for key, ans in (("chief_complaint", "cough with fever"), ("symptom_duration", "4 to 7 days"),
                     ("has_chronic_conditions", "No"), ("current_medications", "No"), ("has_allergies", "No")):
        await answer(client, auth_headers, encounter, key, ans)
    await auto_analysis.wait_idle()
    first = await job_count(encounter)
    r = await client.post(f"/api/interviews/{encounter}/complete", headers=auth_headers)
    assert r.status_code == 200, r.text
    await auto_analysis.wait_idle()
    assert await job_count(encounter) == first + 1


@pytest.mark.asyncio
async def test_unsafe_conclusion_is_not_stored(client, auth_headers, encounter, auto_on):
    llm_service.mock.overrides["analyzed_conclusion"] = {
        "conclusion": "The patient definitely has a heart attack.", "key_findings": [],
        "recommended_next_steps": [], "information_gaps": []}
    await answer(client, auth_headers, encounter, "chief_complaint", "chest pain")
    await auto_analysis.wait_idle()
    doctor = await token(client, "doctor", "Doctor@1234")
    data = (await client.get(f"/api/analysis/{encounter}", headers=doctor)).json()
    assert data["analyzed_conclusion"] is None
    assert any("analyzed conclusion" in n for n in data["job"]["notes"]["validation"])
    # rule-based overview still there for the dashboard
    assert data["overview"]["reason_for_visit"] == "chest pain"


@pytest.mark.asyncio
async def test_llm_down_still_gives_rule_based_overview(client, auth_headers, encounter, auto_on):
    llm_service.mock.force_unavailable = True
    await answer(client, auth_headers, encounter, "chief_complaint", "headache with weakness of face, arm or leg")
    await answer(client, auth_headers, encounter, "neuro_symptoms", "Weakness of face, arm or leg")
    await auto_analysis.wait_idle()
    doctor = await token(client, "doctor", "Doctor@1234")
    overview = (await client.get("/api/analysis/overview", headers=doctor)).json()
    item = next(i for i in overview["items"] if i["encounter_id"] == encounter)
    assert item["analysis_state"] == "ai_unavailable"
    assert item["conclusion"] is None
    assert item["urgency"] == "EMERGENCY" and item["overview"]["red_flags"]


@pytest.mark.asyncio
async def test_finalized_case_is_not_auto_analysed(client, auth_headers, encounter, auto_on):
    doctor = await token(client, "doctor", "Doctor@1234")
    assert (await client.post(f"/api/encounters/{encounter}/finalize", json={"doctor_notes": "done"},
                              headers=doctor)).status_code == 200
    auto_analysis.request_analysis(encounter, "test", delay=0)
    await auto_analysis.wait_idle()
    assert await job_count(encounter) == 0


@pytest.mark.asyncio
async def test_overview_is_doctor_only_and_sorted_by_urgency(client, auth_headers, auto_on):
    encs = []
    for name, cc in (("Calm Case", "mild itchy rash"), ("Urgent Case", "chest pain with shortness of breath and sweating")):
        p = await client.post("/api/patients", json={"full_name": name, "age": 40, "gender": "Female"}, headers=auth_headers)
        e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True}, headers=auth_headers)
        encs.append(e.json()["id"])
        await answer(client, auth_headers, e.json()["id"], "chief_complaint", cc)
    await auto_analysis.wait_idle()

    for user, pw in (("staff", "Staff@1234"), ("patient", "Patient@1234")):
        assert (await client.get("/api/analysis/overview", headers=await token(client, user, pw))).status_code == 403
    doctor = await token(client, "doctor", "Doctor@1234")
    items = (await client.get("/api/analysis/overview", headers=doctor)).json()["items"]
    ours = [i for i in items if i["encounter_id"] in encs]
    assert ours[0]["patient_name"] == "Urgent Case" and ours[0]["urgency"] == "EMERGENCY"
    assert all(i["analysis_state"] == "ready" and i["conclusion"] for i in ours)


@pytest.mark.asyncio
async def test_self_registration_reason_starts_tailored_interview(client):
    r = await client.post("/api/patients/self-register", json={
        "username": "selfreg_auto", "password": "Strong@12345", "full_name": "Self Reg",
        "age": 30, "gender": "Female", "chief_complaint": "burning while passing urine", "consent_given": True,
    })
    assert r.status_code == 201, r.text
    body = r.json()
    h = {"Authorization": f"Bearer {body['access_token']}"}
    enc = body["encounter"]["id"]
    prog = (await client.get(f"/api/interviews/{enc}/progress", headers=h)).json()
    assert "chief_complaint" in prog["answered_keys"]
    assert "urinary_symptoms" in [i["key"] for i in prog["active_path"]]
    # the patient cannot read the AI analysis
    assert (await client.get(f"/api/analysis/{enc}", headers=h)).status_code == 403


@pytest.mark.asyncio
async def test_startup_backfill_analyses_cases_never_analysed(client, auth_headers, encounter):
    # answer while automatic analysis is off (as for cases created before the feature)
    await answer(client, auth_headers, encounter, "chief_complaint", "dry cough for two weeks")
    assert await job_count(encounter) == 0
    with patch.object(settings, "AUTO_ANALYSIS_ENABLED", True):
        queued = await auto_analysis.backfill_unanalyzed()
        await auto_analysis.wait_idle()
        assert queued >= 1
        assert await job_count(encounter) == 1
        assert await auto_analysis.backfill_unanalyzed() == 0  # never twice


@pytest.mark.asyncio
async def test_retired_questions_are_never_listed(client, auth_headers, encounter):
    from app.models import Question
    async with AsyncSessionLocal() as db:
        db.add(Question(key="old_retired_q", text="Old?", answer_type="text", order=99,
                        branching_rules={"retired": True}, skip_why="old rule"))
        await db.commit()
    await answer(client, auth_headers, encounter, "chief_complaint", "rash")
    prog = (await client.get(f"/api/interviews/{encounter}/progress", headers=auth_headers)).json()
    keys = [i["key"] for i in prog["active_path"]] + [s["key"] for s in prog["skipped_questions"]]
    assert "old_retired_q" not in keys


@pytest.mark.asyncio
async def test_registration_reason_is_also_analysed(client, auth_headers):
    p = await client.post("/api/patients", json={"full_name": "Two Reasons", "age": 60, "gender": "Male"}, headers=auth_headers)
    e = await client.post("/api/encounters", json={"patient_id": p.json()["id"], "consent_given": True,
                                                   "chief_complaint": "chest tightness and shortness of breath"},
                          headers=auth_headers)
    enc = e.json()["id"]
    from app.database import AsyncSessionLocal as S
    from app.models import Question, Response
    async with S() as db:  # interview answer stored without touching the encounter text (legacy data)
        q = await db.scalar(select(Question).where(Question.key == "chief_complaint"))
        db.add(Response(encounter_id=enc, question_id=q.id, question_key="chief_complaint", answer="Chest discomfort"))
        await db.commit()
    doctor = await token(client, "doctor", "Doctor@1234")
    await client.post(f"/api/analysis/{enc}/run", headers=doctor)
    data = (await client.get(f"/api/analysis/{enc}", headers=doctor)).json()
    assert data["overall_urgency"] == "EMERGENCY"
