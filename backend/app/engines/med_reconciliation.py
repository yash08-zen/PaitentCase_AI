"""
engines/med_reconciliation.py
-----------------------------
Deterministic medication reconciliation across documents and interview answers.

Compares the medication lists of each source (oldest dated document first,
undated documents after, interview last) and reports, per generic drug:
  - added                    : present in the latest document, absent from earlier ones
  - stopped                  : present in an earlier document, absent from the latest one
  - changed_dose             : same generic, different strength between documents
  - duplicate_brand_generic  : the same generic listed under two names at once
  - not_reported_by_patient  : documented but not mentioned in the interview
  - patient_reported_only    : mentioned in the interview but in no document

Rule-based: no LLM is involved. The brand map is a small local table and is
deliberately incomplete; unknown names are compared as written.
"""
import re
from datetime import date
from typing import Any, Dict, List, Optional

from app.engines.trend_calculator import parse_date

# Small brand -> generic table for common Indian brands. Extend locally.
BRAND_TO_GENERIC: Dict[str, str] = {
    "glycomet": "metformin",
    "glucophage": "metformin",
    "gluconorm": "metformin",
    "crocin": "paracetamol",
    "dolo": "paracetamol",
    "calpol": "paracetamol",
    "acetaminophen": "paracetamol",
    "ecosprin": "aspirin",
    "disprin": "aspirin",
    "telma": "telmisartan",
    "amlong": "amlodipine",
    "amlopres": "amlodipine",
    "stamlo": "amlodipine",
    "atorva": "atorvastatin",
    "lipitor": "atorvastatin",
    "storvas": "atorvastatin",
    "rosuvas": "rosuvastatin",
    "pan": "pantoprazole",
    "pantocid": "pantoprazole",
    "thyronorm": "levothyroxine",
    "eltroxin": "levothyroxine",
    "augmentin": "amoxicillin-clavulanate",
    "moxikind": "amoxicillin",
    "mox": "amoxicillin",
    "azithral": "azithromycin",
    "azee": "azithromycin",
    "combiflam": "ibuprofen-paracetamol",
    "voveran": "diclofenac",
    "lasix": "furosemide",
    "aldactone": "spironolactone",
    "clopilet": "clopidogrel",
    "plavix": "clopidogrel",
    "acitrom": "acenocoumarol",
    "coumadin": "warfarin",
}

_DOSE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|µg|g|ml|iu|units?)\b", re.IGNORECASE)


def to_generic(name: str) -> str:
    """Map a brand or generic name to its generic key (lowercase)."""
    clean = re.sub(r"\b(tab|tablet|cap|capsule|syp|syrup|inj|injection)\.?\b", "", (name or "").lower())
    clean = re.sub(r"[^a-z\s-]", " ", clean).strip()
    if not clean:
        return ""
    first = clean.split()[0]
    return BRAND_TO_GENERIC.get(clean, BRAND_TO_GENERIC.get(first, first))


def normalize_dose(dose: Optional[str]) -> Optional[str]:
    """Return a canonical '500 mg' style dose string, or None if none is parseable."""
    if not dose:
        return None
    m = _DOSE_RE.search(str(dose))
    if not m:
        return None
    num = float(m.group(1))
    num_s = str(int(num)) if num.is_integer() else str(num)
    unit = m.group(2).lower().replace("µg", "mcg")
    if unit.startswith("unit"):
        unit = "units"
    return f"{num_s} {unit}"


def _entries(source: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """generic -> {names, doses} for one source."""
    out: Dict[str, Dict[str, Any]] = {}
    for med in source.get("medications", []):
        name = med.get("name") if isinstance(med, dict) else str(med)
        if not name:
            continue
        generic = to_generic(name)
        if not generic:
            continue
        dose = None
        if isinstance(med, dict):
            dose = normalize_dose(med.get("dose") or med.get("dosage") or med.get("raw_line"))
        if dose is None:
            dose = normalize_dose(name)
        e = out.setdefault(generic, {"names": set(), "doses": set()})
        e["names"].add(name.strip())
        if dose:
            e["doses"].add(dose)
    return out


def reconcile_medications(
    document_sources: List[Dict[str, Any]],
    interview_medications: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    document_sources: [{"source": "doc:3", "date": "2026-05-01" | None,
                        "medications": [{"name", "dose"|"dosage"}...] | [str]}]
    interview_medications: free-text medication names the patient reported,
                           or None when the interview did not ask / answer.
    Returns a list of reconciliation items; an empty list means nothing to reconcile.
    """
    items: List[Dict[str, Any]] = []
    sources = [s for s in document_sources if s.get("medications")]

    def sort_key(s: Dict[str, Any]):
        d = parse_date(s.get("date"))
        return (d is None, d or date.min)

    sources.sort(key=sort_key)
    per_source = [(s["source"], _entries(s)) for s in sources]

    # Duplicates within a single source (brand + generic of the same drug)
    for src, entries in per_source:
        for generic, e in entries.items():
            if len(e["names"]) > 1:
                items.append({
                    "drug": generic,
                    "status": "duplicate_brand_generic",
                    "details": f"Listed more than once as {', '.join(sorted(e['names']))}.",
                    "sources": [src],
                })

    if len(per_source) >= 2:
        first_src, first = per_source[0]
        last_src, last = per_source[-1]
        for generic in sorted(set(first) | set(last)):
            if generic in last and generic not in first:
                items.append({"drug": generic, "status": "added",
                              "details": f"Present in {last_src}, absent from {first_src}.",
                              "sources": [first_src, last_src]})
            elif generic in first and generic not in last:
                items.append({"drug": generic, "status": "stopped",
                              "details": f"Present in {first_src}, absent from {last_src}.",
                              "sources": [first_src, last_src]})
            elif first[generic]["doses"] and last[generic]["doses"] and first[generic]["doses"] != last[generic]["doses"]:
                items.append({"drug": generic, "status": "changed_dose",
                              "details": f"{', '.join(sorted(first[generic]['doses']))} in {first_src} → "
                                         f"{', '.join(sorted(last[generic]['doses']))} in {last_src}.",
                              "sources": [first_src, last_src]})

    if interview_medications is not None:
        reported = {to_generic(m) for m in interview_medications if m and to_generic(m)}
        documented: Dict[str, List[str]] = {}
        for src, entries in per_source:
            for generic in entries:
                documented.setdefault(generic, []).append(src)
        for generic, srcs in sorted(documented.items()):
            if generic not in reported:
                items.append({"drug": generic, "status": "not_reported_by_patient",
                              "details": "Documented but not mentioned in the interview.",
                              "sources": srcs + ["interview:medication_details"]})
        for generic in sorted(reported - set(documented)):
            items.append({"drug": generic, "status": "patient_reported_only",
                          "details": "Reported in the interview but found in no document.",
                          "sources": ["interview:medication_details"]})

    return items
