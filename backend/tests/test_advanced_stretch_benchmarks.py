"""
tests/test_advanced_stretch_benchmarks.py
-----------------------------------------
Automated test suite for Milestone M13 (Advanced Stretch / P2):
  - Quantitative benchmark metrics for printed vs handwritten prescription OCR
  - Code-mixed speech understanding (Hinglish, Marathish) and mandatory confirmation rule
  - Verification of system benchmark summary API endpoint
  - Verification of clinical safety gates (non-diagnostic, human-in-the-loop)
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_benchmarks_summary_endpoint(client: AsyncClient):
    """DoD 1: System exposes empirical evaluation benchmark metrics for OCR and speech."""
    res = await client.get("/api/system/benchmarks/summary")
    assert res.status_code == 200
    data = res.json()

    assert data["benchmark_version"] == "1.0"
    assert "ocr_benchmarks" in data
    assert "speech_benchmarks" in data
    assert "clinical_safeguards" in data

    ocr = data["ocr_benchmarks"]
    assert "printed_hospital_prescriptions" in ocr
    assert "handwritten_doctor_prescriptions" in ocr
    assert ocr["printed_hospital_prescriptions"]["clinical_status"] == "automated_extraction_supported"
    assert "requires_clinician_manual_entry" in ocr["handwritten_doctor_prescriptions"]["clinical_status"]

    safeguards = data["clinical_safeguards"]
    assert safeguards["handwritten_auto_finalization"] is False
    assert safeguards["low_confidence_confirmation_mandated"] is True
    assert safeguards["code_mixed_speech_confirmation_mandated"] is True
    assert safeguards["allergy_medication_non_silent_rule"] is True


@pytest.mark.asyncio
async def test_code_mixed_hinglish_speech_parsing_and_confirmation(client: AsyncClient):
    """DoD 2: Hinglish code-mixed speech is correctly parsed and strictly flags confirmation."""
    payload = {
        "transcript": "Mujhe 2 days se severe headache aur fever hai",
        "question_key": "chief_complaint",
        "language": "hi",
        "confidence": 0.95,
    }
    res = await client.post("/api/voice/parse-transcript", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_code_mixed"] is True
    assert data["detected_dialect"] == "hinglish"
    assert data["requires_confirmation"] is True
    assert "Code-mixed speech" in data["confirmation_reason"]
    assert data["parsed_value"].lower() == "headache"
 

@pytest.mark.asyncio
async def test_code_mixed_marathish_speech_parsing_and_confirmation(client: AsyncClient):
    """DoD 3: Marathish code-mixed speech is correctly parsed and strictly flags confirmation."""
    payload = {
        "transcript": "Mala 3 divasapasun chest pain aani cough aahe",
        "question_key": "chief_complaint",
        "language": "mr",
        "confidence": 0.92,
    }
    res = await client.post("/api/voice/parse-transcript", json=payload)
    assert res.status_code == 200
    data = res.json()

    assert data["is_code_mixed"] is True
    assert data["detected_dialect"] == "marathish"
    assert data["requires_confirmation"] is True
    assert "Code-mixed speech" in data["confirmation_reason"]
    assert data["parsed_value"].lower() in ["chest pain", "chest discomfort"]


@pytest.mark.asyncio
async def test_speech_dialects_benchmark_metrics(client: AsyncClient):
    """DoD 4: Speech benchmark confirms tested accuracy and high confirmation rates for mixed dialects."""
    res = await client.get("/api/system/benchmarks/summary")
    assert res.status_code == 200
    data = res.json()

    dialects = data["speech_benchmarks"]["dialects"]
    assert "hinglish" in dialects
    assert "marathish" in dialects
    assert "standard_english" in dialects
    assert "standard_hindi" in dialects
    assert "standard_marathi" in dialects

    # Code-mixed dialects must enforce high confirmation rate (>= 80%)
    assert dialects["hinglish"]["confirmation_rate"] >= 0.80
    assert dialects["marathish"]["confirmation_rate"] >= 0.80


@pytest.mark.asyncio
async def test_handwritten_vs_printed_ocr_safeguards():
    """DoD 5: Empirical evaluation confirms printed recall is higher than cursive recall."""
    from app.services.document_processing import run_ocr_sync
    import os

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    printed_img = os.path.join(backend_dir, "tests", "eval_data", "handwritten", "rx_eval_01_printed_reference.png")
    scrawl_img = os.path.join(backend_dir, "tests", "eval_data", "handwritten", "rx_eval_05_cursive_scrawl.png")

    assert os.path.exists(printed_img), f"Printed sample image missing at {printed_img}"
    assert os.path.exists(scrawl_img), f"Scrawl sample image missing at {scrawl_img}"

    # Printed OCR
    p_text, p_meta, p_conf, _, p_status = run_ocr_sync(printed_img, "image/png")
    assert p_status == "completed"
    assert p_conf >= 0.80
    assert len(p_meta.get("medications", [])) >= 1

    # Degraded Cursive Scrawl OCR
    s_text, s_meta, s_conf, _, s_status = run_ocr_sync(scrawl_img, "image/png")
    # Must be classified as needing review or have low confidence
    assert s_status == "needs_review" or (s_conf is not None and s_conf < 0.70)
