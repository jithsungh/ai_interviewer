"""
Local Whisper Transcription Provider (Batch Only — CPU-bound)

Uses the ``openai-whisper`` package to run Whisper models locally.
Transcription runs in a thread-pool executor to avoid blocking the
event loop (Whisper inference is CPU-intensive).

Key advantage: data never leaves the host → GDPR / data-sovereignty.
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, List, Optional

from app.shared.observability import get_context_logger

from ..contracts import TranscriptionRequest, TranscriptionResult, TranscriptSegment
from ..confidence import calculate_aggregate_confidence
from ..exceptions import TranscriptionError, UnsupportedFeatureError

try:
    import whisper  # type: ignore[import-untyped]
except ImportError:
    whisper = None  # type: ignore[assignment]

logger = get_context_logger(__name__)


class LocalWhisperTranscriber:
    """
    Local Whisper model transcription provider.

    Loads the model once at construction time and reuses it for all
    calls.  Supports batch mode only.
    """

    supports_streaming: bool = False

    def __init__(self, model: str = "base.en") -> None:
        self._model_name = model
        self._model: Any = None  # Lazy-loaded

    def _load_model(self) -> Any:
        """Load the local Whisper model (heavy — called once)."""
        if self._model is not None:
            return self._model
        if whisper is None:
            raise TranscriptionError(
                message="openai-whisper package is not installed",
                error_code="TRANSCRIPTION_DEPENDENCY_MISSING",
            )
        try:
            self._model = whisper.load_model(self._model_name)
            logger.info(
                "Local Whisper model loaded",
                event_type="transcription.local_whisper.model_loaded",
                metadata={"model": self._model_name},
            )
            return self._model
        except Exception as exc:
            raise TranscriptionError(
                message=f"Failed to load local Whisper model '{self._model_name}': {exc}",
                metadata={"model": self._model_name, "error_detail": str(exc)},
            )

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """Run local Whisper transcription in a thread-pool executor."""
        model = self._load_model()

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            model,
            request,
        )
        return result

    async def transcribe_streaming(
        self,
        request: TranscriptionRequest,
    ) -> AsyncIterator[TranscriptionResult]:
        """Local Whisper does not support streaming."""
        raise UnsupportedFeatureError(provider="local", feature="streaming")
        yield  # pragma: no cover

    # ------------------------------------------------------------------
    # Sync transcription (executed in thread pool)
    # ------------------------------------------------------------------

    @staticmethod
    def _transcribe_sync(
        model: Any,
        request: TranscriptionRequest,
    ) -> TranscriptionResult:
        """CPU-bound Whisper inference — MUST run off the event loop."""
        import numpy as np

        audio_np = (
            np.frombuffer(request.audio_data, dtype=np.int16).astype(np.float32)
            / 32768.0
        )

        kwargs: Dict[str, Any] = {"word_timestamps": True}
        if request.language:
            kwargs["language"] = request.language

        raw = model.transcribe(audio_np, **kwargs)

        segments = LocalWhisperTranscriber._parse_segments(raw.get("segments", []))
        confidence = (
            calculate_aggregate_confidence(segments) if segments else 0.0
        )

        return TranscriptionResult(
            transcript=raw.get("text", "").strip(),
            confidence_score=confidence,
            language_detected=raw.get("language"),
            segments=tuple(segments),
            partial=False,
            provider_metadata={
                "provider": "local",
                "model": model.model_name if hasattr(model, "model_name") else "unknown",
                "local": True,
            },
        )

    @staticmethod
    def _parse_segments(raw_segments: list) -> List[TranscriptSegment]:
        """Convert local Whisper segment dicts to ``TranscriptSegment``."""
        import math

        parsed: List[TranscriptSegment] = []
        for seg in raw_segments:
            text = seg.get("text", "").strip()
            start = seg.get("start", 0.0)
            end = seg.get("end", 0.0)
            # avg_logprob → probability
            avg_logprob = seg.get("avg_logprob", -1.0)
            conf = math.exp(avg_logprob) if avg_logprob < 0 else avg_logprob

            parsed.append(
                TranscriptSegment(
                    text=text,
                    start_ms=int(float(start) * 1000),
                    end_ms=int(float(end) * 1000),
                    confidence=max(0.0, min(1.0, float(conf))),
                )
            )
        return parsed
