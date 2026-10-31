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

            # Check for Handwriting / Degraded Image Vision Fallback
            is_image = bool(doc.mime_type and doc.mime_type.startswith("image/"))
            is_low_conf = (confidence is None or confidence < 0.70) or (not raw_text) or (len(raw_text.strip()) < 5)

            if is_image and is_low_conf:
                from app.core.config import settings
                if not fields:
                    fields = {}
                if settings.LLM_PROVIDER == "hosted":
                    try:
                        import base64
                        with open(doc.stored_path, "rb") as img_f:
                            b64_data = base64.b64encode(img_f.read()).decode("utf-8")
                        from app.services.llm.manager import llm_service
                        vision_result, _ = await llm_service.generate(
                            task="handwriting_transcription",
                            system_prompt=(
                                "Transcribe the medical handwriting in this image exactly as written. "
                                "Extract: patient info (if visible), medications with dose/frequency, "
                                "lab test names and values, doctor's notes, dates. If a word is illegible, "
                                "write [illegible]. Do NOT guess."
                            ),
                            user_content="Transcribe handwritten medical prescription or clinical note image accurately.",
                            json_schema={
                                "type": "object",
                                "properties": {
                                    "transcription": {"type": "string"},
                                    "medications": {"type": "array", "items": {"type": "object"}},
                                    "labs": {"type": "array", "items": {"type": "object"}},
                                    "notes": {"type": "string"}
                                },
                                "required": ["transcription"]
                            },
                            images=[{"mime_type": doc.mime_type, "data": b64_data}],
                            encounter_id=doc.encounter_id
                        )
                        if vision_result and vision_result.get("transcription"):
                            raw_text = vision_result["transcription"]
                            fields["extraction_method"] = "vision_fallback"
                            fields["vision_transcription"] = vision_result
                            status = "needs_review"

                            from app.models import DocumentEntity
                            for med in vision_result.get("medications", []):
                                if med.get("name"):
                                    db.add(DocumentEntity(
                                        encounter_id=doc.encounter_id,
                                        document_id=doc.id,
                                        entity_type="medication",
                                        raw_text=med["name"],
                                        value=med,
                                        grounded=True,
                                        confidence=0.88,
                                        provenance="vision_fallback"
                                    ))
                    except Exception as vexc:
                        print(f"[document_processing] Vision fallback failed: {vexc}")
                        fields["vision_fallback_error"] = str(vexc)
                        status = "needs_review"
                else:
                    status = "needs_review"
                    fields["handwriting_notice"] = (
                        "Handwritten document requires doctor manual transcription "
                        "(local mode does not run large vision models; upgrade to hosted or transcribe manually)"
                    )

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
