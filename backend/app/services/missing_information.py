"""
services/missing_information.py
--------------------------------
Compares collected responses against a configurable required-field checklist.
Returns only genuinely missing required fields — optional fields are never flagged.

Safety rule (M5):
  - Missing information ≠ negative answer.
  - An unreported allergy is displayed as "Not provided / unknown", never "no allergies".
  - Blanks/skipped are always treated as "Not provided / unknown", never as "No".
"""
from typing import List, Dict, Optional
from app.schemas import MissingField

# Required clinical intake checklist — maps question_key to clinical label, section, rationale, criticality
REQUIRED_FIELDS = [
    {
        "key": "chief_complaint",
        "label": "Chief complaint",
        "section": "Symptoms",
        "reason": "Primary reason for visit is essential for clinician review and triage.",
        "critical": True,
    },
    {
        "key": "symptom_duration",
        "label": "Duration of symptoms",
        "section": "Symptoms",
        "reason": "Duration helps assess acuity and whether condition is acute vs chronic.",
        "critical": True,
    },
    {
        "key": "symptom_severity",
        "label": "Symptom severity (1-10)",
        "section": "Symptoms",
        "reason": "Severity rating (1-10) indicates patient pain/discomfort level for clinician review.",
        "critical": True,
    },
    {
        "key": "has_chronic_conditions",
        "label": "Chronic medical conditions",
        "section": "Medical History",
        "reason": "Chronic conditions (hypertension, diabetes, asthma) affect diagnosis and treatment.",
        "critical": True,
    },
    {
        "key": "current_medications",
        "label": "Current medications",
        "section": "Medications",
        "reason": "Current medications affect prescription choice and avoid medication discrepancies.",
        "critical": True,
    },
    {
        "key": "has_allergies",
        "label": "Known allergies",
        "section": "Allergies",
        "reason": "Allergy status is essential for patient safety and safe prescribing.",
        "critical": True,
    },
]


def is_missing_value(val: Optional[str]) -> bool:
    """Check if an answer string represents an unknown / missing / skipped answer."""
    if val is None:
        return True
    s = str(val).strip()
    if not s:
        return True
    lower = s.lower()
    if lower in ("[skipped by patient]", "not answered", "not provided", "not provided / unknown", "unknown", "[not provided]"):
        return True
    return False


def detect_missing(answered: Dict[str, str]) -> List[MissingField]:
    """
    answered: dict mapping question_key -> answer string.
    Returns list of MissingField for each required checklist item that has no substantive answer.
    """
    missing: List[MissingField] = []

    for field in REQUIRED_FIELDS:
        key = field["key"]
        val = answered.get(key)
        if is_missing_value(val):
            missing.append(
                MissingField(
                    field=key,
                    label=field["label"],
                    section=field["section"],
                    reason=field["reason"],
                    is_critical=field["critical"],
                    status="Not provided / unknown",
                )
            )

    return missing
