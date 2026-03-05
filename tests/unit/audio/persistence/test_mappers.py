"""
Unit Tests — Audio Persistence Mappers

Tests for ORM ↔ entity conversion functions.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

from app.audio.persistence.entities import AudioAnalytics, AudioAnalyticsCreate
from app.audio.persistence.mappers import create_dto_to_model, model_to_entity
from app.audio.persistence.models import AudioAnalyticsModel


class TestModelToEntity:
    """Tests for model_to_entity mapper."""

    def _make_model(self, **overrides) -> MagicMock:
        """Create a mock ORM model with default values."""
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
            hesitation_detected=True,
            frustration_detected=False,
            audio_quality_score=0.85,
            background_noise_detected=False,
            analysis_metadata={"key": "val"},
            created_at=now,
            updated_at=now,
            finalized_at=None,
        )
        defaults.update(overrides)
        model = MagicMock(spec=AudioAnalyticsModel)
        for k, v in defaults.items():
            setattr(model, k, v)
        return model

    def test_maps_all_fields(self):
        """All ORM model fields map to entity fields."""
        model = self._make_model()
        entity = model_to_entity(model)

        assert isinstance(entity, AudioAnalytics)
        assert entity.id == 1
        assert entity.interview_exchange_id == 42
        assert entity.transcript == "Test transcript"
        assert entity.transcript_finalized is False
        assert entity.confidence_score == Decimal("0.92")
        assert entity.language_detected == "en"
        assert entity.speech_state == "complete"
        assert entity.speech_rate_wpm == 145
        assert entity.pause_duration_ms == 200
        assert entity.long_pause_count == 3
        assert entity.filler_word_count == 5
        assert entity.filler_rate == Decimal("2.5")
        assert entity.sentiment_score == Decimal("0.35")
        assert entity.hesitation_detected is True
        assert entity.frustration_detected is False
        assert entity.audio_quality_score == Decimal("0.85")
        assert entity.background_noise_detected is False
        assert entity.analysis_metadata == {"key": "val"}

    def test_handles_none_numeric_fields(self):
        """None numeric fields map to None (not Decimal)."""
        model = self._make_model(
            confidence_score=None,
            sentiment_score=None,
            filler_rate=None,
            audio_quality_score=None,
        )
        entity = model_to_entity(model)

        assert entity.confidence_score is None
        assert entity.sentiment_score is None
        assert entity.filler_rate is None
        assert entity.audio_quality_score is None

    def test_finalized_model(self):
        """Finalized model maps correctly."""
        now = datetime.now(timezone.utc)
        model = self._make_model(
            transcript_finalized=True,
            finalized_at=now,
        )
        entity = model_to_entity(model)

        assert entity.transcript_finalized is True
        assert entity.finalized_at == now


class TestCreateDtoToModel:
    """Tests for create_dto_to_model mapper."""

    def test_maps_required_fields(self):
        """Required fields map correctly."""
        dto = AudioAnalyticsCreate(
            interview_exchange_id=42,
            transcript="Test",
            confidence_score=0.9,
        )
        model = create_dto_to_model(dto)

        assert isinstance(model, AudioAnalyticsModel)
        assert model.interview_exchange_id == 42
        assert model.transcript == "Test"
        assert model.confidence_score == 0.9

    def test_maps_all_optional_fields(self):
        """All optional fields map correctly."""
        dto = AudioAnalyticsCreate(
            interview_exchange_id=1,
            transcript="T",
            confidence_score=0.5,
            speech_state="incomplete",
            speech_rate_wpm=120,
            pause_duration_ms=500,
            long_pause_count=4,
            filler_word_count=8,
            filler_rate=3.2,
            sentiment_score=-0.5,
            hesitation_detected=True,
            frustration_detected=True,
            audio_quality_score=0.6,
            background_noise_detected=True,
            language_detected="es",
            analysis_metadata={"extra": "data"},
        )
        model = create_dto_to_model(dto)

        assert model.speech_state == "incomplete"
        assert model.speech_rate_wpm == 120
        assert model.pause_duration_ms == 500
        assert model.hesitation_detected is True
        assert model.language_detected == "es"
        assert model.analysis_metadata == {"extra": "data"}

    def test_defaults_preserved(self):
        """Default values from DTO are passed through to model."""
        dto = AudioAnalyticsCreate(
            interview_exchange_id=1,
            transcript="T",
            confidence_score=0.5,
        )
        model = create_dto_to_model(dto)

        assert model.filler_word_count == 0
        assert model.filler_rate == 0.0
        assert model.hesitation_detected is False
        assert model.frustration_detected is False
        assert model.background_noise_detected is False
