"""
Candidate Service

Business logic layer for candidate-facing operations.
Orchestrates repository calls and maps to response DTOs.

Mock-data fallback: when ENABLE_MOCK_DATA is True and no real data
exists for a candidate, the service returns mock data from mock_data.py,
preserving the exact response format expected by the frontend UI.
When ENABLE_MOCK_DATA is False (default), empty results are returned.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.candidate.api.contracts import (
    CandidateProfileResponse,
    CandidateStatsResponse,
    CandidateSubmissionDTO,
    CandidateSubmissionDetailResponse,
    CandidateSubmissionListResponse,
    CandidateWindowDTO,
    CandidateWindowListResponse,
    DifficultyDistributionDTO,
    PaginationMeta,
    PracticeQuestionDTO,
    PracticeQuestionListResponse,
    PracticeSkillDTO,
    PracticeTemplateDTO,
    PracticeTemplateListResponse,
    ResumeDTO,
    ResumeListResponse,
    ResumeUploadResponse,
    ScoreHistoryPoint,
    SessionSummaryDTO,
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
from app.persistence.blob import upload_blob, BlobStorageError

logger = logging.getLogger(__name__)


def _mock_data_enabled() -> bool:
    """Check if mock data fallback is enabled via feature flags."""
    from app.config import feature_flags
    if feature_flags is None:
        return False
    return feature_flags.ENABLE_MOCK_DATA


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

        # ── Mock-data fallback (only when ENABLE_MOCK_DATA=true) ──
        if total == 0 and _mock_data_enabled():
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

        # ── Mock-data fallback (only when ENABLE_MOCK_DATA=true) ──
        if total == 0 and _mock_data_enabled():
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

        # ── Mock-data fallback (when ENABLE_MOCK_DATA=true) ──
        if _mock_data_enabled():
            mock = mock_data.mock_stats()
            # If there's real data, merge total interviews to look realistic, otherwise use mock wholesale
            total_interviews = raw.get("total_interviews", 0) if raw else 0
            if total_interviews == 0:
                total_interviews = mock["total_interviews"]
                
            return CandidateStatsResponse(
                total_interviews=total_interviews,
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

        # Profile is personal user data — never replaced with mock content.
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

        # ── Mock-data fallback (only when ENABLE_MOCK_DATA=true) ──
        if total == 0 and _mock_data_enabled():
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
    # Practice Templates (Interview Setup)
    # ────────────────────────────────────────────────────────────

    def list_practice_templates(self) -> PracticeTemplateListResponse:
        """Return all active templates for the Interview Setup page."""
        templates = self._repo.list_practice_templates()
        return PracticeTemplateListResponse(
            templates=[PracticeTemplateDTO(**t) for t in templates],
        )

    # ────────────────────────────────────────────────────────────
    # Start Practice
    # ────────────────────────────────────────────────────────────

    def start_practice(
        self,
        user_id: int,
        template_id: int,
        experience_level: str,
        target_company: Optional[str],
        voice_interview: bool,
        video_recording: bool,
        ai_proctoring: bool,
        consent_accepted: bool,
    ) -> StartPracticeResponse:
        if not consent_accepted:
            raise AppValidationError("Consent is required to start a practice session")

        submission, template = self._repo.create_practice_submission(
            user_id=user_id,
            template_id=template_id,
            experience_level=experience_level,
            target_company=target_company,
            voice_interview=voice_interview,
            video_recording=video_recording,
            ai_proctoring=ai_proctoring,
        )

        # Build session summary from template structure
        ts = template.template_structure or {}
        topics_section = (ts.get("sections") or {}).get("topics_assessment") or {}
        topic_names = [t.get("topic_name", "") for t in (topics_section.get("topics") or [])]
        coding_section = (ts.get("sections") or {}).get("coding_round") or {}

        # Count difficulty distribution from coding problems
        diff_dist = DifficultyDistributionDTO()
        for prob in coding_section.get("problems", []):
            d = prob.get("difficulty", "").lower()
            if d == "easy":
                diff_dist.easy += 1
            elif d == "medium":
                diff_dist.medium += 1
            elif d == "hard":
                diff_dist.hard += 1

        session_summary = SessionSummaryDTO(
            interview_type=template.name,
            duration_minutes=template.total_estimated_time_minutes,
            total_questions=ts.get("total_questions"),
            experience_level=experience_level,
            difficulty_distribution=diff_dist,
            topics=topic_names,
            adaptive=topics_section.get("difficulty_strategy", "dynamic") == "dynamic"
                if topics_section else True,
        )

        return StartPracticeResponse(
            submission_id=submission.id,
            status=submission.status,
            started_at=submission.started_at,
            session_summary=session_summary,
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

        # ── Mock-data fallback (only when ENABLE_MOCK_DATA=true) ──
        if detail is None and _mock_data_enabled():
            mock = mock_data.mock_submission_detail(submission_id)
            if mock is not None:
                return CandidateSubmissionDetailResponse(**mock)

        if detail is None:
            raise NotFoundError(
                resource_type="InterviewSubmission",
                resource_id=submission_id,
            )

        return CandidateSubmissionDetailResponse(**detail)

    # ────────────────────────────────────────────────────────────
    # Resumes
    # ────────────────────────────────────────────────────────────

    def get_resumes(self, user_id: int) -> ResumeListResponse:
        rows = self._repo.get_candidate_resumes(user_id)

        # ── Mock-data fallback (only when ENABLE_MOCK_DATA=true) ──
        if not rows and _mock_data_enabled():
            mock = mock_data.mock_resumes()
            return ResumeListResponse(
                data=[ResumeDTO(**r) for r in mock],
            )

        return ResumeListResponse(
            data=[ResumeDTO(**r) for r in rows],
        )

    def upload_resume(
        self,
        user_id: int,
        file: UploadFile,
    ) -> ResumeUploadResponse:
        _ALLOWED_TYPES = {
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        content_type = file.content_type or ""
        if content_type not in _ALLOWED_TYPES:
            raise AppValidationError(
                "Only PDF and Word documents are accepted (pdf, doc, docx)"
            )

        from app.config.settings import AzureStorageSettings
        try:
            cfg = AzureStorageSettings()
            container = cfg.azure_container_resumes
        except Exception:
            container = "candidate-resumes"

        try:
            result = upload_blob(
                container_name=container,
                data=file.file,
                original_filename=file.filename or "resume",
                content_type=content_type,
                prefix=f"candidate_{user_id}",
            )
            file_url = result["url"]
        except BlobStorageError as exc:
            logger.error("Blob upload failed for user %s: %s", user_id, exc)
            raise AppValidationError("File upload failed; please try again later") from exc

        row = self._repo.create_resume(user_id=user_id, file_url=file_url)
        return ResumeUploadResponse(**row)

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
