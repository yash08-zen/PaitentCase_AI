"""
tests/test_adaptive_interview.py
---------------------------------
Comprehensive unit and integration test suite for Milestone M4:
Guided Interview and Adaptive Rule Engine (FR-02, FR-03).

Covers:
  1. Free-text reason for visit as initial question
  2. Complaint modules: pain -> pain questions (unrelated modules skipped)
  3. Complaint modules: chest -> exertion & chest symptoms
  4. Complaint modules chosen from Hindi / Marathi text
  5. Fever complaint -> skips redundant fever question (skip_if)
  6. Branching: No medications -> skips details and dosage
  7. Branching: Yes medications -> triggers details and dosage
  8. Branching: No allergies -> skips details and reaction
  9. Branching: Yes allergies -> triggers details and reaction
 10. Bidirectional navigation (Back) & dynamic branch re-evaluation / pruning
 11. Interrupted session resume at exact unanswered question
 12. Deterministic completion from required fields
 13. Source metadata ('patient_reported') and timestamp verification
"""
import pytest
from app.models import Response
from sqlalchemy import select


@pytest.fixture
async def interview_encounter(client, auth_headers):
    """Helper fixture to register a patient and encounter with consent."""
    p_res = await client.post(
        "/api/patients",
        json={"full_name": "Adaptive Test Patient", "age": 35, "gender": "Female"},
        headers=auth_headers,
    )
    assert p_res.status_code in (200, 201)
    p_id = p_res.json()["id"]

    e_res = await client.post(
        "/api/encounters",
        json={"patient_id": p_id, "consent_given": True},
        headers=auth_headers,
    )
    assert e_res.status_code in (200, 201)
    return e_res.json()["id"]


async def _answer(client, headers, enc, key, ans):
    r = await client.post(f"/api/interviews/{enc}/responses", json={"question_key": key, "answer": ans}, headers=headers)
    assert r.status_code == 201, r.text
    return r


async def _active_keys(client, headers, enc):
    prog = await client.get(f"/api/interviews/{enc}/progress", headers=headers)
    return [i["key"] for i in prog.json()["active_path"]], [s["key"] for s in prog.json()["skipped_questions"]]


@pytest.mark.asyncio
async def test_first_question_is_free_text_reason_for_visit(client, auth_headers, interview_encounter):
    """1. The first question asks for the reason for visit in the patient's own words."""
    res = await client.get(f"/api/interviews/{interview_encounter}/next-question", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is False
    assert data["question"]["key"] == "chief_complaint"
    assert data["question"]["answer_type"] == "text"
    assert not data["question"]["choices"]
    assert data["can_go_back"] is False


@pytest.mark.asyncio
async def test_pain_complaint_adds_pain_questions(client, auth_headers, interview_encounter):
    """2. A free-text pain complaint adds the pain module; unrelated modules stay out."""
    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "Sharp pain in my lower belly since yesterday")
    active, skipped = await _active_keys(client, auth_headers, interview_encounter)
    assert {"pain_location", "pain_character", "pain_radiation", "gi_symptoms"} <= set(active)
    assert "cough_type" in skipped and "urinary_symptoms" in skipped
    # generic questions apply to every complaint
    assert {"symptom_onset", "symptom_duration", "symptom_course", "symptom_triggers"} <= set(active)

    for key, ans in (("symptom_onset", "Suddenly"), ("symptom_duration", "1 to 3 days"), ("symptom_severity", "6"),
                     ("symptom_course", "Getting worse"), ("symptom_triggers", "worse after food"),
                     ("previous_episodes", "No")):
        await _answer(client, auth_headers, interview_encounter, key, ans)
    nxt = (await client.get(f"/api/interviews/{interview_encounter}/next-question", headers=auth_headers)).json()
    assert nxt["question"]["key"] == "pain_location"
    assert nxt["adaptive_note"] and "pain" in nxt["adaptive_note"].lower()
    assert "Lower abdomen" in nxt["question"]["choices"]


@pytest.mark.asyncio
async def test_chest_complaint_adds_exertion_and_chest_symptoms(client, auth_headers, interview_encounter):
    """3. Chest complaints add exertion and chest-symptom questions."""
    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "Tightness in chest when I climb stairs")
    active, _ = await _active_keys(client, auth_headers, interview_encounter)
    assert "worse_with_activity" in active and "chest_symptoms" in active


@pytest.mark.asyncio
async def test_hindi_and_marathi_complaints_select_modules(client, auth_headers, interview_encounter):
    """4. Complaints typed in Hindi or Marathi choose the same modules."""
    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "तीन दिन से बुखार और खांसी है")
    active, _ = await _active_keys(client, auth_headers, interview_encounter)
    assert {"fever_pattern", "cough_type", "breathlessness_level"} <= set(active)

    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "लघवी करताना जळजळ होते")
    active, _ = await _active_keys(client, auth_headers, interview_encounter)
    assert "urinary_symptoms" in active and "fever_pattern" not in active


@pytest.mark.asyncio
async def test_fever_complaint_skips_has_fever_question(client, auth_headers, interview_encounter):
    """5. When the complaint mentions fever, the generic fever question is skipped (skip_if)."""
    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "High fever with chills")
    _, skipped = await _active_keys(client, auth_headers, interview_encounter)
    assert "has_fever" in skipped


@pytest.mark.asyncio
async def test_changing_complaint_prunes_answers_of_dropped_modules(client, auth_headers, interview_encounter):
    """Changing the reason for visit removes answers to questions that no longer apply."""
    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "cough for a week")
    await _answer(client, auth_headers, interview_encounter, "cough_type", "Dry cough")
    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "itchy rash on arms")
    keys = [a["question_key"] for a in (await client.get(f"/api/interviews/{interview_encounter}/answers",
                                                          headers=auth_headers)).json()]
    assert "cough_type" not in keys


@pytest.mark.asyncio
async def test_localized_choice_answers_drive_branching(client, auth_headers, interview_encounter):
    """Choices answered in Hindi ('हां (Yes)') branch exactly like English ones."""
    await _answer(client, auth_headers, interview_encounter, "current_medications", "हां (Yes)")
    active, _ = await _active_keys(client, auth_headers, interview_encounter)
    assert "medication_details" in active


@pytest.mark.asyncio
async def test_reason_for_visit_is_stored_on_encounter(client, auth_headers, interview_encounter):
    await _answer(client, auth_headers, interview_encounter, "chief_complaint", "Back pain after lifting a box")
    enc = (await client.get(f"/api/encounters/{interview_encounter}", headers=auth_headers)).json()
    assert enc["chief_complaint"] == "Back pain after lifting a box"


@pytest.mark.asyncio
async def test_no_medications_skips_medication_details_and_dosage(
    client, auth_headers, interview_encounter
):
    """6. Answering 'No' to current_medications skips medication_details and medication_dosage."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "current_medications", "answer": "No"},
        headers=auth_headers,
    )

    progress = await client.get(
        f"/api/interviews/{interview_encounter}/progress",
        headers=auth_headers,
    )
    assert progress.status_code == 200
    data = progress.json()
    skipped_keys = [s["key"] for s in data["skipped_questions"]]
    assert "medication_details" in skipped_keys
    assert "medication_dosage" in skipped_keys


@pytest.mark.asyncio
async def test_yes_medications_triggers_details_and_dosage(
    client, auth_headers, interview_encounter
):
    """7. Answering 'Yes' to current_medications activates medication_details and medication_dosage."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "current_medications", "answer": "Yes"},
        headers=auth_headers,
    )

    progress = await client.get(
        f"/api/interviews/{interview_encounter}/progress",
        headers=auth_headers,
    )
    assert progress.status_code == 200
    active_keys = [item["key"] for item in progress.json()["active_path"]]
    assert "medication_details" in active_keys
    assert "medication_dosage" in active_keys


@pytest.mark.asyncio
async def test_no_allergies_skips_allergy_details_and_reaction(
    client, auth_headers, interview_encounter
):
    """8. Answering 'No' to has_allergies skips allergy_details and allergy_reaction."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "has_allergies", "answer": "No"},
        headers=auth_headers,
    )

    progress = await client.get(
        f"/api/interviews/{interview_encounter}/progress",
        headers=auth_headers,
    )
    skipped_keys = [s["key"] for s in progress.json()["skipped_questions"]]
    assert "allergy_details" in skipped_keys
    assert "allergy_reaction" in skipped_keys


@pytest.mark.asyncio
async def test_yes_allergies_triggers_allergen_and_reaction(
    client, auth_headers, interview_encounter
):
    """9. Answering 'Yes' to has_allergies activates allergy_details and allergy_reaction."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "has_allergies", "answer": "Yes"},
        headers=auth_headers,
    )

    progress = await client.get(
        f"/api/interviews/{interview_encounter}/progress",
        headers=auth_headers,
    )
    active_keys = [item["key"] for item in progress.json()["active_path"]]
    assert "allergy_details" in active_keys
    assert "allergy_reaction" in active_keys


@pytest.mark.asyncio
async def test_back_navigation_and_branch_reevaluation(
    client, auth_headers, interview_encounter
):
    """
    10. Going back and changing an answer from Yes to No re-evaluates the path
    and automatically prunes downstream answers from the database.
    """
    # 1. Answer current_medications = Yes
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "current_medications", "answer": "Yes"},
        headers=auth_headers,
    )
    # 2. Answer medication_details = Metformin 500mg
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "medication_details", "answer": "Metformin 500mg"},
        headers=auth_headers,
    )

    # Verify medication_details is saved
    answers = await client.get(
        f"/api/interviews/{interview_encounter}/answers",
        headers=auth_headers,
    )
    ans_keys = [a["question_key"] for a in answers.json()]
    assert "medication_details" in ans_keys

    # 3. Call back endpoint
    back_res = await client.post(
        f"/api/interviews/{interview_encounter}/back",
        headers=auth_headers,
    )
    assert back_res.status_code == 200

    # 4. Change current_medications to No
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "current_medications", "answer": "No"},
        headers=auth_headers,
    )

    # 5. Check answers list again - medication_details must be pruned!
    answers_after = await client.get(
        f"/api/interviews/{interview_encounter}/answers",
        headers=auth_headers,
    )
    ans_keys_after = [a["question_key"] for a in answers_after.json()]
    assert "medication_details" not in ans_keys_after


@pytest.mark.asyncio
async def test_interrupted_session_resumes_at_correct_unanswered_question(
    client, auth_headers, interview_encounter
):
    """11. An interrupted session resumes at the first unanswered applicable question."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "chief_complaint", "answer": "Cough"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "symptom_duration", "answer": "More than a week"},
        headers=auth_headers,
    )

    # Simulate resuming interview in a new session
    resume_res = await client.post(
        f"/api/interviews/{interview_encounter}/resume",
        headers=auth_headers,
    )
    assert resume_res.status_code == 200
    data = resume_res.json()
    assert data["question"]["key"] == "symptom_onset"  # first unanswered applicable question
    assert data["answered_count"] == 2


@pytest.mark.asyncio
async def test_answer_stored_with_patient_reported_source_and_timestamp(
    client, auth_headers, interview_encounter
):
    """12. Each answer is saved with source='patient_reported' and timestamp."""
    sub_res = await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={
            "question_key": "chief_complaint",
            "answer": "Headache",
            "source": "patient_reported",
            "confirmation_status": "confirmed",
        },
        headers=auth_headers,
    )
    assert sub_res.status_code == 201
    resp_data = sub_res.json()
    assert resp_data["source"] == "patient_reported"
    assert resp_data["confirmation_status"] == "confirmed"
    assert resp_data["answered_at"] is not None

    # Verify answers review endpoint reflects provenance
    answers_res = await client.get(
        f"/api/interviews/{interview_encounter}/answers",
        headers=auth_headers,
    )
    assert answers_res.status_code == 200
    item = answers_res.json()[0]
    assert item["question_key"] == "chief_complaint"
    assert item["source"] == "patient_reported"
    assert item["answer"] == "Headache"


@pytest.mark.asyncio
async def test_complete_interview_enforces_required_questions(
    client, auth_headers, interview_encounter
):
    """13. Cannot complete interview if required applicable questions are missing."""
    # Attempt to complete without answering required fields
    comp_res = await client.post(
        f"/api/interviews/{interview_encounter}/complete",
        headers=auth_headers,
    )
    assert comp_res.status_code == 400
    assert "required questions not answered" in comp_res.json()["detail"]
