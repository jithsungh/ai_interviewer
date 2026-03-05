"""
Audio Persistence Submodule

Repository pattern implementation for audio analytics data access.
This is the ONLY layer that directly accesses the ``audio_analytics`` table.

Public interface:
- AudioAnalytics, AudioAnalyticsCreate, AudioAnalyticsUpdate (entities)
- AudioAnalyticsRepository (protocol)
- SqlAudioAnalyticsRepository (implementation)
- DuplicateAnalyticsError, ImmutabilityError (exceptions)
"""

from app.audio.persistence.entities import (
    AudioAnalytics,
    AudioAnalyticsCreate,
    AudioAnalyticsUpdate,
)
from app.audio.persistence.exceptions import (
    DuplicateAnalyticsError,
    ImmutabilityError,
)
from app.audio.persistence.protocols import AudioAnalyticsRepository
from app.audio.persistence.repository import SqlAudioAnalyticsRepository

__all__ = [
    # Entities
    "AudioAnalytics",
    "AudioAnalyticsCreate",
    "AudioAnalyticsUpdate",
    # Protocol
    "AudioAnalyticsRepository",
    # Implementation
    "SqlAudioAnalyticsRepository",
    # Exceptions
    "DuplicateAnalyticsError",
    "ImmutabilityError",
]
