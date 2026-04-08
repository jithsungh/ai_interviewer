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
from app.shared.errors import ConflictError, NotFoundError


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
        actor: Optional[str] = None,
    ) -> Tuple[object, bool]:
        """pending → in_progress (idempotent if already in_progress)."""
        return self._do_transition(
            submission_id=submission_id,
            expected_status=SubmissionStatus.PENDING,
            target_status=SubmissionStatus.IN_PROGRESS,
            idempotent_status=SubmissionStatus.IN_PROGRESS,
            extra_updates="started_at = now(), consent_captured = true",
            candidate_id=candidate_id,
            actor=actor,
        )

    def transition_to_completed(
        self,
        submission_id: int,
        candidate_id: Optional[int] = None,
        actor: Optional[str] = None,
    ) -> Tuple[object, bool]:
        """in_progress → completed (idempotent if already completed)."""
        return self._do_transition(
            submission_id=submission_id,
            expected_status=SubmissionStatus.IN_PROGRESS,
            target_status=SubmissionStatus.COMPLETED,
            idempotent_status=SubmissionStatus.COMPLETED,
            extra_updates="submitted_at = now()",
            candidate_id=candidate_id,
            actor=actor,
        )

    def transition_to_expired(
        self,
        submission_id: int,
        actor: Optional[str] = None,
    ) -> Tuple[object, bool]:
        """in_progress → expired (idempotent if already expired)."""
        return self._do_transition(
            submission_id=submission_id,
            expected_status=SubmissionStatus.IN_PROGRESS,
            target_status=SubmissionStatus.EXPIRED,
            idempotent_status=SubmissionStatus.EXPIRED,
            extra_updates="submitted_at = now()",
            actor=actor,
        )

    def transition_to_cancelled(
        self,
        submission_id: int,
        actor: Optional[str] = None,
    ) -> Tuple[object, bool]:
        """pending|in_progress → cancelled (idempotent if already cancelled)."""
        # Cancel is allowed from both pending and in_progress.
        # We try in_progress first, then pending.
        return self._do_multi_source_transition(
            submission_id=submission_id,
            expected_statuses=[SubmissionStatus.IN_PROGRESS, SubmissionStatus.PENDING],
            target_status=SubmissionStatus.CANCELLED,
            idempotent_status=SubmissionStatus.CANCELLED,
            actor=actor,
        )

    def transition_to_reviewed(
        self,
        submission_id: int,
        actor: Optional[str] = None,
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
            actor=actor,
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
        actor: Optional[str] = None,
    ) -> Tuple[object, bool]:
        """
        Core atomic transition via UPDATE … WHERE status = :expected RETURNING id.

        Returns ``(submission_model, True)`` on success, ``(model, False)`` on
        idempotent hit, or raises ``StateTransitionError`` / ``NotFoundError``.
        """
        current_sub = self._reload_scoped(submission_id, candidate_id)
        if current_sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)

        current_status = current_sub.status
        current_version = getattr(current_sub, "version", None)
        if current_version is None:
            raise ConflictError("Submission version missing; run DB migrations before state transitions")

        if current_status == idempotent_status.value:
            return current_sub, False

        validate_transition(current_status, target_status.value)

        if actor:
            self._set_actor(actor)

        set_clause = f"status = :target, updated_at = now(), version = version + 1"
        if extra_updates:
            set_clause += f", {extra_updates}"

        where_clause = "id = :sid AND status = :expected AND version = :expected_version"
        params: dict = {
            "target": target_status.value,
            "sid": submission_id,
            "expected": expected_status.value,
            "expected_version": current_version,
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
        sub = self._reload_scoped(submission_id, candidate_id)
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)

        current = sub.status
        if current == idempotent_status.value:
            return sub, False  # already in desired state

        if getattr(sub, "version", None) != current_version:
            raise ConflictError(
                "Submission state changed concurrently; retry the operation",
                metadata={
                    "submission_id": submission_id,
                    "expected_version": current_version,
                    "actual_version": getattr(sub, "version", None),
                },
            )

        # Forbidden transition
        raise StateTransitionError(current, target_status.value)

    def _do_multi_source_transition(
        self,
        submission_id: int,
        expected_statuses: list[SubmissionStatus],
        target_status: SubmissionStatus,
        idempotent_status: SubmissionStatus,
        actor: Optional[str] = None,
    ) -> Tuple[object, bool]:
        """Try transition from current status with optimistic version check."""
        sub = self._reload(submission_id)
        if sub is None:
            raise NotFoundError(resource_type="Submission", resource_id=submission_id)

        current = sub.status
        current_version = getattr(sub, "version", None)
        if current_version is None:
            raise ConflictError("Submission version missing; run DB migrations before state transitions")

        if current == idempotent_status.value:
            return sub, False

        allowed_sources = {status.value for status in expected_statuses}
        if current not in allowed_sources:
            raise StateTransitionError(current, target_status.value)

        validate_transition(current, target_status.value)

        if actor:
            self._set_actor(actor)

        sql = text(
            "UPDATE interview_submissions "
            "SET status = :target, updated_at = now(), version = version + 1 "
            "WHERE id = :sid AND status = :expected AND version = :expected_version "
            "RETURNING id"
        )
        params = {
            "target": target_status.value,
            "sid": submission_id,
            "expected": current,
            "expected_version": current_version,
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

        if getattr(sub, "version", None) != current_version:
            raise ConflictError(
                "Submission state changed concurrently; retry the operation",
                metadata={
                    "submission_id": submission_id,
                    "expected_version": current_version,
                    "actual_version": getattr(sub, "version", None),
                },
            )

        raise StateTransitionError(current, target_status.value)

    def _reload(self, submission_id: int) -> Optional[object]:
        """Reload the ORM model after an UPDATE."""
        return (
            self._session.query(InterviewSubmissionModel)
            .filter(InterviewSubmissionModel.id == submission_id)
            .first()
        )

    def _reload_scoped(
        self, submission_id: int, candidate_id: Optional[int]
    ) -> Optional[object]:
        query = self._session.query(InterviewSubmissionModel).filter(
            InterviewSubmissionModel.id == submission_id
        )
        if candidate_id is not None:
            query = query.filter(InterviewSubmissionModel.candidate_id == candidate_id)
        return query.first()

    def _set_actor(self, actor: str) -> None:
        self._session.execute(
            text("SELECT set_config('app.actor', :actor, true)"),
            {"actor": actor},
        )
