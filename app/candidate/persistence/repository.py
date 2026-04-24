"""
Candidate Repository

Data access layer for candidate-facing queries.
Handles window listing, submission history, stats aggregation,
profile retrieval, and practice question lookups.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case, func, text
from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError

from app.admin.persistence.models import (
    CodingProblemModel,
    InterviewSubmissionWindowModel,
    InterviewTemplateModel,
    QuestionModel,
    RoleModel,
    RubricDimensionModel,
    TopicModel,
    WindowRoleTemplateModel,
)
from app.auth.persistence.models import (
    Candidate,
    CandidateCareerInsightRun,
    CandidateCareerRoadmap,
    CandidatePracticeDeckRun,
    CandidateSettings,
    Organization,
    User,
)
from app.audio.persistence.models import AudioAnalyticsModel
from app.coding.persistence.models import CodeSubmissionModel, CodeExecutionResultModel
from app.evaluation.persistence.models import (
    EvaluationDimensionScoreModel,
    EvaluationModel,
    InterviewResultModel,
)
from app.interview.session.persistence.models import (
    InterviewExchangeModel,
    InterviewSubmissionModel,
)
from app.proctoring.persistence.models import ProctoringEventModel
from app.shared.errors import NotFoundError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class CandidateQueryRepository:
    """Read-heavy repository for candidate-facing data."""

    def __init__(self, session: Session) -> None:
        self._db = session

    def _resolve_candidate_id(self, user_id: int) -> int:
        """
        Resolve candidates.id from users.id.

        The IdentityContext carries users.id, but interview_submissions
        references candidates.id via FK. This helper bridges the gap.
        """
        row = (
            self._db.query(Candidate.id)
            .filter(Candidate.user_id == user_id)
            .first()
        )
        if row is None:
            raise NotFoundError(
                resource_type="Candidate",
                resource_id=user_id,
            )
        return row[0]

    # ────────────────────────────────────────────────────────────
    # Gap 1: Candidate Window Listing
    # ────────────────────────────────────────────────────────────

    def list_windows_for_candidate(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List interview windows visible to a candidate.

        A window is visible if:
        - scope = 'global', OR
        - scope = 'local' and candidate has a submission for that window, OR
        - scope = 'only_invited' and candidate has a submission for that window.

        Returns (list_of_dicts, total_count).
        """
        now = datetime.now(timezone.utc)
        candidate_id = self._resolve_candidate_id(user_id)

        # Subquery: count candidate's submissions per window
        sub_count = (
            self._db.query(
                InterviewSubmissionModel.window_id,
                func.count(InterviewSubmissionModel.id).label("submission_count"),
            )
            .filter(InterviewSubmissionModel.candidate_id == candidate_id)
            .group_by(InterviewSubmissionModel.window_id)
            .subquery()
        )

        # Step 1: Get distinct visible window IDs with pagination
        window_id_q = (
            self._db.query(
                InterviewSubmissionWindowModel.id,
            )
            .join(
                WindowRoleTemplateModel,
                WindowRoleTemplateModel.window_id == InterviewSubmissionWindowModel.id,
            )
            .outerjoin(
                sub_count,
                sub_count.c.window_id == InterviewSubmissionWindowModel.id,
            )
            .filter(
                (InterviewSubmissionWindowModel.scope == "global")
                | (func.coalesce(sub_count.c.submission_count, 0) > 0)
            )
            .distinct()
        )

        total = window_id_q.count()

        window_ids = [
            row[0]
            for row in window_id_q
            .order_by(InterviewSubmissionWindowModel.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        ]

        if not window_ids:
            return [], total

        # Step 2: Batch-fetch windows with org and submission counts (single query)
        window_rows = (
            self._db.query(
                InterviewSubmissionWindowModel,
                Organization.id.label("org_id"),
                Organization.name.label("org_name"),
                Organization.organization_type.label("org_type"),
                func.coalesce(sub_count.c.submission_count, 0).label("submission_count"),
            )
            .join(
                Organization,
                Organization.id == InterviewSubmissionWindowModel.organization_id,
            )
            .outerjoin(
                sub_count,
                sub_count.c.window_id == InterviewSubmissionWindowModel.id,
            )
            .filter(InterviewSubmissionWindowModel.id.in_(window_ids))
            .order_by(InterviewSubmissionWindowModel.start_time.desc())
            .all()
        )

        # Step 3: Batch-fetch all role-template mappings with joined role + template (single query)
        wrt_rows = (
            self._db.query(
                WindowRoleTemplateModel,
                RoleModel,
                InterviewTemplateModel,
            )
            .join(RoleModel, RoleModel.id == WindowRoleTemplateModel.role_id)
            .outerjoin(
                InterviewTemplateModel,
                InterviewTemplateModel.id == WindowRoleTemplateModel.template_id,
            )
            .filter(WindowRoleTemplateModel.window_id.in_(window_ids))
            .all()
        )

        # Group role-templates by window_id
        wrt_by_window: Dict[int, list] = {}
        for wrt, role_obj, tmpl_obj in wrt_rows:
            wrt_by_window.setdefault(wrt.window_id, []).append((wrt, role_obj, tmpl_obj))

        # Step 4: Build results
        results = []
        for row in window_rows:
            w = row[0]

            # Compute status
            if now < w.start_time:
                status = "upcoming"
            elif now > w.end_time:
                status = "closed"
            else:
                status = "open"

            role_templates = []
            for wrt, role_obj, tmpl_obj in wrt_by_window.get(w.id, []):
                role_templates.append({
                    "id": wrt.id,
                    "window_id": wrt.window_id,
                    "role_id": wrt.role_id,
                    "template_id": wrt.template_id,
                    "selection_weight": wrt.selection_weight,
                    "role": {
                        "id": role_obj.id,
                        "name": role_obj.name,
                        "description": getattr(role_obj, "description", None),
                        "scope": getattr(role_obj, "scope", None),
                    } if role_obj else {"id": wrt.role_id, "name": "Unknown"},
                    "template": {
                        "id": tmpl_obj.id,
                        "name": tmpl_obj.name,
                        "description": getattr(tmpl_obj, "description", None),
                        "scope": getattr(tmpl_obj, "scope", None),
                        "total_estimated_time_minutes": getattr(tmpl_obj, "total_estimated_time_minutes", None),
                        "version": getattr(tmpl_obj, "version", None),
                        "is_active": getattr(tmpl_obj, "is_active", None),
                    } if tmpl_obj else {"id": wrt.template_id, "name": "Unknown"},
                })

            results.append({
                "id": w.id,
                "name": w.name,
                "scope": w.scope,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "timezone": getattr(w, "timezone", None),
                "organization": {
                    "id": row.org_id,
                    "name": row.org_name,
                    "organization_type": row.org_type,
                },
                "role_templates": role_templates,
                "max_allowed_submissions": w.max_allowed_submissions,
                "allow_after_end_time": getattr(w, "allow_after_end_time", False),
                "allow_resubmission": w.allow_resubmission,
                "candidate_submission_count": row.submission_count,
                "status": status,
            })

        return results, total

    # ────────────────────────────────────────────────────────────
    # Gap 2: Candidate Submission History
    # ────────────────────────────────────────────────────────────

    def list_submissions_for_candidate(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
        status_filter: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        List past submissions for a candidate with joined window/org/role info.
        """
        candidate_id = self._resolve_candidate_id(user_id)
        base_q = (
            self._db.query(
                InterviewSubmissionModel,
                InterviewSubmissionWindowModel.id.label("window_id"),
                InterviewSubmissionWindowModel.name.label("window_name"),
                Organization.id.label("org_id"),
                Organization.name.label("org_name"),
                RoleModel.id.label("role_id"),
                RoleModel.name.label("role_name"),
                InterviewTemplateModel.id.label("template_id"),
                InterviewTemplateModel.name.label("template_name"),
            )
            .join(
                InterviewSubmissionWindowModel,
                InterviewSubmissionWindowModel.id == InterviewSubmissionModel.window_id,
            )
            .join(
                Organization,
                Organization.id == InterviewSubmissionWindowModel.organization_id,
            )
            .join(
                RoleModel,
                RoleModel.id == InterviewSubmissionModel.role_id,
            )
            .outerjoin(
                InterviewTemplateModel,
                InterviewTemplateModel.id == InterviewSubmissionModel.template_id,
            )
            .filter(InterviewSubmissionModel.candidate_id == candidate_id)
        )

        if status_filter:
            base_q = base_q.filter(InterviewSubmissionModel.status == status_filter)

        total = base_q.count()

        rows = (
            base_q
            .order_by(InterviewSubmissionModel.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        results = []
        for row in rows:
            sub = row[0]

            # Get latest interview result if exists
            result = (
                self._db.query(InterviewResultModel)
                .filter(
                    InterviewResultModel.interview_submission_id == sub.id,
                    InterviewResultModel.is_current == True,  # noqa: E712
                )
                .first()
            )

            results.append({
                "submission_id": sub.id,
                "window": {"id": row.window_id, "name": row.window_name},
                "organization": {"id": row.org_id, "name": row.org_name},
                "role": {"id": row.role_id, "name": row.role_name},
                "template": {"id": row.template_id, "name": row.template_name} if row.template_id else None,
                "status": sub.status,
                "submitted_at": sub.submitted_at,
                "started_at": sub.started_at,
                "final_score": float(sub.final_score) if sub.final_score else None,
                "result_status": result.result_status if result else None,
                "recommendation": result.recommendation if result else None,
                "mode": sub.mode,
            })

        return results, total

    # ────────────────────────────────────────────────────────────
    # Gap 3: Candidate Performance Statistics
    # ────────────────────────────────────────────────────────────

    def get_candidate_stats(self, user_id: int) -> Dict[str, Any]:
        """
        Calculate aggregate performance statistics for a candidate.
        """
        candidate_id = self._resolve_candidate_id(user_id)

        # Total interviews (completed/reviewed only)
        total_q = (
            self._db.query(func.count(InterviewSubmissionModel.id))
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewSubmissionModel.status.in_(["completed", "reviewed"]),
            )
            .scalar()
        ) or 0

        # Average final score
        avg_score = (
            self._db.query(func.avg(InterviewSubmissionModel.final_score))
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewSubmissionModel.status.in_(["completed", "reviewed"]),
                InterviewSubmissionModel.final_score.isnot(None),
            )
            .scalar()
        )

        # Pass rate from interview_results
        results_q = (
            self._db.query(InterviewResultModel)
            .join(
                InterviewSubmissionModel,
                InterviewSubmissionModel.id == InterviewResultModel.interview_submission_id,
            )
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewResultModel.is_current == True,  # noqa: E712
            )
            .all()
        )

        pass_count = sum(1 for r in results_q if r.result_status == "pass")
        total_results = len(results_q)
        pass_rate = (pass_count / total_results * 100) if total_results > 0 else None

        # Total practice time (sum of time between started_at and submitted_at)
        time_q = (
            self._db.query(
                func.sum(
                    func.extract(
                        "epoch",
                        InterviewSubmissionModel.submitted_at - InterviewSubmissionModel.started_at,
                    )
                )
            )
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewSubmissionModel.started_at.isnot(None),
                InterviewSubmissionModel.submitted_at.isnot(None),
            )
            .scalar()
        )
        total_time_minutes = int(time_q / 60) if time_q else 0

        # Score history — latest 12 submissions by submitted_at
        score_rows = (
            self._db.query(
                InterviewSubmissionModel.submitted_at,
                InterviewSubmissionModel.final_score,
            )
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewSubmissionModel.status.in_(["completed", "reviewed"]),
                InterviewSubmissionModel.final_score.isnot(None),
                InterviewSubmissionModel.submitted_at.isnot(None),
            )
            .order_by(InterviewSubmissionModel.submitted_at.asc())
            .limit(12)
            .all()
        )
        score_history = [
            {
                "date": row.submitted_at.strftime("%Y-%m"),
                "score": float(row.final_score),
            }
            for row in score_rows
        ]

        # Skill breakdown from section_scores in interview_results
        skill_map: Dict[str, List[float]] = {}
        for r in results_q:
            if r.section_scores and isinstance(r.section_scores, dict):
                for section, score_data in r.section_scores.items():
                    score_val = None
                    if isinstance(score_data, (int, float)):
                        score_val = float(score_data)
                    elif isinstance(score_data, dict) and "score" in score_data:
                        score_val = float(score_data["score"])
                    if score_val is not None:
                        skill_map.setdefault(section, []).append(score_val)

        skill_breakdown = [
            {"skill": skill, "score": round(sum(scores) / len(scores), 1)}
            for skill, scores in skill_map.items()
        ]

        # Derive strong areas (score >= 80) and improvement areas (score < 75)
        sorted_skills = sorted(skill_breakdown, key=lambda s: s["score"], reverse=True)
        strong_areas = [s["skill"] for s in sorted_skills if s["score"] >= 80][:5]
        improvement_areas = [s["skill"] for s in sorted_skills if s["score"] < 75][:5]

        return {
            "total_interviews": total_q,
            "average_score": round(float(avg_score), 1) if avg_score else None,
            "pass_rate": round(pass_rate, 1) if pass_rate is not None else None,
            "total_practice_time_minutes": total_time_minutes,
            "strong_areas": strong_areas,
            "improvement_areas": improvement_areas,
            "score_history": score_history,
            "skill_breakdown": skill_breakdown,
        }

    # ────────────────────────────────────────────────────────────
    # Gap 4: Profile
    # ────────────────────────────────────────────────────────────

    def get_candidate_profile(
        self, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get full candidate profile by user_id (from candidates + users)."""
        row = (
            self._db.query(Candidate, User)
            .join(User, User.id == Candidate.user_id)
            .filter(Candidate.user_id == user_id)
            .first()
        )
        if row is None:
            return None

        candidate, user = row
        meta = candidate.profile_metadata or {}

        return {
            "candidate_id": candidate.id,
            "full_name": user.name,
            "email": user.email,
            "phone": meta.get("phone"),
            "location": meta.get("location"),
            "bio": meta.get("bio"),
            "experience_years": meta.get("experience_years"),
            "cgpa": meta.get("cgpa"),
            "skills": meta.get("skills", []),
            "linkedin_url": meta.get("linkedin_url"),
            "github_url": meta.get("github_url"),
            "portfolio_url": meta.get("portfolio_url"),
            "education": meta.get("education", []),
            "work_experience": meta.get("work_experience", []),
            "plan": candidate.plan,
            "status": getattr(candidate, "status", None),
            "user_type": user.user_type,
            "last_login_at": getattr(user, "last_login_at", None),
            "created_at": candidate.created_at,
            "updated_at": getattr(candidate, "updated_at", None),
        }

    def update_candidate_profile(
        self,
        user_id: int,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Update candidate profile. Splits updates between users table and
        candidates.profile_metadata JSONB.
        """
        candidate = (
            self._db.query(Candidate)
            .filter(Candidate.user_id == user_id)
            .first()
        )
        if candidate is None:
            return None

        # Update name in users table if provided
        if "full_name" in updates and updates["full_name"] is not None:
            self._db.query(User).filter(User.id == user_id).update(
                {"name": updates["full_name"]},
                synchronize_session="fetch",
            )

        # Profile metadata fields
        meta_fields = [
            "phone", "location", "bio", "experience_years", "cgpa",
            "skills", "linkedin_url", "github_url", "portfolio_url",
            "education", "work_experience",
        ]
        existing_meta = candidate.profile_metadata or {}
        for field in meta_fields:
            if field in updates and updates[field] is not None:
                if field == "skills":
                    current_skills = existing_meta.get("skills") or []
                    incoming_skills = updates[field] or []
                    if not isinstance(current_skills, list):
                        current_skills = []
                    if not isinstance(incoming_skills, list):
                        incoming_skills = []

                    merged_skills = []
                    seen = set()
                    for skill in current_skills + incoming_skills:
                        if skill is None:
                            continue
                        normalized = str(skill).strip()
                        if not normalized:
                            continue
                        key = normalized.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        merged_skills.append(normalized)
                    existing_meta[field] = merged_skills
                else:
                    existing_meta[field] = updates[field]

        candidate.profile_metadata = existing_meta
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(candidate, "profile_metadata")

        self._db.flush()
        return self.get_candidate_profile(user_id)

    # ────────────────────────────────────────────────────────────
    # Candidate Settings
    # ────────────────────────────────────────────────────────────

    def get_candidate_settings(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get persistent settings for a candidate, creating defaults if needed."""
        candidate = (
            self._db.query(Candidate)
            .filter(Candidate.user_id == user_id)
            .first()
        )
        if candidate is None:
            return None

        try:
            settings = (
                self._db.query(CandidateSettings)
                .filter(CandidateSettings.candidate_id == candidate.id)
                .first()
            )
        except ProgrammingError as exc:
            message = str(exc).lower()
            if "candidate_settings" in message and "does not exist" in message:
                self._db.rollback()
                return self._default_candidate_settings(candidate.id)
            raise

        if settings is None:
            settings = CandidateSettings(
                candidate_id=candidate.id,
                notification_preferences={
                    "email": True,
                    "interview": True,
                    "reports": True,
                    "marketing": False,
                },
                privacy_preferences={
                    "profileVisible": True,
                    "shareResults": False,
                    "allowAnalytics": True,
                },
                ui_preferences={"theme": "system"},
            )
            self._db.add(settings)
            self._db.flush()

        return {
            "candidate_id": settings.candidate_id,
            "notification_preferences": settings.notification_preferences or {},
            "privacy_preferences": settings.privacy_preferences or {},
            "ui_preferences": settings.ui_preferences or {},
            "created_at": settings.created_at,
            "updated_at": settings.updated_at,
        }

    def update_candidate_settings(
        self,
        user_id: int,
        updates: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Create or update candidate settings."""
        candidate = (
            self._db.query(Candidate)
            .filter(Candidate.user_id == user_id)
            .first()
        )
        if candidate is None:
            return None

        try:
            settings = (
                self._db.query(CandidateSettings)
                .filter(CandidateSettings.candidate_id == candidate.id)
                .first()
            )
        except ProgrammingError as exc:
            message = str(exc).lower()
            if "candidate_settings" in message and "does not exist" in message:
                self._db.rollback()
                default_settings = self._default_candidate_settings(candidate.id)
                if updates.get("notification_preferences") is not None:
                    default_settings["notification_preferences"] = {
                        **default_settings["notification_preferences"],
                        **updates["notification_preferences"],
                    }
                if updates.get("privacy_preferences") is not None:
                    default_settings["privacy_preferences"] = {
                        **default_settings["privacy_preferences"],
                        **updates["privacy_preferences"],
                    }
                if updates.get("ui_preferences") is not None:
                    default_settings["ui_preferences"] = {
                        **default_settings["ui_preferences"],
                        **updates["ui_preferences"],
                    }
                return default_settings
            raise
        if settings is None:
            settings = CandidateSettings(candidate_id=candidate.id)
            self._db.add(settings)

        if updates.get("notification_preferences") is not None:
            existing = settings.notification_preferences or {}
            settings.notification_preferences = {**existing, **updates["notification_preferences"]}

        if updates.get("privacy_preferences") is not None:
            existing = settings.privacy_preferences or {}
            settings.privacy_preferences = {**existing, **updates["privacy_preferences"]}

        if updates.get("ui_preferences") is not None:
            existing = settings.ui_preferences or {}
            settings.ui_preferences = {**existing, **updates["ui_preferences"]}

        self._db.flush()
        return self.get_candidate_settings(user_id)

    @staticmethod
    def _default_candidate_settings(candidate_id: int) -> Dict[str, Any]:
        return {
            "candidate_id": candidate_id,
            "notification_preferences": {
                "email": True,
                "interview": True,
                "reports": True,
                "marketing": False,
            },
            "privacy_preferences": {
                "profileVisible": True,
                "shareResults": False,
                "allowAnalytics": True,
            },
            "ui_preferences": {"theme": "system"},
            "created_at": None,
            "updated_at": None,
        }

    # ────────────────────────────────────────────────────────────
    # Career Path
    # ────────────────────────────────────────────────────────────

    def get_latest_career_insight_run(
        self,
        user_id: int,
        industry: str,
        seniority: str,
    ) -> Optional[Dict[str, Any]]:
        candidate_id = self._resolve_candidate_id(user_id)

        row = (
            self._db.query(CandidateCareerInsightRun)
            .filter(
                CandidateCareerInsightRun.candidate_id == candidate_id,
                CandidateCareerInsightRun.industry == industry,
                CandidateCareerInsightRun.seniority == seniority,
            )
            .order_by(CandidateCareerInsightRun.created_at.desc())
            .first()
        )
        if row is None:
            return None

        return {
            "run_id": row.id,
            "candidate_id": row.candidate_id,
            "industry": row.industry,
            "seniority": row.seniority,
            "insights": row.insights or [],
            "generation_source": row.generation_source,
            "model_provider": row.model_provider,
            "model_name": row.model_name,
            "created_at": row.created_at,
        }

    def create_career_insight_run(
        self,
        user_id: int,
        industry: str,
        seniority: str,
        insights: List[Dict[str, Any]],
        generation_source: str,
        model_provider: Optional[str],
        model_name: Optional[str],
    ) -> Dict[str, Any]:
        candidate_id = self._resolve_candidate_id(user_id)

        row = CandidateCareerInsightRun(
            candidate_id=candidate_id,
            industry=industry,
            seniority=seniority,
            insights=insights,
            generation_source=generation_source,
            model_provider=model_provider,
            model_name=model_name,
        )
        self._db.add(row)
        self._db.flush()

        return {
            "run_id": row.id,
            "candidate_id": row.candidate_id,
            "industry": row.industry,
            "seniority": row.seniority,
            "insights": row.insights or [],
            "generation_source": row.generation_source,
            "model_provider": row.model_provider,
            "model_name": row.model_name,
            "created_at": row.created_at,
        }

    def create_active_career_roadmap(
        self,
        user_id: int,
        industry: str,
        target_role: str,
        steps: List[Dict[str, Any]],
        generation_source: str,
        model_provider: Optional[str],
        model_name: Optional[str],
        insight_run_id: Optional[int] = None,
        selected_insight: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        candidate_id = self._resolve_candidate_id(user_id)

        (
            self._db.query(CandidateCareerRoadmap)
            .filter(
                CandidateCareerRoadmap.candidate_id == candidate_id,
                CandidateCareerRoadmap.is_active == True,  # noqa: E712
            )
            .update({"is_active": False}, synchronize_session="fetch")
        )

        row = CandidateCareerRoadmap(
            candidate_id=candidate_id,
            insight_run_id=insight_run_id,
            industry=industry,
            target_role=target_role,
            selected_insight=selected_insight,
            steps=steps,
            completed_levels=[],
            current_level=1,
            is_active=True,
            generation_source=generation_source,
            model_provider=model_provider,
            model_name=model_name,
        )
        self._db.add(row)
        self._db.flush()

        return self._map_career_roadmap(row)

    def get_active_career_roadmap(self, user_id: int) -> Optional[Dict[str, Any]]:
        candidate_id = self._resolve_candidate_id(user_id)
        row = (
            self._db.query(CandidateCareerRoadmap)
            .filter(
                CandidateCareerRoadmap.candidate_id == candidate_id,
                CandidateCareerRoadmap.is_active == True,  # noqa: E712
            )
            .order_by(CandidateCareerRoadmap.updated_at.desc())
            .first()
        )
        if row is None:
            return None
        return self._map_career_roadmap(row)

    def list_career_roadmap_history(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        candidate_id = self._resolve_candidate_id(user_id)
        base_q = self._db.query(CandidateCareerRoadmap).filter(
            CandidateCareerRoadmap.candidate_id == candidate_id
        )

        total = base_q.count()
        rows = (
            base_q
            .order_by(CandidateCareerRoadmap.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return [self._map_career_roadmap(row) for row in rows], total

    def update_career_roadmap_progress(
        self,
        user_id: int,
        roadmap_id: int,
        completed_levels: List[int],
        current_level: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        candidate_id = self._resolve_candidate_id(user_id)
        row = (
            self._db.query(CandidateCareerRoadmap)
            .filter(
                CandidateCareerRoadmap.id == roadmap_id,
                CandidateCareerRoadmap.candidate_id == candidate_id,
            )
            .first()
        )
        if row is None:
            return None

        normalized_levels = sorted({int(level) for level in completed_levels if 1 <= int(level) <= 4})
        row.completed_levels = normalized_levels

        if current_level is not None:
            row.current_level = max(1, min(4, int(current_level)))
        elif normalized_levels:
            row.current_level = max(1, min(4, max(normalized_levels) + 1))
        else:
            row.current_level = 1

        self._db.flush()
        return self._map_career_roadmap(row)

    @staticmethod
    def _map_career_roadmap(row: CandidateCareerRoadmap) -> Dict[str, Any]:
        return {
            "roadmap_id": row.id,
            "candidate_id": row.candidate_id,
            "insight_run_id": row.insight_run_id,
            "industry": row.industry,
            "target_role": row.target_role,
            "selected_insight": row.selected_insight,
            "steps": row.steps or [],
            "completed_levels": row.completed_levels or [],
            "current_level": row.current_level or 1,
            "is_active": bool(row.is_active),
            "generation_source": row.generation_source,
            "model_provider": row.model_provider,
            "model_name": row.model_name,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _map_practice_deck(row: CandidatePracticeDeckRun) -> Dict[str, Any]:
        cards = row.flashcards or []
        return {
            "deck_id": row.id,
            "candidate_id": row.candidate_id,
            "role": row.role,
            "industry": row.industry,
            "question_type": row.question_type,
            "difficulty": row.difficulty,
            "card_count": len(cards),
            "source_question_ids": row.source_question_ids or [],
            "flashcards": cards,
            "bookmarked_indices": row.bookmarked_indices or [],
            "mastered_indices": row.mastered_indices or [],
            "current_card_index": row.current_card_index or 0,
            "progress_percent": row.progress_percent or 0,
            "is_active": bool(row.is_active),
            "generation_source": row.generation_source,
            "model_provider": row.model_provider,
            "model_name": row.model_name,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
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
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
        """
        List practice questions (coding problems + general questions).

        Returns (skills_summary, questions, total).
        """
        candidate_id = self._resolve_candidate_id(user_id)

        # Completed question/problem IDs for this candidate
        completed_question_ids = set(
            r[0]
            for r in self._db.query(InterviewExchangeModel.question_id)
            .join(
                InterviewSubmissionModel,
                InterviewSubmissionModel.id == InterviewExchangeModel.interview_submission_id,
            )
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewExchangeModel.question_id.isnot(None),
                InterviewExchangeModel.response_text.isnot(None),
            )
            .all()
        )
        completed_problem_ids = set(
            r[0]
            for r in self._db.query(InterviewExchangeModel.coding_problem_id)
            .join(
                InterviewSubmissionModel,
                InterviewSubmissionModel.id == InterviewExchangeModel.interview_submission_id,
            )
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewExchangeModel.coding_problem_id.isnot(None),
                InterviewExchangeModel.response_text.isnot(None),
            )
            .all()
        )

        # Build questions list from general questions
        q_query = (
            self._db.query(QuestionModel)
            .filter(
                QuestionModel.is_active == True,  # noqa: E712
                QuestionModel.scope.in_(["public", "organization"]),
            )
        )
        if skill:
            q_query = q_query.filter(QuestionModel.question_type == skill)
        if difficulty:
            q_query = q_query.filter(QuestionModel.difficulty == difficulty)
        if question_type and question_type != "coding":
            q_query = q_query.filter(QuestionModel.question_type == question_type)

        # Build coding problems list
        cp_query = (
            self._db.query(CodingProblemModel)
            .filter(
                CodingProblemModel.is_active == True,  # noqa: E712
                CodingProblemModel.scope.in_(["public", "organization"]),
            )
        )
        if difficulty:
            cp_query = cp_query.filter(CodingProblemModel.difficulty == difficulty)

        # Combine into unified list
        questions = []

        if question_type != "coding":
            for q in q_query.all():
                questions.append({
                    "id": q.id,
                    "title": q.question_text[:80],
                    "skill": q.question_type,
                    "difficulty": q.difficulty,
                    "type": q.question_type,
                    "estimated_time_minutes": getattr(q, "estimated_time_minutes", None),
                    "completed": q.id in completed_question_ids,
                })

        if not question_type or question_type == "coding":
            for cp in cp_query.all():
                questions.append({
                    "id": cp.id,
                    "title": cp.title,
                    "skill": "coding",
                    "difficulty": cp.difficulty,
                    "type": "coding",
                    "estimated_time_minutes": getattr(cp, "estimated_time_minutes", None),
                    "completed": cp.id in completed_problem_ids,
                })

        total = len(questions)

        # Skill summary
        skill_groups: Dict[str, Dict[str, int]] = {}
        for q in questions:
            s = q["skill"]
            if s not in skill_groups:
                skill_groups[s] = {"total": 0, "completed": 0}
            skill_groups[s]["total"] += 1
            if q["completed"]:
                skill_groups[s]["completed"] += 1

        skills_summary = [
            {
                "id": s,
                "name": s.replace("_", " ").title(),
                "question_count": counts["total"],
                "completed_count": counts["completed"],
            }
            for s, counts in skill_groups.items()
        ]

        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        paginated = questions[start:end]

        return skills_summary, paginated, total

    def get_practice_question_pool(
        self,
        user_id: int,
        *,
        question_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Return raw question rows for interview prep deck generation."""
        candidate_id = self._resolve_candidate_id(user_id)

        completed_question_ids = set(
            r[0]
            for r in self._db.query(InterviewExchangeModel.question_id)
            .join(
                InterviewSubmissionModel,
                InterviewSubmissionModel.id == InterviewExchangeModel.interview_submission_id,
            )
            .filter(
                InterviewSubmissionModel.candidate_id == candidate_id,
                InterviewExchangeModel.question_id.isnot(None),
                InterviewExchangeModel.response_text.isnot(None),
            )
            .all()
        )

        q_query = (
            self._db.query(QuestionModel)
            .filter(
                QuestionModel.is_active == True,  # noqa: E712
                QuestionModel.scope.in_(["public", "organization"]),
            )
        )
        if question_type:
            q_query = q_query.filter(QuestionModel.question_type == question_type)
        if difficulty:
            q_query = q_query.filter(QuestionModel.difficulty == difficulty)

        rows = (
            q_query
            .order_by(func.random())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": q.id,
                "question_text": q.question_text,
                "answer_text": q.answer_text,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "estimated_time_minutes": getattr(q, "estimated_time_minutes", None),
                "completed": q.id in completed_question_ids,
            }
            for q in rows
        ]

    def get_latest_submission_generation_context(self, user_id: int) -> Optional[Dict[str, int]]:
        """Return latest submission context required by question generation service."""
        candidate_id = self._resolve_candidate_id(user_id)
        row = (
            self._db.query(
                InterviewSubmissionModel.id.label("submission_id"),
                InterviewSubmissionWindowModel.organization_id.label("organization_id"),
            )
            .join(
                InterviewSubmissionWindowModel,
                InterviewSubmissionWindowModel.id == InterviewSubmissionModel.window_id,
            )
            .filter(InterviewSubmissionModel.candidate_id == candidate_id)
            .order_by(
                InterviewSubmissionModel.started_at.desc().nullslast(),
                InterviewSubmissionModel.id.desc(),
            )
            .first()
        )
        if row is None:
            return None

        return {
            "submission_id": int(row.submission_id),
            "organization_id": int(row.organization_id) if row.organization_id else 1,
        }

    def create_generated_practice_questions(
        self,
        *,
        organization_id: int,
        questions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Persist generated practice questions and return normalized pool rows."""
        if not questions:
            return []

        normalized_scope = "public" if int(organization_id) == 1 else "organization"
        normalized_org_id = None if int(organization_id) == 1 else int(organization_id)

        inserted: List[Dict[str, Any]] = []
        for item in questions:
            model = QuestionModel(
                question_text=item["question_text"],
                answer_text=item.get("answer_text"),
                question_type=item.get("question_type") or "technical",
                difficulty=item.get("difficulty") or "medium",
                scope=normalized_scope,
                organization_id=normalized_org_id,
                source_type=item.get("source_type") or "generated_practice_deck",
                estimated_time_minutes=item.get("estimated_time_minutes") or 5,
                is_active=True,
            )
            self._db.add(model)
            self._db.flush()
            inserted.append(
                {
                    "id": model.id,
                    "question_text": model.question_text,
                    "answer_text": model.answer_text,
                    "question_type": model.question_type,
                    "difficulty": model.difficulty,
                    "estimated_time_minutes": model.estimated_time_minutes,
                    "completed": False,
                }
            )

        return inserted

    def get_active_practice_deck(self, user_id: int) -> Optional[Dict[str, Any]]:
        candidate_id = self._resolve_candidate_id(user_id)
        row = (
            self._db.query(CandidatePracticeDeckRun)
            .filter(
                CandidatePracticeDeckRun.candidate_id == candidate_id,
                CandidatePracticeDeckRun.is_active == True,  # noqa: E712
            )
            .order_by(CandidatePracticeDeckRun.updated_at.desc())
            .first()
        )
        if row is None:
            return None
        return self._map_practice_deck(row)

    def get_practice_deck_by_id(self, user_id: int, deck_id: int) -> Optional[Dict[str, Any]]:
        candidate_id = self._resolve_candidate_id(user_id)
        row = (
            self._db.query(CandidatePracticeDeckRun)
            .filter(
                CandidatePracticeDeckRun.id == deck_id,
                CandidatePracticeDeckRun.candidate_id == candidate_id,
            )
            .first()
        )
        if row is None:
            return None
        return self._map_practice_deck(row)

    def list_practice_deck_history(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        candidate_id = self._resolve_candidate_id(user_id)
        base_q = (
            self._db.query(CandidatePracticeDeckRun)
            .filter(CandidatePracticeDeckRun.candidate_id == candidate_id)
        )
        total = base_q.count()
        rows = (
            base_q
            .order_by(CandidatePracticeDeckRun.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return [self._map_practice_deck(row) for row in rows], total

    def create_active_practice_deck(
        self,
        user_id: int,
        *,
        role: str,
        industry: str,
        question_type: Optional[str],
        difficulty: Optional[str],
        source_question_ids: List[int],
        flashcards: List[Dict[str, Any]],
        generation_source: str,
        model_provider: Optional[str],
        model_name: Optional[str],
    ) -> Dict[str, Any]:
        candidate_id = self._resolve_candidate_id(user_id)

        self._db.query(CandidatePracticeDeckRun).filter(
            CandidatePracticeDeckRun.candidate_id == candidate_id,
            CandidatePracticeDeckRun.is_active == True,  # noqa: E712
        ).update({"is_active": False}, synchronize_session=False)

        deck = CandidatePracticeDeckRun(
            candidate_id=candidate_id,
            role=role,
            industry=industry,
            question_type=question_type,
            difficulty=difficulty,
            source_question_ids=source_question_ids,
            flashcards=flashcards,
            bookmarked_indices=[],
            mastered_indices=[],
            current_card_index=0,
            progress_percent=0,
            is_active=True,
            generation_source=generation_source,
            model_provider=model_provider,
            model_name=model_name,
        )
        self._db.add(deck)
        self._db.flush()
        return self._map_practice_deck(deck)

    def update_practice_deck_progress(
        self,
        user_id: int,
        deck_id: int,
        *,
        current_card_index: int,
        mastered_indices: List[int],
        bookmarked_indices: List[int],
    ) -> Optional[Dict[str, Any]]:
        candidate_id = self._resolve_candidate_id(user_id)
        deck = (
            self._db.query(CandidatePracticeDeckRun)
            .filter(
                CandidatePracticeDeckRun.id == deck_id,
                CandidatePracticeDeckRun.candidate_id == candidate_id,
            )
            .first()
        )
        if deck is None:
            return None

        flashcards = deck.flashcards or []
        card_count = len(flashcards) if isinstance(flashcards, list) and flashcards else 0
        mastered_clean = sorted({int(i) for i in mastered_indices if int(i) >= 0})
        bookmarked_clean = sorted({int(i) for i in bookmarked_indices if int(i) >= 0})
        current_index = max(0, current_card_index)
        progress = int(round((len(mastered_clean) / card_count) * 100)) if card_count > 0 else 0

        deck.current_card_index = current_index
        deck.mastered_indices = mastered_clean
        deck.bookmarked_indices = bookmarked_clean
        deck.progress_percent = min(max(progress, 0), 100)
        deck.updated_at = datetime.now(timezone.utc)
        self._db.flush()
        return self._map_practice_deck(deck)

    # ────────────────────────────────────────────────────────────
    # Practice Templates (Interview Setup)
    # ────────────────────────────────────────────────────────────

    _TEMPLATE_CATEGORY_MAP: Dict[str, str] = {
        "DSA Fundamentals": "DSA",
        "System Design": "SYSTEM DESIGN",
        "Backend Engineering": "BACKEND",
        "Frontend Development": "FRONTEND",
        "Behavioral Interview": "BEHAVIORAL",
        "DevOps & Cloud": "DEVOPS",
    }

    def list_practice_templates(self) -> List[Dict[str, Any]]:
        """Return all active templates with parsed structure for the UI."""
        templates = (
            self._db.query(InterviewTemplateModel)
            .filter(
                InterviewTemplateModel.is_active == True,  # noqa: E712
                InterviewTemplateModel.id.in_([1, 2, 3, 4, 5, 6]),
            )
            .order_by(InterviewTemplateModel.id)
            .all()
        )

        result = []
        for t in templates:
            ts = t.template_structure or {}
            sections_raw = ts.get("sections") or {}
            topics_data = (sections_raw.get("topics_assessment") or {}).get("topics") or []
            coding_data = sections_raw.get("coding_round") or {}

            # Difficulty distribution from coding problems
            diff_dist: Dict[str, int] = {"easy": 0, "medium": 0, "hard": 0}
            for prob in coding_data.get("problems", []):
                d = prob.get("difficulty", "").lower()
                if d in diff_dist:
                    diff_dist[d] += 1

            sections = {
                "resume_analysis": sections_raw.get("resume_analysis", {}).get("enabled", False),
                "self_introduction": sections_raw.get("self_introduction", {}).get("enabled", False),
                "topics_assessment": sections_raw.get("topics_assessment", {}).get("enabled", False),
                "coding_round": coding_data.get("enabled", False),
                "complexity_analysis": sections_raw.get("complexity_analysis", {}).get("enabled", False),
                "behavioral": sections_raw.get("behavioral", {}).get("enabled", False),
            }

            category = self._TEMPLATE_CATEGORY_MAP.get(t.name, t.name.upper())

            result.append({
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "category": category,
                "total_estimated_time_minutes": t.total_estimated_time_minutes,
                "total_questions": ts.get("total_questions"),
                "target_level": ts.get("target_level"),
                "topics": [
                    {"topic_id": tp.get("topic_id", 0), "topic_name": tp.get("topic_name", ""), "weight": tp.get("weight")}
                    for tp in topics_data
                ],
                "sections": sections,
                "difficulty_distribution": diff_dist,
                "is_active": t.is_active,
            })

        return result

    # ────────────────────────────────────────────────────────────
    # Practice Submission Creation
    # ────────────────────────────────────────────────────────────

    def create_practice_submission(
        self,
        user_id: int,
        template_id: int,
        experience_level: str,
        target_company: Optional[str],
        voice_interview: bool,
        video_recording: bool,
        ai_proctoring: bool,
    ) -> Tuple[InterviewSubmissionModel, InterviewTemplateModel]:
        """
        Create a practice submission using the specified template.
        Returns (submission, template) for building the session summary.
        """
        candidate_id = self._resolve_candidate_id(user_id)

        # Validate template exists and is active
        template = (
            self._db.query(InterviewTemplateModel)
            .filter(
                InterviewTemplateModel.id == template_id,
                InterviewTemplateModel.is_active == True,  # noqa: E712
            )
            .first()
        )
        if template is None:
            raise ValueError(f"Template {template_id} not found or is inactive.")

        # Find the practice window
        practice_window = (
            self._db.query(InterviewSubmissionWindowModel)
            .filter(InterviewSubmissionWindowModel.name == "__practice__")
            .first()
        )
        if practice_window is None:
            raise ValueError(
                "Practice window not found. Run migration to create the __practice__ window."
            )

        # Find a role mapping for this template in the practice window
        mapping = (
            self._db.query(WindowRoleTemplateModel)
            .filter(
                WindowRoleTemplateModel.window_id == practice_window.id,
                WindowRoleTemplateModel.template_id == template_id,
            )
            .first()
        )

        if mapping is not None:
            role_id = mapping.role_id
        else:
            role = self._db.query(RoleModel).first()
            if not role:
                raise ValueError("No roles available for practice mode.")
            role_id = role.id

        # Build a proper TemplateSnapshot (required by the question sequencer
        # and WebSocket event handler). The practice config is stored as an
        # additional key (ignored by TemplateSnapshot validation).
        practice_config = {
            "experience_level": experience_level,
            "target_company": target_company,
            "voice_interview": voice_interview,
            "video_recording": video_recording,
            "ai_proctoring": ai_proctoring,
            "practice_mode": True,
        }

        snapshot = self._build_practice_snapshot(template, practice_config)

        # Validation: Ensure template has at least one question
        if snapshot.get("total_questions", 0) == 0:
            raise ValueError(
                f"Cannot start practice session: Template '{template.name}' has no available questions. "
                "Please ensure the database has active questions for the configured sections, or try a different template."
            )

        submission = InterviewSubmissionModel(
            candidate_id=candidate_id,
            window_id=practice_window.id,
            role_id=role_id,
            template_id=template_id,
            mode="async",
            status="in_progress",
            consent_captured=True,
            started_at=datetime.now(timezone.utc),
            template_structure_snapshot=snapshot,
        )
        self._db.add(submission)
        self._db.flush()

        return submission, template

    def _build_practice_snapshot(
        self,
        template: InterviewTemplateModel,
        practice_config: dict,
    ) -> dict:
        """
        Build a dict that validates as ``TemplateSnapshot`` from a template's
        structure JSONB, by querying and freezing actual question/problem IDs.

        The ``practice_config`` is stored under an extra key so it is
        available for display purposes; it is silently ignored by the
        Pydantic TemplateSnapshot validator.

        Sections resolved:
        - ``topics_assessment`` → questions table (by topic_id join)
        - ``coding_round``      → coding_problems table (by difficulty)
        - ``behavioral``        → questions table (question_type='behavioral')
        - AI-driven sections (resume_analysis, self_introduction,
          complexity_analysis) are skipped because they have no static
          question pool.

        Raises:
            ValueError: If the template yields no questions at all.
        """
        ts = template.template_structure or {}

        # Handle both "sections wrapper" and flat template_structure formats
        if "sections" in ts and isinstance(ts["sections"], dict):
            sections_raw: dict = ts["sections"]
        else:
            # Flat format – the structure IS the sections dict
            _non_section = {"scoring", "rules", "difficulty_adaptation",
                            "total_questions", "interview_structure",
                            "template_metadata", "section_sequence"}
            sections_raw = {k: v for k, v in ts.items()
                            if k not in _non_section and isinstance(v, dict)}

        # Determine processing order
        section_sequence: list = (
            ts.get("interview_structure", {}).get("section_sequence")
            or list(sections_raw.keys())
        )

        # AI-driven sections that have no static question pool
        # (coding_round is skipped until fully implemented in realtime flow)
        _ai_driven = {"resume_analysis", "complexity_analysis", "coding_round"}

        snapshot_sections: List[Dict[str, Any]] = []

        # Always attempt self-introduction first when enabled
        self_intro_cfg = sections_raw.get("self_introduction") or {}
        if self_intro_cfg.get("enabled", False):
            self_intro_ids = self._sample_self_introduction_question_ids(
                count=self_intro_cfg.get("question_count") or 1
            )
            if self_intro_ids:
                snapshot_sections.append({
                    "section_name": "self_introduction",
                    "question_count": len(self_intro_ids),
                    "question_ids": self_intro_ids,
                })

        for key in section_sequence:
            cfg = sections_raw.get(key)
            if not cfg or not cfg.get("enabled", False):
                continue
            if key == "self_introduction":
                continue
            if key in _ai_driven:
                continue

            if key == "coding_round":
                ids = self._sample_coding_problem_ids(cfg)
                if ids:
                    snapshot_sections.append({
                        "section_name": "coding",
                        "question_count": len(ids),
                        "question_ids": ids,
                    })

            elif key == "topics_assessment":
                ids = self._sample_topic_question_ids(cfg)
                if ids:
                    snapshot_sections.append({
                        "section_name": "topics_assessment",
                        "question_count": len(ids),
                        "question_ids": ids,
                    })

            elif key == "behavioral":
                count = cfg.get("question_count") or 3
                ids = self._sample_questions_by_type("behavioral", count)
                if ids:
                    snapshot_sections.append({
                        "section_name": "behavioral",
                        "question_count": len(ids),
                        "question_ids": ids,
                    })

            # Other unknown section keys: attempt generic technical questions
            else:
                count = cfg.get("question_count") or cfg.get("total_questions") or 0
                if count > 0:
                    ids = self._sample_questions_by_type("technical", count)
                    if ids:
                        snapshot_sections.append({
                            "section_name": key,
                            "question_count": len(ids),
                            "question_ids": ids,
                        })

        total_questions = sum(s["question_count"] for s in snapshot_sections)

        return {
            "template_id": template.id,
            "template_name": template.name,
            "total_questions": total_questions,
            "sections": snapshot_sections,
            # Extra key — ignored by TemplateSnapshot, kept for auditing
            "practice_config": practice_config,
        }

    def _sample_coding_problem_ids(self, cfg: dict) -> List[int]:
        """Randomly sample ``total_problems`` IDs from coding_problems."""
        count = cfg.get("total_problems") or 1
        difficulty = cfg.get("difficulty")

        sql = (
            "SELECT id FROM coding_problems "
            "WHERE is_active = true "
            "AND pipeline_status = 'imported' "
            + ("AND difficulty = :diff " if difficulty else "")
            + "ORDER BY RANDOM() LIMIT :n"
        )
        params: Dict[str, Any] = {"n": count}
        if difficulty:
            params["diff"] = difficulty

        rows = self._db.execute(text(sql), params).fetchall()

        # Fallback: if 'imported' filter yields nothing, try without it
        if not rows:
            sql_fb = (
                "SELECT id FROM coding_problems WHERE is_active = true "
                + ("AND difficulty = :diff " if difficulty else "")
                + "ORDER BY RANDOM() LIMIT :n"
            )
            rows = self._db.execute(text(sql_fb), params).fetchall()

        return [r[0] for r in rows]

    def _sample_topic_question_ids(self, cfg: dict) -> List[int]:
        """
        Randomly sample up to ``total_questions`` question IDs for a
        topics_assessment section, filtered by the configured topic IDs.
        """
        total = cfg.get("total_questions") or 0
        if total <= 0:
            return []

        topics = cfg.get("topics") or []
        topic_ids = [t["topic_id"] for t in topics if "topic_id" in t]

        if topic_ids:
            placeholders = ", ".join(f":t{i}" for i in range(len(topic_ids)))
            params: Dict[str, Any] = {"n": total}
            for i, tid in enumerate(topic_ids):
                params[f"t{i}"] = tid
            rows = self._db.execute(
                text(
                    "SELECT q.id FROM questions q "
                    "JOIN question_topics qt ON q.id = qt.question_id "
                    f"WHERE qt.topic_id IN ({placeholders}) "
                    "AND q.is_active = true "
                    "GROUP BY q.id "
                    "ORDER BY RANDOM() LIMIT :n"
                ),
                params,
            ).fetchall()
        else:
            rows = self._db.execute(
                text(
                    "SELECT id FROM questions WHERE is_active = true "
                    "ORDER BY RANDOM() LIMIT :n"
                ),
                {"n": total},
            ).fetchall()

        return [r[0] for r in rows]

    def _sample_questions_by_type(self, question_type: str, count: int) -> List[int]:
        """Randomly sample ``count`` question IDs matching ``question_type``."""
        rows = self._db.execute(
            text(
                "SELECT id FROM questions "
                "WHERE question_type = :qtype AND is_active = true "
                "AND COALESCE(source_type, '') <> 'self_intro_preset' "
                "ORDER BY RANDOM() LIMIT :n"
            ),
            {"qtype": question_type, "n": count},
        ).fetchall()
        return [r[0] for r in rows]

    def _sample_self_introduction_question_ids(self, count: int = 1) -> List[int]:
        """Sample self-introduction preset questions from DB-maintained pool."""
        if count <= 0:
            return []

        rows = self._db.execute(
            text(
                "SELECT id FROM questions "
                "WHERE question_type = 'behavioral' "
                "AND is_active = true "
                "AND source_type = 'self_intro_preset' "
                "ORDER BY RANDOM() LIMIT :n"
            ),
            {"n": count},
        ).fetchall()

        if rows:
            return [r[0] for r in rows]

        # Fallback for environments where preset seed migration has not run yet
        fallback = self._db.execute(
            text(
                "SELECT id FROM questions "
                "WHERE question_type = 'behavioral' AND is_active = true "
                "ORDER BY RANDOM() LIMIT :n"
            ),
            {"n": count},
        ).fetchall()
        return [r[0] for r in fallback]

    # ────────────────────────────────────────────────────────────
    # Submission Detail (full nested view)
    # ────────────────────────────────────────────────────────────

    def get_submission_detail(
        self,
        user_id: int,
        submission_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch a single submission with all nested data:
        window (+org), role, template, result, exchanges
        (+evaluations +dimension_scores +audio_analytics +code_submissions),
        and proctoring events.

        Returns None if the submission doesn't exist or doesn't belong
        to the candidate.
        """
        candidate_id = self._resolve_candidate_id(user_id)

        sub = (
            self._db.query(InterviewSubmissionModel)
            .filter(
                InterviewSubmissionModel.id == submission_id,
                InterviewSubmissionModel.candidate_id == candidate_id,
            )
            .first()
        )
        if sub is None:
            return None

        # --- Window + Organization ---
        window_dict = None
        win = (
            self._db.query(InterviewSubmissionWindowModel)
            .filter(InterviewSubmissionWindowModel.id == sub.window_id)
            .first()
        )
        if win:
            org = (
                self._db.query(Organization)
                .filter(Organization.id == win.organization_id)
                .first()
            )
            window_dict = {
                "id": win.id,
                "organization_id": win.organization_id,
                "admin_id": getattr(win, "admin_id", None),
                "name": win.name,
                "scope": win.scope,
                "start_time": self._iso(win.start_time),
                "end_time": self._iso(win.end_time),
                "timezone": getattr(win, "timezone", None),
                "max_allowed_submissions": win.max_allowed_submissions,
                "allow_after_end_time": getattr(win, "allow_after_end_time", False),
                "allow_resubmission": win.allow_resubmission,
                "organization": {
                    "id": org.id,
                    "name": org.name,
                    "organization_type": getattr(org, "organization_type", None),
                    "plan": getattr(org, "plan", None),
                    "domain": getattr(org, "domain", None),
                    "status": getattr(org, "status", None),
                } if org else None,
            }

        # --- Role ---
        role_dict = None
        role = self._db.query(RoleModel).filter(RoleModel.id == sub.role_id).first()
        if role:
            role_dict = {
                "id": role.id,
                "name": role.name,
                "description": getattr(role, "description", None),
                "scope": getattr(role, "scope", None),
            }

        # --- Template ---
        template_dict = None
        tmpl = self._db.query(InterviewTemplateModel).filter(InterviewTemplateModel.id == sub.template_id).first()
        if tmpl:
            template_dict = {
                "id": tmpl.id,
                "name": tmpl.name,
                "description": getattr(tmpl, "description", None),
                "scope": getattr(tmpl, "scope", None),
                "total_estimated_time_minutes": getattr(tmpl, "total_estimated_time_minutes", None),
                "version": getattr(tmpl, "version", None),
                "is_active": getattr(tmpl, "is_active", None),
            }

        # --- Result ---
        result_dict = None
        result = (
            self._db.query(InterviewResultModel)
            .filter(
                InterviewResultModel.interview_submission_id == sub.id,
                InterviewResultModel.is_current == True,  # noqa: E712
            )
            .first()
        )
        if result:
            result_dict = {
                "id": result.id,
                "interview_submission_id": result.interview_submission_id,
                "final_score": float(result.final_score) if result.final_score else None,
                "normalized_score": float(result.normalized_score) if result.normalized_score else None,
                "result_status": result.result_status,
                "recommendation": result.recommendation,
                "section_scores": result.section_scores,
                "strengths": result.strengths,
                "weaknesses": result.weaknesses,
                "summary_notes": result.summary_notes,
                "generated_by": result.generated_by,
                "is_current": result.is_current,
                "computed_at": self._iso(getattr(result, "computed_at", None)),
                "created_at": self._iso(result.created_at),
            }

        # --- Exchanges ---
        exchange_rows = (
            self._db.query(InterviewExchangeModel)
            .filter(InterviewExchangeModel.interview_submission_id == sub.id)
            .order_by(InterviewExchangeModel.sequence_order.asc())
            .all()
        )
        exchanges = []
        for ex in exchange_rows:
            # Evaluation for this exchange
            eval_dict = None
            evaluation = (
                self._db.query(EvaluationModel)
                .filter(
                    EvaluationModel.interview_exchange_id == ex.id,
                    EvaluationModel.is_final == True,  # noqa: E712
                )
                .first()
            )
            if evaluation:
                dim_rows = (
                    self._db.query(
                        EvaluationDimensionScoreModel,
                        RubricDimensionModel.dimension_name,
                    )
                    .outerjoin(
                        RubricDimensionModel,
                        RubricDimensionModel.id == EvaluationDimensionScoreModel.rubric_dimension_id,
                    )
                    .filter(EvaluationDimensionScoreModel.evaluation_id == evaluation.id)
                    .all()
                )
                eval_dict = {
                    "id": evaluation.id,
                    "interview_exchange_id": evaluation.interview_exchange_id,
                    "evaluator_type": evaluation.evaluator_type,
                    "total_score": float(evaluation.total_score) if evaluation.total_score else None,
                    "is_final": evaluation.is_final,
                    "evaluated_at": self._iso(evaluation.evaluated_at),
                    "created_at": self._iso(evaluation.created_at),
                    "dimension_scores": [
                        {
                            "id": ds.id,
                            "evaluation_id": ds.evaluation_id,
                            "rubric_dimension_id": ds.rubric_dimension_id,
                            "score": float(ds.score) if ds.score else 0,
                            "dimension_name": dim_name or "",
                            "created_at": self._iso(ds.created_at),
                        }
                        for ds, dim_name in dim_rows
                    ],
                }

            # Audio analytics
            audio_dict = None
            audio = (
                self._db.query(AudioAnalyticsModel)
                .filter(AudioAnalyticsModel.interview_exchange_id == ex.id)
                .first()
            )
            if audio:
                audio_dict = {
                    "id": audio.id,
                    "interview_exchange_id": audio.interview_exchange_id,
                    "transcript": audio.transcript,
                    "confidence_score": float(audio.confidence_score) if audio.confidence_score else None,
                    "speech_rate_wpm": audio.speech_rate_wpm,
                    "filler_word_count": audio.filler_word_count,
                    "sentiment_score": float(audio.sentiment_score) if audio.sentiment_score else None,
                    "created_at": self._iso(audio.created_at),
                }

            # Code submission
            code_dict = None
            code_sub = (
                self._db.query(CodeSubmissionModel)
                .filter(CodeSubmissionModel.interview_exchange_id == ex.id)
                .first()
            )
            if code_sub:
                exec_results = (
                    self._db.query(CodeExecutionResultModel)
                    .filter(CodeExecutionResultModel.code_submission_id == code_sub.id)
                    .all()
                )
                code_dict = {
                    "id": code_sub.id,
                    "interview_exchange_id": code_sub.interview_exchange_id,
                    "coding_problem_id": code_sub.coding_problem_id,
                    "language": code_sub.language,
                    "source_code": code_sub.source_code,
                    "execution_status": code_sub.execution_status,
                    "score": float(code_sub.score) if code_sub.score else None,
                    "execution_time_ms": code_sub.execution_time_ms,
                    "memory_kb": code_sub.memory_kb,
                    "submitted_at": self._iso(code_sub.submitted_at),
                    "created_at": self._iso(code_sub.created_at),
                    "execution_results": [
                        {
                            "id": er.id,
                            "code_submission_id": er.code_submission_id,
                            "test_case_id": er.test_case_id,
                            "passed": er.passed,
                            "actual_output": er.actual_output,
                            "runtime_ms": er.runtime_ms,
                            "memory_kb": er.memory_kb,
                            "exit_code": er.exit_code,
                            "created_at": self._iso(er.created_at),
                        }
                        for er in exec_results
                    ],
                }

            exchanges.append({
                "id": ex.id,
                "interview_submission_id": ex.interview_submission_id,
                "sequence_order": ex.sequence_order,
                "question_text": ex.question_text,
                "difficulty_at_time": ex.difficulty_at_time,
                "coding_problem_id": getattr(ex, "coding_problem_id", None),
                "response_text": ex.response_text,
                "response_code": getattr(ex, "response_code", None),
                "response_time_ms": ex.response_time_ms,
                "created_at": self._iso(ex.created_at),
                "evaluation": eval_dict,
                "audio_analytics": audio_dict,
                "code_submission": code_dict,
            })

        # --- Proctoring events ---
        proctor_rows = (
            self._db.query(ProctoringEventModel)
            .filter(ProctoringEventModel.interview_submission_id == sub.id)
            .order_by(ProctoringEventModel.occurred_at.asc())
            .all()
        )
        proctoring_events = [
            {
                "id": pe.id,
                "interview_submission_id": pe.interview_submission_id,
                "event_type": pe.event_type,
                "severity": pe.severity,
                "risk_weight": float(pe.risk_weight) if pe.risk_weight else None,
                "occurred_at": self._iso(pe.occurred_at),
                "created_at": self._iso(pe.created_at),
            }
            for pe in proctor_rows
        ]

        return {
            "id": sub.id,
            "candidate_id": sub.candidate_id,
            "window_id": sub.window_id,
            "role_id": sub.role_id,
            "template_id": sub.template_id,
            "mode": sub.mode,
            "status": sub.status,
            "final_score": float(sub.final_score) if sub.final_score else None,
            "consent_captured": sub.consent_captured,
            "started_at": self._iso(sub.started_at),
            "submitted_at": self._iso(sub.submitted_at),
            "created_at": self._iso(sub.created_at),
            "updated_at": self._iso(getattr(sub, "updated_at", None)),
            "window": window_dict,
            "role": role_dict,
            "template": template_dict,
            "result": result_dict,
            "exchanges": exchanges,
            "proctoring_events": proctoring_events,
        }

    # ────────────────────────────────────────────────────────────
    # Resumes
    # ────────────────────────────────────────────────────────────

    def get_candidate_resumes(self, user_id: int) -> List[Dict[str, Any]]:
        """Fetch resumes for a candidate via raw SQL (no ORM model)."""
        candidate_id = self._resolve_candidate_id(user_id)
        rows = self._db.execute(
            text(
                "SELECT id, candidate_id, file_url, file_name, parsed_text, extracted_data, "
                "structured_json, llm_feedback, ats_score, ats_feedback, embeddings, "
                "parse_status, llm_analysis_status, embeddings_status, parse_error, llm_error, "
                "embeddings_error, analyzed_at, uploaded_at, created_at, updated_at "
                "FROM resumes WHERE candidate_id = :cid "
                "ORDER BY created_at DESC"
            ),
            {"cid": candidate_id},
        ).fetchall()

        return [
            self._resume_row_to_dict(r)
            for r in rows
        ]

    def create_resume(self, user_id: int, file_url: str, file_name: Optional[str] = None) -> Dict[str, Any]:
        """Insert a new resume row and return it."""
        candidate_id = self._resolve_candidate_id(user_id)
        now = datetime.now(timezone.utc)
        row = self._db.execute(
            text(
                "INSERT INTO resumes (candidate_id, file_url, file_name, uploaded_at, created_at) "
                "VALUES (:cid, :url, :file_name, :now, :now) "
                "RETURNING id, candidate_id, file_url, file_name, parsed_text, extracted_data, "
                "structured_json, llm_feedback, ats_score, ats_feedback, embeddings, "
                "parse_status, llm_analysis_status, embeddings_status, parse_error, llm_error, "
                "embeddings_error, analyzed_at, uploaded_at, created_at, updated_at"
            ),
            {"cid": candidate_id, "url": file_url, "file_name": file_name, "now": now},
        ).fetchone()
        return self._resume_row_to_dict(row)

    def update_resume_analysis(
        self,
        user_id: int,
        resume_id: int,
        parsed_text: Optional[str],
        extracted_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Persist parsed resume text + extraction payload for a candidate-owned resume."""
        candidate_id = self._resolve_candidate_id(user_id)
        row = self._db.execute(
            text(
                "UPDATE resumes "
                "SET parsed_text = :parsed_text, extracted_data = CAST(:extracted_data AS JSONB), "
                "    parse_status = :parse_status, parse_error = :parse_error, updated_at = :now "
                "WHERE id = :resume_id AND candidate_id = :candidate_id "
                "RETURNING id, candidate_id, file_url, file_name, parsed_text, extracted_data, "
                "structured_json, llm_feedback, ats_score, ats_feedback, embeddings, "
                "parse_status, llm_analysis_status, embeddings_status, parse_error, llm_error, "
                "embeddings_error, analyzed_at, uploaded_at, created_at, updated_at"
            ),
            {
                "parsed_text": parsed_text,
                "extracted_data": json.dumps(extracted_data or {}),
                "parse_status": extracted_data.get("parse_status", "success") if extracted_data else "success",
                "parse_error": extracted_data.get("error") if extracted_data else None,
                "now": datetime.now(timezone.utc),
                "resume_id": resume_id,
                "candidate_id": candidate_id,
            },
        ).fetchone()

        if row is None:
            raise NotFoundError(resource_type="Resume", resource_id=resume_id)

        return self._resume_row_to_dict(row)

    def update_resume_llm_analysis(
        self,
        user_id: int,
        resume_id: int,
        structured_json: Optional[Dict[str, Any]],
        llm_feedback: Optional[Dict[str, Any]],
        ats_score: Optional[int],
        ats_feedback: Optional[str],
    ) -> Dict[str, Any]:
        """Update resume with LLM analysis results."""
        candidate_id = self._resolve_candidate_id(user_id)
        now = datetime.now(timezone.utc)
        row = self._db.execute(
            text(
                "UPDATE resumes "
                "SET structured_json = CAST(:structured_json AS JSONB), "
                "    llm_feedback = CAST(:llm_feedback AS JSONB), "
                "    ats_score = :ats_score, "
                "    ats_feedback = :ats_feedback, "
                "    llm_analysis_status = :llm_status, "
                "    llm_error = :llm_error, "
                "    analyzed_at = :analyzed_at, "
                "    updated_at = :now "
                "WHERE id = :resume_id AND candidate_id = :candidate_id "
                "RETURNING id, candidate_id, file_url, file_name, parsed_text, extracted_data, "
                "structured_json, llm_feedback, ats_score, ats_feedback, embeddings, "
                "parse_status, llm_analysis_status, embeddings_status, parse_error, llm_error, "
                "embeddings_error, analyzed_at, uploaded_at, created_at, updated_at"
            ),
            {
                "structured_json": json.dumps(structured_json or {}),
                "llm_feedback": json.dumps(llm_feedback or {}),
                "ats_score": ats_score,
                "ats_feedback": ats_feedback,
                "llm_status": "success" if ats_score is not None else "failed",
                "llm_error": None if ats_score is not None else "LLM analysis failed",
                "analyzed_at": now,
                "now": now,
                "resume_id": resume_id,
                "candidate_id": candidate_id,
            },
        ).fetchone()

        if row is None:
            raise NotFoundError(resource_type="Resume", resource_id=resume_id)

        return self._resume_row_to_dict(row)

    def update_resume_embeddings(
        self,
        user_id: int,
        resume_id: int,
        embeddings: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Update resume with embeddings data."""
        candidate_id = self._resolve_candidate_id(user_id)
        now = datetime.now(timezone.utc)
        row = self._db.execute(
            text(
                "UPDATE resumes "
                "SET embeddings = CAST(:embeddings AS JSONB), "
                "    embeddings_status = :emb_status, "
                "    embeddings_error = :emb_error, "
                "    updated_at = :now "
                "WHERE id = :resume_id AND candidate_id = :candidate_id "
                "RETURNING id, candidate_id, file_url, file_name, parsed_text, extracted_data, "
                "structured_json, llm_feedback, ats_score, ats_feedback, embeddings, "
                "parse_status, llm_analysis_status, embeddings_status, parse_error, llm_error, "
                "embeddings_error, analyzed_at, uploaded_at, created_at, updated_at"
            ),
            {
                "embeddings": json.dumps(embeddings or {}),
                "emb_status": "success" if embeddings else "failed",
                "emb_error": None if embeddings else "Embedding generation failed",
                "now": now,
                "resume_id": resume_id,
                "candidate_id": candidate_id,
            },
        ).fetchone()

        if row is None:
            raise NotFoundError(resource_type="Resume", resource_id=resume_id)

        return self._resume_row_to_dict(row)


    # ────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _iso(dt) -> Optional[str]:
        """Format datetime to ISO-8601 string or None."""
        if dt is None:
            return None
        return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)

    def _resume_row_to_dict(self, row) -> Dict[str, Any]:
        """Normalize a resume row to the API response shape using extracted_data as the source of analysis fields."""
        extracted_data = row[5] if len(row) > 5 else None
        if isinstance(extracted_data, str):
            try:
                extracted_data = json.loads(extracted_data)
            except Exception:
                extracted_data = {}
        extracted_data = extracted_data or {}

        return {
            "id": row[0],
            "candidate_id": row[1],
            "file_url": row[2],
            "file_name": row[3],
            "parsed_text": row[4],
            "extracted_data": extracted_data,
            "structured_json": row[6],
            "llm_feedback": row[7],
            "ats_score": row[8],
            "ats_feedback": row[9],
            "parse_status": row[11],
            "llm_analysis_status": row[12],
            "parse_error": row[14],
            "llm_error": row[15],
            "embeddings_error": row[16],
            "analyzed_at": self._iso(row[17]),
            "uploaded_at": self._iso(row[18]),
            "created_at": self._iso(row[19]),
            "updated_at": self._iso(row[20]),
        }
