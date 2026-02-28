"""
Audio Ingestion Module

Entry point for all audio data in voice-based interviews.
Accepts real-time audio streams, normalizes format, detects silence,
manages audio session lifecycle, and buffers chunks for downstream transcription.

This module is stateless — it persists nothing.
All audio metadata is persisted by audio.persistence after transcription.
"""

from .service import AudioIngestionService
from .contracts import (
    AudioStreamRequest,
    AudioSessionControl,
    AudioChunk,
    SilenceDetectedEvent,
    SessionAction,
    SilenceReason,
)
from .exceptions import (
    SessionAlreadyActiveError,
    SessionNotFoundError,
    SessionClosedError,
    SessionPausedError,
    InvalidExchangeStageError,
    AudioIngestionError,
)

__all__ = [
    "AudioIngestionService",
    "AudioStreamRequest",
    "AudioSessionControl",
    "AudioChunk",
    "SilenceDetectedEvent",
    "SessionAction",
    "SilenceReason",
    "SessionAlreadyActiveError",
    "SessionNotFoundError",
    "SessionClosedError",
    "SessionPausedError",
    "InvalidExchangeStageError",
    "AudioIngestionError",
]
