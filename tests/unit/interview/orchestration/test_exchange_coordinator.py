"""
Unit Tests — Exchange Coordinator

Tests the central orchestration service that coordinates exchange lifecycle.
Uses mocks for DB, Redis, and dependent modules.

Patching strategy:
- ``RaceResolver`` is constructed in ``ExchangeCoordinator.__init__``, so we
  patch the *class* at the import location
  (``app.interview.orchestration.exchange_coordinator.RaceResolver``).
- ``InterviewExchangeRepository`` is also constructed in ``__init__`` and
  patched the same way.
- ``ProgressTracker`` is constructed in ``__init__`` — patched similarly.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.interview.orchestration.contracts import (
    AudioCompletionSignal,
    CodeCompletionSignal,
    NextQuestionResult,
    OrchestrationConfig,
    ProgressUpdate,
    TextResponseSignal,
)
from app.interview.orchestration.errors import (
    InterviewCompleteError,
    SequenceMismatchError,
    TemplateSnapshotMissingError,
)
from app.interview.orchestration.exchange_coordinator import ExchangeCoordinator
from app.shared.errors import InterviewNotActiveError, NotFoundError

# ════════════════════════════════════════════════════════════════════════
# Shared constants / helpers
# ════════════════════════════════════════════════════════════════════════

VALID_SNAPSHOT = {
    "template_id": 3,
    "template_name": "Test Interview",
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


def _make_submission(
    sub_id: int = 1,
    status: str = "in_progress",
    current_seq: int = 0,
    snapshot=None,
):
    """Create a mock submission SimpleNamespace matching ORM model shape."""
    return SimpleNamespace(
        id=sub_id,
        status=status,
        current_exchange_sequence=current_seq,
        template_structure_snapshot=snapshot if snapshot is not None else VALID_SNAPSHOT,
    )


def _make_progress(seq: int, total: int = 3) -> ProgressUpdate:
    """Create a ProgressUpdate matching the given sequence."""
    pct = round((seq / total) * 100, 1) if total else 0.0
    return ProgressUpdate(
        submission_id=1,
        current_sequence=seq,
        total_questions=total,
        progress_percentage=pct,
        is_complete=seq >= total,
    )


# ────────────────────────────────────────────────────────────────────
# Module-level constants for the three classes we need to patch.
# ────────────────────────────────────────────────────────────────────
_COORD_MOD = "app.interview.orchestration.exchange_coordinator"
_RACE_CLS = f"{_COORD_MOD}.RaceResolver"
_PROGRESS_CLS = f"{_COORD_MOD}.ProgressTracker"
_REPO_CLS = f"{_COORD_MOD}.InterviewExchangeRepository"


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get.return_value = None
    redis.set.return_value = True
    return redis


def _build_coordinator(
    mock_db,
    mock_redis,
    submission=None,
    *,
    race_resolver=None,
    progress_tracker=None,
    exchange_repo=None,
):
    """
    Build a coordinator with injectable mocks for private collaborators.

    Returns (coordinator, race_mock, progress_mock, repo_mock).
    """
    if submission is None:
        submission = _make_submission()

    mock_db.query.return_value.filter.return_value.first.return_value = submission

    coordinator = ExchangeCoordinator(mock_db, mock_redis)

    # Replace internal collaborators with the supplied mocks
    if race_resolver is not None:
        coordinator._race_resolver = race_resolver
    if progress_tracker is not None:
        coordinator._progress_tracker = progress_tracker
    if exchange_repo is not None:
        coordinator._exchange_repo = exchange_repo

    return coordinator


# ════════════════════════════════════════════════════════════════════════
# get_next_question
# ════════════════════════════════════════════════════════════════════════


class TestGetNextQuestion:

    def test_returns_first_question(self, mock_db, mock_redis):
        """First question for a fresh submission (current_seq=0)."""
        coordinator = _build_coordinator(mock_db, mock_redis)

        result = coordinator.get_next_question(submission_id=1)

        assert result is not None
        assert result.question_id == 101
        assert result.sequence_order == 1
        assert result.section_name == "behavioral"
        assert result.is_final_question is False

    def test_returns_second_question(self, mock_db, mock_redis):
        """Second question after first exchange completed."""
        sub = _make_submission(current_seq=1)
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        result = coordinator.get_next_question(submission_id=1)

        assert result is not None
        assert result.question_id == 102
        assert result.sequence_order == 2
        assert result.section_name == "behavioral"

    def test_returns_question_across_section_boundary(self, mock_db, mock_redis):
        """Third question crosses into the coding section."""
        sub = _make_submission(current_seq=2)
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        result = coordinator.get_next_question(submission_id=1)

        assert result is not None
        assert result.question_id == 301
        assert result.section_name == "coding"
        assert result.is_final_question is True

    def test_returns_none_when_all_complete(self, mock_db, mock_redis):
        """Returns None when all questions answered."""
        sub = _make_submission(current_seq=3)
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        result = coordinator.get_next_question(submission_id=1)
        assert result is None

    def test_raises_not_found_for_missing_submission(self, mock_db, mock_redis):
        """NotFoundError if submission_id does not exist in DB."""
        mock_db.query.return_value.filter.return_value.first.return_value = None
        coordinator = ExchangeCoordinator(mock_db, mock_redis)

        with pytest.raises(NotFoundError):
            coordinator.get_next_question(submission_id=999)

    def test_raises_not_active_for_completed(self, mock_db, mock_redis):
        """InterviewNotActiveError if submission is not in_progress."""
        sub = _make_submission(status="completed")
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        with pytest.raises(InterviewNotActiveError):
            coordinator.get_next_question(submission_id=1)

    def test_raises_snapshot_missing(self, mock_db, mock_redis):
        """TemplateSnapshotMissingError when snapshot is None."""
        sub = _make_submission()
        sub.template_structure_snapshot = None
        mock_db.query.return_value.filter.return_value.first.return_value = sub
        coordinator = ExchangeCoordinator(mock_db, mock_redis)

        with pytest.raises(TemplateSnapshotMissingError):
            coordinator.get_next_question(submission_id=1)


# ════════════════════════════════════════════════════════════════════════
# create_exchange_from_text
# ════════════════════════════════════════════════════════════════════════


class TestCreateExchangeFromText:

    def _signal(self, seq: int = 1, text: str = "My answer") -> TextResponseSignal:
        return TextResponseSignal(
            submission_id=1,
            sequence_order=seq,
            response_text=text,
            response_time_ms=30_000,
        )

    def test_creates_exchange_and_returns_progress(self, mock_db, mock_redis):
        """Happy path: exchange created, progress returned."""
        sub = _make_submission(current_seq=0)

        exchange = SimpleNamespace(id=42, sequence_order=1)
        race = MagicMock()
        race.resolve_or_create.side_effect = (
            lambda submission_id, sequence_order, create_fn: create_fn()
        )
        progress = _make_progress(1)
        pt = MagicMock()
        pt.update_progress.return_value = progress
        repo = MagicMock()
        repo.create.return_value = exchange

        coordinator = _build_coordinator(
            mock_db,
            mock_redis,
            sub,
            race_resolver=race,
            progress_tracker=pt,
            exchange_repo=repo,
        )

        ex, prog = coordinator.create_exchange_from_text(
            signal=self._signal(seq=1),
            question_text="What is polymorphism?",
            question_difficulty="medium",
        )

        assert ex.id == 42
        assert isinstance(prog, ProgressUpdate)
        assert prog.current_sequence == 1
        race.resolve_or_create.assert_called_once()
        pt.update_progress.assert_called_once()

    def test_raises_sequence_mismatch(self, mock_db, mock_redis):
        """SequenceMismatchError when signal.sequence_order != expected."""
        sub = _make_submission(current_seq=0)  # expected: 1
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        with pytest.raises(SequenceMismatchError):
            coordinator.create_exchange_from_text(
                signal=self._signal(seq=5),
                question_text="Q?",
                question_difficulty="easy",
            )

    def test_raises_interview_complete(self, mock_db, mock_redis):
        """InterviewCompleteError when all questions have been answered."""
        sub = _make_submission(current_seq=3)  # total=3 → done
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        with pytest.raises(InterviewCompleteError):
            coordinator.create_exchange_from_text(
                signal=self._signal(seq=4),
                question_text="Q?",
                question_difficulty="easy",
            )

    def test_idempotent_on_race(self, mock_db, mock_redis):
        """Race resolver returns existing exchange (idempotent)."""
        sub = _make_submission(current_seq=0)
        existing_exchange = SimpleNamespace(id=99, sequence_order=1)

        race = MagicMock()
        race.resolve_or_create.return_value = existing_exchange
        pt = MagicMock()
        pt.update_progress.return_value = _make_progress(1)

        coordinator = _build_coordinator(
            mock_db,
            mock_redis,
            sub,
            race_resolver=race,
            progress_tracker=pt,
        )

        ex, _ = coordinator.create_exchange_from_text(
            signal=self._signal(seq=1),
            question_text="Q?",
            question_difficulty="easy",
        )
        assert ex.id == 99  # Got existing, not a new one


# ════════════════════════════════════════════════════════════════════════
# create_exchange_from_audio
# ════════════════════════════════════════════════════════════════════════


class TestCreateExchangeFromAudio:

    def test_creates_audio_exchange(self, mock_db, mock_redis):
        """Happy path with audio signal → exchange + progress."""
        sub = _make_submission(current_seq=0)

        exchange = SimpleNamespace(id=55, sequence_order=1)
        race = MagicMock()
        race.resolve_or_create.side_effect = (
            lambda submission_id, sequence_order, create_fn: create_fn()
        )
        pt = MagicMock()
        pt.update_progress.return_value = _make_progress(1)
        repo = MagicMock()
        repo.create.return_value = exchange

        coordinator = _build_coordinator(
            mock_db,
            mock_redis,
            sub,
            race_resolver=race,
            progress_tracker=pt,
            exchange_repo=repo,
        )

        signal = AudioCompletionSignal(
            submission_id=1,
            sequence_order=1,
            recording_id=456,
            transcription_text="I would use a hash map",
            duration_ms=5000,
        )

        ex, prog = coordinator.create_exchange_from_audio(
            signal=signal,
            question_text="How would you approach this?",
            question_difficulty="medium",
        )

        assert ex.id == 55
        assert prog.current_sequence == 1
        repo.create.assert_called_once()


# ════════════════════════════════════════════════════════════════════════
# create_exchange_from_code
# ════════════════════════════════════════════════════════════════════════


class TestCreateExchangeFromCode:

    def test_creates_code_exchange_marks_complete(self, mock_db, mock_redis):
        """Creates exchange from code signal; last question marks complete."""
        sub = _make_submission(current_seq=2)

        exchange = SimpleNamespace(id=77, sequence_order=3)
        race = MagicMock()
        race.resolve_or_create.side_effect = (
            lambda submission_id, sequence_order, create_fn: create_fn()
        )
        pt = MagicMock()
        pt.update_progress.return_value = _make_progress(3, total=3)
        repo = MagicMock()
        repo.create.return_value = exchange

        coordinator = _build_coordinator(
            mock_db,
            mock_redis,
            sub,
            race_resolver=race,
            progress_tracker=pt,
            exchange_repo=repo,
        )

        signal = CodeCompletionSignal(
            submission_id=1,
            sequence_order=3,
            code_submission_id=789,
            code="def solve(): return 42",
            language="python",
            execution_status="passed",
            response_time_ms=30000,
        )

        ex, prog = coordinator.create_exchange_from_code(
            signal=signal,
            question_text="Implement the solution",
            question_difficulty="hard",
            coding_problem_id=301,
        )

        assert ex.id == 77
        assert prog.current_sequence == 3
        assert prog.is_complete is True


# ════════════════════════════════════════════════════════════════════════
# get_progress
# ════════════════════════════════════════════════════════════════════════


class TestGetProgress:

    def test_delegates_to_progress_tracker(self, mock_db, mock_redis):
        """get_progress delegates to ProgressTracker.get_progress."""
        pt = MagicMock()
        pt.get_progress.return_value = _make_progress(2)

        coordinator = _build_coordinator(
            mock_db, mock_redis, progress_tracker=pt
        )

        result = coordinator.get_progress(submission_id=1)
        assert result.current_sequence == 2
        pt.get_progress.assert_called_once_with(1)

    def test_returns_none_when_no_progress(self, mock_db, mock_redis):
        """Returns None when progress tracker has no data."""
        pt = MagicMock()
        pt.get_progress.return_value = None

        coordinator = _build_coordinator(
            mock_db, mock_redis, progress_tracker=pt
        )
        assert coordinator.get_progress(submission_id=1) is None


# ════════════════════════════════════════════════════════════════════════
# Submission status guard (cross-cutting)
# ════════════════════════════════════════════════════════════════════════


class TestSubmissionStatusGuard:
    """
    Exchange creation entries (text/audio/code) ALL call
    ``_load_active_submission`` which rejects non-in_progress statuses.
    """

    _INACTIVE_STATUSES = ("pending", "completed", "expired", "cancelled", "reviewed")

    @pytest.mark.parametrize("bad_status", _INACTIVE_STATUSES)
    def test_text_rejects_inactive(self, bad_status, mock_db, mock_redis):
        sub = _make_submission(status=bad_status)
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        signal = TextResponseSignal(
            submission_id=1,
            sequence_order=1,
            response_text="Answer",
            response_time_ms=1000,
        )

        with pytest.raises(InterviewNotActiveError):
            coordinator.create_exchange_from_text(
                signal=signal,
                question_text="Q?",
                question_difficulty="easy",
            )

    @pytest.mark.parametrize("bad_status", _INACTIVE_STATUSES)
    def test_audio_rejects_inactive(self, bad_status, mock_db, mock_redis):
        sub = _make_submission(status=bad_status)
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        signal = AudioCompletionSignal(
            submission_id=1,
            sequence_order=1,
            recording_id=1,
            transcription_text="Hi",
            duration_ms=1000,
        )

        with pytest.raises(InterviewNotActiveError):
            coordinator.create_exchange_from_audio(
                signal=signal,
                question_text="Q?",
                question_difficulty="easy",
            )

    @pytest.mark.parametrize("bad_status", _INACTIVE_STATUSES)
    def test_code_rejects_inactive(self, bad_status, mock_db, mock_redis):
        sub = _make_submission(status=bad_status)
        coordinator = _build_coordinator(mock_db, mock_redis, sub)

        signal = CodeCompletionSignal(
            submission_id=1,
            sequence_order=1,
            code_submission_id=1,
            code="x=1",
            language="python",
            execution_status="passed",
            response_time_ms=1000,
        )

        with pytest.raises(InterviewNotActiveError):
            coordinator.create_exchange_from_code(
                signal=signal,
                question_text="Q?",
                question_difficulty="easy",
                coding_problem_id=1,
            )
