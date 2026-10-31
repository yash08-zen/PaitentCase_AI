"""
services/llm/mock_provider.py
-----------------------------
Offline deterministic mock provider for testing and air-gapped evaluation.
Returns schema-valid clinical fixtures tailored to the requested task and input content.
"""
from typing import Dict, Any, Optional, List
import re
from app.services.llm.interface import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock LLM provider for unit and integration testing."""

    def __init__(self, model_name: str = "mock-clinical-v1"):
        self.model_name = model_name
        self.call_history: List[Dict[str, Any]] = []

    async def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": "mock",
            "model": self.model_name,
            "offline_mode": True,
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
            "content_len": len(user_content),
            "has_images": bool(images),
        })

        content_lower = user_content.lower()

        # ── 1. Document classification ──
        if task == "document_classification":
            doc_type = "prescription"
            if any(k in content_lower for k in ["lab", "serum", "haemoglobin", "creatinine", "test report", "pathology", "blood"]):
                doc_type = "lab_report"
            elif any(k in content_lower for k in ["discharge", "admission", "hospital course", "ipd"]):
                doc_type = "discharge_summary"
            elif any(k in content_lower for k in ["x-ray", "mri", "ct scan", "ultrasound", "imaging"]):
                doc_type = "imaging_report"

            return {
                "document_type": doc_type,
                "confidence": 0.96,
                "issuing_facility": "Metropolitan Health Services",
                "issuing_doctor": "Dr. R. K. Mehta, MD",
                "document_date": "2026-05-15",
                "notes": "Verified high clarity document text"
            }

        # ── 2. Type-specific document extraction ──
        if task == "document_extraction":
            # Extract grounded items matching text
            diagnoses = []
            if "type 2 diabetes" in content_lower or "diabetes" in content_lower:
                diagnoses.append({
                    "name": "Type 2 Diabetes Mellitus",
                    "source_span": "Type 2 Diabetes" if "Type 2 Diabetes" in user_content else "diabetes",
                    "status": "documented"
                })
            if "hypertension" in content_lower:
                diagnoses.append({
                    "name": "Essential Hypertension",
                    "source_span": "Hypertension" if "Hypertension" in user_content else "hypertension",
                    "status": "documented"
                })

            medications = []
            if "metformin" in content_lower:
                medications.append({
                    "name": "Metformin",
                    "dose": "500 mg",
                    "frequency": "twice daily",
                    "route": "oral",
                    "duration": "ongoing",
                    "source_span": "Metformin 500mg" if "Metformin 500mg" in user_content else "metformin"
                })
            if "atorvastatin" in content_lower:
                medications.append({
                    "name": "Atorvastatin",
                    "dose": "20 mg",
                    "frequency": "once daily at bedtime",
                    "route": "oral",
                    "duration": "ongoing",
                    "source_span": "Atorvastatin 20mg" if "Atorvastatin 20mg" in user_content else "atorvastatin"
                })
            if "amoxicillin" in content_lower:
                medications.append({
                    "name": "Amoxicillin",
                    "dose": "500 mg",
                    "frequency": "TDS",
                    "route": "oral",
                    "duration": "5 days",
                    "source_span": "Amoxicillin" if "Amoxicillin" in user_content else "amoxicillin"
                })

            lab_rows = []
            if "creatinine" in content_lower:
                # Find number near creatinine
                match = re.search(r"creatinine[^\d]*(\d+(?:\.\d+)?)", content_lower)
                val = float(match.group(1)) if match else 1.4
                lab_rows.append({
                    "test": "Serum Creatinine",
                    "normalized_test": "creatinine",
                    "value": val,
                    "unit": "mg/dL",
                    "ref_low": 0.7,
                    "ref_high": 1.3,
                    "date": "2026-05-15",
                    "source_span": f"Creatinine {val}" if f"Creatinine {val}" in user_content else "creatinine"
                })
            if "haemoglobin" in content_lower or "hb" in content_lower:
                match = re.search(r"(?:haemoglobin|hb)[^\d]*(\d+(?:\.\d+)?)", content_lower)
                val = float(match.group(1)) if match else 13.5
                lab_rows.append({
                    "test": "Haemoglobin",
                    "normalized_test": "haemoglobin",
                    "value": val,
                    "unit": "g/dL",
                    "ref_low": 12.0,
                    "ref_high": 16.0,
                    "date": "2026-05-15",
                    "source_span": f"Haemoglobin {val}" if f"Haemoglobin {val}" in user_content else "haemoglobin"
                })

            return {
                "diagnoses": diagnoses,
                "medications": medications,
                "lab_rows": lab_rows,
                "procedures": [],
                "dates": ["2026-05-15"],
                "issuing_doctor": "Dr. R. K. Mehta",
                "issuing_facility": "Metropolitan Health Services"
            }

        # ── 3. Disease considerations ──
        if task == "disease_considerations":
            return {
                "considerations": [
                    {
                        "name": "Type 2 Diabetes Mellitus with suboptimal glycemic control",
                        "likelihood": "more likely",
                        "supporting_findings": [
                            {"finding": "Elevated HbA1c reported in records", "evidence": "hba1c 8.2%"},
                            {"finding": "Reported polyuria and polydipsia", "evidence": "interview_symptoms"}
                        ],
                        "findings_against": [
                            {"finding": "No documented diabetic ketoacidosis history", "evidence": "interview_history"}
                        ],
                        "suggested_confirmatory_tests": [
                            "Fasting Plasma Glucose (FPG)",
                            "Urine Albumin-to-Creatinine Ratio (uACR)"
                        ]
                    },
                    {
                        "name": "Essential Hypertension",
                        "likelihood": "possible",
                        "supporting_findings": [
                            {"finding": "Prescribed antihypertensive medication in active documents", "evidence": "amlodipine 5mg"}
                        ],
                        "findings_against": [
                            {"finding": "No current documented end-organ retinal changes", "evidence": "document_review"}
                        ],
                        "suggested_confirmatory_tests": [
                            "Serial Ambulatory Blood Pressure Monitoring (ABPM)"
                        ]
                    }
                ]
            }

        # ── 4. Treatment and dose reference ──
        if task == "treatment_reference":
            return {
                "guideline_summaries": [
                    {
                        "topic": "Type 2 Diabetes Glycemic Management",
                        "guideline_source": "Standard Treatment Workflow (SAMPLE – replace with verified source)",
                        "citation": "Section 4.1: Initial Metformin Dosing",
                        "recommended_regimen": "First-line oral monotherapy titration for adult patients with adequate eGFR.",
                        "dose_quotation": "Metformin 500 mg orally once or twice daily with meals, titrating gradually up to 1000 mg twice daily.",
                        "contraindications": ["eGFR < 30 mL/min/1.73m²", "Severe hepatic impairment"],
                        "cautions": "Monitor serum creatinine annually."
                    }
                ]
            }

        # ── 5. Trend interpretation ──
        if task == "trend_interpretation":
            # Clinical sentence using only computed numbers and configured rule match
            return {
                "interpretation": "Creatinine rose from 1.0 mg/dL to 1.8 mg/dL over 90 days, meeting the configured rise criterion; this may indicate reduced renal function. Clinical correlation required."
            }

        # ── 6. Case summary ──
        if task == "case_summary":
            return {
                "chief_complaint": "Persistent fatigue and increased thirst over past 3 weeks.",
                "hpi": "A 45-year-old patient reports progressive fatigue and polydipsia without acute fever or chills.",
                "pmh_psh": "Documented history of Type 2 Diabetes diagnosed 2 years ago.",
                "drug_allergy": "Reports Penicillin allergy (hives). Current medications include Metformin 500mg BD.",
                "family_history": "Maternal history of diabetes and cardiovascular disease.",
                "personal_history": "Non-smoker, sedentary lifestyle.",
                "ros": "Positive for fatigue and nocturia; negative for chest pain, dyspnea, or vision loss.",
                "prior_investigations": "Documented HbA1c 8.2% and Serum Creatinine 1.1 mg/dL.",
                "source_references": [
                    {"section": "chief_complaint", "source": "interview:chief_complaint"},
                    {"section": "pmh_psh", "source": "doc:1:diagnoses"},
                    {"section": "drug_allergy", "source": "interview:allergies"}
                ]
            }

        # ── 7. Questions to ask ──
        if task == "questions_to_ask":
            return {
                "questions": [
                    {
                        "question": "Can you verify if you have ever had an adverse allergic reaction to penicillin or amoxicillin?",
                        "reason": "Discrepancy between patient-reported penicillin allergy and prescription containing amoxicillin.",
                        "evidence_gap": "Prescription lists Amoxicillin 500mg whereas intake interview reports Penicillin allergy."
                    },
                    {
                        "question": "How often have you been missing doses of your morning Metformin?",
                        "reason": "Elevated HbA1c suggests suboptimal adherence or progression requiring dose adjustment.",
                        "evidence_gap": "Documented HbA1c 8.2% despite documented ongoing metformin prescription."
                    }
                ]
            }

        # ── 8. AI follow-up interview questions ──
        if task == "followup_questions":
            return {
                "followups": [
                    {
                        "key": "socrates_onset",
                        "text": "Did your symptoms start suddenly or did they develop gradually over several days?",
                        "reason": "SOCRATES symptom onset characterization",
                        "group": "symptoms"
                    },
                    {
                        "key": "socrates_severity",
                        "text": "On a scale from 1 to 10, how severe would you rate your discomfort at its worst?",
                        "reason": "SOCRATES severity quantification",
                        "group": "symptoms"
                    }
                ]
            }

        # ── 9. Handwriting Vision Fallback ──
        if task == "handwriting_transcription":
            return {
                "transcription": "Rx: Tab Metformin 500mg 1-0-1 after food x 30 days.\nTab Telmisartan 40mg 1-0-0 x 30 days.\nFollow up after 1 month with Fasting Blood Sugar and S. Creatinine.",
                "medications": [
                    {"name": "Metformin", "dosage": "500 mg", "frequency": "twice daily"},
                    {"name": "Telmisartan", "dosage": "40 mg", "frequency": "once daily"}
                ],
                "labs": [
                    {"test_name": "Fasting Blood Sugar", "value": "pending", "reference_range": "70-99 mg/dL"},
                    {"test_name": "S. Creatinine", "value": "pending", "reference_range": "0.7-1.3 mg/dL"}
                ],
                "notes": "Handwritten clinical script transcribed via vision fallback."
            }

        # Fallback default
        return {"status": "ok", "message": "Mock generation completed"}

