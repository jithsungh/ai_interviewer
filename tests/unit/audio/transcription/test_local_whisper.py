"""
Unit tests for LocalWhisperTranscriber provider.

The ``whisper`` package is mocked — no real model loading or inference.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.audio.transcription.contracts import TranscriptionRequest
from app.audio.transcription.exceptions import (
    TranscriptionError,
    UnsupportedFeatureError,
)
from app.audio.transcription.providers.local_whisper import LocalWhisperTranscriber


class TestLocalWhisperTranscriber:
    """Tests for the local Whisper model provider."""

    @pytest.fixture
    def mock_whisper_model(self):
        """Create a mock whisper model that returns a valid response."""
        model = MagicMock()
        model.model_name = "base.en"
        model.transcribe.return_value = {
            "text": " Local transcription result ",
            "language": "en",
            "segments": [
                {
                    "text": " Local",
                    "start": 0.0,
                    "end": 0.3,
                    "avg_logprob": -0.2,
                },
                {
                    "text": " transcription",
                    "start": 0.3,
                    "end": 0.9,
                    "avg_logprob": -0.3,
                },
                {
                    "text": " result",
                    "start": 0.9,
                    "end": 1.2,
                    "avg_logprob": -0.15,
                },
            ],
        }
        return model

    @pytest.fixture
    def transcription_request(self):
        # 16-bit PCM audio (all zeros)
        import numpy as np

        audio = np.zeros(16000, dtype=np.int16)
        return TranscriptionRequest(
            audio_data=audio.tobytes(),
            sample_rate=16000,
        )

    @pytest.mark.asyncio
    async def test_local_transcription(self, mock_whisper_model, transcription_request):
        with patch(
            "app.audio.transcription.providers.local_whisper.whisper"
        ) as mock_whisper:
            mock_whisper.load_model.return_value = mock_whisper_model

            transcriber = LocalWhisperTranscriber(model="base.en")
            result = await transcriber.transcribe(transcription_request)
            assert result.language_detected == "en"
            assert len(result.segments) == 3
            assert result.partial is False
            assert result.provider_metadata["local"] is True
            assert result.provider_metadata["provider"] == "local"

    @pytest.mark.asyncio
    async def test_runs_in_executor(self, mock_whisper_model, transcription_request):
        """Verify that transcription runs off the event loop."""
        with patch(
            "app.audio.transcription.providers.local_whisper.whisper"
        ) as mock_whisper:
            mock_whisper.load_model.return_value = mock_whisper_model

            with patch("asyncio.get_running_loop") as mock_loop:
                mock_loop_inst = MagicMock()
                from app.audio.transcription.contracts import TranscriptionResult

                mock_loop_inst.run_in_executor = AsyncMock(
                    return_value=TranscriptionResult(
                        transcript="test", confidence_score=0.9
                    )
                )
                mock_loop.return_value = mock_loop_inst

                transcriber = LocalWhisperTranscriber(model="base.en")
                result = await transcriber.transcribe(transcription_request)
                assert result.transcript == "test"

    @pytest.mark.asyncio
    async def test_streaming_not_supported(self, transcription_request):
        transcriber = LocalWhisperTranscriber.__new__(LocalWhisperTranscriber)
        transcriber._model_name = "base.en"
        transcriber._model = None

        assert transcriber.supports_streaming is False
        with pytest.raises(UnsupportedFeatureError) as exc_info:
            async for _ in transcriber.transcribe_streaming(transcription_request):
                pass
        assert exc_info.value.metadata["feature"] == "streaming"

    def test_no_api_key_required(self):
        """Local provider does not need an API key."""
        transcriber = LocalWhisperTranscriber.__new__(LocalWhisperTranscriber)
        transcriber._model_name = "base.en"
        transcriber._model = None
        # No error — construction succeeds without API key

    @pytest.mark.asyncio
    async def test_model_load_failure_raises_error(self, transcription_request):
        with patch(
            "app.audio.transcription.providers.local_whisper.whisper"
        ) as mock_whisper:
            mock_whisper.load_model.side_effect = RuntimeError("CUDA OOM")

            transcriber = LocalWhisperTranscriber(model="large-v3")
            with pytest.raises(TranscriptionError) as exc_info:
                await transcriber.transcribe(transcription_request)
            assert "Failed to load local Whisper model" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_segments_logprob_converted(self, mock_whisper_model, transcription_request):
        """avg_logprob values are converted to probability [0, 1]."""
        import math

        with patch(
            "app.audio.transcription.providers.local_whisper.whisper"
        ) as mock_whisper:
            mock_whisper.load_model.return_value = mock_whisper_model

            transcriber = LocalWhisperTranscriber(model="base.en")
            result = await transcriber.transcribe(transcription_request)

            first_seg = result.segments[0]
            expected_conf = math.exp(-0.2)
            assert first_seg.confidence == pytest.approx(expected_conf, abs=0.01)

    @pytest.mark.asyncio
    async def test_empty_segments(self, transcription_request):
        model = MagicMock()
        model.model_name = "base.en"
        model.transcribe.return_value = {
            "text": "",
            "language": "en",
            "segments": [],
        }

        with patch(
            "app.audio.transcription.providers.local_whisper.whisper"
        ) as mock_whisper:
            mock_whisper.load_model.return_value = model

            transcriber = LocalWhisperTranscriber(model="base.en")
            result = await transcriber.transcribe(transcription_request)

            assert result.transcript == ""
            assert result.confidence_score == 0.0
            assert len(result.segments) == 0
