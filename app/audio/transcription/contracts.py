"""
Audio Transcription Domain Contracts

Frozen dataclass models exchanged by the transcription module.
No business logic — structure and validation only.

Follows the same pattern as ``audio.ingestion.contracts``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Input Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TranscriptionRequest:
    """
    Request to transcribe an audio buffer.

    All audio MUST be 16 kHz mono (normalised by the ingestion module).
    """

    audio_data: bytes
    sample_rate: int = 16000
    language: Optional[str] = None
    context: Optional[str] = None
    streaming: bool = False

    def __post_init__(self) -> None:
        if not self.audio_data:
            raise ValueError("audio_data must not be empty")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")


@dataclass(frozen=True)
class TranscriptionConfig:
    """
    Configuration for a transcription provider.

    Provider-specific knobs (model, language forcing, profanity filter, etc.).
    """

    provider: Literal["whisper", "google", "azure", "assemblyai", "local"] = "whisper"
    api_key: Optional[str] = None
    model: Optional[str] = None
    language: Optional[str] = None
    detect_language: bool = True
    word_timestamps: bool = True
    profanity_filter: bool = False


# ---------------------------------------------------------------------------
# Output Contracts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TranscriptSegment:
    """
    Word- or phrase-level transcript segment with timing.

    ``start_ms`` / ``end_ms`` are relative to the beginning of the audio
    buffer that was transcribed.
    """

    text: str
    start_ms: int = 0
    end_ms: int = 0
    confidence: float = 0.0

    def __post_init__(self) -> None:
        if self.end_ms < self.start_ms:
            raise ValueError("end_ms must be >= start_ms")


@dataclass(frozen=True)
class TranscriptionResult:
    """
    Immutable transcription output.

    Once returned, the result MUST NOT be modified (frozen dataclass).
    """

    transcript: str
    confidence_score: float
    language_detected: Optional[str] = None
    segments: tuple[TranscriptSegment, ...] = ()
    partial: bool = False
    provider_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Ensure confidence is clamped to [0.0, 1.0]
        if not (0.0 <= self.confidence_score <= 1.0):
            object.__setattr__(
                self,
                "confidence_score",
                max(0.0, min(1.0, self.confidence_score)),
            )
