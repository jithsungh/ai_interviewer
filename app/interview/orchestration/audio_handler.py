"""
Audio Handler — Audio Completion Signal Processing

Handles audio completion signals from the audio module and orchestrates
exchange creation with the transcription text as the response.

Flow:
1. Receive audio completion signal (recording_id, transcription, duration)
2. Validate submission is active
3. Validate sequence matches expected
4. Delegate exchange creation to ExchangeCoordinator

This handler does NOT:
- Process audio (audio module)
- Run transcription (audio/transcription module)
- Score the response (evaluation module)
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.interview.orchestration.contracts import (
    AudioCompletionSignal,
    OrchestrationConfig,
    ProgressUpdate,
)
from app.interview.orchestration.exchange_coordinator import ExchangeCoordinator
from app.interview.session.persistence.models import InterviewExchangeModel

logger = logging.getLogger(__name__)


class AudioCompletionHandler:
    """
    Processes audio completion signals.

    Audio module emits signal when silence is detected and transcription
    is complete. This handler creates the exchange with the transcription.
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
        signal: AudioCompletionSignal,
        question_text: str,
        question_difficulty: str,
        expected_answer: Optional[str] = None,
    ) -> tuple[InterviewExchangeModel, ProgressUpdate]:
        """
        Handle audio completion signal → create exchange.

        Args:
            signal: Audio completion signal from audio module.
            question_text: Snapshot of question text at time of asking.
            question_difficulty: Difficulty level (easy/medium/hard).
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
            "Handling audio completion",
            extra={
                "submission_id": signal.submission_id,
                "sequence_order": signal.sequence_order,
                "recording_id": signal.recording_id,
                "duration_ms": signal.duration_ms,
            },
        )

        return self._coordinator.create_exchange_from_audio(
            signal=signal,
            question_text=question_text,
            question_difficulty=question_difficulty,
            expected_answer=expected_answer,
        )
