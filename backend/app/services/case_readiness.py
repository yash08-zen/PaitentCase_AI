"""
services/case_readiness.py
--------------------------
Calculates a transparent case-completeness score.

Score factors (configurable weights):
  1. Required fields answered         (40 %)
  2. No open critical missing fields  (30 %)
  3. No unresolved conflicts          (20 %)
  4. No open review flags             (10 %)

The score is a data-completeness indicator ONLY.
It is NOT a measure of diagnostic accuracy or patient health status.
"""
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import Response, Conflict, ReviewFlag
from app.services.missing_information import detect_missing, REQUIRED_FIELDS


DISCLAIMER = (
    "This score reflects case data completeness only. "
    "It is NOT a measure of diagnostic accuracy or patient health."
)


async def calculate_readiness(encounter_id: int, db: AsyncSession) -> Dict[str, Any]:
    # Gather answers
    responses = (
        await db.scalars(select(Response).where(Response.encounter_id == encounter_id))
    ).all()
    answered = {r.question_key: (r.answer or "").strip() for r in responses}

    # Factor 1: required fields answered
    total_required = len(REQUIRED_FIELDS)
    missing_fields = detect_missing(answered)
    answered_required = total_required - len(missing_fields)
    required_score = answered_required / total_required if total_required else 1.0

    # Factor 2: no critical missing fields
    critical_missing = [m for m in missing_fields if m.is_critical]
    critical_score = 1.0 if not critical_missing else max(0.0, 1.0 - len(critical_missing) * 0.2)

    # Factor 3: no unresolved conflicts
    open_conflicts = await db.scalar(
        select(func.count(Conflict.id)).where(
            Conflict.encounter_id == encounter_id, Conflict.status == "open"
        )
    ) or 0
    conflict_score = 1.0 if open_conflicts == 0 else max(0.0, 1.0 - open_conflicts * 0.3)

    # Factor 4: no open review flags
    open_flags = await db.scalar(
        select(func.count(ReviewFlag.id)).where(
            ReviewFlag.encounter_id == encounter_id, ReviewFlag.status == "open"
        )
    ) or 0
    flag_score = 1.0 if open_flags == 0 else max(0.0, 1.0 - open_flags * 0.25)

    # Weighted composite
    composite = (
        required_score * 0.40
        + critical_score * 0.30
        + conflict_score * 0.20
        + flag_score * 0.10
    )
    composite = round(min(1.0, max(0.0, composite)), 3)

    if composite >= 0.80:
        label = "Ready for Review"
    elif composite >= 0.50:
        label = "Partially Ready"
    else:
        label = "Not Ready"

    return {
        "score": composite,
        "label": label,
        "factors": {
            "required_fields_answered": f"{answered_required}/{total_required}",
            "required_fields_score": round(required_score, 3),
            "critical_missing_score": round(critical_score, 3),
            "open_conflicts": open_conflicts,
            "conflict_score": round(conflict_score, 3),
            "open_flags": open_flags,
            "flag_score": round(flag_score, 3),
            "missing_fields": [m.model_dump() for m in missing_fields],
        },
        "disclaimer": DISCLAIMER,
    }
