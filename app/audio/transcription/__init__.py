"""
Audio Transcription Module

Provider-agnostic speech-to-text conversion for voice-based interviews.

**Stateless** — converts audio buffers to text transcripts with confidence
scores and word-level timestamps.  All transcript persistence is handled
by ``audio.persistence``.

Public API:
    - TranscriptionService: Main facade for batch / streaming transcription
    - TranscriptionRequest / TranscriptionResult: Domain contracts
    - TranscriptSegment: Word-level segment
    - TranscriptionConfig: Provider configuration
"""

from .contracts import (
    TranscriptionConfig,
    TranscriptionRequest,
    TranscriptionResult,
    TranscriptSegment,
)
from .service import TranscriptionService

__all__ = [
    "TranscriptionService",
    "TranscriptionRequest",
    "TranscriptionResult",
    "TranscriptSegment",
    "TranscriptionConfig",
]
