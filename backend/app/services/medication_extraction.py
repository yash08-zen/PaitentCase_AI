"""
services/medication_extraction.py
-----------------------------------
Deterministic clinical medication extraction from raw prescription OCR text.

Extracts:
  - Drug / brand / generic name
  - Dosage (strength and unit: mg, mcg, g, ml, etc.)
  - Pharmaceutical form (tablets, capsules, syrup, injection, etc.)
  - Frequency / dosing schedule (OD, BD, TID, QID, 1-0-1, etc.)
  - Duration (e.g. 5 days, 1 month, ongoing)
  - Administration instructions (e.g. after food, at bedtime)

All extractions are tagged with provenance: document_extracted_unverified.
"""
import re
from typing import List, Dict, Any, Optional

# Curated reference dictionary of common medications (brand and generic)
COMMON_MEDICATIONS = [
    # Antibiotics
    "amoxicillin", "clavulanate", "augmentin", "azithromycin", "ciprofloxacin",
    "doxycycline", "cephalexin", "metronidazole", "levofloxacin", "trimethoprim",
    "sulfamethoxazole", "bactrim", "clindamycin", "clarithromycin", "penicillin",
    "ampicillin", "ceftriaxone", "cefuroxime", "nitrofurantoin",

    # Analgesics / Antipyretics / NSAIDs
    "paracetamol", "acetaminophen", "ibuprofen", "naproxen", "aspirin",
    "tramadol", "diclofenac", "celecoxib", "meloxicam", "mefenamic acid",
    "aceclofenac", "codeine", "ketorolac",

    # Cardiovascular / Antihypertensive
    "atorvastatin", "rosuvastatin", "simvastatin", "amlodipine", "lisinopril",
    "losartan", "metoprolol", "atenolol", "hydrochlorothiazide", "telmisartan",
    "ramipril", "enalapril", "valsartan", "carvedilol", "furosemide", "spironolactone",
    "clopidogrel", "diltiazem", "verapamil",

    # Endocrine / Diabetes / Thyroid
    "metformin", "glimepiride", "gliclazide", "sitagliptin", "empagliflozin",
    "dapagliflozin", "insulin", "glipizide", "pioglitazone", "levothyroxine",
    "thyroxine", "carbimazole",

    # Gastrointestinal
    "pantoprazole", "omeprazole", "rabeprazole", "esomeprazole", "ranitidine",
    "famotidine", "ondansetron", "domperidone", "antacid", "sucralfate",

    # Respiratory / Allergy
    "cetirizine", "levocetirizine", "fexofenadine", "loratadine", "montelukast",
    "salbutamol", "albuterol", "budesonide", "fluticasone", "formoterol",

    # Neurological / Psychiatric / Other
    "gabapentin", "pregabalin", "alprazolam", "clonazepam", "escitalopram",
    "sertraline", "duloxetine", "multivitamin", "folic acid", "calcium",
    "vitamin d3", "cholecalciferol", "iron", "cyanocobalamin"
]

# Regex patterns for dosage extraction
DOSAGE_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|iu|units|meq)\b",
    re.IGNORECASE
)

# Regex patterns for pharmaceutical form
FORM_PATTERN = re.compile(
    r"\b(tablet|tablets|tab|tabs|capsule|capsules|cap|caps|syrup|syp|injection|inj|ointment|oint|drops|cream|inhaler|gel|suspension)\b",
    re.IGNORECASE
)

# Regex patterns for frequency & dosing schedule
FREQUENCY_PATTERN = re.compile(
    r"\b(once\s+daily|twice\s+daily|thrice\s+daily|three\s+times\s+daily|four\s+times\s+daily|"
    r"every\s+\d+\s+hours|as\s+needed|at\s+bedtime|morning\s+and\s+night|"
    r"1-0-1|1-1-1|1-0-0|0-0-1|0-1-0|0-1-1|1-1-0|2-0-2|"
    r"od|bd|bid|tid|qid|prn|sos|stat|qhs|qam|daily)\b",
    re.IGNORECASE
)

# Regex patterns for duration
DURATION_PATTERN = re.compile(
    r"\b(for\s+\d+\s*(?:days?|weeks?|months?)|x\s*\d+\s*(?:days?|weeks?|months?)|\d+\s*(?:days?|weeks?|months?)|ongoing|continuous)\b",
    re.IGNORECASE
)

# Regex patterns for instructions
INSTRUCTION_PATTERN = re.compile(
    r"\b(after\s+meals?|before\s+meals?|with\s+food|empty\s+stomach|at\s+night|before\s+breakfast|ac|pc)\b",
    re.IGNORECASE
)


def normalize_frequency(freq_raw: str) -> str:
    """Normalize colloquial and Latin prescription frequencies into standard English descriptions."""
    f = freq_raw.strip().lower()
    mapping = {
        "od": "Once daily",
        "once daily": "Once daily",
        "1-0-0": "Once daily (Morning)",
        "0-0-1": "Once daily (Night)",
        "bd": "Twice daily",
        "bid": "Twice daily",
        "1-0-1": "Twice daily (Morning & Night)",
        "tid": "Three times daily",
        "1-1-1": "Three times daily (Morning, Afternoon & Night)",
        "qid": "Four times daily",
        "prn": "As needed (PRN)",
        "sos": "As needed (SOS)",
        "qhs": "At bedtime",
        "at bedtime": "At bedtime",
        "stat": "Immediately (Single dose)",
        "daily": "Once daily",
    }
    return mapping.get(f, freq_raw.capitalize())


def extract_medications_from_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    Parses OCR prescription text and extracts structured medication entities.
    Returns a list of structured medication dictionaries.
    """
    if not raw_text or not raw_text.strip():
        return []

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    extracted: List[Dict[str, Any]] = []
    seen_names = set()

    # Strategy 1: Line-by-line examination (prescriptions typically have one med per line or section)
    for line in lines:
        line_lower = line.lower()

        # Look for known medication names in the line
        found_med = None
        for med in COMMON_MEDICATIONS:
            # Word boundary check
            if re.search(rf"\b{re.escape(med)}\b", line_lower):
                found_med = med.capitalize()
                break

        # Also detect generic "Tab. <Name>" or "Cap. <Name>" or "Rx: <Name>" patterns
        if not found_med:
            prefix_match = re.search(r"\b(?:tab|tablets?|cap|capsules?|syp|inj|rx)\.?\s+([A-Za-z]{3,20})\b", line, re.IGNORECASE)
            if prefix_match:
                candidate = prefix_match.group(1).capitalize()
                # Exclude common non-drug words
                if candidate.lower() not in {"take", "daily", "after", "before", "with", "food", "oral", "dose", "patient", "dr", "doctor"}:
                    found_med = candidate

        if found_med and found_med.lower() not in seen_names:
            seen_names.add(found_med.lower())

            # Extract dosage
            dosage_match = DOSAGE_PATTERN.search(line)
            dosage = dosage_match.group(0).lower() if dosage_match else None

            # Extract form
            form_match = FORM_PATTERN.search(line)
            form = form_match.group(0).capitalize() if form_match else "Tablet"

            # Extract frequency
            freq_match = FREQUENCY_PATTERN.search(line)
            frequency = normalize_frequency(freq_match.group(0)) if freq_match else "Unspecified"

            # Extract duration
            dur_match = DURATION_PATTERN.search(line)
            duration = dur_match.group(0) if dur_match else None

            # Extract instruction
            inst_match = INSTRUCTION_PATTERN.search(line)
            instruction = inst_match.group(0).capitalize() if inst_match else None

            extracted.append({
                "name": found_med,
                "dosage": dosage,
                "form": form,
                "frequency": frequency,
                "duration": duration,
                "instructions": instruction,
                "raw_line": line,
                "provenance": "document_extracted_unverified",
            })

    # Strategy 2: If no line-by-line matched, search globally across full text
    if not extracted:
        text_lower = raw_text.lower()
        for med in COMMON_MEDICATIONS:
            if re.search(rf"\b{re.escape(med)}\b", text_lower) and med.lower() not in seen_names:
                seen_names.add(med.lower())
                # Extract surrounding window for dosage
                med_pos = text_lower.find(med)
                window = raw_text[max(0, med_pos - 20):min(len(raw_text), med_pos + 60)]
                dosage_match = DOSAGE_PATTERN.search(window)
                dosage = dosage_match.group(0).lower() if dosage_match else None

                extracted.append({
                    "name": med.capitalize(),
                    "dosage": dosage,
                    "form": "Tablet",
                    "frequency": "Unspecified",
                    "duration": None,
                    "instructions": None,
                    "raw_line": window.strip(),
                    "provenance": "document_extracted_unverified",
                })

    return extracted


def extract_allergy_mentions_from_text(raw_text: str) -> List[str]:
    """
    Extracts allergy references from medical document text.
    E.g., "Allergic to Penicillin", "NKDA", "Known drug allergy: Sulfa"
    """
    if not raw_text:
        return []

    allergies = []
    text_lower = raw_text.lower()

    # Look for allergy trigger words
    allergy_patterns = [
        r"allergic\s+to\s+([A-Za-z\s,]+)(?:\.|\n|$)",
        r"allerg(?:y|ies):\s*([A-Za-z\s,]+)(?:\.|\n|$)",
        r"adverse\s+reactions?:\s*([A-Za-z\s,]+)(?:\.|\n|$)",
    ]

    for pat in allergy_patterns:
        matches = re.finditer(pat, text_lower)
        for m in matches:
            sub = m.group(1).strip()
            # Split comma separated allergens
            parts = [p.strip().capitalize() for p in re.split(r"[,;]", sub) if p.strip()]
            for p in parts:
                if len(p) > 2 and p.lower() not in {"none", "nil", "no", "denies", "nkda"}:
                    allergies.append(p)

    return list(dict.fromkeys(allergies))
