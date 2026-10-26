"""
tests/test_multilingual_voice.py
--------------------------------
Comprehensive unit and integration tests for Milestone M12:
Multilingual Voice Conversation (FR-12).

Verifies:
  1. Supported language list returns tested languages (English, Hindi, Marathi).
  2. Localized question texts, help, and audio prompts retrieve accurately across en, hi, mr.
  3. Speech transcript parsing accurately maps English, Hindi, and Marathi utterances to structured fields.
  4. Mandatory confirmation enforcement for critical clinical safety fields (allergies, medications)
     and low-confidence (< 0.85) transcripts.
  5. Language choice persistence across encounter and patient entities.
  6. Rejection of unsupported languages with HTTP 400.
"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Patient, Encounter


@pytest.mark.asyncio
async def test_voice_languages_list(client: AsyncClient):
    """Verify supported language endpoint exposes English, Hindi, and Marathi."""
    res = await client.get("/api/voice/languages")
    assert res.status_code == 200
    data = res.json()
    codes = [l["code"] for l in data["languages"]]
    assert "en" in codes
    assert "hi" in codes
    assert "mr" in codes
    assert set(data["tested_subset"]) == {"en", "hi", "mr"}


@pytest.mark.asyncio
async def test_question_translation_retrieval(client: AsyncClient):
    """Verify localized questions, options, and spoken prompts for English, Hindi, and Marathi."""
    # English
    en_res = await client.get("/api/voice/questions/chief_complaint?lang=en")
    assert en_res.status_code == 200
    assert "troubling you the most" in en_res.json()["text"]
    assert "Headache" in en_res.json()["choices"]

    # Hindi
    hi_res = await client.get("/api/voice/questions/chief_complaint?lang=hi")
    assert hi_res.status_code == 200
    assert "तकलीफ" in hi_res.json()["text"]
    assert any("सिरदर्द" in c for c in hi_res.json()["choices"])

    # Marathi
    mr_res = await client.get("/api/voice/questions/chief_complaint?lang=mr")
    assert mr_res.status_code == 200
    assert "त्रास" in mr_res.json()["text"]
    assert any("डोकेदुखी" in c for c in mr_res.json()["choices"])


@pytest.mark.asyncio
async def test_voice_transcript_parsing_multilingual(client: AsyncClient):
    """Verify speech transcript mapping for English, Hindi, and Marathi utterances."""
    # 1. English symptom
    en_parse = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "I have a severe headache", "question_key": "chief_complaint", "language": "en", "confidence": 0.95},
    )
    assert en_parse.status_code == 200
    assert en_parse.json()["parsed_value"] == "Headache"

    # 2. Hindi symptom ("सिर दर्द")
    hi_parse = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "मुझे बहुत तेज सिर दर्द हो रहा है", "question_key": "chief_complaint", "language": "hi", "confidence": 0.92},
    )
    assert hi_parse.status_code == 200
    assert hi_parse.json()["parsed_value"] == "Headache"

    # 3. Marathi symptom ("डोकेदुखी")
    mr_parse = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "मला खूप डोकेदुखी आहे", "question_key": "chief_complaint", "language": "mr", "confidence": 0.90},
    )
    assert mr_parse.status_code == 200
    assert mr_parse.json()["parsed_value"] == "Headache"

    # 4. Scale numbers (Hindi "पांच", Marathi "आठ")
    scale_hi = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "लगभग पांच", "question_key": "symptom_severity", "language": "hi", "confidence": 0.95},
    )
    assert scale_hi.json()["parsed_value"] == "5"

    scale_mr = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "आठ", "question_key": "symptom_severity", "language": "mr", "confidence": 0.95},
    )
    assert scale_mr.json()["parsed_value"] == "8"


@pytest.mark.asyncio
async def test_mandatory_confirmation_for_critical_fields(client: AsyncClient):
    """
    Non-negotiable Clinical Rule:
    Transcripts for medications and allergies must ALWAYS set requires_confirmation=True,
    and transcripts with confidence < 0.85 must require confirmation.
    """
    # 1. Medication question with 1.0 confidence -> MUST still require confirmation
    med_res = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "No I do not take any pills", "question_key": "current_medications", "language": "en", "confidence": 1.0},
    )
    assert med_res.status_code == 200
    assert med_res.json()["requires_confirmation"] is True
    assert "medication and allergy" in med_res.json()["confirmation_reason"]

    # 2. Allergy question with 1.0 confidence -> MUST still require confirmation
    allg_res = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "No known allergies", "question_key": "has_allergies", "language": "en", "confidence": 1.0},
    )
    assert allg_res.status_code == 200
    assert allg_res.json()["requires_confirmation"] is True

    # 3. Low confidence (< 0.85) on regular symptom -> MUST require confirmation
    low_res = await client.post(
        "/api/voice/parse-transcript",
        json={"transcript": "headache", "question_key": "chief_complaint", "language": "en", "confidence": 0.72},
    )
    assert low_res.status_code == 200
    assert low_res.json()["requires_confirmation"] is True
    assert "Low speech recognition confidence" in low_res.json()["confirmation_reason"]


@pytest.mark.asyncio
async def test_encounter_language_preference_persistence(client: AsyncClient):
    """
    Verify language selection is stored on patient and maintained across the interview.
    """
    # Login as staff
    staff_login = await client.post("/api/auth/login", json={"username": "staff", "password": "Staff@1234"})
    staff_token = staff_login.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # Register patient
    p_res = await client.post(
        "/api/patients",
        json={
            "full_name": "Multilingual Test Patient",
            "date_of_birth": "1992-04-10",
            "gender": "male",
            "consent_given": True,
            "preferred_language": "English",
        },
        headers=staff_headers,
    )
    assert p_res.status_code == 201
    patient_id = p_res.json()["id"]

    # Create encounter
    e_res = await client.post(
        "/api/encounters",
        json={"patient_id": patient_id, "consent_given": True},
        headers=staff_headers,
    )
    assert e_res.status_code == 201
    encounter_id = e_res.json()["id"]

    # Switch language to Hindi
    lang_hi = await client.post(
        f"/api/voice/encounters/{encounter_id}/language",
        json={"language": "Hindi"},
        headers=staff_headers,
    )
    assert lang_hi.status_code == 200
    assert lang_hi.json()["preferred_language"] == "Hindi"

    # Verify directly in DB
    async with AsyncSessionLocal() as session:
        db_p = await session.get(Patient, patient_id)
        assert db_p.preferred_language == "Hindi"

    # Switch language to Marathi
    lang_mr = await client.post(
        f"/api/voice/encounters/{encounter_id}/language",
        json={"language": "Marathi"},
        headers=staff_headers,
    )
    assert lang_mr.status_code == 200
    assert lang_mr.json()["preferred_language"] == "Marathi"

    async with AsyncSessionLocal() as session:
        db_p = await session.get(Patient, patient_id)
        assert db_p.preferred_language == "Marathi"

    # Attempt invalid language -> 400
    invalid_res = await client.post(
        f"/api/voice/encounters/{encounter_id}/language",
        json={"language": "Klingon"},
        headers=staff_headers,
    )
    assert invalid_res.status_code == 400
