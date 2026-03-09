"""
Candidate Service

Business logic layer for candidate-facing operations.
Orchestrates repository calls and maps to response DTOs.

Mock-data fallback: when no real data exists for a candidate,
the service returns mock data from mock_data.py, preserving
the exact response format expected by the frontend UI.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from sqlalchemy.orm import Session

from app.candidate.api.contracts import (
    CandidateProfileResponse,
    CandidateStatsResponse,
    CandidateSubmissionDTO,
    CandidateSubmissionDetailResponse,
    CandidateSubmissionListResponse,
    CandidateWindowDTO,
    CandidateWindowListResponse,
    PaginationMeta,
    PracticeQuestionDTO,
    PracticeQuestionListResponse,
    PracticeSkillDTO,
    ResumeDTO,
    ResumeListResponse,
    ScoreHistoryPoint,
    SkillBreakdownItem,
    StartPracticeResponse,
    SubmissionOrganizationDTO,
    SubmissionRoleDTO,
    SubmissionTemplateDTO,
    SubmissionWindowDTO,
    UpdateCandidateProfileRequest,
    WindowOrganizationDTO,
    WindowRoleDTO,
    WindowRoleTemplateDTO,
    WindowTemplateDTO,
)
from app.candidate.api import mock_data
from app.candidate.persistence.repository import CandidateQueryRepository
from app.shared.errors import NotFoundError, ValidationError as AppValidationError

logger = logging.getLogger(__name__)


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

        # ── Mock-data fallback ──
        if total == 0:
            mock_rows = mock_data.mock_windows()
            return CandidateWindowListResponse(
                data=[CandidateWindowDTO(**w) for w in mock_rows],
                pagination=self._paginate(1, per_page, len(mock_rows)),
            )

        data = [
            CandidateWindowDTO(
                id=r["id"],
                name=r["name"],
                scope=r["scope"],
                start_time=r["start_time"],
                end_time=r["end_time"],
                timezone=r.get("timezone"),
                organization=WindowOrganizationDTO(**r["organization"]),
                role_templates=[
                    WindowRoleTemplateDTO(
                        id=rt["id"],
                        window_id=rt["window_id"],
                        role_id=rt["role_id"],
                        template_id=rt["template_id"],
                        selection_weight=rt.get("selection_weight", 1),
                        role=WindowRoleDTO(**rt["role"]),
                        template=WindowTemplateDTO(**rt["template"]),
                    )
                    for rt in r.get("role_templates", [])
                ],
                max_allowed_submissions=r["max_allowed_submissions"],
                allow_after_end_time=r.get("allow_after_end_time", False),
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

        # ── Mock-data fallback ──
        if total == 0:
            mock_rows = mock_data.mock_submissions_list()
            return CandidateSubmissionListResponse(
                data=[CandidateSubmissionDTO(**s) for s in mock_rows],
                pagination=self._paginate(1, per_page, len(mock_rows)),
            )

        data = [
            CandidateSubmissionDTO(
                submission_id=r["submission_id"],
                window=SubmissionWindowDTO(**r["window"]),
                organization=SubmissionOrganizationDTO(**r["organization"]),
                role=SubmissionRoleDTO(**r["role"]),
                template=SubmissionTemplateDTO(**r["template"]) if r.get("template") else None,
                status=r["status"],
                submitted_at=r["submitted_at"],
                started_at=r["started_at"],
                final_score=r["final_score"],
                result_status=r["result_status"],
                recommendation=r["recommendation"],
                mode=r.get("mode"),
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

        # ── Mock-data fallback ──
        if raw["total_interviews"] == 0:
            mock = mock_data.mock_stats()
            return CandidateStatsResponse(
                total_interviews=mock["total_interviews"],
                average_score=mock["average_score"],
                pass_rate=mock["pass_rate"],
                total_practice_time_minutes=mock["total_practice_time_minutes"],
                total_practice_time=mock["total_practice_time"],
                strong_areas=mock["strong_areas"],
                improvement_areas=mock["improvement_areas"],
                score_history=[ScoreHistoryPoint(**s) for s in mock["score_history"]],
                skill_breakdown=[SkillBreakdownItem(**s) for s in mock["skill_breakdown"]],
            )

        # Format practice time as human-readable string
        total_mins = raw["total_practice_time_minutes"]
        hours, mins = divmod(total_mins, 60)
        if hours > 0:
            total_practice_time = f"{hours}h {mins}m"
        else:
            total_practice_time = f"{mins}m"

        return CandidateStatsResponse(
            total_interviews=raw["total_interviews"],
            average_score=raw["average_score"],
            pass_rate=raw["pass_rate"],
            total_practice_time_minutes=total_mins,
            total_practice_time=total_practice_time,
            strong_areas=raw.get("strong_areas", []),
            improvement_areas=raw.get("improvement_areas", []),
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

        # ── Mock-data fallback ──
        if profile is None:
            mock = mock_data.mock_profile()
            return CandidateProfileResponse(**mock)

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

        # ── Mock-data fallback ──
        if total == 0:
            mock_skills = mock_data.mock_practice_skills()
            mock_questions = mock_data.mock_practice_questions()
            return PracticeQuestionListResponse(
                skills=[PracticeSkillDTO(**s) for s in mock_skills],
                questions=[PracticeQuestionDTO(**q) for q in mock_questions],
                pagination=self._paginate(1, per_page, len(mock_questions)),
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
    # Submission Detail
    # ────────────────────────────────────────────────────────────

    def get_submission_detail(
        self,
        user_id: int,
        submission_id: int,
    ) -> CandidateSubmissionDetailResponse:
        detail = self._repo.get_submission_detail(
            user_id=user_id,
            submission_id=submission_id,
        )

        # ── Mock-data fallback ──
        if detail is None:
            mock = mock_data.mock_submission_detail(submission_id)
            if mock is None:
                raise NotFoundError(
                    resource_type="InterviewSubmission",
                    resource_id=submission_id,
                )
            return CandidateSubmissionDetailResponse(**mock)

        return CandidateSubmissionDetailResponse(**detail)

    # ────────────────────────────────────────────────────────────
    # Resumes
    # ────────────────────────────────────────────────────────────

    def get_resumes(self, user_id: int) -> ResumeListResponse:
        rows = self._repo.get_candidate_resumes(user_id)

        # ── Mock-data fallback ──
        if not rows:
            mock = mock_data.mock_resumes()
            return ResumeListResponse(
                data=[ResumeDTO(**r) for r in mock],
            )

        return ResumeListResponse(
            data=[ResumeDTO(**r) for r in rows],
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
