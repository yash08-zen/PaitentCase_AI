"""
engines/trend_calculator.py
---------------------------
Deterministic clinical laboratory trend calculator.
Computes delta, percent change, direction, and time intervals between sequential tests.
Evaluates trend criteria from config/trend_rules.yaml with clear clinician warnings.
"""
import os
import yaml
from datetime import datetime, date
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("app.engines.trend")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config", "trend_rules.yaml")


def load_trend_rules() -> Dict[str, Any]:
    """Load configurable clinical trend thresholds from YAML."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load trend_rules.yaml: {e}")
    return {}


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse common clinical date string formats."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None


def calculate_trend(
    previous_val: float,
    current_val: float,
    previous_date_str: Optional[str] = None,
    current_date_str: Optional[str] = None,
    test_normalized_name: str = "creatinine"
) -> Dict[str, Any]:
    """
    Compute delta, percentage, direction, and matched rules for two sequential tests.
    """
    delta = round(current_val - previous_val, 2)
    percent_change = 0.0
    if previous_val != 0.0:
        percent_change = round(((current_val - previous_val) / abs(previous_val)) * 100.0, 1)

    if delta > 0.05:
        direction = "rising"
    elif delta < -0.05:
        direction = "falling"
    else:
        direction = "stable"

    # Compute time span days
    days_span = None
    d1 = parse_date(previous_date_str)
    d2 = parse_date(current_date_str)
    if d1 and d2:
        days_span = abs((d2 - d1).days)

    matched_rule = None
    clinical_label = None

    # Evaluate rules from config
    config = load_trend_rules()
    rules_dict = config.get("rules", {})

    test_rules = rules_dict.get(test_normalized_name, {}).get("criteria", [])
    for criterion in test_rules:
        target_dir = criterion.get("direction")
        if target_dir != direction:
            continue

        # Check time window if days_span is known
        max_days = criterion.get("time_window_days")
        if days_span is not None and max_days is not None and days_span > max_days:
            continue

        # Check min absolute change
        min_abs = criterion.get("min_absolute_change")
        if min_abs is not None and abs(delta) < min_abs:
            continue

        # Check min percent change
        min_pct = criterion.get("min_percent_change")
        if min_pct is not None and abs(percent_change) < min_pct:
            continue

        matched_rule = criterion.get("id")
        clinical_label = criterion.get("label")
        break

    return {
        "test_name": test_normalized_name,
        "previous_value": previous_val,
        "current_value": current_val,
        "delta": delta,
        "percent_change": percent_change,
        "direction": direction,
        "time_span_days": days_span,
        "rule_matched": matched_rule,
        "clinical_label": clinical_label,
        "disclaimer": "Thresholds require clinician verification before real use."
    }

