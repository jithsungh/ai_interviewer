"""
Candidate Service

Business logic layer for candidate-facing operations.
Orchestrates repository calls and maps to response DTOs.
"""

from __future__ import annotations

import math
from typing import Optional

from sqlalchemy.orm import Session

from app.candidate.api.contracts import (
    CandidateProfileResponse,
    CandidateStatsResponse,
    CandidateSubmissionDTO,
    CandidateSubmissionListResponse,
    CandidateWindowDTO,
    CandidateWindowListResponse,
    PaginationMeta,
    PracticeQuestionDTO,
    PracticeQuestionListResponse,
    PracticeSkillDTO,
    ScoreHistoryPoint,
    SkillBreakdownItem,
    StartPracticeResponse,
    SubmissionOrganizationDTO,
    SubmissionRoleDTO,
    SubmissionWindowDTO,
    UpdateCandidateProfileRequest,
    WindowOrganizationDTO,
    WindowRoleDTO,
)
from app.candidate.persistence.repository import CandidateQueryRepository
from app.shared.errors import NotFoundError, ValidationError as AppValidationError


class CandidateService:
    """High-level candidate operations."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = CandidateQueryRepository(db)

    # ────────────────────────────────────────────────────────────
    # Gap 1: Windows
    # ────────────────────────────────────────────────────────────

    def list_windows(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> CandidateWindowListResponse:
        rows, total = self._repo.list_windows_for_candidate(
            user_id=user_id,
            page=page,
            per_page=per_page,
        )
        data = [
            CandidateWindowDTO(
                id=r["id"],
                name=r["name"],
                scope=r["scope"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                organization=WindowOrganizationDTO(**r["organization"]),
                role=WindowRoleDTO(**r["role"]),
                duration_minutes=r["duration_minutes"],
                max_allowed_submissions=r["max_allowed_submissions"],
                allow_resubmission=r["allow_resubmission"],
                candidate_submission_count=r["candidate_submission_count"],
                status=r["status"],
            )
            for r in rows
        ]
        return CandidateWindowListResponse(
            data=data,
            pagination=self._paginate(page, per_page, total),
        )

    # ────────────────────────────────────────────────────────────
    # Gap 2: Submissions
    # ────────────────────────────────────────────────────────────

    def list_submissions(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        status: Optional[str] = None,
    ) -> CandidateSubmissionListResponse:
        rows, total = self._repo.list_submissions_for_candidate(
            user_id=user_id,
            page=page,
            per_page=per_page,
            status_filter=status,
        )
        data = [
            CandidateSubmissionDTO(
                submission_id=r["submission_id"],
                window=SubmissionWindowDTO(**r["window"]),
                organization=SubmissionOrganizationDTO(**r["organization"]),
                role=SubmissionRoleDTO(**r["role"]),
                status=r["status"],
                submitted_at=r["submitted_at"],
                started_at=r["started_at"],
                final_score=r["final_score"],
                result_status=r["result_status"],
                recommendation=r["recommendation"],
            )
            for r in rows
        ]
        return CandidateSubmissionListResponse(
            data=data,
            pagination=self._paginate(page, per_page, total),
        )

    # ────────────────────────────────────────────────────────────
    # Gap 3: Stats
    # ────────────────────────────────────────────────────────────

    def get_stats(self, user_id: int) -> CandidateStatsResponse:
        raw = self._repo.get_candidate_stats(user_id)
        return CandidateStatsResponse(
            total_interviews=raw["total_interviews"],
            average_score=raw["average_score"],
            pass_rate=raw["pass_rate"],
            total_practice_time_minutes=raw["total_practice_time_minutes"],
            score_history=[
                ScoreHistoryPoint(**s) for s in raw["score_history"]
            ],
            skill_breakdown=[
                SkillBreakdownItem(**s) for s in raw["skill_breakdown"]
            ],
        )

    # ────────────────────────────────────────────────────────────
    # Gap 4: Profile
    # ────────────────────────────────────────────────────────────

    def get_profile(self, user_id: int) -> CandidateProfileResponse:
        profile = self._repo.get_candidate_profile(user_id)
        if profile is None:
            raise NotFoundError(
                resource_type="CandidateProfile",
                resource_id=user_id,
            )
        return CandidateProfileResponse(**profile)

    def update_profile(
        self,
        user_id: int,
        body: UpdateCandidateProfileRequest,
    ) -> CandidateProfileResponse:
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            raise AppValidationError("No fields to update")

        result = self._repo.update_candidate_profile(
            user_id=user_id,
            updates=updates,
        )
        if result is None:
            raise NotFoundError(
                resource_type="CandidateProfile",
                resource_id=user_id,
            )
        return CandidateProfileResponse(**result)

    # ────────────────────────────────────────────────────────────
    # Gap 5: Practice Questions
    # ────────────────────────────────────────────────────────────

    def list_practice_questions(
        self,
        user_id: int,
        skill: Optional[str] = None,
        difficulty: Optional[str] = None,
        question_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> PracticeQuestionListResponse:
        skills_summary, questions, total = self._repo.list_practice_questions(
            user_id=user_id,
            skill=skill,
            difficulty=difficulty,
            question_type=question_type,
            page=page,
            per_page=per_page,
        )
        return PracticeQuestionListResponse(
            skills=[PracticeSkillDTO(**s) for s in skills_summary],
            questions=[PracticeQuestionDTO(**q) for q in questions],
            pagination=self._paginate(page, per_page, total),
        )

    # ────────────────────────────────────────────────────────────
    # Gap 6: Start Practice
    # ────────────────────────────────────────────────────────────

    def start_practice(
        self,
        user_id: int,
        interview_type: str,
        difficulty: str,
        consent_accepted: bool,
    ) -> StartPracticeResponse:
        if not consent_accepted:
            raise AppValidationError("Consent is required to start a practice session")

        submission = self._repo.create_practice_submission(
            user_id=user_id,
            interview_type=interview_type,
            difficulty=difficulty,
        )
        return StartPracticeResponse(
            submission_id=submission.id,
            status=submission.status,
            started_at=submission.started_at,
        )

    # ────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _paginate(page: int, per_page: int, total: int) -> PaginationMeta:
        return PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=max(1, math.ceil(total / per_page)),
        )
