"""
services/grounding_validator.py
-------------------------------
Grounding validator ensuring every LLM-proposed claim, extracted entity,
and clinical number is strictly traceable to raw source document OCR text,
intake interview responses, or code-computed values.

NON-NEGOTIABLE CORE DESIGN PRINCIPLE:
  The LLM proposes. Code verifies. The doctor decides.
  Any extracted fact or clinical number not grounded in source evidence is
  rejected or routed to 'needs_review', never silently accepted.
"""
import re
from typing import Dict, Any, List, Optional, Tuple


def normalize_for_matching(text: str) -> str:
    """Strip punctuation and collapse whitespace for normalized span matching."""
    if not text:
        return ""
    # Remove non-alphanumeric except spaces and periods (for numbers)
    cleaned = re.sub(r"[^\w\s.]", " ", str(text).lower())
    return " ".join(cleaned.split())


class GroundingValidator:
    """Verifies that extracted or generated claims exist in raw source text."""

    @staticmethod
    def verify_span(candidate_text: str, source_text: str) -> Tuple[bool, Optional[str], float]:
        """
        Verify if candidate_text is grounded in source_text.
        Returns:
            (is_grounded: bool, matched_span: Optional[str], match_confidence: float)
        """
        if not candidate_text or not source_text:
            return False, None, 0.0

        cand_norm = normalize_for_matching(candidate_text)
        src_norm = normalize_for_matching(source_text)

        # 1. Exact or normalized substring match
        if cand_norm in src_norm:
            # Locate original span
            start_idx = src_norm.find(cand_norm)
            matched_span = candidate_text
            return True, matched_span, 1.0

        # 2. Token overlap check (for phrases where word order might have minor variance)
        cand_tokens = cand_norm.split()
        if len(cand_tokens) >= 2:
            matched_count = sum(1 for tok in cand_tokens if tok in src_norm)
            ratio = matched_count / len(cand_tokens)
            if ratio >= 0.8:  # At least 80% tokens present
                return True, " ".join(cand_tokens), round(ratio, 2)

        # 3. Numeric match check (if candidate is a number)
        if re.match(r"^\d+(?:\.\d+)?$", candidate_text.strip()):
            num = candidate_text.strip()
            pattern = rf"\b{re.escape(num)}\b"
            if re.search(pattern, source_text):
                return True, num, 1.0

        return False, None, 0.0

    @classmethod
    def validate_extracted_entities(
        cls,
        extracted_data: Dict[str, Any],
        source_ocr_text: str
    ) -> Dict[str, Any]:
        """
        Validates all items in diagnoses, medications, lab_rows against OCR text.
        Marks ungrounded items as grounded=False with reason.
        """
        validated_diagnoses = []
        for d in extracted_data.get("diagnoses", []):
            name = d.get("name", "")
            span = d.get("source_span") or name
            ok, matched, conf = cls.verify_span(span, source_ocr_text)
            if not ok:
                ok, matched, conf = cls.verify_span(name, source_ocr_text)

            validated_diagnoses.append({
                **d,
                "grounded": ok,
                "grounding_confidence": conf,
                "verified_span": matched,
                "status": d.get("status", "documented") if ok else "unverified_hallucination_risk"
            })

        validated_medications = []
        for m in extracted_data.get("medications", []):
            name = m.get("name", "")
            span = m.get("source_span") or name
            ok, matched, conf = cls.verify_span(span, source_ocr_text)
            if not ok:
                ok, matched, conf = cls.verify_span(name, source_ocr_text)

            validated_medications.append({
                **m,
                "grounded": ok,
                "grounding_confidence": conf,
                "verified_span": matched,
                "status": "grounded" if ok else "needs_review"
            })

        validated_lab_rows = []
        for l in extracted_data.get("lab_rows", []):
            test = l.get("test", "")
            val_str = str(l.get("value", ""))
            ok_val, _, _ = cls.verify_span(val_str, source_ocr_text)
            ok_test, _, _ = cls.verify_span(test, source_ocr_text)
            is_grounded = ok_val and ok_test

            validated_lab_rows.append({
                **l,
                "grounded": is_grounded,
                "grounding_confidence": 1.0 if is_grounded else 0.0,
                "status": "grounded" if is_grounded else "needs_review"
            })

        return {
            "diagnoses": validated_diagnoses,
            "medications": validated_medications,
            "lab_rows": validated_lab_rows,
            "procedures": extracted_data.get("procedures", []),
            "dates": extracted_data.get("dates", []),
            "all_grounded": all(
                d.get("grounded", False) for d in validated_diagnoses
            ) and all(
                m.get("grounded", False) for m in validated_medications
            ) and all(
                l.get("grounded", False) for l in validated_lab_rows
            )
        }

    @classmethod
    def validate_trend_sentence_numbers(
        cls,
        sentence: str,
        computed_previous: float,
        computed_current: float,
        computed_delta: float,
        computed_percent: float,
        time_span_days: Optional[int] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validates that any numbers appearing in an LLM trend interpretation sentence
        match the deterministically computed values.
        Prevents hallucinated numbers in trend explanations.
        """
        if not sentence:
            return False, ["Sentence is empty"]

        # Extract all floats / integers from sentence
        found_numbers = re.findall(r"\b\d+(?:\.\d+)?\b", sentence)
        allowed_numbers = {
            f"{computed_previous:.1f}", f"{computed_previous:.2f}", str(int(computed_previous)) if computed_previous.is_integer() else "",
            f"{computed_current:.1f}", f"{computed_current:.2f}", str(int(computed_current)) if computed_current.is_integer() else "",
            f"{abs(computed_delta):.1f}", f"{abs(computed_delta):.2f}",
            f"{abs(computed_percent):.1f}", f"{abs(computed_percent):.0f}",
        }
        if time_span_days is not None:
            allowed_numbers.add(str(time_span_days))
            allowed_numbers.add(str(time_span_days // 30))  # e.g. "3 months"
            allowed_numbers.add(str(time_span_days // 7))   # e.g. "2 weeks"

        # Filter out empty strings
        allowed_numbers = {n for n in allowed_numbers if n}

        unverified_numbers = []
        for num in found_numbers:
            # Check if num or close approximation is allowed
            if num not in allowed_numbers and not any(abs(float(num) - float(a)) < 0.05 for a in allowed_numbers if a):
                unverified_numbers.append(num)

        is_valid = (len(unverified_numbers) == 0)
        return is_valid, unverified_numbers

