"""
Unit tests for transcription exception hierarchy.

Validates error_code, http_status_code, message formatting, and
metadata for all transcription-specific exceptions.
"""

import pytest

from app.audio.transcription.exceptions import (
    AllProvidersFailedError,
    ProviderConfigurationError,
    ProviderNotFoundError,
    TranscriptionError,
    TranscriptionTimeoutError,
    UnsupportedFeatureError,
)
from app.shared.errors import BaseError, ConfigurationError


class TestTranscriptionError:
    """Tests for the base TranscriptionError."""

    def test_inherits_base_error(self):
        err = TranscriptionError(message="test")
        assert isinstance(err, BaseError)

    def test_default_fields(self):
        err = TranscriptionError(message="something failed")
        assert err.error_code == "TRANSCRIPTION_ERROR"
        assert err.http_status_code == 502
        assert err.message == "something failed"

    def test_custom_error_code(self):
        err = TranscriptionError(
            message="custom", error_code="CUSTOM_ERROR", http_status_code=400
        )
        assert err.error_code == "CUSTOM_ERROR"
        assert err.http_status_code == 400


class TestProviderNotFoundError:
    """Tests for ProviderNotFoundError."""

    def test_message_includes_provider(self):
        err = ProviderNotFoundError("unknown_provider")
        assert "unknown_provider" in err.message
        assert err.error_code == "TRANSCRIPTION_PROVIDER_NOT_FOUND"
        assert err.http_status_code == 400

    def test_metadata_contains_provider(self):
        err = ProviderNotFoundError("bogus")
        assert err.metadata["provider"] == "bogus"


class TestProviderConfigurationError:
    """Tests for ProviderConfigurationError."""

    def test_inherits_configuration_error(self):
        err = ProviderConfigurationError(
            provider="whisper", detail="API key missing"
        )
        assert isinstance(err, ConfigurationError)
        assert err.http_status_code == 500
        assert "whisper" in err.message
        assert "API key missing" in err.message

    def test_metadata(self):
        err = ProviderConfigurationError(
            provider="google", detail="credentials expired"
        )
        assert err.metadata["provider"] == "google"
        assert err.metadata["detail"] == "credentials expired"


class TestTranscriptionTimeoutError:
    """Tests for TranscriptionTimeoutError."""

    def test_fields(self):
        err = TranscriptionTimeoutError(provider="whisper", timeout_s=10.0)
        assert err.error_code == "TRANSCRIPTION_TIMEOUT"
        assert err.http_status_code == 504
        assert "10.0" in err.message
        assert err.metadata["provider"] == "whisper"
        assert err.metadata["timeout_seconds"] == 10.0


class TestUnsupportedFeatureError:
    """Tests for UnsupportedFeatureError."""

    def test_fields(self):
        err = UnsupportedFeatureError(provider="whisper", feature="streaming")
        assert err.error_code == "TRANSCRIPTION_UNSUPPORTED_FEATURE"
        assert err.http_status_code == 400
        assert "whisper" in err.message
        assert "streaming" in err.message
        assert err.metadata["feature"] == "streaming"


class TestAllProvidersFailedError:
    """Tests for AllProvidersFailedError."""

    def test_fields(self):
        err = AllProvidersFailedError(providers=["whisper", "google", "local"])
        assert err.error_code == "TRANSCRIPTION_ALL_PROVIDERS_FAILED"
        assert err.http_status_code == 502
        assert "whisper" in err.message
        assert "google" in err.message
        assert "local" in err.message
        assert err.metadata["providers"] == ["whisper", "google", "local"]

    def test_single_provider(self):
        err = AllProvidersFailedError(providers=["whisper"])
        assert "whisper" in err.message
