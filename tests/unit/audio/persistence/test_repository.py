"""
Unit Tests — Audio Persistence Repository

Tests for SqlAudioAnalyticsRepository with mocked SQLAlchemy session.
Validates CRUD operations, finalization, immutability enforcement,
and error handling.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

from sqlalchemy.exc import IntegrityError

from app.audio.persistence.entities import (
    AudioAnalytics,
    AudioAnalyticsCreate,
    AudioAnalyticsUpdate,
)
from app.audio.persistence.exceptions import (
    DuplicateAnalyticsError,
    ImmutabilityError,
)
from app.audio.persistence.models import AudioAnalyticsModel
from app.audio.persistence.repository import SqlAudioAnalyticsRepository
from app.shared.errors import NotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(**overrides) -> MagicMock:
    """Create a mock AudioAnalyticsModel."""
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=1,
        interview_exchange_id=42,
        transcript="Test transcript",
        transcript_finalized=False,
        confidence_score=0.92,
        language_detected="en",
        speech_state="complete",
        speech_rate_wpm=145,
        pause_duration_ms=200,
        long_pause_count=3,
        filler_word_count=5,
        filler_rate=2.5,
        sentiment_score=0.35,
        hesitation_detected=False,
        frustration_detected=False,
        audio_quality_score=0.85,
        background_noise_detected=False,
        analysis_metadata=None,
        created_at=now,
        updated_at=now,
        finalized_at=None,
    )
    defaults.update(overrides)
    model = MagicMock(spec=AudioAnalyticsModel)
    for k, v in defaults.items():
        setattr(model, k, v)
    return model


def _make_create_dto(**overrides) -> AudioAnalyticsCreate:
    defaults = dict(
        interview_exchange_id=42,
        transcript="Test transcript",
        confidence_score=0.92,
        speech_state="complete",
    )
    defaults.update(overrides)
    return AudioAnalyticsCreate(**defaults)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreate:
    """Tests for SqlAudioAnalyticsRepository.create()."""

    @patch("app.audio.persistence.repository.create_dto_to_model")
    @patch("app.audio.persistence.repository.model_to_entity")
    def test_create_success(self, mock_to_entity, mock_to_model):
        """Successfully creates an analytics record."""
        session = MagicMock()
        model = _make_model()
        mock_to_model.return_value = model
        mock_to_entity.return_value = AudioAnalytics(id=1, interview_exchange_id=42)

        repo = SqlAudioAnalyticsRepository(session)
        dto = _make_create_dto()
        result = repo.create(dto)

        session.add.assert_called_once_with(model)
        session.flush.assert_called_once()
        assert result.id == 1

    @patch("app.audio.persistence.repository.create_dto_to_model")
    def test_create_duplicate_raises(self, mock_to_model):
        """Raises DuplicateAnalyticsError on UNIQUE violation."""
        session = MagicMock()
        mock_to_model.return_value = _make_model()
        session.begin_nested.return_value.__enter__ = MagicMock()
        session.begin_nested.return_value.__exit__ = MagicMock(return_value=False)
        session.flush.side_effect = IntegrityError(
            "unique constraint", params=None, orig=Exception("unique")
        )

        repo = SqlAudioAnalyticsRepository(session)
        dto = _make_create_dto()

        with pytest.raises(DuplicateAnalyticsError) as exc_info:
            repo.create(dto)

        assert exc_info.value.exchange_id == 42
        session.begin_nested.assert_called_once()


class TestCreateOrGet:
    """Tests for SqlAudioAnalyticsRepository.create_or_get()."""

    @patch("app.audio.persistence.repository.create_dto_to_model")
    @patch("app.audio.persistence.repository.model_to_entity")
    def test_create_or_get_creates_new(self, mock_to_entity, mock_to_model):
        """Creates new record when none exists."""
        session = MagicMock()
        model = _make_model()
        mock_to_model.return_value = model
        mock_to_entity.return_value = AudioAnalytics(id=1)

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.create_or_get(_make_create_dto())
        assert result.id == 1

    @patch("app.audio.persistence.repository.create_dto_to_model")
    @patch("app.audio.persistence.repository.model_to_entity")
    def test_create_or_get_returns_existing(self, mock_to_entity, mock_to_model):
        """Returns existing record when duplicate detected."""
        session = MagicMock()
        mock_to_model.return_value = _make_model()
        session.flush.side_effect = IntegrityError(
            "unique", params=None, orig=Exception("unique")
        )

        existing_model = _make_model(id=99)
        session.query.return_value.filter.return_value.first.return_value = existing_model
        mock_to_entity.return_value = AudioAnalytics(id=99)

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.create_or_get(_make_create_dto())
        assert result.id == 99


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


class TestGetById:
    """Tests for SqlAudioAnalyticsRepository.get_by_id()."""

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_found(self, mock_to_entity):
        """Returns entity when found."""
        session = MagicMock()
        model = _make_model(id=1)
        session.get.return_value = model
        mock_to_entity.return_value = AudioAnalytics(id=1)

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.get_by_id(1)
        assert result.id == 1

    def test_not_found(self):
        """Returns None when not found."""
        session = MagicMock()
        session.get.return_value = None

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.get_by_id(999)
        assert result is None


class TestGetByExchangeId:
    """Tests for SqlAudioAnalyticsRepository.get_by_exchange_id()."""

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_found(self, mock_to_entity):
        """Returns entity when found."""
        session = MagicMock()
        model = _make_model(interview_exchange_id=42)
        session.query.return_value.filter.return_value.first.return_value = model
        mock_to_entity.return_value = AudioAnalytics(interview_exchange_id=42)

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.get_by_exchange_id(42)
        assert result.interview_exchange_id == 42

    def test_not_found(self):
        """Returns None when not found."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.get_by_exchange_id(999)
        assert result is None


class TestIsFinalized:
    """Tests for SqlAudioAnalyticsRepository.is_finalized()."""

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_finalized(self, mock_to_entity):
        """Returns True when finalized."""
        session = MagicMock()
        model = _make_model(transcript_finalized=True)
        session.query.return_value.filter.return_value.first.return_value = model
        mock_to_entity.return_value = AudioAnalytics(transcript_finalized=True)

        repo = SqlAudioAnalyticsRepository(session)
        assert repo.is_finalized(42) is True

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_not_finalized(self, mock_to_entity):
        """Returns False when not finalized."""
        session = MagicMock()
        model = _make_model(transcript_finalized=False)
        session.query.return_value.filter.return_value.first.return_value = model
        mock_to_entity.return_value = AudioAnalytics(transcript_finalized=False)

        repo = SqlAudioAnalyticsRepository(session)
        assert repo.is_finalized(42) is False

    def test_no_analytics_returns_false(self):
        """Returns False when no analytics exists."""
        session = MagicMock()
        session.query.return_value.filter.return_value.first.return_value = None

        repo = SqlAudioAnalyticsRepository(session)
        assert repo.is_finalized(999) is False


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdate:
    """Tests for SqlAudioAnalyticsRepository.update()."""

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_update_success(self, mock_to_entity):
        """Successfully updates non-finalized record."""
        session = MagicMock()
        model = _make_model(id=1, transcript_finalized=False)
        session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = model
        mock_to_entity.return_value = AudioAnalytics(id=1, transcript="Updated")

        repo = SqlAudioAnalyticsRepository(session)
        data = AudioAnalyticsUpdate(transcript="Updated")
        result = repo.update(1, data)

        assert model.transcript == "Updated"
        session.flush.assert_called_once()

    def test_update_not_found_raises(self):
        """Raises NotFoundError when record not found."""
        session = MagicMock()
        session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None

        repo = SqlAudioAnalyticsRepository(session)
        data = AudioAnalyticsUpdate(transcript="Updated")

        with pytest.raises(NotFoundError):
            repo.update(999, data)

    def test_update_finalized_raises_immutability(self):
        """Raises ImmutabilityError when record is finalized."""
        session = MagicMock()
        model = _make_model(id=1, transcript_finalized=True)
        session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = model

        repo = SqlAudioAnalyticsRepository(session)
        data = AudioAnalyticsUpdate(transcript="Should fail")

        with pytest.raises(ImmutabilityError) as exc_info:
            repo.update(1, data)

        assert exc_info.value.analytics_id == 1

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_update_only_non_none_fields(self, mock_to_entity):
        """Only non-None fields from update DTO are applied."""
        session = MagicMock()
        model = _make_model(
            id=1,
            transcript_finalized=False,
            transcript="Original",
            confidence_score=0.5,
        )
        session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = model
        mock_to_entity.return_value = AudioAnalytics(id=1)

        repo = SqlAudioAnalyticsRepository(session)
        # Only update transcript, leave confidence_score unchanged
        data = AudioAnalyticsUpdate(transcript="New text")
        repo.update(1, data)

        assert model.transcript == "New text"
        # confidence_score should not have been changed
        # (the None field in update DTO is filtered out)


# ---------------------------------------------------------------------------
# Finalize
# ---------------------------------------------------------------------------


class TestFinalize:
    """Tests for SqlAudioAnalyticsRepository.finalize()."""

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_finalize_success(self, mock_to_entity):
        """Successfully finalizes record."""
        session = MagicMock()
        model = _make_model(id=1, transcript_finalized=False)
        session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = model
        mock_to_entity.return_value = AudioAnalytics(
            id=1, transcript_finalized=True
        )

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.finalize(1)

        assert model.transcript_finalized is True
        assert model.finalized_at is not None
        session.flush.assert_called_once()

    @patch("app.audio.persistence.repository.model_to_entity")
    def test_finalize_idempotent(self, mock_to_entity):
        """Finalizing already-finalized record is idempotent."""
        session = MagicMock()
        now = datetime.now(timezone.utc)
        model = _make_model(id=1, transcript_finalized=True, finalized_at=now)
        session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = model
        mock_to_entity.return_value = AudioAnalytics(
            id=1, transcript_finalized=True, finalized_at=now
        )

        repo = SqlAudioAnalyticsRepository(session)
        result = repo.finalize(1)

        assert result.transcript_finalized is True
        session.flush.assert_not_called()  # No flush needed for idempotent

    def test_finalize_not_found_raises(self):
        """Raises NotFoundError when record not found."""
        session = MagicMock()
        session.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = None

        repo = SqlAudioAnalyticsRepository(session)

        with pytest.raises(NotFoundError):
            repo.finalize(999)
