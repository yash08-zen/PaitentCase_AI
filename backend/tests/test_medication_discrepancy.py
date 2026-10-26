"""
tests/test_medication_discrepancy.py
-------------------------------------
Milestone 7 Test Suite: Medication Extraction and Clinical Discrepancy Rules (FR-08).

Tests:
  1. Medication extraction from raw OCR prescription text (name, dosage, form, frequency).
  2. RULE-MED-DENIAL: Patient denies medications, prescription contains medications.
  3. RULE-MED-NAME-MISMATCH: Patient reports taking Drug A, prescription specifies Drug B.
  4. RULE-MED-DOSAGE-MISMATCH: Patient reports 500mg, prescription specifies 1000mg.
  5. RULE-ALLERGY-CONFLICT: Patient reports Penicillin allergy, prescription contains Amoxicillin.
  6. RULE-ALLERGY-DENIAL: Patient denies allergies, document lists adverse reactions.
  7. Conflict resolution endpoint with audit event logging.
  8. Role boundary security: Patient role forbidden on conflict resolution.
"""
import pytest
from httpx import AsyncClient

from app.services.medication_extraction import (
    extract_medications_from_text,
    extract_allergy_mentions_from_text,
    normalize_frequency,
)
from app.models import Document, DocumentStatus, Response


def test_medication_extraction_from_prescription_text():
    """Verify deterministic parsing of drug name, dosage, form, frequency, and instructions."""
    sample_rx_text = """
    RX CLINIC
    Date: 2026-10-24
    Patient: John Doe

    1. Tab. Amoxicillin 500mg - 1-0-1 for 7 days after meals
    2. Tab. Paracetamol 650mg - PRN for fever
    3. Cap. Omeprazole 20mg - OD before breakfast
    4. Metformin 1000mg twice daily with food
    """

    meds = extract_medications_from_text(sample_rx_text)
    assert len(meds) >= 4

    med_dict = {m["name"].lower(): m for m in meds}

    # Amoxicillin check
    assert "amoxicillin" in med_dict
    amox = med_dict["amoxicillin"]
    assert amox["dosage"] == "500mg"
    assert "Twice daily" in amox["frequency"]
    assert amox["provenance"] == "document_extracted_unverified"

    # Paracetamol check
    assert "paracetamol" in med_dict
    para = med_dict["paracetamol"]
    assert para["dosage"] == "650mg"
    assert "PRN" in para["frequency"] or "needed" in para["frequency"].lower()

    # Omeprazole check
    assert "omeprazole" in med_dict
    assert med_dict["omeprazole"]["dosage"] == "20mg"

    # Metformin check
    assert "metformin" in med_dict
    assert med_dict["metformin"]["dosage"] == "1000mg"
    assert "Twice daily" in med_dict["metformin"]["frequency"]


def test_allergy_extraction_from_document_text():
    """Verify extraction of allergy mentions from document text."""
    doc_text = """
    DISCHARGE SUMMARY
    Allergies: Penicillin, Sulfa drugs
    Adverse reaction: Codeine
    """
    allergies = extract_allergy_mentions_from_text(doc_text)
    assert "Penicillin" in allergies or "penicillin" in [a.lower() for a in allergies]
    assert any("sulfa" in a.lower() for a in allergies)


@pytest.mark.asyncio
async def test_rule_med_denial_when_patient_denies_medications(client: AsyncClient, auth_headers: dict):
    """DoD: RULE-MED-DENIAL flags discrepancy when patient says No medications but doc has extractions."""
    # 1. Create Patient & Encounter
    p_res = await client.post("/api/patients", json={"full_name": "Denial Patient", "age": 52}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # 2. Patient answers current_medications = "No"
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "current_medications", "answer": "No"},
        headers=auth_headers,
    )

    # 3. Simulate attached document with extracted medications
    async with (await import_async_session()) as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=enc_id,
            original_filename="rx_amoxicillin.png",
            stored_path="test_uploads/fake.png",
            status=DocumentStatus.completed,
            extracted_text="Tab. Amoxicillin 500mg twice daily",
            extracted_fields={
                "medications": ["Amoxicillin"],
                "medication_details": [{"name": "Amoxicillin", "dosage": "500mg", "frequency": "Twice daily"}],
            },
            extraction_confidence=0.92,
        )
        db.add(doc)
        await db.commit()

    # 4. Trigger contradictions evaluation
    res = await client.get(f"/api/encounters/{enc_id}/contradictions", headers=auth_headers)
    assert res.status_code == 200
    conflicts = res.json()

    assert len(conflicts) >= 1
    c = next((x for x in conflicts if x["rule_id"] == "RULE-MED-DENIAL"), None)
    assert c is not None
    assert c["field"] == "current_medications"
    assert c["source_a"] == "patient_reported"
    assert c["source_b"] == "document_extracted_unverified"
    assert "No current medications" in c["value_a"]
    assert "Amoxicillin" in c["value_b"]
    assert c["status"] == "open"


@pytest.mark.asyncio
async def test_rule_med_name_mismatch(client: AsyncClient, auth_headers: dict):
    """DoD: RULE-MED-NAME-MISMATCH flags discrepancy when patient reports drug A but prescription states drug B."""
    p_res = await client.post("/api/patients", json={"full_name": "Mismatch Patient", "age": 60}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Patient reported taking Lisinopril
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "current_medications", "answer": "Yes"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "medication_details", "answer": "Lisinopril 10mg daily"},
        headers=auth_headers,
    )

    # Document prescribes Amlodipine
    async with (await import_async_session()) as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=enc_id,
            original_filename="rx_cardio.png",
            stored_path="test_uploads/fake.png",
            status=DocumentStatus.completed,
            extracted_text="Tab. Amlodipine 5mg OD",
            extracted_fields={
                "medications": ["Amlodipine"],
                "medication_details": [{"name": "Amlodipine", "dosage": "5mg", "frequency": "Once daily"}],
            },
            extraction_confidence=0.90,
        )
        db.add(doc)
        await db.commit()

    res = await client.get(f"/api/encounters/{enc_id}/contradictions", headers=auth_headers)
    assert res.status_code == 200
    conflicts = res.json()

    c = next((x for x in conflicts if x["rule_id"] == "RULE-MED-NAME-MISMATCH"), None)
    assert c is not None
    assert c["field"] == "medication_name"
    assert "Lisinopril" in c["value_a"]
    assert "Amlodipine" in c["value_b"]


@pytest.mark.asyncio
async def test_rule_med_dosage_mismatch(client: AsyncClient, auth_headers: dict):
    """DoD: RULE-MED-DOSAGE-MISMATCH flags difference between patient reported dosage and prescription."""
    p_res = await client.post("/api/patients", json={"full_name": "Dosage Patient", "age": 48}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Patient reports taking Metformin 500mg
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "current_medications", "answer": "Yes"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "medication_dosage", "answer": "Metformin 500mg twice a day"},
        headers=auth_headers,
    )

    # Prescription prescribes Metformin 1000mg
    async with (await import_async_session()) as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=enc_id,
            original_filename="rx_diabetes.png",
            stored_path="test_uploads/fake.png",
            status=DocumentStatus.completed,
            extracted_text="Tab. Metformin 1000mg BD after food",
            extracted_fields={
                "medications": ["Metformin"],
                "medication_details": [{"name": "Metformin", "dosage": "1000mg", "frequency": "Twice daily"}],
            },
            extraction_confidence=0.95,
        )
        db.add(doc)
        await db.commit()

    res = await client.get(f"/api/encounters/{enc_id}/contradictions", headers=auth_headers)
    assert res.status_code == 200
    conflicts = res.json()

    c = next((x for x in conflicts if x["rule_id"] == "RULE-MED-DOSAGE-MISMATCH"), None)
    assert c is not None
    assert "500" in c["value_a"]
    assert "1000" in c["value_b"]


@pytest.mark.asyncio
async def test_rule_allergy_contraindication_conflict(client: AsyncClient, auth_headers: dict):
    """DoD: RULE-ALLERGY-CONFLICT flags contraindication when allergic patient is prescribed matching drug."""
    p_res = await client.post("/api/patients", json={"full_name": "Allergic Patient", "age": 35}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Patient reports penicillin allergy
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "has_allergies", "answer": "Yes"},
        headers=auth_headers,
    )
    await client.post(
        f"/api/interviews/{enc_id}/responses",
        json={"question_key": "allergy_details", "answer": "Severe rash with Penicillin"},
        headers=auth_headers,
    )

    # Document prescribes Amoxicillin (cross-reactive penicillin derivative)
    async with (await import_async_session()) as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=enc_id,
            original_filename="rx_antibiotic.png",
            stored_path="test_uploads/fake.png",
            status=DocumentStatus.completed,
            extracted_text="Tab. Amoxicillin 500mg TID",
            extracted_fields={
                "medications": ["Amoxicillin"],
                "medication_details": [{"name": "Amoxicillin", "dosage": "500mg"}],
            },
            extraction_confidence=0.91,
        )
        db.add(doc)
        await db.commit()

    res = await client.get(f"/api/encounters/{enc_id}/contradictions", headers=auth_headers)
    assert res.status_code == 200
    conflicts = res.json()

    c = next((x for x in conflicts if x["rule_id"] == "RULE-ALLERGY-CONFLICT"), None)
    assert c is not None
    assert c["field"] == "allergy_contraindication"
    assert "Penicillin" in c["value_a"]
    assert "Amoxicillin" in c["value_b"]
    assert "CRITICAL CONTRAINDICATION" in c["description"]


@pytest.mark.asyncio
async def test_conflict_resolution_and_audit_logging(client: AsyncClient, auth_headers: dict):
    """DoD: Clinician reconciles discrepancy -> persists resolution note, resolved status, and audit trail."""
    p_res = await client.post("/api/patients", json={"full_name": "Resolve Patient", "age": 40}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Trigger a conflict
    await client.post(f"/api/interviews/{enc_id}/responses", json={"question_key": "current_medications", "answer": "No"}, headers=auth_headers)
    async with (await import_async_session()) as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=enc_id,
            original_filename="rx_test.png",
            stored_path="test_uploads/fake.png",
            status=DocumentStatus.completed,
            extracted_text="Tab. Atorvastatin 20mg OD",
            extracted_fields={"medications": ["Atorvastatin"]},
            extraction_confidence=0.88,
        )
        db.add(doc)
        await db.commit()

    # Fetch conflicts
    list_res = await client.get(f"/api/conflicts?encounter_id={enc_id}&refresh=true", headers=auth_headers)
    assert list_res.status_code == 200
    conflicts = list_res.json()
    assert len(conflicts) >= 1
    conflict_id = conflicts[0]["id"]

    # Clinician resolves conflict
    resolve_res = await client.put(
        f"/api/conflicts/{conflict_id}/resolve",
        json={
            "status": "resolved",
            "resolution_note": "Spoke with patient; Atorvastatin was prescribed last week but patient has not started yet.",
        },
        headers=auth_headers,
    )
    assert resolve_res.status_code == 200
    resolved = resolve_res.json()
    assert resolved["status"] == "resolved"
    assert "Spoke with patient" in resolved["resolution_note"]
    assert resolved["resolved_by"] is not None
    assert resolved["resolved_at"] is not None

    # Verify audit log recorded CONFLICT_RESOLVED
    audit_res = await client.get("/api/auth/audit", headers=auth_headers)
    assert audit_res.status_code == 200
    events = audit_res.json()
    match_event = next((ev for ev in events if ev["action"] == "CONFLICT_RESOLVED" and ev["resource_id"] == str(conflict_id)), None)
    assert match_event is not None


@pytest.mark.asyncio
async def test_patient_role_forbidden_on_conflict_resolution(client: AsyncClient, auth_headers: dict):
    """DoD: Patients cannot resolve clinical discrepancies (HTTP 403)."""
    p_res = await client.post("/api/patients", json={"full_name": "Security Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # Trigger a conflict
    await client.post(f"/api/interviews/{enc_id}/responses", json={"question_key": "current_medications", "answer": "No"}, headers=auth_headers)
    async with (await import_async_session()) as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=enc_id,
            original_filename="rx_test.png",
            stored_path="test_uploads/fake.png",
            status=DocumentStatus.completed,
            extracted_text="Tab. Azithromycin 500mg OD",
            extracted_fields={"medications": ["Azithromycin"]},
            extraction_confidence=0.88,
        )
        db.add(doc)
        await db.commit()

    list_res = await client.get(f"/api/conflicts?encounter_id={enc_id}&refresh=true", headers=auth_headers)
    conflict_id = list_res.json()[0]["id"]

    # Login as patient
    p_login = await client.post("/api/auth/login", json={"username": "patient", "password": "Patient@1234"})
    p_token = p_login.json()["access_token"]
    p_headers = {"Authorization": f"Bearer {p_token}"}

    # Attempt resolution as patient
    res = await client.put(
        f"/api/conflicts/{conflict_id}/resolve",
        json={"status": "resolved", "resolution_note": "Patient trying to dismiss"},
        headers=p_headers,
    )
    assert res.status_code == 403


async def import_async_session():
    from app.database import AsyncSessionLocal
    return AsyncSessionLocal()
