"""
engines/lab_flagging.py
-----------------------
Deterministic laboratory reference range comparison and synonym normalization.
Follows the non-negotiable rule:
    If no reference range is printed on the document, flag as 'range_not_available'.
    Never invent, assume, or hallucinate a reference range.
"""
import re
from typing import Dict, Any, Optional, Tuple, List


# Canonical normalization dictionary for common lab test synonyms
TEST_SYNONYMS: Dict[str, str] = {
    "hb": "haemoglobin",
    "hgb": "haemoglobin",
    "haemoglobin": "haemoglobin",
    "hemoglobin": "haemoglobin",
    "cr": "creatinine",
    "creatinine": "creatinine",
    "serum creatinine": "creatinine",
    "s creatinine": "creatinine",
    "s. creatinine": "creatinine",
    "sr creatinine": "creatinine",
    "fbs": "fasting_blood_glucose",
    "fasting blood sugar": "fasting_blood_glucose",
    "fasting plasma glucose": "fasting_blood_glucose",
    "fpg": "fasting_blood_glucose",
    "ppbs": "postprandial_blood_glucose",
    "post prandial blood sugar": "postprandial_blood_glucose",
    "hba1c": "hba1c",
    "glycated hemoglobin": "hba1c",
    "glycated haemoglobin": "hba1c",
    "platelets": "platelets",
    "platelet count": "platelets",
    "plt": "platelets",
    "wbc": "wbc_count",
    "total leukocyte count": "wbc_count",
    "tlc": "wbc_count",
    "white blood cells": "wbc_count",
    "potassium": "potassium",
    "serum potassium": "potassium",
    "k+": "potassium",
    "sodium": "sodium",
    "serum sodium": "sodium",
    "na+": "sodium",
    "urea": "blood_urea",
    "blood urea": "blood_urea",
    "bun": "blood_urea_nitrogen",
    "blood urea nitrogen": "blood_urea_nitrogen",
    "bilirubin": "total_bilirubin",
    "total bilirubin": "total_bilirubin",
    "sgot": "ast",
    "ast": "ast",
    "sgpt": "alt",
    "alt": "alt",
}

# Critical physiological thresholds requiring immediate clinician notification
CRITICAL_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "potassium": {"critical_low": 2.5, "critical_high": 6.2},
    "sodium": {"critical_low": 120.0, "critical_high": 160.0},
    "haemoglobin": {"critical_low": 7.0},
    "platelets": {"critical_low": 20.0},
    "creatinine": {"critical_high": 4.0},
    "fasting_blood_glucose": {"critical_low": 50.0, "critical_high": 400.0},
}


# Canonical unit per normalized test, with deterministic conversions from
# alternate units (factor multiplies the alternate value into the canonical unit).
CANONICAL_UNITS: Dict[str, Dict[str, Any]] = {
    "creatinine": {"unit": "mg/dL", "convert": {"umol/l": 1 / 88.4, "µmol/l": 1 / 88.4}},
    "fasting_blood_glucose": {"unit": "mg/dL", "convert": {"mmol/l": 18.016}},
    "postprandial_blood_glucose": {"unit": "mg/dL", "convert": {"mmol/l": 18.016}},
    "haemoglobin": {"unit": "g/dL", "convert": {"g/l": 0.1}},
    "blood_urea": {"unit": "mg/dL", "convert": {"mmol/l": 6.006}},
    "blood_urea_nitrogen": {"unit": "mg/dL", "convert": {"mmol/l": 2.801}},
    "potassium": {"unit": "mmol/L", "convert": {"meq/l": 1.0}},
    "sodium": {"unit": "mmol/L", "convert": {"meq/l": 1.0}},
}


def _unit_key(unit: Optional[str]) -> str:
    return (unit or "").strip().lower().replace(" ", "").replace("μ", "µ").replace("micromol", "umol")


def normalize_units(
    normalized_test: str,
    value: float,
    unit: Optional[str],
    ref_low: Optional[float],
    ref_high: Optional[float],
) -> Tuple[float, Optional[str], Optional[float], Optional[float], Optional[str]]:
    """
    Convert value and printed reference range into the canonical unit for the test.
    Returns (value, unit, ref_low, ref_high, note). Unknown units are left untouched
    and reported in note; nothing is guessed.
    """
    spec = CANONICAL_UNITS.get(normalized_test)
    if not spec or not unit:
        return value, unit, ref_low, ref_high, None
    if _unit_key(unit) == _unit_key(spec["unit"]):
        return value, spec["unit"], ref_low, ref_high, None
    factor = spec["convert"].get(_unit_key(unit))
    if factor is None:
        return value, unit, ref_low, ref_high, f"unit '{unit}' not normalized"

    def conv(x: Optional[float]) -> Optional[float]:
        return round(x * factor, 2) if x is not None else None

    return conv(value), spec["unit"], conv(ref_low), conv(ref_high), f"converted from {unit}"


def normalize_test_name(raw_name: str) -> str:
    """Normalize test name using clinical synonym dictionary."""
    clean = re.sub(r"[^a-zA-Z0-9\s+]", "", raw_name).strip().lower()
    return TEST_SYNONYMS.get(clean, clean)


def flag_lab_value(
    value: float,
    ref_low: Optional[float],
    ref_high: Optional[float],
    normalized_test: Optional[str] = None
) -> Tuple[str, str]:
    """
    Deterministically flag a laboratory result against document reference ranges.
    Returns:
        (flag, description)
        flag is one of: 'normal', 'low', 'high', 'critical_low', 'critical_high', 'range_not_available'
    """
    # Rule 1: Never invent ranges. If both are missing, mark range_not_available.
    if ref_low is None and ref_high is None:
        return "range_not_available", "Reference range not printed on document; range unavailable."

    test_key = normalized_test or ""
    crit_info = CRITICAL_THRESHOLDS.get(test_key, {})

    # Check critical alerts
    if "critical_low" in crit_info and value <= crit_info["critical_low"]:
        return "critical_low", f"Critically low value ({value}); exceeds safe threshold ({crit_info['critical_low']})."
    if "critical_high" in crit_info and value >= crit_info["critical_high"]:
        return "critical_high", f"Critically high value ({value}); exceeds safe threshold ({crit_info['critical_high']})."

    # Compare against document-printed ranges
    if ref_low is not None and value < ref_low:
        return "low", f"Below document reference range ({ref_low} – {ref_high or 'N/A'})."
    if ref_high is not None and value > ref_high:
        return "high", f"Above document reference range ({ref_low or 'N/A'} – {ref_high})."

    return "normal", "Within printed reference range."


def process_lab_row(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Process a raw extracted lab row into a flagged, validated dictionary."""
    test_name = row_dict.get("test") or row_dict.get("name") or "Unknown Test"
    norm_name = row_dict.get("normalized_test") or normalize_test_name(test_name)

    raw_value = row_dict.get("value")
    if raw_value is None or str(raw_value).strip() == "":
        raise ValueError(f"Lab row '{test_name}' has no value; refusing to invent one.")
    val = float(raw_value)
    ref_low = float(row_dict["ref_low"]) if row_dict.get("ref_low") is not None else None
    ref_high = float(row_dict["ref_high"]) if row_dict.get("ref_high") is not None else None

    val, unit, ref_low, ref_high, unit_note = normalize_units(
        norm_name, val, row_dict.get("unit"), ref_low, ref_high
    )
    flag, desc = flag_lab_value(val, ref_low, ref_high, norm_name)

    return {
        "test_name": test_name,
        "normalized_test": norm_name,
        "value": val,
        "unit": unit,
        "unit_note": unit_note,
        "original_value": raw_value,
        "original_unit": row_dict.get("unit"),
        "ref_low": ref_low,
        "ref_high": ref_high,
        "flag": flag,
        "flag_description": desc,
        "test_date": row_dict.get("date") or row_dict.get("test_date"),
        "source_span": row_dict.get("source_span"),
    }
