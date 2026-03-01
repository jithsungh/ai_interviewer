"""
Adaptation Log Repository

INSERT-ONLY repository for difficulty adaptation audit records.
All methods enforce strict typing — no business logic.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from sqlalchemy.orm import Session

from app.question.selection.contracts import AdaptationDecision
from app.question.selection.persistence.models import (
    DifficultyAdaptationLogModel,
)

logger = logging.getLogger(__name__)


class AdaptationLogRepository:
    """
    Write-only repository for difficulty adaptation logs.

    Injected with a SQLAlchemy Session via FastAPI DI.
    Only INSERT operations — no UPDATE, no DELETE (immutable audit).
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def log_decision(self, decision: AdaptationDecision) -> int:
        """
        Persist an adaptation decision to the audit log.

        Args:
            decision: AdaptationDecision DTO.

        Returns:
            ID of the created record.
        """
        record = DifficultyAdaptationLogModel(
            submission_id=decision.submission_id,
            exchange_sequence_order=decision.exchange_sequence_order,
            previous_difficulty=decision.previous_difficulty,
            previous_score=(
                float(decision.previous_score)
                if decision.previous_score is not None
                else None
            ),
            previous_question_id=decision.previous_question_id,
            adaptation_rule=decision.adaptation_rule,
            threshold_up=(
                float(decision.threshold_up)
                if decision.threshold_up is not None
                else None
            ),
            threshold_down=(
                float(decision.threshold_down)
                if decision.threshold_down is not None
                else None
            ),
            max_difficulty_jump=decision.max_difficulty_jump,
            next_difficulty=decision.next_difficulty,
            adaptation_reason=decision.adaptation_reason,
            difficulty_changed=decision.difficulty_changed,
            decided_at=decision.decided_at,
            rule_version=decision.rule_version,
        )
        self._db.add(record)
        self._db.flush()

        logger.info(
            "Logged adaptation decision: submission=%d seq=%d "
            "%s → %s (reason: %s)",
            decision.submission_id,
            decision.exchange_sequence_order,
            decision.previous_difficulty,
            decision.next_difficulty,
            decision.adaptation_reason,
        )

        return record.id  # type: ignore[return-value]

    def get_by_submission(
        self, submission_id: int
    ) -> List[DifficultyAdaptationLogModel]:
        """
        Retrieve all adaptation logs for a submission (ordered by seq).

        Args:
            submission_id: Interview submission ID.

        Returns:
            List of log records ordered by exchange_sequence_order.
        """
        return (
            self._db.query(DifficultyAdaptationLogModel)
            .filter(
                DifficultyAdaptationLogModel.submission_id == submission_id
            )
            .order_by(DifficultyAdaptationLogModel.exchange_sequence_order)
            .all()
        )

    def get_latest_for_submission(
        self, submission_id: int
    ) -> Optional[DifficultyAdaptationLogModel]:
        """
        Get the most recent adaptation log for a submission.

        Returns None if no logs exist.
        """
        return (
            self._db.query(DifficultyAdaptationLogModel)
            .filter(
                DifficultyAdaptationLogModel.submission_id == submission_id
            )
            .order_by(
                DifficultyAdaptationLogModel.exchange_sequence_order.desc()
            )
            .first()
        )
