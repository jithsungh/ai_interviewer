"""
Unit tests for TranscriptionService.

Validates retry logic, timeout handling, fallback behaviour, and
streaming delegation.  All provider calls are mocked.
"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.audio.transcription.contracts import (
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptSegment,
)
from app.audio.transcription.exceptions import (
    AllProvidersFailedError,
    TranscriptionError,
    TranscriptionTimeoutError,
)
from app.audio.transcription.service import TranscriptionService


@pytest.fixture
def transcription_request():
    return TranscriptionRequest(audio_data=b"\x00" * 1000, sample_rate=16000)


@pytest.fixture
def success_result():
    return TranscriptionResult(
        transcript="The answer is dynamic programming.",
        confidence_score=0.92,
        language_detected="en",
        segments=(
            TranscriptSegment(text="The", start_ms=0, end_ms=200, confidence=0.95),
            TranscriptSegment(
                text="answer", start_ms=200, end_ms=500, confidence=0.92
            ),
        ),
        provider_metadata={"provider": "whisper"},
    )


class TestTranscriptionServiceBatch:
    """Tests for batch transcription with retry."""

    @pytest.mark.asyncio
    async def test_successful_transcription(self, transcription_request, success_result):
        mock_transcriber = AsyncMock()
        mock_transcriber.transcribe = AsyncMock(return_value=success_result)

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as MockSelector:
            MockSelector.return_value.get_provider.return_value = mock_transcriber

            svc = TranscriptionService(
                provider="whisper",
                api_key="key",
                max_retries=3,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )
            result = await svc.transcribe(transcription_request)

            assert result.transcript == "The answer is dynamic programming."
            assert result.confidence_score == 0.92
            mock_transcriber.transcribe.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_succeed(self, transcription_request, success_result):
        mock_transcriber = AsyncMock()
        mock_transcriber.transcribe = AsyncMock(
            side_effect=[
                Exception("API Error"),
                Exception("API Error"),
                success_result,
            ]
        )

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as MockSelector:
            MockSelector.return_value.get_provider.return_value = mock_transcriber

            svc = TranscriptionService(
                provider="whisper",
                api_key="key",
                max_retries=3,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )
            result = await svc.transcribe(transcription_request)

            assert result.transcript == "The answer is dynamic programming."
            assert mock_transcriber.transcribe.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_error(self, transcription_request):
        mock_transcriber = AsyncMock()
        mock_transcriber.transcribe = AsyncMock(
            side_effect=Exception("Persistent failure")
        )

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as MockSelector:
            MockSelector.return_value.get_provider.return_value = mock_transcriber

            svc = TranscriptionService(
                provider="whisper",
                api_key="key",
                max_retries=2,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )

            with pytest.raises(TranscriptionError) as exc_info:
                await svc.transcribe(transcription_request)
            assert "failed after 2 attempts" in exc_info.value.message
            assert mock_transcriber.transcribe.call_count == 2

    @pytest.mark.asyncio
    async def test_timeout_raises_error(self, transcription_request):
        async def slow_transcribe(*args, **kwargs):
            await asyncio.sleep(5)
            return TranscriptionResult(transcript="too slow", confidence_score=0.5)

        mock_transcriber = AsyncMock()
        mock_transcriber.transcribe = slow_transcribe

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as MockSelector:
            MockSelector.return_value.get_provider.return_value = mock_transcriber

            svc = TranscriptionService(
                provider="whisper",
                api_key="key",
                max_retries=1,
                retry_delay_s=0.01,
                timeout_s=0.05,
            )

            with pytest.raises((TranscriptionTimeoutError, TranscriptionError)):
                await svc.transcribe(transcription_request)


class TestTranscriptionServiceFallback:
    """Tests for provider fallback chain."""

    @pytest.mark.asyncio
    async def test_fallback_to_secondary(self, transcription_request, success_result):
        whisper_transcriber = AsyncMock()
        whisper_transcriber.transcribe = AsyncMock(
            side_effect=Exception("Whisper down")
        )

        google_transcriber = AsyncMock()
        google_result = TranscriptionResult(
            transcript="Fallback result",
            confidence_score=0.88,
            provider_metadata={"provider": "google"},
        )
        google_transcriber.transcribe = AsyncMock(return_value=google_result)

        def get_provider_side_effect(name, **kwargs):
            if name == "whisper":
                return whisper_transcriber
            return google_transcriber

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as MockSelector:
            MockSelector.return_value.get_provider.side_effect = (
                get_provider_side_effect
            )

            svc = TranscriptionService(
                provider="whisper",
                api_key="key",
                providers=["whisper", "google"],
                fallback_api_keys={"google": "google_key"},
                fallback_enabled=True,
                max_retries=1,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )
            result = await svc.transcribe_with_fallback(transcription_request)

            assert result.transcript == "Fallback result"

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises(self, transcription_request):
        mock_transcriber = AsyncMock()
        mock_transcriber.transcribe = AsyncMock(side_effect=Exception("Failure"))

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as MockSelector:
            MockSelector.return_value.get_provider.return_value = mock_transcriber

            svc = TranscriptionService(
                provider="whisper",
                providers=["whisper", "google"],
                fallback_api_keys={"whisper": "k1", "google": "k2"},
                fallback_enabled=True,
                max_retries=1,
                retry_delay_s=0.01,
                timeout_s=5.0,
            )

            with pytest.raises(AllProvidersFailedError):
                await svc.transcribe_with_fallback(transcription_request)


class TestTranscriptionServiceStreaming:
    """Tests for streaming delegation."""

    @pytest.mark.asyncio
    async def test_streaming_delegates_to_provider(self, transcription_request):
        partial = TranscriptionResult(
            transcript="partial", confidence_score=0.7, partial=True
        )
        final = TranscriptionResult(
            transcript="final result", confidence_score=0.92, partial=False
        )

        async def mock_streaming(req):
            yield partial
            yield final

        mock_transcriber = MagicMock()
        mock_transcriber.transcribe_streaming = mock_streaming

        with patch(
            "app.audio.transcription.service.TranscriptionProviderSelector"
        ) as MockSelector:
            MockSelector.return_value.get_provider.return_value = mock_transcriber

            svc = TranscriptionService(provider="google", api_key="key")
            results = []
            async for r in svc.transcribe_streaming(transcription_request):
                results.append(r)

            assert len(results) == 2
            assert results[0].partial is True
            assert results[1].partial is False
            assert results[1].transcript == "final result"
