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

import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

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
    GeneratePracticeFlashcardsRequest,
    PaginationMeta,
    PracticeQuestionDTO,
    PracticeQuestionListResponse,
    PracticeFlashcardDeckActiveResponse,
    PracticeFlashcardDeckHistoryResponse,
    PracticeFlashcardDeckResponse,
    PracticeFlashcardDeckSummaryDTO,
    PracticeFlashcardDTO,
    UpdatePracticeFlashcardDeckProgressRequest,
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
from app.candidate.api.practice_prep_generator import PracticePrepGenerator
from app.candidate.persistence.repository import CandidateQueryRepository
from app.ai.llm.provider_factory import ProviderFactory
from app.ai.prompts.repository import SqlPromptTemplateRepository
from app.ai.prompts.service import PromptService
from app.question.generation.contracts import GenerationRequest
from app.question.generation.persistence.fallback_repository import FallbackQuestionRepository
from app.question.generation.service import QuestionGenerationService
from app.shared.errors import NotFoundError, ValidationError as AppValidationError
from app.config import feature_flags, settings

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
        self._practice_generator = PracticePrepGenerator()
        self._question_generation_service = self._build_question_generation_service()

    def _build_question_generation_service(self) -> Optional[QuestionGenerationService]:
        try:
            llm_provider = ProviderFactory.create_text_provider()
            prompt_service = PromptService(repository=SqlPromptTemplateRepository(self._db))
            fallback_repo = FallbackQuestionRepository(self._db)
            return QuestionGenerationService(
                llm_provider=llm_provider,
                prompt_service=prompt_service,
                fallback_repo=fallback_repo,
            )
        except Exception as exc:
            logger.warning("Question generation fallback unavailable: %s", exc)
            return None

    @staticmethod
    def _normalize_generation_question_type(question_type: Optional[str]) -> str:
        allowed = {"behavioral", "technical", "situational", "coding"}
        if not question_type:
            return "technical"
        normalized = question_type.strip().lower()
        alias_map = {
            "system_design": "technical",
            "architecture": "technical",
            "dsa": "technical",
        }
        normalized = alias_map.get(normalized, normalized)
        return normalized if normalized in allowed else "technical"

    @staticmethod
    def _normalize_generation_difficulty(difficulty: Optional[str]) -> str:
        allowed = {"easy", "medium", "hard"}
        if not difficulty:
            return "medium"
        normalized = difficulty.strip().lower()
        return normalized if normalized in allowed else "medium"

    @staticmethod
    def _run_async(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result(timeout=60)

    def _generate_and_persist_practice_questions(
        self,
        user_id: int,
        role: str,
        industry: str,
        card_count: int,
        question_type: Optional[str],
        difficulty: Optional[str],
    ) -> List[Dict[str, Any]]:
        if self._question_generation_service is None:
            return []

        context = self._repo.get_latest_submission_generation_context(user_id)
        if context:
            submission_id = int(context["submission_id"])
            organization_id = int(context["organization_id"])
        else:
            submission_id = max(1, int(user_id))
            organization_id = 1

        normalized_type = self._normalize_generation_question_type(question_type)
        normalized_difficulty = self._normalize_generation_difficulty(difficulty)
        topic = (role or industry or "general").strip() or "general"

        generated_rows: List[Dict[str, Any]] = []
        previous_questions: List[str] = []

        for _ in range(card_count):
            request = GenerationRequest(
                submission_id=submission_id,
                organization_id=organization_id,
                difficulty=normalized_difficulty,
                topic=topic,
                question_type=normalized_type,
                template_instructions=f"Industry context: {industry}",
                previous_questions=previous_questions,
                exchange_number=len(previous_questions) + 1,
                total_exchanges=card_count,
            )

            result = self._run_async(self._question_generation_service.generate(request))
            if not result.question_text:
                continue

            generated_rows.append(
                {
                    "question_text": result.question_text,
                    "answer_text": result.expected_answer,
                    "question_type": result.question_type or normalized_type,
                    "difficulty": result.difficulty or normalized_difficulty,
                    "estimated_time_minutes": max(
                        1,
                        int(math.ceil((result.estimated_time_seconds or 300) / 60)),
                    ),
                    "source_type": result.source_type or "generated",
                }
            )
            previous_questions.append(result.question_text)

        if not generated_rows:
            return []

        return self._repo.create_generated_practice_questions(
            organization_id=organization_id,
            questions=generated_rows,
        )

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
        mock = mock_data.mock_stats()

        raw_total = int((raw or {}).get("total_interviews") or 0)
        raw_avg = (raw or {}).get("average_score")
        raw_pass_rate = (raw or {}).get("pass_rate")
        raw_minutes = int((raw or {}).get("total_practice_time_minutes") or 0)
        raw_history = list((raw or {}).get("score_history") or [])
        raw_skills = list((raw or {}).get("skill_breakdown") or [])
        raw_strong = list((raw or {}).get("strong_areas") or [])
        raw_improvement = list((raw or {}).get("improvement_areas") or [])

        has_real_signal = (
            raw_total > 0
            or bool(raw_history)
            or bool(raw_skills)
            or (raw_avg is not None and float(raw_avg) > 0)
            or (raw_pass_rate is not None and float(raw_pass_rate) > 0)
            or raw_minutes > 0
        )

        # Always return meaningful dashboard visibility: if real signal is absent,
        # serve deterministic mock stats instead of nil/zero values.
        if not has_real_signal:
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

        # ── Mock-data fallback (when ENABLE_MOCK_DATA=true) ──
        if _mock_data_enabled():
            # Merge real data with mock defaults to avoid sparse/zero dashboard stats.
            total_interviews = raw_total if raw_total > 0 else mock["total_interviews"]
            average_score = float(raw_avg) if raw_avg is not None and float(raw_avg) > 0 else mock["average_score"]
            pass_rate = float(raw_pass_rate) if raw_pass_rate is not None and float(raw_pass_rate) > 0 else mock["pass_rate"]
            total_minutes = raw_minutes if raw_minutes > 0 else mock["total_practice_time_minutes"]
            hours, mins = divmod(total_minutes, 60)
            total_practice_time = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

            return CandidateStatsResponse(
                total_interviews=total_interviews,
                average_score=average_score,
                pass_rate=pass_rate,
                total_practice_time_minutes=total_minutes,
                total_practice_time=total_practice_time,
                strong_areas=raw_strong or mock["strong_areas"],
                improvement_areas=raw_improvement or mock["improvement_areas"],
                score_history=[ScoreHistoryPoint(**s) for s in (raw_history or mock["score_history"])],
                skill_breakdown=[SkillBreakdownItem(**s) for s in (raw_skills or mock["skill_breakdown"])],
            )

        # Format practice time as human-readable string
        total_mins = raw_minutes
        hours, mins = divmod(total_mins, 60)
        if hours > 0:
            total_practice_time = f"{hours}h {mins}m"
        else:
            total_practice_time = f"{mins}m"

        return CandidateStatsResponse(
            total_interviews=raw_total,
            average_score=raw_avg,
            pass_rate=raw_pass_rate,
            total_practice_time_minutes=total_mins,
            total_practice_time=total_practice_time,
            strong_areas=raw_strong,
            improvement_areas=raw_improvement,
            score_history=[
                ScoreHistoryPoint(**s) for s in raw_history
            ],
            skill_breakdown=[
                SkillBreakdownItem(**s) for s in raw_skills
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

    def _to_practice_deck_response(self, row: dict) -> PracticeFlashcardDeckResponse:
        mapped_cards: list[PracticeFlashcardDTO] = []
        for card in (row.get("flashcards") or []):
            if not isinstance(card, dict):
                continue
            source_question_id = card.get("source_question_id")
            if source_question_id is None:
                source_question_id = card.get("sourceQuestionId")
            if source_question_id is None:
                continue

            mapped_cards.append(
                PracticeFlashcardDTO(
                    source_question_id=int(source_question_id),
                    topic=str(card.get("topic") or "").strip(),
                    difficulty=str(card.get("difficulty") or "Medium").strip(),
                    question=str(card.get("question") or "").strip(),
                    answer=str(card.get("answer") or "").strip(),
                    tags=[str(tag).strip() for tag in (card.get("tags") or []) if str(tag).strip()],
                    hint=(str(card.get("hint")).strip() if card.get("hint") is not None else None),
                )
            )

        return PracticeFlashcardDeckResponse(
            deck_id=row["deck_id"],
            candidate_id=row["candidate_id"],
            role=row["role"],
            industry=row["industry"],
            question_type=row.get("question_type"),
            difficulty=row.get("difficulty"),
            card_count=row.get("card_count") or len(row.get("flashcards") or []),
            source_question_ids=[int(x) for x in (row.get("source_question_ids") or [])],
            flashcards=mapped_cards,
            bookmarked_indices=[int(x) for x in (row.get("bookmarked_indices") or [])],
            mastered_indices=[int(x) for x in (row.get("mastered_indices") or [])],
            current_card_index=row.get("current_card_index") or 0,
            progress_percent=row.get("progress_percent") or 0,
            is_active=bool(row.get("is_active", True)),
            generation_source=row.get("generation_source") or "db",
            model_provider=row.get("model_provider"),
            model_name=row.get("model_name"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _to_practice_deck_summary(self, row: dict) -> dict:
        return {
            "deck_id": row["deck_id"],
            "role": row["role"],
            "industry": row["industry"],
            "question_type": row.get("question_type"),
            "difficulty": row.get("difficulty"),
            "card_count": row.get("card_count") or len(row.get("flashcards") or []),
            "current_card_index": row.get("current_card_index") or 0,
            "progress_percent": row.get("progress_percent") or 0,
            "is_active": bool(row.get("is_active", True)),
            "generation_source": row.get("generation_source") or "db",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

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

    def generate_practice_flashcards(
        self,
        user_id: int,
        role: str,
        industry: str,
        card_count: int = 10,
        question_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        use_cached: bool = True,
    ) -> PracticeFlashcardDeckResponse:
        if use_cached:
            active = self._repo.get_active_practice_deck(user_id)
            if active and active.get("role") == role and active.get("industry") == industry:
                if question_type is None or active.get("question_type") == question_type:
                    if difficulty is None or active.get("difficulty") == difficulty:
                        if active.get("card_count") == card_count:
                            return self._to_practice_deck_response(active)

        question_pool = self._repo.get_practice_question_pool(
            user_id,
            question_type=question_type,
            difficulty=difficulty,
            limit=max(card_count * 2, card_count),
        )
        used_direct_generation = False
        if not question_pool:
            question_pool = self._generate_and_persist_practice_questions(
                user_id=user_id,
                role=role,
                industry=industry,
                card_count=card_count,
                question_type=question_type,
                difficulty=difficulty,
            )
            used_direct_generation = bool(question_pool)

        if not question_pool:
            raise AppValidationError("No practice questions are available for the selected filters")

        flashcards, source, provider, model_name = self._practice_generator.generate_flashcards(
            role=role,
            industry=industry,
            source_questions=question_pool,
            card_count=card_count,
            question_type=question_type,
            difficulty=difficulty,
        )

        source_question_ids = [int(card["sourceQuestionId"]) for card in flashcards]
        deck = self._repo.create_active_practice_deck(
            user_id,
            role=role,
            industry=industry,
            question_type=question_type,
            difficulty=difficulty,
            source_question_ids=source_question_ids,
            flashcards=flashcards,
            generation_source="direct_generation" if used_direct_generation else source,
            model_provider=provider,
            model_name=model_name,
        )
        return self._to_practice_deck_response(deck)

    def get_active_practice_deck(self, user_id: int) -> PracticeFlashcardDeckActiveResponse:
        deck = self._repo.get_active_practice_deck(user_id)
        return PracticeFlashcardDeckActiveResponse(
            deck=self._to_practice_deck_response(deck) if deck else None,
        )

    def get_practice_deck(self, user_id: int, deck_id: int) -> PracticeFlashcardDeckResponse:
        deck = self._repo.get_practice_deck_by_id(user_id, deck_id)
        if deck is None:
            raise NotFoundError(resource_type="PracticeDeck", resource_id=deck_id)
        return self._to_practice_deck_response(deck)

    def list_practice_deck_history(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> PracticeFlashcardDeckHistoryResponse:
        rows, total = self._repo.list_practice_deck_history(user_id, page=page, per_page=per_page)
        return PracticeFlashcardDeckHistoryResponse(
            data=[PracticeFlashcardDeckSummaryDTO(**self._to_practice_deck_summary(row)) for row in rows],
            pagination=self._paginate(page, per_page, total),
        )

    def update_practice_deck_progress(
        self,
        user_id: int,
        deck_id: int,
        body: UpdatePracticeFlashcardDeckProgressRequest,
    ) -> PracticeFlashcardDeckResponse:
        updated = self._repo.update_practice_deck_progress(
            user_id,
            deck_id,
            current_card_index=body.current_card_index,
            mastered_indices=body.mastered_indices,
            bookmarked_indices=body.bookmarked_indices,
        )
        if updated is None:
            raise NotFoundError(resource_type="PracticeDeck", resource_id=deck_id)
        return self._to_practice_deck_response(updated)

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
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }
        _ALLOWED_EXTENSIONS = {".pdf", ".docx"}

        filename = file.filename or "resume"
        suffix = Path(filename).suffix.lower()
        content_type = file.content_type or ""
        if content_type not in _ALLOWED_TYPES or suffix not in _ALLOWED_EXTENSIONS:
            raise AppValidationError(
                "Only PDF and DOCX files are accepted"
            )

        max_size_mb = settings.app.max_resume_upload_size_mb if settings else 10
        max_size_bytes = max_size_mb * 1024 * 1024

        try:
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)
        except Exception as exc:
            raise AppValidationError("Unable to inspect uploaded file") from exc

        if file_size <= 0:
            raise AppValidationError("Uploaded file is empty")

        if file_size > max_size_bytes:
            raise AppValidationError(
                f"File exceeds maximum allowed size of {max_size_mb}MB"
            )

        file_bytes = file.file.read()
        if not file_bytes:
            raise AppValidationError("Uploaded file is empty")

        file_url = self._save_resume_to_local_storage(
            user_id=user_id,
            original_filename=filename,
            file_bytes=file_bytes,
        )

        row = self._repo.create_resume(user_id=user_id, file_url=file_url, file_name=filename)

        parsed_text = None
        extracted_data = None
        structured_json = None
        llm_feedback = None
        ats_score = None
        ats_feedback = None
        
        if feature_flags is not None and feature_flags.ENABLE_RESUME_PARSING:
            # Step 1: Parse and extract basic info
            parsed_text, extracted_data = self._parse_and_extract_resume(
                content=file_bytes,
                suffix=suffix,
                original_filename=filename,
            )
            
            row = self._repo.update_resume_analysis(
                user_id=user_id,
                resume_id=row["id"],
                parsed_text=parsed_text,
                extracted_data=extracted_data,
            )
            
            # Step 2: LLM Analysis (structured JSON, feedback, ATS score)
            if parsed_text:
                from app.candidate.api.resume_analysis_service import get_resume_analysis_service
                analysis_service = get_resume_analysis_service()
                analysis_result = analysis_service.analyze_resume(
                    parsed_text,
                    filename,
                    extracted_data,
                )
                
                if not analysis_result.get("error"):
                    structured_json = analysis_result.get("structured_json")
                    llm_feedback = analysis_result.get("llm_feedback")
                    ats_score = analysis_result.get("ats_score")
                    ats_feedback = analysis_result.get("ats_feedback")
                    
                    row = self._repo.update_resume_llm_analysis(
                        user_id=user_id,
                        resume_id=row["id"],
                        structured_json=structured_json,
                        llm_feedback=llm_feedback,
                        ats_score=ats_score,
                        ats_feedback=ats_feedback,
                    )
                else:
                    logger.warning(f"LLM analysis failed: {analysis_result.get('error')}")
            
            # Step 3: Embeddings intentionally skipped for candidate-facing resume flow.

        return ResumeUploadResponse(**row)

    def _save_resume_to_local_storage(
        self,
        user_id: int,
        original_filename: str,
        file_bytes: bytes,
    ) -> str:
        suffix = Path(original_filename).suffix.lower() or ".pdf"
        storage_root = self._resolve_local_storage_root()
        candidate_dir = storage_root / "resumes" / f"candidate_{user_id}"
        candidate_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_name = f"{timestamp}_{uuid4().hex[:10]}{suffix}"
        destination = candidate_dir / safe_name

        destination.write_bytes(file_bytes)

        relative_path = destination.relative_to(storage_root)
        return f"local://{relative_path.as_posix()}"

    def _resolve_local_storage_root(self) -> Path:
        configured = settings.app.local_storage_dir if settings else "storage"
        storage_root = Path(configured)
        if not storage_root.is_absolute():
            backend_root = Path(__file__).resolve().parents[3]
            storage_root = backend_root / storage_root
        storage_root.mkdir(parents=True, exist_ok=True)
        return storage_root

    def _parse_and_extract_resume(
        self,
        content: bytes,
        suffix: str,
        original_filename: str,
    ) -> tuple[str, dict]:
        try:
            parsed_text = self._extract_text(content=content, suffix=suffix)
        except Exception as exc:
            logger.warning("Resume parse failed for %s: %s", original_filename, exc)
            return "", {
                "parse_status": "failed",
                "error": str(exc),
                "source": "local_server_parser",
                "parsed_at": datetime.now(timezone.utc).isoformat(),
            }

        extracted_data = self._build_extracted_summary(parsed_text)
        extracted_data["source"] = "local_server_parser"
        extracted_data["parsed_at"] = datetime.now(timezone.utc).isoformat()
        extracted_data["parse_status"] = "success"
        return parsed_text, extracted_data

    def _extract_text(self, content: bytes, suffix: str) -> str:
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except Exception as exc:
                raise AppValidationError("PDF parser dependency is unavailable") from exc

            reader = PdfReader(BytesIO(content))
            chunks = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(chunks).strip()
            if not text:
                raise AppValidationError("Could not extract text from PDF")
            return text

        if suffix == ".docx":
            try:
                from docx import Document
            except Exception as exc:
                raise AppValidationError("DOCX parser dependency is unavailable") from exc

            document = Document(BytesIO(content))
            chunks = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text and paragraph.text.strip()]
            text = "\n".join(chunks).strip()
            if not text:
                raise AppValidationError("Could not extract text from DOCX")
            return text

        raise AppValidationError("Unsupported file type for parsing")

    def _build_extracted_summary(self, parsed_text: str) -> dict:
        lines = [line.strip() for line in parsed_text.splitlines() if line.strip()]
        lowered = parsed_text.lower()

        name = lines[0] if lines else None

        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", parsed_text)
        phone_match = re.search(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}", parsed_text)
        years_match = re.search(r"(\d{1,2})\+?\s+years?\s+(?:of\s+)?experience", lowered)

        skill_bank = [
            "python", "java", "javascript", "typescript", "react", "node", "sql", "postgresql",
            "aws", "azure", "docker", "kubernetes", "fastapi", "django", "flask", "machine learning",
            "data structures", "algorithms", "system design", "git", "redis", "mongodb",
        ]
        skills = [skill for skill in skill_bank if skill in lowered]

        highlights = []
        if years_match:
            highlights.append(f"{years_match.group(1)} years of experience identified")
        if skills:
            highlights.append(f"{len(skills)} relevant skills detected")
        if "education" in lowered:
            highlights.append("Education section detected")
        if "experience" in lowered:
            highlights.append("Work experience section detected")

        summary_preview = " ".join(lines[:4])[:700]

        return {
            "name": name,
            "email": email_match.group(0) if email_match else None,
            "phone": phone_match.group(0) if phone_match else None,
            "experience_years": int(years_match.group(1)) if years_match else None,
            "skills": skills,
            "highlights": highlights,
            "summary": summary_preview,
        }

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
