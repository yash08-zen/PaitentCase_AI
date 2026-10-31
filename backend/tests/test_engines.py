"""
tests/test_engines.py
---------------------
Unit test suite verifying deterministic clinical engines:
  1. Lab flagging & synonym normalization (never inventing ranges)
  2. Trend calculator against trend_rules.yaml
  3. Published risk scores (qSOFA, CURB-65, NEWS2, CHA2DS2-VASc) against hand-calculated cases
  4. Red-flag acuity urgency rules
  5. Drug-drug interactions, allergy contraindications, diagnosis denials, wrong-patient checks
  6. Grounding validator for extracted entities and trend sentence numbers
"""
import pytest
from app.engines.lab_flagging import normalize_test_name, flag_lab_value, process_lab_row
from app.engines.trend_calculator import calculate_trend
from app.engines.risk_scores import (
    calculate_qsofa,
    calculate_curb65,
    calculate_news2,
    calculate_cha2ds2_vasc,
)
from app.engines.red_flags import evaluate_red_flags
from app.engines.interactions import (
    check_drug_interactions,
    check_allergy_contraindications,
    check_diagnosis_denials,
    check_wrong_patient,
)
from app.services.grounding_validator import GroundingValidator


# ── 1. Lab Flagging Tests ──

def test_lab_flagging_never_invents_ranges():
    """Verify that when document has no reference range, flag is strictly range_not_available."""
    flag, desc = flag_lab_value(1.4, ref_low=None, ref_high=None, normalized_test="creatinine")
    assert flag == "range_not_available"
    assert "not printed on document" in desc


def test_lab_flagging_abnormal_and_critical():
    """Verify high/low and critical threshold flags."""
    # Low haemoglobin
    flag, _ = flag_lab_value(10.5, ref_low=12.0, ref_high=16.0, normalized_test="haemoglobin")
    assert flag == "low"

    # Critical low haemoglobin (< 7.0)
    crit_flag, _ = flag_lab_value(5.8, ref_low=12.0, ref_high=16.0, normalized_test="haemoglobin")
    assert crit_flag == "critical_low"

    # Normal potassium
    k_norm, _ = flag_lab_value(4.2, ref_low=3.5, ref_high=5.0, normalized_test="potassium")
    assert k_norm == "normal"

    # Critical high potassium (> 6.2)
    k_crit, _ = flag_lab_value(6.8, ref_low=3.5, ref_high=5.0, normalized_test="potassium")
    assert k_crit == "critical_high"


def test_test_name_synonym_normalization():
    """Verify clinical test name synonym normalization."""
    assert normalize_test_name("Hb") == "haemoglobin"
    assert normalize_test_name("Hgb") == "haemoglobin"
    assert normalize_test_name("Serum Creatinine") == "creatinine"
    assert normalize_test_name("S. Creatinine") == "creatinine"
    assert normalize_test_name("FBS") == "fasting_blood_glucose"
    assert normalize_test_name("Total Leukocyte Count") == "wbc_count"


# ── 2. Trend Calculator Tests ──

def test_trend_calculator_aki_rise_criterion():
    """Verify acute creatinine rise criterion (>= 0.3 mg/dL within 7 days)."""
    trend = calculate_trend(
        previous_val=1.0,
        current_val=1.4,
        previous_date_str="2026-05-01",
        current_date_str="2026-05-05",
        test_normalized_name="creatinine"
    )
    assert trend["direction"] == "rising"
    assert trend["delta"] == 0.4
    assert trend["percent_change"] == 40.0
    assert trend["rule_matched"] == "CREATININE_AKI_ACUTE_RISE"
    assert "KDIGO Stage 1" in trend["clinical_label"]


def test_trend_calculator_stable():
    """Verify stable lab result trend."""
    trend = calculate_trend(
        previous_val=14.0,
        current_val=14.0,
        previous_date_str="2026-01-01",
        current_date_str="2026-02-01",
        test_normalized_name="haemoglobin"
    )
    assert trend["direction"] == "stable"
    assert trend["delta"] == 0.0
    assert trend["rule_matched"] is None


# ── 3. Published Clinical Risk Scores Tests ──

def test_qsofa_hand_calculated_cases():
    """Verify qSOFA score against hand-calculated cases and missing input handling."""
    # Case 1: SBP <= 100 (+1), RR >= 22 (+1), AMS True (+1) => Score = 3
    c1 = calculate_qsofa(respiratory_rate=24, systolic_bp=95, altered_mental_status=True)
    assert c1["status"] == "calculated"
    assert c1["score_value"] == 3.0
    assert "High risk" in c1["interpretation"]

    # Case 2: SBP 120 (0), RR 16 (0), AMS False (0) => Score = 0
    c2 = calculate_qsofa(respiratory_rate=16, systolic_bp=120, altered_mental_status=False)
    assert c2["status"] == "calculated"
    assert c2["score_value"] == 0.0

    # Case 3: Missing systolic_bp => NOT CALCULABLE
    c3 = calculate_qsofa(respiratory_rate=24, systolic_bp=None, altered_mental_status=True)
    assert c3["status"] == "not_calculable"
    assert c3["score_value"] is None
    assert "systolic_bp" in c3["missing_inputs"]


def test_curb65_hand_calculated_cases():
    """Verify CURB-65 pneumonia severity score against hand-calculated cases."""
    # Case 1: Confusion (+1), BUN > 19 (+1), RR >= 30 (+1), SBP < 90 (+1), Age >= 65 (+1) => Score = 5
    c1 = calculate_curb65(
        confusion=True,
        urea_mmol_or_bun_mgdl=28.0,
        respiratory_rate=34,
        systolic_bp=85,
        diastolic_bp=55,
        age=72,
        is_bun=True
    )
    assert c1["status"] == "calculated"
    assert c1["score_value"] == 5.0
    assert "High severity" in c1["interpretation"]

    # Case 2: Missing inputs => NOT CALCULABLE
    c2 = calculate_curb65(
        confusion=False,
        urea_mmol_or_bun_mgdl=None,
        respiratory_rate=20,
        systolic_bp=120,
        diastolic_bp=80,
        age=55
    )
    assert c2["status"] == "not_calculable"
    assert "urea_or_bun" in c2["missing_inputs"]


def test_news2_hand_calculated_cases():
    """Verify NEWS2 score calculation across multiple physiological parameters."""
    # Case 1: Healthy baseline => Score = 0
    c1 = calculate_news2(
        respiration_rate=16,
        spo2=98,
        air_or_oxygen="air",
        systolic_bp=125,
        pulse_rate=72,
        consciousness="alert",
        temperature=37.0
    )
    assert c1["status"] == "calculated"
    assert c1["score_value"] == 0.0
    assert "Low clinical risk" in c1["interpretation"]

    # Case 2: High acuity => RR 28 (+3), SpO2 90 (+3), O2 (+2), SBP 88 (+3), PR 115 (+2), CVPU (+3), Temp 39.5 (+2) => Score = 18
    c2 = calculate_news2(
        respiration_rate=28,
        spo2=90,
        air_or_oxygen="oxygen",
        systolic_bp=88,
        pulse_rate=115,
        consciousness="cvpu",
        temperature=39.5
    )
    assert c2["status"] == "calculated"
    assert c2["score_value"] == 18.0
    assert "High clinical risk" in c2["interpretation"]


def test_cha2ds2_vasc_hand_calculated_cases():
    """Verify CHA2DS2-VASc stroke risk in AF score."""
    # Case: Female (+1), Age 78 (+2), HTN (+1), DM (+1), Prior Stroke (+2), CHF (+1), Vascular (+1) => Score = 9
    c1 = calculate_cha2ds2_vasc(
        age=78,
        sex="female",
        congestive_heart_failure=True,
        hypertension=True,
        stroke_or_tia_history=True,
        vascular_disease=True,
        diabetes=True
    )
    assert c1["status"] == "calculated"
    assert c1["score_value"] == 9.0
    assert "Moderate-high stroke risk" in c1["interpretation"]

    # Case 2: Young male with no risk factors => Score = 0
    c2 = calculate_cha2ds2_vasc(
        age=40,
        sex="male",
        congestive_heart_failure=False,
        hypertension=False,
        stroke_or_tia_history=False,
        vascular_disease=False,
        diabetes=False
    )
    assert c2["status"] == "calculated"
    assert c2["score_value"] == 0.0


# ── 4. Red-Flag Acuity Rules Tests ──

def test_red_flags_cardiac_and_neurological():
    """Verify emergency acuity trigger for ACS and stroke warning signs."""
    # Cardiac ACS trigger
    cardiac = evaluate_red_flags(
        interview_answers={
            "chief_complaint": "Severe chest pain radiating to left arm",
            "pain_characteristics": "breathless and sweating"
        }
    )
    assert cardiac["overall_urgency"] == "EMERGENCY"
    assert any(a["code"] == "CARD_ACS_RED_FLAG" for a in cardiac["alerts"])

    # Neurological FAST stroke trigger
    neuro = evaluate_red_flags(
        interview_answers={
            "chief_complaint": "Sudden facial droop and weakness on one side of body"
        }
    )
    assert neuro["overall_urgency"] == "EMERGENCY"
    assert any(a["code"] == "NEURO_STROKE_RED_FLAG" for a in neuro["alerts"])

    # Routine mild symptoms
    routine = evaluate_red_flags(
        interview_answers={"chief_complaint": "Mild common cold and runny nose"}
    )
    assert routine["overall_urgency"] == "ROUTINE"
    assert not routine["has_red_flags"]


# ── 5. Interactions and Discrepancies Tests ──

def test_drug_drug_interaction_detection():
    """Verify detection of severe drug interaction (Metformin + Radiocontrast)."""
    meds = ["Metformin 500mg", "Iohexol radiocontrast", "Multivitamin"]
    conflicts = check_drug_interactions(meds)
    assert len(conflicts) > 0
    assert conflicts[0]["rule_id"] == "RULE-INTERACTION"
    assert "lactic acidosis" in conflicts[0]["description"]


def test_allergy_contraindication_detection():
    """Verify contraindication check for Penicillin allergy with Amoxicillin."""
    allergies = ["penicillin"]
    meds = ["Amoxicillin 500mg TDS", "Paracetamol 650mg"]
    conflicts = check_allergy_contraindications(allergies, meds)
    assert len(conflicts) > 0
    assert conflicts[0]["rule_id"] == "RULE-ALLERGY-CONFLICT"
    assert "contraindicated" in conflicts[0]["description"]


def test_diagnosis_denial_check():
    """Verify RULE-DIAGNOSIS-DENIAL when patient denied condition that record documents."""
    denied = ["diabetes"]
    documented = ["Type 2 Diabetes Mellitus", "Dyslipidemia"]
    conflicts = check_diagnosis_denials(denied, documented)
    assert len(conflicts) > 0
    assert conflicts[0]["rule_id"] == "RULE-DIAGNOSIS-DENIAL"


def test_wrong_patient_check():
    """Verify RULE-WRONG-PATIENT when document header name conflicts with registered patient."""
    doc_header = "Hospital Discharge Summary\nPatient Name: Suresh Chandra Patel\nAge: 62\nDate: 2026-03-12"
    conflicts = check_wrong_patient(doc_header, patient_name="Ramesh Kumar Gupta", patient_age=35)
    assert len(conflicts) >= 1
    assert any(c["rule_id"] == "RULE-WRONG-PATIENT" for c in conflicts)


# ── 6. Grounding Validator Tests ──

def test_grounding_validator_spans():
    """Verify that ungrounded extracted claims are caught and flagged."""
    ocr_source = "Rx: Tab Metformin 500mg PO BD. Diagnosis: Type 2 Diabetes. S. Creatinine 1.2 mg/dL."
    
    extracted = {
        "diagnoses": [
            {"name": "Type 2 Diabetes", "source_span": "Type 2 Diabetes"},
            {"name": "Rheumatoid Arthritis", "source_span": "Rheumatoid Arthritis"}  # Hallucinated
        ],
        "medications": [
            {"name": "Metformin", "source_span": "Metformin 500mg"},
            {"name": "Ciprofloxacin", "source_span": "Ciprofloxacin"}  # Hallucinated
        ],
        "lab_rows": [
            {"test": "Creatinine", "value": 1.2, "unit": "mg/dL"}
        ]
    }

    validated = GroundingValidator.validate_extracted_entities(extracted, ocr_source)
    assert validated["diagnoses"][0]["grounded"] is True
    assert validated["diagnoses"][1]["grounded"] is False  # Flagged!

    assert validated["medications"][0]["grounded"] is True
    assert validated["medications"][1]["grounded"] is False  # Flagged!
    assert validated["all_grounded"] is False


def test_grounding_validator_trend_sentence_numbers():
    """Verify rejection of sentences with hallucinated numbers."""
    valid_sentence = "Creatinine rose from 1.0 to 1.8 mg/dL over 90 days."
    is_valid, bad_nums = GroundingValidator.validate_trend_sentence_numbers(
        valid_sentence,
        computed_previous=1.0,
        computed_current=1.8,
        computed_delta=0.8,
        computed_percent=80.0,
        time_span_days=90
    )
    assert is_valid is True
    assert len(bad_nums) == 0

    # Hallucinated number (e.g. model made up '4.5')
    hallucinated_sentence = "Creatinine rose from 1.0 to 1.8 mg/dL and eGFR dropped to 45 with 4.5 ratio."
    is_valid_bad, bad_nums = GroundingValidator.validate_trend_sentence_numbers(
        hallucinated_sentence,
        computed_previous=1.0,
        computed_current=1.8,
        computed_delta=0.8,
        computed_percent=80.0,
        time_span_days=90
    )
    assert is_valid_bad is False
    assert "4.5" in bad_nums

