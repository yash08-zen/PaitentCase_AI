import os
import asyncio
import pytest
from httpx import AsyncClient

TEST_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "test_images")


@pytest.mark.asyncio
async def test_real_prescription_upload_and_async_ocr(client: AsyncClient, auth_headers: dict):
    """DoD 1: Real test image uploaded via API, processed by backend OCR engine, and extracted text stored."""
    # 1. Create patient and encounter
    p_res = await client.post("/api/patients", json={"full_name": "OCR Test Patient", "age": 45, "gender": "Male"}, headers=auth_headers)
    patient_id = p_res.json()["id"]
    e_res = await client.post("/api/encounters", json={"patient_id": patient_id, "consent_given": True}, headers=auth_headers)
    enc_id = e_res.json()["id"]

    # 2. Upload real clear prescription image
    img_path = os.path.join(TEST_IMAGES_DIR, "rx_sample_1_amoxicillin.png")
    assert os.path.exists(img_path), f"Test image not found at {img_path}"

    with open(img_path, "rb") as f:
        img_bytes = f.read()

    upload_res = await client.post(
        f"/api/documents/upload/{patient_id}",
        files={"file": ("rx_sample_1_amoxicillin.png", img_bytes, "image/png")},
        data={"encounter_id": str(enc_id), "document_type": "prescription"},
        headers=auth_headers,
    )
    assert upload_res.status_code == 201
    doc_data = upload_res.json()
    doc_id = doc_data["id"]
    assert doc_data["status"] in ("pending", "processing", "uploaded")

    # 3. Poll extraction endpoint until OCR completes (max 15 seconds)
    completed_doc = None
    for _ in range(30):
        await asyncio.sleep(0.5)
        ext_res = await client.get(f"/api/documents/{doc_id}/extraction", headers=auth_headers)
        assert ext_res.status_code == 200
        data = ext_res.json()
        if data["status"] in ("completed", "needs_review", "failed"):
            completed_doc = data
            break

    assert completed_doc is not None, "OCR did not finish within timeout"
    assert completed_doc["status"] == "completed"
    assert completed_doc["extracted_text"] is not None
    assert "amoxicillin" in completed_doc["extracted_text"].lower()
    assert "paracetamol" in completed_doc["extracted_text"].lower()
    assert completed_doc["extraction_confidence"] is not None
    assert completed_doc["extraction_confidence"] >= 0.80
    assert completed_doc["provenance_label"] == "document_extracted_unverified"


@pytest.mark.asyncio
async def test_unsupported_file_type_and_content_spoofing_rejected(client: AsyncClient, auth_headers: dict):
    """DoD 2: Unsupported file types and content-spoofed files are rejected with 415."""
    p_res = await client.post("/api/patients", json={"full_name": "Reject Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]

    # Case A: Content sniffing rejects an executable even if mime_type says image/jpeg
    fake_exe_path = os.path.join(TEST_IMAGES_DIR, "malware_fake.exe")
    with open(fake_exe_path, "rb") as f:
        exe_bytes = f.read()

    res_spoofed = await client.post(
        f"/api/documents/upload/{patient_id}",
        files={"file": ("disguised_photo.jpg", exe_bytes, "image/jpeg")},
        data={"document_type": "prescription"},
        headers=auth_headers,
    )
    assert res_spoofed.status_code == 415

    # Case B: Text file rejected
    res_txt = await client.post(
        f"/api/documents/upload/{patient_id}",
        files={"file": ("notes.txt", b"plain text content", "text/plain")},
        data={"document_type": "prescription"},
        headers=auth_headers,
    )
    assert res_txt.status_code == 415


@pytest.mark.asyncio
async def test_oversize_files_rejected(client: AsyncClient, auth_headers: dict):
    """DoD 2: Oversize files are rejected with 413."""
    p_res = await client.post("/api/patients", json={"full_name": "Oversize Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]

    # 21 MB dummy payload (limit is 20 MB)
    large_payload = b"0" * (21 * 1024 * 1024)
    res = await client.post(
        f"/api/documents/upload/{patient_id}",
        files={"file": ("large_scan.png", large_payload, "image/png")},
        data={"document_type": "prescription"},
        headers=auth_headers,
    )
    assert res.status_code == 413
    assert "exceeds" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_blank_image_sets_needs_review_and_preserves_upload(client: AsyncClient, auth_headers: dict):
    """DoD 3: Blank/empty image safely handled -> sets needs_review, keeps upload intact, never crashes."""
    p_res = await client.post("/api/patients", json={"full_name": "Blank Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]

    blank_path = os.path.join(TEST_IMAGES_DIR, "blank_empty.png")
    with open(blank_path, "rb") as f:
        blank_bytes = f.read()

    upload_res = await client.post(
        f"/api/documents/upload/{patient_id}",
        files={"file": ("blank_empty.png", blank_bytes, "image/png")},
        data={"document_type": "prescription"},
        headers=auth_headers,
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    # Poll until OCR finishes
    final_data = None
    for _ in range(30):
        await asyncio.sleep(0.5)
        ext_res = await client.get(f"/api/documents/{doc_id}/extraction", headers=auth_headers)
        data = ext_res.json()
        if data["status"] in ("needs_review", "completed", "failed"):
            final_data = data
            break

    assert final_data is not None
    assert final_data["status"] == "needs_review"

    # Verify original file remains intact on disk
    file_res = await client.get(f"/api/documents/{doc_id}/file", headers=auth_headers)
    assert file_res.status_code == 200
    assert len(file_res.content) == len(blank_bytes)


@pytest.mark.asyncio
async def test_uploaded_files_not_accessible_without_authorization(client: AsyncClient, auth_headers: dict):
    """DoD 5: Uploaded files cannot be accessed without authorization."""
    # Create patient 1 and upload document
    p1 = await client.post("/api/patients", json={"full_name": "Auth File Patient"}, headers=auth_headers)
    p1_id = p1.json()["id"]

    img_path = os.path.join(TEST_IMAGES_DIR, "rx_sample_1_amoxicillin.png")
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    up = await client.post(
        f"/api/documents/upload/{p1_id}",
        files={"file": ("rx.png", img_bytes, "image/png")},
        headers=auth_headers,
    )
    doc_id = up.json()["id"]

    # 1. Direct access with NO auth token returns 401
    unauth_res = await client.get(f"/api/documents/{doc_id}/file")
    assert unauth_res.status_code == 401

    # 2. Direct access by unauthorized patient returns 403
    # Create second patient user
    u2 = await client.post(
        "/api/auth/register",
        json={"username": "patient_other_m6", "email": "pother_m6@test.com", "password": "Password@123", "role": "patient"},
        headers=auth_headers,
    )
    p2 = await client.post("/api/patients", json={"full_name": "Other Patient", "user_id": u2.json()["id"]}, headers=auth_headers)
    p2_login = await client.post("/api/auth/login", json={"username": "patient_other_m6", "password": "Password@123"})
    p2_headers = {"Authorization": f"Bearer {p2_login.json()['access_token']}"}

    forbidden_res = await client.get(f"/api/documents/{doc_id}/file", headers=p2_headers)
    assert forbidden_res.status_code == 403

    # 3. Authorized doctor or admin returns 200
    doctor_res = await client.get(f"/api/documents/{doc_id}/file", headers=auth_headers)
    assert doctor_res.status_code == 200
    assert len(doctor_res.content) == len(img_bytes)


@pytest.mark.asyncio
async def test_ocr_test_set_evaluation_and_timing(client: AsyncClient, auth_headers: dict):
    """DoD 6 & 7: Test set of 5 clear printed prescription images evaluated, all under 15s."""
    p_res = await client.post("/api/patients", json={"full_name": "Evaluation Patient"}, headers=auth_headers)
    patient_id = p_res.json()["id"]

    samples = [
        ("rx_sample_1_amoxicillin.png", "amoxicillin"),
        ("rx_sample_2_metformin.png", "metformin"),
        ("rx_sample_3_atorvastatin.png", "atorvastatin"),
        ("rx_sample_4_azithromycin.png", "azithromycin"),
        ("rx_sample_5_pantoprazole.png", "pantoprazole"),
    ]

    for filename, expected_med in samples:
        path = os.path.join(TEST_IMAGES_DIR, filename)
        with open(path, "rb") as f:
            content = f.read()

        up = await client.post(
            f"/api/documents/upload/{patient_id}",
            files={"file": (filename, content, "image/png")},
            data={"document_type": "prescription"},
            headers=auth_headers,
        )
        assert up.status_code == 201
        doc_id = up.json()["id"]

        # Wait for processing
        final = None
        for _ in range(30):
            await asyncio.sleep(0.5)
            ext = await client.get(f"/api/documents/{doc_id}/extraction", headers=auth_headers)
            d = ext.json()
            if d["status"] in ("completed", "needs_review", "failed"):
                final = d
                break

        assert final is not None, f"Timeout processing {filename}"
        assert final["status"] == "completed", f"Status for {filename} was {final['status']}"
        assert expected_med in final["extracted_text"].lower(), f"Expected '{expected_med}' in {filename}"
        assert final["extraction_confidence"] >= 0.85

        # Timing check: target under 15 seconds
        elapsed = final.get("processing_time_seconds")
        if elapsed is not None:
            assert elapsed < 15.0, f"OCR took {elapsed}s, exceeded 15s threshold"
