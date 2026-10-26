"""
routers/conflicts.py
--------------------
API routes for clinical conflict and discrepancy management.

Endpoints:
  GET /api/conflicts: List conflicts for an encounter (filtered by status)
  GET /api/conflicts/{id}: Get detailed discrepancy record
  PUT /api/conflicts/{id}/resolve: Doctor/Clinician reconciles discrepancy with audit trail
"""
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Conflict, ConflictStatus, Encounter, Patient, User
from app.schemas import ConflictOut, ConflictResolveRequest
from app.dependencies import require_roles, get_current_user
from app.services.audit import log_audit_event
from app.services.contradiction_detection import detect_contradictions

router = APIRouter(prefix="/api/conflicts", tags=["Conflicts"])


@router.get("", response_model=List[ConflictOut])
async def list_conflicts(
    encounter_id: int = Query(..., description="ID of the encounter"),
    status: Optional[str] = Query(None, description="Filter by status: open | resolved | dismissed"),
    refresh: bool = Query(False, description="Whether to re-evaluate discrepancy rules before returning"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "staff", "admin")),
):
    """
    List all clinical discrepancies and contradictions detected for an encounter.
    Optionally re-evaluates rules if refresh=True.
    """
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")

    if refresh:
        await detect_contradictions(encounter_id, db)

    query = select(Conflict).where(Conflict.encounter_id == encounter_id)
    if status:
        query = query.where(Conflict.status == status)
    query = query.order_by(Conflict.created_at.desc())

    conflicts = (await db.scalars(query)).all()
    return list(conflicts)


@router.get("/{conflict_id}", response_model=ConflictOut)
async def get_conflict(
    conflict_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "staff", "admin")),
):
    """Fetch details of a single conflict by ID."""
    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict record not found")
    return conflict


@router.put("/{conflict_id}/resolve", response_model=ConflictOut)
async def resolve_conflict(
    conflict_id: int,
    req: ConflictResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
):
    """
    Clinician reconciles or dismisses an information discrepancy.
    Requires doctor or admin role.
    Records resolution note, timestamp, and audit event.
    """
    conflict = await db.get(Conflict, conflict_id)
    if not conflict:
        raise HTTPException(status_code=404, detail="Conflict record not found")

    enc = await db.get(Encounter, conflict.encounter_id)

    target_status = ConflictStatus(req.status)
    conflict.status = target_status
    conflict.resolution_note = req.resolution_note.strip()
    conflict.resolved_by = current_user.id
    conflict.resolved_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(conflict)

    # Record audit event
    await log_audit_event(
        db=db,
        action="CONFLICT_RESOLVED",
        actor=current_user,
        resource_type="conflict",
        resource_id=str(conflict.id),
        change_summary=(
            f"Resolved conflict #{conflict.id} (Rule: {conflict.rule_id}, Field: {conflict.field}) "
            f"as {target_status.value}. Note: {req.resolution_note}"
        ),
    )

    return conflict
