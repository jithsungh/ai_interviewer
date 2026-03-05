"""
Audio Persistence Mappers — Bidirectional ORM ↔ entity conversion

Keeps the audio domain layer free of SQLAlchemy dependencies.
Follows the pattern established by ``app/coding/persistence/mappers.py``.

References:
- coding/persistence/mappers.py (pattern reference)
- audio/persistence/REQUIREMENTS.md §4 (ORM → entity mapping)
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from app.audio.persistence.entities import AudioAnalytics, AudioAnalyticsCreate
from app.audio.persistence.models import AudioAnalyticsModel


def model_to_entity(m: AudioAnalyticsModel) -> AudioAnalytics:
    """Convert an ORM ``AudioAnalyticsModel`` to a domain ``AudioAnalytics``."""
    return AudioAnalytics(
        id=m.id,
        interview_exchange_id=m.interview_exchange_id,
        transcript=m.transcript,
        transcript_finalized=m.transcript_finalized,
        confidence_score=(
            Decimal(str(m.confidence_score))
            if m.confidence_score is not None
            else None
        ),
        language_detected=m.language_detected,
        speech_state=m.speech_state,
        speech_rate_wpm=m.speech_rate_wpm,
        pause_duration_ms=m.pause_duration_ms,
        long_pause_count=m.long_pause_count or 0,
        filler_word_count=m.filler_word_count,
        filler_rate=(
            Decimal(str(m.filler_rate))
            if m.filler_rate is not None
            else None
        ),
        sentiment_score=(
            Decimal(str(m.sentiment_score))
            if m.sentiment_score is not None
            else None
        ),
        hesitation_detected=m.hesitation_detected,
        frustration_detected=m.frustration_detected,
        audio_quality_score=(
            Decimal(str(m.audio_quality_score))
            if m.audio_quality_score is not None
            else None
        ),
        background_noise_detected=m.background_noise_detected,
        analysis_metadata=m.analysis_metadata,
        created_at=m.created_at,
        updated_at=m.updated_at,
        finalized_at=m.finalized_at,
    )


def create_dto_to_model(dto: AudioAnalyticsCreate) -> AudioAnalyticsModel:
    """Convert an ``AudioAnalyticsCreate`` DTO to an ORM model for INSERT."""
    model = AudioAnalyticsModel()
    model.interview_exchange_id = dto.interview_exchange_id
    model.transcript = dto.transcript
    model.confidence_score = dto.confidence_score
    model.speech_state = dto.speech_state
    model.speech_rate_wpm = dto.speech_rate_wpm
    model.pause_duration_ms = dto.pause_duration_ms
    model.long_pause_count = dto.long_pause_count
    model.filler_word_count = dto.filler_word_count
    model.filler_rate = dto.filler_rate
    model.sentiment_score = dto.sentiment_score
    model.hesitation_detected = dto.hesitation_detected
    model.frustration_detected = dto.frustration_detected
    model.audio_quality_score = dto.audio_quality_score
    model.background_noise_detected = dto.background_noise_detected
    model.language_detected = dto.language_detected
    model.analysis_metadata = dto.analysis_metadata
    return model
