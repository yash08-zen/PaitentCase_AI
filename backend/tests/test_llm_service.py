"""
tests/test_llm_service.py
-------------------------
Comprehensive test suite for Phase 1: LLM Service Layer, Scrubber,
Mock Provider, and Provider Lifecycle.
"""
import pytest
from app.services.llm.scrubber import TextScrubber
from app.services.llm.interface import LLMUnavailableError, LLMProviderError
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.manager import LLMServiceManager, CURRENT_PROMPT_VERSION
from app.core.config import settings


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

    # Assert PII is removed
    assert "Ramesh Kumar Gupta" not in scrubbed
    assert "2345 6789 0123" not in scrubbed
    assert "12-3456-7890-1234" not in scrubbed
    assert "9876543210" not in scrubbed
    assert "ramesh.gupta@example.in" not in scrubbed
    assert "UHID-98234" not in scrubbed

    # Assert placeholders exist
    assert "[PATIENT_NAME_1]" in scrubbed
    assert "[AADHAAR_" in scrubbed
    assert "[PHONE_" in scrubbed
    assert "[EMAIL_" in scrubbed

    # Re-attach
    reattached = TextScrubber.reattach(scrubbed, token_map)
    assert reattached == clinical_text


@pytest.mark.asyncio
async def test_mock_provider_tasks():
    """Verify mock provider generates valid schema structures for all core clinical tasks."""
    provider = MockLLMProvider()

    # 1. Document classification
    cls_res = await provider.generate(
        task="document_classification",
        system_prompt="Classify document",
        user_content="Complete blood count and serum creatinine lab report",
        json_schema={"type": "object"}
    )
    assert cls_res["document_type"] == "lab_report"
    assert cls_res["confidence"] > 0.9

    # 2. Document extraction
    ext_res = await provider.generate(
        task="document_extraction",
        system_prompt="Extract clinical entities",
        user_content="Diagnosed with Type 2 Diabetes. Take Metformin 500mg twice daily. Creatinine 1.4 mg/dL.",
        json_schema={"type": "object"}
    )
    assert any("Diabetes" in d["name"] for d in ext_res["diagnoses"])
    assert any("Metformin" in m["name"] for m in ext_res["medications"])
    assert any("Creatinine" in l["test"] for l in ext_res["lab_rows"])

    # 3. Disease considerations
    con_res = await provider.generate(
        task="disease_considerations",
        system_prompt="Propose considerations",
        user_content="Patient reports polyuria, polydipsia, HbA1c 8.2%",
        json_schema={"type": "object"}
    )
    assert len(con_res["considerations"]) > 0
    assert con_res["considerations"][0]["likelihood"] in ("more likely", "possible", "less likely")
    assert "supporting_findings" in con_res["considerations"][0]

    # 4. Treatment reference
    tx_res = await provider.generate(
        task="treatment_reference",
        system_prompt="Retrieve guidelines",
        user_content="Type 2 Diabetes initial therapy",
        json_schema={"type": "object"}
    )
    assert len(tx_res["guideline_summaries"]) > 0
    assert "dose_quotation" in tx_res["guideline_summaries"][0]
    assert "SAMPLE – replace with verified source" in tx_res["guideline_summaries"][0]["guideline_source"]

    # 5. Trend interpretation
    trend_res = await provider.generate(
        task="trend_interpretation",
        system_prompt="Interpret trend",
        user_content="Creatinine delta: +0.8 mg/dL over 90 days",
        json_schema={"type": "object"}
    )
    assert "Creatinine rose from" in trend_res["interpretation"]

    # 6. Case summary
    summ_res = await provider.generate(
        task="case_summary",
        system_prompt="Summarize case",
        user_content="Intake details and history",
        json_schema={"type": "object"}
    )
    assert "chief_complaint" in summ_res
    assert "hpi" in summ_res
    assert "source_references" in summ_res


@pytest.mark.asyncio
async def test_llm_service_manager_status():
    """Verify LLM service manager status returns provider metadata and safety notices."""
    manager = LLMServiceManager()
    status = await manager.get_status()

    assert "active_mode" in status
    assert status["prompt_version"] == CURRENT_PROMPT_VERSION
    assert "synthetic_data_notice" in status
    assert "consent_statement" in status


@pytest.mark.asyncio
async def test_llm_unavailable_handling():
    """Verify graceful error propagation when hosted provider is missing API key."""
    from app.services.llm.hosted_provider import HostedLLMProvider
    hosted = HostedLLMProvider(api_key="")
    
    with pytest.raises(LLMUnavailableError):
        await hosted.generate(
            task="document_classification",
            system_prompt="test",
            user_content="test",
            json_schema={}
        )

