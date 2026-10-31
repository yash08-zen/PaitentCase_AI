"""
services/llm/mock_provider.py
-----------------------------
Offline, deterministic mock provider used by all automated tests and by the
evaluation harness when no hosted key is configured.

It is NOT a model. It reads the <case_data> payload and produces schema-valid
output with simple rules:
  - extraction is a dictionary/regex stand-in (lab synonyms, the existing
    regex medication extractor, a short diagnosis keyword list);
  - considerations, summaries and questions only cite entries that exist in
    the evidence catalogue it was given.
Its results say nothing about how a real LLM performs; the eval report labels
them as mock-provider measurements.

Tests can inject adversarial output per task through `overrides`
(task -> dict, or task -> callable(payload) -> dict) and simulate an outage
with `force_unavailable`.
"""
import json
import re
from typing import Any, Callable, Dict, List, Optional, Union

from app.engines.lab_flagging import TEST_SYNONYMS
from app.services.llm.interface import BaseLLMProvider, LLMUnavailableError

_CASE_RE = re.compile(r"<case_data>\s*(.*?)\s*</case_data>", re.DOTALL)
_NUM = r"(\d+(?:\.\d+)?)"
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})\b")
_NEGATION_RE = re.compile(r"\b(no|not|denies|denied|without|negative for|nil)\b[^.\n]{0,25}$", re.IGNORECASE)

DIAGNOSIS_TERMS = [
    "type 2 diabetes mellitus", "type 2 diabetes", "diabetes mellitus", "essential hypertension",
    "hypertension", "hypothyroidism", "bronchial asthma", "asthma", "copd",
    "chronic kidney disease", "coronary artery disease", "atrial fibrillation", "heart failure",
    "community-acquired pneumonia", "pneumonia", "pulmonary tuberculosis", "tuberculosis",
    "iron deficiency anaemia", "anaemia", "anemia", "dyslipidemia",
]

UNIT_RE = r"(mg/dl|g/dl|mmol/l|meq/l|umol/l|µmol/l|g/l|u/l|iu/l|%|x10\^3/ul|x10\^9/l|/cumm|ml/min/1\.73m2|ml/min)"


def _parse_payload(user_content: str) -> Dict[str, Any]:
    m = _CASE_RE.search(user_content or "")
    if not m:
        return {}
    try:
        return json.loads(m.group(1).replace("<\\/case_data>", "</case_data>"))
    except json.JSONDecodeError:
        return {}


def mock_extract_labs(text: str) -> List[Dict[str, str]]:
    """Dictionary-driven lab row reader: '<synonym> [:] value [unit] [(ref a-b | >a | <b)]'."""
    rows: List[Dict[str, str]] = []
    taken: List[range] = []
    date_m = _DATE_RE.search(text)
    doc_date = date_m.group(1) if date_m else ""
    for syn in sorted(TEST_SYNONYMS, key=len, reverse=True):
        if len(syn) < 3 and syn not in ("hb", "k+"):
            continue
        pat = re.compile(
            rf"(?<![A-Za-z]){re.escape(syn)}(?![A-Za-z])\s*[:\-=]?\s*{_NUM}\s*{UNIT_RE}?"
            rf"(?:\s*\(\s*(?:ref(?:erence)?(?:\s*range)?)?[\s:]*(?:{_NUM}\s*[-–]\s*{_NUM}|([<>])\s*{_NUM})\s*\))?",
            re.IGNORECASE,
        )
        for m in pat.finditer(text):
            if any(m.start() in r for r in taken):
                continue
            taken.append(range(m.start(), m.end()))
            low, high = m.group(3) or "", m.group(4) or ""
            if m.group(5) == ">":
                low = m.group(6)
            elif m.group(5) == "<":
                high = m.group(6)
            rows.append({
                "test": text[m.start():m.start() + len(syn)],
                "value": m.group(1),
                "unit": m.group(2) or "",
                "ref_low": low,
                "ref_high": high,
                "date": doc_date,
                "source_span": text[m.start():m.end()],
            })
    return rows


def mock_extract_diagnoses(text: str) -> List[Dict[str, str]]:
    found: List[Dict[str, str]] = []
    lower = text.lower()
    covered: List[range] = []
    for term in DIAGNOSIS_TERMS:
        for m in re.finditer(rf"\b{re.escape(term)}\b", lower):
            if any(m.start() in r for r in covered):
                continue
            if _NEGATION_RE.search(lower[max(0, m.start() - 40):m.start()]):
                continue
            covered.append(range(m.start(), m.end()))
            span = text[m.start():m.end()]
            found.append({"name": span, "source_span": span})
    return found


def mock_extract_medications(text: str) -> List[Dict[str, str]]:
    from app.services.medication_extraction import extract_medications_from_text
    meds = []
    for m in extract_medications_from_text(text):
        name = m.get("name") or ""
        idx = text.lower().find(name.lower())
        meds.append({
            "name": text[idx:idx + len(name)] if idx >= 0 else name,
            "dose": m.get("dosage") or "",
            "frequency": "" if m.get("frequency") in (None, "Unspecified") else m["frequency"],
            "route": "",
            "duration": m.get("duration") or "",
            "source_span": text[idx:idx + len(name)] if idx >= 0 else name,
        })
    return meds


# keyword -> (consideration name, likelihood, suggested questions/tests)
CONSIDERATION_RULES = [
    (["chest pain", "chest discomfort", "chest tightness"],
     "Consider ischaemic chest pain (findings consistent with possible angina)", "possible",
     ["Ask about exertional pattern and relief with rest", "Consider ECG and troponin"]),
    (["creatinine"], "Consider reduced renal function", "possible",
     ["Consider repeat serum creatinine and urine albumin-to-creatinine ratio"]),
    (["hba1c", "glucose", "diabetes"], "Consider suboptimal glycaemic control", "possible",
     ["Consider fasting plasma glucose and HbA1c review"]),
    (["haemoglobin", "hemoglobin", "anaemia", "anemia"], "Consider anaemia work-up", "possible",
     ["Consider complete blood count with indices and iron studies"]),
    (["fever", "cough"], "Consider respiratory tract infection", "possible",
     ["Ask about sputum and duration of fever", "Consider chest examination findings"]),
]


def _cite(entry: Dict[str, str], keyword: str) -> Dict[str, str]:
    text = entry.get("text", "")
    i = text.lower().find(keyword)
    quote = text[i:i + len(keyword)] if i >= 0 else ""
    return {"finding": f"{keyword} noted in record", "evidence_ref": entry["ref"], "quote": quote}


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock LLM provider for unit and integration testing."""

    def __init__(self, model_name: str = "mock-clinical-v2"):
        self.model_name = model_name
        self.call_history: List[Dict[str, Any]] = []
        self.overrides: Dict[str, Union[Dict[str, Any], Callable[[Dict[str, Any]], Dict[str, Any]]]] = {}
        self.force_unavailable = False

    def reset(self) -> None:
        self.call_history.clear()
        self.overrides.clear()
        self.force_unavailable = False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "offline" if self.force_unavailable else "healthy",
            "provider": "mock",
            "model": self.model_name,
            "offline_mode": True,
            "available": not self.force_unavailable,
            "vision_capable": True,
        }

    async def generate(
        self,
        task: str,
        system_prompt: str,
        user_content: str,
        json_schema: Dict[str, Any],
        *,
        images: Optional[List[Dict[str, Any]]] = None,
        encounter_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        self.call_history.append({
            "task": task,
            "encounter_id": encounter_id,
            "content_len": len(user_content or ""),
            "has_images": bool(images),
            "system_prompt": system_prompt,
            "user_content": user_content,
        })
        if self.force_unavailable:
            raise LLMUnavailableError("Mock provider set to unavailable")

        payload = _parse_payload(user_content)
        override = self.overrides.get(task)
        if override is not None:
            out = override(payload) if callable(override) else json.loads(json.dumps(override))
        else:
            out = self._respond(task, payload, user_content)
        out["_usage"] = {"model": self.model_name, "input_tokens": 0, "output_tokens": 0}
        return out

    def _respond(self, task: str, payload: Dict[str, Any], raw: str) -> Dict[str, Any]:
        text = payload.get("document_text") or ""
        catalogue: List[Dict[str, str]] = payload.get("evidence_catalogue") or []

        if task == "document_classification":
            low = text.lower()
            doc_type = "other"
            if any(k in low for k in ["discharge", "hospital course", "date of admission"]):
                doc_type = "discharge_summary"
            elif any(k in low for k in ["x-ray", "mri", "ct scan", "ultrasound", "impression:"]):
                doc_type = "imaging_report"
            elif any(k in low for k in ["ref", "reference", "lab", "pathology", "blood count", "serum"]):
                doc_type = "lab_report"
            elif any(k in low for k in ["rx", "tab", "cap", "prescri", " mg"]):
                doc_type = "prescription"
            date_m = _DATE_RE.search(text)
            return {"document_type": doc_type, "issuing_facility": "", "issuing_doctor": "",
                    "document_date": date_m.group(1) if date_m else ""}

        if task == "document_extraction":
            return {
                "diagnoses": mock_extract_diagnoses(text),
                "medications": mock_extract_medications(text),
                "lab_rows": mock_extract_labs(text),
                "procedures": [],
                "dates": _DATE_RE.findall(text),
                "issuing_doctor": "",
                "issuing_facility": "",
            }

        if task == "disease_considerations":
            out = []
            for keywords, name, likelihood, suggestions in CONSIDERATION_RULES:
                support = []
                for entry in catalogue:
                    low = entry.get("text", "").lower()
                    kw = next((k for k in keywords if k in low), None)
                    if kw:
                        support.append(_cite(entry, kw))
                if support:
                    out.append({"name": name, "likelihood": likelihood,
                                "supporting_findings": support[:3], "findings_against": [],
                                "suggested_questions_or_tests": suggestions})
            return {"considerations": out[:5]}

        if task == "treatment_reference":
            passages = payload.get("passages") or []
            summaries = []
            for p in passages:
                sentences = re.split(r"(?<=\.)\s+", p.get("text", ""))
                dose = next((s for s in sentences if re.search(r"\d+\s*mg", s)), "")
                summaries.append({"topic": p.get("topic", ""), "passage_id": int(p["id"]),
                                  "summary": sentences[0] if sentences else "",
                                  "dose_quotation": dose.rstrip("."), "cautions": ""})
            return {"nothing_relevant": not summaries, "summaries": summaries}

        if task == "trend_interpretation":
            verb = {"rising": "rose", "falling": "fell"}.get(payload.get("direction"), "changed")
            span = payload.get("time_span_days")
            over = f" over {span} days" if span is not None else ""
            unit = f" {payload.get('unit')}" if payload.get("unit") else ""
            rule = payload.get("matched_rule_id") or "configured"
            return {"interpretation": (
                f"{str(payload.get('test', 'The test')).capitalize()} {verb} from "
                f"{payload.get('previous_value')} to {payload.get('current_value')}{unit}{over}, "
                f"meeting the configured {rule} criterion. Clinical correlation required.")}

        if task == "case_summary":
            by_prefix = {
                "chief_complaint": ["interview:chief_complaint"],
                "hpi": ["interview:symptom_duration", "interview:symptom_severity",
                        "interview:associated_symptoms", "interview:pain_location"],
                "pmh_psh": ["dx:", "interview:chronic_conditions_detail", "interview:surgery_details"],
                "drug_allergy": ["interview:medication_details", "interview:allergy_details", "med:"],
                "family": ["interview:family_history"],
                "prior_investigations": ["lab:"],
            }
            sections = []
            for section, prefixes in by_prefix.items():
                hits = [e for e in catalogue if any(e["ref"].startswith(p) for p in prefixes)]
                if hits:
                    sections.append({"section": section,
                                     "text": "; ".join(e["text"] for e in hits[:4]),
                                     "evidence_refs": [e["ref"] for e in hits[:4]]})
            return {"sections": sections}

        if task == "questions_to_ask":
            qs = []
            for c in payload.get("conflicts") or []:
                qs.append({"question": f"Can you clarify this point: {c.get('field', '').replace('_', ' ')}?",
                           "reason": c.get("description", ""), "evidence_refs": [c.get("ref", "")]})
            for gap in payload.get("missing") or []:
                topic = re.sub(r"^(has|is)_", "", gap).replace("_", " ")
                qs.append({"question": f"Can you tell me more about your {topic}?",
                           "reason": "Not answered in the interview (unknown, not negative).",
                           "evidence_refs": [f"missing:{gap}"]})
            return {"questions": qs[:8]}

        if task == "followup_questions":
            return {"followups": [
                {"text": "When did this problem first start?", "socrates_dimension": "onset",
                 "reason": "SOCRATES onset"},
                {"text": "What makes it better or worse?", "socrates_dimension": "exacerbating_relieving",
                 "reason": "SOCRATES exacerbating and relieving factors"},
            ]}

        if task == "handwriting_transcription":
            return {
                "transcription": "Rx: Tab Metformin 500mg 1-0-1 after food x 30 days.\n"
                                 "Tab Telmisartan 40mg 1-0-0 x 30 days.",
                "medications": [{"name": "Metformin", "dose": "500mg", "frequency": "1-0-1"},
                                {"name": "Telmisartan", "dose": "40mg", "frequency": "1-0-0"}],
                "lab_rows": [],
                "illegible_segments": 0,
            }

        return {}
