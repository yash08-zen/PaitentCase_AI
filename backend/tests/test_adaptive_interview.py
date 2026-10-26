"""
tests/test_adaptive_interview.py
---------------------------------
Comprehensive unit and integration test suite for Milestone M4:
Guided Interview and Adaptive Rule Engine (FR-02, FR-03).

Covers:
  1. Chief complaint as initial question
  2. Branching: Pain -> location & associated symptoms
  3. Branching: Chest discomfort -> worse with activity
  4. Branching: Headache -> symptom frequency
  5. Branching: Fever -> skips redundant fever question (skip_if)
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


@pytest.mark.asyncio
async def test_first_question_is_chief_complaint(client, auth_headers, interview_encounter):
    """1. First question presented must always be chief_complaint with order=1."""
    res = await client.get(
        f"/api/interviews/{interview_encounter}/next-question",
        headers=auth_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_complete"] is False
    assert data["question"] is not None
    assert data["question"]["key"] == "chief_complaint"
    assert data["question"]["answer_type"] == "choice"
    assert "Abdominal pain" in data["question"]["choices"]
    assert data["can_go_back"] is False


@pytest.mark.asyncio
async def test_pain_branching_triggers_location_and_associated_symptoms(
    client, auth_headers, interview_encounter
):
    """2. Answering 'Abdominal pain' triggers pain_location and associated_symptoms follow-ups."""
    # Answer chief complaint = Abdominal pain
    r1 = await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "chief_complaint", "answer": "Abdominal pain"},
        headers=auth_headers,
    )
    assert r1.status_code == 201

    # Answer duration = 1 to 3 days
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "symptom_duration", "answer": "1 to 3 days"},
        headers=auth_headers,
    )
    # Answer severity = 6
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "symptom_severity", "answer": "6"},
        headers=auth_headers,
    )

    # Next question should be pain_location (show_if satisfied)
    next_q = await client.get(
        f"/api/interviews/{interview_encounter}/next-question",
        headers=auth_headers,
    )
    assert next_q.status_code == 200
    q_data = next_q.json()["question"]
    assert q_data["key"] == "pain_location"
    assert next_q.json()["adaptive_note"] is not None
    assert "Upper abdomen" in q_data["choices"]


@pytest.mark.asyncio
async def test_chest_discomfort_triggers_worse_with_activity(
    client, auth_headers, interview_encounter
):
    """3. Answering 'Chest discomfort' triggers worse_with_activity question."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "chief_complaint", "answer": "Chest discomfort"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "symptom_duration", "answer": "Less than a day"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "symptom_severity", "answer": "8"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "pain_location", "answer": "Left chest"},
        headers=auth_headers,
    )

    # worse_with_activity should be next
    res = await client.get(
        f"/api/interviews/{interview_encounter}/next-question",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["question"]["key"] == "worse_with_activity"


@pytest.mark.asyncio
async def test_headache_triggers_frequency(
    client, auth_headers, interview_encounter
):
    """4. Answering 'Headache' triggers symptom_frequency question."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "chief_complaint", "answer": "Headache"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "symptom_duration", "answer": "4 to 7 days"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "symptom_severity", "answer": "5"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "pain_location", "answer": "Forehead / temples"},
        headers=auth_headers,
    )

    # symptom_frequency should be next (not worse_with_activity)
    res = await client.get(
        f"/api/interviews/{interview_encounter}/next-question",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.json()["question"]["key"] == "symptom_frequency"


@pytest.mark.asyncio
async def test_fever_complaint_skips_has_fever_question(
    client, auth_headers, interview_encounter
):
    """5. When chief complaint is 'Fever', has_fever question is skipped (skip_if)."""
    await client.post(
        f"/api/interviews/{interview_encounter}/responses",
        json={"question_key": "chief_complaint", "answer": "Fever"},
        headers=auth_headers,
    )

    progress = await client.get(
        f"/api/interviews/{interview_encounter}/progress",
        headers=auth_headers,
    )
    assert progress.status_code == 200
    data = progress.json()

    # has_fever should be in skipped_questions
    skipped_keys = [s["key"] for s in data["skipped_questions"]]
    assert "has_fever" in skipped_keys


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
    assert data["question"]["key"] == "symptom_severity"
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
