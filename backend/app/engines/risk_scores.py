"""
engines/risk_scores.py
----------------------
Deterministic published clinical risk and urgency score calculators:
  - qSOFA (Quick Sepsis Organ Failure Assessment, Singer et al. 2016)
  - CURB-65 (Community-Acquired Pneumonia Severity, Lim et al. 2003)
  - NEWS2 (National Early Warning Score 2, Royal College of Physicians 2017)
  - CHA2DS2-VASc (Atrial Fibrillation Stroke Risk, Lip et al. 2010)

NON-NEGOTIABLE CLINICAL SAFETY RULE:
  If ANY required physiological input is missing, the engine returns status='not_calculable'
  along with an explicit list of missing inputs. Missing values are NEVER assumed or hallucinated.
"""
from typing import Dict, Any, List, Optional


def calculate_qsofa(
    respiratory_rate: Optional[float],
    systolic_bp: Optional[float],
    altered_mental_status: Optional[bool]
) -> Dict[str, Any]:
    """
    qSOFA:
      RR >= 22 bpm -> 1
      SBP <= 100 mmHg -> 1
      Altered mental status -> 1
    Total range: 0 - 3
    """
    version = "Singer et al. JAMA 2016 (qSOFA)"
    inputs = {
        "respiratory_rate": respiratory_rate,
        "systolic_bp": systolic_bp,
        "altered_mental_status": altered_mental_status,
    }
    missing = [k for k, v in inputs.items() if v is None]

    if missing:
        return {
            "score_name": "qSOFA",
            "score_value": None,
            "status": "not_calculable",
            "inputs": inputs,
            "missing_inputs": missing,
            "formula_version": version,
            "interpretation": f"Cannot calculate qSOFA. Missing required inputs: {', '.join(missing)}."
        }

    score = 0
    if float(respiratory_rate) >= 22.0:
        score += 1
    if float(systolic_bp) <= 100.0:
        score += 1
    if bool(altered_mental_status) is True:
        score += 1

    interp = "Low risk for sepsis-related poor outcome (< 2 points)."
    if score >= 2:
        interp = "High risk (score >= 2): Suggests high risk of in-hospital mortality or prolonged ICU stay; investigate for sepsis."

    return {
        "score_name": "qSOFA",
        "score_value": float(score),
        "status": "calculated",
        "inputs": inputs,
        "missing_inputs": [],
        "formula_version": version,
        "interpretation": interp
    }


def calculate_curb65(
    confusion: Optional[bool],
    urea_mmol_or_bun_mgdl: Optional[float],
    respiratory_rate: Optional[float],
    systolic_bp: Optional[float],
    diastolic_bp: Optional[float],
    age: Optional[float],
    *,
    is_bun: bool = False
) -> Dict[str, Any]:
    """
    CURB-65:
      C: Confusion -> 1
      U: Urea > 7 mmol/L (or BUN > 19 mg/dL) -> 1
      R: RR >= 30 bpm -> 1
      B: SBP < 90 mmHg or DBP <= 60 mmHg -> 1
      65: Age >= 65 -> 1
    Range: 0 - 5
    """
    version = "Lim et al. Thorax 2003 (CURB-65)"
    inputs = {
        "confusion": confusion,
        "urea_or_bun": urea_mmol_or_bun_mgdl,
        "respiratory_rate": respiratory_rate,
        "systolic_bp": systolic_bp,
        "diastolic_bp": diastolic_bp,
        "age": age,
    }
    missing = [k for k, v in inputs.items() if v is None]

    if missing:
        return {
            "score_name": "CURB-65",
            "score_value": None,
            "status": "not_calculable",
            "inputs": inputs,
            "missing_inputs": missing,
            "formula_version": version,
            "interpretation": f"Cannot calculate CURB-65. Missing required inputs: {', '.join(missing)}."
        }

    score = 0
    if bool(confusion) is True:
        score += 1

    u_val = float(urea_mmol_or_bun_mgdl)
    if is_bun:
        if u_val > 19.0:
            score += 1
    else:
        if u_val > 7.0:
            score += 1

    if float(respiratory_rate) >= 30.0:
        score += 1
    if float(systolic_bp) < 90.0 or float(diastolic_bp) <= 60.0:
        score += 1
    if float(age) >= 65.0:
        score += 1

    if score <= 1:
        interp = "Low severity pneumonia (score 0-1): Outpatient care typically considered."
    elif score == 2:
        interp = "Intermediate severity pneumonia (score 2): Inpatient observation or short stay considered."
    else:
        interp = "High severity pneumonia (score 3-5): Urgent inpatient hospital admission / ICU evaluation indicated."

    return {
        "score_name": "CURB-65",
        "score_value": float(score),
        "status": "calculated",
        "inputs": inputs,
        "missing_inputs": [],
        "formula_version": version,
        "interpretation": interp
    }


def calculate_news2(
    respiration_rate: Optional[float],
    spo2: Optional[float],
    air_or_oxygen: Optional[str],  # 'air' or 'oxygen'
    systolic_bp: Optional[float],
    pulse_rate: Optional[float],
    consciousness: Optional[str],  # 'alert' or 'cvpu' / 'confusion'
    temperature: Optional[float]
) -> Dict[str, Any]:
    """
    NEWS2 (National Early Warning Score 2, Royal College of Physicians 2017).
    Range: 0 - 20.
    """
    version = "Royal College of Physicians 2017 (NEWS2)"
    inputs = {
        "respiration_rate": respiration_rate,
        "spo2": spo2,
        "air_or_oxygen": air_or_oxygen,
        "systolic_bp": systolic_bp,
        "pulse_rate": pulse_rate,
        "consciousness": consciousness,
        "temperature": temperature,
    }
    missing = [k for k, v in inputs.items() if v is None]

    if missing:
        return {
            "score_name": "NEWS2",
            "score_value": None,
            "status": "not_calculable",
            "inputs": inputs,
            "missing_inputs": missing,
            "formula_version": version,
            "interpretation": f"Cannot calculate NEWS2. Missing required physiological inputs: {', '.join(missing)}."
        }

    score = 0

    # 1. Respiration Rate
    rr = float(respiration_rate)
    if rr <= 8.0:
        score += 3
    elif 9.0 <= rr <= 11.0:
        score += 1
    elif 12.0 <= rr <= 20.0:
        score += 0
    elif 21.0 <= rr <= 24.0:
        score += 2
    else:  # >= 25
        score += 3

    # 2. SpO2 (Scale 1)
    s = float(spo2)
    if s <= 91.0:
        score += 3
    elif 92.0 <= s <= 93.0:
        score += 2
    elif 94.0 <= s <= 95.0:
        score += 1
    else:
        score += 0

    # 3. Supplemental Oxygen
    if str(air_or_oxygen).strip().lower() in ("oxygen", "o2", "supplemental"):
        score += 2

    # 4. Systolic BP
    sbp = float(systolic_bp)
    if sbp <= 90.0:
        score += 3
    elif 91.0 <= sbp <= 100.0:
        score += 2
    elif 101.0 <= sbp <= 110.0:
        score += 1
    elif 111.0 <= sbp <= 219.0:
        score += 0
    else:  # >= 220
        score += 3

    # 5. Pulse rate
    pr = float(pulse_rate)
    if pr <= 40.0:
        score += 3
    elif 41.0 <= pr <= 50.0:
        score += 1
    elif 51.0 <= pr <= 90.0:
        score += 0
    elif 91.0 <= pr <= 110.0:
        score += 1
    elif 111.0 <= pr <= 130.0:
        score += 2
    else:  # >= 131
        score += 3

    # 6. Consciousness (Alert vs CVPU)
    c_str = str(consciousness).strip().lower()
    if c_str not in ("a", "alert"):
        score += 3

    # 7. Temperature
    temp = float(temperature)
    if temp <= 35.0:
        score += 3
    elif 35.1 <= temp <= 36.0:
        score += 1
    elif 36.1 <= temp <= 38.0:
        score += 0
    elif 38.1 <= temp <= 39.0:
        score += 1
    else:  # >= 39.1
        score += 2

    if score <= 4:
        interp = "Low clinical risk: Ward-based monitoring."
    elif 5 <= score <= 6:
        interp = "Medium clinical risk: Urgent response by clinician or team with critical care skills."
    else:
        interp = "High clinical risk (score >= 7): Emergency critical care response required."

    return {
        "score_name": "NEWS2",
        "score_value": float(score),
        "status": "calculated",
        "inputs": inputs,
        "missing_inputs": [],
        "formula_version": version,
        "interpretation": interp
    }


def calculate_cha2ds2_vasc(
    age: Optional[float],
    sex: Optional[str],  # 'male' or 'female'
    congestive_heart_failure: Optional[bool],
    hypertension: Optional[bool],
    stroke_or_tia_history: Optional[bool],
    vascular_disease: Optional[bool],
    diabetes: Optional[bool]
) -> Dict[str, Any]:
    """
    CHA2DS2-VASc:
      C: Congestive heart failure -> 1
      H: Hypertension -> 1
      A2: Age >= 75 -> 2
      D: Diabetes -> 1
      S2: Prior Stroke/TIA/thromboembolism -> 2
      V: Vascular disease history -> 1
      A: Age 65-74 -> 1 (if age < 75)
      Sc: Sex category Female -> 1
    Range: 0 - 9
    """
    version = "Lip et al. Chest 2010 (CHA2DS2-VASc)"
    inputs = {
        "age": age,
        "sex": sex,
        "congestive_heart_failure": congestive_heart_failure,
        "hypertension": hypertension,
        "stroke_or_tia_history": stroke_or_tia_history,
        "vascular_disease": vascular_disease,
        "diabetes": diabetes,
    }
    missing = [k for k, v in inputs.items() if v is None]

    if missing:
        return {
            "score_name": "CHA2DS2-VASc",
            "score_value": None,
            "status": "not_calculable",
            "inputs": inputs,
            "missing_inputs": missing,
            "formula_version": version,
            "interpretation": f"Cannot calculate CHA2DS2-VASc. Missing required clinical inputs: {', '.join(missing)}."
        }

    score = 0
    if bool(congestive_heart_failure) is True:
        score += 1
    if bool(hypertension) is True:
        score += 1

    a_val = float(age)
    if a_val >= 75.0:
        score += 2
    elif 65.0 <= a_val < 75.0:
        score += 1

    if bool(diabetes) is True:
        score += 1
    if bool(stroke_or_tia_history) is True:
        score += 2
    if bool(vascular_disease) is True:
        score += 1

    s_str = str(sex).strip().lower()
    if s_str in ("female", "f", "woman"):
        score += 1

    if score == 0:
        interp = "Very low stroke risk (score 0 in males). Anticoagulation typically not recommended."
    elif score == 1:
        interp = "Low-moderate stroke risk (score 1). Oral anticoagulation may be considered."
    else:
        interp = f"Moderate-high stroke risk (score {score}). Oral anticoagulation strongly recommended in nonvalvular AF."

    return {
        "score_name": "CHA2DS2-VASc",
        "score_value": float(score),
        "status": "calculated",
        "inputs": inputs,
        "missing_inputs": [],
        "formula_version": version,
        "interpretation": interp
    }

