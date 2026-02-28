"""
Audio Ingestion Contracts

Pydantic and dataclass models for audio ingestion input/output.
Defines all data structures exchanged by the ingestion module.

No business logic — validation of format and types only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal, Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SessionAction(str, Enum):
    """Audio session control actions."""
    START = "start"
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"


class SilenceReason(str, Enum):
    """Reason for silence detection event."""
    THRESHOLD_REACHED = "threshold_reached"
    SESSION_ENDED = "session_ended"


# ---------------------------------------------------------------------------
# Input Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AudioStreamRequest:
    """
    Single audio chunk from the client.

    Frozen (immutable) after creation.
    """
    interview_exchange_id: int
    audio_chunk: bytes
    sample_rate: int
    channels: int = 1
    timestamp_ms: Optional[int] = None
    chunk_sequence: Optional[int] = None

    def __post_init__(self):
        if self.interview_exchange_id <= 0:
            raise ValueError("interview_exchange_id must be positive")
        if not self.audio_chunk:
            raise ValueError("audio_chunk must not be empty")
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels < 1:
            raise ValueError("channels must be >= 1")


@dataclass(frozen=True)
class AudioSessionControl:
    """
    Session lifecycle control message.

    Frozen (immutable) after creation.
    """
    interview_exchange_id: int
    action: SessionAction
    reason: Optional[str] = None

    def __post_init__(self):
        if self.interview_exchange_id <= 0:
            raise ValueError("interview_exchange_id must be positive")


# ---------------------------------------------------------------------------
# Output Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AudioChunk:
    """
    Normalized audio chunk ready for downstream processing.

    All audio forwarded to transcription is 16 kHz mono.
    """
    exchange_id: int
    audio_data: bytes
    sample_rate: int
    channels: int
    timestamp_ms: int
    duration_ms: int
    normalized: bool


@dataclass(frozen=True)
class SilenceDetectedEvent:
    """
    Emitted when configurable silence threshold is reached
    or when a session ends.

    The consumer (orchestrator) decides the next action; the ingestion
    module MUST NOT advance interview state.
    """
    exchange_id: int
    silence_duration_ms: int
    last_audio_timestamp_ms: int
    should_evaluate: bool
    reason: SilenceReason
