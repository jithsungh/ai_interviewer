"""
Interview Exchange Repository — Immutable CRUD

CREATE + READ only. UPDATE and DELETE are forbidden and raise
``ExchangeImmutabilityViolation``.

Uses the existing ``InterviewExchangeModel`` ORM model from
``app.interview.session.persistence.models``.

Concurrency: The UNIQUE(interview_submission_id, sequence_order) DB constraint
prevents duplicate exchanges. IntegrityError on duplicate is caught and
returns the existing exchange (idempotent).
"""

from __future__ import annotations

import logging
from typing import List, Optional, Set

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.interview.exchanges.contracts import ExchangeCreationData
from app.interview.exchanges.validators import (
    validate_response_completeness,
    validate_sequence_order,
)
from app.interview.session.domain.state_machine import SubmissionStatus
from app.interview.session.persistence.models import (
    InterviewExchangeModel,
    InterviewSubmissionModel,
)
from app.shared.errors import (
    ExchangeImmutabilityViolation,
    InterviewNotActiveError,
    NotFoundError,
)

logger = logging.getLogger(__name__)


class InterviewExchangeRepository:
    """
    Immutable exchange repository.

    Only ``create`` writes are allowed. ``update`` and ``delete`` raise
    ``ExchangeImmutabilityViolation`` unconditionally.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # ────────────────────────────────────────────────────────────
    # CREATE (the ONLY allowed write operation)
    # ────────────────────────────────────────────────────────────

    def create(self, data: ExchangeCreationData) -> InterviewExchangeModel:
        """
        Create an immutable exchange snapshot.

        Steps:
        1. Validate submission exists and is in_progress
        2. Validate sequence order (no gaps, no duplicates)
        3. Validate response completeness (type-specific)
        4. Persist exchange
        5. Handle idempotent duplicate (IntegrityError → return existing)

        Args:
            data: Complete exchange creation data.

        Returns:
            The created (or existing, if idempotent) exchange model.

        Raises:
            NotFoundError: Submission does not exist.
            InterviewNotActiveError: Submission not in_progress.
            SequenceGapError: Gap in sequence ordering.
            DuplicateSequenceError: Sequence already exists.
            IncompleteResponseError: Response data incomplete for question type.
        """
        # Step 1: Validate submission state
        submission = (
            self._session.query(InterviewSubmissionModel)
            .filter(InterviewSubmissionModel.id == data.submission_id)
            .first()
        )
        if submission is None:
            raise NotFoundError(
                resource_type="Submission",
                resource_id=data.submission_id,
            )
        if submission.status != SubmissionStatus.IN_PROGRESS.value:
            raise InterviewNotActiveError(submission_id=data.submission_id)

        # Step 2: Validate sequence order
        current_count = (
            self._session.query(InterviewExchangeModel)
            .filter(
                InterviewExchangeModel.interview_submission_id == data.submission_id
            )
            .count()
        )
        existing_orders: Set[int] = {
            row[0]
            for row in self._session.query(InterviewExchangeModel.sequence_order)
            .filter(
                InterviewExchangeModel.interview_submission_id == data.submission_id
            )
            .all()
        }
        validate_sequence_order(
            submission_id=data.submission_id,
            proposed_sequence=data.sequence_order,
            current_exchange_count=current_count,
            existing_sequence_orders=existing_orders,
        )

        # Step 3: Validate response completeness
        exchange_dict = data.model_dump()
        if data.content_metadata is not None:
            exchange_dict["content_metadata"] = data.content_metadata.model_dump()
        validate_response_completeness(exchange_dict)

        # Step 4: Build and persist exchange
        content_meta_json = None
        if data.content_metadata is not None:
            content_meta_json = data.content_metadata.model_dump(mode="json")

        exchange = InterviewExchangeModel(
            interview_submission_id=data.submission_id,
            sequence_order=data.sequence_order,
            question_id=data.question_id,
            coding_problem_id=data.coding_problem_id,
            question_text=data.question_text,
            expected_answer=data.expected_answer,
            difficulty_at_time=data.difficulty_at_time,
            response_text=data.response_text,
            response_code=data.response_code,
            response_time_ms=data.response_time_ms,
            ai_followup_message=data.ai_followup_message,
            content_metadata=content_meta_json,
        )

        try:
            self._session.add(exchange)
            self._session.flush()
            logger.info(
                "Exchange created",
                extra={
                    "submission_id": data.submission_id,
                    "sequence_order": data.sequence_order,
                    "exchange_id": exchange.id,
                },
            )
            return exchange

        except IntegrityError:
            # Step 5: Idempotent — duplicate detected via UNIQUE constraint
            self._session.rollback()
            logger.warning(
                "Duplicate exchange creation attempt (idempotent)",
                extra={
                    "submission_id": data.submission_id,
                    "sequence_order": data.sequence_order,
                },
            )
            existing = self.get_by_submission_and_sequence(
                data.submission_id, data.sequence_order
            )
            if existing is not None:
                return existing
            # Should not happen — re-raise if we can't find the duplicate
            raise  # pragma: no cover

    # ────────────────────────────────────────────────────────────
    # UPDATE — FORBIDDEN
    # ────────────────────────────────────────────────────────────

    def update(self, exchange_id: int, **updates: object) -> None:
        """
        UPDATE IS FORBIDDEN.

        Exchanges are immutable after creation. Any update attempt indicates
        a system bug.

        Raises:
            ExchangeImmutabilityViolation: Always.
        """
        raise ExchangeImmutabilityViolation(exchange_id=exchange_id)

    # ────────────────────────────────────────────────────────────
    # DELETE — FORBIDDEN
    # ────────────────────────────────────────────────────────────

    def delete(self, exchange_id: int) -> None:
        """
        DELETE IS FORBIDDEN (except CASCADE when submission deleted).

        Individual exchange deletion is never allowed. Exchanges are only
        removed when the parent submission is deleted via CASCADE.

        Raises:
            ExchangeImmutabilityViolation: Always.
        """
        raise ExchangeImmutabilityViolation(exchange_id=exchange_id)

    # ────────────────────────────────────────────────────────────
    # READ operations
    # ────────────────────────────────────────────────────────────

    def get_by_id(self, exchange_id: int) -> Optional[InterviewExchangeModel]:
        """Fetch exchange by primary key. Returns None if not found."""
        return (
            self._session.query(InterviewExchangeModel)
            .filter(InterviewExchangeModel.id == exchange_id)
            .first()
        )

    def get_by_id_or_raise(self, exchange_id: int) -> InterviewExchangeModel:
        """Fetch exchange by primary key. Raises NotFoundError if missing."""
        exchange = self.get_by_id(exchange_id)
        if exchange is None:
            raise NotFoundError(resource_type="Exchange", resource_id=exchange_id)
        return exchange

    def list_by_submission(
        self,
        submission_id: int,
    ) -> List[InterviewExchangeModel]:
        """Fetch all exchanges for a submission, ordered by sequence."""
        return (
            self._session.query(InterviewExchangeModel)
            .filter(
                InterviewExchangeModel.interview_submission_id == submission_id
            )
            .order_by(InterviewExchangeModel.sequence_order)
            .all()
        )

    def list_by_section(
        self,
        submission_id: int,
        section_name: str,
    ) -> List[InterviewExchangeModel]:
        """
        Fetch exchanges for a specific section (stored in content_metadata).

        Uses PostgreSQL JSONB containment operator for filtering.
        """
        return (
            self._session.query(InterviewExchangeModel)
            .filter(
                InterviewExchangeModel.interview_submission_id == submission_id,
                InterviewExchangeModel.content_metadata["section_name"].astext
                == section_name,
            )
            .order_by(InterviewExchangeModel.sequence_order)
            .all()
        )

    def get_by_submission_and_sequence(
        self,
        submission_id: int,
        sequence_order: int,
    ) -> Optional[InterviewExchangeModel]:
        """Fetch exchange by (submission_id, sequence_order) pair."""
        return (
            self._session.query(InterviewExchangeModel)
            .filter(
                InterviewExchangeModel.interview_submission_id == submission_id,
                InterviewExchangeModel.sequence_order == sequence_order,
            )
            .first()
        )

    def exists_for_sequence(
        self,
        submission_id: int,
        sequence_order: int,
    ) -> bool:
        """Check if exchange exists for given (submission_id, sequence_order)."""
        return (
            self._session.query(
                self._session.query(InterviewExchangeModel)
                .filter(
                    InterviewExchangeModel.interview_submission_id == submission_id,
                    InterviewExchangeModel.sequence_order == sequence_order,
                )
                .exists()
            ).scalar()
            or False
        )

    def count_by_submission(self, submission_id: int) -> int:
        """Count exchanges for a submission."""
        return (
            self._session.query(InterviewExchangeModel)
            .filter(
                InterviewExchangeModel.interview_submission_id == submission_id
            )
            .count()
        )
