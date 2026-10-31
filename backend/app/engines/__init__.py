"""
app.engines package
-------------------
Deterministic, pure-code clinical calculation and safety engines:
  - lab_flagging: Reference range comparisons and synonym normalization
  - trend_calculator: Delta, percentage change, and threshold evaluations
  - risk_scores: qSOFA, CURB-65, NEWS2, CHA2DS2-VASc
  - red_flags: High-acuity red flag and priority alert detection
  - interactions: Drug-drug interactions, allergy contraindications, diagnosis denials, wrong patient checks
"""
from app.engines.lab_flagging import normalize_test_name, flag_lab_value, process_lab_row
from app.engines.trend_calculator import calculate_trend, load_trend_rules
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

__all__ = [
    "normalize_test_name",
    "flag_lab_value",
    "process_lab_row",
    "calculate_trend",
    "load_trend_rules",
    "calculate_qsofa",
    "calculate_curb65",
    "calculate_news2",
    "calculate_cha2ds2_vasc",
    "evaluate_red_flags",
    "check_drug_interactions",
    "check_allergy_contraindications",
    "check_diagnosis_denials",
    "check_wrong_patient",
]

