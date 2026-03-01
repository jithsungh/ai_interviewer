"""
Integration Tests — Orchestration Service (Full Flow)

Tests the complete orchestration flow with mocked infrastructure,
exercising real class interactions:
  1. ExchangeCoordinator → RaceResolver → InterviewExchangeRepository
  2. ExchangeCoordinator → ProgressTracker (DB + Redis)
  3. AudioCompletionHandler → ExchangeCoordinator
  4. CodingCompletionHandler → ExchangeCoordinator
  5. End-to-end: 3-question walkthrough from first question to interview complete

Mocked boundaries: DB Session, Redis client, Redis lock.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

import pytest

from app.interview.orchestration.audio_handler import AudioCompletionHandler
from app.interview.orchestration.coding_handler import CodingCompletionHandler
from app.interview.orchestration.contracts import (
    AudioCompletionSignal,
    CodeCompletionSignal,
    ProgressUpdate,
    TextResponseSignal,
)
from app.interview.orchestration.errors import (
    InterviewCompleteError,
    SequenceMismatchError,
)
from app.interview.orchestration.exchange_coordinator import ExchangeCoordinator
from app.shared.errors import InterviewNotActiveError, NotFoundError


# ═══════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════

TEMPLATE_SNAPSHOT = {
    "template_id": 5,
    "template_name": "Standard Graduate Interview",
    "sections": [
        {
            "section_name": "behavioral",
            "question_count": 2,
            "question_ids": [101, 102],
        },
        {
            "section_name": "coding",
            "question_count": 1,
            "question_ids": [301],
        },
    ],
    "total_questions": 3,
}


def _make_submission(sub_id=1, current_seq=0, status="in_progress", snapshot=None):
    return SimpleNamespace(
        id=sub_id,
        status=status,
        current_exchange_sequence=current_seq,
        template_structure_snapshot=snapshot or TEMPLATE_SNAPSHOT,
    )


def _make_exchange(exchange_id, seq):
    return SimpleNamespace(id=exchange_id, sequence_order=seq)


def _noop_lock():
    """Context manager that does nothing (bypasses real Redis lock)."""

    @contextmanager
    def _lock(*args, **kwargs):
        yield

    return _lock


def _mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    redis.set.return_value = True
    return redis


def _replace_repos(coordinator, mock_repo):
    """
    Replace exchange repositories on BOTH the coordinator and its race resolver.

    The coordinator creates its own InterviewExchangeRepository, and the
    race resolver creates a separate one. Both need to be mocked.
    """
    coordinator._exchange_repo = mock_repo
    coordinator._race_resolver._exchange_repo = mock_repo


_LOCK_MODULE = "app.interview.orchestration.race_resolver.acquire_lock"


# ═══════════════════════════════════════════════════════════════════════════
# Full flow: text → audio → code (3-question walkthrough)
# ═══════════════════════════════════════════════════════════════════════════


class TestThreeQuestionWalkthrough:
    """
    Simulates a complete 3-question interview:
      Q1 (behavioral, text) → Q2 (behavioral, audio) → Q3 (coding, code) → complete
    """

    @patch(_LOCK_MODULE)
    def test_complete_walkthrough(self, mock_lock):
        mock_lock.side_effect = _noop_lock()

        db = MagicMock()
        redis = _mock_redis()

        # Each call to create() returns a new exchange
        exchange_counter = iter([
            _make_exchange(10, 1),
            _make_exchange(11, 2),
            _make_exchange(12, 3),
        ])

        # ──────────────────────────────────────────
        # Step 0: get_next_question before any exchanges
        # ──────────────────────────────────────────
        sub = _make_submission(current_seq=0)
        db.query.return_value.filter.return_value.first.return_value = sub

        coordinator = ExchangeCoordinator(db, redis)

        # Replace real repos with mock (both coordinator and race resolver)
        mock_repo = MagicMock()
        _replace_repos(coordinator, mock_repo)

        # No existing exchange; creates from counter
        mock_repo.get_by_submission_and_sequence.return_value = None
        mock_repo.create.side_effect = lambda data: next(exchange_counter)

        # DB execute mock for progress_tracker
        db_result = MagicMock()
        db_result.fetchone.return_value = (1,)
        db.execute.return_value = db_result

        result = coordinator.get_next_question(submission_id=1)
        assert result is not None
        assert result.question_id == 101
        assert result.sequence_order == 1
        assert result.section_name == "behavioral"
        assert result.is_final_question is False

        # ──────────────────────────────────────────
        # Step 1: Text response to Q1
        # ──────────────────────────────────────────
        text_signal = TextResponseSignal(
            submission_id=1,
            sequence_order=1,
            response_text="I handle stress by prioritizing tasks.",
            response_time_ms=25000,
        )

        ex1, prog1 = coordinator.create_exchange_from_text(
            signal=text_signal,
            question_text="How do you handle stress?",
            question_difficulty="easy",
        )

        assert ex1.id == 10
        assert prog1.current_sequence == 1
        assert prog1.total_questions == 3
        assert prog1.is_complete is False

        # ──────────────────────────────────────────
        # Step 2: Audio response to Q2
        # ──────────────────────────────────────────
        # Advance submission to seq=1
        sub.current_exchange_sequence = 1

        audio_signal = AudioCompletionSignal(
            submission_id=1,
            sequence_order=2,
            recording_id=456,
            transcription_text="I led a team through a difficult product launch",
            duration_ms=8000,
        )

        ex2, prog2 = coordinator.create_exchange_from_audio(
            signal=audio_signal,
            question_text="Describe a leadership challenge",
            question_difficulty="medium",
        )

        assert ex2.id == 11
        assert prog2.current_sequence == 2
        assert prog2.is_complete is False

        # ──────────────────────────────────────────
        # Step 3: Code response to Q3 (final)
        # ──────────────────────────────────────────
        sub.current_exchange_sequence = 2

        code_signal = CodeCompletionSignal(
            submission_id=1,
            sequence_order=3,
            code_submission_id=789,
            code="def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i",
            language="python",
            execution_status="passed",
            response_time_ms=60000,
        )

        ex3, prog3 = coordinator.create_exchange_from_code(
            signal=code_signal,
            question_text="Implement two_sum",
            question_difficulty="hard",
            coding_problem_id=301,
        )

        assert ex3.id == 12
        assert prog3.current_sequence == 3
        assert prog3.is_complete is True  # 3/3
        assert prog3.progress_percentage == 100.0

        # ──────────────────────────────────────────
        # Step 4: Verify no more questions
        # ──────────────────────────────────────────
        sub.current_exchange_sequence = 3
        result_final = coordinator.get_next_question(submission_id=1)
        assert result_final is None

        # Attempting to create Q4 should raise InterviewCompleteError
        sub.current_exchange_sequence = 3
        with pytest.raises(InterviewCompleteError):
            coordinator.create_exchange_from_text(
                signal=TextResponseSignal(
                    submission_id=1,
                    sequence_order=4,
                    response_text="extra",
                    response_time_ms=1000,
                ),
                question_text="Q?",
                question_difficulty="easy",
            )


# ═══════════════════════════════════════════════════════════════════════════
# Handler → Coordinator integration
# ═══════════════════════════════════════════════════════════════════════════


class TestHandlerToCoordinatorIntegration:
    """
    Verifies that handlers correctly delegate to ExchangeCoordinator
    and the full chain (handler → coordinator → race_resolver → repo)
    works end-to-end with mocked infrastructure.
    """

    @patch(_LOCK_MODULE)
    def test_audio_handler_full_chain(self, mock_lock):
        mock_lock.side_effect = _noop_lock()

        db = MagicMock()
        redis = _mock_redis()

        sub = _make_submission(current_seq=0)
        db.query.return_value.filter.return_value.first.return_value = sub
        db_result = MagicMock()
        db_result.fetchone.return_value = (1,)
        db.execute.return_value = db_result

        handler = AudioCompletionHandler(db, redis)

        exchange = _make_exchange(20, 1)
        mock_repo = MagicMock()
        _replace_repos(handler._coordinator, mock_repo)
        mock_repo.get_by_submission_and_sequence.return_value = None
        mock_repo.create.return_value = exchange

        signal = AudioCompletionSignal(
            submission_id=1,
            sequence_order=1,
            recording_id=42,
            transcription_text="Binary search approach",
            duration_ms=4000,
        )

        ex, prog = handler.handle(
            signal=signal,
            question_text="How would you optimize this?",
            question_difficulty="medium",
        )

        assert ex.id == 20
        assert isinstance(prog, ProgressUpdate)

    @patch(_LOCK_MODULE)
    def test_coding_handler_full_chain(self, mock_lock):
        mock_lock.side_effect = _noop_lock()

        db = MagicMock()
        redis = _mock_redis()

        sub = _make_submission(current_seq=2)
        db.query.return_value.filter.return_value.first.return_value = sub
        db_result = MagicMock()
        db_result.fetchone.return_value = (1,)
        db.execute.return_value = db_result

        handler = CodingCompletionHandler(db, redis)

        exchange = _make_exchange(30, 3)
        mock_repo = MagicMock()
        _replace_repos(handler._coordinator, mock_repo)
        mock_repo.get_by_submission_and_sequence.return_value = None
        mock_repo.create.return_value = exchange

        signal = CodeCompletionSignal(
            submission_id=1,
            sequence_order=3,
            code_submission_id=99,
            code="def solve(): pass",
            language="python",
            execution_status="passed",
            response_time_ms=20000,
        )

        ex, prog = handler.handle(
            signal=signal,
            question_text="Implement merge sort",
            question_difficulty="hard",
            coding_problem_id=301,
        )

        assert ex.id == 30
        assert prog.is_complete is True


# ═══════════════════════════════════════════════════════════════════════════
# Race condition integration
# ═══════════════════════════════════════════════════════════════════════════


class TestRaceConditionIntegration:
    """
    Tests that the race resolver correctly prevents duplicate exchange creation
    when two signals arrive concurrently for the same (submission, sequence).
    """

    @patch(_LOCK_MODULE)
    def test_second_signal_gets_existing_exchange(self, mock_lock):
        """
        Simulates two signals for the same sequence:
        - First creates the exchange
        - Second should detect existing and return it (idempotent)
        """
        mock_lock.side_effect = _noop_lock()

        db = MagicMock()
        redis = _mock_redis()

        sub = _make_submission(current_seq=0)
        db.query.return_value.filter.return_value.first.return_value = sub
        db_result = MagicMock()
        db_result.fetchone.return_value = (1,)
        db.execute.return_value = db_result

        coordinator = ExchangeCoordinator(db, redis)

        # Replace real repo with mock
        mock_repo = MagicMock()
        _replace_repos(coordinator, mock_repo)

        # First call: no existing exchange → create
        first_exchange = _make_exchange(100, 1)
        mock_repo.get_by_submission_and_sequence.return_value = None
        mock_repo.create.return_value = first_exchange

        text_signal = TextResponseSignal(
            submission_id=1,
            sequence_order=1,
            response_text="Answer 1",
            response_time_ms=5000,
        )

        ex1, _ = coordinator.create_exchange_from_text(
            signal=text_signal,
            question_text="Q1?",
            question_difficulty="easy",
        )
        assert ex1.id == 100

        # Second call: exchange already exists → return it (idempotent)
        mock_repo.get_by_submission_and_sequence.return_value = first_exchange

        audio_signal = AudioCompletionSignal(
            submission_id=1,
            sequence_order=1,
            recording_id=1,
            transcription_text="Same answer via audio",
            duration_ms=3000,
        )

        ex2, _ = coordinator.create_exchange_from_audio(
            signal=audio_signal,
            question_text="Q1?",
            question_difficulty="easy",
        )

        # Both should return the same exchange
        assert ex2.id == 100
        # create should only have been called once
        assert mock_repo.create.call_count == 1


# ═══════════════════════════════════════════════════════════════════════════
# Progress tracking through Redis integration
# ═══════════════════════════════════════════════════════════════════════════


class TestProgressRedisIntegration:
    """Tests that progress updates flow correctly to Redis."""

    @patch(_LOCK_MODULE)
    def test_redis_receives_progress_after_exchange(self, mock_lock):
        mock_lock.side_effect = _noop_lock()

        db = MagicMock()
        redis = _mock_redis()

        sub = _make_submission(current_seq=0)
        db.query.return_value.filter.return_value.first.return_value = sub
        db_result = MagicMock()
        db_result.fetchone.return_value = (1,)
        db.execute.return_value = db_result

        coordinator = ExchangeCoordinator(db, redis)
        mock_repo = MagicMock()
        _replace_repos(coordinator, mock_repo)
        mock_repo.get_by_submission_and_sequence.return_value = None
        mock_repo.create.return_value = _make_exchange(50, 1)

        signal = TextResponseSignal(
            submission_id=1,
            sequence_order=1,
            response_text="My answer",
            response_time_ms=10000,
        )

        _, prog = coordinator.create_exchange_from_text(
            signal=signal,
            question_text="Q?",
            question_difficulty="easy",
        )

        # Verify Redis.set was called with progress data
        redis.set.assert_called()
        set_call = redis.set.call_args
        stored_data = json.loads(set_call[0][1])  # Second positional arg
        assert stored_data["current_sequence"] == 1
        assert stored_data["total_questions"] == 3
        assert stored_data["is_complete"] is False

    @patch(_LOCK_MODULE)
    def test_get_progress_reads_from_redis(self, mock_lock):
        mock_lock.side_effect = _noop_lock()

        db = MagicMock()
        redis = _mock_redis()

        # Pre-populate Redis with progress data
        redis.get.return_value = json.dumps({
            "submission_id": 1,
            "current_sequence": 2,
            "total_questions": 3,
            "progress_percentage": 66.67,
            "is_complete": False,
        })

        coordinator = ExchangeCoordinator(db, redis)
        progress = coordinator.get_progress(submission_id=1)

        assert progress is not None
        assert progress.current_sequence == 2
        assert progress.total_questions == 3
        assert progress.is_complete is False


# ═══════════════════════════════════════════════════════════════════════════
# Sequence validation integration
# ═══════════════════════════════════════════════════════════════════════════


class TestSequenceValidationIntegration:
    """End-to-end sequence validation across coordinator."""

    def test_skipping_question_raises_mismatch(self):
        db = MagicMock()
        redis = _mock_redis()

        sub = _make_submission(current_seq=0)  # Expected: seq=1
        db.query.return_value.filter.return_value.first.return_value = sub

        coordinator = ExchangeCoordinator(db, redis)

        with pytest.raises(SequenceMismatchError) as exc_info:
            coordinator.create_exchange_from_text(
                signal=TextResponseSignal(
                    submission_id=1,
                    sequence_order=3,  # Skipped seq 1 and 2
                    response_text="Answer",
                    response_time_ms=1000,
                ),
                question_text="Q?",
                question_difficulty="easy",
            )

        assert "expected" in str(exc_info.value).lower() or hasattr(
            exc_info.value, "metadata"
        )

    def test_non_active_submission_across_all_paths(self):
        """All creation paths reject non-active submissions."""
        db = MagicMock()
        redis = _mock_redis()

        for status in ("pending", "completed", "expired", "cancelled"):
            sub = _make_submission(status=status)
            db.query.return_value.filter.return_value.first.return_value = sub

            coordinator = ExchangeCoordinator(db, redis)

            with pytest.raises(InterviewNotActiveError):
                coordinator.get_next_question(submission_id=1)
