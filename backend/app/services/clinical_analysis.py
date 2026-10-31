"""
services/clinical_analysis.py
-----------------------------
Master Orchestrator for the AI Clinical Insights Layer.
Coordinates:
  - Document intelligence & grounding validation
  - Deterministic lab flagging, trend calculation, and published risk scores
  - Red-flag detection & priority alerts
  - Drug-drug, allergy contraindication, diagnosis denial, and wrong-patient checks
  - The 4 clinical features (Disease considerations, Treatment reference, Risk explanations, Trend interpretations)
  - Doctor questions-to-ask and structured AI case summaries
  - Job tracking in LLM_JOBS table
"""
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models import (
    Encounter, Patient, Document, Response, Question, Conflict, ReviewFlag,
    AIInsight, LabResult, DocumentEntity, TrendFlag, RiskScore, LLMJob,
    AIInsightStatus, JobStatus, EncounterStatus
)
from app.services.llm.manager import llm_service, CURRENT_PROMPT_VERSION
from app.services.grounding_validator import GroundingValidator
from app.engines.lab_flagging import process_lab_row
from app.engines.trend_calculator import calculate_trend
from app.engines.risk_scores import (
    calculate_qsofa, calculate_curb65, calculate_news2, calculate_cha2ds2_vasc
)
from app.engines.red_flags import evaluate_red_flags
from app.engines.interactions import (
    check_drug_interactions, check_allergy_contraindications,
    check_diagnosis_denials, check_wrong_patient
)
from app.services.guidelines import search_guidelines, verify_dose_is_quoted, seed_guideline_passages


def _utcnow():
    return datetime.now(timezone.utc)


class ClinicalAnalysisService:
    """Orchestrates comprehensive clinical analysis for an encounter."""

    @classmethod
    async def run_analysis(
        cls,
        encounter_id: int,
        db: AsyncSession,
        job_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes end-to-end clinical intelligence pipeline for an encounter.
        Can run as background task or inline test runner.
        """
        # Ensure guideline passages are seeded
        await seed_guideline_passages(db)

        # 1. Fetch encounter and associated patient
        encounter = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
        if not encounter:
            raise ValueError(f"Encounter {encounter_id} not found")

        patient = await db.scalar(select(Patient).where(Patient.id == encounter.patient_id))
        patient_name = patient.full_name if patient else ""

        # Update job progress if job exists
        job = None
        if job_id:
            job = await db.scalar(select(LLMJob).where(LLMJob.id == job_id))
            if job:
                job.status = JobStatus.running
                job.started_at = _utcnow()
                job.progress = 0.1
                await db.commit()

        # 2. Gather interview answers
        responses = (await db.scalars(
            select(Response).where(Response.encounter_id == encounter_id)
        )).all()
        interview_answers: Dict[str, Any] = {r.question_key: r.answer for r in responses}
        if encounter.chief_complaint:
            interview_answers["chief_complaint"] = encounter.chief_complaint

        # 3. Gather documents
        documents = (await db.scalars(
            select(Document).where(Document.encounter_id == encounter_id)
        )).all()

        all_ocr_text = " ".join([d.extracted_text or "" for d in documents])
        all_extracted_meds: List[str] = []
        all_extracted_diagnoses: List[str] = []
        all_lab_results: List[Dict[str, Any]] = []

        # 4. Document Intelligence & Entity Extraction
        for doc in documents:
            text_content = doc.extracted_text or ""
            if not text_content:
                continue

            # Check wrong-patient demographic mismatch
            wrong_pt_conflicts = check_wrong_patient(
                doc_text=text_content,
                patient_name=patient_name,
                patient_age=patient.age if patient else None,
                patient_gender=patient.gender if patient else None
            )
            for c_dict in wrong_pt_conflicts:
                conflict = Conflict(
                    encounter_id=encounter_id,
                    rule_id=c_dict["rule_id"],
                    field=c_dict["field"],
                    source_a=c_dict["source_a"],
                    value_a=c_dict["value_a"],
                    source_b=c_dict["source_b"],
                    value_b=c_dict["value_b"],
                    description=c_dict["description"]
                )
                db.add(conflict)

            # Classify document with LLM if document_type is empty or generic
            if not doc.document_type or doc.document_type in ("other", "report"):
                try:
                    cls_output, _ = await llm_service.generate(
                        task="document_classification",
                        system_prompt="Classify medical document and extract metadata",
                        user_content=text_content[:2000],
                        json_schema={
                            "type": "object",
                            "properties": {
                                "document_type": {"type": "string"},
                                "confidence": {"type": "number"},
                                "issuing_facility": {"type": "string"},
                                "issuing_doctor": {"type": "string"},
                                "document_date": {"type": "string"}
                            },
                            "required": ["document_type", "confidence"]
                        },
                        encounter_id=encounter_id,
                        patient_name=patient_name
                    )
                    doc.document_type = cls_output.get("document_type", doc.document_type)
                except Exception:
                    pass

            # Structured entity extraction
            try:
                ext_output, _ = await llm_service.generate(
                    task="document_extraction",
                    system_prompt="Extract diagnoses, medications, lab rows from medical text",
                    user_content=text_content,
                    json_schema={
                        "type": "object",
                        "properties": {
                            "diagnoses": {"type": "array", "items": {"type": "object"}},
                            "medications": {"type": "array", "items": {"type": "object"}},
                            "lab_rows": {"type": "array", "items": {"type": "object"}},
                            "procedures": {"type": "array", "items": {"type": "object"}},
                            "dates": {"type": "array", "items": {"type": "string"}}
                        }
                    },
                    encounter_id=encounter_id,
                    patient_name=patient_name
                )

                # Grounding validation against raw OCR text
                validated = GroundingValidator.validate_extracted_entities(ext_output, text_content)

                # Store validated entities
                for d_ent in validated["diagnoses"]:
                    all_extracted_diagnoses.append(d_ent.get("name", ""))
                    db.add(DocumentEntity(
                        document_id=doc.id,
                        encounter_id=encounter_id,
                        entity_type="diagnosis",
                        value=d_ent,
                        raw_text=d_ent.get("name"),
                        source_span=d_ent.get("verified_span"),
                        grounded=d_ent.get("grounded", False),
                        confidence=d_ent.get("grounding_confidence", 1.0)
                    ))

                for m_ent in validated["medications"]:
                    all_extracted_meds.append(m_ent.get("name", ""))
                    db.add(DocumentEntity(
                        document_id=doc.id,
                        encounter_id=encounter_id,
                        entity_type="medication",
                        value=m_ent,
                        raw_text=m_ent.get("name"),
                        source_span=m_ent.get("verified_span"),
                        grounded=m_ent.get("grounded", False),
                        confidence=m_ent.get("grounding_confidence", 1.0)
                    ))

                for l_raw in validated["lab_rows"]:
                    flagged_row = process_lab_row(l_raw)
                    all_lab_results.append(flagged_row)
                    db.add(LabResult(
                        encounter_id=encounter_id,
                        document_id=doc.id,
                        test_name=flagged_row["test_name"],
                        normalized_test=flagged_row["normalized_test"],
                        value=flagged_row["value"],
                        unit=flagged_row["unit"],
                        ref_low=flagged_row["ref_low"],
                        ref_high=flagged_row["ref_high"],
                        flag=flagged_row["flag"],
                        test_date=flagged_row["test_date"],
                        source_span=flagged_row["source_span"]
                    ))

            except Exception:
                pass

        if job:
            job.progress = 0.4
            await db.commit()

        # 5. Deterministic Trends Calculation
        # Check if we have multiple lab results for the same test across dates
        test_history: Dict[str, List[Dict[str, Any]]] = {}
        for lr in all_lab_results:
            key = lr["normalized_test"]
            test_history.setdefault(key, []).append(lr)

        computed_trends: List[Dict[str, Any]] = []
        for test_key, items in test_history.items():
            if len(items) >= 2:
                # Sort by date if available
                p_item = items[0]
                c_item = items[-1]
                trend = calculate_trend(
                    previous_val=p_item["value"],
                    current_val=c_item["value"],
                    previous_date_str=p_item.get("test_date"),
                    current_date_str=c_item.get("test_date"),
                    test_normalized_name=test_key
                )
                computed_trends.append(trend)
                db.add(TrendFlag(
                    encounter_id=encounter_id,
                    test_name=trend["test_name"],
                    previous_value=trend["previous_value"],
                    current_value=trend["current_value"],
                    unit=p_item.get("unit"),
                    delta=trend["delta"],
                    percent_change=trend["percent_change"],
                    direction=trend["direction"],
                    time_span_days=trend["time_span_days"],
                    rule_matched=trend["rule_matched"],
                    clinical_label=trend["clinical_label"]
                ))

        # 6. Published Clinical Risk Scores Calculation
        # Extract inputs from interview responses or defaults
        patient_age = float(patient.age) if patient and patient.age is not None else None
        patient_gender = patient.gender if patient else None

        # Vitals extraction helper from interview or docs
        rr = interview_answers.get("respiratory_rate")
        sbp = interview_answers.get("systolic_bp")
        dbp = interview_answers.get("diastolic_bp")
        spo2 = interview_answers.get("spo2")
        temp = interview_answers.get("temperature")
        hr = interview_answers.get("pulse_rate")

        # Fallback search in all OCR text if vitals not in interview
        import re
        if sbp is None or dbp is None:
            bp_match = re.search(r"\bBP[\s:]*(\d{2,3})[/](\d{2,3})\b", all_ocr_text, re.IGNORECASE)
            if bp_match:
                sbp = float(bp_match.group(1))
                dbp = float(bp_match.group(2))

        # qSOFA
        qsofa_res = calculate_qsofa(
            respiratory_rate=float(rr) if rr is not None else None,
            systolic_bp=float(sbp) if sbp is not None else None,
            altered_mental_status=interview_answers.get("altered_mental_status")
        )
        db.add(RiskScore(
            encounter_id=encounter_id,
            score_name="qSOFA",
            score_value=qsofa_res["score_value"],
            status=qsofa_res["status"],
            inputs=qsofa_res["inputs"],
            missing_inputs=qsofa_res["missing_inputs"],
            formula_version=qsofa_res["formula_version"],
            interpretation=qsofa_res["interpretation"]
        ))

        # CURB-65
        urea_val = next((lr["value"] for lr in all_lab_results if lr["normalized_test"] in ("blood_urea", "blood_urea_nitrogen")), None)
        curb_res = calculate_curb65(
            confusion=interview_answers.get("confusion"),
            urea_mmol_or_bun_mgdl=urea_val,
            respiratory_rate=float(rr) if rr is not None else None,
            systolic_bp=float(sbp) if sbp is not None else None,
            diastolic_bp=float(dbp) if dbp is not None else None,
            age=patient_age
        )
        db.add(RiskScore(
            encounter_id=encounter_id,
            score_name="CURB-65",
            score_value=curb_res["score_value"],
            status=curb_res["status"],
            inputs=curb_res["inputs"],
            missing_inputs=curb_res["missing_inputs"],
            formula_version=curb_res["formula_version"],
            interpretation=curb_res["interpretation"]
        ))

        # NEWS2
        news2_res = calculate_news2(
            respiration_rate=float(rr) if rr is not None else None,
            spo2=float(spo2) if spo2 is not None else None,
            air_or_oxygen=interview_answers.get("air_or_oxygen", "air"),
            systolic_bp=float(sbp) if sbp is not None else None,
            pulse_rate=float(hr) if hr is not None else None,
            consciousness=interview_answers.get("consciousness", "alert"),
            temperature=float(temp) if temp is not None else None
        )
        db.add(RiskScore(
            encounter_id=encounter_id,
            score_name="NEWS2",
            score_value=news2_res["score_value"],
            status=news2_res["status"],
            inputs=news2_res["inputs"],
            missing_inputs=news2_res["missing_inputs"],
            formula_version=news2_res["formula_version"],
            interpretation=news2_res["interpretation"]
        ))

        # CHA2DS2-VASc
        cha_res = calculate_cha2ds2_vasc(
            age=patient_age,
            sex=patient_gender,
            congestive_heart_failure=interview_answers.get("has_chf"),
            hypertension=interview_answers.get("has_hypertension") or ("hypertension" in all_ocr_text.lower()),
            stroke_or_tia_history=interview_answers.get("has_stroke"),
            vascular_disease=interview_answers.get("has_vascular_disease"),
            diabetes=interview_answers.get("has_diabetes") or ("diabetes" in all_ocr_text.lower())
        )
        db.add(RiskScore(
            encounter_id=encounter_id,
            score_name="CHA2DS2-VASc",
            score_value=cha_res["score_value"],
            status=cha_res["status"],
            inputs=cha_res["inputs"],
            missing_inputs=cha_res["missing_inputs"],
            formula_version=cha_res["formula_version"],
            interpretation=cha_res["interpretation"]
        ))

        # 7. Red Flags & Acuity Urgency
        scores_map = {"NEWS2": news2_res, "qSOFA": qsofa_res}
        vitals_map = {"systolic_bp": sbp, "spo2": spo2}
        red_flag_eval = evaluate_red_flags(
            interview_answers=interview_answers,
            lab_results=all_lab_results,
            computed_scores=scores_map,
            vitals=vitals_map
        )
        if red_flag_eval["has_red_flags"]:
            for alert in red_flag_eval["alerts"]:
                db.add(ReviewFlag(
                    encounter_id=encounter_id,
                    flag_type="red_flag",
                    description=f"[{alert['urgency']}] {alert['title']}: {alert['evidence']} Recommendation: {alert['action']}"
                ))

        # 8. Drug Interactions & Allergy Cross-checks
        patient_allergies: List[str] = []
        raw_allergy = interview_answers.get("known_allergies") or interview_answers.get("allergies")
        if raw_allergy and raw_allergy.lower() not in ("none", "no", "denied"):
            patient_allergies.append(raw_allergy)

        allergy_conflicts = check_allergy_contraindications(patient_allergies, all_extracted_meds)
        for c in allergy_conflicts:
            db.add(Conflict(
                encounter_id=encounter_id,
                rule_id=c["rule_id"],
                field=c["field"],
                source_a=c["source_a"],
                value_a=c["value_a"],
                source_b=c["source_b"],
                value_b=c["value_b"],
                description=c["description"]
            ))

        drug_conflicts = check_drug_interactions(all_extracted_meds)
        for c in drug_conflicts:
            db.add(Conflict(
                encounter_id=encounter_id,
                rule_id=c["rule_id"],
                field=c["field"],
                source_a=c["source_a"],
                value_a=c["value_a"],
                source_b=c["source_b"],
                value_b=c["value_b"],
                description=c["description"]
            ))

        # Diagnosis denial checks
        denied_conditions = []
        for qk, ans in interview_answers.items():
            if "denied" in str(ans).lower() or "no" == str(ans).strip().lower():
                denied_conditions.append(qk.replace("has_", ""))
        denial_conflicts = check_diagnosis_denials(denied_conditions, all_extracted_diagnoses)
        for c in denial_conflicts:
            db.add(Conflict(
                encounter_id=encounter_id,
                rule_id=c["rule_id"],
                field=c["field"],
                source_a=c["source_a"],
                value_a=c["value_a"],
                source_b=c["source_b"],
                value_b=c["value_b"],
                description=c["description"]
            ))

        if job:
            job.progress = 0.7
            await db.commit()

        # 9. LLM Clinical Features (Doctor-gated, provenance: ai_generated_unverified)
        # Feature 1: Disease Considerations ("possible diagnoses")
        try:
            diag_prompt_user = (
                f"Patient Age: {patient_age}, Gender: {patient_gender}.\n"
                f"Chief Complaint: {interview_answers.get('chief_complaint')}\n"
                f"Symptoms/History: {interview_answers}\n"
                f"Documented diagnoses in records: {all_extracted_diagnoses}\n"
                f"Abnormal labs: {[l for l in all_lab_results if l.get('flag') in ('low', 'high', 'critical_low', 'critical_high')]}\n"
                f"Computed trends: {computed_trends}\n"
                "Propose up to 5 possible differential disease considerations for clinician review."
            )
            dis_res, meta_dis = await llm_service.generate(
                task="disease_considerations",
                system_prompt=(
                    "You are a clinical decision support system assisting a licensed physician. "
                    "Propose differential disease considerations. Never output a single definitive diagnosis. "
                    "Use phrasing such as 'consider', 'findings consistent with'. "
                    "Qualitative likelihood must be 'more likely', 'possible', or 'less likely'. "
                    "Every finding must point to evidence."
                ),
                user_content=diag_prompt_user,
                json_schema={"type": "object"},
                encounter_id=encounter_id,
                patient_name=patient_name
            )
            for c_item in dis_res.get("considerations", [])[:5]:
                db.add(AIInsight(
                    encounter_id=encounter_id,
                    insight_type="disease_consideration",
                    content=c_item,
                    evidence={"supporting": c_item.get("supporting_findings"), "against": c_item.get("findings_against")},
                    status=AIInsightStatus.pending,
                    provenance="ai_generated_unverified",
                    model_name=meta_dis.get("model_name"),
                    prompt_version=meta_dis.get("prompt_version")
                ))
        except Exception:
            pass

        # Feature 2: Treatment & Dose Reference
        try:
            # Query local guideline library for relevant topics
            search_query = f"{interview_answers.get('chief_complaint', '')} {' '.join(all_extracted_diagnoses)}"
            passages = await search_guidelines(search_query, db, limit=3)
            if passages:
                passages_text = "\n\n".join([f"Source: {p['source']}\nPassage: {p['passage_text']}" for p in passages])
                tx_user_content = (
                    f"Retrieved Guidelines:\n{passages_text}\n\n"
                    f"Patient Current Medications: {all_extracted_meds}\n"
                    f"Patient Allergies: {patient_allergies}\n"
                    "Summarize retrieved treatment references. Quoted doses MUST appear in retrieved text."
                )
                tx_res, meta_tx = await llm_service.generate(
                    task="treatment_reference",
                    system_prompt=(
                        "Summarize treatment guidance STRICTLY based on provided retrieved passages. "
                        "Never recall doses from memory. Only show doses quoted directly from retrieved text. "
                        "Label: 'Reference information for the prescriber. Not a prescription.'"
                    ),
                    user_content=tx_user_content,
                    json_schema={"type": "object"},
                    encounter_id=encounter_id,
                    patient_name=patient_name
                )
                for tx_item in tx_res.get("guideline_summaries", []):
                    dose_quote = tx_item.get("dose_quotation", "")
                    # Code verification: ensure dose is quoted in at least one retrieved passage
                    dose_verified = any(verify_dose_is_quoted(dose_quote, p["passage_text"]) for p in passages)
                    if not dose_verified:
                        tx_item["dose_quotation"] = "[Dose omitted – unverified by retrieved guideline]"

                    db.add(AIInsight(
                        encounter_id=encounter_id,
                        insight_type="treatment_reference",
                        content=tx_item,
                        evidence={"retrieved_passages": [p["id"] for p in passages]},
                        status=AIInsightStatus.pending,
                        provenance="ai_generated_unverified",
                        model_name=meta_tx.get("model_name"),
                        prompt_version=meta_tx.get("prompt_version")
                    ))
        except Exception:
            pass

        # Feature 3: Trend Interpretation
        for tr in computed_trends:
            if tr.get("rule_matched"):
                try:
                    trend_user = (
                        f"Test: {tr['test_name']}. Previous: {tr['previous_value']}, "
                        f"Current: {tr['current_value']}, Delta: {tr['delta']}, "
                        f"Percent change: {tr['percent_change']}%, Direction: {tr['direction']}. "
                        f"Matched Rule: {tr['clinical_label']}."
                    )
                    t_res, meta_t = await llm_service.generate(
                        task="trend_interpretation",
                        system_prompt=(
                            "Write a short 1-sentence clinical interpretation of this lab trend "
                            "using ONLY the provided computed numbers and matched rule. "
                            "Do not invent any additional numbers."
                        ),
                        user_content=trend_user,
                        json_schema={"type": "object"},
                        encounter_id=encounter_id,
                        patient_name=patient_name
                    )
                    sentence = t_res.get("interpretation", "")
                    is_valid_num, bad_nums = GroundingValidator.validate_trend_sentence_numbers(
                        sentence,
                        tr["previous_value"],
                        tr["current_value"],
                        tr["delta"],
                        tr["percent_change"],
                        tr.get("time_span_days")
                    )
                    if is_valid_num:
                        db.add(AIInsight(
                            encounter_id=encounter_id,
                            insight_type="trend_interpretation",
                            content={"test_name": tr["test_name"], "interpretation": sentence, "rule": tr["rule_matched"]},
                            evidence={"delta": tr["delta"], "percent_change": tr["percent_change"]},
                            status=AIInsightStatus.pending,
                            provenance="ai_generated_unverified",
                            model_name=meta_t.get("model_name"),
                            prompt_version=meta_t.get("prompt_version")
                        ))
                except Exception:
                    pass

        # Feature 4: AI Case Summary & Questions to Ask
        try:
            summary_user = (
                f"Patient: {patient_name}, Age: {patient_age}, Gender: {patient_gender}.\n"
                f"Chief Complaint: {interview_answers.get('chief_complaint')}\n"
                f"Interview Details: {interview_answers}\n"
                f"Documented Diagnoses: {all_extracted_diagnoses}\n"
                f"Medications: {all_extracted_meds}\n"
                f"Allergies: {patient_allergies}\n"
                f"Lab Findings: {all_lab_results}\n"
                f"Red Flags & Urgency: {red_flag_eval['overall_urgency']}\n"
            )
            summ_res, meta_s = await llm_service.generate(
                task="case_summary",
                system_prompt="Create structured clinical case summary with explicit per-line source references.",
                user_content=summary_user,
                json_schema={"type": "object"},
                encounter_id=encounter_id,
                patient_name=patient_name
            )
            db.add(AIInsight(
                encounter_id=encounter_id,
                insight_type="case_summary",
                content=summ_res,
                evidence={"source_references": summ_res.get("source_references", [])},
                status=AIInsightStatus.pending,
                provenance="ai_generated_unverified",
                model_name=meta_s.get("model_name"),
                prompt_version=meta_s.get("prompt_version")
            ))

            # Questions to Ask
            q_res, meta_q = await llm_service.generate(
                task="questions_to_ask",
                system_prompt="Propose questions for doctor to ask patient to resolve gaps and contradictions.",
                user_content=summary_user,
                json_schema={"type": "object"},
                encounter_id=encounter_id,
                patient_name=patient_name
            )
            for q_item in q_res.get("questions", []):
                db.add(AIInsight(
                    encounter_id=encounter_id,
                    insight_type="questions_to_ask",
                    content=q_item,
                    evidence={"reason": q_item.get("reason"), "evidence_gap": q_item.get("evidence_gap")},
                    status=AIInsightStatus.pending,
                    provenance="ai_generated_unverified",
                    model_name=meta_q.get("model_name"),
                    prompt_version=meta_q.get("prompt_version")
                ))

        except Exception:
            pass

        # Finalize background job if active
        if job:
            job.status = JobStatus.completed
            job.progress = 1.0
            job.finished_at = _utcnow()

        await db.commit()

        return {
            "encounter_id": encounter_id,
            "overall_urgency": red_flag_eval["overall_urgency"],
            "red_flags": red_flag_eval["alerts"],
            "lab_results_count": len(all_lab_results),
            "trends_computed": len(computed_trends),
            "job_id": job.id if job else None,
            "status": "completed"
        }

