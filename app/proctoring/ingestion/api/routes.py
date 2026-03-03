"""
Proctoring Ingestion API — Event Intake Endpoints

REST endpoints for single and batch proctoring event ingestion.
Advisory-only: never blocks interview flow.

Endpoints:
- POST /api/v1/proctoring/events          — ingest single event
- POST /api/v1/proctoring/events/batch     — ingest batch of events
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import get_db_session_with_commit, get_identity
from app.persistence.redis import get_redis_client
from app.proctoring.ingestion.contracts.schemas import (
    BatchEventRequest,
    BatchIngestionResult,
    EventIngestionResult,
    ProctoringEventInput,
)
from app.proctoring.ingestion.domain.ingestion_service import IngestionService
from app.shared.auth_context import IdentityContext
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)

router = APIRouter()


def _build_ingestion_service(
    session: Session,
) -> IngestionService:
    """Factory for IngestionService with DI."""
    try:
        redis = get_redis_client()
    except Exception:
        redis = None
    return IngestionService(session=session, redis_client=redis)


@router.post(
    "/events",
    response_model=EventIngestionResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single proctoring event",
    description="Accepts a proctoring event for processing. Non-blocking, advisory-only.",
)
async def ingest_event(
    event: ProctoringEventInput,
    session: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(get_identity),
) -> EventIngestionResult:
    """
    Ingest a single proctoring event.

    Validates event, applies severity/weight rules, persists,
    and triggers risk score recomputation.

    Returns 202 Accepted (event queued/processed).
    """
    service = _build_ingestion_service(session)
    result = service.ingest_event(event)
    return result


@router.post(
    "/events/batch",
    response_model=BatchIngestionResult,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of proctoring events",
    description="Accepts up to 50 proctoring events for a single submission.",
)
async def ingest_batch(
    request: BatchEventRequest,
    session: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(get_identity),
) -> BatchIngestionResult:
    """
    Ingest a batch of proctoring events.

    All events must target the same submission_id.
    Each event is processed individually to ensure clustering rules
    account for previously ingested events in the same batch.

    Returns 202 Accepted with counts of accepted/rejected events.
    """
    service = _build_ingestion_service(session)
    result = service.ingest_batch(
        submission_id=request.submission_id,
        events=request.events,
    )
    return result
