"""
Candidate API Routes

REST endpoints for candidate-facing operations:
  GET  /windows                 — list visible interview windows (Gap 1)
  GET  /submissions             — list past submissions (Gap 2)
  GET  /stats                   — aggregate performance statistics (Gap 3)
  GET  /profile                 — get candidate profile (Gap 4)
  PUT  /profile                 — update candidate profile (Gap 4)
  GET  /practice/questions      — list practice questions by skill (Gap 5)
  POST /practice/start          — start ad-hoc practice session (Gap 6)

URL prefix: /api/v1/candidate (set in router_registry.py)
Auth: All endpoints require candidate JWT (via require_candidate dependency).
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import (
    get_db_session,
    get_db_session_with_commit,
    require_candidate,
)
from app.candidate.api.contracts import (
    CandidateProfileResponse,
    CandidateStatsResponse,
    CandidateSubmissionListResponse,
    CandidateWindowListResponse,
    PracticeQuestionListResponse,
    StartPracticeRequest,
    StartPracticeResponse,
    UpdateCandidateProfileRequest,
)
from app.candidate.api.service import CandidateService
from app.shared.auth_context import IdentityContext

logger = logging.getLogger(__name__)

router = APIRouter()


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────


def _build_service(db: Session) -> CandidateService:
    return CandidateService(db=db)


# ────────────────────────────────────────────────────────────
# Gap 1: Candidate Window Listing
# ────────────────────────────────────────────────────────────


@router.get(
    "/windows",
    response_model=CandidateWindowListResponse,
    summary="List interview windows visible to this candidate",
    status_code=200,
)
def list_windows(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateWindowListResponse:
    """
    List interview windows the candidate can see:
    - Global scope windows (visible to all)
    - Windows where the candidate has existing submissions
    """
    svc = _build_service(db)
    return svc.list_windows(
        user_id=identity.user_id,
        page=page,
        per_page=per_page,
    )


# ────────────────────────────────────────────────────────────
# Gap 2: Candidate Submission History
# ────────────────────────────────────────────────────────────


@router.get(
    "/submissions",
    response_model=CandidateSubmissionListResponse,
    summary="List candidate's past interview submissions",
    status_code=200,
)
def list_submissions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(
        None,
        description="Filter by submission status (e.g. completed, reviewed)",
        max_length=20,
    ),
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateSubmissionListResponse:
    """
    List all submissions for the authenticated candidate,
    including window/org/role info and interview results.
    """
    svc = _build_service(db)
    return svc.list_submissions(
        user_id=identity.user_id,
        page=page,
        per_page=per_page,
        status=status,
    )


# ────────────────────────────────────────────────────────────
# Gap 3: Candidate Performance Statistics
# ────────────────────────────────────────────────────────────


@router.get(
    "/stats",
    response_model=CandidateStatsResponse,
    summary="Get aggregate performance statistics",
    status_code=200,
)
def get_stats(
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateStatsResponse:
    """
    Returns aggregate stats: total interviews, average score,
    pass rate, score history, and skill breakdown.
    """
    svc = _build_service(db)
    return svc.get_stats(user_id=identity.user_id)


# ────────────────────────────────────────────────────────────
# Gap 4: Candidate Profile
# ────────────────────────────────────────────────────────────


@router.get(
    "/profile",
    response_model=CandidateProfileResponse,
    summary="Get candidate profile",
    status_code=200,
)
def get_profile(
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateProfileResponse:
    """
    Get the full candidate profile including personal info,
    skills, education, work experience, and social links.
    """
    svc = _build_service(db)
    return svc.get_profile(user_id=identity.user_id)


@router.put(
    "/profile",
    response_model=CandidateProfileResponse,
    summary="Update candidate profile",
    status_code=200,
)
def update_profile(
    body: UpdateCandidateProfileRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateProfileResponse:
    """
    Update the candidate's profile. Only provided fields are updated.
    """
    svc = _build_service(db)
    return svc.update_profile(
        user_id=identity.user_id,
        body=body,
    )


# ────────────────────────────────────────────────────────────
# Gap 5: Practice Question Listing
# ────────────────────────────────────────────────────────────


@router.get(
    "/practice/questions",
    response_model=PracticeQuestionListResponse,
    summary="List practice questions by skill and difficulty",
    status_code=200,
)
def list_practice_questions(
    skill: Optional[str] = Query(
        None,
        description="Filter by skill type (e.g. 'behavioral', 'technical', 'coding')",
        max_length=50,
    ),
    difficulty: Optional[str] = Query(
        None,
        description="Filter by difficulty (easy, medium, hard)",
        max_length=10,
    ),
    question_type: Optional[str] = Query(
        None,
        description="Filter by question type",
        max_length=20,
    ),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> PracticeQuestionListResponse:
    """
    List available practice questions organized by skill area.
    Includes completion status for the candidate.
    """
    svc = _build_service(db)
    return svc.list_practice_questions(
        user_id=identity.user_id,
        skill=skill,
        difficulty=difficulty,
        question_type=question_type,
        page=page,
        per_page=per_page,
    )


# ────────────────────────────────────────────────────────────
# Gap 6: Start Practice Session
# ────────────────────────────────────────────────────────────


@router.post(
    "/practice/start",
    response_model=StartPracticeResponse,
    summary="Start a new practice interview session",
    status_code=201,
)
def start_practice(
    body: StartPracticeRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> StartPracticeResponse:
    """
    Create a new ad-hoc practice interview submission.
    Returns a submission_id that can be used with the WebSocket endpoint.
    """
    svc = _build_service(db)
    return svc.start_practice(
        user_id=identity.user_id,
        interview_type=body.interview_type,
        difficulty=body.difficulty,
        consent_accepted=body.consent_accepted,
    )
