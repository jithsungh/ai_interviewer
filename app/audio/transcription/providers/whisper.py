"""
OpenAI Whisper Transcription Provider (Batch Only)

Uses the OpenAI Whisper API (``openai.audio.transcriptions``) for
high-accuracy batch transcription.

Streaming is NOT supported — Whisper is a batch-only model.
"""

from __future__ import annotations

import io
import asyncio
from typing import Any, AsyncIterator, Dict, List

from app.shared.observability import get_context_logger

from ..contracts import TranscriptionRequest, TranscriptionResult, TranscriptSegment
from ..confidence import calculate_aggregate_confidence
from ..exceptions import TranscriptionError, UnsupportedFeatureError

try:
    import openai
except ImportError:
    openai = None  # type: ignore[assignment]

logger = get_context_logger(__name__)


class WhisperTranscriber:
    """
    OpenAI Whisper API transcription provider.

    Supports batch transcription only.  Returns word-level timestamps
    when ``response_format="verbose_json"`` is used.
    """

    supports_streaming: bool = False

    def __init__(
        self,
        api_key: str,
        model: str = "whisper-1",
        language: str | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required for WhisperTranscriber")
        self._api_key = api_key
        self._model = model
        self._language = language

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Transcribe audio using the OpenAI Whisper API."""
        if openai is None:
            raise TranscriptionError(
                message="openai package is not installed",
                error_code="TRANSCRIPTION_DEPENDENCY_MISSING",
            )
        try:
            client = openai.AsyncOpenAI(api_key=self._api_key)

            audio_file = io.BytesIO(request.audio_data)
            audio_file.name = "audio.wav"

            kwargs: Dict[str, Any] = {
                "model": self._model,
                "file": audio_file,
                "response_format": "verbose_json",
            }
            language = request.language or self._language
            if language:
                kwargs["language"] = language

            response = await client.audio.transcriptions.create(**kwargs)

            # Parse segments from response
            segments = self._parse_segments(
                getattr(response, "segments", None) or []
            )

            confidence = calculate_aggregate_confidence(segments) if segments else 0.85

            return TranscriptionResult(
                transcript=response.text or "",
                confidence_score=confidence,
                language_detected=getattr(response, "language", None),
                segments=tuple(segments),
                partial=False,
                provider_metadata={
                    "provider": "whisper",
                    "model": self._model,
                },
            )

        except Exception as exc:
            if isinstance(exc, (TranscriptionError, UnsupportedFeatureError)):
                raise
            raise TranscriptionError(
                message=f"Whisper transcription failed: {exc}",
                metadata={"provider": "whisper", "error_detail": str(exc)},
            )

    async def transcribe_streaming(
        self,
        request: TranscriptionRequest,
    ) -> AsyncIterator[TranscriptionResult]:
        """Whisper does not support streaming."""
        raise UnsupportedFeatureError(provider="whisper", feature="streaming")
        # Make this a valid async generator for type checkers
        yield  # pragma: no cover

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_segments(raw_segments: list) -> List[TranscriptSegment]:
        """Convert Whisper API segment dicts to ``TranscriptSegment``."""
        parsed: List[TranscriptSegment] = []
        for seg in raw_segments:
            if isinstance(seg, dict):
                text = seg.get("text", "")
                start = seg.get("start", 0.0)
                end = seg.get("end", 0.0)
                conf = seg.get("confidence", seg.get("avg_logprob", 0.0))
            else:
                # Pydantic-like response objects
                text = getattr(seg, "text", "")
                start = getattr(seg, "start", 0.0)
                end = getattr(seg, "end", 0.0)
                conf = getattr(
                    seg, "confidence", getattr(seg, "avg_logprob", 0.0)
                )

            # Normalise log-prob to 0–1 if needed
            if conf < 0:
                import math
                conf = math.exp(conf)

            parsed.append(
                TranscriptSegment(
                    text=str(text).strip(),
                    start_ms=int(float(start) * 1000),
                    end_ms=int(float(end) * 1000),
                    confidence=max(0.0, min(1.0, float(conf))),
                )
            )
        return parsed
