"""
Audio Transcription Exceptions

Domain-specific errors for the transcription module.
All exceptions inherit from the shared BaseError hierarchy
to ensure consistent error serialisation and HTTP status codes.

Follows the same pattern as ``audio.ingestion.exceptions``.
"""

from app.shared.errors import BaseError, ConfigurationError


class TranscriptionError(BaseError):
    """
    Base exception for all transcription errors.

    Subclasses carry specific ``error_code`` values for
    machine-readable consumption.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "TRANSCRIPTION_ERROR",
        http_status_code: int = 502,
        **kwargs,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            http_status_code=http_status_code,
            **kwargs,
        )


class ProviderNotFoundError(TranscriptionError):
    """Raised when the requested transcription provider is unknown."""

    def __init__(self, provider: str, *, request_id=None):
        super().__init__(
            message=f"Transcription provider '{provider}' is not supported",
            error_code="TRANSCRIPTION_PROVIDER_NOT_FOUND",
            http_status_code=400,
            request_id=request_id,
            metadata={"provider": provider},
        )


class ProviderConfigurationError(ConfigurationError):
    """Raised when a provider is missing required configuration (e.g. API key)."""

    def __init__(self, provider: str, detail: str, *, request_id=None):
        super().__init__(
            message=f"Transcription provider '{provider}' misconfigured: {detail}",
            request_id=request_id,
            metadata={"provider": provider, "detail": detail},
        )


class TranscriptionTimeoutError(TranscriptionError):
    """Raised when the transcription call exceeds the configured timeout."""

    def __init__(self, provider: str, timeout_s: float, *, request_id=None):
        super().__init__(
            message=f"Transcription via '{provider}' timed out after {timeout_s}s",
            error_code="TRANSCRIPTION_TIMEOUT",
            http_status_code=504,
            request_id=request_id,
            metadata={"provider": provider, "timeout_seconds": timeout_s},
        )


class UnsupportedFeatureError(TranscriptionError):
    """Raised when the provider does not support the requested feature."""

    def __init__(self, provider: str, feature: str, *, request_id=None):
        super().__init__(
            message=f"Provider '{provider}' does not support '{feature}'",
            error_code="TRANSCRIPTION_UNSUPPORTED_FEATURE",
            http_status_code=400,
            request_id=request_id,
            metadata={"provider": provider, "feature": feature},
        )


class AllProvidersFailedError(TranscriptionError):
    """Raised when fallback transcription exhausted all configured providers."""

    def __init__(self, providers: list[str], *, request_id=None):
        super().__init__(
            message=f"All transcription providers failed: {', '.join(providers)}",
            error_code="TRANSCRIPTION_ALL_PROVIDERS_FAILED",
            http_status_code=502,
            request_id=request_id,
            metadata={"providers": providers},
        )
