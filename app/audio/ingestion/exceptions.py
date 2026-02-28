"""
Audio Ingestion Exceptions

Domain-specific errors for the audio ingestion module.
All exceptions inherit from the shared BaseError hierarchy
to ensure consistent error serialisation and HTTP status codes.
"""

from app.shared.errors import BaseError, ConflictError, NotFoundError, ValidationError


class AudioIngestionError(BaseError):
    """
    Base exception for all audio ingestion errors.

    Subclasses carry specific error_code values for machine-readable consumption.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AUDIO_INGESTION_ERROR",
        http_status_code: int = 500,
        **kwargs,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            http_status_code=http_status_code,
            **kwargs,
        )


class SessionAlreadyActiveError(ConflictError):
    """Raised when attempting to start a session that already exists."""

    def __init__(self, exchange_id: int, *, request_id=None):
        super().__init__(
            message=f"Audio session already active for exchange {exchange_id}",
            request_id=request_id,
            metadata={"exchange_id": exchange_id},
        )


class SessionNotFoundError(NotFoundError):
    """Raised when referencing a session that does not exist."""

    def __init__(self, exchange_id: int, *, request_id=None):
        super().__init__(
            resource_type="AudioSession",
            resource_id=exchange_id,
            request_id=request_id,
        )


class SessionClosedError(ConflictError):
    """Raised when audio arrives after the session has been stopped."""

    def __init__(self, exchange_id: int, *, request_id=None):
        super().__init__(
            message=f"Audio session for exchange {exchange_id} is closed",
            request_id=request_id,
            metadata={"exchange_id": exchange_id},
        )


class SessionPausedError(ConflictError):
    """Raised when audio arrives while the session is paused."""

    def __init__(self, exchange_id: int, *, request_id=None):
        super().__init__(
            message=f"Audio session for exchange {exchange_id} is paused",
            request_id=request_id,
            metadata={"exchange_id": exchange_id},
        )


class InvalidExchangeStageError(ValidationError):
    """Raised when exchange is not in the expected stage for audio intake."""

    def __init__(self, exchange_id: int, current_stage: str, *, request_id=None):
        super().__init__(
            message=(
                f"Exchange {exchange_id} is in stage '{current_stage}'; "
                "audio ingestion requires 'responding' stage"
            ),
            field="interview_exchange_id",
            request_id=request_id,
            metadata={"exchange_id": exchange_id, "current_stage": current_stage},
        )
