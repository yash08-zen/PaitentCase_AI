"""
services/document_processing.py
---------------------------------
Real OCR processing pipeline for printed prescriptions and medical documents.

Features:
- Image preprocessing (grayscale, contrast normalization, bilateral denoising)
- Real local OCR engine via RapidOCR (ONNX Runtime, offline, high-accuracy)
- Failure safety: corrupt or empty scans trigger 'needs_review' or 'failed'
- Original uploaded files are always preserved
- Non-blocking asynchronous execution via background task
- Detailed execution metrics (confidence, processing elapsed time)
- Provenance tagging: document_extracted_unverified
"""
import os
import time
import asyncio
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any, List

import cv2
import numpy as np
from PIL import Image

from app.database import AsyncSessionLocal

# Global OCR engine instance (lazy-loaded on first call to optimize startup time)
_ocr_engine = None


def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
            _ocr_engine = RapidOCR()
        except Exception as exc:
            print(f"[document_processing] Warning: Failed to initialize RapidOCR: {exc}")
            _ocr_engine = False
    return _ocr_engine


def preprocess_image(file_path: str) -> Optional[np.ndarray]:
    """
    Load and preprocess image for OCR clarity:
    - Grayscale conversion
    - Denoise using bilateral filter (preserves edges of characters)
    - Contrast stretching / CLAHE
    """
    if not os.path.exists(file_path):
        return None

    try:
        # Read image
        img = cv2.imread(file_path)
        if img is None:
            # Fallback to PIL in case of non-ASCII paths or special formats
            pil_img = Image.open(file_path)
            img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Apply bilateral filter to denoise while maintaining crisp character boundaries
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)

        # Enhance contrast with CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(denoised)

        return contrast_enhanced
    except Exception as err:
        print(f"[document_processing] Preprocessing fallback: {err}")
        return cv2.imread(file_path)


def run_ocr_sync(file_path: str, mime_type: str) -> Tuple[Optional[str], Dict[str, Any], Optional[float], float, str]:
    """
    Synchronous OCR execution on an image.
    Returns: (raw_text, extracted_fields, confidence, elapsed_seconds, status)
    """
    start_time = time.time()

    # Preprocess
    processed = preprocess_image(file_path)
    if processed is None:
        elapsed = round(time.time() - start_time, 3)
        return None, {"error": "Image file could not be read or decoded"}, 0.0, elapsed, "failed"

    engine = get_ocr_engine()
    if not engine:
        # Fallback if RapidOCR not available: check pytesseract
        try:
            import pytesseract
            raw_text = pytesseract.image_to_string(processed).strip()
            elapsed = round(time.time() - start_time, 3)
            status = "completed" if raw_text else "needs_review"
            return raw_text, {"engine": "pytesseract", "processing_time_seconds": elapsed}, 0.85 if raw_text else 0.0, elapsed, status
        except Exception as exc:
            elapsed = round(time.time() - start_time, 3)
            return None, {"error": f"OCR engine unavailable: {exc}"}, 0.0, elapsed, "failed"

    try:
        results, _ = engine(processed)

        elapsed = round(time.time() - start_time, 3)

        if not results:
            # Empty / blank image
            return "", {"ocr_engine": "rapidocr", "processing_time_seconds": elapsed, "line_count": 0}, 0.0, elapsed, "needs_review"

        lines: List[str] = []
        confidences: List[float] = []

        for item in results:
            # Each item format: [bounding_box, text, confidence]
            text = item[1].strip() if len(item) > 1 else ""
            conf = float(item[2]) if len(item) > 2 else 0.0
            if text:
                lines.append(text)
                confidences.append(conf)

        raw_text = "\n".join(lines).strip()
        mean_confidence = round(sum(confidences) / len(confidences), 3) if confidences else 0.0

        if not raw_text or len(raw_text) < 3:
            status = "needs_review"
        elif mean_confidence < 0.40:
            status = "needs_review"
        else:
            status = "completed"

        # Structured medication and allergy extraction
        from app.services.medication_extraction import (
            extract_medications_from_text,
            extract_allergy_mentions_from_text,
        )
        extracted_meds = extract_medications_from_text(raw_text)
        extracted_allergies = extract_allergy_mentions_from_text(raw_text)

        # Preliminary structured metadata
        metadata = {
            "ocr_engine": "rapidocr",
            "processing_time_seconds": elapsed,
            "line_count": len(lines),
            "mean_confidence": mean_confidence,
            "provenance": "document_extracted_unverified",
            "medications": [m["name"] for m in extracted_meds],
            "medication_details": extracted_meds,
            "allergies": extracted_allergies,
        }

        return raw_text, metadata, mean_confidence, elapsed, status

    except Exception as exc:
        elapsed = round(time.time() - start_time, 3)
        print(f"[document_processing] OCR exception on {file_path}: {exc}")
        return None, {"error": str(exc), "processing_time_seconds": elapsed}, 0.0, elapsed, "failed"


async def run_vision_fallback(db, doc, ocr_text: Optional[str], fields: Dict[str, Any]) -> Dict[str, Any]:
    """
    Low-confidence image (handwritten / cursive): send the page image to the
    hosted vision-capable model. Results are stored as unverified entities with
    review_status 'read_from_handwriting_verify'. In local mode (or when the
    LLM is down) nothing is sent and the document is routed to needs_review.
    """
    from app.models import AuditEvent, DocumentEntity
    from app.services.llm.interface import LLMProviderError
    from app.services.llm.manager import llm_service
    from app.services.llm.prompts import SCHEMAS, SYSTEM_PROMPTS, wrap_case_data

    fields = dict(fields)
    fields["ocr_text_before_vision"] = ocr_text or ""
    if not llm_service.vision_available:
        fields["handwriting_notice"] = (
            "Low-confidence handwritten page. The vision path is not available in local mode; "
            "manual transcription by the doctor is required."
        )
        return fields
    try:
        import base64
        with open(doc.stored_path, "rb") as img_f:
            b64_data = base64.standard_b64encode(img_f.read()).decode("utf-8")
        result, meta = await llm_service.generate(
            task="handwriting_transcription",
            system_prompt=SYSTEM_PROMPTS["handwriting_transcription"],
            user_content=wrap_case_data({"document_id": doc.id}),
            json_schema=SCHEMAS["handwriting_transcription"],
            images=[{"media_type": doc.mime_type, "base64_data": b64_data}],
            encounter_id=doc.encounter_id,
        )
    except (LLMProviderError, OSError) as exc:
        fields["vision_fallback_error"] = type(exc).__name__
        fields["handwriting_notice"] = "Vision path unavailable; manual transcription required."
        return fields

    if not result.get("transcription"):
        fields["handwriting_notice"] = "Vision path returned no text; manual transcription required."
        return fields
    fields["extraction_method"] = "vision_fallback"
    fields["vision_transcription"] = result
    fields["vision_model"] = meta.get("model_name")
    fields["vision_prompt_version"] = meta.get("prompt_version")
    fields["handwriting_notice"] = "Read from handwriting by AI - verify every value against the scan."
    if doc.encounter_id:
        for med in result.get("medications", []):
            if med.get("name"):
                db.add(DocumentEntity(
                    encounter_id=doc.encounter_id, document_id=doc.id, entity_type="medication",
                    raw_text=med["name"], value=med, grounded=False, confidence=None,
                    provenance="vision_fallback", review_status="read_from_handwriting_verify",
                ))
    if meta.get("is_external"):
        db.add(AuditEvent(
            action="LLM_EXTERNAL_CALL", resource_type="document", resource_id=str(doc.id),
            change_summary=(f"Page image sent to {meta['provider']} model {meta['model_name']} for "
                            f"handwriting transcription (prompt {meta['prompt_version']})"),
        ))
    return fields


async def process_document_async(document_id: int) -> None:
    """
    Enqueues OCR processing in the background without blocking the HTTP request/response.
    """
    asyncio.create_task(_process_worker(document_id))


async def _process_worker(document_id: int) -> None:
    """Internal background task that executes OCR and persists results to the database."""
    try:
        async with AsyncSessionLocal() as db:
            from app.models import Document
            doc = await db.get(Document, document_id)
            if not doc:
                return

            doc.status = "processing"
            await db.commit()

            # Execute OCR in a thread pool to avoid blocking the asyncio event loop
            raw_text, fields, confidence, elapsed, status = await asyncio.to_thread(
                run_ocr_sync, doc.stored_path, doc.mime_type
            )

            # Handwriting / degraded image: vision fallback (hosted only)
            is_image = bool(doc.mime_type and doc.mime_type.startswith("image/"))
            is_low_conf = (confidence is None or confidence < 0.70) or (not raw_text) or (len(raw_text.strip()) < 5)
            if is_image and is_low_conf:
                fields = await run_vision_fallback(db, doc, raw_text, fields or {})
                status = "needs_review"
                if fields.get("extraction_method") == "vision_fallback":
                    raw_text = fields["vision_transcription"]["transcription"]

            # Re-fetch or update
            doc.extracted_text = raw_text
            doc.extracted_fields = fields
            doc.extraction_confidence = confidence
            doc.status = status
            doc.processed_at = datetime.now(timezone.utc)
            await db.commit()

            # Trigger discrepancy detection if linked to an encounter
            if doc.encounter_id and status in ("completed", "needs_review"):
                try:
                    from app.services.contradiction_detection import detect_contradictions
                    await detect_contradictions(doc.encounter_id, db)
                except Exception as c_err:
                    print(f"[document_processing] Note: Discrepancy detection warning: {c_err}")

    except Exception as exc:
        print(f"[document_processing] Critical error processing document {document_id}: {exc}")
        try:
            async with AsyncSessionLocal() as db:
                from app.models import Document
                doc = await db.get(Document, document_id)
                if doc:
                    doc.status = "failed"
                    doc.extracted_fields = {"error": str(exc)}
                    await db.commit()
        except Exception:
            pass
