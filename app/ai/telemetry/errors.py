"""
AI Error Classification

Maps provider-specific exceptions to normalized telemetry error types.
Reuses error hierarchy from shared/errors and ai/llm/errors.

Design decisions:
- Never raises exceptions (returns string classification)
- Unknown errors classified as "provider_error"
- Classification is deterministic (same exception → same type)
"""

from .contracts import AIErrorType


def classify_error(error: Exception) -> str:
    """
    Classify an exception into a telemetry error type.

    Maps provider-specific exceptions from ai/llm/errors and shared/errors
    to normalized AIErrorType strings for telemetry recording.

    Args:
        error: The exception to classify.

    Returns:
        Error type string (matches AIErrorType values).

    Invariant:
        - Never raises an exception
        - Unknown errors → "provider_error"
        - Classification based on exception type hierarchy
    """
    try:
        return _classify_by_type(error)
    except Exception:
        # Defensive: classification itself should never fail
        return AIErrorType.PROVIDER_ERROR.value


def _classify_by_type(error: Exception) -> str:
    """
    Internal classification by exception type.

    Uses lazy imports to avoid circular dependencies.
    Checks from most specific to least specific.
    """
    # Lazy imports to avoid circular dependency with ai/llm
    # and to ensure this module works even if ai/llm is not fully loaded
    try:
        from app.ai.llm.errors import (
            LLMTimeoutError,
            LLMRateLimitError,
            LLMAuthenticationError,
            LLMSchemaValidationError,
            LLMContentFilterError,
            LLMModelNotFoundError,
            LLMContextLengthError,
            LLMProviderError,
        )

        # Most specific first
        if isinstance(error, LLMTimeoutError):
            return AIErrorType.TIMEOUT.value

        if isinstance(error, LLMRateLimitError):
            return AIErrorType.RATE_LIMIT.value

        if isinstance(error, LLMAuthenticationError):
            return AIErrorType.AUTHENTICATION.value

        if isinstance(error, LLMSchemaValidationError):
            return AIErrorType.SCHEMA_VALIDATION.value

        if isinstance(error, LLMContentFilterError):
            return AIErrorType.CONTENT_FILTER.value

        if isinstance(error, LLMModelNotFoundError):
            return AIErrorType.MODEL_NOT_FOUND.value

        if isinstance(error, LLMContextLengthError):
            return AIErrorType.CONTEXT_LENGTH.value

        if isinstance(error, LLMProviderError):
            return AIErrorType.PROVIDER_ERROR.value

    except ImportError:
        # ai/llm not available — fall through to shared errors
        pass

    # Check shared error hierarchy
    try:
        from app.shared.errors import (
            AIProviderTimeoutError,
            AIProviderError,
            ValidationError,
            AuthenticationError,
        )

        if isinstance(error, AIProviderTimeoutError):
            return AIErrorType.TIMEOUT.value

        if isinstance(error, ValidationError):
            return AIErrorType.SCHEMA_VALIDATION.value

        if isinstance(error, AuthenticationError):
            return AIErrorType.AUTHENTICATION.value

        if isinstance(error, AIProviderError):
            return AIErrorType.PROVIDER_ERROR.value

    except ImportError:
        pass

    # Check standard library exceptions
    if isinstance(error, TimeoutError):
        return AIErrorType.TIMEOUT.value

    if isinstance(error, ConnectionError):
        return AIErrorType.PROVIDER_ERROR.value

    # Check by error class name (fallback for dynamically-typed errors)
    error_name = type(error).__name__.lower()

    if "timeout" in error_name:
        return AIErrorType.TIMEOUT.value

    if "ratelimit" in error_name or "rate_limit" in error_name:
        return AIErrorType.RATE_LIMIT.value

    if "auth" in error_name:
        return AIErrorType.AUTHENTICATION.value

    # Default: provider_error
    return AIErrorType.PROVIDER_ERROR.value
