"""
Interview Query Repository — Read-Only Data Access Layer

Provides read-optimised queries for:
- Exchange listing with section filtering
- Section-level progress calculation
- Submission listing with pagination
- Exchange count/existence checks

Reuses existing ORM models (NOT duplicated):
- ``InterviewSubmissionModel``   → app.interview.session.persistence.models
- ``InterviewExchangeModel``     → app.interview.session.persistence.models

Does NOT handle:
- State transitions (→ SubmissionRepository)
- Exchange creation (→ InterviewExchangeRepository)
- Progress tracking writes (→ ProgressTracker)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.interview.session.persistence.models import (
    InterviewExchangeModel,
    InterviewSubmissionModel,
)
from app.shared.errors import NotFoundError

logger = logging.getLogger(__name__)


class InterviewQueryRepository:
    """
    Read-only query repository for the interview API layer.

    Provides read optimisation:
    - Eager loading (joinedload) for submissions + exchanges
    - Section grouping via JSONB queries
    - Pagination support
    - Count queries for progress

    Thread safety: Uses request-scoped SQLAlchemy session.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ────────────────────────────────────────────────────────────
    # Submission Queries
    # ────────────────────────────────────────────────────────────

    def get_submission_by_id(
        self,
        submission_id: int,
        with_exchanges: bool = False,
    ) -> InterviewSubmissionModel:
        """
        Fetch submission by primary key.

        Args:
            submission_id: Submission ID.
            with_exchanges: Eagerly load exchanges if True.

        Returns:
            InterviewSubmissionModel.

        Raises:
            NotFoundError: Submission does not exist.
        """
        query = self._session.query(InterviewSubmissionModel).filter(
            InterviewSubmissionModel.id == submission_id
        )
        if with_exchanges:
            query = query.options(
                joinedload(InterviewSubmissionModel.exchanges)
            )

        sub = query.first()
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)
        return sub

    def get_submission_for_candidate(
        self,
        submission_id: int,
        candidate_id: int,
        with_exchanges: bool = False,
    ) -> InterviewSubmissionModel:
        """
        Fetch submission scoped to a candidate.

        Args:
            submission_id: Submission ID.
            candidate_id: Authenticated candidate's user ID.
            with_exchanges: Eagerly load exchanges if True.

        Returns:
            InterviewSubmissionModel.

        Raises:
            NotFoundError: Submission not found or not owned by candidate.
        """
        query = self._session.query(InterviewSubmissionModel).filter(
            InterviewSubmissionModel.id == submission_id,
            InterviewSubmissionModel.candidate_id == candidate_id,
        )
        if with_exchanges:
            query = query.options(
                joinedload(InterviewSubmissionModel.exchanges)
            )

        sub = query.first()
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)
        return sub

    def list_submissions_by_candidate(
        self,
        candidate_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InterviewSubmissionModel]:
        """
        List submissions for a candidate with optional status filter and pagination.

        Args:
            candidate_id: Candidate's user ID.
            status: Optional status filter.
            limit: Maximum records to return.
            offset: Pagination offset.

        Returns:
            List of InterviewSubmissionModel.
        """
        query = self._session.query(InterviewSubmissionModel).filter(
            InterviewSubmissionModel.candidate_id == candidate_id,
        )

        if status:
            query = query.filter(InterviewSubmissionModel.status == status)

        return (
            query.order_by(InterviewSubmissionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    # ────────────────────────────────────────────────────────────
    # Exchange Queries
    # ────────────────────────────────────────────────────────────

    def list_exchanges(
        self,
        submission_id: int,
        section: Optional[str] = None,
        include_responses: bool = True,
    ) -> List[InterviewExchangeModel]:
        """
        List exchanges for a submission with optional section filter.

        Args:
            submission_id: Submission ID.
            section: Optional section name filter (matches content_metadata.section_name).
            include_responses: If False, response columns are not loaded
                               (currently returns full model; filtering can be done at DTO level).

        Returns:
            List of InterviewExchangeModel ordered by sequence_order.
        """
        query = self._session.query(InterviewExchangeModel).filter(
            InterviewExchangeModel.interview_submission_id == submission_id,
        )

        if section:
            query = query.filter(
                InterviewExchangeModel.content_metadata["section_name"].astext == section,
            )

        return query.order_by(InterviewExchangeModel.sequence_order).all()

    def count_exchanges(self, submission_id: int) -> int:
        """Count total exchanges for a submission."""
        return (
            self._session.query(InterviewExchangeModel)
            .filter(InterviewExchangeModel.interview_submission_id == submission_id)
            .count()
        )

    # ────────────────────────────────────────────────────────────
    # Progress Queries
    # ────────────────────────────────────────────────────────────

    def get_section_progress(
        self,
        submission_id: int,
    ) -> Dict[str, Any]:
        """
        Calculate section-level progress for a submission.

        Reads the template_structure_snapshot from the submission and compares
        it against completed exchanges to produce per-section progress.

        Args:
            submission_id: Submission ID.

        Returns:
            Dict with structure:
            {
                "submission_id": int,
                "overall_progress": float,
                "sections": [
                    {
                        "section_name": str,
                        "questions_total": int,
                        "questions_answered": int,
                        "progress_percentage": float,
                    }
                ]
            }

        Raises:
            NotFoundError: Submission does not exist.
        """
        submission = self.get_submission_by_id(submission_id, with_exchanges=True)

        snapshot = submission.template_structure_snapshot
        if not snapshot or not isinstance(snapshot, dict):
            # No snapshot → return basic progress from current_exchange_sequence
            total = 0
            return {
                "submission_id": submission_id,
                "overall_progress": 0.0,
                "sections": [],
            }

        # Parse sections from snapshot
        sections_data = snapshot.get("sections", [])
        total_questions = snapshot.get("total_questions", 0)

        # Build set of answered question_ids from exchanges
        answered_question_ids: set = set()
        answered_coding_problem_ids: set = set()
        for ex in (submission.exchanges or []):
            if ex.question_id:
                answered_question_ids.add(ex.question_id)
            if ex.coding_problem_id:
                answered_coding_problem_ids.add(ex.coding_problem_id)

        sections_progress = []
        total_answered = 0

        for section in sections_data:
            section_name = section.get("section_name", "unknown")
            question_ids = section.get("question_ids", [])
            questions_total = section.get("question_count", len(question_ids))

            # Count how many of this section's questions have been answered
            questions_answered = 0
            for qid in question_ids:
                if qid in answered_question_ids or qid in answered_coding_problem_ids:
                    questions_answered += 1

            total_answered += questions_answered

            section_pct = (
                (questions_answered / questions_total * 100.0)
                if questions_total > 0
                else 0.0
            )

            sections_progress.append({
                "section_name": section_name,
                "questions_total": questions_total,
                "questions_answered": questions_answered,
                "progress_percentage": round(section_pct, 1),
            })

        overall_pct = (
            (total_answered / total_questions * 100.0)
            if total_questions > 0
            else 0.0
        )

        return {
            "submission_id": submission_id,
            "overall_progress": round(overall_pct, 1),
            "sections": sections_progress,
        }
