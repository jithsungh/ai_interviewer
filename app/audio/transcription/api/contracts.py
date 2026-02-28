"""
Audio Transcription API Contracts

Pydantic request / response models for the REST endpoints exposed by the
transcription submodule.

No business logic — validation of format and types only.
Follows the same pattern as ``audio.ingestion.api.contracts``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════
# Request Models
# ═══════════════════════════════════════════════════════════════════════════


class TranscribeRequest(BaseModel):
    """POST body for manual / diagnostic batch transcription."""

    audio_base64: str = Field(
        ...,
        min_length=1,
        description="Base64-encoded audio data (16 kHz mono WAV / PCM)",
    )
    sample_rate: int = Field(
        default=16000,
        gt=0,
        description="Audio sample rate in Hz",
    )
    language: Optional[str] = Field(
        default=None,
        max_length=10,
        description="ISO 639-1 language code (e.g. 'en', 'es')",
    )
    context: Optional[str] = Field(
        default=None,
        max_length=256,
        description="Contextual hint for better accuracy",
    )
    provider: Optional[Literal["whisper", "google", "local"]] = Field(
        default=None,
        description="Override the default transcription provider",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "audio_base64": "UklGRi4AAABXQVZF...",
                    "sample_rate": 16000,
                    "language": "en",
                },
            ]
        }
    }


# ═══════════════════════════════════════════════════════════════════════════
# Response Models
# ═══════════════════════════════════════════════════════════════════════════


class TranscriptSegmentResponse(BaseModel):
    """Word- or phrase-level transcript segment."""

    text: str
    start_ms: int
    end_ms: int
    confidence: float


class TranscriptionResponse(BaseModel):
    """Response for a completed transcription."""

    transcript: str
    confidence_score: float
    language_detected: Optional[str] = None
    segments: List[TranscriptSegmentResponse] = Field(default_factory=list)
    provider: Optional[str] = None


class TranscriptionHealthResponse(BaseModel):
    """Response for the transcription provider health check."""

    provider: str
    status: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error envelope (matches shared error serialisation)."""

    error_code: str
    message: str
    metadata: Optional[Dict[str, Any]] = None
