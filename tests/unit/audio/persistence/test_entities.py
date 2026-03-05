"""
Unit Tests — Audio Persistence Entities

Tests for AudioAnalytics, AudioAnalyticsCreate, and AudioAnalyticsUpdate
domain data classes.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.audio.persistence.entities import (
    AudioAnalytics,
    AudioAnalyticsCreate,
    AudioAnalyticsUpdate,
)


class TestAudioAnalytics:
    """Tests for AudioAnalytics entity."""

    def test_default_values(self):
        """Verify sensible defaults for a new entity."""
        entity = AudioAnalytics()
        assert entity.id is None
        assert entity.interview_exchange_id == 0
        assert entity.transcript is None
        assert entity.transcript_finalized is False
        assert entity.confidence_score is None
        assert entity.speech_state == "complete"
        assert entity.long_pause_count == 0
        assert entity.hesitation_detected is False
        assert entity.frustration_detected is False
        assert entity.background_noise_detected is False
        assert entity.analysis_metadata is None
        assert entity.created_at is None
        assert entity.updated_at is None
        assert entity.finalized_at is None

    def test_populated_entity(self):
        """Entity can be fully populated."""
        now = datetime.now(timezone.utc)
        entity = AudioAnalytics(
            id=1,
            interview_exchange_id=42,
            transcript="The answer is dynamic programming.",
            transcript_finalized=True,
            confidence_score=Decimal("0.92"),
            language_detected="en",
            speech_state="complete",
            speech_rate_wpm=145,
            pause_duration_ms=200,
            long_pause_count=3,
            filler_word_count=5,
            filler_rate=Decimal("2.5"),
            sentiment_score=Decimal("0.35"),
            hesitation_detected=True,
            frustration_detected=False,
            audio_quality_score=Decimal("0.85"),
            background_noise_detected=True,
            analysis_metadata={"key": "value"},
            created_at=now,
            updated_at=now,
            finalized_at=now,
        )
        assert entity.id == 1
        assert entity.transcript == "The answer is dynamic programming."
        assert entity.transcript_finalized is True
        assert entity.confidence_score == Decimal("0.92")
        assert entity.sentiment_score == Decimal("0.35")
        assert entity.analysis_metadata == {"key": "value"}

    def test_mutable(self):
        """Entity is mutable (not frozen)."""
        entity = AudioAnalytics()
        entity.transcript = "Updated text"
        entity.transcript_finalized = True
        assert entity.transcript == "Updated text"
        assert entity.transcript_finalized is True


class TestAudioAnalyticsCreate:
    """Tests for AudioAnalyticsCreate input DTO."""

    def test_required_fields(self):
        """Create DTO requires exchange_id, transcript, and confidence_score."""
        dto = AudioAnalyticsCreate(
            interview_exchange_id=1,
            transcript="Test transcript",
            confidence_score=0.9,
        )
        assert dto.interview_exchange_id == 1
        assert dto.transcript == "Test transcript"
        assert dto.confidence_score == 0.9
        assert dto.speech_state == "complete"

    def test_default_optional_fields(self):
        """Verify defaults for optional fields."""
        dto = AudioAnalyticsCreate(
            interview_exchange_id=1,
            transcript="Test",
            confidence_score=0.5,
        )
        assert dto.speech_rate_wpm is None
        assert dto.pause_duration_ms is None
        assert dto.long_pause_count == 0
        assert dto.filler_word_count == 0
        assert dto.filler_rate == 0.0
        assert dto.sentiment_score is None
        assert dto.hesitation_detected is False
        assert dto.frustration_detected is False
        assert dto.audio_quality_score is None
        assert dto.background_noise_detected is False
        assert dto.language_detected is None
        assert dto.analysis_metadata is None

    def test_full_create_dto(self):
        """Create DTO accepts all fields."""
        dto = AudioAnalyticsCreate(
            interview_exchange_id=42,
            transcript="Answer",
            confidence_score=0.95,
            speech_state="incomplete",
            speech_rate_wpm=160,
            pause_duration_ms=300,
            long_pause_count=2,
            filler_word_count=3,
            filler_rate=1.5,
            sentiment_score=-0.2,
            hesitation_detected=True,
            frustration_detected=True,
            audio_quality_score=0.7,
            background_noise_detected=True,
            language_detected="fr",
            analysis_metadata={"extra": "data"},
        )
        assert dto.speech_state == "incomplete"
        assert dto.hesitation_detected is True
        assert dto.language_detected == "fr"


class TestAudioAnalyticsUpdate:
    """Tests for AudioAnalyticsUpdate input DTO."""

    def test_all_fields_default_none(self):
        """All fields default to None (partial update)."""
        dto = AudioAnalyticsUpdate()
        for field_name, value in dto.__dict__.items():
            assert value is None, f"{field_name} should default to None"

    def test_partial_update(self):
        """Only set fields are non-None."""
        dto = AudioAnalyticsUpdate(
            transcript="Updated transcript",
            confidence_score=0.99,
        )
        assert dto.transcript == "Updated transcript"
        assert dto.confidence_score == 0.99
        assert dto.speech_state is None
        assert dto.sentiment_score is None

    def test_non_none_fields_extraction(self):
        """Can extract non-None fields for update."""
        dto = AudioAnalyticsUpdate(
            transcript="New text",
            filler_word_count=10,
        )
        non_none = {k: v for k, v in dto.__dict__.items() if v is not None}
        assert "transcript" in non_none
        assert "filler_word_count" in non_none
        assert "speech_state" not in non_none
