"""
services/contradiction_detection.py
-------------------------------------
Deterministic clinical discrepancy engine comparing patient-reported interview answers
against document-extracted medical evidence (prescriptions, discharge summaries).

Discrepancy Rules:
  1. RULE-MED-DENIAL: Patient denies taking medications, but document extracts active prescriptions.
  2. RULE-MED-NAME-MISMATCH: Patient reports taking drug A, but document prescribes drug B.
  3. RULE-MED-DOSAGE-MISMATCH: Patient reports drug at dosage X, document prescribes dosage Y.
  4. RULE-ALLERGY-CONFLICT: Patient reports drug allergy (e.g. Penicillin), but document prescribes an allergenic compound (e.g. Amoxicillin).
  5. RULE-ALLERGY-DENIAL: Patient denies allergies, but document records known adverse reactions.
  6. RULE-DOC-LOW-CONFIDENCE: Document scan is blurry, low-confidence (<0.50), or needs manual review.

Core Safety Principles:
  - Both sources are preserved: neither patient testimony nor OCR text is overwritten.
  - OCR extraction is treated as unverified evidence requiring clinician reconciliation.
  - All discrepancies are logged with rule_id, provenance, and audit tracking.
"""
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Conflict, Response, Document, ConflictStatus, DocumentStatus
from app.services.medication_extraction import DOSAGE_PATTERN

# Allergen family mappings for contraindication detection
ALLERGEN_CROSS_REACTIVITY = {
    "penicillin": ["penicillin", "amoxicillin", "ampicillin", "augmentin", "clavulanate", "piperacillin"],
    "amoxicillin": ["penicillin", "amoxicillin", "ampicillin", "augmentin"],
    "sulfa": ["bactrim", "trimethoprim", "sulfamethoxazole", "sulfasalazine"],
    "aspirin": ["aspirin", "ibuprofen", "naproxen", "diclofenac", "ketorolac", "mefenamic acid", "meloxicam"],
    "nsaid": ["aspirin", "ibuprofen", "naproxen", "diclofenac", "ketorolac", "mefenamic acid", "meloxicam", "celecoxib"],
    "statin": ["atorvastatin", "rosuvastatin", "simvastatin", "pravastatin"],
}


def _parse_dosage_number(val: Optional[str]) -> Optional[float]:
    """Extract numeric dosage value in milligrams/grams for exact comparison."""
    if not val:
        return None
    match = DOSAGE_PATTERN.search(val)
    if match:
        num = float(match.group(1))
        unit = match.group(2).lower()
        if unit == "g":
            return num * 1000.0
        elif unit == "mcg":
            return num / 1000.0
        return num
    return None


async def detect_contradictions(encounter_id: int, db: AsyncSession) -> List[Conflict]:
    """
    Evaluates all clinical discrepancy rules for an encounter.
    Compares patient responses with uploaded document extractions.
    Returns the list of open or existing Conflict records.
    """
    # 1. Gather patient interview responses
    responses = (
        await db.scalars(select(Response).where(Response.encounter_id == encounter_id))
    ).all()
    answered = {r.question_key: (r.answer or "").strip() for r in responses}

    # 2. Gather documents linked to this encounter
    docs = (
        await db.scalars(select(Document).where(Document.encounter_id == encounter_id))
    ).all()

    conflicts: List[Conflict] = []

    for doc in docs:
        extracted = doc.extracted_fields or {}
        # Extractions may store medications as plain names or as {"name": ..., "dose": ...} dicts
        medications_raw = [
            (m.get("name") or m.get("drug") or "") if isinstance(m, dict) else str(m)
            for m in (extracted.get("medications") or [])
        ]
        medications_raw = [m for m in medications_raw if m.strip()]
        med_details = extracted.get("medication_details", [])
        doc_allergies = extracted.get("allergies", [])
        doc_confidence = doc.extraction_confidence or 0.0

        doc_ref = f"document:{doc.id}:{doc.original_filename}"

        # ── Rule 1: RULE-MED-DENIAL ──────────────────────────────────────────
        med_answer = answered.get("current_medications", "").strip().lower()
        if med_answer in ("no", "none", "denies") and medications_raw:
            med_list_str = ", ".join(medications_raw)
            conflict = await _upsert_conflict(
                db=db,
                encounter_id=encounter_id,
                rule_id="RULE-MED-DENIAL",
                field="current_medications",
                source_a="patient_reported",
                value_a="Patient stated: No current medications.",
                source_b="document_extracted_unverified",
                value_b=f"Extracted medications ({doc.original_filename}): {med_list_str}",
                description=(
                    f"Patient denied taking any medications, but document '{doc.original_filename}' "
                    f"contains prescriptions for: {med_list_str}. Clinician verification required."
                ),
            )
            if conflict:
                conflicts.append(conflict)

        # ── Rule 2: RULE-MED-NAME-MISMATCH ──────────────────────────────────
        patient_meds_text = (
            answered.get("medication_details")
            or answered.get("medications_list")
            or answered.get("current_medications_names", "")
        ).strip()

        if med_answer in ("yes", "y") and patient_meds_text and medications_raw:
            # Check if patient reported a drug that does NOT appear in the prescription
            # or if the prescription lists drugs not mentioned by the patient
            patient_meds_lower = patient_meds_text.lower()
            unmatched_doc_meds = [
                m for m in medications_raw if m.lower() not in patient_meds_lower
            ]

            # If there is a complete mismatch
            if unmatched_doc_meds and not any(m.lower() in patient_meds_lower for m in medications_raw):
                conflict = await _upsert_conflict(
                    db=db,
                    encounter_id=encounter_id,
                    rule_id="RULE-MED-NAME-MISMATCH",
                    field="medication_name",
                    source_a="patient_reported",
                    value_a=f"Patient reported taking: {patient_meds_text}",
                    source_b="document_extracted_unverified",
                    value_b=f"Prescription specifies: {', '.join(unmatched_doc_meds)}",
                    description=(
                        f"Patient reported taking '{patient_meds_text}', but uploaded prescription "
                        f"'{doc.original_filename}' prescribes '{', '.join(unmatched_doc_meds)}'. "
                        "Verify whether medication was changed or discontinued."
                    ),
                )
                if conflict:
                    conflicts.append(conflict)

        # ── Rule 3: RULE-MED-DOSAGE-MISMATCH ────────────────────────────────
        dosage_answer = answered.get("medication_dosage", "").strip()
        if not dosage_answer and patient_meds_text:
            dosage_answer = patient_meds_text  # May contain dosage e.g. "Metformin 500mg"

        if dosage_answer and med_details:
            pat_dose_num = _parse_dosage_number(dosage_answer)
            for md in med_details:
                doc_med_name = md.get("name", "")
                doc_dosage_str = md.get("dosage", "")
                doc_dose_num = _parse_dosage_number(doc_dosage_str)

                # Check if this med is the one the patient reported
                if doc_med_name.lower() in dosage_answer.lower():
                    if pat_dose_num and doc_dose_num and pat_dose_num != doc_dose_num:
                        conflict = await _upsert_conflict(
                            db=db,
                            encounter_id=encounter_id,
                            rule_id="RULE-MED-DOSAGE-MISMATCH",
                            field=f"dosage_{doc_med_name.lower()}",
                            source_a="patient_reported",
                            value_a=f"{doc_med_name} {int(pat_dose_num)}mg (Patient reported)",
                            source_b="document_extracted_unverified",
                            value_b=f"{doc_med_name} {doc_dosage_str} (Prescription: {doc.original_filename})",
                            description=(
                                f"Dosage discrepancy detected for {doc_med_name}: "
                                f"Patient reported {int(pat_dose_num)}mg, while prescription specifies {doc_dosage_str}. "
                                "Confirm patient adherence or dosage modification."
                            ),
                        )
                        if conflict:
                            conflicts.append(conflict)

        # ── Rule 4: RULE-ALLERGY-CONFLICT (Contraindication Warning) ─────────
        allergy_text = (
            answered.get("allergy_details")
            or answered.get("allergy_reactions")
            or answered.get("has_allergies", "")
        ).lower()

        if allergy_text and allergy_text not in ("no", "none", "denies"):
            for allergen_key, related_drugs in ALLERGEN_CROSS_REACTIVITY.items():
                if allergen_key in allergy_text:
                    # Check if any extracted medication matches this allergen family
                    for prescribed_med in medications_raw:
                        p_lower = prescribed_med.lower()
                        if p_lower in related_drugs or allergen_key in p_lower:
                            conflict = await _upsert_conflict(
                                db=db,
                                encounter_id=encounter_id,
                                rule_id="RULE-ALLERGY-CONFLICT",
                                field="allergy_contraindication",
                                source_a="patient_reported",
                                value_a=f"Allergy reported: {allergen_key.capitalize()} ({answered.get('allergy_details', allergy_text)})",
                                source_b="document_extracted_unverified",
                                value_b=f"Prescribed drug: {prescribed_med} ({doc.original_filename})",
                                description=(
                                    f"CRITICAL CONTRAINDICATION: Patient reported allergy to '{allergen_key.capitalize()}', "
                                    f"but uploaded prescription contains '{prescribed_med}'. "
                                    "Immediate physician review required before administration."
                                ),
                            )
                            if conflict:
                                conflicts.append(conflict)

        # ── Rule 5: RULE-ALLERGY-DENIAL ──────────────────────────────────────
        has_allergy_answer = answered.get("has_allergies", "").strip().lower()
        if has_allergy_answer in ("no", "none", "denies") and doc_allergies:
            conflict = await _upsert_conflict(
                db=db,
                encounter_id=encounter_id,
                rule_id="RULE-ALLERGY-DENIAL",
                field="allergies",
                source_a="patient_reported",
                value_a="Patient stated: No known allergies.",
                source_b="document_extracted_unverified",
                value_b=f"Document lists allergy references: {', '.join(doc_allergies)}",
                description=(
                    f"Patient denied having allergies, but document '{doc.original_filename}' "
                    f"notes allergies/reactions to: {', '.join(doc_allergies)}. "
                    "Clinical verification required."
                ),
            )
            if conflict:
                conflicts.append(conflict)

        # ── Rule 6: RULE-DOC-LOW-CONFIDENCE ──────────────────────────────────
        if doc.status == DocumentStatus.needs_review or (doc.status == DocumentStatus.completed and doc_confidence < 0.50):
            conflict = await _upsert_conflict(
                db=db,
                encounter_id=encounter_id,
                rule_id="RULE-DOC-LOW-CONFIDENCE",
                field=f"document_legibility_{doc.id}",
                source_a="system_quality_check",
                value_a="OCR scan quality inspection",
                source_b="document_extracted_unverified",
                value_b=f"Low OCR confidence ({round(doc_confidence * 100)}%) on {doc.original_filename}",
                description=(
                    f"Document '{doc.original_filename}' has low optical confidence or unreadable text. "
                    "Original scan has been preserved for manual doctor inspection."
                ),
            )
            if conflict:
                conflicts.append(conflict)

    return conflicts


async def _upsert_conflict(
    db: AsyncSession,
    encounter_id: int,
    rule_id: str,
    field: str,
    source_a: str,
    value_a: str,
    source_b: str,
    value_b: str,
    description: str,
) -> Conflict | None:
    """
    Inserts a conflict record only if an open conflict doesn't already exist
    for this encounter, rule_id, and field.
    """
    existing = await db.scalar(
        select(Conflict).where(
            Conflict.encounter_id == encounter_id,
            Conflict.rule_id == rule_id,
            Conflict.field == field,
            Conflict.status == ConflictStatus.open,
        )
    )
    if existing:
        return existing

    conflict = Conflict(
        encounter_id=encounter_id,
        rule_id=rule_id,
        field=field,
        source_a=source_a,
        value_a=value_a,
        source_b=source_b,
        value_b=value_b,
        description=description,
        status=ConflictStatus.open,
        created_at=datetime.now(timezone.utc),
    )
    db.add(conflict)
    await db.commit()
    await db.refresh(conflict)
    return conflict
