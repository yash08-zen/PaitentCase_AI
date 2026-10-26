"""
services/case_summary.py
-------------------------
Builds structured case summary and plain-text summary with explicit provenance.

Clinical Safety Rules (M5 & Master Prompt):
  - Never invents diagnoses, medications, or treatments.
  - Missing information ≠ negative answer.
  - An unreported allergy is displayed as "Not provided / unknown", NEVER "no allergies".
  - An unreported medication is displayed as "Not provided / unknown", NEVER "no medications".
  - Every statement references its provenance source:
      * patient_reported
      * document_extracted_unverified
      * doctor_verified
      * missing_unknown
  - Clear clinical boundary notices on all outputs:
      "FOR CLINICAL REVIEW ONLY — NOT A DIAGNOSTIC TOOL"
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Encounter, Patient, Response, Document, Conflict, ReviewFlag
from app.schemas import SummaryFieldOut, SummarySectionOut
from app.services.missing_information import is_missing_value


PROVENANCE_LABELS = {
    "patient_reported": "Patient reported",
    "document_extracted_unverified": "Document extracted (unverified)",
    "doctor_verified": "Doctor verified",
    "missing_unknown": "Not provided / unknown",
}


def make_field(
    key: str,
    label: str,
    raw_val: Optional[str],
    source: Optional[str] = None,
    formatter=None,
    details: Optional[str] = None,
) -> SummaryFieldOut:
    """Helper to construct a SummaryFieldOut with honest handling of unknowns and provenance."""
    is_missing = is_missing_value(raw_val)
    if is_missing:
        display_val = "Not provided / unknown"
        field_source = "missing_unknown"
    else:
        display_val = formatter(raw_val) if formatter else str(raw_val).strip()
        field_source = source or "patient_reported"

    source_label = PROVENANCE_LABELS.get(field_source, field_source.replace("_", " ").title())

    return SummaryFieldOut(
        key=key,
        label=label,
        value=display_val,
        source=field_source,
        source_label=source_label,
        is_missing=is_missing,
        details=details,
    )


async def build_structured_summary(encounter_id: int, db: AsyncSession) -> Dict[str, Any]:
    """
    Builds a structured dictionary with sections and findings from saved database data only.
    """
    enc: Optional[Encounter] = await db.get(Encounter, encounter_id)
    if not enc:
        raise ValueError(f"Encounter {encounter_id} not found")

    patient: Optional[Patient] = await db.get(Patient, enc.patient_id)

    # Gather responses
    responses = (
        await db.scalars(select(Response).where(Response.encounter_id == encounter_id))
    ).all()
    answered: Dict[str, str] = {r.question_key: (r.answer or "").strip() for r in responses}
    sources: Dict[str, str] = {r.question_key: (r.source or "patient_reported") for r in responses}

    # Gather documents
    docs = (
        await db.scalars(select(Document).where(Document.encounter_id == encounter_id))
    ).all()

    # Gather open conflicts
    conflicts = (
        await db.scalars(
            select(Conflict).where(
                Conflict.encounter_id == encounter_id, Conflict.status == "open"
            )
        )
    ).all()

    # Gather open review flags
    flags = (
        await db.scalars(
            select(ReviewFlag).where(
                ReviewFlag.encounter_id == encounter_id, ReviewFlag.status == "open"
            )
        )
    ).all()

    # 1. Patient Demographics Section
    demo_fields = [
        make_field("full_name", "Patient Name", patient.full_name if patient else None, "patient_reported"),
        make_field("age_dob", "Age / Date of Birth", f"{patient.age or ''} ({patient.date_of_birth or 'DOB not provided'})" if (patient and (patient.age or patient.date_of_birth)) else None, "patient_reported"),
        make_field("gender", "Gender", patient.gender if patient else None, "patient_reported"),
        make_field("preferred_language", "Preferred Language", patient.preferred_language if patient else None, "patient_reported"),
        make_field("contact", "Contact Information", (patient.contact_phone or patient.contact_email) if patient else None, "patient_reported"),
    ]

    # 2. Chief Complaint Section
    cc_val = answered.get("chief_complaint")
    cc_fields = [
        make_field("chief_complaint", "Chief Complaint", cc_val, sources.get("chief_complaint")),
    ]

    # 3. Symptoms Exploration Section
    sym_fields = [
        make_field("symptom_duration", "Duration", answered.get("symptom_duration"), sources.get("symptom_duration")),
        make_field("symptom_severity", "Severity", answered.get("symptom_severity"), sources.get("symptom_severity"), formatter=lambda v: f"{v} / 10"),
        make_field("symptom_frequency", "Frequency", answered.get("symptom_frequency"), sources.get("symptom_frequency")),
    ]
    if "pain_location" in answered:
        sym_fields.append(make_field("pain_location", "Pain Location", answered.get("pain_location"), sources.get("pain_location")))
    if "chest_discomfort_exertion" in answered:
        sym_fields.append(make_field("chest_discomfort_exertion", "Worse with Exertion", answered.get("chest_discomfort_exertion"), sources.get("chest_discomfort_exertion")))
    if "associated_symptoms" in answered:
        sym_fields.append(make_field("associated_symptoms", "Associated Symptoms", answered.get("associated_symptoms"), sources.get("associated_symptoms")))

    # 4. Medical & Surgical History Section
    chronic_ans = answered.get("has_chronic_conditions")
    if is_missing_value(chronic_ans):
        chronic_val = None
    elif chronic_ans.lower() == "no":
        chronic_val = "Reports no known chronic conditions"
    elif chronic_ans.lower() == "yes":
        details = answered.get("chronic_conditions_detail", "").strip()
        chronic_val = f"Reports chronic conditions: {details}" if details else "Reports chronic conditions (details not provided)"
    else:
        chronic_val = chronic_ans

    med_history_fields = [
        make_field("has_chronic_conditions", "Chronic Conditions", chronic_val, sources.get("has_chronic_conditions")),
        make_field("hospitalization_history", "Previous Hospitalizations", answered.get("hospitalization_history"), sources.get("hospitalization_history")),
        make_field("family_history", "Family Medical History", answered.get("family_history"), sources.get("family_history")),
        make_field("previous_treatments", "Previous Treatments", answered.get("previous_treatments"), sources.get("previous_treatments")),
    ]

    # 5. Current Medications Section
    med_ans = answered.get("current_medications")
    if is_missing_value(med_ans):
        med_val = None
    elif med_ans.lower() == "no":
        med_val = "Reports no current medications"
    elif med_ans.lower() == "yes":
        details = answered.get("medication_details", "").strip()
        med_val = f"Reports taking: {details}" if details else "Reports taking medications (details not specified)"
    else:
        med_val = med_ans

    med_fields = [
        make_field("current_medications", "Current Medications", med_val, sources.get("current_medications")),
    ]

    # 6. Allergies Section
    allergy_ans = answered.get("has_allergies")
    if is_missing_value(allergy_ans):
        allergy_val = None
    elif allergy_ans.lower() == "no":
        allergy_val = "No known allergies reported"
    elif allergy_ans.lower() == "yes":
        details = answered.get("allergy_details", "").strip()
        allergy_val = f"Known allergy reported: {details}" if details else "Reports known allergy (details not specified)"
    else:
        allergy_val = allergy_ans

    allergy_fields = [
        make_field("has_allergies", "Known Allergies", allergy_val, sources.get("has_allergies")),
    ]

    # 7. Uploaded Documents Section
    doc_fields = []
    if docs:
        for d in docs:
            verification_status = "doctor_verified" if d.is_verified else "document_extracted_unverified"
            doc_desc = f"{d.document_type or 'Prescription'}: {d.original_filename}"
            if d.extracted_fields:
                doc_desc += f" (Extracted: {d.extracted_fields})"
            doc_fields.append(
                SummaryFieldOut(
                    key=f"document_{d.id}",
                    label=f"Uploaded Document #{d.id}",
                    value=doc_desc,
                    source=verification_status,
                    source_label=PROVENANCE_LABELS.get(verification_status),
                    is_missing=False,
                )
            )
    else:
        doc_fields.append(
            SummaryFieldOut(
                key="documents_none",
                label="Uploaded Prescriptions / Documents",
                value="No documents uploaded for this encounter",
                source="missing_unknown",
                source_label="Not provided / unknown",
                is_missing=True,
            )
        )

    # 8. Contradictions & Discrepancies Section
    conflict_fields = []
    if conflicts:
        for c in conflicts:
            conflict_fields.append(
                SummaryFieldOut(
                    key=f"conflict_{c.id}",
                    label=f"Potential Discrepancy: {c.field}",
                    value=f"{c.source_a}: {c.value_a} vs {c.source_b}: {c.value_b}",
                    source="document_extracted_unverified",
                    source_label="Document extracted (unverified)",
                    is_missing=False,
                    details=c.description or "Medication information requires clinician verification",
                )
            )

    sections = [
        SummarySectionOut(id="patient_demographics", title="Patient Demographics", fields=demo_fields),
        SummarySectionOut(id="chief_complaint", title="Chief Complaint", fields=cc_fields),
        SummarySectionOut(id="symptoms", title="Symptom Exploration", fields=sym_fields),
        SummarySectionOut(id="medical_history", title="Medical & Surgical History", fields=med_history_fields),
        SummarySectionOut(id="medications", title="Current Medications", fields=med_fields),
        SummarySectionOut(id="allergies", title="Allergies & Sensitivities", fields=allergy_fields),
        SummarySectionOut(id="documents", title="Uploaded Documents & Extractions", fields=doc_fields),
    ]
    if conflict_fields:
        sections.append(
            SummarySectionOut(
                id="conflicts",
                title="Potential Information Discrepancies (Require Review)",
                fields=conflict_fields,
            )
        )

    # Flat structured findings for tabular rendering
    findings: List[SummaryFieldOut] = [
        cc_fields[0],
        sym_fields[0],  # duration
        sym_fields[1],  # severity
        med_history_fields[0],  # chronic conditions
        med_fields[0],  # medications
        allergy_fields[0],  # allergies
    ]
    # Add any extra answered symptom fields
    for f in sym_fields[2:]:
        if not f.is_missing:
            findings.append(f)
    # Add documents
    for f in doc_fields:
        if not f.is_missing:
            findings.append(f)
    # Add conflicts
    for f in conflict_fields:
        findings.append(f)

    # Generate plain-text summary
    summary_text = _format_text_summary(patient, answered, sources, docs, conflicts)

    return {
        "encounter_id": encounter_id,
        "patient": patient,
        "sections": sections,
        "findings": findings,
        "summary_text": summary_text,
    }


def _format_text_summary(
    patient: Optional[Patient],
    answered: Dict[str, str],
    sources: Dict[str, str],
    docs: List[Document],
    conflicts: List[Conflict],
) -> str:
    """Format structured data into human-readable text with explicit provenance and safety labels."""
    lines = [
        "=" * 80,
        "             PATIENT CASE SUMMARY (DRAFT)",
        "  ⚠️ FOR CLINICAL REVIEW ONLY — NOT A DIAGNOSIS ⚠️",
        "=" * 80,
        "",
        "--- PATIENT INFORMATION --------------------------------------------------------",
        f"  Name            : {patient.full_name if patient else 'Unknown'}",
        f"  Age / DOB       : {patient.age or 'Age not provided'} / {patient.date_of_birth or 'DOB not provided'}",
        f"  Gender          : {patient.gender or 'Not provided / unknown'}",
        f"  Contact         : {patient.contact_phone or patient.contact_email or 'Not provided / unknown'}",
        f"  Language        : {patient.preferred_language if patient else 'Not provided / unknown'}",
        "",
        "--- CHIEF COMPLAINT ------------------------------------------------------------",
    ]

    cc = answered.get("chief_complaint")
    if is_missing_value(cc):
        lines += [
            "  Not provided / unknown",
            "  (Source: missing_unknown)",
        ]
    else:
        lines += [
            f"  {cc}",
            "  (Source: patient response / patient_reported)",
        ]
    lines.append("")

    lines += [
        "--- SYMPTOM DETAILS ------------------------------------------------------------",
        f"  Duration   : {answered.get('symptom_duration', 'Not provided / unknown')}",
        f"  Severity   : {answered.get('symptom_severity', 'Not provided / unknown')} / 10",
        f"  Frequency  : {answered.get('symptom_frequency', 'Not provided / unknown')}",
    ]
    if "pain_location" in answered:
        lines.append(f"  Location   : {answered.get('pain_location')}")
    if "chest_discomfort_exertion" in answered:
        lines.append(f"  Exertion   : {answered.get('chest_discomfort_exertion')}")
    if "associated_symptoms" in answered:
        lines.append(f"  Associated : {answered.get('associated_symptoms')}")
    lines += [
        "  (Source: patient response / patient_reported)",
        "",
        "--- MEDICAL HISTORY ------------------------------------------------------------",
    ]

    chronic = answered.get("has_chronic_conditions")
    if is_missing_value(chronic):
        lines.append("  Chronic conditions  : Not provided / unknown")
    elif chronic.lower() == "no":
        lines.append("  Chronic conditions  : Reports no known chronic conditions")
    elif chronic.lower() == "yes":
        lines.append(f"  Chronic conditions  : Reports chronic conditions ({answered.get('chronic_conditions_detail', 'details not specified')})")
    else:
        lines.append(f"  Chronic conditions  : {chronic}")

    lines += [
        f"  Hospitalizations    : {answered.get('hospitalization_history', 'Not provided / unknown')}",
        f"  Family history      : {answered.get('family_history', 'Not provided / unknown')}",
        f"  Previous treatments : {answered.get('previous_treatments', 'Not provided / unknown')}",
        "  (Source: patient response / patient_reported)",
        "",
        "--- MEDICATIONS ----------------------------------------------------------------",
    ]

    meds = answered.get("current_medications")
    if is_missing_value(meds):
        lines += [
            "  Currently taking medications : Not provided / unknown",
            "  (Source: missing_unknown — requires clinician verification)",
        ]
    elif meds.lower() == "no":
        lines += [
            "  Currently taking medications : Reports no current medications",
            "  (Source: patient response / patient_reported)",
        ]
    else:
        lines += [
            f"  Currently taking medications : Reports taking {answered.get('medication_details', meds)}",
            "  (Source: patient response / patient_reported)",
        ]
    lines.append("")

    lines += [
        "--- ALLERGIES ------------------------------------------------------------------",
    ]
    allergies = answered.get("has_allergies")
    if is_missing_value(allergies):
        lines += [
            "  Known allergies : Not provided / unknown",
            "  (Source: missing_unknown — requires clinician verification)",
        ]
    elif allergies.lower() == "no":
        lines += [
            "  Known allergies : No known allergies reported",
            "  (Source: patient response / patient_reported)",
        ]
    else:
        lines += [
            f"  Known allergies : Reported allergy: {answered.get('allergy_details', allergies)}",
            "  (Source: patient response / patient_reported)",
        ]
    lines.append("")

    if docs:
        lines.append("--- UPLOADED DOCUMENTS ---------------------------------------------------------")
        for doc in docs:
            verified_label = "✅ Verified by doctor" if doc.is_verified else "⚠️ Unverified — requires clinician review"
            lines.append(f"  [{doc.document_type or 'document'}] {doc.original_filename}  — {verified_label}")
            if doc.extracted_fields:
                lines.append(f"    Extracted fields : {doc.extracted_fields}")
            elif doc.extracted_text:
                preview = doc.extracted_text[:200].replace("\n", " ")
                lines.append(f"    Extracted text   : {preview}...")
        lines.append("")

    if conflicts:
        lines.append("--- ⚠️ POTENTIAL MEDICATION DISCREPANCIES (REQUIRE REVIEW) ---------------------")
        for c in conflicts:
            lines.append(f"  Field : {c.field}")
            lines.append(f"  {c.source_a}: {c.value_a}")
            lines.append(f"  {c.source_b}: {c.value_b}")
            lines.append(f"  Note  : {c.description or 'Medication information requires verification'}")
            lines.append("")

    lines += [
        "=" * 80,
        f"  Generated : {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "  Status    : Awaiting clinician review",
        "  Disclaimer: This summary assists with information collection and organization.",
        "              It does not replace professional clinical judgment.",
        "              It is NOT a diagnosis, prescription, or clinical decision.",
        "=" * 80,
    ]

    return "\n".join(lines)


async def generate_summary(encounter_id: int, db: AsyncSession) -> str:
    """Convenience method returning plain text summary string."""
    data = await build_structured_summary(encounter_id, db)
    return data["summary_text"]
