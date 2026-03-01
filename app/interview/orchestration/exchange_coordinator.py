"""
Exchange Coordinator — Central Exchange Lifecycle Orchestration

Coordinates the complete lifecycle of an exchange:
1. Validate submission is active
2. Resolve next question from template snapshot
3. Acquire distributed lock (race protection)
4. Create immutable exchange via InterviewExchangeRepository
5. Update progress (DB + Redis)
6. Emit evaluation trigger event

This is the CENTRAL COORDINATOR. It does NOT:
- Score/evaluate exchanges (evaluation module)
- Parse rubrics (evaluation module)
- Make AI calls (ai module)
- Manage WebSocket connections (realtime module)
- Handle audio processing (audio module)
- Execute code (coding module)

It delegates to domain modules and enforces architectural invariants at runtime.
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.interview.exchanges.contracts import (
    ContentMetadata,
    ExchangeCreationData,
    ExchangeQuestionType,
)
from app.interview.exchanges.repository import InterviewExchangeRepository
from app.interview.orchestration.contracts import (
    AudioCompletionSignal,
    CodeCompletionSignal,
    NextQuestionResult,
    OrchestrationConfig,
    ProgressUpdate,
    TemplateSnapshot,
    TextResponseSignal,
)
from app.interview.orchestration.errors import (
    InterviewCompleteError,
    SequenceMismatchError,
    TemplateSnapshotMissingError,
)
from app.interview.orchestration.progress_tracker import ProgressTracker
from app.interview.orchestration.question_sequencer import (
    get_total_questions,
    resolve_next_question,
    validate_template_snapshot,
)
from app.interview.orchestration.race_resolver import RaceResolver
from app.interview.session.domain.state_machine import SubmissionStatus
from app.interview.session.persistence.models import (
    InterviewExchangeModel,
    InterviewSubmissionModel,
)
from app.shared.errors import InterviewNotActiveError, NotFoundError

logger = logging.getLogger(__name__)


class ExchangeCoordinator:
    """
    Orchestrates exchange creation across all response types.

    Coordinates between:
    - Question sequencer (template snapshot → next question)
    - Exchange repository (immutable persistence)
    - Progress tracker (DB + Redis progress)
    - Race resolver (distributed lock + idempotent check)

    Thread safety: Uses Redis distributed locks for concurrent access.
    Idempotency: Duplicate exchange creation returns existing exchange.
    """

    def __init__(
        self,
        db: Session,
        redis,
        config: Optional[OrchestrationConfig] = None,
    ) -> None:
        self._db = db
        self._redis = redis
        self._config = config or OrchestrationConfig()
        self._exchange_repo = InterviewExchangeRepository(db)
        self._progress_tracker = ProgressTracker(db, redis)
        self._race_resolver = RaceResolver(
            db, redis, lock_timeout=self._config.exchange_creation_lock_timeout_seconds
        )

    # ────────────────────────────────────────────────────────────
    # Public API
    # ────────────────────────────────────────────────────────────

    def get_next_question(
        self,
        submission_id: int,
    ) -> Optional[NextQuestionResult]:
        """
        Resolve the next question for a submission.

        Reads the frozen template snapshot and current progress to
        determine which question to deliver next.

        Args:
            submission_id: Interview submission ID.

        Returns:
            NextQuestionResult if more questions remain, None if complete.

        Raises:
            NotFoundError: Submission does not exist.
            InterviewNotActiveError: Submission is not in_progress.
            TemplateSnapshotMissingError: No template snapshot set.
        """
        submission = self._load_active_submission(submission_id)
        snapshot = validate_template_snapshot(
            submission.template_structure_snapshot, submission_id
        )
        return resolve_next_question(snapshot, submission.current_exchange_sequence)

    def create_exchange_from_text(
        self,
        signal: TextResponseSignal,
        question_text: str,
        question_difficulty: str,
        expected_answer: Optional[str] = None,
    ) -> tuple[InterviewExchangeModel, ProgressUpdate]:
        """
        Create an exchange from a text response.

        Args:
            signal: Text response signal with submission_id, sequence_order, etc.
            question_text: Snapshot of question text.
            question_difficulty: Difficulty at time of asking.
            expected_answer: Expected answer snapshot (optional).

        Returns:
            Tuple of (created exchange, progress update).
        """
        submission = self._load_active_submission(signal.submission_id)
        snapshot = validate_template_snapshot(
            submission.template_structure_snapshot, signal.submission_id
        )
        next_q = self._validate_sequence(
            snapshot, submission, signal.sequence_order
        )

        creation_data = ExchangeCreationData(
            submission_id=signal.submission_id,
            sequence_order=signal.sequence_order,
            question_id=next_q.question_id,
            question_text=question_text,
            expected_answer=expected_answer,
            difficulty_at_time=question_difficulty,
            response_text=signal.response_text,
            response_time_ms=signal.response_time_ms,
            content_metadata=ContentMetadata(
                question_type=ExchangeQuestionType.TEXT,
                section_name=next_q.section_name,
            ),
        )

        return self._create_exchange_with_progress(
            submission_id=signal.submission_id,
            sequence_order=signal.sequence_order,
            creation_data=creation_data,
            total_questions=snapshot.total_questions,
        )

    def create_exchange_from_audio(
        self,
        signal: AudioCompletionSignal,
        question_text: str,
        question_difficulty: str,
        expected_answer: Optional[str] = None,
    ) -> tuple[InterviewExchangeModel, ProgressUpdate]:
        """
        Create an exchange from an audio completion signal.

        Args:
            signal: Audio completion signal with transcription, recording_id, etc.
            question_text: Snapshot of question text.
            question_difficulty: Difficulty at time of asking.
            expected_answer: Expected answer snapshot (optional).

        Returns:
            Tuple of (created exchange, progress update).
        """
        submission = self._load_active_submission(signal.submission_id)
        snapshot = validate_template_snapshot(
            submission.template_structure_snapshot, signal.submission_id
        )
        next_q = self._validate_sequence(
            snapshot, submission, signal.sequence_order
        )

        creation_data = ExchangeCreationData(
            submission_id=signal.submission_id,
            sequence_order=signal.sequence_order,
            question_id=next_q.question_id,
            question_text=question_text,
            expected_answer=expected_answer,
            difficulty_at_time=question_difficulty,
            response_text=signal.transcription_text,
            response_time_ms=signal.duration_ms,
            content_metadata=ContentMetadata(
                question_type=ExchangeQuestionType.AUDIO,
                section_name=next_q.section_name,
                audio_recording_id=signal.recording_id,
            ),
        )

        return self._create_exchange_with_progress(
            submission_id=signal.submission_id,
            sequence_order=signal.sequence_order,
            creation_data=creation_data,
            total_questions=snapshot.total_questions,
        )

    def create_exchange_from_code(
        self,
        signal: CodeCompletionSignal,
        question_text: str,
        question_difficulty: str,
        coding_problem_id: int,
        expected_answer: Optional[str] = None,
    ) -> tuple[InterviewExchangeModel, ProgressUpdate]:
        """
        Create an exchange from a code execution completion signal.

        Args:
            signal: Code completion signal with code, language, execution_status.
            question_text: Snapshot of question text.
            question_difficulty: Difficulty at time of asking.
            coding_problem_id: FK to coding_problems table.
            expected_answer: Expected answer snapshot (optional).

        Returns:
            Tuple of (created exchange, progress update).
        """
        submission = self._load_active_submission(signal.submission_id)
        snapshot = validate_template_snapshot(
            submission.template_structure_snapshot, signal.submission_id
        )
        next_q = self._validate_sequence(
            snapshot, submission, signal.sequence_order
        )

        creation_data = ExchangeCreationData(
            submission_id=signal.submission_id,
            sequence_order=signal.sequence_order,
            question_id=None,
            coding_problem_id=coding_problem_id,
            question_text=question_text,
            expected_answer=expected_answer,
            difficulty_at_time=question_difficulty,
            response_code=signal.code,
            response_time_ms=signal.response_time_ms,
            content_metadata=ContentMetadata(
                question_type=ExchangeQuestionType.CODING,
                section_name=next_q.section_name,
                response_language=signal.language,
                code_submission_id=signal.code_submission_id,
            ),
        )

        return self._create_exchange_with_progress(
            submission_id=signal.submission_id,
            sequence_order=signal.sequence_order,
            creation_data=creation_data,
            total_questions=snapshot.total_questions,
        )

    def get_progress(self, submission_id: int) -> Optional[ProgressUpdate]:
        """
        Get current progress for a submission.

        Reads from Redis (fast) with DB fallback.
        """
        return self._progress_tracker.get_progress(submission_id)

    # ────────────────────────────────────────────────────────────
    # Internal helpers
    # ────────────────────────────────────────────────────────────

    def _load_active_submission(
        self, submission_id: int
    ) -> InterviewSubmissionModel:
        """
        Load submission and validate it is in_progress.

        Raises:
            NotFoundError: Submission does not exist.
            InterviewNotActiveError: Submission is not in_progress.
        """
        submission = (
            self._db.query(InterviewSubmissionModel)
            .filter(InterviewSubmissionModel.id == submission_id)
            .first()
        )
        if submission is None:
            raise NotFoundError(
                resource_type="Submission", resource_id=submission_id
            )
        if submission.status != SubmissionStatus.IN_PROGRESS.value:
            raise InterviewNotActiveError(submission_id=submission_id)
        return submission

    def _validate_sequence(
        self,
        snapshot: TemplateSnapshot,
        submission: InterviewSubmissionModel,
        sequence_order: int,
    ) -> NextQuestionResult:
        """
        Validate that the requested sequence_order matches expected.

        Args:
            snapshot: Validated template snapshot.
            submission: Current submission model.
            sequence_order: Requested sequence order (1-indexed).

        Returns:
            NextQuestionResult for the requested sequence.

        Raises:
            InterviewCompleteError: All questions already answered.
            SequenceMismatchError: Sequence doesn't match expected.
        """
        expected_sequence = submission.current_exchange_sequence + 1

        if expected_sequence > snapshot.total_questions:
            raise InterviewCompleteError(
                submission_id=submission.id,
                total_questions=snapshot.total_questions,
            )

        if sequence_order != expected_sequence:
            raise SequenceMismatchError(
                submission_id=submission.id,
                expected_sequence=expected_sequence,
                received_sequence=sequence_order,
            )

        # Resolve question for this sequence (0-indexed input)
        next_q = resolve_next_question(
            snapshot, submission.current_exchange_sequence
        )
        if next_q is None:
            raise InterviewCompleteError(
                submission_id=submission.id,
                total_questions=snapshot.total_questions,
            )
        return next_q

    def _create_exchange_with_progress(
        self,
        submission_id: int,
        sequence_order: int,
        creation_data: ExchangeCreationData,
        total_questions: int,
    ) -> tuple[InterviewExchangeModel, ProgressUpdate]:
        """
        Create exchange under distributed lock, then update progress.

        Race-safe: If another handler already created the exchange,
        returns the existing one (idempotent).

        Args:
            submission_id: Interview submission ID.
            sequence_order: Exchange sequence number (1-indexed).
            creation_data: Complete exchange data for persistence.
            total_questions: Total questions from template (for progress).

        Returns:
            Tuple of (exchange, progress update).
        """

        def _do_create() -> InterviewExchangeModel:
            return self._exchange_repo.create(creation_data)

        # Race-safe: acquire lock → check existing → create
        exchange = self._race_resolver.resolve_or_create(
            submission_id=submission_id,
            sequence_order=sequence_order,
            create_fn=_do_create,
        )

        # Update progress (DB + Redis)
        progress = self._progress_tracker.update_progress(
            submission_id=submission_id,
            sequence_order=sequence_order,
            total_questions=total_questions,
        )

        logger.info(
            "Exchange created and progress updated",
            extra={
                "submission_id": submission_id,
                "sequence_order": sequence_order,
                "exchange_id": exchange.id,
                "progress_percentage": progress.progress_percentage,
            },
        )

        return exchange, progress
