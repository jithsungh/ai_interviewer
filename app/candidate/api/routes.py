"""
Candidate API Routes

REST endpoints for candidate-facing operations:
  GET  /windows                      — list visible interview windows (Gap 1)
  GET  /submissions                  — list past submissions (Gap 2)
  GET  /submissions/{submission_id}  — detailed submission view
  GET  /stats                        — aggregate performance statistics (Gap 3)
  GET  /profile                      — get candidate profile (Gap 4)
  PUT  /profile                      — update candidate profile (Gap 4)
  GET  /practice/questions           — list practice questions by skill (Gap 5)
  POST /practice/start               — start ad-hoc practice session (Gap 6)
  GET  /resumes                      — list candidate resumes
  POST /resumes                      — upload a resume

URL prefix: /api/v1/candidate (set in router_registry.py)
Auth: All endpoints require candidate JWT (via require_candidate dependency).
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.bootstrap.dependencies import (
    get_db_session,
    get_db_session_with_commit,
    require_candidate,
)
from app.candidate.api.contracts import (
    CareerRoadmapActiveResponse,
    CareerRoadmapHistoryResponse,
    CareerRoadmapResponse,
    CandidateProfileResponse,
    CandidateSettingsResponse,
    CandidateStatsResponse,
    CandidateSubmissionDetailResponse,
    CandidateSubmissionListResponse,
    CandidateWindowListResponse,
    GenerateCareerInsightsRequest,
    GenerateCareerInsightsResponse,
    GenerateCareerRoadmapRequest,
    PracticeQuestionListResponse,
    PracticeFlashcardDeckActiveResponse,
    PracticeFlashcardDeckHistoryResponse,
    PracticeFlashcardDeckResponse,
    GeneratePracticeFlashcardsRequest,
    PracticeTemplateListResponse,
    ResumeListResponse,
    ResumeUploadResponse,
    StartPracticeRequest,
    StartPracticeResponse,
    UpdatePracticeFlashcardDeckProgressRequest,
    UpdateCareerRoadmapProgressRequest,
    UpdateCandidateProfileRequest,
    UpdateCandidateSettingsRequest,
)
from app.candidate.api.service import CandidateService
from app.shared.auth_context import IdentityContext

logger = logging.getLogger(__name__)

router = APIRouter()


# ────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────


class SubmissionStatusFilter(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    expired = "expired"
    cancelled = "cancelled"
    reviewed = "reviewed"


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
    status: Optional[SubmissionStatusFilter] = Query(
        None,
        description="Filter by submission status (e.g. completed, reviewed)",
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
        status=status.value if status else None,
    )


# ────────────────────────────────────────────────────────────
# Submission Detail
# ────────────────────────────────────────────────────────────


@router.get(
    "/submissions/{submission_id}",
    response_model=CandidateSubmissionDetailResponse,
    summary="Get full submission detail with nested data",
    status_code=200,
)
def get_submission_detail(
    submission_id: int,
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateSubmissionDetailResponse:
    """
    Get a detailed view of a single submission including
    window, role, template, result (with section scores),
    exchanges (with evaluations, code submissions, audio analytics),
    and proctoring events.
    """
    svc = _build_service(db)
    return svc.get_submission_detail(
        user_id=identity.user_id,
        submission_id=submission_id,
    )


@router.get(
    "/submissions/{submission_id}/exchanges",
    summary="Get exchanges for a submission (candidate-scoped)",
    status_code=200,
)
def get_submission_exchanges(
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
    identity: IdentityContext = Depends(require_candidate),
):
    """
    List exchanges for a submission. Automatically scoped to authenticated candidate.
    """
    from app.interview.api.service import InterviewApiService
    
    svc = InterviewApiService(db=db)
    return svc.list_exchanges(
        submission_id=submission_id,
        candidate_id=identity.candidate_id,  # Enforce candidate ownership
        section=section,
        include_responses=include_responses,
    )


@router.get(
    "/submissions/{submission_id}/results",
    summary="Get evaluation results for a submission (candidate-scoped)",
    status_code=200,
)
async def get_submission_results(
    submission_id: int,
    include_history: bool = Query(
        False, description="Include non-current results"
    ),
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
):
    """
    Get interview results for a submission. Automatically scoped to authenticated candidate.
    """
    from app.evaluation.api.dependencies import build_result_repository
    from app.evaluation.api.contracts import SubmissionResultsResponse, InterviewResultResponse
    from app.shared.errors import NotFoundError
    from app.interview.session.persistence.models import InterviewSubmissionModel
    
    # Verify ownership by candidate
    submission = db.query(InterviewSubmissionModel).filter(
        InterviewSubmissionModel.id == submission_id,
        InterviewSubmissionModel.candidate_id == identity.candidate_id,
    ).first()
    
    if not submission:
        raise NotFoundError(resource_type="Submission", resource_id=submission_id)
    
    result_repo = build_result_repository(db)
    results = result_repo.list_by_submission(
        submission_id, include_non_current=include_history
    )

    responses = [InterviewResultResponse.from_model(r) for r in results]

    current_id = None
    for r in results:
        if r.is_current:
            current_id = r.id
            break

    return SubmissionResultsResponse(
        interview_submission_id=submission_id,
        results=responses,
        current_result_id=current_id,
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


# ────────────────────────────────────────────────────────────
# Gap 4b: Candidate Settings
# ────────────────────────────────────────────────────────────


@router.get(
    "/settings",
    response_model=CandidateSettingsResponse,
    summary="Get candidate settings",
    status_code=200,
)
def get_settings(
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateSettingsResponse:
    """Get the candidate's persisted notification/privacy/UI settings."""
    svc = _build_service(db)
    return svc.get_candidate_settings(user_id=identity.user_id)


@router.put(
    "/settings",
    response_model=CandidateSettingsResponse,
    summary="Update candidate settings",
    status_code=200,
)
def update_settings(
    body: UpdateCandidateSettingsRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> CandidateSettingsResponse:
    """Update the candidate's persisted notification/privacy/UI settings."""
    svc = _build_service(db)
    return svc.update_candidate_settings(user_id=identity.user_id, body=body)


@router.post(
    "/career-path/insights/generate",
    response_model=GenerateCareerInsightsResponse,
    summary="Generate and persist career market insights",
    status_code=200,
)
def generate_career_insights(
    body: GenerateCareerInsightsRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> GenerateCareerInsightsResponse:
    svc = _build_service(db)
    return svc.generate_career_insights(user_id=identity.user_id, body=body)


@router.post(
    "/career-path/roadmap/generate",
    response_model=CareerRoadmapResponse,
    summary="Generate and persist active career roadmap",
    status_code=200,
)
def generate_career_roadmap(
    body: GenerateCareerRoadmapRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> CareerRoadmapResponse:
    svc = _build_service(db)
    return svc.generate_career_roadmap(user_id=identity.user_id, body=body)


@router.get(
    "/career-path/roadmap/active",
    response_model=CareerRoadmapActiveResponse,
    summary="Get candidate's active career roadmap",
    status_code=200,
)
def get_active_career_roadmap(
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CareerRoadmapActiveResponse:
    svc = _build_service(db)
    return svc.get_active_career_roadmap(user_id=identity.user_id)


@router.get(
    "/career-path/roadmap/history",
    response_model=CareerRoadmapHistoryResponse,
    summary="List candidate roadmap history",
    status_code=200,
)
def list_career_roadmap_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> CareerRoadmapHistoryResponse:
    svc = _build_service(db)
    return svc.list_career_roadmap_history(
        user_id=identity.user_id,
        page=page,
        per_page=per_page,
    )


@router.put(
    "/career-path/roadmap/{roadmap_id}/progress",
    response_model=CareerRoadmapResponse,
    summary="Update candidate roadmap completion progress",
    status_code=200,
)
def update_career_roadmap_progress(
    roadmap_id: int,
    body: UpdateCareerRoadmapProgressRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> CareerRoadmapResponse:
    svc = _build_service(db)
    return svc.update_career_roadmap_progress(
        user_id=identity.user_id,
        roadmap_id=roadmap_id,
        body=body,
    )


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
# Practice Templates (Interview Setup)
# ────────────────────────────────────────────────────────────


@router.get(
    "/practice/templates",
    response_model=PracticeTemplateListResponse,
    summary="List available practice interview templates",
    status_code=200,
)
def list_practice_templates(
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> PracticeTemplateListResponse:
    """
    List all active interview templates available for practice.
    Returns template cards for the Interview Setup page.
    """
    svc = _build_service(db)
    return svc.list_practice_templates()


# ────────────────────────────────────────────────────────────
# Start Practice Session
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
    Create a new practice interview submission.
    Accepts template_id, experience level, and interaction modes.
    Returns submission_id + session summary for the UI.
    """
    svc = _build_service(db)
    return svc.start_practice(
        user_id=identity.user_id,
        template_id=body.template_id,
        experience_level=body.experience_level,
        target_company=body.target_company,
        voice_interview=body.voice_interview,
        video_recording=body.video_recording,
        ai_proctoring=body.ai_proctoring,
        consent_accepted=body.consent_accepted,
    )


@router.post(
    "/practice/decks/generate",
    response_model=PracticeFlashcardDeckResponse,
    summary="Generate an AI-backed interview prep flashcard deck",
    status_code=201,
)
def generate_practice_deck(
    body: GeneratePracticeFlashcardsRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> PracticeFlashcardDeckResponse:
    svc = _build_service(db)
    return svc.generate_practice_flashcards(
        user_id=identity.user_id,
        role=body.role,
        industry=body.industry,
        card_count=body.card_count,
        question_type=body.question_type,
        difficulty=body.difficulty,
        use_cached=body.use_cached,
    )


@router.get(
    "/practice/decks/active",
    response_model=PracticeFlashcardDeckActiveResponse,
    summary="Get the active interview prep flashcard deck",
    status_code=200,
)
def get_active_practice_deck(
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> PracticeFlashcardDeckActiveResponse:
    svc = _build_service(db)
    return svc.get_active_practice_deck(user_id=identity.user_id)


@router.get(
    "/practice/decks/history",
    response_model=PracticeFlashcardDeckHistoryResponse,
    summary="List saved interview prep flashcard decks",
    status_code=200,
)
def list_practice_decks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> PracticeFlashcardDeckHistoryResponse:
    svc = _build_service(db)
    return svc.list_practice_deck_history(user_id=identity.user_id, page=page, per_page=per_page)


@router.get(
    "/practice/decks/{deck_id}",
    response_model=PracticeFlashcardDeckResponse,
    summary="Get a saved interview prep flashcard deck by ID",
    status_code=200,
)
def get_practice_deck(
    deck_id: int,
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> PracticeFlashcardDeckResponse:
    svc = _build_service(db)
    return svc.get_practice_deck(user_id=identity.user_id, deck_id=deck_id)


@router.put(
    "/practice/decks/{deck_id}/progress",
    response_model=PracticeFlashcardDeckResponse,
    summary="Update interview prep deck progress",
    status_code=200,
)
def update_practice_deck_progress(
    deck_id: int,
    body: UpdatePracticeFlashcardDeckProgressRequest,
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> PracticeFlashcardDeckResponse:
    svc = _build_service(db)
    return svc.update_practice_deck_progress(user_id=identity.user_id, deck_id=deck_id, body=body)


# ────────────────────────────────────────────────────────────
# Resumes
# ────────────────────────────────────────────────────────────


@router.get(
    "/resumes",
    response_model=ResumeListResponse,
    summary="List candidate resumes",
    status_code=200,
)
def list_resumes(
    db: Session = Depends(get_db_session),
    identity: IdentityContext = Depends(require_candidate),
) -> ResumeListResponse:
    """
    Get all resumes for the authenticated candidate,
    including parsed text and extracted data.
    """
    svc = _build_service(db)
    return svc.get_resumes(user_id=identity.user_id)


@router.post(
    "/resumes",
    response_model=ResumeUploadResponse,
    summary="Upload a resume",
    status_code=201,
)
def upload_resume(
    file: UploadFile = File(..., description="Resume file (pdf, docx)"),
    db: Session = Depends(get_db_session_with_commit),
    identity: IdentityContext = Depends(require_candidate),
) -> ResumeUploadResponse:
    """
    Upload a new resume. Accepted formats: PDF, DOCX.
    The file is stored in the server's local storage directory and a record is created
    in the resumes table linked to the candidate.
    """
    svc = _build_service(db)
    return svc.upload_resume(user_id=identity.user_id, file=file)
