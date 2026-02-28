"""
Audio Transcription API Routes

REST endpoints for manual / diagnostic transcription.

The primary transcription path is internal (ingestion → service callback),
but these endpoints allow:
  - Manual batch transcription (admin / testing)
  - Provider health checks

URL prefix: ``/api/v1/audio/transcription`` (set in router_registry.py)

Auth: All endpoints require an authenticated identity.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends

from app.bootstrap.dependencies import get_identity
from app.shared.auth_context import IdentityContext
from app.shared.observability import get_context_logger

from .contracts import (
    ErrorResponse,
    TranscribeRequest,
    TranscriptionHealthResponse,
    TranscriptionResponse,
    TranscriptSegmentResponse,
)
from .dependencies import get_transcription_service
from app.audio.transcription.contracts import TranscriptionRequest
from app.audio.transcription.service import TranscriptionService

logger = get_context_logger(__name__)

router = APIRouter()


# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――
# Batch transcription
# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
    status_code=200,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
    },
    summary="Batch transcribe audio",
)
async def transcribe_audio(
    body: TranscribeRequest,
    identity: IdentityContext = Depends(get_identity),
):
    """
    Transcribe Base64-encoded audio data using the configured STT provider.

    Primarily for manual testing and admin diagnostics.  The normal
    production path is the internal ingestion → transcription callback.
    """
    try:
        audio_bytes = base64.b64decode(body.audio_base64)
    except Exception:
        from app.shared.errors import ValidationError

        raise ValidationError(
            message="Invalid base64 audio data",
            field="audio_base64",
        )

    svc: TranscriptionService = get_transcription_service()

    # Allow per-request provider override
    if body.provider and body.provider != svc._provider_name:
        from app.audio.transcription.service import TranscriptionService as _Svc

        svc = _Svc(
            provider=body.provider,
            api_key=svc._api_key,
            max_retries=svc._max_retries,
            retry_delay_s=svc._retry_delay_s,
            timeout_s=svc._timeout_s,
        )

    request = TranscriptionRequest(
        audio_data=audio_bytes,
        sample_rate=body.sample_rate,
        language=body.language,
        context=body.context,
    )

    result = await svc.transcribe(request)

    return TranscriptionResponse(
        transcript=result.transcript,
        confidence_score=result.confidence_score,
        language_detected=result.language_detected,
        segments=[
            TranscriptSegmentResponse(
                text=seg.text,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                confidence=seg.confidence,
            )
            for seg in result.segments
        ],
        provider=result.provider_metadata.get("provider"),
    )


# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――
# Health check
# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――


@router.get(
    "/health",
    response_model=TranscriptionHealthResponse,
    summary="Check transcription provider health",
)
async def transcription_health(
    identity: IdentityContext = Depends(get_identity),
):
    """
    Return the configured transcription provider and its readiness status.
    """
    svc: TranscriptionService = get_transcription_service()
    provider_name = svc._provider_name

    return TranscriptionHealthResponse(
        provider=provider_name,
        status="configured",
        message=f"Transcription provider '{provider_name}' is configured",
    )
