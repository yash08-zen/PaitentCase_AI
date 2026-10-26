"""
tests/test_case_summary_and_completeness.py
-------------------------------------------
Milestone M5 tests:
- Structured history and summary generation with provenance
- Missing-information detection (blanks -> "Not provided / unknown", never "No")
- Allergy question behavior (unanswered -> missing list + "Not provided / unknown")
- Completing a field removes it from the missing list
- Summary updates dynamically when answers change
- Completeness indicator formula reproducibility & absence of clinical risk wording
- Record-level authorization for summary and missing endpoints
"""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_summary_content_updates_when_answers_change(client: AsyncClient, auth_headers: dict):
    """DoD 1: Summary content changes when answers change (edit answer -> summary updates)."""
    # 1. Create patient and encounter
    p_res = await client.post("/api/patients", json={"full_name": "Dynamic Patient", "age": 42, "gender": "Male"}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # 2. Initial answer: Chief complaint = "Initial mild cough"
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Initial mild cough"},
        headers=auth_headers,
    )

    s1 = await client.get(f"/api/encounters/{enc_id}/summary", headers=auth_headers)
    assert s1.status_code == 200
    data1 = s1.json()
    assert "Initial mild cough" in data1["summary_text"]
    cc_field1 = next(f for f in data1["structured_findings"] if f["key"] == "chief_complaint")
    assert cc_field1["value"] == "Initial mild cough"
    assert cc_field1["source"] == "patient_reported"

    # 3. Update answer: Chief complaint = "Severe acute migraine"
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Severe acute migraine"},
        headers=auth_headers,
    )

    # 4. Fetch summary again and verify immediate update
    s2 = await client.get(f"/api/encounters/{enc_id}/summary", headers=auth_headers)
    assert s2.status_code == 200
    data2 = s2.json()
    assert "Severe acute migraine" in data2["summary_text"]
    assert "Initial mild cough" not in data2["summary_text"]
    cc_field2 = next(f for f in data2["structured_findings"] if f["key"] == "chief_complaint")
    assert cc_field2["value"] == "Severe acute migraine"


@pytest.mark.asyncio
async def test_unanswered_allergy_renders_unknown_and_in_missing_list(client: AsyncClient, auth_headers: dict):
    """
    DoD 2: An unanswered allergy question renders 'Not provided / unknown'
    and appears in the missing list (explicit test). Never assume 'No allergies'.
    """
    p_res = await client.post("/api/patients", json={"full_name": "Allergy Test Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Check missing information before allergy is answered
    m_res = await client.get(f"/api/encounters/{enc_id}/missing", headers=auth_headers)
    assert m_res.status_code == 200
    m_data = m_res.json()
    allergy_missing = next((f for f in m_data["missing_fields"] if f["field"] == "has_allergies"), None)
    assert allergy_missing is not None
    assert allergy_missing["is_critical"] is True
    assert allergy_missing["status"] == "Not provided / unknown"

    # Check summary representation
    s_res = await client.get(f"/api/encounters/{enc_id}/summary", headers=auth_headers)
    assert s_res.status_code == 200
    s_data = s_res.json()

    # Must NOT say "no allergies" or "no known allergies"
    assert "No known allergies reported" not in s_data["summary_text"]
    assert "Known allergies : Not provided / unknown" in s_data["summary_text"]

    allergy_finding = next(f for f in s_data["structured_findings"] if f["key"] == "has_allergies")
    assert allergy_finding["value"] == "Not provided / unknown"
    assert allergy_finding["source"] == "missing_unknown"
    assert allergy_finding["is_missing"] is True


@pytest.mark.asyncio
async def test_completing_field_removes_it_from_missing_list(client: AsyncClient, auth_headers: dict):
    """DoD 3: Completing the field removes it from the missing list."""
    p_res = await client.post("/api/patients", json={"full_name": "Removable Missing Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Initial check: 6 required fields missing
    m1 = await client.get(f"/api/encounters/{enc_id}/missing", headers=auth_headers)
    assert m1.json()["total_missing"] == 6

    # Answer has_allergies = "No"
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "has_allergies", "answer": "No"},
        headers=auth_headers,
    )

    # Check missing fields again: total_missing should decrease to 5, has_allergies removed
    m2 = await client.get(f"/api/encounters/{enc_id}/missing", headers=auth_headers)
    assert m2.json()["total_missing"] == 5
    remaining_keys = [f["field"] for f in m2.json()["missing_fields"]]
    assert "has_allergies" not in remaining_keys

    # Also answer current_medications = "Yes"
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "current_medications", "answer": "Yes"},
        headers=auth_headers,
    )

    m3 = await client.get(f"/api/encounters/{enc_id}/missing", headers=auth_headers)
    assert m3.json()["total_missing"] == 4
    remaining_keys2 = [f["field"] for f in m3.json()["missing_fields"]]
    assert "current_medications" not in remaining_keys2


@pytest.mark.asyncio
async def test_each_summary_field_shows_valid_source_label(client: AsyncClient, auth_headers: dict):
    """DoD 4: Each summary field shows its source label with valid provenance."""
    p_res = await client.post("/api/patients", json={"full_name": "Provenance Patient", "age": 30, "gender": "Other"}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Severe knee pain"},
        headers=auth_headers,
    )

    s_res = await client.get(f"/api/encounters/{enc_id}/summary", headers=auth_headers)
    assert s_res.status_code == 200
    data = s_res.json()

    valid_sources = {
        "patient_reported",
        "document_extracted_unverified",
        "doctor_verified",
        "missing_unknown",
    }

    # Verify structured sections
    assert "sections" in data and len(data["sections"]) >= 6
    for sec in data["sections"]:
        assert sec["id"]
        assert sec["title"]
        for f in sec["fields"]:
            assert f["source"] in valid_sources, f"Invalid source {f['source']} in field {f['key']}"
            assert f["source_label"] is not None
            assert len(f["source_label"]) > 0

    # Verify structured findings
    assert "structured_findings" in data and len(data["structured_findings"]) >= 6
    for f in data["structured_findings"]:
        assert f["source"] in valid_sources
        assert f["source_label"] is not None


@pytest.mark.asyncio
async def test_completeness_indicator_reproducible_and_no_risk_wording(client: AsyncClient, auth_headers: dict):
    """
    DoD 5: Completeness indicator is reproducible: same inputs -> same value (unit tests);
    no medical-risk wording anywhere in outputs.
    """
    p_res = await client.post("/api/patients", json={"full_name": "Completeness Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Check readiness score twice with same input
    r1 = await client.get(f"/api/encounters/{enc_id}/readiness", headers=auth_headers)
    r2 = await client.get(f"/api/encounters/{enc_id}/readiness", headers=auth_headers)

    d1 = r1.json()
    d2 = r2.json()

    # Exact equality (deterministic)
    assert d1["score"] == d2["score"]
    assert d1["label"] == d2["label"]
    assert d1["factors"] == d2["factors"]

    # Verify no clinical risk / disease severity wording
    prohibited_words = ["urgent", "emergency", "high risk", "low risk", "disease probability", "mortality", "triage priority", "severity score"]
    combined_text = (d1["label"] + " " + d1["disclaimer"] + " " + str(d1["factors"])).lower()
    for word in prohibited_words:
        assert word not in combined_text, f"Prohibited clinical risk word found: '{word}'"

    # Answer all 6 required fields
    required_answers = {
        "chief_complaint": "Back pain",
        "symptom_duration": "1 to 3 days",
        "symptom_severity": "6",
        "has_chronic_conditions": "No",
        "current_medications": "No",
        "has_allergies": "No",
    }
    for k, v in required_answers.items():
        await client.post(
            f"/api/interviews/{enc_id}/responses",
            json={"question_key": k, "answer": v},
            headers=auth_headers,
        )

    r3 = await client.get(f"/api/encounters/{enc_id}/readiness", headers=auth_headers)
    d3 = r3.json()
    assert d3["score"] >= 0.8
    assert d3["label"] == "Ready for Review"
    assert d3["factors"]["required_fields_score"] == 1.0


@pytest.mark.asyncio
async def test_patient_record_level_access_for_summary_and_missing(client: AsyncClient, auth_headers: dict):
    """Verify patients can only access summary and missing endpoints for their own encounters."""
    # Create user for patient 1
    u_res = await client.post(
        "/api/auth/register",
        json={"username": "patient_one", "email": "p1@test.com", "password": "Password@123", "role": "patient"},
        headers=auth_headers,
    )
    p1_user_id = u_res.json()["id"]

    # Create patient 1 record linked to patient_one user
    p1 = await client.post(
        "/api/patients",
        json={"full_name": "Patient One", "user_id": p1_user_id},
        headers=auth_headers,
    )
    p1_id = p1.json()["id"]

    # Create encounter for patient 1
    e1 = await client.post(
        "/api/encounters",
        json={"patient_id": p1_id, "consent_given": True},
        headers=auth_headers,
    )
    enc1_id = e1.json()["id"]

    # Login as patient_one
    p1_login = await client.post("/api/auth/login", json={"username": "patient_one", "password": "Password@123"})
    p1_headers = {"Authorization": f"Bearer {p1_login.json()['access_token']}"}

    # Patient 1 can access own summary and missing
    r_sum = await client.get(f"/api/encounters/{enc1_id}/summary", headers=p1_headers)
    assert r_sum.status_code == 200

    r_mis = await client.get(f"/api/encounters/{enc1_id}/missing", headers=p1_headers)
    assert r_mis.status_code == 200

    # Create another encounter for a different patient
    p2 = await client.post("/api/patients", json={"full_name": "Patient Two"}, headers=auth_headers)
    e2 = await client.post("/api/encounters", json={"patient_id": p2.json()["id"], "consent_given": True}, headers=auth_headers)
    enc2_id = e2.json()["id"]

    # Patient 1 cannot access encounter 2 (returns 403)
    r_sum_forbidden = await client.get(f"/api/encounters/{enc2_id}/summary", headers=p1_headers)
    assert r_sum_forbidden.status_code == 403

    r_mis_forbidden = await client.get(f"/api/encounters/{enc2_id}/missing", headers=p1_headers)
    assert r_mis_forbidden.status_code == 403
