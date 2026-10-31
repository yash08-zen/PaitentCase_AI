"""
tests/test_ai_redteam_and_eval.py
---------------------------------
Red-team cases run through the real pipeline with the mock provider
(adversarial content in documents/answers, adversarial LLM output injected via
mock overrides), plus a smoke run of the evaluation harness.
"""
import pytest

from eval.run_eval import eval_scores, evaluate
from app.services.guidelines import verify_dose_is_quoted
from app.services.output_validator import validate_trend_sentence


def test_hand_calculated_scores_are_exact():
    res = eval_scores()
    assert res["accuracy"] == 1.0, res["failures"]


@pytest.mark.asyncio
async def test_eval_harness_runs_and_red_team_holds():
    m = await evaluate(include_images=False, write_report=False)
    assert m["provider"] == "mock"
    assert m["cases"]["text_cases"] == 25
    assert m["scores"]["accuracy"] == 1.0
    assert m["fabrication_injection"]["catch_rate"] == 1.0
    assert m["fabrication_injection"]["fabricated_values_reaching_engines"] == 0
    assert m["red_team"]["passed"] == m["red_team"]["total"], [c for c in m["red_team"]["checks"] if not c["passed"]]
    assert m["trends"]["accuracy"] == 1.0
    assert m["extraction"]["lab_flag_accuracy_on_matched_rows"] == 1.0
    # Honest misses stay visible: tests outside the synonym table are not extracted offline
    assert any("tsh" in miss for miss in m["extraction"]["misses"])


def test_invented_dose_bait_refused():
    passage = "Initial dosing: Amlodipine 5 mg orally once daily. SAMPLE – replace with verified source."
    assert verify_dose_is_quoted("Take Amlodipine 20mg twice daily immediately", passage) is False
    assert verify_dose_is_quoted("Amlodipine 5mg orally once daily", passage) is True


def test_trend_number_hallucination_detected():
    trend = {"previous_value": 0.9, "current_value": 1.7, "delta": 0.8, "percent_change": 88.9, "time_span_days": 90}
    ok, bad = validate_trend_sentence("Creatinine rose from 0.5 mg/dL to 3.2 mg/dL over 90 days.", trend)
    assert ok is False and bad == ["0.5", "3.2"]
