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
    CareerRoadmapActiveResponse,
    CareerRoadmapHistoryResponse,
    CareerRoadmapResponse,
    CareerRoadmapStepDTO,
    CandidateProfileResponse,
    CandidatePrivacyPreferences,
    CandidateNotificationPreferences,
    CandidateSettingsResponse,
    CandidateUiPreferences,
    CandidateStatsResponse,
    CandidateSubmissionDTO,
    CandidateSubmissionDetailResponse,
    CandidateSubmissionListResponse,
    CandidateWindowDTO,
    CandidateWindowListResponse,
    DifficultyDistributionDTO,
    GenerateCareerInsightsRequest,
    GenerateCareerInsightsResponse,
    GenerateCareerRoadmapRequest,
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
    UpdateCareerRoadmapProgressRequest,
    UpdateCandidateProfileRequest,
    UpdateCandidateSettingsRequest,
    WindowOrganizationDTO,
    WindowRoleDTO,
    WindowRoleTemplateDTO,
    WindowTemplateDTO,
)
from app.candidate.api import mock_data
from app.candidate.api.career_path_generator import CareerPathGenerator
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
        self._career_generator = CareerPathGenerator()

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
    # Candidate Settings
    # ────────────────────────────────────────────────────────────

    def get_candidate_settings(self, user_id: int) -> CandidateSettingsResponse:
        result = self._repo.get_candidate_settings(user_id=user_id)
        if result is None:
            raise NotFoundError(resource_type="Candidate", resource_id=user_id)
        return CandidateSettingsResponse(
            candidate_id=result["candidate_id"],
            notification_preferences=CandidateNotificationPreferences(**result["notification_preferences"]),
            privacy_preferences=CandidatePrivacyPreferences(**result["privacy_preferences"]),
            ui_preferences=CandidateUiPreferences(**(result.get("ui_preferences") or {})),
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )

    def update_candidate_settings(
        self,
        user_id: int,
        body: UpdateCandidateSettingsRequest,
    ) -> CandidateSettingsResponse:
        updates = {
            "notification_preferences": body.notification_preferences.model_dump(exclude_unset=True) if body.notification_preferences else None,
            "privacy_preferences": body.privacy_preferences.model_dump(exclude_unset=True) if body.privacy_preferences else None,
            "ui_preferences": body.ui_preferences.model_dump(exclude_unset=True) if body.ui_preferences else None,
        }
        result = self._repo.update_candidate_settings(user_id=user_id, updates=updates)
        if result is None:
            raise NotFoundError(resource_type="Candidate", resource_id=user_id)
        return CandidateSettingsResponse(
            candidate_id=result["candidate_id"],
            notification_preferences=CandidateNotificationPreferences(**result["notification_preferences"]),
            privacy_preferences=CandidatePrivacyPreferences(**result["privacy_preferences"]),
            ui_preferences=CandidateUiPreferences(**(result.get("ui_preferences") or {})),
            created_at=result.get("created_at"),
            updated_at=result.get("updated_at"),
        )

    # ────────────────────────────────────────────────────────────
    # Career Path
    # ────────────────────────────────────────────────────────────

    def generate_career_insights(
        self,
        user_id: int,
        body: GenerateCareerInsightsRequest,
    ) -> GenerateCareerInsightsResponse:
        if body.use_cached:
            cached = self._repo.get_latest_career_insight_run(
                user_id=user_id,
                industry=body.industry,
                seniority=body.seniority,
            )
            if cached is not None:
                return GenerateCareerInsightsResponse(
                    run_id=cached["run_id"],
                    industry=cached["industry"],
                    seniority=cached["seniority"],
                    generation_source=cached["generation_source"],
                    model_provider=cached.get("model_provider"),
                    model_name=cached.get("model_name"),
                    insights=cached.get("insights", []),
                    created_at=cached["created_at"],
                )

        insights, source, provider, model_name = self._career_generator.generate_market_insights(
            industry=body.industry,
            seniority=body.seniority,
        )
        result = self._repo.create_career_insight_run(
            user_id=user_id,
            industry=body.industry,
            seniority=body.seniority,
            insights=insights,
            generation_source=source,
            model_provider=provider,
            model_name=model_name,
        )

        return GenerateCareerInsightsResponse(
            run_id=result["run_id"],
            industry=result["industry"],
            seniority=result["seniority"],
            generation_source=result["generation_source"],
            model_provider=result.get("model_provider"),
            model_name=result.get("model_name"),
            insights=result.get("insights", []),
            created_at=result["created_at"],
        )

    def generate_career_roadmap(
        self,
        user_id: int,
        body: GenerateCareerRoadmapRequest,
    ) -> CareerRoadmapResponse:
        steps, source, provider, model_name = self._career_generator.generate_role_roadmap(
            role=body.role,
            industry=body.industry,
        )
        result = self._repo.create_active_career_roadmap(
            user_id=user_id,
            industry=body.industry,
            target_role=body.role,
            steps=steps,
            generation_source=source,
            model_provider=provider,
            model_name=model_name,
            insight_run_id=body.insight_run_id,
            selected_insight=body.selected_insight.model_dump() if body.selected_insight else None,
        )
        return self._to_career_roadmap_response(result)

    def get_active_career_roadmap(self, user_id: int) -> CareerRoadmapActiveResponse:
        result = self._repo.get_active_career_roadmap(user_id=user_id)
        if result is None:
            return CareerRoadmapActiveResponse(roadmap=None)
        return CareerRoadmapActiveResponse(roadmap=self._to_career_roadmap_response(result))

    def list_career_roadmap_history(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> CareerRoadmapHistoryResponse:
        rows, total = self._repo.list_career_roadmap_history(
            user_id=user_id,
            page=page,
            per_page=per_page,
        )
        return CareerRoadmapHistoryResponse(
            data=[self._to_career_roadmap_response(row) for row in rows],
            pagination=self._paginate(page, per_page, total),
        )

    def update_career_roadmap_progress(
        self,
        user_id: int,
        roadmap_id: int,
        body: UpdateCareerRoadmapProgressRequest,
    ) -> CareerRoadmapResponse:
        result = self._repo.update_career_roadmap_progress(
            user_id=user_id,
            roadmap_id=roadmap_id,
            completed_levels=body.completed_levels,
            current_level=body.current_level,
        )
        if result is None:
            raise NotFoundError(resource_type="CareerRoadmap", resource_id=roadmap_id)
        return self._to_career_roadmap_response(result)

    def _to_career_roadmap_response(self, row: dict) -> CareerRoadmapResponse:
        return CareerRoadmapResponse(
            roadmap_id=row["roadmap_id"],
            candidate_id=row["candidate_id"],
            insight_run_id=row.get("insight_run_id"),
            industry=row["industry"],
            target_role=row["target_role"],
            selected_insight=row.get("selected_insight"),
            steps=[CareerRoadmapStepDTO(**step) for step in (row.get("steps") or [])],
            completed_levels=row.get("completed_levels") or [],
            current_level=row.get("current_level") or 1,
            is_active=bool(row.get("is_active", True)),
            generation_source=row.get("generation_source") or "fallback",
            model_provider=row.get("model_provider"),
            model_name=row.get("model_name"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

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
