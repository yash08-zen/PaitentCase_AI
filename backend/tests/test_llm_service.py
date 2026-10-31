"""
tests/test_llm_service.py
-------------------------
LLM service layer: scrubber, mock provider contract, manager metadata and
de-identification, provider-unavailable handling.
"""
import pytest
from unittest.mock import patch

from app.core.config import settings
from app.services.llm.interface import LLMUnavailableError
from app.services.llm.manager import CURRENT_PROMPT_VERSION, LLMServiceManager
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.prompts import SCHEMAS, SYSTEM_PROMPTS, wrap_case_data
from app.services.llm.scrubber import TextScrubber


def test_scrubber_deidentification_and_reattachment():
    """Verify de-identification of sensitive PII/PHI and lossless local re-attachment."""
    scrubber = TextScrubber(known_patient_name="Ramesh Kumar Gupta", known_identifiers=["UHID-98234"])

    clinical_text = (
        "Patient Name: Ramesh Kumar Gupta, Age 54, Male.\n"
        "UHID: UHID-98234, Aadhaar: 2345 6789 0123, ABHA: 12-3456-7890-1234.\n"
        "Contact: +91 9876543210, Email: ramesh.gupta@example.in, Pin: 400001.\n"
        "Chief complaint: Burning sensation in chest. Prescribed Metformin 500mg."
    )

    scrubbed, token_map = scrubber.scrub(clinical_text)

    assert "Ramesh Kumar Gupta" not in scrubbed
    assert "2345 6789 0123" not in scrubbed
    assert "12-3456-7890-1234" not in scrubbed
    assert "9876543210" not in scrubbed
    assert "ramesh.gupta@example.in" not in scrubbed
    assert "UHID-98234" not in scrubbed
    assert "400001" not in scrubbed
    assert "Metformin 500mg" in scrubbed  # clinical content survives

    assert "[PATIENT_NAME_1]" in scrubbed
    assert "[AADHAAR_" in scrubbed
    assert "[PHONE_" in scrubbed
    assert "[EMAIL_" in scrubbed

    assert TextScrubber.reattach(scrubbed, token_map) == clinical_text


async def _gen(provider, task, payload):
    return await provider.generate(task=task, system_prompt=SYSTEM_PROMPTS[task],
                                   user_content=wrap_case_data(payload), json_schema=SCHEMAS[task])


@pytest.mark.asyncio
async def test_mock_provider_tasks():
    """Mock provider returns schema-shaped output derived only from the case payload."""
    provider = MockLLMProvider()
    lab_text = "Pathology lab report 2026-05-15. Serum Creatinine 1.4 mg/dL (ref 0.7-1.3)."

    cls_res = await _gen(provider, "document_classification", {"document_text": lab_text})
    assert cls_res["document_type"] == "lab_report"
    assert cls_res["document_date"] == "2026-05-15"

    ext = await _gen(provider, "document_extraction", {
        "document_text": "Diagnosis: Type 2 Diabetes. Tab Metformin 500mg twice daily. Creatinine 1.4 mg/dL (0.7-1.3)."})
    assert [d["name"] for d in ext["diagnoses"]] == ["Type 2 Diabetes"]
    assert any(m["name"] == "Metformin" for m in ext["medications"])
    assert ext["lab_rows"][0]["value"] == "1.4" and ext["lab_rows"][0]["ref_high"] == "1.3"

    catalogue = [{"ref": "interview:chief_complaint", "text": "Chest pain on exertion"}]
    con = await _gen(provider, "disease_considerations", {"evidence_catalogue": catalogue})
    first = con["considerations"][0]
    assert first["likelihood"] in ("more likely", "possible", "less likely")
    assert first["supporting_findings"][0]["evidence_ref"] == "interview:chief_complaint"
    assert first["supporting_findings"][0]["quote"] == "Chest pain"

    empty = await _gen(provider, "disease_considerations", {"evidence_catalogue": []})
    assert empty["considerations"] == []

    tx = await _gen(provider, "treatment_reference", {"passages": [
        {"id": 7, "topic": "T2DM", "text": "Metformin is first line. Metformin 500 mg once daily with meals."}]})
    assert tx["summaries"][0]["passage_id"] == 7
    assert tx["summaries"][0]["dose_quotation"] == "Metformin 500 mg once daily with meals"
    assert (await _gen(provider, "treatment_reference", {"passages": []}))["nothing_relevant"] is True

    trend = await _gen(provider, "trend_interpretation", {
        "test": "creatinine", "previous_value": 1.0, "current_value": 1.8, "unit": "mg/dL",
        "direction": "rising", "time_span_days": 90, "matched_rule_id": "CREATININE_PERCENT_RISE"})
    assert trend["interpretation"].startswith("Creatinine rose from 1.0 to 1.8 mg/dL over 90 days")

    summ = await _gen(provider, "case_summary", {"evidence_catalogue": catalogue})
    assert summ["sections"][0] == {"section": "chief_complaint", "text": "Chest pain on exertion",
                                   "evidence_refs": ["interview:chief_complaint"]}


@pytest.mark.asyncio
async def test_llm_service_manager_status():
    manager = LLMServiceManager()
    status = await manager.get_status()
    assert status["active_mode"] == "mock"
    assert status["prompt_version"] == CURRENT_PROMPT_VERSION
    assert status["available"] is True and status["state"] == "available"
    assert "synthetic_data_notice" in status and "consent_statement" in status
    assert "ANTHROPIC_API_KEY" not in str(status.get("provider_health", {}).get("api_key", ""))


@pytest.mark.asyncio
async def test_manager_metadata_and_hosted_deidentification():
    """Hosted calls are scrubbed before leaving and re-identified locally; metadata carries provenance."""
    manager = LLMServiceManager()
    seen = {}

    async def fake_generate(**kwargs):
        seen["content"] = kwargs["user_content"]
        return {"echo": kwargs["user_content"], "_usage": {"model": "claude-x", "input_tokens": 11, "output_tokens": 3}}

    with patch.object(settings, "LLM_PROVIDER", "hosted"):
        with patch.object(manager._hosted, "generate", side_effect=fake_generate):
            out, meta = await manager.generate(
                task="case_summary", system_prompt="s",
                user_content="Patient Name: Asha Kale\nPhone 9123456780\nHb 9.0",
                json_schema={}, encounter_id=5, patient_name="Asha Kale")
    assert "Asha Kale" not in seen["content"] and "9123456780" not in seen["content"]
    assert "Asha Kale" in out["echo"]  # re-attached locally
    assert meta["is_external"] and meta["deidentified"]
    assert (meta["model_name"], meta["input_tokens"], meta["output_tokens"]) == ("claude-x", 11, 3)
    assert meta["prompt_version"] == CURRENT_PROMPT_VERSION and meta["encounter_id"] == 5


@pytest.mark.asyncio
async def test_llm_unavailable_handling():
    """Hosted provider without a key is unavailable, never a crash."""
    from app.services.llm.hosted_provider import HostedLLMProvider
    hosted = HostedLLMProvider(api_key="")
    with patch.object(settings, "ANTHROPIC_API_KEY", ""):
        health = await hosted.health_check()
        assert health["available"] is False
        with pytest.raises(LLMUnavailableError):
            await hosted.generate(task="document_classification", system_prompt="test",
                                  user_content="test", json_schema={})


@pytest.mark.asyncio
async def test_local_provider_has_no_vision():
    from app.services.llm.local_provider import LocalLLMProvider
    with pytest.raises(LLMUnavailableError):
        await LocalLLMProvider().generate(task="handwriting_transcription", system_prompt="s",
                                          user_content="x", json_schema={},
                                          images=[{"media_type": "image/png", "base64_data": "AA=="}])
