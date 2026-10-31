"""
services/followup_safety.py
---------------------------
Gate for AI-proposed follow-up interview questions (feature flag
AI_FOLLOWUPS_ENABLED). Proposed questions are shown to the patient, so a
proposal is used only if:
  - it maps to an existing question-bank question (then the bank question is
    used, unchanged), or
  - it passes the safety filter below: one short open question, no diagnosis
    or disease names, no leading or suggestive phrasing, no definitive claims.
"""
import re
from typing import Dict, List, Optional, Tuple

from app.services.output_validator import has_definitive_phrasing

DISEASE_TERMS = [
    "diabetes", "hypertension", "cancer", "tumour", "tumor", "heart attack", "infarction", "angina",
    "stroke", "tuberculosis", "tb", "covid", "pneumonia", "asthma", "copd", "hiv", "hepatitis",
    "kidney disease", "renal failure", "sepsis", "infection", "anaemia", "anemia", "migraine",
    "depression", "anxiety", "ulcer", "appendicitis", "gallstone", "thyroid", "arthritis", "dengue",
    "malaria", "typhoid", "diagnos", "disease", "syndrome", "disorder",
]
LEADING_PATTERNS = [
    r"\bdon'?t you\b", r"\bisn'?t it\b", r"\baren'?t you\b", r"\bwouldn'?t you\b", r"\bsurely\b",
    r"\bobviously\b", r"\byou (?:must|probably|likely) have\b", r"\bis it because\b",
    r"\bcould (?:this|it) be\b", r"\bdo you think you have\b", r"\bit sounds like\b",
    r"\bthis (?:means|suggests|indicates)\b", r"\bworried\b", r"\bserious\b", r"\bdangerous\b",
]
_LEADING_RE = re.compile("|".join(LEADING_PATTERNS), re.IGNORECASE)
MAX_WORDS = 20


def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z]+", (text or "").lower()) if len(t) > 2}


def map_to_bank(text: str, bank: Dict[str, str], threshold: float = 0.5) -> Optional[str]:
    """Return the key of a bank question with Jaccard token overlap >= threshold."""
    cand = _tokens(text)
    if not cand:
        return None
    best_key, best = None, 0.0
    for key, q in bank.items():
        other = _tokens(q)
        if not other:
            continue
        score = len(cand & other) / len(cand | other)
        if score > best:
            best_key, best = key, score
    return best_key if best >= threshold else None


def safety_filter(text: str) -> Tuple[bool, str]:
    q = (text or "").strip()
    if not q:
        return False, "empty"
    if not q.endswith("?") or q.count("?") != 1:
        return False, "must be exactly one question"
    if len(q.split()) > MAX_WORDS:
        return False, "too long"
    low = q.lower()
    if any(re.search(rf"\b{re.escape(t)}", low) for t in DISEASE_TERMS):
        return False, "mentions a diagnosis or disease"
    if _LEADING_RE.search(q):
        return False, "leading or suggestive phrasing"
    if has_definitive_phrasing(q):
        return False, "definitive phrasing"
    return True, "ok"


def screen_followups(proposals: List[Dict[str, str]], bank: Dict[str, str]) -> List[Dict[str, str]]:
    """Annotate each proposal with decision: 'use_bank' | 'accept' | 'reject' and reason."""
    out = []
    for p in proposals:
        text = p.get("text", "")
        mapped = map_to_bank(text, bank)
        if mapped:
            out.append({**p, "decision": "use_bank", "bank_key": mapped, "reason": "maps to question bank"})
            continue
        ok, reason = safety_filter(text)
        out.append({**p, "decision": "accept" if ok else "reject", "reason": reason})
    return out
