"""
Transcriber Protocol

Defines the interface that every STT provider must implement.
Provider implementations live under ``providers/``.

Uses ``typing.Protocol`` (structural subtyping) to avoid inheritance coupling.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable

from .contracts import TranscriptionRequest, TranscriptionResult


@runtime_checkable
class Transcriber(Protocol):
    """
    Abstract transcription provider.

    Every concrete provider MUST implement ``transcribe`` (batch mode).
    Streaming providers additionally implement ``transcribe_streaming``.
    """

    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        """
        Perform batch transcription on a complete audio buffer.

        Parameters
        ----------
        request : TranscriptionRequest
            Contains normalised 16 kHz mono audio and optional language hint.

        Returns
        -------
        TranscriptionResult
            Frozen result with transcript, confidence, segments.
        """
        ...

    @property
    def supports_streaming(self) -> bool:
        """Return True if the provider supports real-time partial transcripts."""
        ...

    async def transcribe_streaming(
        self,
        request: TranscriptionRequest,
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Yield partial ``TranscriptionResult`` objects as audio is processed.

        Only callable when ``supports_streaming`` is ``True``.

        Raises
        ------
        UnsupportedFeatureError
            If the provider does not support streaming.
        """
        ...
