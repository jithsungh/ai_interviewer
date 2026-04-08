"""
Interview Session API Routes

Endpoints for interview submission state management:
  POST /start      — candidate starts interview
  GET  /{id}/status — get session detail
  POST /complete   — candidate completes interview
  POST /cancel     — admin cancels interview
  POST /review     — admin reviews interview
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import (
    get_db_session_with_commit,
    get_db_session,
    require_admin,
    require_candidate,
    get_identity,
)
from app.interview.session.api.service import SessionService
from app.interview.session.contracts.schemas import (
    CancelInterviewRequest,
    CompleteInterviewRequest,
    ExpireOverdueRequest,
    ExpireOverdueResponse,
    InterviewSessionDetailDTO,
    InterviewSessionDTO,
    ReviewInterviewRequest,
    StartInterviewRequest,
)
from app.persistence.redis.client import get_redis_client
from app.shared.errors import (
    ConflictError,
    NotFoundError,
    ValidationError as AppValidationError,
)
from app.interview.session.domain.state_machine import StateTransitionError

logger = logging.getLogger(__name__)

router = APIRouter()


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _build_service(db: Session) -> SessionService:
    """Create a SessionService with the request-scoped DB and global Redis."""
    redis = get_redis_client()
    return SessionService(db=db, redis=redis)


# ────────────────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=InterviewSessionDTO,
    summary="Start interview",
    status_code=200,
)
def start_interview(
    body: StartInterviewRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity=Depends(require_candidate),
):
    """Transition a pending submission to in_progress."""
    svc = _build_service(db)
    try:
        dto, _transitioned = svc.start_interview(
            submission_id=body.submission_id,
            candidate_id=identity.candidate_id,
            consent_accepted=body.consent_accepted,
        )
    except StateTransitionError as exc:
        raise ConflictError(str(exc))

    return dto


@router.get(
    "/{submission_id}/status",
    response_model=InterviewSessionDetailDTO,
    summary="Get session status",
    status_code=200,
)
def get_session_status(
    submission_id: int,
    db: Session = Depends(get_db_session),
    identity=Depends(get_identity),
):
    """Return full session detail with exchanges."""
    svc = _build_service(db)
    # Admins can see any submission; candidates only their own.
    candidate_id = identity.candidate_id if identity.user_type.value == "candidate" else None
    return svc.get_session_status(submission_id=submission_id, candidate_id=candidate_id)


@router.post(
    "/complete",
    response_model=InterviewSessionDTO,
    summary="Complete interview",
    status_code=200,
)
def complete_interview(
    body: CompleteInterviewRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity=Depends(require_candidate),
):
    """Transition an in_progress submission to completed."""
    svc = _build_service(db)
    try:
        dto, _transitioned = svc.complete_interview(
            submission_id=body.submission_id,
            candidate_id=identity.candidate_id,
        )
    except StateTransitionError as exc:
        raise ConflictError(str(exc))

    return dto


@router.post(
    "/cancel",
    response_model=InterviewSessionDTO,
    summary="Cancel interview (admin)",
    status_code=200,
)
def cancel_interview(
    body: CancelInterviewRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity=Depends(require_admin),
):
    """Admin-only: cancel a pending or in_progress submission."""
    svc = _build_service(db)
    try:
        dto, _transitioned = svc.cancel_interview(
            submission_id=body.submission_id,
            admin_id=identity.user_id,
            reason=body.reason,
        )
    except StateTransitionError as exc:
        raise ConflictError(str(exc))

    return dto


@router.post(
    "/review",
    response_model=InterviewSessionDTO,
    summary="Review interview (admin)",
    status_code=200,
)
def review_interview(
    body: ReviewInterviewRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity=Depends(require_admin),
):
    """Admin-only: mark a completed/expired/cancelled submission as reviewed."""
    svc = _build_service(db)
    try:
        dto, _transitioned = svc.review_interview(
            submission_id=body.submission_id,
            admin_id=identity.user_id,
            review_notes=body.review_notes,
        )
    except StateTransitionError as exc:
        raise ConflictError(str(exc))

    return dto


@router.post(
    "/expire-overdue",
    response_model=ExpireOverdueResponse,
    summary="Expire overdue interviews (admin)",
    status_code=200,
)
def expire_overdue_interviews(
    body: ExpireOverdueRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity=Depends(require_admin),
):
    """Admin-only: expire stale in-progress submissions whose schedule has ended."""
    svc = _build_service(db)
    expired_count = svc.expire_overdue_submissions(
        actor=f"admin:{identity.user_id}",
        limit=body.limit,
    )
    return ExpireOverdueResponse(expired_count=expired_count, limit=body.limit)
