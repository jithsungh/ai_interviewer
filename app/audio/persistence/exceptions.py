"""
Audio Persistence — Domain-Specific Exceptions

Exceptions raised by the audio persistence layer.
All inherit from shared base error classes to maintain
consistent HTTP status codes and error formatting.

References:
- audio/persistence/REQUIREMENTS.md §5 (Error Cases)
- app/shared/errors/exceptions.py (base classes)
"""

from __future__ import annotations

from app.shared.errors.exceptions import BaseError, ConflictError


class DuplicateAnalyticsError(ConflictError):
    """
    Raised when attempting to create audio analytics for an
    exchange that already has an analytics record.

    Maps to HTTP 409 Conflict.
    """

    def __init__(self, exchange_id: int) -> None:
        super().__init__(
            message=(
                f"Audio analytics already exists for "
                f"exchange_id={exchange_id}"
            ),
            metadata={"exchange_id": exchange_id},
        )
        self.error_code = "DUPLICATE_ANALYTICS"
        self.exchange_id = exchange_id


class ImmutabilityError(BaseError):
    """
    Raised when attempting to update a finalized (immutable)
    audio analytics record.

    Maps to HTTP 400 Bad Request (domain invariant violation).
    """

    def __init__(self, analytics_id: int) -> None:
        super().__init__(
            error_code="ANALYTICS_IMMUTABLE",
            message=(
                f"Cannot update finalized audio analytics: {analytics_id}. "
                f"Transcripts are immutable after finalization."
            ),
            http_status_code=400,
            metadata={"analytics_id": analytics_id},
        )
        self.analytics_id = analytics_id
