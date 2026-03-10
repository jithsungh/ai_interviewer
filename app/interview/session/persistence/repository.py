"""
Submission Repository

Atomic state transitions via ``UPDATE … WHERE status = :expected RETURNING *``.
Each ``transition_to_*`` method returns ``(submission, transitioned)`` where
*transitioned* is ``True`` if the row was actually mutated, or ``False`` for
an idempotent no-op.

Raises:
    StateTransitionError — forbidden transition (e.g. pending → completed).
    NotFoundError        — submission does not exist.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.interview.session.domain.state_machine import (
    StateTransitionError,
    SubmissionStatus,
    validate_transition,
)
from app.interview.session.persistence.models import InterviewSubmissionModel
from app.shared.errors import NotFoundError


class SubmissionRepository:
    """Repository for interview submission state transitions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # ────────────────────────────────────────────────────────────
    # Public transition helpers
    # ────────────────────────────────────────────────────────────

    def transition_to_in_progress(
        self,
        submission_id: int,
        candidate_id: int,
    ) -> Tuple[object, bool]:
        """pending → in_progress (idempotent if already in_progress)."""
        return self._do_transition(
            submission_id=submission_id,
            expected_status=SubmissionStatus.PENDING,
            target_status=SubmissionStatus.IN_PROGRESS,
            idempotent_status=SubmissionStatus.IN_PROGRESS,
            extra_updates="started_at = now(), consent_captured = true",
            candidate_id=candidate_id,
        )

    def transition_to_completed(
        self,
        submission_id: int,
        candidate_id: Optional[int] = None,
    ) -> Tuple[object, bool]:
        """in_progress → completed (idempotent if already completed)."""
        return self._do_transition(
            submission_id=submission_id,
            expected_status=SubmissionStatus.IN_PROGRESS,
            target_status=SubmissionStatus.COMPLETED,
            idempotent_status=SubmissionStatus.COMPLETED,
            extra_updates="submitted_at = now()",
            candidate_id=candidate_id,
        )

    def transition_to_expired(
        self,
        submission_id: int,
    ) -> Tuple[object, bool]:
        """in_progress → expired (idempotent if already expired)."""
        return self._do_transition(
            submission_id=submission_id,
            expected_status=SubmissionStatus.IN_PROGRESS,
            target_status=SubmissionStatus.EXPIRED,
            idempotent_status=SubmissionStatus.EXPIRED,
            extra_updates="submitted_at = now()",
        )

    def transition_to_cancelled(
        self,
        submission_id: int,
    ) -> Tuple[object, bool]:
        """pending|in_progress → cancelled (idempotent if already cancelled)."""
        # Cancel is allowed from both pending and in_progress.
        # We try in_progress first, then pending.
        return self._do_multi_source_transition(
            submission_id=submission_id,
            expected_statuses=[SubmissionStatus.IN_PROGRESS, SubmissionStatus.PENDING],
            target_status=SubmissionStatus.CANCELLED,
            idempotent_status=SubmissionStatus.CANCELLED,
        )

    def transition_to_reviewed(
        self,
        submission_id: int,
    ) -> Tuple[object, bool]:
        """completed|expired|cancelled → reviewed (idempotent if already reviewed)."""
        return self._do_multi_source_transition(
            submission_id=submission_id,
            expected_statuses=[
                SubmissionStatus.COMPLETED,
                SubmissionStatus.EXPIRED,
                SubmissionStatus.CANCELLED,
            ],
            target_status=SubmissionStatus.REVIEWED,
            idempotent_status=SubmissionStatus.REVIEWED,
        )

    # ────────────────────────────────────────────────────────────
    # Read helpers
    # ────────────────────────────────────────────────────────────

    def get_by_id(self, submission_id: int) -> object:
        """Fetch submission by ID (any role). Raises NotFoundError."""
        sub = (
            self._session.query(InterviewSubmissionModel)
            .filter(InterviewSubmissionModel.id == submission_id)
            .first()
        )
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)
        return sub

    def get_by_id_for_candidate(
        self, submission_id: int, candidate_id: int
    ) -> object:
        """Fetch submission scoped to a candidate. Raises NotFoundError."""
        sub = (
            self._session.query(InterviewSubmissionModel)
            .filter(
                InterviewSubmissionModel.id == submission_id,
                InterviewSubmissionModel.candidate_id == candidate_id,
            )
            .first()
        )
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)
        return sub

    # ────────────────────────────────────────────────────────────
    # Internal
    # ────────────────────────────────────────────────────────────

    def _do_transition(
        self,
        submission_id: int,
        expected_status: SubmissionStatus,
        target_status: SubmissionStatus,
        idempotent_status: SubmissionStatus,
        extra_updates: str = "",
        candidate_id: Optional[int] = None,
    ) -> Tuple[object, bool]:
        """
        Core atomic transition via UPDATE … WHERE status = :expected RETURNING id.

        Returns ``(submission_model, True)`` on success, ``(model, False)`` on
        idempotent hit, or raises ``StateTransitionError`` / ``NotFoundError``.
        """
        set_clause = f"status = :target, updated_at = now()"
        if extra_updates:
            set_clause += f", {extra_updates}"

        where_clause = "id = :sid AND status = :expected"
        params: dict = {
            "target": target_status.value,
            "sid": submission_id,
            "expected": expected_status.value,
        }
        if candidate_id is not None:
            # Enforce ownership: only the owning candidate can transition
            where_clause += " AND candidate_id = :cid"
            params["cid"] = candidate_id

        sql = text(
            f"UPDATE interview_submissions "
            f"SET {set_clause} "
            f"WHERE {where_clause} "
            f"RETURNING id"
        )

        result = self._session.execute(sql, params)
        row = result.fetchone()

        if row is not None:
            # Transition succeeded — expire cached ORM state, reload
            self._session.expire_all()
            sub = self._reload(submission_id)
            return sub, True

        # Row not updated — figure out why
        sub = self._reload(submission_id)
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)

        current = sub.status
        if current == idempotent_status.value:
            return sub, False  # already in desired state

        # Forbidden transition
        raise StateTransitionError(current, target_status.value)

    def _do_multi_source_transition(
        self,
        submission_id: int,
        expected_statuses: list[SubmissionStatus],
        target_status: SubmissionStatus,
        idempotent_status: SubmissionStatus,
    ) -> Tuple[object, bool]:
        """Try each *expected_status* in order; first successful UPDATE wins."""
        for expected in expected_statuses:
            sql = text(
                "UPDATE interview_submissions "
                "SET status = :target, updated_at = now() "
                "WHERE id = :sid AND status = :expected "
                "RETURNING id"
            )
            params = {
                "target": target_status.value,
                "sid": submission_id,
                "expected": expected.value,
            }
            result = self._session.execute(sql, params)
            row = result.fetchone()
            if row is not None:
                self._session.expire_all()
                sub = self._reload(submission_id)
                return sub, True

        # None matched — reload to determine why
        sub = self._reload(submission_id)
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)

        current = sub.status
        if current == idempotent_status.value:
            return sub, False

        raise StateTransitionError(current, target_status.value)

    def _reload(self, submission_id: int) -> Optional[object]:
        """Reload the ORM model after an UPDATE."""
        return (
            self._session.query(InterviewSubmissionModel)
            .filter(InterviewSubmissionModel.id == submission_id)
            .first()
        )
