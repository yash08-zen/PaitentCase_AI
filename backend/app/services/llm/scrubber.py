"""
services/llm/scrubber.py
------------------------
De-identification utility for sanitizing clinical text before sending to hosted LLMs.
Strips patient name, phone, Aadhaar / ABHA patterns, addresses, emails, and MRN/UHID.
Maintains a local re-identification dictionary for deterministic restoration.
"""
import re
from collections import defaultdict
from typing import Tuple, Dict, Optional, List


# Regex patterns for clinical identifier sanitization
AADHAAR_PATTERN = re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b")
ABHA_PATTERN = re.compile(r"\b\d{2}-\d{4}-\d{4}-\d{4}\b|[a-zA-Z0-9._%+-]+@abdm\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b(?:\+91[\s-]?)?[6-9]\d{9}\b|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PIN_CODE_PATTERN = re.compile(r"\b(?:Pin|PIN|Pincode|Pin Code)[\s:]*([1-9][0-9]{5})\b")
MRN_PATTERN = re.compile(r"\b(?:MRN|UHID|PID|Patient\s*ID|Reg\.?\s*No\.?)[\s:]*([A-Za-z0-9/-]+)", re.IGNORECASE)
ADDRESS_PATTERN = re.compile(r"\b(?:Address|Addr\.?|Residence|R/o)[\s:]+([^\n]+)", re.IGNORECASE)
NAME_HEADER_PATTERN = re.compile(r"(?:Patient\s*Name|Name|Pt\.?\s*Name)[\s:]+([A-Za-z\s.]+?)(?=\n|,|Age|Sex|Gender|DOB|Date|$)", re.IGNORECASE)


class TextScrubber:
    """Sanitizes text by replacing direct patient identifiers with placeholder tokens."""

    def __init__(self, known_patient_name: Optional[str] = None, known_identifiers: Optional[List[str]] = None):
        self.known_patient_name = known_patient_name
        self.known_identifiers = known_identifiers or []

    def scrub(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        De-identify text.
        Returns:
            sanitized_text (str): Scrubbed text with tokens like [PATIENT_NAME_1]
            token_map (Dict[str, str]): Token to original text mapping for re-attachment
        """
        if not text:
            return "", {}

        token_map: Dict[str, str] = {}
        counter = defaultdict(int)

        def get_token(category: str, original: str) -> str:
            # Check if original already mapped
            for t, orig in token_map.items():
                if orig.strip().lower() == original.strip().lower():
                    return t
            counter[category] += 1
            token = f"[{category.upper()}_{counter[category]}]"
            token_map[token] = original.strip()
            return token

        scrubbed = text

        # 1. Scrub known patient name if supplied
        if self.known_patient_name and len(self.known_patient_name.strip()) > 2:
            name = self.known_patient_name.strip()
            tok = get_token("patient_name", name)
            scrubbed = re.sub(re.escape(name), tok, scrubbed, flags=re.IGNORECASE)

        # 2. Scrub known identifiers
        for ident in self.known_identifiers:
            if ident and len(ident.strip()) > 2:
                tok = get_token("patient_id", ident.strip())
                scrubbed = re.sub(re.escape(ident.strip()), tok, scrubbed, flags=re.IGNORECASE)

        # 3. Aadhaar
        def sub_aadhaar(m):
            return get_token("aadhaar", m.group(0))
        scrubbed = AADHAAR_PATTERN.sub(sub_aadhaar, scrubbed)

        # 4. ABHA
        def sub_abha(m):
            return get_token("abha", m.group(0))
        scrubbed = ABHA_PATTERN.sub(sub_abha, scrubbed)

        # 5. Email
        def sub_email(m):
            return get_token("email", m.group(0))
        scrubbed = EMAIL_PATTERN.sub(sub_email, scrubbed)

        # 6. Phone
        def sub_phone(m):
            return get_token("phone", m.group(0))
        scrubbed = PHONE_PATTERN.sub(sub_phone, scrubbed)

        # 7. MRN / UHID
        def sub_mrn(m):
            full = m.group(0)
            val = m.group(1)
            tok = get_token("mrn", val)
            return full.replace(val, tok)
        scrubbed = MRN_PATTERN.sub(sub_mrn, scrubbed)

        # 8. Name header pattern in clinical text
        def sub_name_hdr(m):
            full = m.group(0)
            raw_name = m.group(1).strip()
            if raw_name and len(raw_name) > 2 and not raw_name.lower().startswith("[patient"):
                tok = get_token("patient_name", raw_name)
                return full.replace(raw_name, tok)
            return full
        scrubbed = NAME_HEADER_PATTERN.sub(sub_name_hdr, scrubbed)

        # 9. Address lines
        def sub_addr(m):
            full = m.group(0)
            addr = m.group(1).strip()
            if addr and not addr.startswith("["):
                return full.replace(addr, get_token("address", addr))
            return full
        scrubbed = ADDRESS_PATTERN.sub(sub_addr, scrubbed)

        # 10. PIN codes
        def sub_pin(m):
            full = m.group(0)
            code = m.group(1)
            tok = get_token("pin", code)
            return full.replace(code, tok)
        scrubbed = PIN_CODE_PATTERN.sub(sub_pin, scrubbed)

        return scrubbed, token_map

    @staticmethod
    def reattach(scrubbed_text: str, token_map: Dict[str, str]) -> str:
        """Restores de-identified tokens back to original values."""
        if not scrubbed_text or not token_map:
            return scrubbed_text
        result = scrubbed_text
        for token, original in token_map.items():
            result = result.replace(token, original)
        return result
