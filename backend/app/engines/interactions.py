"""
engines/interactions.py
-----------------------
Deterministic drug-drug interactions, drug-allergy contraindications,
diagnosis denial contradictions, and wrong-patient demographic mismatch checks.
Rule-based evaluation mapping to conflict rule IDs:
  - RULE-INTERACTION
  - RULE-ALLERGY-CONFLICT
  - RULE-DIAGNOSIS-DENIAL
  - RULE-WRONG-PATIENT
  - RULE-LAB-ABNORMAL
"""
import re
from typing import List, Dict, Any, Optional, Tuple


# Known drug-drug interaction pairs with clinical severity and clinical rationale
DRUG_DRUG_PAIRS: List[Dict[str, Any]] = [
    {
        "drug_a": "metformin",
        "drug_b": "contrast",
        "synonyms_a": ["metformin", "glycomet", "glucophage"],
        "synonyms_b": ["contrast", "iohexol", "iopamidol", "radiocontrast"],
        "severity": "severe",
        "description": "Metformin combined with iodinated radiocontrast carries elevated risk of contrast-induced nephropathy and lactic acidosis.",
        "action": "Withhold metformin 48h prior to and after procedure until renal function is confirmed stable."
    },
    {
        "drug_a": "warfarin",
        "drug_b": "nsaid",
        "synonyms_a": ["warfarin", "coumadin", "acitrom"],
        "synonyms_b": ["aspirin", "ibuprofen", "naproxen", "diclofenac", "nsaid", "combiflam"],
        "severity": "severe",
        "description": "Concurrent anticoagulant and NSAID therapy significantly elevates major gastrointestinal and systemic hemorrhage risk.",
        "action": "Avoid concurrent use or monitor INR closely with gastroprotection (PPI)."
    },
    {
        "drug_a": "ace_inhibitor",
        "drug_b": "spironolactone_or_potassium",
        "synonyms_a": ["enalapril", "ramipril", "lisinopril", "telmisartan", "losartan"],
        "synonyms_b": ["spironolactone", "aldactone", "potassium chloride", "potklor", "amiloride"],
        "severity": "severe",
        "description": "Co-administration of ACE inhibitor/ARB with potassium-sparing diuretics or potassium supplements can precipitate severe hyperkalemia.",
        "action": "Regularly monitor serum potassium and renal function."
    },
    {
        "drug_a": "sildenafil",
        "drug_b": "nitrate",
        "synonyms_a": ["sildenafil", "viagra", "tadalafil", "cialis"],
        "synonyms_b": ["nitroglycerin", "sorbitrate", "isosorbide", "mononitrate"],
        "severity": "severe",
        "description": "PDE-5 inhibitors potentiate the hypotensive effect of nitrates, risking severe, potentially fatal refractory hypotension.",
        "action": "Contraindicated. Do not administer nitrates within 24–48 hours of PDE-5 inhibitor use."
    },
    {
        "drug_a": "methotrexate",
        "drug_b": "cotrimoxazole",
        "synonyms_a": ["methotrexate", "folitrax"],
        "synonyms_b": ["co-trimoxazole", "bactrim", "septra", "trimethoprim"],
        "severity": "severe",
        "description": "Co-trimoxazole impairs renal clearance and additive folate antagonism of methotrexate, risking severe bone marrow suppression.",
        "action": "Avoid concomitant therapy; utilize alternative antibiotic."
    },
    {
        "drug_a": "statin",
        "drug_b": "macrolide",
        "synonyms_a": ["atorvastatin", "simvastatin", "rosuvastatin", "atorva"],
        "synonyms_b": ["clarithromycin", "erythromycin", "azithromycin"],
        "severity": "moderate",
        "description": "CYP3A4 inhibition by macrolides increases statin exposure, elevating risk of myopathy or rhabdomyolysis.",
        "action": "Temporarily pause statin during macrolide course or use non-CYP3A4 metabolized agent."
    }
]

# Known drug-allergy contraindication classes
ALLERGY_CROSS_REACTIVITY: List[Dict[str, Any]] = [
    {
        "allergen": "penicillin",
        "triggers": ["penicillin", "amoxicillin", "ampicillin", "augmentin", "moxikind", "clavum", "piperacillin"],
        "severity": "severe",
        "reaction_risk": "Anaphylaxis, angioedema, urticaria"
    },
    {
        "allergen": "sulfa",
        "triggers": ["sulfa", "sulfonamide", "co-trimoxazole", "bactrim", "septra", "sulfamethoxazole", "dapsone"],
        "severity": "severe",
        "reaction_risk": "Severe cutaneous adverse reactions (SCAR), Stevens-Johnson syndrome"
    },
    {
        "allergen": "nsaid",
        "triggers": ["aspirin", "ibuprofen", "diclofenac", "naproxen", "combiflam", "voveran", "piroxicam", "ketorolac"],
        "severity": "severe",
        "reaction_risk": "Bronchospasm, facial angioedema, anaphylactoid reaction"
    },
    {
        "allergen": "cephalosporin",
        "triggers": ["cephalexin", "cefixime", "ceftriaxone", "cefuroxime", "cefpodoxime"],
        "severity": "moderate",
        "reaction_risk": "Cross-sensitivity in beta-lactam allergic patients"
    }
]


def check_drug_interactions(medications: List[str]) -> List[Dict[str, Any]]:
    """
    Check list of medication names for known severe/moderate drug-drug interactions.
    """
    conflicts: List[Dict[str, Any]] = []
    meds_lower = [m.lower() for m in medications if m]

    for rule in DRUG_DRUG_PAIRS:
        matched_a = None
        matched_b = None

        for m in meds_lower:
            if not matched_a and any(syn in m for syn in rule["synonyms_a"]):
                matched_a = m
            if not matched_b and any(syn in m for syn in rule["synonyms_b"]):
                matched_b = m

        if matched_a and matched_b and matched_a != matched_b:
            conflicts.append({
                "rule_id": "RULE-INTERACTION",
                "field": "medication_interaction",
                "source_a": f"medication:{matched_a}",
                "value_a": matched_a,
                "source_b": f"medication:{matched_b}",
                "value_b": matched_b,
                "description": f"Potential {rule['severity'].upper()} interaction between '{matched_a}' and '{matched_b}': {rule['description']} Recommended action: {rule['action']}",
                "severity": rule["severity"]
            })

    return conflicts


def check_allergy_contraindications(
    allergies: List[str],
    medications: List[str]
) -> List[Dict[str, Any]]:
    """
    Check for contraindications between patient-reported allergies and prescribed/extracted medications.
    """
    conflicts: List[Dict[str, Any]] = []
    meds_lower = [m.lower() for m in medications if m]
    allergies_lower = [a.lower() for a in allergies if a]

    for rule in ALLERGY_CROSS_REACTIVITY:
        allergen_match = any(rule["allergen"] in a for a in allergies_lower)
        if allergen_match:
            for med in meds_lower:
                if any(trig in med for trig in rule["triggers"]):
                    conflicts.append({
                        "rule_id": "RULE-ALLERGY-CONFLICT",
                        "field": "allergy_contraindication",
                        "source_a": f"patient_reported_allergy:{rule['allergen']}",
                        "value_a": rule["allergen"],
                        "source_b": f"document_medication:{med}",
                        "value_b": med,
                        "description": f"Prescribed medication '{med}' is contraindicated in patient with reported '{rule['allergen']}' allergy. Risk: {rule['reaction_risk']}.",
                        "severity": rule["severity"]
                    })

    return conflicts


def check_diagnosis_denials(
    denied_conditions: List[str],
    documented_diagnoses: List[str]
) -> List[Dict[str, Any]]:
    """
    RULE-DIAGNOSIS-DENIAL: Patient explicitly denied a condition during intake
    that is documented in uploaded medical records.
    """
    conflicts: List[Dict[str, Any]] = []
    denied_lower = [d.lower() for d in denied_conditions if d]

    for diag in documented_diagnoses:
        d_low = diag.lower()
        for denied in denied_lower:
            # Check overlap like "diabetes", "hypertension", "asthma"
            if denied in d_low or any(k in denied and k in d_low for k in ["diabet", "hypertens", "asthma", "thyroid", "heart"]):
                conflicts.append({
                    "rule_id": "RULE-DIAGNOSIS-DENIAL",
                    "field": "medical_history_denial",
                    "source_a": f"patient_reported_denial:{denied}",
                    "value_a": f"Denied {denied}",
                    "source_b": f"document_recorded_diagnosis:{diag}",
                    "value_b": diag,
                    "description": f"Patient denied prior history of '{denied}' during intake interview, but document records '{diag}'. Clinical clarification needed.",
                    "severity": "moderate"
                })

    return conflicts


def check_wrong_patient(
    doc_text: str,
    patient_name: str,
    patient_age: Optional[int] = None,
    patient_gender: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    RULE-WRONG-PATIENT: Detect mismatch between document header demographics and registered patient.
    Prevents clinical errors from misfiled or wrong-patient records.
    """
    conflicts: List[Dict[str, Any]] = []
    if not doc_text:
        return conflicts

    # Look for name in doc
    name_match = re.search(r"(?:Patient\s*Name|Name|Pt\.?\s*Name)[\s:]+([A-Za-z\s.]+?)(?=\n|,|Age|Sex|Gender|DOB|Date|$)", doc_text, re.IGNORECASE)
    if name_match and patient_name:
        doc_pname = name_match.group(1).strip()
        # Clean titles and spaces
        clean_doc = re.sub(r"\b(mr|mrs|ms|shri|smt|dr)\.?\b", "", doc_pname, flags=re.IGNORECASE).strip().lower()
        clean_pat = re.sub(r"\b(mr|mrs|ms|shri|smt|dr)\.?\b", "", patient_name, flags=re.IGNORECASE).strip().lower()

        # If length is reasonable and no token overlap
        doc_tokens = set(clean_doc.split())
        pat_tokens = set(clean_pat.split())
        if doc_tokens and pat_tokens and not (doc_tokens & pat_tokens):
            conflicts.append({
                "rule_id": "RULE-WRONG-PATIENT",
                "field": "patient_identity_mismatch",
                "source_a": f"registered_patient_name:{patient_name}",
                "value_a": patient_name,
                "source_b": f"document_header_name:{doc_pname}",
                "value_b": doc_pname,
                "description": f"Document header displays patient name '{doc_pname}', which does not match registered patient '{patient_name}'. Possibility of misfiled or wrong-patient document.",
                "severity": "critical"
            })

    # Age check if present
    if patient_age is not None:
        age_match = re.search(r"\b(?:Age|Yrs|Years)[\s:]*(\d{1,3})\b", doc_text, re.IGNORECASE)
        if age_match:
            doc_age = int(age_match.group(1))
            if abs(doc_age - patient_age) > 10:  # Significant demographic mismatch
                conflicts.append({
                    "rule_id": "RULE-WRONG-PATIENT",
                    "field": "patient_age_mismatch",
                    "source_a": f"registered_age:{patient_age}",
                    "value_a": str(patient_age),
                    "source_b": f"document_header_age:{doc_age}",
                    "value_b": str(doc_age),
                    "description": f"Document records age {doc_age} while registered patient is {patient_age}. Significant age discrepancy.",
                    "severity": "warning"
                })

    return conflicts

