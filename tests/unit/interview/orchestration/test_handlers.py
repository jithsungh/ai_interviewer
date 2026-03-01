"""
Unit Tests — Audio & Coding Handlers

Both handlers are thin delegates that forward signals to ExchangeCoordinator.
Tests verify delegation wiring and argument pass-through.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.interview.orchestration.audio_handler import AudioCompletionHandler
from app.interview.orchestration.coding_handler import CodingCompletionHandler
from app.interview.orchestration.contracts import (
    AudioCompletionSignal,
    CodeCompletionSignal,
    ProgressUpdate,
)

# ────────────────────────────────────────────────────────────────────
# Shared helpers
# ────────────────────────────────────────────────────────────────────

_AUDIO_MOD = "app.interview.orchestration.audio_handler.ExchangeCoordinator"
_CODE_MOD = "app.interview.orchestration.coding_handler.ExchangeCoordinator"


def _progress(seq: int = 1, total: int = 3) -> ProgressUpdate:
    return ProgressUpdate(
        submission_id=1,
        current_sequence=seq,
        total_questions=total,
        progress_percentage=round((seq / total) * 100, 1),
        is_complete=seq >= total,
    )


# ════════════════════════════════════════════════════════════════════════
# AudioCompletionHandler
# ════════════════════════════════════════════════════════════════════════


class TestAudioCompletionHandler:

    @patch(_AUDIO_MOD)
    def test_delegates_to_coordinator(self, MockCoordinator):
        """handle() forwards all arguments to ExchangeCoordinator.create_exchange_from_audio."""
        exchange = SimpleNamespace(id=10, sequence_order=1)
        coord_instance = MockCoordinator.return_value
        coord_instance.create_exchange_from_audio.return_value = (
            exchange,
            _progress(1),
        )

        handler = AudioCompletionHandler(MagicMock(), MagicMock())

        signal = AudioCompletionSignal(
            submission_id=1,
            sequence_order=1,
            recording_id=42,
            transcription_text="Hash map approach",
            duration_ms=5000,
        )

        ex, prog = handler.handle(
            signal=signal,
            question_text="Describe your approach",
            question_difficulty="medium",
            expected_answer="Hash map",
        )

        assert ex.id == 10
        assert prog.current_sequence == 1

        coord_instance.create_exchange_from_audio.assert_called_once_with(
            signal=signal,
            question_text="Describe your approach",
            question_difficulty="medium",
            expected_answer="Hash map",
        )

    @patch(_AUDIO_MOD)
    def test_propagates_exceptions(self, MockCoordinator):
        """Coordinator exceptions bubble up unchanged."""
        coord_instance = MockCoordinator.return_value
        coord_instance.create_exchange_from_audio.side_effect = RuntimeError(
            "lock timeout"
        )

        handler = AudioCompletionHandler(MagicMock(), MagicMock())

        signal = AudioCompletionSignal(
            submission_id=1,
            sequence_order=1,
            recording_id=1,
            transcription_text="text",
            duration_ms=1000,
        )

        with pytest.raises(RuntimeError, match="lock timeout"):
            handler.handle(
                signal=signal,
                question_text="Q?",
                question_difficulty="easy",
            )


# ════════════════════════════════════════════════════════════════════════
# CodingCompletionHandler
# ════════════════════════════════════════════════════════════════════════


class TestCodingCompletionHandler:

    @patch(_CODE_MOD)
    def test_delegates_to_coordinator(self, MockCoordinator):
        """handle() forwards all arguments to ExchangeCoordinator.create_exchange_from_code."""
        exchange = SimpleNamespace(id=20, sequence_order=3)
        coord_instance = MockCoordinator.return_value
        coord_instance.create_exchange_from_code.return_value = (
            exchange,
            _progress(3, 3),
        )

        handler = CodingCompletionHandler(MagicMock(), MagicMock())

        signal = CodeCompletionSignal(
            submission_id=1,
            sequence_order=3,
            code_submission_id=789,
            code="def solve(): return 42",
            language="python",
            execution_status="passed",
            response_time_ms=3000,
        )

        ex, prog = handler.handle(
            signal=signal,
            question_text="Implement the solution",
            question_difficulty="hard",
            coding_problem_id=301,
            expected_answer="42",
        )

        assert ex.id == 20
        assert prog.is_complete is True

        coord_instance.create_exchange_from_code.assert_called_once_with(
            signal=signal,
            question_text="Implement the solution",
            question_difficulty="hard",
            coding_problem_id=301,
            expected_answer="42",
        )

    @patch(_CODE_MOD)
    def test_propagates_exceptions(self, MockCoordinator):
        """Coordinator exceptions bubble up unchanged."""
        coord_instance = MockCoordinator.return_value
        coord_instance.create_exchange_from_code.side_effect = ValueError(
            "invalid signal"
        )

        handler = CodingCompletionHandler(MagicMock(), MagicMock())

        signal = CodeCompletionSignal(
            submission_id=1,
            sequence_order=1,
            code_submission_id=1,
            code="x=1",
            language="python",
            execution_status="error",
            response_time_ms=1000,
        )

        with pytest.raises(ValueError, match="invalid signal"):
            handler.handle(
                signal=signal,
                question_text="Q?",
                question_difficulty="easy",
                coding_problem_id=1,
            )
