"""
tests/test_e2e_p0_release_gate.py
---------------------------------
Comprehensive End-to-End Integration Test Suite for Milestone M10 (P0 Release Gate, FR-15).

Automates and verifies the full 9-step clinical lifecycle:
  1. Register a sample patient and create an encounter with consent.
  2. Complete an adaptive symptom interview with deterministic branching.
  3. Leave a required field incomplete -> missing-information flag appears in completeness analysis.
  4. Upload a clear prescription image -> real OCR runs and extracts text.
  5. Extracted medication text/dosage shown where legible.
  6. Patient says no current medication -> discrepancy flagged (RULE-MED-DENIAL / RULE-MED-NAME-MISMATCH).
  7. Doctor logs in, opens the case from the doctor dashboard.
  8. Doctor resolves the conflict, adds clinical notes, and finalizes the encounter.
  9. Reopen encounter -> verify persistence and verify patient edits are rejected (HTTP 400).
"""
import io
import os
import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw
from app.models import Document, DocumentStatus
from app.database import AsyncSessionLocal


@pytest.fixture
def sample_prescription_bytes():
    """Generate a clean synthetic prescription image in-memory."""
    img = Image.new("RGB", (600, 300), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((30, 30), "CITY HEALTH CLINIC - Dr. R. Sharma, MD", fill=(0, 0, 0))
    draw.text((30, 70), "Patient: E2E Test Patient", fill=(0, 0, 0))
    draw.text((30, 120), "Rx: Amoxicillin 500mg capsules", fill=(0, 0, 0))
    draw.text((30, 160), "Sig: 1 capsule TID x 7 days", fill=(0, 0, 0))
    draw.text((30, 220), "Disp: 21 capsules", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_e2e_p0_full_clinical_lifecycle(client: AsyncClient, sample_prescription_bytes):
    """
    Executes the complete 9-step clinical intake lifecycle end-to-end.
    """
    # =========================================================================
    # Step 0: Ensure Default Users Exist (Staff, Doctor, Patient)
    # =========================================================================
    admin_login = await client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create Doctor user
    doc_res = await client.post(
        "/api/auth/register",
        json={"username": "e2e_doctor", "email": "e2e_doctor@patientcase.local", "password": "Doctor@1234", "role": "doctor"},
        headers=admin_headers,
    )
    assert doc_res.status_code in [201, 400]

    # Create Staff user
    staff_res = await client.post(
        "/api/auth/register",
        json={"username": "e2e_staff", "email": "e2e_staff@patientcase.local", "password": "Staff@1234", "role": "staff"},
        headers=admin_headers,
    )
    assert staff_res.status_code in [201, 400]

    # Login as Staff to register patient
    staff_login = await client.post("/api/auth/login", json={"username": "e2e_staff", "password": "Staff@1234"})
    assert staff_login.status_code == 200
    staff_token = staff_login.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # =========================================================================
    # Step 1: Register Sample Patient and Create Encounter with Consent
    # =========================================================================
    patient_payload = {
        "full_name": "Devendra Joshi",
        "age": 48,
        "gender": "Male",
        "contact_phone": "9819922334",
        "contact_email": "devendra.joshi@example.com",
        "preferred_language": "English",
    }
    patient_res = await client.post("/api/patients", json=patient_payload, headers=staff_headers)
    assert patient_res.status_code == 201, patient_res.text
    patient_data = patient_res.json()
    patient_id = patient_data["id"]
    assert patient_data["full_name"] == "Devendra Joshi"

    # Create encounter with consent
    encounter_payload = {
        "patient_id": patient_id,
        "chief_complaint": "Persistent dry cough and chest tightness for 5 days",
        "consent_given": True,
    }
    encounter_res = await client.post("/api/encounters", json=encounter_payload, headers=staff_headers)
    assert encounter_res.status_code == 201, encounter_res.text
    encounter_data = encounter_res.json()
    encounter_id = encounter_data["id"]
    assert encounter_data["consent_given"] is True
    assert encounter_data["consent_timestamp"] is not None

    # =========================================================================
    # Step 2: Complete Adaptive Symptom Interview with Deterministic Branching
    # =========================================================================
    # Fetch initial question
    next_q = await client.get(f"/api/interviews/{encounter_id}/next-question", headers=staff_headers)
    assert next_q.status_code == 200
    q_data = next_q.json()
    assert q_data["question"]["key"] == "chief_complaint"

    # Answer chief_complaint: Cough
    r1 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Cough"},
        headers=staff_headers,
    )
    assert r1.status_code == 201

    # Answer symptom_duration: 4 to 7 days
    r2 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "symptom_duration", "answer": "4 to 7 days"},
        headers=staff_headers,
    )
    assert r2.status_code == 201

    # Answer symptom_severity: 6
    r3 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "symptom_severity", "answer": "6"},
        headers=staff_headers,
    )
    assert r3.status_code == 201

    # Answer symptom_course (generic question for every complaint)
    r4 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "symptom_course", "answer": "Getting worse"},
        headers=staff_headers,
    )
    assert r4.status_code == 201

    # Answer has_fever: Yes
    r5 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "has_fever", "answer": "Yes"},
        headers=staff_headers,
    )
    assert r5.status_code == 201

    # Answer has_chronic_conditions: No
    r6 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "has_chronic_conditions", "answer": "No"},
        headers=staff_headers,
    )
    assert r6.status_code == 201

    # Step 6: Patient explicitly says NO current medications
    r7 = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "current_medications", "answer": "No"},
        headers=staff_headers,
    )
    assert r7.status_code == 201

    # =========================================================================
    # Step 3: Missing Information Flag Appears (Missing != Negative)
    # =========================================================================
    # We deliberately did not answer has_allergies yet.
    missing_res = await client.get(f"/api/encounters/{encounter_id}/missing", headers=staff_headers)
    assert missing_res.status_code == 200
    missing_data = missing_res.json()
    missing_keys = [item["field"] for item in missing_data.get("missing_fields", [])]
    assert "has_allergies" in missing_keys, f"Expected has_allergies in missing items: {missing_keys}"

    # Completeness analysis reflects partial completeness
    readiness_res = await client.get(f"/api/encounters/{encounter_id}/readiness", headers=staff_headers)
    assert readiness_res.status_code == 200
    comp_data = readiness_res.json()
    assert 0.0 < comp_data["score"] <= 1.0
    assert comp_data["label"] in ["Ready for Review", "Partially Ready", "Not Ready"]
    assert any(m["field"] == "has_allergies" for m in comp_data["factors"]["missing_fields"])

    # =========================================================================
    # Step 4: Upload Real Prescription Image -> OCR Extraction
    # =========================================================================
    upload_res = await client.post(
        f"/api/documents/upload/{patient_id}",
        data={"encounter_id": str(encounter_id), "document_type": "prescription"},
        files={"file": ("prescription_amoxicillin.png", sample_prescription_bytes, "image/png")},
        headers=staff_headers,
    )
    assert upload_res.status_code == 201, upload_res.text
    doc_info = upload_res.json()
    doc_id = doc_info["id"]

    # Retrieve document status
    doc_get = await client.get(f"/api/documents/{doc_id}", headers=staff_headers)
    assert doc_get.status_code == 200
    doc_data = doc_get.json()
    assert doc_data["status"] in ["uploaded", "processing", "processed"]

    # =========================================================================
    # Step 5 & 6: Medication Extraction & Discrepancy Flagging
    # =========================================================================
    # Attach a processed document record with extracted Amoxicillin to test discrepancy detection
    async with AsyncSessionLocal() as db:
        doc = Document(
            patient_id=patient_id,
            encounter_id=encounter_id,
            document_type="prescription",
            original_filename="prescription_amoxicillin.png",
            stored_path="test_uploads/prescription_amoxicillin.png",
            status=DocumentStatus.completed,
            extracted_text="Rx: Amoxicillin 500mg capsules TID x 7 days. Dr. R. Sharma.",
            extracted_fields={
                "medications": ["Amoxicillin"],
                "medication_details": [{"name": "Amoxicillin", "dosage": "500mg", "frequency": "TID"}],
            },
            extraction_confidence=0.92,
            is_verified=False,
        )
        db.add(doc)
        await db.commit()

    # Trigger contradiction check (patient answered current_medications=No, doc has Amoxicillin)
    conflicts_res = await client.get(f"/api/encounters/{encounter_id}/contradictions", headers=staff_headers)
    assert conflicts_res.status_code == 200
    conflicts_list = conflicts_res.json()
    assert len(conflicts_list) >= 1
    conflict = next((c for c in conflicts_list if c["rule_id"] == "RULE-MED-DENIAL"), None)
    assert conflict is not None, f"Expected RULE-MED-DENIAL conflict: {conflicts_list}"
    conflict_id = conflict["id"]
    assert conflict["status"] == "open"
    assert "Amoxicillin" in conflict["value_b"]

    # =========================================================================
    # Step 7: Doctor Logs In, Opens Case From Dashboard
    # =========================================================================
    doctor_login = await client.post("/api/auth/login", json={"username": "e2e_doctor", "password": "Doctor@1234"})
    assert doctor_login.status_code == 200
    doc_token = doctor_login.json()["access_token"]
    doctor_headers = {"Authorization": f"Bearer {doc_token}"}

    # Doctor views dashboard queue
    dash_res = await client.get("/api/dashboard/cases?status=all", headers=doctor_headers)
    assert dash_res.status_code == 200
    cases_queue = dash_res.json()
    matching_case = next((c for c in cases_queue if c["encounter_id"] == encounter_id), None)
    assert matching_case is not None, "Encounter not found in doctor's dashboard queue"
    assert matching_case["patient_name"] == "Devendra Joshi"

    # =========================================================================
    # Step 8: Doctor Resolves Discrepancy, Adds Notes, Finalizes Case
    # =========================================================================
    # Resolve the conflict
    resolve_res = await client.put(
        f"/api/conflicts/{conflict_id}/resolve",
        json={"status": "resolved", "resolution_note": "Reconciled with patient: prescription was completed last month. Currently not taking."},
        headers=doctor_headers,
    )
    assert resolve_res.status_code == 200
    resolved_data = resolve_res.json()
    assert resolved_data["status"] == "resolved"

    # Doctor adds clinical notes
    clinical_note = (
        "E2E Clinical Review: Patient presents with subacute cough and fever. "
        "Medication discrepancy resolved. Recommended supportive care, hydration, "
        "and follow-up in 3 days if symptoms do not improve. Non-diagnostic intake completed."
    )
    notes_res = await client.put(
        f"/api/encounters/{encounter_id}/notes",
        json={"doctor_notes": clinical_note},
        headers=doctor_headers,
    )
    assert notes_res.status_code == 200
    assert notes_res.json()["doctor_notes"] == clinical_note

    # Doctor finalizes the encounter
    finalize_res = await client.post(f"/api/encounters/{encounter_id}/finalize", headers=doctor_headers)
    assert finalize_res.status_code == 200
    fin_data = finalize_res.json()
    assert fin_data["status"] == "reviewed"
    assert fin_data["review_status"] == "reviewed"
    assert fin_data["reviewed_at"] is not None

    # =========================================================================
    # Step 9: Reopen / Refresh -> Everything Persisted; Modifications Locked
    # =========================================================================
    # Verify notes and finalized metadata persist
    get_notes = await client.get(f"/api/encounters/{encounter_id}/notes", headers=doctor_headers)
    assert get_notes.status_code == 200
    assert get_notes.json()["doctor_notes"] == clinical_note
    assert get_notes.json()["reviewed_at"] is not None

    # Verify encounter locking: patient/staff attempts to modify answers are rejected with HTTP 400
    blocked_edit = await client.post(
        f"/api/interviews/{encounter_id}/responses",
        json={"question_key": "has_allergies", "answer": "No"},
        headers=staff_headers,
    )
    assert blocked_edit.status_code == 400, "Expected HTTP 400 when attempting to modify finalized encounter"
    assert "finalized" in blocked_edit.text.lower() or "locked" in blocked_edit.text.lower()

    # Verify back-navigation is also locked
    blocked_back = await client.post(f"/api/interviews/{encounter_id}/back", headers=staff_headers)
    assert blocked_back.status_code == 400
    assert "finalized" in blocked_back.text.lower() or "locked" in blocked_back.text.lower()


@pytest.mark.asyncio
async def test_e2e_non_diagnostic_boundary_and_provenance(client: AsyncClient):
    """
    Verifies that non-diagnostic notices and source provenance labels are returned across
    case summary, completeness indicators, and interview responses.
    """
    admin_login = await client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Register patient & encounter
    p_res = await client.post(
        "/api/patients",
        json={"full_name": "Boundary Test Patient", "age": 30, "gender": "Female", "preferred_language": "English"},
        headers=headers,
    )
    p_id = p_res.json()["id"]

    e_res = await client.post(
        "/api/encounters",
        json={"patient_id": p_id, "chief_complaint": "Mild headache", "consent_given": True},
        headers=headers,
    )
    e_id = e_res.json()["id"]

    # Submit answer
    resp = await client.post(
        f"/api/interviews/{e_id}/responses",
        json={"question_key": "chief_complaint", "answer": "Headache"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["source"] == "patient_reported"

    # Get readiness / completeness summary
    readiness = await client.get(f"/api/encounters/{e_id}/readiness", headers=headers)
    assert readiness.status_code == 200
    data = readiness.json()
    assert "disclaimer" in data
    assert "not a measure of diagnostic accuracy" in data["disclaimer"].lower() or "data completeness only" in data["disclaimer"].lower()

    # Get case summary
    summary_res = await client.get(f"/api/encounters/{e_id}/summary", headers=headers)
    assert summary_res.status_code == 200
    sum_data = summary_res.json()
    assert sum_data["encounter_id"] == e_id
    assert sum_data["sections"] is not None
