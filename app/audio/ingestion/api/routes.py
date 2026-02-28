"""
Audio Ingestion API Routes

REST endpoints for audio session lifecycle management.

WebSocket streaming is intentionally excluded from this first iteration
(the REQUIREMENTS.md describes WebSocket as the transport, but the REST
control-plane endpoints are needed first and can be integration-tested
without a running WS server).

URL prefix: ``/api/v1/audio/ingestion`` (set in router_registry.py)

Auth: All endpoints require an authenticated identity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Request

from app.bootstrap.dependencies import get_identity
from app.shared.auth_context import IdentityContext
from app.shared.observability import get_context_logger

from .contracts import (
    AudioSessionControlRequest,
    AudioSessionResponse,
    AudioSessionStartRequest,
    ErrorResponse,
)
from .dependencies import get_audio_ingestion_service
from app.audio.ingestion.service import AudioIngestionService

logger = get_context_logger(__name__)

router = APIRouter()


# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――
# Session lifecycle
# ―――――――――――――――――――――――――――――――――――――――――――――――――――――――――――――


@router.post(
    "/exchanges/{exchange_id}/session/start",
    response_model=AudioSessionResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse}},
    summary="Start audio session",
)
async def start_audio_session(
    exchange_id: int = Path(..., gt=0),
    body: AudioSessionStartRequest = AudioSessionStartRequest(),
    identity: IdentityContext = Depends(get_identity),
):
    """
    Start a new audio ingestion session bound to *exchange_id*.

    Returns 201 on success, 409 if a session already exists.
    """
    svc: AudioIngestionService = get_audio_ingestion_service()

    svc.start_session(
        exchange_id=exchange_id,
        sample_rate=body.sample_rate,
        silence_threshold_ms=body.silence_threshold_ms,
    )

    return AudioSessionResponse(
        exchange_id=exchange_id,
        status="started",
        message=f"Audio session started for exchange {exchange_id}",
    )


@router.post(
    "/exchanges/{exchange_id}/session/control",
    response_model=AudioSessionResponse,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
    summary="Control audio session",
)
async def control_audio_session(
    body: AudioSessionControlRequest,
    exchange_id: int = Path(..., gt=0),
    identity: IdentityContext = Depends(get_identity),
):
    """
    Pause, resume, or stop an active audio session.
    """
    svc: AudioIngestionService = get_audio_ingestion_service()

    if body.action == "pause":
        svc.pause_session(exchange_id, reason=body.reason)
        status = "paused"
    elif body.action == "resume":
        svc.resume_session(exchange_id)
        status = "resumed"
    elif body.action == "stop":
        svc.stop_session(exchange_id)
        status = "stopped"
    else:
        # Should not happen — Pydantic validates action
        status = "unknown"

    return AudioSessionResponse(
        exchange_id=exchange_id,
        status=status,
        message=f"Audio session {status} for exchange {exchange_id}",
    )


@router.get(
    "/exchanges/{exchange_id}/session/status",
    response_model=AudioSessionResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get audio session status",
)
async def get_audio_session_status(
    exchange_id: int = Path(..., gt=0),
    identity: IdentityContext = Depends(get_identity),
):
    """
    Return the current status of an audio session.
    """
    svc: AudioIngestionService = get_audio_ingestion_service()
    session = svc._session_manager.get_session(exchange_id)

    if session.is_paused:
        status = "paused"
    elif session.is_active:
        status = "active"
    else:
        status = "closed"

    return AudioSessionResponse(
        exchange_id=exchange_id,
        status=status,
        message=f"Audio session is {status}",
    )
