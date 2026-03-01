"""
Audio Analysis Exceptions

Domain-specific errors for the audio analysis module.
All exceptions inherit from the shared BaseError hierarchy
to ensure consistent error serialisation and HTTP status codes.

Follows the same pattern as ``audio.ingestion.exceptions``
and ``audio.transcription.exceptions``.
"""

from app.shared.errors import BaseError, ConfigurationError, ValidationError


class AudioAnalysisError(BaseError):
    """
    Base exception for all audio analysis errors.

    Subclasses carry specific ``error_code`` values for
    machine-readable consumption.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AUDIO_ANALYSIS_ERROR",
        http_status_code: int = 500,
        **kwargs,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            http_status_code=http_status_code,
            **kwargs,
        )


class SpacyModelNotFoundError(ConfigurationError):
    """Raised when the required spaCy model is not installed."""

    def __init__(self, model_name: str, *, request_id=None):
        super().__init__(
            message=(
                f"spaCy model '{model_name}' is not installed. "
                f"Run: python -m spacy download {model_name}"
            ),
            request_id=request_id,
            metadata={"model_name": model_name},
        )


class AnalysisValidationError(ValidationError):
    """Raised when analysis input fails validation."""

    def __init__(self, detail: str, *, field: str = None, request_id=None):
        super().__init__(
            message=f"Audio analysis validation error: {detail}",
            field=field,
            request_id=request_id,
        )


class SentimentEngineError(AudioAnalysisError):
    """Raised when the sentiment analysis engine fails."""

    def __init__(self, engine: str, detail: str, *, request_id=None):
        super().__init__(
            message=f"Sentiment engine '{engine}' failed: {detail}",
            error_code="SENTIMENT_ENGINE_ERROR",
            http_status_code=500,
            request_id=request_id,
            metadata={"engine": engine, "detail": detail},
        )
