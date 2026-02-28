"""
Audio Ingestion API Contracts

Pydantic request / response models for the REST and WebSocket endpoints
exposed by the audio ingestion submodule.

No business logic — validation of format and types only.
Reuses domain contracts from ``audio.ingestion.contracts``.
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from app.audio.ingestion.contracts import SessionAction, SilenceReason


# ═══════════════════════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════════════════════


class AudioSessionStartRequest(BaseModel):
    """POST body to start an audio session."""

    sample_rate: int = Field(
        default=16000,
        gt=0,
        description="Audio sample rate in Hz",
    )
    silence_threshold_ms: Optional[int] = Field(
        default=None,
        gt=0,
        description="Custom silence threshold in ms (default from config)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"sample_rate": 16000},
                {"sample_rate": 48000, "silence_threshold_ms": 5000},
            ]
        }
    }


class AudioSessionControlRequest(BaseModel):
    """POST body for session control (pause / resume / stop)."""

    action: Literal["pause", "resume", "stop"] = Field(
        ...,
        description="Session action to perform",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Human-readable reason",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════════════════


class AudioSessionResponse(BaseModel):
    """Response after starting / controlling a session."""

    exchange_id: int
    status: str
    message: str


class SilenceEventResponse(BaseModel):
    """Serialised SilenceDetectedEvent for WebSocket push."""

    exchange_id: int
    silence_duration_ms: int
    last_audio_timestamp_ms: int
    should_evaluate: bool
    reason: str


class AudioChunkAck(BaseModel):
    """Acknowledgement returned for each ingested chunk (WebSocket)."""

    exchange_id: int
    chunk_sequence: Optional[int] = None
    timestamp_ms: int
    duration_ms: int
    normalized: bool


class ErrorResponse(BaseModel):
    """Standard error envelope (matches shared error serialisation)."""

    error_code: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
