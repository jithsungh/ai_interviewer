"""
Candidate Repository

Data access layer for candidate-facing queries.
Handles window listing, submission history, stats aggregation,
profile retrieval, and practice question lookups.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import case, func, text
from sqlalchemy.orm import Session

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
from app.auth.persistence.models import Candidate, Organization, User
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
                existing_meta[field] = updates[field]

        candidate.profile_metadata = existing_meta
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(candidate, "profile_metadata")

        self._db.flush()
        return self.get_candidate_profile(user_id)

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
        # Also includes coding_round which is disabled until fully implemented
        _ai_driven = {"resume_analysis", "self_introduction", "complexity_analysis", "coding_round"}

        snapshot_sections: List[Dict[str, Any]] = []

        for key in section_sequence:
            cfg = sections_raw.get(key)
            if not cfg or not cfg.get("enabled", False):
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
                "ORDER BY RANDOM() LIMIT :n"
            ),
            {"qtype": question_type, "n": count},
        ).fetchall()
        return [r[0] for r in rows]

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
                "SELECT id, candidate_id, file_url, parsed_text, "
                "extracted_data, uploaded_at, created_at "
                "FROM resumes WHERE candidate_id = :cid "
                "ORDER BY created_at DESC"
            ),
            {"cid": candidate_id},
        ).fetchall()

        return [
            {
                "id": r[0],
                "candidate_id": r[1],
                "file_url": r[2],
                "parsed_text": r[3],
                "extracted_data": r[4],
                "uploaded_at": self._iso(r[5]),
                "created_at": self._iso(r[6]),
            }
            for r in rows
        ]

    def create_resume(self, user_id: int, file_url: str) -> Dict[str, Any]:
        """Insert a new resume row and return it."""
        candidate_id = self._resolve_candidate_id(user_id)
        now = datetime.now(timezone.utc)
        row = self._db.execute(
            text(
                "INSERT INTO resumes (candidate_id, file_url, uploaded_at, created_at) "
                "VALUES (:cid, :url, :now, :now) "
                "RETURNING id, candidate_id, file_url, uploaded_at, created_at"
            ),
            {"cid": candidate_id, "url": file_url, "now": now},
        ).fetchone()
        return {
            "id": row[0],
            "candidate_id": row[1],
            "file_url": row[2],
            "uploaded_at": self._iso(row[3]),
            "created_at": self._iso(row[4]),
        }

    # ────────────────────────────────────────────────────────────
    # Helpers
    # ────────────────────────────────────────────────────────────

    @staticmethod
    def _iso(dt) -> Optional[str]:
        """Format datetime to ISO-8601 string or None."""
        if dt is None:
            return None
        return dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
