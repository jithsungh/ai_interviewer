"""
Unit Tests for Error Classification

Tests classify_error() with all LLM error types, shared error types,
standard library exceptions, and unknown errors.
"""

import pytest

from app.ai.telemetry.errors import classify_error
from app.ai.telemetry.contracts import AIErrorType


class TestClassifyLLMErrors:
    """Test classification of ai/llm/errors exceptions"""

    def test_timeout_classified(self):
        """LLMTimeoutError classified as timeout"""
        from app.ai.llm.errors import LLMTimeoutError

        error = LLMTimeoutError(
            provider="openai",
            timeout_seconds=30,
        )
        assert classify_error(error) == "timeout"

    def test_rate_limit_classified(self):
        """LLMRateLimitError classified as rate_limit"""
        from app.ai.llm.errors import LLMRateLimitError

        error = LLMRateLimitError(
            provider="openai",
            message="Rate limit exceeded",
        )
        assert classify_error(error) == "rate_limit"

    def test_authentication_classified(self):
        """LLMAuthenticationError classified as authentication"""
        from app.ai.llm.errors import LLMAuthenticationError

        error = LLMAuthenticationError(
            provider="openai",
            message="Invalid API key",
        )
        assert classify_error(error) == "authentication"

    def test_schema_validation_classified(self):
        """LLMSchemaValidationError classified as schema_validation"""
        from app.ai.llm.errors import LLMSchemaValidationError

        error = LLMSchemaValidationError(
            message="Invalid response schema",
        )
        assert classify_error(error) == "schema_validation"

    def test_content_filter_classified(self):
        """LLMContentFilterError classified as content_filter"""
        from app.ai.llm.errors import LLMContentFilterError

        error = LLMContentFilterError(
            provider="openai",
            message="Content policy violation",
        )
        assert classify_error(error) == "content_filter"

    def test_model_not_found_classified(self):
        """LLMModelNotFoundError classified as model_not_found"""
        from app.ai.llm.errors import LLMModelNotFoundError

        error = LLMModelNotFoundError(
            provider="openai",
            model_id="nonexistent-model",
        )
        assert classify_error(error) == "model_not_found"

    def test_context_length_classified(self):
        """LLMContextLengthError classified as context_length"""
        from app.ai.llm.errors import LLMContextLengthError

        error = LLMContextLengthError(
            provider="openai",
            model_id="gpt-4",
            max_tokens=8192,
            actual_tokens=10000,
        )
        assert classify_error(error) == "context_length"

    def test_generic_provider_error_classified(self):
        """LLMProviderError classified as provider_error"""
        from app.ai.llm.errors import LLMProviderError

        error = LLMProviderError(
            provider="openai",
            message="Some provider error",
        )
        assert classify_error(error) == "provider_error"


class TestClassifySharedErrors:
    """Test classification of shared/errors exceptions"""

    def test_ai_provider_timeout_classified(self):
        """AIProviderTimeoutError classified as timeout"""
        from app.shared.errors import AIProviderTimeoutError

        error = AIProviderTimeoutError(
            provider="openai",
            timeout_s=30,
        )
        assert classify_error(error) == "timeout"

    def test_validation_error_classified(self):
        """ValidationError classified as schema_validation"""
        from app.shared.errors import ValidationError

        error = ValidationError(
            message="Invalid input",
        )
        assert classify_error(error) == "schema_validation"

    def test_authentication_error_classified(self):
        """AuthenticationError classified as authentication"""
        from app.shared.errors import AuthenticationError

        error = AuthenticationError(
            message="Authentication failed",
        )
        assert classify_error(error) == "authentication"

    def test_ai_provider_error_classified(self):
        """AIProviderError classified as provider_error"""
        from app.shared.errors import AIProviderError

        error = AIProviderError(
            provider="openai",
            message="Provider error",
        )
        assert classify_error(error) == "provider_error"


class TestClassifyStdlibErrors:
    """Test classification of standard library exceptions"""

    def test_stdlib_timeout_classified(self):
        """Standard TimeoutError classified as timeout"""
        error = TimeoutError("Connection timed out")
        assert classify_error(error) == "timeout"

    def test_connection_error_classified(self):
        """ConnectionError classified as provider_error"""
        error = ConnectionError("Connection refused")
        assert classify_error(error) == "provider_error"


class TestClassifyUnknownErrors:
    """Test classification of unrecognized exceptions"""

    def test_unknown_error_classified_as_provider_error(self):
        """Unknown errors classified as provider_error"""
        error = Exception("Something went wrong")
        assert classify_error(error) == "provider_error"

    def test_value_error_classified_as_provider_error(self):
        """ValueError classified as provider_error"""
        error = ValueError("Bad value")
        assert classify_error(error) == "provider_error"

    def test_runtime_error_classified_as_provider_error(self):
        """RuntimeError classified as provider_error"""
        error = RuntimeError("Runtime issue")
        assert classify_error(error) == "provider_error"

    def test_error_with_timeout_in_name(self):
        """Custom error with 'timeout' in class name classified as timeout"""

        class CustomTimeoutError(Exception):
            pass

        error = CustomTimeoutError("Custom timeout")
        assert classify_error(error) == "timeout"

    def test_error_with_ratelimit_in_name(self):
        """Custom error with 'ratelimit' in class name classified as rate_limit"""

        class RateLimitException(Exception):
            pass

        error = RateLimitException("Custom rate limit")
        assert classify_error(error) == "rate_limit"

    def test_error_with_auth_in_name(self):
        """Custom error with 'auth' in class name classified as authentication"""

        class AuthFailedException(Exception):
            pass

        error = AuthFailedException("Auth failed")
        assert classify_error(error) == "authentication"


class TestClassifyNeverRaises:
    """Test that classify_error never raises exceptions"""

    def test_none_like_error(self):
        """handles weird error object"""

        class WeirdError(Exception):
            def __class__(self):
                raise RuntimeError("broken __class__")

        # Should not raise, even with weird error
        result = classify_error(WeirdError("weird"))
        assert isinstance(result, str)

    def test_classify_returns_string(self):
        """classify_error always returns a string"""
        errors = [
            Exception("test"),
            ValueError("test"),
            TimeoutError("test"),
            ConnectionError("test"),
        ]
        for error in errors:
            result = classify_error(error)
            assert isinstance(result, str)
            assert result in [e.value for e in AIErrorType]
