"""
Audio Persistence Protocols — Abstract interfaces for data access

Domain services depend on these protocols, never on concrete
SQLAlchemy repository classes.  Uses ``typing.Protocol`` for
structural subtyping (consistent with ``app/coding/persistence/protocols.py``).

References:
- audio/persistence/REQUIREMENTS.md §7 (Repository Pattern)
- coding/persistence/protocols.py (pattern reference)
"""

from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from app.audio.persistence.entities import (
    AudioAnalytics,
    AudioAnalyticsCreate,
    AudioAnalyticsUpdate,
)


@runtime_checkable
class AudioAnalyticsRepository(Protocol):
    """Repository protocol for the ``audio_analytics`` table."""

    def create(self, data: AudioAnalyticsCreate) -> AudioAnalytics:
        """
        Create a new audio analytics record.

        Raises ``DuplicateAnalyticsError`` if a record already exists
        for the exchange.
        """
        ...

    def get_by_id(self, analytics_id: int) -> Optional[AudioAnalytics]:
        """Get analytics by primary key."""
        ...

    def get_by_exchange_id(self, exchange_id: int) -> Optional[AudioAnalytics]:
        """Get analytics for a specific exchange (at most one)."""
        ...

    def update(
        self, analytics_id: int, data: AudioAnalyticsUpdate
    ) -> AudioAnalytics:
        """
        Update analytics (only if not finalized).

        Raises ``ImmutabilityError`` if the record is finalized.
        Raises ``NotFoundError`` if the record does not exist.
        """
        ...

    def finalize(self, analytics_id: int) -> AudioAnalytics:
        """
        Mark transcript as finalized (immutable).

        Idempotent: returns existing record if already finalized.
        """
        ...

    def get_by_submission_id(
        self, submission_id: int
    ) -> List[AudioAnalytics]:
        """Get all analytics for an interview submission."""
        ...

    def is_finalized(self, exchange_id: int) -> bool:
        """Check if analytics for exchange is finalized."""
        ...

    def create_or_get(self, data: AudioAnalyticsCreate) -> AudioAnalytics:
        """
        Create analytics or return existing (idempotent).

        If a record already exists for the exchange, returns it
        instead of raising an error.
        """
        ...
