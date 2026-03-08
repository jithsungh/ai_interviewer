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
    QuestionModel,
    RoleModel,
    TopicModel,
    WindowRoleTemplateModel,
)
from app.auth.persistence.models import Candidate, Organization, User
from app.evaluation.persistence.models import InterviewResultModel
from app.interview.session.persistence.models import (
    InterviewExchangeModel,
    InterviewSubmissionModel,
)
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

        # Base query: windows visible to candidate
        base_q = (
            self._db.query(
                InterviewSubmissionWindowModel,
                Organization.id.label("org_id"),
                Organization.name.label("org_name"),
                RoleModel.id.label("role_id"),
                RoleModel.name.label("role_name"),
                func.coalesce(sub_count.c.submission_count, 0).label("submission_count"),
            )
            .join(
                Organization,
                Organization.id == InterviewSubmissionWindowModel.organization_id,
            )
            .join(
                WindowRoleTemplateModel,
                WindowRoleTemplateModel.window_id == InterviewSubmissionWindowModel.id,
            )
            .join(
                RoleModel,
                RoleModel.id == WindowRoleTemplateModel.role_id,
            )
            .outerjoin(
                sub_count,
                sub_count.c.window_id == InterviewSubmissionWindowModel.id,
            )
            .filter(
                # Global windows visible to all, or windows with existing submissions
                (InterviewSubmissionWindowModel.scope == "global")
                | (func.coalesce(sub_count.c.submission_count, 0) > 0)
            )
        )

        total = base_q.distinct(InterviewSubmissionWindowModel.id).count()

        rows = (
            base_q
            .order_by(InterviewSubmissionWindowModel.start_time.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        results = []
        seen_windows = set()
        for row in rows:
            w = row[0]
            if w.id in seen_windows:
                continue
            seen_windows.add(w.id)

            # Compute status
            if now < w.start_time:
                status = "upcoming"
            elif now > w.end_time:
                status = "closed"
            else:
                status = "open"

            # Duration in minutes from time range
            delta = w.end_time - w.start_time
            duration_minutes = int(delta.total_seconds() / 60) if delta else None

            results.append({
                "id": w.id,
                "name": w.name,
                "scope": w.scope,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "organization": {"id": row.org_id, "name": row.org_name},
                "role": {"id": row.role_id, "name": row.role_name},
                "duration_minutes": duration_minutes,
                "max_allowed_submissions": w.max_allowed_submissions,
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
                "status": sub.status,
                "submitted_at": sub.submitted_at,
                "started_at": sub.started_at,
                "final_score": float(sub.final_score) if sub.final_score else None,
                "result_status": result.result_status if result else None,
                "recommendation": result.recommendation if result else None,
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
                "date": row.submitted_at.strftime("%b %Y"),
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

        return {
            "total_interviews": total_q,
            "average_score": round(float(avg_score), 1) if avg_score else None,
            "pass_rate": round(pass_rate, 1) if pass_rate is not None else None,
            "total_practice_time_minutes": total_time_minutes,
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
            "created_at": candidate.created_at,
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
    # Gap 6: Practice Submission Creation
    # ────────────────────────────────────────────────────────────

    def create_practice_submission(
        self,
        user_id: int,
        interview_type: str,
        difficulty: str,
    ) -> InterviewSubmissionModel:
        """
        Create ad-hoc practice submission without a real window.

        Uses the practice window (id=0 or a special system window)
        and auto-selects a role/template.
        """
        candidate_id = self._resolve_candidate_id(user_id)

        # Find or create practice window
        practice_window = (
            self._db.query(InterviewSubmissionWindowModel)
            .filter(InterviewSubmissionWindowModel.name == "__practice__")
            .first()
        )

        if practice_window is None:
            raise ValueError(
                "Practice window not found. Run migration to create the __practice__ window."
            )

        # Find a matching role-template mapping for the interview type
        mapping = (
            self._db.query(WindowRoleTemplateModel)
            .join(RoleModel, RoleModel.id == WindowRoleTemplateModel.role_id)
            .filter(WindowRoleTemplateModel.window_id == practice_window.id)
            .first()
        )

        if mapping is None:
            # Fallback: use first available role and template
            from app.admin.persistence.models import InterviewTemplateModel

            role = self._db.query(RoleModel).first()
            template = (
                self._db.query(InterviewTemplateModel)
                .filter(InterviewTemplateModel.is_active == True)  # noqa: E712
                .first()
            )
            if not role or not template:
                raise ValueError("No roles or templates available for practice mode.")
            role_id = role.id
            template_id = template.id
        else:
            role_id = mapping.role_id
            template_id = mapping.template_id

        submission = InterviewSubmissionModel(
            candidate_id=candidate_id,
            window_id=practice_window.id,
            role_id=role_id,
            template_id=template_id,
            mode="async",
            status="in_progress",
            consent_captured=True,
            started_at=datetime.now(timezone.utc),
        )
        self._db.add(submission)
        self._db.flush()

        return submission
