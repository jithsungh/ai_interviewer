"""
Integration tests for TranscriptionService.

Tests the full service stack with mocked external APIs.
Validates retry logic, timeout handling, and provider interaction
end-to-end (service → provider selector → provider → result).
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.audio.transcription.contracts import (
    TranscriptionRequest,
    TranscriptionResult,
)
from app.audio.transcription.exceptions import TranscriptionError


@pytest.fixture
def audio_request():
    """Standard transcription request with 16 kHz mono PCM audio."""
    import numpy as np

    audio = np.zeros(16000, dtype=np.int16)  # 1 second of silence
    return TranscriptionRequest(
        audio_data=audio.tobytes(),
        sample_rate=16000,
        language="en",
    )


class TestTranscriptionServiceIntegration:
    """End-to-end service tests with mocked external APIs."""

    @pytest.mark.asyncio
    async def test_whisper_end_to_end(self, audio_request):
        """Full round-trip: service → WhisperTranscriber → mock OpenAI → result."""
        from app.audio.transcription.service import TranscriptionService

        mock_response = MagicMock()
        mock_response.text = "Integration test transcript"
        mock_response.language = "en"
        mock_response.segments = [
            {"text": "Integration", "start": 0.0, "end": 0.5, "confidence": 0.95},
            {"text": "test", "start": 0.5, "end": 0.8, "confidence": 0.90},
            {"text": "transcript", "start": 0.8, "end": 1.3, "confidence": 0.88},
        ]

        with patch(
            "app.audio.transcription.providers.whisper.openai"
        ) as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                return_value=mock_response
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            svc = TranscriptionService(
                provider="whisper",
                api_key="test_key",
                max_retries=1,
                timeout_s=5.0,
            )
            result = await svc.transcribe(audio_request)

            assert result.transcript == "Integration test transcript"
            assert result.confidence_score > 0.85
            assert len(result.segments) == 3
            assert result.provider_metadata["provider"] == "whisper"

    @pytest.mark.asyncio
    async def test_retry_on_api_failure(self, audio_request):
        """Service retries on transient API failure, then succeeds."""
        from app.audio.transcription.service import TranscriptionService

        success_response = MagicMock()
        success_response.text = "Retry success"
        success_response.language = "en"
        success_response.segments = []

        with patch(
            "app.audio.transcription.providers.whisper.openai"
        ) as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                side_effect=[
                    Exception("Transient error"),
                    Exception("Transient error"),
                    success_response,
                ]
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            svc = TranscriptionService(
                provider="whisper",
                api_key="test_key",
                max_retries=3,
                retry_delay_s=0.01,  # Fast for testing
                timeout_s=5.0,
            )
            result = await svc.transcribe(audio_request)

            assert result.transcript == "Retry success"
            assert mock_client.audio.transcriptions.create.call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_propagated(self, audio_request):
        """Service raises on timeout."""
        from app.audio.transcription.service import TranscriptionService

        async def slow_api(*args, **kwargs):
            await asyncio.sleep(5)
            return MagicMock(text="late", language="en", segments=[])

        with patch(
            "app.audio.transcription.providers.whisper.openai"
        ) as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = slow_api
            mock_openai.AsyncOpenAI.return_value = mock_client

            svc = TranscriptionService(
                provider="whisper",
                api_key="test_key",
                max_retries=1,
                retry_delay_s=0.01,
                timeout_s=0.05,
            )

            with pytest.raises(TranscriptionError):
                await svc.transcribe(audio_request)

    @pytest.mark.asyncio
    async def test_empty_audio_transcription(self):
        """Empty (silent) audio returns empty transcript."""
        from app.audio.transcription.service import TranscriptionService

        mock_response = MagicMock()
        mock_response.text = ""
        mock_response.language = "en"
        mock_response.segments = []

        with patch(
            "app.audio.transcription.providers.whisper.openai"
        ) as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                return_value=mock_response
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            svc = TranscriptionService(
                provider="whisper",
                api_key="test_key",
                max_retries=1,
                timeout_s=5.0,
            )
            request = TranscriptionRequest(audio_data=b"\x00" * 100, sample_rate=16000)
            result = await svc.transcribe(request)

            assert result.transcript == ""
            assert result.confidence_score == pytest.approx(0.85)

    @pytest.mark.asyncio
    async def test_local_whisper_end_to_end(self, audio_request):
        """Full round-trip with local Whisper model."""
        from app.audio.transcription.service import TranscriptionService

        mock_model = MagicMock()
        mock_model.model_name = "base.en"
        mock_model.transcribe.return_value = {
            "text": " Local integration test ",
            "language": "en",
            "segments": [
                {"text": " Local", "start": 0.0, "end": 0.3, "avg_logprob": -0.2},
            ],
        }

        with patch(
            "app.audio.transcription.providers.local_whisper.whisper"
        ) as mock_whisper:
            mock_whisper.load_model.return_value = mock_model

            svc = TranscriptionService(
                provider="local",
                max_retries=1,
                timeout_s=10.0,
            )
            result = await svc.transcribe(audio_request)

            assert "Local integration test" in result.transcript
            assert result.provider_metadata["local"] is True


class TestProviderFallbackIntegration:
    """Integration tests for the fallback chain."""

    @pytest.mark.asyncio
    async def test_fallback_whisper_to_local(self, audio_request):
        """When Whisper fails, fall back to local model."""
        from app.audio.transcription.service import TranscriptionService

        mock_model = MagicMock()
        mock_model.model_name = "base.en"
        mock_model.transcribe.return_value = {
            "text": " Fallback transcript ",
            "language": "en",
            "segments": [],
        }

        with patch(
            "app.audio.transcription.providers.whisper.openai"
        ) as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                side_effect=Exception("Whisper API down")
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            with patch(
                "app.audio.transcription.providers.local_whisper.whisper"
            ) as mock_whisper:
                mock_whisper.load_model.return_value = mock_model

                svc = TranscriptionService(
                    provider="whisper",
                    api_key="test_key",
                    providers=["whisper", "local"],
                    fallback_enabled=True,
                    max_retries=1,
                    retry_delay_s=0.01,
                    timeout_s=5.0,
                )
                result = await svc.transcribe_with_fallback(audio_request)

                assert "Fallback transcript" in result.transcript

    @pytest.mark.asyncio
    async def test_all_providers_exhausted(self, audio_request):
        """All providers fail → AllProvidersFailedError."""
        from app.audio.transcription.service import TranscriptionService
        from app.audio.transcription.exceptions import AllProvidersFailedError

        with patch(
            "app.audio.transcription.providers.whisper.openai"
        ) as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                side_effect=Exception("Whisper failed")
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            with patch(
                "app.audio.transcription.providers.local_whisper.whisper"
            ) as mock_whisper:
                mock_whisper.load_model.side_effect = RuntimeError("Model load failed")

                svc = TranscriptionService(
                    provider="whisper",
                    api_key="test_key",
                    providers=["whisper", "local"],
                    fallback_enabled=True,
                    max_retries=1,
                    retry_delay_s=0.01,
                    timeout_s=5.0,
                )

                with pytest.raises(AllProvidersFailedError):
                    await svc.transcribe_with_fallback(audio_request)
