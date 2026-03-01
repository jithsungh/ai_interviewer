"""
Coding Handler — Code Execution Completion Signal Processing

Handles code execution completion signals from the coding module and
orchestrates exchange creation with the code submission as the response.

Flow:
1. Receive code completion signal (code_submission_id, code, language, status)
2. Validate submission is active
3. Validate sequence matches expected
4. Delegate exchange creation to ExchangeCoordinator

This handler does NOT:
- Execute code (coding/sandbox module)
- Score the submission (evaluation module)
- Manage sandboxes (coding/sandbox module)
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.interview.orchestration.contracts import (
    CodeCompletionSignal,
    OrchestrationConfig,
    ProgressUpdate,
)
from app.interview.orchestration.exchange_coordinator import ExchangeCoordinator
from app.interview.session.persistence.models import InterviewExchangeModel

logger = logging.getLogger(__name__)


class CodingCompletionHandler:
    """
    Processes code execution completion signals.

    Coding module emits signal when sandbox execution is complete.
    This handler creates the exchange with the code as the response.
    """

    def __init__(
        self,
        db: Session,
        redis,
        config: Optional[OrchestrationConfig] = None,
    ) -> None:
        self._coordinator = ExchangeCoordinator(db, redis, config)

    def handle(
        self,
        signal: CodeCompletionSignal,
        question_text: str,
        question_difficulty: str,
        coding_problem_id: int,
        expected_answer: Optional[str] = None,
    ) -> tuple[InterviewExchangeModel, ProgressUpdate]:
        """
        Handle code execution completion signal → create exchange.

        Args:
            signal: Code completion signal from coding module.
            question_text: Snapshot of question text at time of asking.
            question_difficulty: Difficulty level (easy/medium/hard).
            coding_problem_id: FK to coding_problems table.
            expected_answer: Expected answer snapshot (optional).

        Returns:
            Tuple of (created exchange, progress update).

        Raises:
            NotFoundError: Submission not found.
            InterviewNotActiveError: Submission not in_progress.
            SequenceMismatchError: Wrong sequence order.
            LockAcquisitionError: Could not acquire distributed lock.
        """
        logger.info(
            "Handling code execution completion",
            extra={
                "submission_id": signal.submission_id,
                "sequence_order": signal.sequence_order,
                "code_submission_id": signal.code_submission_id,
                "language": signal.language,
                "execution_status": signal.execution_status,
            },
        )

        return self._coordinator.create_exchange_from_code(
            signal=signal,
            question_text=question_text,
            question_difficulty=question_difficulty,
            coding_problem_id=coding_problem_id,
            expected_answer=expected_answer,
        )
