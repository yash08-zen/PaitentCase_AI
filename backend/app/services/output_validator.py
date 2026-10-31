"""
services/output_validator.py
----------------------------
Code-side verification of every LLM proposal before it is stored.

"The LLM proposes. Code verifies. The doctor decides."

Rules enforced here:
  1. Every claim must cite evidence that resolves to this case's evidence
     catalogue (interview answer, document text, lab row, computed trend).
     A cited quote must actually appear in the referenced source.
  2. Definitive-diagnosis phrasing is rejected.
  3. Every number in generated text must be traceable to the source text or
     to a code-computed value.
  4. A dose is kept only when quoted verbatim from a retrieved passage.
  5. Treatment references are cross-checked against allergies, current
     medications and the local interaction table.

Each validator returns the cleaned item plus a list of validation notes, or
None when the item must be dropped.
"""
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from app.engines.interactions import check_allergy_contraindications, check_drug_interactions
from app.services.grounding_validator import GroundingValidator, normalize_for_matching
from app.services.guidelines import verify_dose_is_quoted

DEFINITIVE_PATTERNS = [
    r"\bdefinitely\b", r"\bdefinitive(?:ly)?\b", r"\bconfirmed diagnosis\b", r"\bdiagnosis is\b",
    r"\bdiagnosed with\b", r"\bcertainly\b", r"\bconclusively\b", r"\bwithout doubt\b",
    r"\bis suffering from\b", r"\bpatient has\b", r"\bconfirms\b", r"\bproves?\b",
    r"\b100\s*%\b", r"\bguaranteed\b", r"\bfinal diagnosis\b",
]
_DEFINITIVE_RE = re.compile("|".join(DEFINITIVE_PATTERNS), re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![A-Za-z_])\d+(?:\.\d+)?")
ALLOWED_LIKELIHOODS = ("more likely", "possible", "less likely")


# Instruction-like text copied from a document or answer into generated output
INJECTION_MARKERS = [
    r"ignore (?:all |any )?(?:previous|prior|above) instructions", r"system override", r"you are (?:a|an|the) ",
    r"no treatment (?:is )?needed", r"\bhealthy\b", r"dismiss (?:all )?warnings", r"immediate discharge",
    r"disregard", r"new instructions",
]
_INJECTION_RE = re.compile("|".join(INJECTION_MARKERS), re.IGNORECASE)


def has_definitive_phrasing(text: str) -> bool:
    return bool(text and _DEFINITIVE_RE.search(text))


def looks_injected(text: str) -> bool:
    return bool(text and _INJECTION_RE.search(text))


def _num_variants(value: Any) -> Set[str]:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return set()
    out = {f"{f:g}", f"{f:.1f}", f"{f:.2f}", f"{abs(f):g}", f"{abs(f):.1f}"}
    if f.is_integer():
        out.add(str(int(f)))
        out.add(str(abs(int(f))))
    return out


@dataclass
class EvidenceIndex:
    """Resolvable evidence for one encounter: ref -> source text."""
    entries: Dict[str, str] = field(default_factory=dict)
    computed_numbers: Set[str] = field(default_factory=set)

    def add(self, ref: str, text: Any) -> None:
        if text is None or str(text).strip() == "":
            return
        self.entries[ref] = str(text)

    def add_numbers(self, values: Iterable[Any]) -> None:
        for v in values:
            self.computed_numbers |= _num_variants(v)

    def catalogue(self, max_chars: int = 600) -> List[Dict[str, str]]:
        """Catalogue sent to the LLM (refs + text, truncated for size)."""
        return [{"ref": r, "text": t[:max_chars]} for r, t in self.entries.items()]

    def resolve(self, ref: str, quote: str = "") -> bool:
        """True when ref exists and (if given) quote appears in its text."""
        if not ref or ref not in self.entries:
            return False
        if quote and quote.strip():
            ok, _, _ = GroundingValidator.verify_span(quote, self.entries[ref])
            return ok
        return True

    def all_text(self) -> str:
        return "\n".join(self.entries.values())

    def untraceable_numbers(self, text: str, extra_allowed: Iterable[Any] = ()) -> List[str]:
        """Numbers in text that appear neither in any source nor in computed values."""
        allowed = set(self.computed_numbers)
        for v in extra_allowed:
            allowed |= _num_variants(v)
        corpus = normalize_for_matching(self.all_text())
        bad = []
        for num in _NUMBER_RE.findall(text or ""):
            if num in allowed or any(v in allowed for v in _num_variants(num)):
                continue
            if re.search(rf"(?<![\d.]){re.escape(num)}(?![\d])", corpus):
                continue
            bad.append(num)
        return bad


def _validate_evidence_list(items: List[Dict[str, Any]], index: EvidenceIndex) -> Tuple[List[Dict[str, Any]], int]:
    kept, dropped = [], 0
    for ev in items or []:
        if not isinstance(ev, dict):
            dropped += 1
            continue
        ref = ev.get("evidence_ref") or ev.get("evidence") or ""
        quote = ev.get("quote") or ""
        finding = ev.get("finding") or ""
        if not index.resolve(ref, quote):
            dropped += 1
            continue
        if has_definitive_phrasing(finding) or looks_injected(finding) or index.untraceable_numbers(finding):
            dropped += 1
            continue
        kept.append({"finding": finding, "evidence_ref": ref, "quote": quote,
                     "source_text": index.entries[ref][:300]})
    return kept, dropped


def validate_consideration(item: Dict[str, Any], index: EvidenceIndex) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    name = (item.get("name") or "").strip()
    if not name:
        return None, ["dropped: empty name"]
    texts = [name] + list(item.get("suggested_questions_or_tests") or [])
    if any(has_definitive_phrasing(t) for t in texts):
        return None, ["dropped: definitive-diagnosis phrasing"]
    if any(looks_injected(t) for t in texts):
        return None, ["dropped: instruction-like text copied from the record"]
    bad = index.untraceable_numbers(name)
    if bad:
        return None, [f"dropped: untraceable numbers in name {bad}"]

    support, dropped_s = _validate_evidence_list(item.get("supporting_findings"), index)
    against, dropped_a = _validate_evidence_list(item.get("findings_against"), index)
    if dropped_s:
        notes.append(f"{dropped_s} supporting finding(s) removed: evidence not resolvable")
    if dropped_a:
        notes.append(f"{dropped_a} finding(s) against removed: evidence not resolvable")
    if not support:
        return None, notes + ["dropped: no resolvable supporting evidence"]

    likelihood = (item.get("likelihood") or "").strip().lower()
    if likelihood not in ALLOWED_LIKELIHOODS:
        notes.append(f"likelihood '{likelihood}' replaced with 'possible'")
        likelihood = "possible"
    suggestions = [s for s in (item.get("suggested_questions_or_tests") or [])
                   if not index.untraceable_numbers(s)]
    return {
        "name": name,
        "likelihood": likelihood,
        "supporting_findings": support,
        "findings_against": against,
        "suggested_questions_or_tests": suggestions,
        "wording_notice": "Possible consideration for clinician review - not a diagnosis.",
    }, notes


def validate_summary_sections(sections: List[Dict[str, Any]], index: EvidenceIndex) -> Tuple[List[Dict[str, Any]], List[str]]:
    kept, notes = [], []
    for sec in sections or []:
        name = sec.get("section", "")
        text = (sec.get("text") or "").strip()
        refs = [r for r in (sec.get("evidence_refs") or []) if index.resolve(r)]
        if not text:
            continue
        if not refs:
            notes.append(f"section '{name}' removed: no resolvable source reference")
            continue
        if has_definitive_phrasing(text):
            notes.append(f"section '{name}' removed: definitive-diagnosis phrasing")
            continue
        if looks_injected(text):
            notes.append(f"section '{name}' removed: instruction-like text from the record")
            continue
        bad = index.untraceable_numbers(text)
        if bad:
            notes.append(f"section '{name}' removed: untraceable numbers {bad}")
            continue
        kept.append({"section": name, "text": text, "evidence_refs": refs})
    return kept, notes


def validate_question(item: Dict[str, Any], index: EvidenceIndex) -> Optional[Dict[str, Any]]:
    q = (item.get("question") or "").strip()
    if not q or has_definitive_phrasing(q) or looks_injected(q) or index.untraceable_numbers(q):
        return None
    refs = [r for r in (item.get("evidence_refs") or []) if index.resolve(r) or r.startswith("missing:")]
    if not refs:
        return None
    return {"question": q, "reason": item.get("reason") or "", "evidence_refs": refs}


def validate_trend_sentence(sentence: str, trend: Dict[str, Any], rule_numbers: Iterable[Any] = ()) -> Tuple[bool, List[str]]:
    """Every number must be one code computed (values, delta, percent, span) or a configured threshold."""
    if not sentence or has_definitive_phrasing(sentence):
        return False, ["empty or definitive sentence"]
    allowed: Set[str] = set()
    span = trend.get("time_span_days")
    values = [trend.get("previous_value"), trend.get("current_value"), trend.get("delta"),
              trend.get("percent_change"), span, *rule_numbers]
    if span:
        values += [span // 7, span // 30, round(span / 30)]
    for v in values:
        if v is not None:
            allowed |= _num_variants(v)
    bad = [n for n in _NUMBER_RE.findall(sentence)
           if n not in allowed and not any(abs(float(n) - float(a)) < 0.051 for a in allowed)]
    return not bad, bad


def validate_treatment_summary(
    item: Dict[str, Any],
    passages: List[Dict[str, Any]],
    allergies: List[str],
    current_medications: List[str],
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    by_id = {int(p["id"]): p for p in passages}
    pid = item.get("passage_id")
    try:
        passage = by_id.get(int(pid))
    except (TypeError, ValueError):
        passage = None
    if passage is None:
        return None, ["dropped: cites a passage that was not retrieved"]

    summary = (item.get("summary") or "").strip()
    if has_definitive_phrasing(summary) or looks_injected(summary):
        return None, ["dropped: definitive or instruction-like phrasing"]
    passage_index = EvidenceIndex()
    passage_index.add(f"passage:{passage['id']}", passage["passage_text"])
    if passage_index.untraceable_numbers(summary):
        notes.append("summary removed: contained numbers not in the passage")
        summary = ""

    dose = (item.get("dose_quotation") or "").strip()
    if dose and not verify_dose_is_quoted(dose, passage["passage_text"]):
        notes.append("dose removed: not quoted verbatim from the retrieved passage")
        dose = ""

    # Cross-check every drug named in the passage/dose against the patient
    from app.services.medication_extraction import COMMON_MEDICATIONS
    mentioned = sorted({m for m in COMMON_MEDICATIONS
                        if re.search(rf"\b{re.escape(m)}\b", f"{dose} {passage['passage_text']}", re.IGNORECASE)})
    conflicts = [c["description"] for c in check_allergy_contraindications(allergies, mentioned)]
    conflicts += [c["description"] for c in check_drug_interactions(list(current_medications) + mentioned)
                  if any(m in (c.get("value_a", "") + c.get("value_b", "")) for m in mentioned)]

    return {
        "topic": item.get("topic") or passage.get("condition_or_topic"),
        "summary": summary,
        "dose_quotation": dose,
        "cautions": item.get("cautions") or "",
        "citation": {
            "passage_id": passage["id"],
            "source": passage["source"],
            "version_date": passage["version_date"],
            "section": passage["section"],
            "is_sample": passage.get("is_sample", True),
        },
        "patient_conflicts": conflicts,
        "label": "Reference information for the prescriber. Not a prescription.",
    }, notes
