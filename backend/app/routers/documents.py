"""
routers/documents.py
--------------------
Document upload, secure file retrieval, OCR extraction status polling, and review endpoints.
All files are stored in protected storage outside the web root with non-guessable filenames.
Validates file type by content inspection (not just client-supplied MIME or extension).
Enforces least-privilege role boundaries and patient record-level access.
"""
import io
import os
import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from PIL import Image

from app.database import get_db
from app.models import Document, Patient, Encounter, User
from app.schemas import DocumentOut, DocumentExtractionOut
from app.core.config import settings
from app.dependencies import get_current_user, require_roles
from app.services.document_processing import process_document_async
from app.core.rate_limiter import rate_limit

router = APIRouter(prefix="/api/documents", tags=["Documents"])

ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/tiff",
    "application/pdf",
}

# Image extensions recognized
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def _get_upload_dir() -> str:
    path = os.path.abspath(settings.UPLOAD_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def validate_file_content_by_sniffing(content: bytes, filename: str, mime_type: str) -> str:
    """
    Validate file content by reading magic bytes / decoding with PIL.
    Prevents content spoofing (e.g. uploading an executable disguised as an image).
    """
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty (0 bytes).",
        )

    # Check for PDF
    if content.startswith(b"%PDF"):
        return "application/pdf"

    # Check for executable magic bytes (e.g. MZ)
    if content.startswith(b"MZ") or content.startswith(b"\x7fELF"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type: Executable files are strictly prohibited.",
        )

    # Validate image decoding via Pillow
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()
        format_name = (img.format or "").lower()
        if format_name in ("jpeg", "jpg"):
            return "image/jpeg"
        elif format_name == "png":
            return "image/png"
        elif format_name == "webp":
            return "image/webp"
        elif format_name in ("tiff", "tif"):
            return "image/tiff"
        else:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported image format: {format_name}. Supported formats: JPEG, PNG, WebP, TIFF.",
            )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Invalid file content: The uploaded file cannot be identified or decoded as a valid image.",
        )


@router.post(
    "/upload/{patient_id}",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, bucket="doc_upload"))],
)
async def upload_document(
    patient_id: int,
    file: UploadFile = File(...),
    encounter_id: Optional[int] = Form(None),
    document_type: str = Form("prescription"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a prescription or medical document.
    Validates file type by content inspection and file size.
    Stores with a non-guessable UUID in protected storage.
    Enqueues OCR processing in the background.
    """
    patient = await db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        if patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only upload documents to their own record",
            )

    if encounter_id is not None:
        enc = await db.get(Encounter, encounter_id)
        if not enc or enc.patient_id != patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid encounter_id: Encounter does not belong to this patient",
            )

    # 1. Check client-reported MIME type
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WebP, TIFF, PDF.",
        )

    # 2. Read content and enforce size limits
    content = await file.read()
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size limit of {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # 3. Content sniffing / magic byte validation
    verified_mime = validate_file_content_by_sniffing(content, file.filename or "", file.content_type or "")

    # 4. Save file with a non-guessable UUID filename in protected storage
    ext = os.path.splitext(file.filename or "doc")[1].lower()
    if not ext or ext not in IMAGE_EXTENSIONS and ext != ".pdf":
        ext = ".png" if verified_mime == "image/png" else ".jpg"

    stored_name = f"{uuid.uuid4().hex}{ext}"
    upload_dir = _get_upload_dir()
    stored_path = os.path.join(upload_dir, stored_name)

    with open(stored_path, "wb") as f:
        f.write(content)

    doc = Document(
        patient_id=patient_id,
        encounter_id=encounter_id,
        document_type=document_type,
        original_filename=file.filename or "unknown",
        stored_path=stored_path,
        file_size_bytes=len(content),
        mime_type=verified_mime,
        status="pending",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # 5. Trigger asynchronous real OCR pipeline
    await process_document_async(doc.id)

    return doc


@router.get("", response_model=List[DocumentOut])
async def list_documents(
    encounter_id: Optional[int] = Query(None),
    patient_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List uploaded documents filtered by encounter or patient with record-level scoping."""
    query = select(Document).order_by(Document.uploaded_at.desc())
    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    if user_role_str == "patient":
        query = query.join(Patient, Document.patient_id == Patient.id).where(Patient.user_id == current_user.id)
    else:
        if patient_id:
            query = query.where(Document.patient_id == patient_id)

    if encounter_id:
        query = query.where(Document.encounter_id == encounter_id)

    return (await db.scalars(query)).all()


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve document metadata and current OCR processing status."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        patient = await db.get(Patient, doc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only access their own documents",
            )
    return doc


@router.get("/{document_id}/extraction", response_model=DocumentExtractionOut)
async def get_extraction(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve extracted OCR text, confidence metrics, and processing metadata."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        patient = await db.get(Patient, doc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only access their own documents",
            )

    elapsed = doc.extracted_fields.get("processing_time_seconds") if isinstance(doc.extracted_fields, dict) else None

    return DocumentExtractionOut(
        document_id=doc.id,
        status=doc.status.value if hasattr(doc.status, "value") else str(doc.status),
        extracted_text=doc.extracted_text,
        extracted_fields=doc.extracted_fields,
        extraction_confidence=doc.extraction_confidence,
        is_verified=doc.is_verified,
        processing_time_seconds=elapsed,
        provenance_label="document_extracted_unverified",
    )


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Secure file retrieval endpoint.
    Guarantees uploaded files are never accessible publicly without authentication.
    Validates path traversal safety.
    """
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    user_role_str = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if user_role_str == "patient":
        patient = await db.get(Patient, doc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: patients may only access their own uploaded files",
            )

    # Path traversal safety check
    abs_stored = os.path.abspath(doc.stored_path)
    abs_upload_dir = _get_upload_dir()
    if not abs_stored.startswith(abs_upload_dir) or not os.path.exists(abs_stored):
        raise HTTPException(status_code=404, detail="Requested file not found on disk")

    return FileResponse(
        path=abs_stored,
        media_type=doc.mime_type or "application/octet-stream",
        filename=doc.original_filename,
    )


@router.post("/{document_id}/review")
async def review_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """Clinician review and verification of document extraction."""
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.is_verified = True
    doc.status = "reviewed"
    await db.commit()
    return {"ok": True, "message": "Document marked as reviewed"}
