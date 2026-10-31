"""
routers/interviews.py
---------------------
Adaptive interview endpoints:
  - GET  /{encounter_id}/next-question : returns next question & branch note
  - POST /{encounter_id}/responses     : incremental answer upsert & branch re-eval
  - POST /{encounter_id}/back          : pop last answer and navigate back
  - GET  /{encounter_id}/progress      : real-time progress, active path, skipped questions
  - POST /{encounter_id}/resume        : resume interrupted session
  - GET  /{encounter_id}/answers       : list of all submitted answers for review screen
  - POST /{encounter_id}/complete      : validate required questions and finalize interview
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Encounter, Patient, User
from app.schemas import (
    NextQuestionResponse,
    SubmitResponseRequest,
    ResponseOut,
    InterviewProgressOut,
    ReviewAnswerOut,
)
from app.services.adaptive_engine import AdaptiveEngine
from app.services.auto_analysis import request_analysis
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/interviews", tags=["Interviews"])


async def _get_encounter_or_404(
    encounter_id: int, db: AsyncSession, current_user: User
) -> Encounter:
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(status_code=404, detail="Encounter not found")
    user_role_str = (
        current_user.role.value
        if hasattr(current_user.role, "value")
        else str(current_user.role)
    )
    if user_role_str == "patient":
        patient = await db.get(Patient, enc.patient_id)
        if not patient or patient.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Forbidden: patients may only access their own encounter interview",
            )

    if not enc.consent_given:
        raise HTTPException(
            status_code=400,
            detail="Informed consent must be recorded before starting or resuming the interview.",
        )
    return enc


@router.get("/{encounter_id}/next-question", response_model=NextQuestionResponse)
async def next_question(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_encounter_or_404(encounter_id, db, current_user)
    engine = AdaptiveEngine(db)
    return await engine.get_next_question(encounter_id)


@router.post("/{encounter_id}/responses", response_model=ResponseOut, status_code=201)
async def submit_response(
    encounter_id: int,
    payload: SubmitResponseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enc = await _get_encounter_or_404(encounter_id, db, current_user)
    enc_status = enc.status.value if hasattr(enc.status, "value") else str(enc.status)
    if enc_status == "reviewed":
        raise HTTPException(
            status_code=400,
            detail="Cannot modify responses for a finalized encounter",
        )
    engine = AdaptiveEngine(db)
    saved = await engine.save_response(
        encounter_id=encounter_id,
        question_key=payload.question_key,
        answer=payload.answer,
        source=payload.source or "patient_reported",
        confirmation_status=payload.confirmation_status or "confirmed",
    )
    request_analysis(encounter_id, "interview_answer")  # debounced automatic analysis
    return saved


@router.post("/{encounter_id}/back", response_model=NextQuestionResponse)
async def back_question(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enc = await _get_encounter_or_404(encounter_id, db, current_user)
    enc_status = enc.status.value if hasattr(enc.status, "value") else str(enc.status)
    if enc_status == "reviewed":
        raise HTTPException(
            status_code=400,
            detail="Cannot modify responses for a finalized encounter",
        )
    engine = AdaptiveEngine(db)
    return await engine.back_question(encounter_id)


@router.get("/{encounter_id}/progress", response_model=InterviewProgressOut)
async def get_progress(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_encounter_or_404(encounter_id, db, current_user)
    engine = AdaptiveEngine(db)
    return await engine.get_progress(encounter_id)


@router.post("/{encounter_id}/resume", response_model=NextQuestionResponse)
async def resume_interview(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    enc = await _get_encounter_or_404(encounter_id, db, current_user)
    if enc.status == "pending":
        enc.status = "in_progress"
        await db.commit()
    engine = AdaptiveEngine(db)
    return await engine.get_next_question(encounter_id)


@router.get("/{encounter_id}/answers", response_model=List[ReviewAnswerOut])
async def get_answers(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_encounter_or_404(encounter_id, db, current_user)
    engine = AdaptiveEngine(db)
    return await engine.get_encounter_responses(encounter_id)


@router.post("/{encounter_id}/complete", response_model=InterviewProgressOut)
async def complete_interview(
    encounter_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_encounter_or_404(encounter_id, db, current_user)
    engine = AdaptiveEngine(db)
    progress = await engine.complete_interview(encounter_id)
    request_analysis(encounter_id, "interview_completed", delay=0)
    return progress
