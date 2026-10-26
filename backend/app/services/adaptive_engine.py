"""
services/adaptive_engine.py
---------------------------
Deterministic, rule-based adaptive interview engine.

Evaluates branching rules (show_if, skip_if, conditions), prunes invalid downstream
branches upon answer modification, manages bidirectional back navigation, and calculates
real-time progress and completion.
"""
import os
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models import Question, Response, Encounter, EncounterStatus
from app.schemas import (
    QuestionOut,
    NextQuestionResponse,
    ResponseOut,
    InterviewProgressOut,
    ActivePathItem,
    SkippedPathItem,
    ReviewAnswerOut,
)

# Load canonical question bank from configuration JSON
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
QUESTION_BANK_PATH = os.path.join(DATA_DIR, "question_bank.json")

if os.path.exists(QUESTION_BANK_PATH):
    with open(QUESTION_BANK_PATH, "r", encoding="utf-8") as f:
        QUESTION_BANK = json.load(f)
else:
    QUESTION_BANK = []


class AdaptiveEngine:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def get_next_question(self, encounter_id: int) -> NextQuestionResponse:
        """Return the next unanswered applicable question for this encounter."""
        answered = await self._get_answered_map(encounter_id)
        all_questions = await self._load_questions_ordered()
        applicable = [q for q in all_questions if self._is_applicable(q, answered)]
        answered_count = sum(1 for q in applicable if q.key in answered)
        total_app = len(applicable)
        progress = (answered_count / total_app) if total_app else 0.0

        for question in applicable:
            if question.key not in answered:
                adaptive_note = None
                if question.because and (question.branching_rules or question.conditions):
                    adaptive_note = f"Follow-up added: {question.because}."
                return NextQuestionResponse(
                    question=QuestionOut.model_validate(question),
                    progress=round(progress, 3),
                    is_complete=False,
                    adaptive_note=adaptive_note,
                    answered_count=answered_count,
                    total_applicable=total_app,
                    can_go_back=answered_count > 0,
                )

        # All applicable questions answered
        return NextQuestionResponse(
            question=None,
            progress=1.0,
            is_complete=True,
            adaptive_note="All relevant questions have been completed.",
            answered_count=answered_count,
            total_applicable=total_app,
            can_go_back=answered_count > 0,
        )

    async def save_response(
        self,
        encounter_id: int,
        question_key: str,
        answer: str,
        source: str = "patient_reported",
        confirmation_status: str = "confirmed",
    ) -> ResponseOut:
        """
        Incrementally save/upsert an answer and dynamically prune dependent responses
        if earlier answers change the branching conditions.
        """
        # Find question by key
        question = await self.db.scalar(
            select(Question).where(Question.key == question_key)
        )
        if not question:
            raise HTTPException(
                status_code=404, detail=f"Question key '{question_key}' not found"
            )

        now = datetime.now(timezone.utc)

        # Upsert: update existing or create new
        existing = await self.db.scalar(
            select(Response).where(
                Response.encounter_id == encounter_id,
                Response.question_key == question_key,
            )
        )
        if existing:
            existing.answer = answer
            existing.source = source
            existing.confirmation_status = confirmation_status
            existing.answered_at = now
            resp_out_target = existing
        else:
            resp = Response(
                encounter_id=encounter_id,
                question_id=question.id,
                question_key=question_key,
                answer=answer,
                source=source,
                confirmation_status=confirmation_status,
                answered_at=now,
            )
            self.db.add(resp)
            resp_out_target = resp

        await self.db.flush()

        # Update encounter status if pending
        enc = await self.db.get(Encounter, encounter_id)
        if enc and enc.status == EncounterStatus.pending:
            enc.status = EncounterStatus.in_progress

        # Re-evaluate all questions and prune any saved responses that are no longer applicable
        answered = await self._get_answered_map(encounter_id)
        all_questions = await self._load_questions_ordered()
        q_map = {q.key: q for q in all_questions}

        existing_responses = (
            await self.db.scalars(
                select(Response).where(Response.encounter_id == encounter_id)
            )
        ).all()

        for r in existing_responses:
            if r.question_key != question_key:
                q_def = q_map.get(r.question_key)
                if q_def and not self._is_applicable(q_def, answered):
                    await self.db.delete(r)

        await self.db.commit()
        await self.db.refresh(resp_out_target)
        return ResponseOut.model_validate(resp_out_target)

    async def back_question(self, encounter_id: int) -> NextQuestionResponse:
        """
        Navigate back: remove the most recently answered applicable response
        so the patient can re-answer or alter their path.
        """
        responses = (
            await self.db.scalars(
                select(Response)
                .where(Response.encounter_id == encounter_id)
                .order_by(Response.answered_at.desc(), Response.id.desc())
            )
        ).all()

        if responses:
            last_resp = responses[0]
            await self.db.delete(last_resp)
            await self.db.commit()

        return await self.get_next_question(encounter_id)

    async def get_progress(self, encounter_id: int) -> InterviewProgressOut:
        """Calculate detailed interview progress including active and skipped paths."""
        answered = await self._get_answered_map(encounter_id)
        all_questions = await self._load_questions_ordered()

        applicable: List[Question] = []
        skipped: List[SkippedPathItem] = []

        for q in all_questions:
            if self._is_applicable(q, answered):
                applicable.append(q)
            elif q.skip_why:
                skipped.append(
                    SkippedPathItem(
                        key=q.key,
                        label=q.label or q.key,
                        skip_why=q.skip_why,
                    )
                )

        answered_count = sum(1 for q in applicable if q.key in answered)
        total_count = len(applicable)
        progress_pct = (answered_count / total_count * 100) if total_count else 0.0

        # Build active path for the UI panel
        active_path: List[ActivePathItem] = [
            ActivePathItem(
                key=q.key,
                label=q.label or q.key,
                section=q.section or q.group,
                value=answered.get(q.key),
                is_answered=q.key in answered,
                because=q.because,
            )
            for q in applicable
        ]

        # Deterministic completion: all required applicable questions answered
        required_applicable = [q for q in applicable if q.is_required]
        required_answered = sum(1 for q in required_applicable if q.key in answered)
        is_complete = (required_answered == len(required_applicable)) and (
            answered_count == total_count
        )

        return InterviewProgressOut(
            encounter_id=encounter_id,
            total_questions=total_count,
            answered_questions=answered_count,
            progress_percent=round(progress_pct, 1),
            is_complete=is_complete,
            answered_keys=list(answered.keys()),
            active_path=active_path,
            skipped_questions=skipped,
        )

    async def get_encounter_responses(
        self, encounter_id: int
    ) -> List[ReviewAnswerOut]:
        """Fetch all answered questions with human-readable labels and metadata."""
        responses = (
            await self.db.scalars(
                select(Response)
                .where(Response.encounter_id == encounter_id)
                .order_by(Response.id)
            )
        ).all()

        all_questions = await self._load_questions_ordered()
        q_map = {q.key: q for q in all_questions}

        results: List[ReviewAnswerOut] = []
        for r in responses:
            q = q_map.get(r.question_key)
            results.append(
                ReviewAnswerOut(
                    question_key=r.question_key,
                    label=q.label if q else r.question_key,
                    section=q.section if q else None,
                    text=q.text if q else r.question_key,
                    answer=r.answer,
                    source=r.source or "patient_reported",
                    confirmation_status=r.confirmation_status or "confirmed",
                    answered_at=r.answered_at,
                )
            )
        return results

    async def complete_interview(self, encounter_id: int) -> InterviewProgressOut:
        """Mark interview complete after verifying all required questions are answered."""
        progress = await self.get_progress(encounter_id)
        all_questions = await self._load_questions_ordered()
        answered = await self._get_answered_map(encounter_id)

        applicable = [q for q in all_questions if self._is_applicable(q, answered)]
        missing_required = [
            q.label or q.key for q in applicable if q.is_required and q.key not in answered
        ]
        if missing_required:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot complete interview: required questions not answered: {', '.join(missing_required)}",
            )

        enc = await self.db.get(Encounter, encounter_id)
        if enc:
            enc.status = EncounterStatus.needs_review
            await self.db.commit()

        return progress

    # ------------------------------------------------------------------
    # Internals: Rule Evaluation & Applicability
    # ------------------------------------------------------------------

    async def _load_questions_ordered(self) -> List[Question]:
        return (
            await self.db.scalars(select(Question).order_by(Question.order))
        ).all()

    async def _get_answered_map(self, encounter_id: int) -> Dict[str, str]:
        responses = (
            await self.db.scalars(
                select(Response).where(Response.encounter_id == encounter_id)
            )
        ).all()
        return {r.question_key: (r.answer or "").strip() for r in responses}

    def _evaluate_rule(self, rule_dict: Dict[str, Any], answered: Dict[str, str]) -> bool:
        """Evaluate a single rule dictionary against current answers."""
        key = rule_dict.get("question_key")
        if not key:
            return True

        val = answered.get(key, "").strip()
        if not val:
            return False

        val_lower = val.lower()

        # 1. equals
        if "equals" in rule_dict:
            target = str(rule_dict["equals"]).strip().lower()
            return val_lower == target

        # 2. in
        if "in" in rule_dict:
            targets = [str(t).strip().lower() for t in rule_dict["in"]]
            # Check individual token matches (for multi-choice or single choice)
            tokens = [t.strip().lower() for t in val.split(",")]
            return any(t in tokens or t == val_lower for t in targets)

        # 3. contains
        if "contains" in rule_dict:
            return str(rule_dict["contains"]).strip().lower() in val_lower

        # 4. not_equals
        if "not_equals" in rule_dict:
            return val_lower != str(rule_dict["not_equals"]).strip().lower()

        # 5. answer_contains (legacy support)
        if "answer_contains" in rule_dict:
            return str(rule_dict["answer_contains"]).strip().lower() in val_lower

        return True

    def _is_applicable(self, question: Question, answered: Dict[str, str]) -> bool:
        """
        Deterministic branch evaluation.
        A question applies if:
          1. branching_rules['show_if'] evaluates to True (if specified).
          2. branching_rules['skip_if'] does NOT evaluate to True (if specified).
          3. legacy conditions are all satisfied (if specified and no show_if).
        """
        rules = question.branching_rules
        if rules and isinstance(rules, dict):
            show_if = rules.get("show_if")
            if show_if and isinstance(show_if, dict):
                if not self._evaluate_rule(show_if, answered):
                    return False

            skip_if = rules.get("skip_if")
            if skip_if and isinstance(skip_if, dict):
                if self._evaluate_rule(skip_if, answered):
                    return False

        conditions = question.conditions
        if conditions and isinstance(conditions, list):
            # Only evaluate conditions if show_if was not provided
            if not (rules and isinstance(rules, dict) and "show_if" in rules):
                for cond in conditions:
                    key = cond.get("question_key")
                    contains = cond.get("answer_contains", "").lower()
                    answered_val = answered.get(key, "").lower()
                    if contains not in answered_val:
                        return False

        return True
