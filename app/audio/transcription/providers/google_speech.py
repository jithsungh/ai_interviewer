"""
Google Cloud Speech Transcription Provider (Streaming + Batch)

Uses the Google Cloud Speech-to-Text API for both streaming and batch
transcription.  Streaming yields partial results (``partial=True``)
followed by a final result.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List

from app.shared.observability import get_context_logger

from ..contracts import TranscriptionRequest, TranscriptionResult, TranscriptSegment
from ..confidence import calculate_aggregate_confidence
from ..exceptions import TranscriptionError

try:
    from google.cloud import speech  # type: ignore[import-untyped]
except ImportError:
    speech = None  # type: ignore[assignment]

logger = get_context_logger(__name__)


class GoogleSpeechTranscriber:
    """
    Google Cloud Speech-to-Text transcription provider.

    Supports both **batch** (single request/response) and **streaming**
    (interim + final results).
    """

    supports_streaming: bool = True

    def __init__(
        self,
        api_key: str | None = None,
        language_code: str = "en-US",
    ) -> None:
        self._api_key = api_key
        self._language_code = language_code

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Synchronous (batch) transcription via Google Cloud Speech."""
        if speech is None:
            raise TranscriptionError(
                message="google-cloud-speech package is not installed",
                error_code="TRANSCRIPTION_DEPENDENCY_MISSING",
            )
        try:
            client = speech.SpeechAsyncClient()

            language = request.language or self._language_code
            if language and len(language) == 2:
                # Map ISO 639-1 to BCP-47 (e.g. "en" → "en-US")
                language = f"{language}-US" if language == "en" else language

            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=request.sample_rate,
                language_code=language,
                enable_word_time_offsets=True,
                enable_automatic_punctuation=True,
            )

            audio = speech.RecognitionAudio(content=request.audio_data)
            response = await client.recognize(config=config, audio=audio)

            segments: List[TranscriptSegment] = []
            transcript_parts: List[str] = []

            for result in response.results:
                alt = result.alternatives[0] if result.alternatives else None
                if alt is None:
                    continue
                transcript_parts.append(alt.transcript)
                segments.extend(self._parse_words(alt.words))

            transcript = " ".join(transcript_parts)
            confidence = (
                calculate_aggregate_confidence(segments) if segments else 0.0
            )

            return TranscriptionResult(
                transcript=transcript,
                confidence_score=confidence,
                language_detected=language,
                segments=tuple(segments),
                partial=False,
                provider_metadata={"provider": "google"},
            )

        except Exception as exc:
            if isinstance(exc, TranscriptionError):
                raise
            raise TranscriptionError(
                message=f"Google Speech transcription failed: {exc}",
                metadata={"provider": "google", "error_detail": str(exc)},
            )

    async def transcribe_streaming(
        self,
        request: TranscriptionRequest,
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Stream partial transcription results from Google Cloud Speech.

        Yields ``TranscriptionResult`` objects with ``partial=True`` for
        interim results, followed by a final result with ``partial=False``.
        """
        if speech is None:
            raise TranscriptionError(
                message="google-cloud-speech package is not installed",
                error_code="TRANSCRIPTION_DEPENDENCY_MISSING",
            )
        try:
            client = speech.SpeechAsyncClient()

            language = request.language or self._language_code
            if language and len(language) == 2:
                language = f"{language}-US" if language == "en" else language

            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=request.sample_rate,
                language_code=language,
                enable_word_time_offsets=True,
                enable_automatic_punctuation=True,
            )

            streaming_config = speech.StreamingRecognitionConfig(
                config=config,
                interim_results=True,
            )

            # Build streaming request from the audio data
            audio_request = speech.StreamingRecognizeRequest(
                streaming_config=streaming_config,
            )
            content_request = speech.StreamingRecognizeRequest(
                audio_content=request.audio_data,
            )

            async for response in client.streaming_recognize(
                requests=iter([audio_request, content_request]),
            ):
                for result in response.results:
                    alt = result.alternatives[0] if result.alternatives else None
                    if alt is None:
                        continue

                    segments = self._parse_words(getattr(alt, "words", []))
                    confidence = (
                        calculate_aggregate_confidence(segments)
                        if segments
                        else getattr(alt, "confidence", 0.0)
                    )

                    yield TranscriptionResult(
                        transcript=alt.transcript,
                        confidence_score=confidence,
                        language_detected=language,
                        segments=tuple(segments),
                        partial=not result.is_final,
                        provider_metadata={"provider": "google"},
                    )

        except Exception as exc:
            if isinstance(exc, TranscriptionError):
                raise
            raise TranscriptionError(
                message=f"Google Speech streaming failed: {exc}",
                metadata={"provider": "google", "error_detail": str(exc)},
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_words(words: Any) -> List[TranscriptSegment]:
        """Convert Google word-info objects to ``TranscriptSegment``."""
        parsed: List[TranscriptSegment] = []
        for word_info in words or []:
            text = getattr(word_info, "word", "")
            start = getattr(word_info, "start_time", None)
            end = getattr(word_info, "end_time", None)
            conf = getattr(word_info, "confidence", 0.0)

            start_ms = int(start.total_seconds() * 1000) if start else 0
            end_ms = int(end.total_seconds() * 1000) if end else 0

            parsed.append(
                TranscriptSegment(
                    text=str(text),
                    start_ms=start_ms,
                    end_ms=end_ms,
                    confidence=max(0.0, min(1.0, float(conf))),
                )
            )
        return parsed
