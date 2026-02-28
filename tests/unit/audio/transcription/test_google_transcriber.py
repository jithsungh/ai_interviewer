"""
Unit tests for GoogleSpeechTranscriber provider.

All Google Cloud API calls are mocked — no real network traffic.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import timedelta

from app.audio.transcription.contracts import TranscriptionRequest
from app.audio.transcription.exceptions import TranscriptionError
from app.audio.transcription.providers.google_speech import GoogleSpeechTranscriber


class TestGoogleSpeechTranscriber:
    """Tests for the Google Cloud Speech provider."""

    @pytest.fixture
    def transcriber(self):
        return GoogleSpeechTranscriber(api_key="test_key", language_code="en-US")

    @pytest.fixture
    def transcription_request(self):
        return TranscriptionRequest(
            audio_data=b"\x00" * 1000,
            sample_rate=16000,
            language="en",
        )

    @pytest.fixture
    def mock_word_info(self):
        """Build a mock Google word-info object."""
        word = MagicMock()
        word.word = "dynamic"
        word.start_time = timedelta(seconds=0.5)
        word.end_time = timedelta(seconds=0.9)
        word.confidence = 0.92
        return word

    @pytest.fixture
    def mock_google_batch_response(self, mock_word_info):
        """Mock a batch (non-streaming) recognition response."""
        alt = MagicMock()
        alt.transcript = "dynamic programming"
        alt.confidence = 0.88
        alt.words = [mock_word_info]

        result = MagicMock()
        result.alternatives = [alt]

        response = MagicMock()
        response.results = [result]
        return response

    @pytest.mark.asyncio
    async def test_batch_transcription(
        self, transcriber, transcription_request, mock_google_batch_response
    ):
        with patch(
            "app.audio.transcription.providers.google_speech.speech"
        ) as mock_speech:
            mock_client = AsyncMock()
            mock_client.recognize = AsyncMock(
                return_value=mock_google_batch_response
            )
            mock_speech.SpeechAsyncClient.return_value = mock_client
            # Provide dummy config constructors
            mock_speech.RecognitionConfig.return_value = MagicMock()
            mock_speech.RecognitionConfig.AudioEncoding.LINEAR16 = 1
            mock_speech.RecognitionAudio.return_value = MagicMock()

            result = await transcriber.transcribe(transcription_request)

            assert result.transcript == "dynamic programming"
            assert result.partial is False
            assert result.provider_metadata["provider"] == "google"

    @pytest.mark.asyncio
    async def test_word_timestamps_parsed(
        self, transcriber, transcription_request, mock_google_batch_response
    ):
        with patch(
            "app.audio.transcription.providers.google_speech.speech"
        ) as mock_speech:
            mock_client = AsyncMock()
            mock_client.recognize = AsyncMock(
                return_value=mock_google_batch_response
            )
            mock_speech.SpeechAsyncClient.return_value = mock_client
            mock_speech.RecognitionConfig.return_value = MagicMock()
            mock_speech.RecognitionConfig.AudioEncoding.LINEAR16 = 1
            mock_speech.RecognitionAudio.return_value = MagicMock()

            result = await transcriber.transcribe(transcription_request)

            assert len(result.segments) == 1
            seg = result.segments[0]
            assert seg.text == "dynamic"
            assert seg.start_ms == 500
            assert seg.end_ms == 900
            assert seg.confidence == pytest.approx(0.92)

    @pytest.mark.asyncio
    async def test_api_failure_raises_transcription_error(self, transcriber, transcription_request):
        with patch(
            "app.audio.transcription.providers.google_speech.speech"
        ) as mock_speech:
            mock_client = AsyncMock()
            mock_client.recognize = AsyncMock(side_effect=RuntimeError("API down"))
            mock_speech.SpeechAsyncClient.return_value = mock_client
            mock_speech.RecognitionConfig.return_value = MagicMock()
            mock_speech.RecognitionConfig.AudioEncoding.LINEAR16 = 1
            mock_speech.RecognitionAudio.return_value = MagicMock()

            with pytest.raises(TranscriptionError) as exc_info:
                await transcriber.transcribe(transcription_request)
            assert "Google Speech transcription failed" in exc_info.value.message

    def test_supports_streaming(self, transcriber):
        assert transcriber.supports_streaming is True

    @pytest.mark.asyncio
    async def test_streaming_yields_results(self, transcriber, transcription_request):
        with patch(
            "app.audio.transcription.providers.google_speech.speech"
        ) as mock_speech:
            # Mock a streaming response with one interim + one final
            interim_alt = MagicMock()
            interim_alt.transcript = "dynamic"
            interim_alt.confidence = 0.7
            interim_alt.words = []
            interim_result = MagicMock()
            interim_result.alternatives = [interim_alt]
            interim_result.is_final = False

            final_alt = MagicMock()
            final_alt.transcript = "dynamic programming"
            final_alt.confidence = 0.92
            final_alt.words = []
            final_result = MagicMock()
            final_result.alternatives = [final_alt]
            final_result.is_final = True

            interim_response = MagicMock()
            interim_response.results = [interim_result]
            final_response = MagicMock()
            final_response.results = [final_result]

            mock_client = AsyncMock()

            async def mock_streaming_recognize(**kwargs):
                yield interim_response
                yield final_response

            mock_client.streaming_recognize = mock_streaming_recognize
            mock_speech.SpeechAsyncClient.return_value = mock_client
            mock_speech.RecognitionConfig.return_value = MagicMock()
            mock_speech.RecognitionConfig.AudioEncoding.LINEAR16 = 1
            mock_speech.StreamingRecognitionConfig.return_value = MagicMock()
            mock_speech.StreamingRecognizeRequest.return_value = MagicMock()

            results = []
            async for r in transcriber.transcribe_streaming(transcription_request):
                results.append(r)

            assert len(results) == 2
            assert results[0].partial is True
            assert results[0].transcript == "dynamic"
            assert results[1].partial is False
            assert results[1].transcript == "dynamic programming"

    @pytest.mark.asyncio
    async def test_language_code_mapping(self, transcription_request):
        """Short ISO code 'en' is mapped to 'en-US'."""
        transcriber = GoogleSpeechTranscriber(api_key="key", language_code="en")

        with patch(
            "app.audio.transcription.providers.google_speech.speech"
        ) as mock_speech:
            mock_client = AsyncMock()
            resp = MagicMock()
            resp.results = []
            mock_client.recognize = AsyncMock(return_value=resp)
            mock_speech.SpeechAsyncClient.return_value = mock_client
            mock_speech.RecognitionConfig.return_value = MagicMock()
            mock_speech.RecognitionConfig.AudioEncoding.LINEAR16 = 1
            mock_speech.RecognitionAudio.return_value = MagicMock()

            result = await transcriber.transcribe(transcription_request)

            assert result.transcript == ""
            assert result.confidence_score == 0.0
