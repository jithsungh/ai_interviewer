"""
Unit tests for TranscriptionProviderSelector.

Validates provider selection, API key requirements, unknown providers,
and local provider behaviour.
"""

import pytest

from app.audio.transcription.contracts import TranscriptionConfig
from app.audio.transcription.exceptions import (
    ProviderConfigurationError,
    ProviderNotFoundError,
)
from app.audio.transcription.provider_selector import TranscriptionProviderSelector
from app.audio.transcription.providers.whisper import WhisperTranscriber
from app.audio.transcription.providers.local_whisper import LocalWhisperTranscriber


class TestTranscriptionProviderSelector:
    """Tests for provider selection factory."""

    @pytest.fixture
    def selector(self):
        return TranscriptionProviderSelector()

    def test_select_whisper_provider(self, selector):
        provider = selector.get_provider("whisper", api_key="test_key")
        assert isinstance(provider, WhisperTranscriber)

    def test_select_local_provider(self, selector):
        provider = selector.get_provider("local")
        assert isinstance(provider, LocalWhisperTranscriber)

    def test_unknown_provider_raises(self, selector):
        with pytest.raises(ProviderNotFoundError) as exc_info:
            selector.get_provider("unknown_provider")
        assert "unknown_provider" in str(exc_info.value.message)

    def test_external_provider_requires_api_key(self, selector):
        with pytest.raises(ProviderConfigurationError):
            selector.get_provider("whisper", api_key=None)

    def test_external_provider_empty_api_key_raises(self, selector):
        with pytest.raises(ProviderConfigurationError):
            selector.get_provider("whisper", api_key="")

    def test_local_provider_no_api_key_required(self, selector):
        provider = selector.get_provider("local", api_key=None)
        assert isinstance(provider, LocalWhisperTranscriber)

    def test_google_provider_requires_api_key(self, selector):
        with pytest.raises(ProviderConfigurationError):
            selector.get_provider("google", api_key=None)

    def test_google_provider_with_key(self, selector):
        from app.audio.transcription.providers.google_speech import (
            GoogleSpeechTranscriber,
        )

        provider = selector.get_provider("google", api_key="test_key")
        assert isinstance(provider, GoogleSpeechTranscriber)

    def test_azure_not_yet_implemented(self, selector):
        with pytest.raises(ProviderNotFoundError) as exc_info:
            selector.get_provider("azure", api_key="key")
        assert "not yet implemented" in str(exc_info.value.message)

    def test_assemblyai_not_yet_implemented(self, selector):
        with pytest.raises(ProviderNotFoundError) as exc_info:
            selector.get_provider("assemblyai", api_key="key")
        assert "not yet implemented" in str(exc_info.value.message)

    def test_config_model_override(self, selector):
        config = TranscriptionConfig(provider="whisper", model="whisper-large-v3")
        provider = selector.get_provider("whisper", api_key="key", config=config)
        assert isinstance(provider, WhisperTranscriber)
        assert provider._model == "whisper-large-v3"

    def test_config_language_override(self, selector):
        config = TranscriptionConfig(provider="local", model="small.en", language="en")
        provider = selector.get_provider("local", config=config)
        assert isinstance(provider, LocalWhisperTranscriber)
        assert provider._model_name == "small.en"

    def test_case_insensitive_provider_name(self, selector):
        provider = selector.get_provider("WHISPER", api_key="key")
        assert isinstance(provider, WhisperTranscriber)

    def test_whitespace_trimmed(self, selector):
        provider = selector.get_provider("  local  ")
        assert isinstance(provider, LocalWhisperTranscriber)
