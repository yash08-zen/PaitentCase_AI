"""
tests/test_vision_and_followups.py
-----------------------------------
Tests for:
1. Handwriting OCR vision fallback and local non-diagnostic safety guard.
2. Feature-flagged AI follow-up questions using SOCRATES framework and silent failure fallback.
"""
import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models import Document, DocumentEntity, Encounter, Patient, Question, Response
from app.services.document_processing import _process_worker
from app.services.adaptive_engine import AdaptiveEngine
from app.core.config import settings


@pytest.fixture
async def sample_encounter_with_patient():
    async with AsyncSessionLocal() as db:
        patient = Patient(full_name="Vision Test Patient", age=42, gender="Male")
        db.add(patient)
        await db.commit()
        await db.refresh(patient)

        encounter = Encounter(patient_id=patient.id, consent_given=True, chief_complaint="Chest tightness and fatigue")
        db.add(encounter)
        await db.commit()
        await db.refresh(encounter)
        return encounter


@pytest.mark.asyncio
async def test_handwriting_local_mode_safety_guard(sample_encounter_with_patient, tmp_path):
    """In local/mock mode, low-confidence handwriting gets status 'needs_review' with manual transcription notice."""
    fake_img = tmp_path / "handwritten_rx.jpg"
    fake_img.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

    async with AsyncSessionLocal() as db:
        doc = Document(
            patient_id=sample_encounter_with_patient.patient_id,
            encounter_id=sample_encounter_with_patient.id,
            original_filename="handwritten_rx.jpg",
            stored_path=str(fake_img),
            mime_type="image/jpeg",
            document_type="prescription"
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    with patch("app.services.document_processing.run_ocr_sync") as mock_ocr:
        mock_ocr.return_value = ("scrawl", {}, 0.35, 0.5, "needs_review")
        await _process_worker(doc_id)

    async with AsyncSessionLocal() as db:
        updated_doc = await db.get(Document, doc_id)
        print("UPDATED DOC FIELDS:", updated_doc.extracted_fields)
        assert updated_doc.status == "needs_review"
        assert "handwriting_notice" in updated_doc.extracted_fields
        assert "manual transcription" in updated_doc.extracted_fields["handwriting_notice"]


@pytest.mark.asyncio
async def test_handwriting_vision_fallback_in_hosted_mode(sample_encounter_with_patient, tmp_path):
    """When LLM_PROVIDER is hosted, vision model transcribes text and creates grounded DocumentEntity records."""
    fake_img = tmp_path / "rx_scan.png"
    fake_img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    async with AsyncSessionLocal() as db:
        doc = Document(
            patient_id=sample_encounter_with_patient.patient_id,
            encounter_id=sample_encounter_with_patient.id,
            original_filename="rx_scan.png",
            stored_path=str(fake_img),
            mime_type="image/png",
            document_type="prescription"
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        doc_id = doc.id

    with patch.object(settings, "LLM_PROVIDER", "hosted"):
        with patch("app.services.document_processing.run_ocr_sync") as mock_ocr:
            mock_ocr.return_value = ("", {}, 0.10, 0.4, "needs_review")
            with patch("app.services.llm.manager.llm_service.generate", new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = ({
                    "transcription": "Tab Metformin 500mg BD x 30 days",
                    "medications": [{"name": "Metformin", "dosage": "500mg", "frequency": "BD"}],
                    "labs": []
                }, {})
                await _process_worker(doc_id)
                print("MOCK GEN CALL COUNT:", mock_gen.call_count)

    async with AsyncSessionLocal() as db:
        updated_doc = await db.get(Document, doc_id)
        print("UPDATED DOC FIELDS:", updated_doc.extracted_fields)
        assert updated_doc.status == "needs_review"
        assert updated_doc.extracted_fields.get("extraction_method") == "vision_fallback"
        assert "Metformin" in updated_doc.extracted_text

        entities = (await db.scalars(
            select(DocumentEntity).where(DocumentEntity.document_id == doc_id)
        )).all()
        assert len(entities) >= 1
        assert entities[0].entity_type == "medication"
        assert entities[0].grounded is True
        assert entities[0].provenance == "vision_fallback"


@pytest.mark.asyncio
async def test_feature_flagged_ai_followups_disabled_by_default(sample_encounter_with_patient):
    """When AI_FOLLOWUPS_ENABLED is False, next-question returns deterministic next question."""
    async with AsyncSessionLocal() as db:
        engine = AdaptiveEngine(db)
        await engine.save_response(sample_encounter_with_patient.id, "chief_complaint", "Chest discomfort / tightness")

        with patch.object(settings, "AI_FOLLOWUPS_ENABLED", False):
            res = await engine.get_next_question(sample_encounter_with_patient.id)
            assert res.question is not None
            assert not res.question.key.startswith("ai_followup_")


@pytest.mark.asyncio
async def test_feature_flagged_ai_followups_enabled_and_socrates(sample_encounter_with_patient):
    """When enabled, AI proposes a non-leading SOCRATES follow-up question."""
    async with AsyncSessionLocal() as db:
        engine = AdaptiveEngine(db)
        await engine.save_response(sample_encounter_with_patient.id, "chief_complaint", "Severe chest tightness")

        with patch.object(settings, "AI_FOLLOWUPS_ENABLED", True):
            res = await engine.get_next_question(sample_encounter_with_patient.id)
            assert res.question is not None
            assert res.question.key.startswith("ai_followup_")
            assert res.question.is_required is False
            assert "SOCRATES" in res.question.because


@pytest.mark.asyncio
async def test_ai_followup_failure_silently_falls_back(sample_encounter_with_patient):
    """If LLM fails or times out, next-question gracefully falls back to deterministic question."""
    async with AsyncSessionLocal() as db:
        engine = AdaptiveEngine(db)
        await engine.save_response(sample_encounter_with_patient.id, "chief_complaint", "Severe chest tightness")

        with patch.object(settings, "AI_FOLLOWUPS_ENABLED", True):
            with patch("app.services.llm.manager.llm_service.generate", side_effect=RuntimeError("LLM timeout")):
                res = await engine.get_next_question(sample_encounter_with_patient.id)
                assert res.question is not None
                # Silently falls back to the normal next question
                assert not res.question.key.startswith("ai_followup_")
