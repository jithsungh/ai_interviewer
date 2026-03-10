"""
Interview API Routes — Parent REST Endpoints

Endpoints for interview data retrieval:
  GET  /{submission_id}/exchanges  — list exchanges (audit trail)
  GET  /{submission_id}/progress   — section-level progress breakdown

State-transition endpoints live in the session sub-module router
(registered separately at /api/v1/interviews/sessions).

Auth:
- Candidates can access their own submissions.
- Admins can access any submission.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import (
    get_db_session,
    get_identity,
)
from app.interview.api.contracts import (
    ExchangeListResponse,
    SectionProgressResponse,
)
from app.interview.api.service import InterviewApiService

logger = logging.getLogger(__name__)

router = APIRouter()


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────

def _build_service(db: Session) -> InterviewApiService:
    """Create an InterviewApiService with the request-scoped DB session."""
    return InterviewApiService(db=db)


def _resolve_candidate_id(identity) -> Optional[int]:
    """
    Return candidate_id if the caller is a candidate, None for admins.

    Admins can access any submission; candidates are scoped to their own.
    """
    if identity.user_type.value == "candidate":
        return identity.candidate_id  # candidates.id, not users.id
    return None


# ────────────────────────────────────────────────────────────
# Endpoints
# ────────────────────────────────────────────────────────────

@router.get(
    "/{submission_id}/exchanges",
    response_model=ExchangeListResponse,
    summary="List interview exchanges",
    status_code=200,
)
def list_exchanges(
    submission_id: int,
    include_responses: bool = Query(
        default=True,
        description="Include response data in exchange listing",
    ),
    section: Optional[str] = Query(
        default=None,
        description="Filter exchanges by section name",
        max_length=50,
    ),
    db: Session = Depends(get_db_session),
    identity=Depends(get_identity),
):
    """
    List all exchanges for an interview submission.

    Returns the complete audit trail of question/response snapshots.
    Supports optional filtering by section name and response inclusion.

    Authorization:
    - Candidate: can view own exchanges
    - Admin: can view all exchanges
    """
    svc = _build_service(db)
    candidate_id = _resolve_candidate_id(identity)

    return svc.list_exchanges(
        submission_id=submission_id,
        candidate_id=candidate_id,
        section=section,
        include_responses=include_responses,
    )


@router.get(
    "/{submission_id}/progress",
    response_model=SectionProgressResponse,
    summary="Get interview progress by section",
    status_code=200,
)
def get_progress(
    submission_id: int,
    db: Session = Depends(get_db_session),
    identity=Depends(get_identity),
):
    """
    Get detailed section-level progress for an interview submission.

    Returns overall progress and per-section breakdown calculated
    from the frozen template snapshot and completed exchanges.

    Authorization:
    - Candidate: can view own progress
    - Admin: can view any progress
    """
    svc = _build_service(db)
    candidate_id = _resolve_candidate_id(identity)

    return svc.get_progress(
        submission_id=submission_id,
        candidate_id=candidate_id,
    )
