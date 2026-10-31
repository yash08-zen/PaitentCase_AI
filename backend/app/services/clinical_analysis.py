"""
services/clinical_analysis.py
-----------------------------
Orchestrator for the AI Clinical Insights layer.

"The LLM proposes. Code verifies. The doctor decides."

Pipeline for one encounter (run as a background job, see routers/ai_analysis.py):
  1. Reset previously derived rows (decided AI insights are kept).
  2. Per document: wrong-patient and quality checks (code), LLM classification
     and extraction, grounding against the OCR text, regex cross-check.
     Only grounded facts feed the engines below.
  3. Deterministic engines: lab flagging, trends (incl. the patient's earlier
     encounters), risk scores, red flags, interaction/allergy/denial/lab rules.
  4. LLM features over an evidence catalogue built from grounded facts:
     disease considerations, treatment reference (retrieved passages only),
     trend sentences (rule-matched trends only), case summary, questions to ask.
     Every proposal passes services/output_validator.py before it is stored
     with provenance 'ai_generated_unverified'.
If the LLM is unreachable, steps 1-3 still complete and the job ends in the
'unavailable' state (reduced capability), never as a hard failure.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engines.interactions import (
    check_allergy_contraindications, check_diagnosis_denials, check_drug_interactions,
    check_lab_abnormal, check_wrong_patient,
)
from app.engines.lab_flagging import process_lab_row
from app.engines.med_reconciliation import to_generic
from app.engines.red_flags import evaluate_red_flags
from app.engines.risk_scores import (
    calculate_cha2ds2_vasc, calculate_curb65, calculate_news2, calculate_qsofa,
)
from app.engines.trend_calculator import load_trend_rules, parse_date, series_trends
from app.models import (
    AIInsight, AIInsightStatus, AuditEvent, Conflict, ConflictStatus, Document, DocumentEntity,
    Encounter, FlagStatus, JobStatus, LabResult, LLMJob, Patient, Question, Response, ReviewFlag,
    RiskScore, TrendFlag,
)
from app.services.grounding_validator import GroundingValidator
from app.services.guidelines import search_guidelines, seed_guideline_passages
from app.services.llm.interface import LLMUnavailableError
from app.services.llm.manager import llm_service
from app.services.llm.prompts import SCHEMAS, SYSTEM_PROMPTS, wrap_case_data
from app.services.medication_extraction import extract_medications_from_text
from app.services.output_validator import (
    EvidenceIndex, validate_conclusion, validate_consideration, validate_question,
    validate_summary_sections, validate_treatment_summary, validate_trend_sentence,
)

# Conflict rules owned by this pipeline (recomputed on every run)
ENGINE_RULE_IDS = ("RULE-INTERACTION", "RULE-LAB-ABNORMAL", "RULE-DIAGNOSIS-DENIAL", "RULE-WRONG-PATIENT")
NO_ANSWERS = ("no", "none", "nil", "denies", "denied", "not applicable")
YES_ANSWERS = ("yes", "y")
DIAGNOSIS_DENIAL_TERMS = ["diabetes", "hypertension", "asthma", "thyroid", "heart", "kidney"]
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|\d{1,2}-\d{1,2}-\d{4})\b")
SUMMARY_LANGUAGES = {"en": "English", "hi": "Hindi", "mr": "Marathi"}


def _utcnow():
    return datetime.now(timezone.utc)


def _blank_to_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _is_no(ans: Optional[str]) -> bool:
    return bool(ans) and ans.strip().lower() in NO_ANSWERS


def _is_yes(ans: Optional[str]) -> bool:
    return bool(ans) and ans.strip().lower().startswith(YES_ANSWERS)


def extract_vitals_from_text(text: str) -> Dict[str, float]:
    """Read vitals printed on a document. Only explicit, labelled values are taken."""
    vitals: Dict[str, float] = {}
    if not text:
        return vitals
    m = re.search(r"\bBP[\s:]*(\d{2,3})\s*/\s*(\d{2,3})\b", text, re.IGNORECASE)
    if m:
        vitals["systolic_bp"], vitals["diastolic_bp"] = float(m.group(1)), float(m.group(2))
    m = re.search(r"\b(?:RR|Resp(?:iratory)?\s*Rate)[\s:]*(\d{1,2})\b", text, re.IGNORECASE)
    if m:
        vitals["respiratory_rate"] = float(m.group(1))
    m = re.search(r"\bSpO2[\s:]*(\d{2,3})\s*%?", text, re.IGNORECASE)
    if m:
        vitals["spo2"] = float(m.group(1))
    m = re.search(r"\b(?:Pulse|HR|Heart\s*Rate)[\s:]*(\d{2,3})\b", text, re.IGNORECASE)
    if m:
        vitals["pulse_rate"] = float(m.group(1))
    m = re.search(r"\bTemp(?:erature)?[\s:]*(\d{2,3}(?:\.\d)?)\s*°?\s*([CF])?\b", text, re.IGNORECASE)
    if m:
        t = float(m.group(1))
        unit = (m.group(2) or "").upper()
        if unit == "F":
            vitals["temperature"] = round((t - 32) * 5 / 9, 1)
        elif unit == "C" or 30.0 <= t <= 45.0:
            vitals["temperature"] = t
    return vitals


class AnalysisRun:
    """State for one analysis run; keeps LLM call metadata and validation notes."""

    def __init__(self, db: AsyncSession, encounter_id: int, patient: Optional[Patient], actor: Optional[Dict[str, Any]]):
        self.db = db
        self.encounter_id = encounter_id
        self.patient = patient
        self.actor = actor or {}
        self.llm_ok = True
        self.calls: List[Dict[str, Any]] = []
        self.notes: Dict[str, Any] = {"validation": [], "llm_errors": []}

    @property
    def patient_name(self) -> str:
        return self.patient.full_name if self.patient else ""

    @property
    def identifiers(self) -> List[str]:
        p = self.patient
        return [x for x in ([p.contact_phone, p.contact_email, p.date_of_birth] if p else []) if x]

    async def llm(self, task: str, payload: Dict[str, Any], images: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
        """One LLM call; returns None (and records why) when it cannot be used."""
        if not self.llm_ok:
            return None
        try:
            out, meta = await llm_service.generate(
                task=task,
                system_prompt=SYSTEM_PROMPTS[task],
                user_content=wrap_case_data(payload),
                json_schema=SCHEMAS[task],
                images=images,
                encounter_id=self.encounter_id,
                patient_name=self.patient_name,
                patient_identifiers=self.identifiers,
            )
        except LLMUnavailableError as exc:
            self.llm_ok = False
            self.notes["llm_state"] = "llm_unavailable"
            self.notes["llm_errors"].append(f"{task}: {exc}")
            return None
        except Exception as exc:  # malformed output, refusal, provider error
            self.notes["llm_errors"].append(f"{task}: {type(exc).__name__}")
            return None
        self.calls.append(meta)
        if meta.get("is_external"):
            self.db.add(AuditEvent(
                actor_id=self.actor.get("id"),
                actor_username=self.actor.get("username"),
                actor_role=self.actor.get("role"),
                action="LLM_EXTERNAL_CALL",
                resource_type="encounter",
                resource_id=str(self.encounter_id),
                change_summary=(
                    f"De-identified {task} request sent to {meta['provider']} model {meta['model_name']} "
                    f"(prompt {meta['prompt_version']}, tokens in/out {meta['input_tokens']}/{meta['output_tokens']})"
                ),
            ))
        return out

    def meta_for(self, task: str) -> Dict[str, Any]:
        for m in reversed(self.calls):
            if m["task"] == task:
                return m
        return {"model_name": llm_service.model_for(task), "prompt_version": None}

    def add_insight(self, insight_type: str, content: Dict[str, Any], evidence: Dict[str, Any], task: str) -> None:
        meta = self.meta_for(task)
        self.db.add(AIInsight(
            encounter_id=self.encounter_id,
            insight_type=insight_type,
            content=content,
            evidence=evidence,
            status=AIInsightStatus.pending,
            provenance="ai_generated_unverified",
            model_name=meta.get("model_name"),
            prompt_version=meta.get("prompt_version"),
        ))

    def usage_summary(self) -> Dict[str, Any]:
        return {
            "provider": llm_service.mode,
            "calls": [{k: m[k] for k in ("task", "model_name", "prompt_version", "input_tokens",
                                         "output_tokens", "latency_ms", "is_external")} for m in self.calls],
            "total_input_tokens": sum(m["input_tokens"] for m in self.calls),
            "total_output_tokens": sum(m["output_tokens"] for m in self.calls),
            "total_latency_ms": round(sum(m["latency_ms"] for m in self.calls), 2),
        }


class ClinicalAnalysisService:
    """Orchestrates comprehensive clinical analysis for an encounter."""

    @classmethod
    async def run_analysis(
        cls,
        encounter_id: int,
        db: AsyncSession,
        job_id: Optional[int] = None,
        *,
        summary_language: str = "en",
        actor: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        await seed_guideline_passages(db)

        encounter = await db.get(Encounter, encounter_id)
        if not encounter:
            raise ValueError(f"Encounter {encounter_id} not found")
        patient = await db.get(Patient, encounter.patient_id)
        run = AnalysisRun(db, encounter_id, patient, actor)

        job = await db.get(LLMJob, job_id) if job_id else None

        async def progress(value: float) -> None:
            if job:
                job.progress = value
                await db.commit()

        if job:
            job.status = JobStatus.running
            job.started_at = job.started_at or _utcnow()
        await progress(0.05)

        if not await llm_service.is_available():
            run.llm_ok = False
            run.notes["llm_state"] = "llm_unavailable"

        await cls._reset_derived_rows(db, encounter_id)

        responses = (await db.scalars(select(Response).where(Response.encounter_id == encounter_id))).all()
        answers: Dict[str, str] = {r.question_key: (r.answer or "").strip() for r in responses if r.answer}
        if encounter.chief_complaint and "chief_complaint" not in answers:
            answers["chief_complaint"] = encounter.chief_complaint
        elif encounter.chief_complaint and encounter.chief_complaint.strip().lower() != answers["chief_complaint"].strip().lower():
            # Reason recorded at registration differs from the interview answer: keep both as evidence
            answers["registration_complaint"] = encounter.chief_complaint.strip()

        index = EvidenceIndex()
        for key, ans in answers.items():
            index.add(f"interview:{key}", ans)

        documents = (await db.scalars(
            select(Document).where(Document.encounter_id == encounter_id).order_by(Document.uploaded_at.asc())
        )).all()

        # ── 2. Document intelligence ──────────────────────────────────────────
        conflicts: List[Dict[str, Any]] = []
        lab_rows: List[Dict[str, Any]] = []
        grounded_meds: List[DocumentEntity] = []
        grounded_dx: List[DocumentEntity] = []
        doc_allergies: List[str] = []
        vitals: Dict[str, float] = {}
        n_docs = max(len(documents), 1)
        for i, doc in enumerate(documents):
            await cls._process_document(run, doc, index, conflicts, lab_rows, grounded_meds, grounded_dx, doc_allergies)
            for k, v in extract_vitals_from_text(doc.extracted_text or "").items():
                vitals.setdefault(k, v)
            await progress(0.05 + 0.4 * (i + 1) / n_docs)

        await db.flush()
        lab_objs = (await db.scalars(select(LabResult).where(LabResult.encounter_id == encounter_id))).all()
        for lab in lab_objs:
            rng = f"{lab.ref_low if lab.ref_low is not None else '-'}-{lab.ref_high if lab.ref_high is not None else '-'}"
            index.add(f"lab:{lab.id}", f"{lab.test_name} {lab.value:g} {lab.unit or ''} "
                                       f"(flag {lab.flag}; printed range {rng}; date {lab.test_date or 'not printed'})")
        for ent in grounded_dx:
            index.add(f"dx:{ent.id}", ent.raw_text)
        for ent in grounded_meds:
            dose = (ent.value or {}).get("dose") or ""
            index.add(f"med:{ent.id}", f"{ent.raw_text} {dose}".strip())

        # ── 3. Deterministic engines ─────────────────────────────────────────
        trends = await cls._compute_trends(db, encounter, lab_rows)
        for tr in trends:
            index.add(f"trend:{tr['test_name']}",
                      f"{tr['test_name']} {tr['previous_value']:g} -> {tr['current_value']:g} {tr.get('unit') or ''} "
                      f"(delta {tr['delta']:g}, {tr['percent_change']:g}%, {tr['direction']}, "
                      f"span {tr['time_span_days'] if tr['time_span_days'] is not None else 'unknown'} days)")
            index.add_numbers([tr["previous_value"], tr["current_value"], tr["delta"], tr["percent_change"],
                               tr["time_span_days"]])

        scores = cls._compute_scores(run, answers, vitals, lab_rows, grounded_dx)
        for s in scores.values():
            if s["status"] == "calculated":
                index.add(f"score:{s['score_name']}", f"{s['score_name']} = {s['score_value']:g} ({s['interpretation']})")
                index.add_numbers([s["score_value"]])

        red = evaluate_red_flags(
            interview_answers=answers,
            lab_results=lab_rows,
            computed_scores={"NEWS2": scores["NEWS2"], "qSOFA": scores["qSOFA"]},
            vitals={"systolic_bp": vitals.get("systolic_bp"), "spo2": vitals.get("spo2")},
        )
        for alert in red["alerts"]:
            db.add(ReviewFlag(
                encounter_id=encounter_id,
                flag_type="red_flag",
                description=f"[{alert['urgency']}] {alert['title']}: {alert['evidence']} Recommendation: {alert['action']}",
            ))

        allergies = list(doc_allergies)
        if not _is_no(answers.get("has_allergies")) and answers.get("allergy_details"):
            allergies.append(answers["allergy_details"])
        med_names = [e.raw_text for e in grounded_meds if e.raw_text]
        dx_names = [e.raw_text for e in grounded_dx if e.raw_text]
        conflicts += check_allergy_contraindications(allergies, med_names)
        conflicts += check_drug_interactions(med_names)
        conflicts += check_lab_abnormal(lab_rows)
        if _is_no(answers.get("has_chronic_conditions")):
            conflicts += check_diagnosis_denials(DIAGNOSIS_DENIAL_TERMS, dx_names)
        await cls._store_conflicts(db, encounter_id, conflicts)
        await progress(0.6)

        # ── 4. LLM features (validated) ──────────────────────────────────────
        catalogue = index.catalogue()
        patient_ctx = {"age": patient.age if patient else None, "sex": patient.gender if patient else None}

        considerations: List[Dict[str, Any]] = []
        if run.llm_ok and catalogue:
            considerations = await cls._considerations(run, index, catalogue, patient_ctx)
        await progress(0.7)
        await cls._treatment_reference(run, answers, dx_names, lab_rows, med_names, allergies)
        await progress(0.8)
        await cls._trend_sentences(run, trends)
        await cls._summary(run, index, catalogue, summary_language)
        missing = await cls._missing_required(db, answers)
        await cls._questions(run, index, catalogue, conflicts, answers)

        # Rule-based overview (always available, also when the LLM is down)
        run.notes["overview"] = {
            "reason_for_visit": answers.get("chief_complaint"),
            "urgency": red["overall_urgency"],
            "red_flags": [a["title"] for a in red["alerts"]],
            "abnormal_labs": [f"{l['test_name']} {l['value']:g} {l.get('unit') or ''} ({l['flag'].replace('_', ' ')})".replace("  ", " ")
                              for l in lab_rows if l["flag"] not in ("normal", "range_not_available")],
            "rule_conflicts": sorted({c["rule_id"] for c in conflicts}),
            "answers": len(answers),
            "documents": len(documents),
            "missing_required": missing,
        }
        await cls._conclusion(run, index, catalogue, considerations, red, missing)

        # ── Finalize ─────────────────────────────────────────────────────────
        if job:
            job.status = JobStatus.completed if run.llm_ok else JobStatus.unavailable
            job.progress = 1.0
            job.finished_at = _utcnow()
            job.usage = run.usage_summary()
            job.notes = run.notes
        await db.commit()

        return {
            "encounter_id": encounter_id,
            "overall_urgency": red["overall_urgency"],
            "red_flags": red["alerts"],
            "lab_results_count": len(lab_rows),
            "trends_computed": len(trends),
            "llm_state": "available" if run.llm_ok else "llm_unavailable",
            "usage": run.usage_summary(),
            "notes": run.notes,
            "job_id": job.id if job else None,
            "status": "completed" if run.llm_ok else "unavailable",
        }

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    async def _reset_derived_rows(db: AsyncSession, encounter_id: int) -> None:
        """Recompute everything derived; keep insights a doctor already decided."""
        await db.execute(delete(LabResult).where(LabResult.encounter_id == encounter_id))
        await db.execute(delete(TrendFlag).where(TrendFlag.encounter_id == encounter_id))
        await db.execute(delete(RiskScore).where(RiskScore.encounter_id == encounter_id))
        await db.execute(delete(DocumentEntity).where(
            DocumentEntity.encounter_id == encounter_id, DocumentEntity.provenance != "vision_fallback"))
        await db.execute(delete(AIInsight).where(
            AIInsight.encounter_id == encounter_id, AIInsight.status == AIInsightStatus.pending))
        await db.execute(delete(ReviewFlag).where(
            ReviewFlag.encounter_id == encounter_id,
            ReviewFlag.flag_type.in_(("red_flag", "document_quality")),
            ReviewFlag.status == FlagStatus.open))
        await db.execute(delete(Conflict).where(
            Conflict.encounter_id == encounter_id, Conflict.rule_id.in_(ENGINE_RULE_IDS),
            Conflict.status == ConflictStatus.open))
        await db.commit()

    @staticmethod
    async def _store_conflicts(db: AsyncSession, encounter_id: int, conflicts: List[Dict[str, Any]]) -> None:
        existing = (await db.scalars(select(Conflict).where(Conflict.encounter_id == encounter_id))).all()
        seen = {(c.rule_id, c.field, c.value_a, c.value_b) for c in existing}
        for c in conflicts:
            key = (c["rule_id"], c["field"][:100], c["value_a"], c["value_b"])
            if key in seen:
                continue
            seen.add(key)
            db.add(Conflict(
                encounter_id=encounter_id, rule_id=c["rule_id"], field=c["field"][:100],
                source_a=c["source_a"][:100], value_a=c["value_a"],
                source_b=c["source_b"][:100], value_b=c["value_b"], description=c["description"],
            ))

    @classmethod
    async def _process_document(cls, run: AnalysisRun, doc: Document, index: EvidenceIndex,
                                conflicts: List[Dict[str, Any]], lab_rows: List[Dict[str, Any]],
                                grounded_meds: List[DocumentEntity], grounded_dx: List[DocumentEntity],
                                doc_allergies: List[str]) -> None:
        db = run.db
        text = doc.extracted_text or ""
        fields = doc.extracted_fields or {}
        from_handwriting = fields.get("extraction_method") == "vision_fallback"

        # Quality checks (code)
        issues = []
        if not text.strip():
            issues.append("no readable text (blank, blurry or unreadable page)")
        elif (doc.extraction_confidence is not None and doc.extraction_confidence < 0.70 and not from_handwriting):
            issues.append(f"low OCR confidence ({doc.extraction_confidence:.2f} < 0.70)")
        if text.strip() and len(text.strip()) < 40:
            issues.append("very little text - page may be cropped or missing")
        if text.strip() and not _DATE_RE.search(text):
            issues.append("no date found on document")
        for issue in issues:
            db.add(ReviewFlag(encounter_id=run.encounter_id, flag_type="document_quality",
                              description=f"{doc.original_filename}: {issue}"))
        if not text.strip():
            return

        index.add(f"doc:{doc.id}", text)
        doc_allergies.extend(fields.get("allergies") or [])
        conflicts += check_wrong_patient(
            doc_text=text, patient_name=run.patient_name,
            patient_age=run.patient.age if run.patient else None,
            patient_gender=run.patient.gender if run.patient else None,
        )

        doc_date = None
        m = _DATE_RE.search(text)
        if m:
            doc_date = m.group(1)

        cls_out = await run.llm("document_classification", {"document_id": doc.id, "document_text": text[:4000]})
        if cls_out:
            if not doc.document_type or doc.document_type in ("other", "report"):
                doc.document_type = cls_out.get("document_type") or doc.document_type
            for etype in ("issuing_doctor", "issuing_facility"):
                val = _blank_to_none(cls_out.get(etype))
                if val:
                    ok, span, conf = GroundingValidator.verify_span(val, text)
                    db.add(DocumentEntity(document_id=doc.id, encounter_id=run.encounter_id,
                                          entity_type=etype.replace("issuing_", ""), value={"name": val},
                                          raw_text=val, source_span=span, grounded=ok, confidence=conf,
                                          review_status="grounded" if ok else "needs_review"))
            printed = _blank_to_none(cls_out.get("document_date"))
            if printed and GroundingValidator.verify_span(printed, text)[0]:
                doc_date = printed

        regex_meds = extract_medications_from_text(text)
        ext = await run.llm("document_extraction", {"document_id": doc.id, "document_text": text})
        if ext is None:
            # Fallback: deterministic regex path only
            ext = {"diagnoses": [], "lab_rows": [], "procedures": [], "dates": [],
                   "medications": [{"name": m["name"], "dose": m.get("dosage") or "",
                                    "source_span": m.get("raw_line") or m["name"]} for m in regex_meds]}
            provenance = "regex_extracted_unverified"
        else:
            provenance = "document_extracted_unverified"

        validated = GroundingValidator.validate_extracted_entities(ext, text)
        review_ok = "read_from_handwriting_verify" if from_handwriting else "grounded"

        def add_entity(etype: str, item: Dict[str, Any], name: str) -> DocumentEntity:
            grounded = bool(item.get("grounded"))
            ent = DocumentEntity(
                document_id=doc.id, encounter_id=run.encounter_id, entity_type=etype, value=item,
                raw_text=name, source_span=(item.get("verified_span") or item.get("source_span") or "")[:255],
                grounded=grounded, confidence=item.get("grounding_confidence"), provenance=provenance,
                review_status=review_ok if grounded else "needs_review",
            )
            db.add(ent)
            return ent

        for d in validated["diagnoses"]:
            ent = add_entity("diagnosis", d, d.get("name", ""))
            if ent.grounded:
                grounded_dx.append(ent)
        for med in validated["medications"]:
            ent = add_entity("medication", med, med.get("name", ""))
            if ent.grounded:
                grounded_meds.append(ent)
        for p in ext.get("procedures") or []:
            ok, span, conf = GroundingValidator.verify_span(p.get("source_span") or p.get("name", ""), text)
            add_entity("procedure", {**p, "grounded": ok, "verified_span": span, "grounding_confidence": conf},
                       p.get("name", ""))
        for d in ext.get("dates") or []:
            ok, span, conf = GroundingValidator.verify_span(d, text)
            add_entity("date", {"value": d, "grounded": ok, "verified_span": span, "grounding_confidence": conf}, d)

        for row in validated["lab_rows"]:
            if not row.get("grounded"):
                add_entity("lab_row", row, row.get("test", ""))
                continue
            raw = {
                "test": row.get("test"),
                "value": _blank_to_none(row.get("value")),
                "unit": _blank_to_none(row.get("unit")),
                "ref_low": _blank_to_none(row.get("ref_low")),
                "ref_high": _blank_to_none(row.get("ref_high")),
                "date": _blank_to_none(row.get("date")) or doc_date,
                "source_span": (row.get("source_span") or "")[:255],
            }
            # A printed reference limit must itself be in the text; otherwise drop it
            for lim in ("ref_low", "ref_high"):
                if raw[lim] is not None and not GroundingValidator.verify_span(str(raw[lim]), text)[0]:
                    run.notes["validation"].append(f"{raw['test']}: {lim} not found in document, discarded")
                    raw[lim] = None
            try:
                flagged = process_lab_row(raw)
            except (ValueError, TypeError):
                run.notes["validation"].append(f"{raw['test']}: non-numeric value, not flagged")
                continue
            flagged["document_id"] = doc.id
            lab_rows.append(flagged)
            db.add(LabResult(
                encounter_id=run.encounter_id, document_id=doc.id,
                test_name=flagged["test_name"], normalized_test=flagged["normalized_test"],
                value=flagged["value"], unit=flagged["unit"], ref_low=flagged["ref_low"],
                ref_high=flagged["ref_high"], flag=flagged["flag"], test_date=flagged["test_date"],
                source_span=flagged["source_span"],
            ))

        # Regex cross-check: disagreements go to review, nothing is silently kept
        if provenance == "document_extracted_unverified":
            llm_set = {to_generic(m.get("name", "")) for m in validated["medications"]} - {""}
            rx_set = {to_generic(m["name"]) for m in regex_meds} - {""}
            for generic, side in [(g, "llm_only") for g in sorted(llm_set - rx_set)] + \
                                 [(g, "regex_only") for g in sorted(rx_set - llm_set)]:
                db.add(DocumentEntity(
                    document_id=doc.id, encounter_id=run.encounter_id, entity_type="extraction_disagreement",
                    value={"medication": generic, "found_by": side}, raw_text=generic, grounded=False,
                    provenance="crosscheck", review_status="regex_disagreement",
                ))

    @staticmethod
    async def _compute_trends(db: AsyncSession, encounter: Encounter, lab_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Trends over this encounter's labs plus the same patient's earlier encounters."""
        earlier = (await db.scalars(
            select(LabResult).join(Encounter, LabResult.encounter_id == Encounter.id)
            .where(Encounter.patient_id == encounter.patient_id, LabResult.encounter_id != encounter.id)
        )).all()
        rows = [{"normalized_test": l.normalized_test, "value": l.value, "unit": l.unit,
                 "test_date": l.test_date, "source_span": l.source_span} for l in earlier]
        rows += lab_rows
        trends = series_trends(rows)
        for tr in trends:
            db.add(TrendFlag(
                encounter_id=encounter.id, test_name=tr["test_name"], previous_value=tr["previous_value"],
                current_value=tr["current_value"], unit=tr.get("unit"), delta=tr["delta"],
                percent_change=tr["percent_change"], direction=tr["direction"],
                time_span_days=tr["time_span_days"], rule_matched=tr["rule_matched"],
                clinical_label=tr["clinical_label"],
            ))
        return trends

    @staticmethod
    def _compute_scores(run: AnalysisRun, answers: Dict[str, str], vitals: Dict[str, float],
                        lab_rows: List[Dict[str, Any]], grounded_dx: List[DocumentEntity]) -> Dict[str, Dict[str, Any]]:
        """Scores from documented inputs only; anything missing stays None (not_calculable)."""
        def num(key: str) -> Optional[float]:
            v = answers.get(key)
            try:
                return float(v) if v not in (None, "") else vitals.get(key)
            except ValueError:
                return vitals.get(key)

        def flag_answer(key: str) -> Optional[bool]:
            if _is_yes(answers.get(key)):
                return True
            if _is_no(answers.get(key)):
                return False
            return None

        rr, sbp, dbp = num("respiratory_rate"), num("systolic_bp"), num("diastolic_bp")
        spo2, hr, temp = num("spo2"), num("pulse_rate"), num("temperature")
        ams = flag_answer("altered_mental_status")
        confusion = flag_answer("confusion")
        p = run.patient
        age = float(p.age) if p and p.age is not None else None

        # Urea: unit-aware, never assumed
        urea_val, is_bun = None, False
        for lr in lab_rows:
            unit = (lr.get("unit") or "").lower()
            if lr["normalized_test"] == "blood_urea" and unit == "mg/dl":
                urea_val, is_bun = round(lr["value"] / 6.006, 2), False  # urea mg/dL -> mmol/L
            elif lr["normalized_test"] == "blood_urea_nitrogen" and unit == "mg/dl":
                urea_val, is_bun = lr["value"], True

        # Comorbidities: documented diagnosis or interview -> True; explicit "no" -> False; else unknown
        dx_text = " ".join((e.raw_text or "").lower() for e in grounded_dx)
        reported = (answers.get("chronic_conditions_detail") or "").lower()
        denied_all = _is_no(answers.get("has_chronic_conditions"))

        def comorbidity(*terms: str) -> Optional[bool]:
            if any(t in dx_text or t in reported for t in terms):
                return True
            return False if denied_all else None

        consciousness = None
        if ams is not None:
            consciousness = "confusion" if ams else "alert"
        o2 = answers.get("air_or_oxygen")

        scores = {
            "qSOFA": calculate_qsofa(respiratory_rate=rr, systolic_bp=sbp, altered_mental_status=ams),
            "CURB-65": calculate_curb65(confusion=confusion if confusion is not None else ams,
                                        urea_mmol_or_bun_mgdl=urea_val, respiratory_rate=rr,
                                        systolic_bp=sbp, diastolic_bp=dbp, age=age, is_bun=is_bun),
            "NEWS2": calculate_news2(respiration_rate=rr, spo2=spo2, air_or_oxygen=o2, systolic_bp=sbp,
                                     pulse_rate=hr, consciousness=consciousness, temperature=temp),
            "CHA2DS2-VASc": calculate_cha2ds2_vasc(
                age=age, sex=(p.gender if p and p.gender else None),
                congestive_heart_failure=comorbidity("heart failure", "chf"),
                hypertension=comorbidity("hypertension"),
                stroke_or_tia_history=comorbidity("stroke", "tia", "transient ischaemic"),
                vascular_disease=comorbidity("coronary artery disease", "myocardial infarction", "peripheral arterial"),
                diabetes=comorbidity("diabetes"),
            ),
        }
        for name, res in scores.items():
            run.db.add(RiskScore(
                encounter_id=run.encounter_id, score_name=name, score_value=res["score_value"],
                status=res["status"], inputs=res["inputs"], missing_inputs=res["missing_inputs"],
                formula_version=res["formula_version"], interpretation=res["interpretation"],
            ))
        return scores

    @staticmethod
    async def _considerations(run: AnalysisRun, index: EvidenceIndex, catalogue: List[Dict[str, str]],
                              patient_ctx: Dict[str, Any]) -> None:
        out = await run.llm("disease_considerations", {"patient": patient_ctx, "evidence_catalogue": catalogue})
        kept: List[Dict[str, Any]] = []
        if not out:
            return kept
        for item in (out.get("considerations") or [])[:5]:
            cleaned, notes = validate_consideration(item, index)
            run.notes["validation"] += [f"consideration '{item.get('name', '')}': {n}" for n in notes]
            if cleaned:
                kept.append({"name": cleaned["name"], "likelihood": cleaned["likelihood"]})
                run.add_insight("disease_consideration", cleaned, {
                    "supporting": cleaned["supporting_findings"], "against": cleaned["findings_against"],
                }, "disease_considerations")
        return kept

    @staticmethod
    async def _treatment_reference(run: AnalysisRun, answers: Dict[str, str], dx_names: List[str],
                                   lab_rows: List[Dict[str, Any]], med_names: List[str], allergies: List[str]) -> None:
        query = " ".join([answers.get("chief_complaint", "")] + dx_names +
                         [l["test_name"] for l in lab_rows if l["flag"] not in ("normal", "range_not_available")])
        passages = await search_guidelines(query, run.db, limit=3)
        if not passages:
            run.notes["treatment_reference"] = "No relevant guideline passage was retrieved; nothing generated."
            return
        if not run.llm_ok:
            run.notes["treatment_reference"] = "Guideline passages retrieved, but the LLM is unavailable."
            return
        out = await run.llm("treatment_reference", {
            "passages": [{"id": p["id"], "topic": p["condition_or_topic"], "source": p["source"],
                          "section": p["section"], "text": p["passage_text"]} for p in passages],
            "current_medications": med_names,
            "allergies": allergies,
        })
        if not out:
            return
        if out.get("nothing_relevant") or not out.get("summaries"):
            run.notes["treatment_reference"] = "Retrieved passages were not relevant; nothing generated."
            return
        kept = 0
        for item in out["summaries"]:
            cleaned, notes = validate_treatment_summary(item, passages, allergies, med_names)
            run.notes["validation"] += [f"treatment reference: {n}" for n in notes]
            if cleaned:
                kept += 1
                run.add_insight("treatment_reference", cleaned,
                                {"retrieved_passages": [p["id"] for p in passages],
                                 "cited_passage": cleaned["citation"]["passage_id"]}, "treatment_reference")
        if not kept:
            run.notes["treatment_reference"] = "No summary survived citation checks; nothing shown."

    @staticmethod
    async def _trend_sentences(run: AnalysisRun, trends: List[Dict[str, Any]]) -> None:
        rules = load_trend_rules().get("rules", {})
        for tr in trends:
            if not tr.get("rule_matched") or not run.llm_ok:
                continue  # without a matched rule the UI shows values and direction only
            criterion = next((c for c in rules.get(tr["test_name"], {}).get("criteria", [])
                              if c.get("id") == tr["rule_matched"]), {})
            rule_numbers = [criterion.get(k) for k in ("min_absolute_change", "min_percent_change", "time_window_days")
                            if criterion.get(k) is not None]
            out = await run.llm("trend_interpretation", {
                "test": tr["test_name"], "previous_value": tr["previous_value"], "current_value": tr["current_value"],
                "unit": tr.get("unit"), "delta": tr["delta"], "percent_change": tr["percent_change"],
                "direction": tr["direction"], "time_span_days": tr["time_span_days"],
                "matched_rule_id": tr["rule_matched"], "matched_rule_label": tr["clinical_label"],
            })
            sentence = (out or {}).get("interpretation", "")
            ok, bad = validate_trend_sentence(sentence, tr, rule_numbers)
            if not out:
                continue
            if not ok:
                run.notes["validation"].append(f"trend sentence for {tr['test_name']} rejected: {bad}")
                continue
            run.add_insight("trend_interpretation",
                            {"test_name": tr["test_name"], "interpretation": sentence, "rule": tr["rule_matched"]},
                            {"computed": {k: tr[k] for k in ("previous_value", "current_value", "delta",
                                                              "percent_change", "time_span_days")},
                             "rule_label": tr["clinical_label"]}, "trend_interpretation")

    @staticmethod
    async def _summary(run: AnalysisRun, index: EvidenceIndex, catalogue: List[Dict[str, str]], language: str) -> None:
        if not run.llm_ok or not catalogue:
            return
        lang = language if language in SUMMARY_LANGUAGES else "en"
        if lang != "en" and llm_service.mode != "hosted":
            run.notes["summary_language"] = "Hindi/Marathi summaries need hosted mode; English used."
            lang = "en"
        out = await run.llm("case_summary", {"evidence_catalogue": catalogue,
                                             "output_language": SUMMARY_LANGUAGES[lang]})
        if not out:
            return
        sections, notes = validate_summary_sections(out.get("sections") or [], index)
        run.notes["validation"] += [f"summary: {n}" for n in notes]
        if sections:
            run.add_insight("case_summary", {"sections": sections, "language": lang},
                            {"source_references": [{"section": s["section"], "refs": s["evidence_refs"]} for s in sections]},
                            "case_summary")

    @staticmethod
    async def _questions(run: AnalysisRun, index: EvidenceIndex, catalogue: List[Dict[str, str]],
                         conflicts: List[Dict[str, Any]], answers: Dict[str, str]) -> None:
        if not run.llm_ok:
            return
        missing = await ClinicalAnalysisService._missing_required(run.db, answers)
        payload_conflicts = [{"field": c["field"], "description": c["description"],
                              "ref": f"conflict:{i}"} for i, c in enumerate(conflicts[:8])]
        out = await run.llm("questions_to_ask", {"evidence_catalogue": catalogue,
                                                 "conflicts": payload_conflicts, "missing": missing})
        if not out:
            return
        # Conflict refs point at rule sources, so expose them as resolvable evidence
        for c in payload_conflicts:
            index.add(c["ref"], c["description"])
        for item in out.get("questions") or []:
            cleaned = validate_question(item, index)
            if cleaned:
                run.add_insight("questions_to_ask", cleaned,
                                {"reason": cleaned["reason"], "refs": cleaned["evidence_refs"]}, "questions_to_ask")
            else:
                run.notes["validation"].append("a question to ask was dropped: no resolvable evidence")

    @staticmethod
    async def _missing_required(db: AsyncSession, answers: Dict[str, str]) -> List[str]:
        required = (await db.scalars(select(Question.key).where(
            Question.is_required.is_(True), ~Question.key.startswith("ai_followup_")))).all()
        return [k for k in required if k not in answers][:6]

    @staticmethod
    async def _conclusion(run: AnalysisRun, index: EvidenceIndex, catalogue: List[Dict[str, str]],
                          considerations: List[Dict[str, Any]], red: Dict[str, Any], missing: List[str]) -> None:
        """Analyzed Conclusion from the patient's inputs (AI-written, code-verified, doctor-gated)."""
        if not run.llm_ok or not catalogue:
            return
        out = await run.llm("analyzed_conclusion", {
            "evidence_catalogue": catalogue,
            "possible_considerations": considerations,
            "urgency": red["overall_urgency"],
            "red_flags": [a["title"] for a in red["alerts"]],
            "missing": missing,
        })
        if not out:
            return
        cleaned, notes = validate_conclusion(out, index)
        run.notes["validation"] += [f"analyzed conclusion: {n}" for n in notes]
        if not cleaned:
            return
        cleaned.update({
            "possible_considerations": considerations,  # validated list, not re-generated
            "urgency": red["overall_urgency"],
            "red_flags": [a["title"] for a in red["alerts"]],
        })
        run.add_insight("analyzed_conclusion", cleaned,
                        {"key_findings": cleaned["key_findings"]}, "analyzed_conclusion")
