"""
Audio Persistence Entities — Domain data classes for audio analytics

Plain dataclasses representing rows from the ``audio_analytics`` table.
Returned by repository methods and consumed by the audio domain layer.

Contains ZERO business logic and ZERO ORM dependencies.

Follows the pattern established by ``app/coding/persistence/entities.py``.

References:
- audio/persistence/REQUIREMENTS.md §2 (Owned Tables)
- audio/persistence/REQUIREMENTS.md §4 (Output Contracts)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional


@dataclass
class AudioAnalytics:
    """
    Domain entity for an audio analytics record.

    Maps 1:1 to the ``audio_analytics`` table.
    Mutable to allow repository construction and updates.
    """

    id: Optional[int] = None
    interview_exchange_id: int = 0

    # Transcript data
    transcript: Optional[str] = None
    transcript_finalized: bool = False
    confidence_score: Optional[Decimal] = None
    language_detected: Optional[str] = None

    # Speech characteristics
    speech_state: str = "complete"
    speech_rate_wpm: Optional[int] = None
    pause_duration_ms: Optional[int] = None
    long_pause_count: int = 0

    # Behavioral signals
    filler_word_count: Optional[int] = None
    filler_rate: Optional[Decimal] = None
    sentiment_score: Optional[Decimal] = None
    hesitation_detected: bool = False
    frustration_detected: bool = False

    # Audio quality
    audio_quality_score: Optional[Decimal] = None
    background_noise_detected: bool = False

    # Metadata
    analysis_metadata: Optional[Dict[str, Any]] = None

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None


@dataclass
class AudioAnalyticsCreate:
    """
    Input DTO for creating a new audio analytics record.

    Used as the input contract for ``AudioAnalyticsRepository.create()``.
    """

    interview_exchange_id: int
    transcript: str
    confidence_score: float
    speech_state: str = "complete"

    # Optional speech characteristics
    speech_rate_wpm: Optional[int] = None
    pause_duration_ms: Optional[int] = None
    long_pause_count: int = 0

    # Optional behavioral signals
    filler_word_count: int = 0
    filler_rate: float = 0.0
    sentiment_score: Optional[float] = None
    hesitation_detected: bool = False
    frustration_detected: bool = False

    # Optional audio quality
    audio_quality_score: Optional[float] = None
    background_noise_detected: bool = False
    language_detected: Optional[str] = None

    # Optional metadata
    analysis_metadata: Optional[Dict[str, Any]] = None


@dataclass
class AudioAnalyticsUpdate:
    """
    Input DTO for updating an audio analytics record.

    Only non-None fields are applied. Updates are rejected if the
    record has been finalized (``transcript_finalized=True``).
    """

    transcript: Optional[str] = None
    confidence_score: Optional[float] = None
    speech_state: Optional[str] = None
    speech_rate_wpm: Optional[int] = None
    pause_duration_ms: Optional[int] = None
    long_pause_count: Optional[int] = None
    filler_word_count: Optional[int] = None
    filler_rate: Optional[float] = None
    sentiment_score: Optional[float] = None
    hesitation_detected: Optional[bool] = None
    frustration_detected: Optional[bool] = None
    audio_quality_score: Optional[float] = None
    background_noise_detected: Optional[bool] = None
    language_detected: Optional[str] = None
    analysis_metadata: Optional[Dict[str, Any]] = None
