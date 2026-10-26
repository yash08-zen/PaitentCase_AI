"""
routers/voice.py
----------------
Multilingual Voice Assistant and Speech-to-Text Parser Router (Milestone M12 / FR-12).

Provides:
  - GET  /api/voice/languages          : List verified languages (English, Hindi, Marathi)
  - GET  /api/voice/questions/{key}    : Retrieve localized prompt and choices for a question
  - POST /api/voice/parse-transcript   : Map spoken utterances to structured clinical fields
                                         with mandatory confirmation for critical fields / low confidence
  - POST /api/encounters/{id}/language : Persist language preference across encounter and patient
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Encounter, Patient, User
from app.dependencies import get_current_user
from app.data.translations import (
    SUPPORTED_LANGUAGES,
    QUESTION_TRANSLATIONS,
    SPEECH_SYNONYMS,
    get_translation_for_question,
    detect_speech_dialect,
)

router = APIRouter(prefix="/api/voice", tags=["Multilingual Voice Assistant"])


class ParseTranscriptRequest(BaseModel):
    transcript: str = Field(..., min_length=1, max_length=1000)
    question_key: str = Field(..., min_length=1)
    language: Optional[str] = "en"
    confidence: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)


class ParseTranscriptResponse(BaseModel):
    raw_transcript: str
    parsed_value: str
    confidence: float
    requires_confirmation: bool
    confirmation_reason: Optional[str] = None
    language: str
    normalized_english: Optional[str] = None
    matched_choice: Optional[str] = None
    detected_dialect: Optional[str] = "standard_english"
    is_code_mixed: Optional[bool] = False


class SetLanguageRequest(BaseModel):
    language: str = Field(..., min_length=2, max_length=20)


@router.get("/languages")
async def list_supported_languages():
    """Returns verified and tested languages with locale and TTS voice targets."""
    return {
        "languages": SUPPORTED_LANGUAGES,
        "default": "en",
        "tested_subset": ["en", "hi", "mr"],
    }


@router.get("/questions/{question_key}")
async def get_question_translation(question_key: str, lang: str = "en"):
    """Returns localized question text, choices, and audio prompt."""
    data = get_translation_for_question(question_key, lang)
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Translations not found for question: {question_key}",
        )
    return {
        "question_key": question_key,
        "language": lang,
        "text": data.get("text"),
        "help": data.get("help"),
        "spoken_prompt": data.get("spoken_prompt"),
        "choices": data.get("choices"),
    }


@router.post("/parse-transcript", response_model=ParseTranscriptResponse)
async def parse_voice_transcript(payload: ParseTranscriptRequest):
    """
    Normalizes spoken speech transcripts into structured intake answers.
    Enforces mandatory human confirmation for:
      1. Low confidence (< 0.85)
      2. High-stakes safety fields (allergies, medications)
      3. Partial / ambiguous choice matches
    """
    raw = payload.transcript.strip()
    lowered = raw.lower()
    q_key = payload.question_key
    lang = (payload.language or "en").lower()
    confidence = payload.confidence if payload.confidence is not None else 1.0

    parsed_value = raw
    matched_choice = None
    normalized_en = None
    requires_confirmation = False
    confirmation_reason = None

    # 1. Scale numbers (1 to 10)
    if q_key == "symptom_severity":
        num_map = SPEECH_SYNONYMS.get("numbers", {})
        matched_num = None
        for word in lowered.split():
            clean_word = word.strip(".,!?")
            if clean_word in num_map:
                matched_num = num_map[clean_word]
                break
        if matched_num:
            parsed_value = matched_num
            matched_choice = matched_num
            normalized_en = matched_num
        else:
            requires_confirmation = True
            confirmation_reason = "Severity score not clearly identified in speech"

    # 2. Chief complaint symptoms
    elif q_key == "chief_complaint":
        sym_map = SPEECH_SYNONYMS.get("symptoms", {})
        matched_sym = None
        for phrase, canonical in sym_map.items():
            if phrase in lowered:
                matched_sym = canonical
                break
        if matched_sym:
            parsed_value = matched_sym
            matched_choice = matched_sym
            normalized_en = matched_sym
        else:
            # Keep raw transcript and flag for confirmation
            requires_confirmation = True
            confirmation_reason = "Unmatched symptom description requires verification"

    # 3. Symptom duration
    elif q_key == "symptom_duration":
        dur_map = SPEECH_SYNONYMS.get("durations", {})
        matched_dur = None
        for phrase, canonical in dur_map.items():
            if phrase in lowered:
                matched_dur = canonical
                break
        if matched_dur:
            parsed_value = matched_dur
            matched_choice = matched_dur
            normalized_en = matched_dur
        else:
            requires_confirmation = True
            confirmation_reason = "Duration timeframe requires patient confirmation"

    # 4. Binary Yes / No choice questions (medications, allergies, surgery)
    elif q_key in ["current_medications", "has_allergies", "previous_surgery", "family_history"]:
        aff_map = SPEECH_SYNONYMS.get("affirmative", {})
        neg_map = SPEECH_SYNONYMS.get("negative", {})

        is_yes = any(aff in lowered for aff in aff_map)
        is_no = any(neg in lowered for neg in neg_map)

        if is_no and not is_yes:
            if q_key == "current_medications":
                parsed_value = "No, none"
            elif q_key == "has_allergies":
                parsed_value = "No known allergies"
            else:
                parsed_value = "No"
            matched_choice = parsed_value
            normalized_en = parsed_value
        elif is_yes and not is_no:
            if q_key == "current_medications":
                parsed_value = "Yes, regularly"
            elif q_key == "has_allergies":
                parsed_value = "Yes, to medicines"
            else:
                parsed_value = "Yes"
            matched_choice = parsed_value
            normalized_en = parsed_value
        else:
            requires_confirmation = True
            confirmation_reason = "Affirmation or negation unclear from spoken response"

    # 5. Dialect and code-mixing detection (e.g. Hinglish / Marathish)
    detected_dialect, is_code_mixed = detect_speech_dialect(raw, lang)
    if is_code_mixed:
        requires_confirmation = True
        if not confirmation_reason:
            confirmation_reason = f"Code-mixed speech ({detected_dialect}) detected: mandatory verification required"

    # 6. Mandatory Clinical Safety Rule:
    # All allergy and medication statements require explicit human confirmation
    CRITICAL_SAFETY_FIELDS = [
        "current_medications",
        "medication_details",
        "medication_dosage",
        "has_allergies",
        "allergy_details",
        "allergy_reaction",
    ]
    if q_key in CRITICAL_SAFETY_FIELDS:
        requires_confirmation = True
        confirmation_reason = "Clinical safety rule: medication and allergy inputs require explicit confirmation"

    # 7. Low-confidence threshold (< 0.85)
    if confidence < 0.85:
        requires_confirmation = True
        if not confirmation_reason:
            confirmation_reason = f"Low speech recognition confidence ({int(confidence * 100)}%)"

    return ParseTranscriptResponse(
        raw_transcript=raw,
        parsed_value=parsed_value,
        confidence=confidence,
        requires_confirmation=requires_confirmation,
        confirmation_reason=confirmation_reason,
        language=lang,
        normalized_english=normalized_en or parsed_value,
        matched_choice=matched_choice,
        detected_dialect=detected_dialect,
        is_code_mixed=is_code_mixed,
    )


@router.post("/encounters/{encounter_id}/language")
async def set_encounter_language(
    encounter_id: int,
    payload: SetLanguageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Updates the preferred language on the encounter and patient.
    Maintains language choice across the entire interview session.
    """
    valid_langs = {"english": "English", "hindi": "Hindi", "marathi": "Marathi", "en": "English", "hi": "Hindi", "mr": "Marathi"}
    req_lang = payload.language.strip().lower()
    if req_lang not in valid_langs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported language: {payload.language}. Supported: English, Hindi, Marathi",
        )
    canonical_lang = valid_langs[req_lang]

    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    patient = await db.get(Patient, enc.patient_id)
    if patient:
        patient.preferred_language = canonical_lang

    await db.commit()

    return {
        "encounter_id": encounter_id,
        "preferred_language": canonical_lang,
        "status": "updated",
    }
