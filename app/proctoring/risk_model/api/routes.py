"""
Proctoring Risk Model API — Risk Score & Review Queue Endpoints

REST endpoints for risk score queries and admin proctoring review.
Advisory-only: these endpoints OBSERVE, never DECIDE.

Endpoints:
- GET /api/v1/proctoring/risk/{submission_id}           — get risk score
- POST /api/v1/proctoring/risk/{submission_id}/recompute — recompute from scratch
- GET /api/v1/proctoring/events/{submission_id}          — list events for submission
- GET /api/v1/proctoring/review-queue                    — admin review queue
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import (
    get_db_session,
    get_db_session_with_commit,
    get_identity,
    require_admin,
)
from app.persistence.redis import get_redis_client
from app.proctoring.persistence.repository import ProctoringEventRepository
from app.proctoring.risk_model.contracts.schemas import (
    ProctoringEventResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
    RiskScoreResponse,
)
from app.proctoring.risk_model.domain.risk_service import RiskModelService
from app.shared.auth_context import IdentityContext
from app.shared.errors import NotFoundError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)

router = APIRouter()


def _build_risk_service(session: Session) -> RiskModelService:
    """Factory for RiskModelService with DI."""
    try:
        redis = get_redis_client()
    except Exception:
        redis = None
    return RiskModelService(session=session, redis_client=redis)


# ════════════════════════════════════════════════════════════════════════
# Risk Score Endpoints
# ════════════════════════════════════════════════════════════════════════


@router.get(
    "/risk/{submission_id}",
    response_model=RiskScoreResponse,
    summary="Get risk score for a submission",
    description="Computes and returns the current risk score. Advisory-only.",
)
async def get_risk_score(
    submission_id: int,
    session: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(get_identity),
) -> RiskScoreResponse:
    """Get the current risk score for an interview submission."""
    service = _build_risk_service(session)
    risk = service.compute(submission_id)
    return RiskScoreResponse(
        submission_id=risk.submission_id,
        total_risk=risk.total_risk,
        classification=risk.classification,
        recommended_action=risk.recommended_action,
        event_count=risk.event_count,
        breakdown_by_type=risk.breakdown_by_type,
        top_events=risk.top_events,
        severity_counts=risk.severity_counts,
        computation_algorithm=risk.computation_algorithm,
        computed_at=risk.computed_at,
    )


@router.post(
    "/risk/{submission_id}/recompute",
    response_model=RiskScoreResponse,
    summary="Recompute risk score from scratch (audit)",
    description="Forces full recomputation of risk score. Admin only.",
)
async def recompute_risk_score(
    submission_id: int,
    session: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_admin),
) -> RiskScoreResponse:
    """Recompute risk score from scratch for audit purposes."""
    service = _build_risk_service(session)
    risk = service.recompute(submission_id)
    return RiskScoreResponse(
        submission_id=risk.submission_id,
        total_risk=risk.total_risk,
        classification=risk.classification,
        recommended_action=risk.recommended_action,
        event_count=risk.event_count,
        breakdown_by_type=risk.breakdown_by_type,
        top_events=risk.top_events,
        severity_counts=risk.severity_counts,
        computation_algorithm=risk.computation_algorithm,
        computed_at=risk.computed_at,
    )


# ════════════════════════════════════════════════════════════════════════
# Event Listing
# ════════════════════════════════════════════════════════════════════════


@router.get(
    "/events/{submission_id}",
    response_model=List[ProctoringEventResponse],
    summary="List proctoring events for a submission",
    description="Returns all proctoring events in chronological order.",
)
async def list_events(
    submission_id: int,
    severity: Optional[str] = Query(None, description="Filter by severity"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    session: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(get_identity),
) -> List[ProctoringEventResponse]:
    """List all proctoring events for a submission."""
    repo = ProctoringEventRepository(session)
    events = repo.get_by_submission(
        submission_id=submission_id,
        severity_filter=severity,
        event_type_filter=event_type,
    )
    return [ProctoringEventResponse.from_model(e) for e in events]


# ════════════════════════════════════════════════════════════════════════
# Admin Review Queue
# ════════════════════════════════════════════════════════════════════════


@router.get(
    "/review-queue",
    response_model=ReviewQueueResponse,
    summary="Admin proctoring review queue",
    description="Returns flagged submissions sorted by risk score (highest first). Admin only.",
)
async def get_review_queue(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_admin),
) -> ReviewQueueResponse:
    """
    Get the admin proctoring review queue.

    Returns submissions where proctoring_flagged = TRUE,
    sorted by risk score descending.

    Requires admin authentication.
    """
    # Query flagged submissions directly from interview_submissions
    count_result = session.execute(
        sql_text(
            "SELECT COUNT(*) FROM interview_submissions WHERE proctoring_flagged = TRUE"
        )
    ).scalar() or 0

    rows = session.execute(
        sql_text(
            """
            SELECT
                id AS submission_id,
                COALESCE(proctoring_risk_score, 0) AS total_risk,
                COALESCE(proctoring_risk_classification, 'low') AS classification,
                COALESCE(proctoring_flagged, FALSE) AS flagged,
                COALESCE(proctoring_reviewed, FALSE) AS reviewed
            FROM interview_submissions
            WHERE proctoring_flagged = TRUE
            ORDER BY proctoring_risk_score DESC NULLS LAST
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).fetchall()

    items = []
    for row in rows:
        # Get event count per submission
        repo = ProctoringEventRepository(session)
        event_count = repo.count_by_submission(row.submission_id)
        items.append(
            ReviewQueueItem(
                submission_id=row.submission_id,
                total_risk=float(row.total_risk),
                classification=row.classification,
                event_count=event_count,
                flagged=bool(row.flagged),
                reviewed=bool(row.reviewed),
            )
        )

    return ReviewQueueResponse(
        total=count_result,
        items=items,
        limit=limit,
        offset=offset,
    )
