"""
engines/red_flags.py
--------------------
Deterministic clinical red-flag and acuity urgency evaluation.
Analyzes interview responses, vital signs, and flagged laboratory data
to identify life-threatening conditions (Acute Coronary Syndrome, Acute Stroke,
Severe Sepsis, Hypoxemia, Critical Lab Derangements).
Rule-based: no LLM hallucination risk.
"""
import re
from typing import Dict, Any, List, Optional

_NEGATIONS = ("no", "not", "denies", "denied", "without", "never", "nil")


def _mentioned(text: str, term: str) -> bool:
    """True if term occurs in text and at least one occurrence is not negated
    by a negation word within the three preceding words."""
    for m in re.finditer(re.escape(term), text):
        preceding = re.findall(r"[a-z']+", text[max(0, m.start() - 40):m.start()])[-3:]
        if not any(w in _NEGATIONS for w in preceding):
            return True
    return False


def evaluate_red_flags(
    interview_answers: Dict[str, Any],
    lab_results: Optional[List[Dict[str, Any]]] = None,
    computed_scores: Optional[Dict[str, Any]] = None,
    vitals: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Evaluates clinical evidence deterministically to determine case urgency.
    Returns:
        {
            "overall_urgency": "ROUTINE" | "URGENT" | "EMERGENCY",
            "has_red_flags": bool,
            "alerts": List[Dict[str, Any]],
        }
    """
    alerts: List[Dict[str, Any]] = []

    # Flatten interview answers to lowercase string representations
    answers_text = " ".join(str(v).lower() for v in interview_answers.values() if v is not None)
    cc = str(interview_answers.get("chief_complaint", "")).lower()

    # ── 1. Acute Cardiac / Chest Pain Red Flag ──
    has_chest_pain = _mentioned(answers_text, "chest") or _mentioned(cc, "chest")
    cardiac_terms = [
        "radiat", "left arm", "jaw", "breathless", "shortness of breath",
        "sweating", "diaphoresis", "worse with activity", "crushing"
    ]
    matched_cardiac = [s for s in cardiac_terms if _mentioned(answers_text, s)]
    has_cardiac_symptoms = bool(matched_cardiac)
    if has_chest_pain and has_cardiac_symptoms:
        alerts.append({
            "code": "CARD_ACS_RED_FLAG",
            "urgency": "EMERGENCY",
            "title": "Possible Acute Coronary Syndrome (ACS)",
            "evidence": f"Chest discomfort accompanied by associated cardiac signs ({', '.join(matched_cardiac)}).",
            "action": "Immediate 12-lead ECG, troponin testing, and physician evaluation."
        })

    # ── 2. Acute Stroke / Neurological Deficit Red Flag ──
    stroke_triggers = [
        "facial droop", "face drooping", "weakness on one side", "slurred speech",
        "speech difficulty", "sudden weakness", "arm weakness", "hemiparesis",
        "weakness of face, arm or leg", "difficulty speaking"
    ]
    matched_stroke = [s for s in stroke_triggers if _mentioned(answers_text, s)]
    if matched_stroke:
        alerts.append({
            "code": "NEURO_STROKE_RED_FLAG",
            "urgency": "EMERGENCY",
            "title": "Acute Neurological Deficit / FAST Warning",
            "evidence": f"Reported sudden neurological signs: {', '.join(matched_stroke)}.",
            "action": "Immediate stroke code activation, non-contrast head CT, assess onset time window."
        })

    # ── 2b. Symptom-module red flags (complaint-driven questionnaire answers) ──
    symptom_rules = [
        ("ALLERGY_ANAPHYLAXIS_RED_FLAG", "EMERGENCY", "Possible severe allergic reaction",
         ["swelling of lips, face or throat"],
         "Immediate assessment of airway and breathing; treat as possible anaphylaxis."),
        ("GI_BLEED_RED_FLAG", "URGENT", "Possible gastrointestinal bleeding",
         ["blood in vomit or stool", "black stools"],
         "Urgent clinical review, haemodynamic check and haemoglobin."),
        ("RESP_HAEMOPTYSIS_RED_FLAG", "URGENT", "Coughing blood reported",
         ["cough with blood"],
         "Urgent clinical review and chest assessment."),
        ("SELF_HARM_RED_FLAG", "URGENT", "Thoughts of self-harm reported",
         ["thoughts of harming yourself"],
         "Same-day clinician assessment of safety; do not leave the patient without follow-up."),
    ]
    for code, urgency, title, terms, action in symptom_rules:
        hits = [t for t in terms if _mentioned(answers_text, t)]
        if hits:
            alerts.append({"code": code, "urgency": urgency, "title": title,
                           "evidence": f"Patient reported: {', '.join(hits)}.", "action": action})
    if str(interview_answers.get("breathlessness_level", "")).lower().find("even at rest") >= 0:
        alerts.append({"code": "RESP_BREATHLESS_AT_REST", "urgency": "URGENT",
                       "title": "Breathless at rest",
                       "evidence": "Patient reported breathlessness even at rest.",
                       "action": "Urgent assessment including oxygen saturation."})

    # ── 3. Critical Physiological Vitals ──
    vitals = vitals or {}
    sbp = vitals.get("systolic_bp")
    if sbp is not None and float(sbp) < 85.0:
        alerts.append({
            "code": "VITALS_SEVERE_HYPOTENSION",
            "urgency": "EMERGENCY",
            "title": "Severe Hypotension / Shock",
            "evidence": f"Systolic Blood Pressure = {sbp} mmHg (critical threshold < 85 mmHg).",
            "action": "Immediate vascular access, fluid challenge assessment, continuous hemodynamic monitoring."
        })

    spo2 = vitals.get("spo2")
    if spo2 is not None and float(spo2) < 90.0:
        alerts.append({
            "code": "VITALS_CRITICAL_HYPOXEMIA",
            "urgency": "EMERGENCY",
            "title": "Critical Hypoxemia",
            "evidence": f"Oxygen Saturation (SpO2) = {spo2}% (< 90%).",
            "action": "Supplemental oxygen, airway assessment, urgent arterial blood gas."
        })

    # ── 4. Critical Early Warning / Sepsis Scores ──
    computed_scores = computed_scores or {}
    news2 = computed_scores.get("NEWS2")
    if news2 and news2.get("status") == "calculated":
        val = news2.get("score_value", 0)
        if val >= 7.0:
            alerts.append({
                "code": "SCORE_NEWS2_CRITICAL",
                "urgency": "EMERGENCY",
                "title": f"High Clinical Risk (NEWS2 = {int(val)})",
                "evidence": f"Aggregate National Early Warning Score is {int(val)} (threshold >= 7).",
                "action": "Emergency critical care assessment and continuous vital sign telemetry."
            })
        elif val >= 5.0:
            alerts.append({
                "code": "SCORE_NEWS2_MEDIUM",
                "urgency": "URGENT",
                "title": f"Medium Clinical Risk (NEWS2 = {int(val)})",
                "evidence": f"Aggregate NEWS2 score is {int(val)}.",
                "action": "Urgent review by clinical team with critical care skills."
            })

    qsofa = computed_scores.get("qSOFA")
    if qsofa and qsofa.get("status") == "calculated":
        qval = qsofa.get("score_value", 0)
        if qval >= 2.0:
            alerts.append({
                "code": "SCORE_QSOFA_SEPSIS_RISK",
                "urgency": "URGENT",
                "title": f"High Sepsis Risk (qSOFA = {int(qval)})",
                "evidence": "qSOFA >= 2 indicates heightened risk of prolonged ICU stay or mortality.",
                "action": "Sepsis screen, serum lactate, blood cultures, broad-spectrum antimicrobial review."
            })

    # ── 5. Critical Laboratory Values ──
    lab_results = lab_results or []
    for lr in lab_results:
        flag = lr.get("flag")
        if flag in ("critical_low", "critical_high"):
            alerts.append({
                "code": f"LAB_{lr.get('normalized_test', 'TEST').upper()}_{flag.upper()}",
                "urgency": "URGENT",
                "title": f"Critical Laboratory Value: {lr.get('test_name')}",
                "evidence": f"{lr.get('test_name')} = {lr.get('value')} {lr.get('unit', '')} ({flag.replace('_', ' ')}).",
                "action": "Urgent repeat confirmation and therapeutic correction."
            })

    # Calculate overall urgency
    if any(a["urgency"] == "EMERGENCY" for a in alerts):
        overall_urgency = "EMERGENCY"
    elif any(a["urgency"] == "URGENT" for a in alerts):
        overall_urgency = "URGENT"
    else:
        overall_urgency = "ROUTINE"

    return {
        "overall_urgency": overall_urgency,
        "has_red_flags": len(alerts) > 0,
        "alert_count": len(alerts),
        "alerts": alerts,
    }

