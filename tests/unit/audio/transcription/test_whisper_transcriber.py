"""
Unit tests for WhisperTranscriber provider.

All OpenAI API calls are mocked — no real network traffic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.audio.transcription.contracts import TranscriptionRequest
from app.audio.transcription.exceptions import (
    TranscriptionError,
    UnsupportedFeatureError,
)
from app.audio.transcription.providers.whisper import WhisperTranscriber


class TestWhisperTranscriber:
    """Tests for the OpenAI Whisper batch provider."""

    @pytest.fixture
    def transcriber(self):
        return WhisperTranscriber(api_key="test_key", model="whisper-1")

    @pytest.fixture
    def transcription_request(self):
        return TranscriptionRequest(
            audio_data=b"\x00" * 1000,
            sample_rate=16000,
            language="en",
        )

    @pytest.fixture
    def mock_whisper_response(self):
        """Simulate the openai.audio.transcriptions.create response."""
        resp = MagicMock()
        resp.text = "The answer is dynamic programming."
        resp.language = "en"
        resp.segments = [
            {"text": "The", "start": 0.0, "end": 0.2, "confidence": 0.95},
            {"text": "answer", "start": 0.2, "end": 0.5, "confidence": 0.92},
            {"text": "is", "start": 0.5, "end": 0.7, "confidence": 0.98},
            {"text": "dynamic", "start": 0.7, "end": 1.1, "confidence": 0.89},
            {"text": "programming", "start": 1.1, "end": 1.7, "confidence": 0.91},
        ]
        return resp

    @pytest.mark.asyncio
    async def test_batch_transcription(
        self, transcriber, transcription_request, mock_whisper_response
    ):
        with patch("app.audio.transcription.providers.whisper.openai") as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                return_value=mock_whisper_response
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            result = await transcriber.transcribe(transcription_request)

            assert result.transcript == "The answer is dynamic programming."
            assert result.language_detected == "en"
            assert len(result.segments) == 5
            assert result.confidence_score > 0.85
            assert result.partial is False
            assert result.provider_metadata["provider"] == "whisper"

    @pytest.mark.asyncio
    async def test_confidence_aggregated_from_segments(
        self, transcriber, transcription_request, mock_whisper_response
    ):
        with patch("app.audio.transcription.providers.whisper.openai") as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                return_value=mock_whisper_response
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            result = await transcriber.transcribe(transcription_request)

            expected = (0.95 + 0.92 + 0.98 + 0.89 + 0.91) / 5
            assert result.confidence_score == pytest.approx(expected, abs=0.01)

    @pytest.mark.asyncio
    async def test_api_failure_raises_transcription_error(self, transcriber, transcription_request):
        with patch("app.audio.transcription.providers.whisper.openai") as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(
                side_effect=Exception("API Error")
            )
            mock_openai.AsyncOpenAI.return_value = mock_client

            with pytest.raises(TranscriptionError) as exc_info:
                await transcriber.transcribe(transcription_request)
            assert "Whisper transcription failed" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_streaming_not_supported(self, transcriber, transcription_request):
        assert transcriber.supports_streaming is False
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            async for _ in transcriber.transcribe_streaming(transcription_request):
                pass
        assert exc_info.value.metadata["feature"] == "streaming"

    def test_api_key_required(self):
        with pytest.raises(ValueError, match="api_key is required"):
            WhisperTranscriber(api_key="")

    @pytest.mark.asyncio
    async def test_no_segments_uses_default_confidence(self, transcriber, transcription_request):
        resp = MagicMock()
        resp.text = "Hello world"
        resp.language = "en"
        resp.segments = []

        with patch("app.audio.transcription.providers.whisper.openai") as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value=resp)
            mock_openai.AsyncOpenAI.return_value = mock_client

            result = await transcriber.transcribe(transcription_request)
            assert result.confidence_score == pytest.approx(0.85)
            assert len(result.segments) == 0

    @pytest.mark.asyncio
    async def test_logprob_segments_normalised(self, transcriber, transcription_request):
        """Segments with avg_logprob (negative) are converted to probability."""
        import math

        resp = MagicMock()
        resp.text = "test"
        resp.language = "en"
        resp.segments = [
            {"text": "test", "start": 0.0, "end": 0.5, "avg_logprob": -0.5}
        ]

        with patch("app.audio.transcription.providers.whisper.openai") as mock_openai:
            mock_client = AsyncMock()
            mock_client.audio.transcriptions.create = AsyncMock(return_value=resp)
            mock_openai.AsyncOpenAI.return_value = mock_client

            result = await transcriber.transcribe(transcription_request)
            expected_conf = math.exp(-0.5)
            assert result.segments[0].confidence == pytest.approx(
                expected_conf, abs=0.01
            )
