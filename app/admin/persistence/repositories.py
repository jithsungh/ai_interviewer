"""
Admin Repository Implementations

Concrete SQLAlchemy implementations of the domain repository protocols.
Each class:
  • Accepts a SQLAlchemy Session
  • Implements the corresponding Protocol from admin.domain.protocols
  • Maps between ORM models and domain entities via mappers module
  • Contains ZERO business logic

Session lifecycle (commit/rollback) is managed by the caller
(FastAPI dependency or context manager).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.admin.domain.entities import (
    SUPER_ORG_ID,
    CodingProblem,
    CodingTopic,
    ContentType,
    OverrideRecord,
    Question,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRole,
    TemplateRubric,
    Topic,
    Window,
    WindowRoleTemplate,
)

from .mappers import (
    coding_problem_entity_to_model,
    coding_problem_model_to_entity,
    coding_topic_entity_to_model,
    coding_topic_model_to_entity,
    dimension_entity_to_model,
    dimension_model_to_entity,
    override_entity_to_model,
    override_model_to_entity,
    question_entity_to_model,
    question_model_to_entity,
    role_entity_to_model,
    role_model_to_entity,
    rubric_entity_to_model,
    rubric_model_to_entity,
    template_entity_to_model,
    template_model_to_entity,
    template_role_model_to_entity,
    template_rubric_entity_to_model,
    template_rubric_model_to_entity,
    topic_entity_to_model,
    topic_model_to_entity,
    window_entity_to_model,
    window_mapping_entity_to_model,
    window_mapping_model_to_entity,
    window_model_to_entity,
)
from .models import (
    AuditLogModel,
    CodingProblemModel,
    CodingTopicModel,
    InterviewSubmissionModel,
    InterviewSubmissionWindowModel,
    InterviewTemplateModel,
    InterviewTemplateRoleModel,
    InterviewTemplateRubricModel,
    OVERRIDE_MODEL_MAP,
    QuestionModel,
    RoleModel,
    RubricDimensionModel,
    RubricModel,
    TopicModel,
    WindowRoleTemplateModel,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Pagination helper
# ═══════════════════════════════════════════════════════════════════════════

def _paginate(query, page: int, per_page: int):
    """Apply offset/limit pagination."""
    offset = (max(page, 1) - 1) * per_page
    return query.offset(offset).limit(per_page)


def _org_filter(model_cls, organization_id: int):
    """
    Multi-tenancy filter: returns content owned by the org + super-org base content.
    """
    return or_(
        model_cls.organization_id == organization_id,
        model_cls.organization_id == SUPER_ORG_ID,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Template Repository
# ═══════════════════════════════════════════════════════════════════════════

class SqlTemplateRepository:
    """Implements TemplateRepository protocol."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, template_id: int) -> Optional[Template]:
        row = self._session.get(InterviewTemplateModel, template_id)
        return template_model_to_entity(row) if row else None

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Template]:
        q = self._session.query(InterviewTemplateModel).filter(
            _org_filter(InterviewTemplateModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(InterviewTemplateModel.is_active == is_active)
        q = q.order_by(InterviewTemplateModel.id)
        q = _paginate(q, page, per_page)
        return [template_model_to_entity(r) for r in q.all()]

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
    ) -> int:
        q = self._session.query(func.count(InterviewTemplateModel.id)).filter(
            _org_filter(InterviewTemplateModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(InterviewTemplateModel.is_active == is_active)
        return q.scalar() or 0

    def create(self, template: Template) -> Template:
        model = template_entity_to_model(template)
        self._session.add(model)
        self._session.flush()
        return template_model_to_entity(model)

    def update(self, template: Template) -> Template:
        model = self._session.get(InterviewTemplateModel, template.id)
        template_entity_to_model(template, model=model)
        self._session.flush()
        return template_model_to_entity(model)

    def exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool:
        q = self._session.query(InterviewTemplateModel.id).filter(
            InterviewTemplateModel.name == name,
            InterviewTemplateModel.organization_id == organization_id,
        )
        if exclude_id is not None:
            q = q.filter(InterviewTemplateModel.id != exclude_id)
        return q.first() is not None

    def get_latest_version(self, name: str, organization_id: Optional[int]) -> Optional[int]:
        row = (
            self._session.query(func.max(InterviewTemplateModel.version))
            .filter(
                InterviewTemplateModel.name == name,
                InterviewTemplateModel.organization_id == organization_id,
            )
            .scalar()
        )
        return row

    # ── Template-Role mappings ─────────────────────────────────────────

    def set_template_roles(self, template_id: int, role_ids: List[int]) -> None:
        self._session.query(InterviewTemplateRoleModel).filter(
            InterviewTemplateRoleModel.interview_template_id == template_id
        ).delete(synchronize_session="fetch")
        for rid in role_ids:
            self._session.add(
                InterviewTemplateRoleModel(
                    interview_template_id=template_id, role_id=rid
                )
            )
        self._session.flush()

    def get_template_roles(self, template_id: int) -> List[TemplateRole]:
        rows = (
            self._session.query(InterviewTemplateRoleModel)
            .filter(InterviewTemplateRoleModel.interview_template_id == template_id)
            .all()
        )
        return [template_role_model_to_entity(r) for r in rows]

    # ── Template-Rubric mappings ───────────────────────────────────────

    def set_template_rubrics(self, template_id: int, rubrics: List[TemplateRubric]) -> None:
        self._session.query(InterviewTemplateRubricModel).filter(
            InterviewTemplateRubricModel.interview_template_id == template_id
        ).delete(synchronize_session="fetch")
        for tr in rubrics:
            model = template_rubric_entity_to_model(tr)
            model.interview_template_id = template_id
            self._session.add(model)
        self._session.flush()

    def get_template_rubrics(self, template_id: int) -> List[TemplateRubric]:
        rows = (
            self._session.query(InterviewTemplateRubricModel)
            .filter(InterviewTemplateRubricModel.interview_template_id == template_id)
            .all()
        )
        return [template_rubric_model_to_entity(r) for r in rows]


# ═══════════════════════════════════════════════════════════════════════════
# Rubric Repository
# ═══════════════════════════════════════════════════════════════════════════

class SqlRubricRepository:
    """Implements RubricRepository protocol."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, rubric_id: int) -> Optional[Rubric]:
        row = self._session.get(RubricModel, rubric_id)
        return rubric_model_to_entity(row) if row else None

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Rubric]:
        q = self._session.query(RubricModel).filter(
            _org_filter(RubricModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(RubricModel.is_active == is_active)
        q = q.order_by(RubricModel.id)
        q = _paginate(q, page, per_page)
        return [rubric_model_to_entity(r) for r in q.all()]

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
    ) -> int:
        q = self._session.query(func.count(RubricModel.id)).filter(
            _org_filter(RubricModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(RubricModel.is_active == is_active)
        return q.scalar() or 0

    def create(self, rubric: Rubric) -> Rubric:
        model = rubric_entity_to_model(rubric)
        self._session.add(model)
        self._session.flush()
        return rubric_model_to_entity(model)

    def update(self, rubric: Rubric) -> Rubric:
        model = self._session.get(RubricModel, rubric.id)
        rubric_entity_to_model(rubric, model=model)
        self._session.flush()
        return rubric_model_to_entity(model)

    def exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool:
        q = self._session.query(RubricModel.id).filter(
            RubricModel.name == name,
            RubricModel.organization_id == organization_id,
        )
        if exclude_id is not None:
            q = q.filter(RubricModel.id != exclude_id)
        return q.first() is not None

    # ── Dimensions ─────────────────────────────────────────────────────

    def get_dimensions(self, rubric_id: int) -> List[RubricDimension]:
        rows = (
            self._session.query(RubricDimensionModel)
            .filter(RubricDimensionModel.rubric_id == rubric_id)
            .order_by(RubricDimensionModel.sequence_order)
            .all()
        )
        return [dimension_model_to_entity(r) for r in rows]

    def set_dimensions(self, rubric_id: int, dimensions: List[RubricDimension]) -> None:
        self._session.query(RubricDimensionModel).filter(
            RubricDimensionModel.rubric_id == rubric_id
        ).delete(synchronize_session="fetch")
        for d in dimensions:
            model = dimension_entity_to_model(d)
            model.rubric_id = rubric_id
            self._session.add(model)
        self._session.flush()


# ═══════════════════════════════════════════════════════════════════════════
# Role Repository
# ═══════════════════════════════════════════════════════════════════════════

class SqlRoleRepository:
    """Implements RoleRepository protocol."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, role_id: int) -> Optional[Role]:
        row = self._session.get(RoleModel, role_id)
        return role_model_to_entity(row) if row else None

    def list_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Role]:
        q = self._session.query(RoleModel).filter(
            _org_filter(RoleModel, organization_id)
        )
        q = q.order_by(RoleModel.id)
        q = _paginate(q, page, per_page)
        return [role_model_to_entity(r) for r in q.all()]

    def count_for_organization(self, organization_id: int) -> int:
        return (
            self._session.query(func.count(RoleModel.id))
            .filter(_org_filter(RoleModel, organization_id))
            .scalar()
        ) or 0

    def create(self, role: Role) -> Role:
        model = role_entity_to_model(role)
        self._session.add(model)
        self._session.flush()
        return role_model_to_entity(model)

    def update(self, role: Role) -> Role:
        model = self._session.get(RoleModel, role.id)
        role_entity_to_model(role, model=model)
        self._session.flush()
        return role_model_to_entity(model)

    def exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool:
        q = self._session.query(RoleModel.id).filter(
            RoleModel.name == name,
            RoleModel.organization_id == organization_id,
        )
        if exclude_id is not None:
            q = q.filter(RoleModel.id != exclude_id)
        return q.first() is not None


# ═══════════════════════════════════════════════════════════════════════════
# Topic Repository
# ═══════════════════════════════════════════════════════════════════════════

class SqlTopicRepository:
    """Implements TopicRepository protocol (general + coding topics)."""

    MAX_ANCESTOR_DEPTH = 50  # Safety limit to prevent infinite loops

    def __init__(self, session: Session) -> None:
        self._session = session

    # ── General Topics ─────────────────────────────────────────────────

    def get_topic_by_id(self, topic_id: int) -> Optional[Topic]:
        row = self._session.get(TopicModel, topic_id)
        return topic_model_to_entity(row) if row else None

    def list_topics_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Topic]:
        q = self._session.query(TopicModel).filter(
            _org_filter(TopicModel, organization_id)
        )
        q = q.order_by(TopicModel.id)
        q = _paginate(q, page, per_page)
        return [topic_model_to_entity(r) for r in q.all()]

    def count_topics_for_organization(self, organization_id: int) -> int:
        return (
            self._session.query(func.count(TopicModel.id))
            .filter(_org_filter(TopicModel, organization_id))
            .scalar()
        ) or 0

    def create_topic(self, topic: Topic) -> Topic:
        model = topic_entity_to_model(topic)
        self._session.add(model)
        self._session.flush()
        return topic_model_to_entity(model)

    def update_topic(self, topic: Topic) -> Topic:
        model = self._session.get(TopicModel, topic.id)
        topic_entity_to_model(topic, model=model)
        self._session.flush()
        return topic_model_to_entity(model)

    def topic_exists_with_name(
        self, name: str, organization_id: Optional[int], *, exclude_id: Optional[int] = None
    ) -> bool:
        q = self._session.query(TopicModel.id).filter(
            TopicModel.name == name,
            TopicModel.organization_id == organization_id,
        )
        if exclude_id is not None:
            q = q.filter(TopicModel.id != exclude_id)
        return q.first() is not None

    def get_topic_ancestors(self, topic_id: int) -> List[int]:
        """Walk parent chain collecting IDs (for cycle detection)."""
        ancestors: List[int] = []
        current_id = topic_id
        for _ in range(self.MAX_ANCESTOR_DEPTH):
            row = self._session.get(TopicModel, current_id)
            if row is None or row.parent_topic_id is None:
                break
            ancestors.append(row.parent_topic_id)
            current_id = row.parent_topic_id
        return ancestors

    # ── Coding Topics ──────────────────────────────────────────────────

    def get_coding_topic_by_id(self, topic_id: int) -> Optional[CodingTopic]:
        row = self._session.get(CodingTopicModel, topic_id)
        return coding_topic_model_to_entity(row) if row else None

    def list_coding_topics_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[CodingTopic]:
        q = self._session.query(CodingTopicModel).filter(
            _org_filter(CodingTopicModel, organization_id)
        )
        q = q.order_by(CodingTopicModel.display_order, CodingTopicModel.id)
        q = _paginate(q, page, per_page)
        return [coding_topic_model_to_entity(r) for r in q.all()]

    def count_coding_topics_for_organization(self, organization_id: int) -> int:
        return (
            self._session.query(func.count(CodingTopicModel.id))
            .filter(_org_filter(CodingTopicModel, organization_id))
            .scalar()
        ) or 0

    def create_coding_topic(self, topic: CodingTopic) -> CodingTopic:
        model = coding_topic_entity_to_model(topic)
        self._session.add(model)
        self._session.flush()
        return coding_topic_model_to_entity(model)

    def update_coding_topic(self, topic: CodingTopic) -> CodingTopic:
        model = self._session.get(CodingTopicModel, topic.id)
        coding_topic_entity_to_model(topic, model=model)
        self._session.flush()
        return coding_topic_model_to_entity(model)

    def get_coding_topic_ancestors(self, topic_id: int) -> List[int]:
        ancestors: List[int] = []
        current_id = topic_id
        for _ in range(self.MAX_ANCESTOR_DEPTH):
            row = self._session.get(CodingTopicModel, current_id)
            if row is None or row.parent_topic_id is None:
                break
            ancestors.append(row.parent_topic_id)
            current_id = row.parent_topic_id
        return ancestors


# ═══════════════════════════════════════════════════════════════════════════
# Question Repository
# ═══════════════════════════════════════════════════════════════════════════

class SqlQuestionRepository:
    """Implements QuestionRepository protocol."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, question_id: int) -> Optional[Question]:
        row = self._session.get(QuestionModel, question_id)
        return question_model_to_entity(row) if row else None

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        question_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Question]:
        q = self._session.query(QuestionModel).filter(
            _org_filter(QuestionModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(QuestionModel.is_active == is_active)
        if question_type is not None:
            q = q.filter(QuestionModel.question_type == question_type)
        q = q.order_by(QuestionModel.id)
        q = _paginate(q, page, per_page)
        return [question_model_to_entity(r) for r in q.all()]

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        question_type: Optional[str] = None,
    ) -> int:
        q = self._session.query(func.count(QuestionModel.id)).filter(
            _org_filter(QuestionModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(QuestionModel.is_active == is_active)
        if question_type is not None:
            q = q.filter(QuestionModel.question_type == question_type)
        return q.scalar() or 0

    def create(self, question: Question) -> Question:
        model = question_entity_to_model(question)
        self._session.add(model)
        self._session.flush()
        return question_model_to_entity(model)

    def update(self, question: Question) -> Question:
        model = self._session.get(QuestionModel, question.id)
        question_entity_to_model(question, model=model)
        self._session.flush()
        return question_model_to_entity(model)


# ═══════════════════════════════════════════════════════════════════════════
# Coding Problem Repository
# ═══════════════════════════════════════════════════════════════════════════

class SqlCodingProblemRepository:
    """Implements CodingProblemRepository protocol."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, problem_id: int) -> Optional[CodingProblem]:
        row = self._session.get(CodingProblemModel, problem_id)
        return coding_problem_model_to_entity(row) if row else None

    def list_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        difficulty: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> List[CodingProblem]:
        q = self._session.query(CodingProblemModel).filter(
            _org_filter(CodingProblemModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(CodingProblemModel.is_active == is_active)
        if difficulty is not None:
            q = q.filter(CodingProblemModel.difficulty == difficulty)
        q = q.order_by(CodingProblemModel.id)
        q = _paginate(q, page, per_page)
        return [coding_problem_model_to_entity(r) for r in q.all()]

    def count_for_organization(
        self,
        organization_id: int,
        *,
        is_active: Optional[bool] = None,
        difficulty: Optional[str] = None,
    ) -> int:
        q = self._session.query(func.count(CodingProblemModel.id)).filter(
            _org_filter(CodingProblemModel, organization_id)
        )
        if is_active is not None:
            q = q.filter(CodingProblemModel.is_active == is_active)
        if difficulty is not None:
            q = q.filter(CodingProblemModel.difficulty == difficulty)
        return q.scalar() or 0

    def create(self, problem: CodingProblem) -> CodingProblem:
        model = coding_problem_entity_to_model(problem)
        self._session.add(model)
        self._session.flush()
        return coding_problem_model_to_entity(model)

    def update(self, problem: CodingProblem) -> CodingProblem:
        model = self._session.get(CodingProblemModel, problem.id)
        coding_problem_entity_to_model(problem, model=model)
        self._session.flush()
        return coding_problem_model_to_entity(model)


# ═══════════════════════════════════════════════════════════════════════════
# Window Repository
# ═══════════════════════════════════════════════════════════════════════════

class SqlWindowRepository:
    """Implements WindowRepository protocol."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, window_id: int) -> Optional[Window]:
        row = self._session.get(InterviewSubmissionWindowModel, window_id)
        return window_model_to_entity(row) if row else None

    def list_for_organization(
        self,
        organization_id: int,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> List[Window]:
        q = (
            self._session.query(InterviewSubmissionWindowModel)
            .filter(InterviewSubmissionWindowModel.organization_id == organization_id)
            .order_by(InterviewSubmissionWindowModel.start_time.desc())
        )
        q = _paginate(q, page, per_page)
        return [window_model_to_entity(r) for r in q.all()]

    def count_for_organization(self, organization_id: int) -> int:
        return (
            self._session.query(func.count(InterviewSubmissionWindowModel.id))
            .filter(InterviewSubmissionWindowModel.organization_id == organization_id)
            .scalar()
        ) or 0

    def create(self, window: Window) -> Window:
        model = window_entity_to_model(window)
        self._session.add(model)
        self._session.flush()
        return window_model_to_entity(model)

    def update(self, window: Window) -> Window:
        model = self._session.get(InterviewSubmissionWindowModel, window.id)
        window_entity_to_model(window, model=model)
        self._session.flush()
        return window_model_to_entity(model)

    def delete(self, window_id: int) -> None:
        self._session.query(InterviewSubmissionWindowModel).filter(
            InterviewSubmissionWindowModel.id == window_id
        ).delete(synchronize_session="fetch")
        self._session.flush()

    def find_overlapping_windows(
        self,
        organization_id: int,
        role_id: int,
        start_time: Any,
        end_time: Any,
        *,
        exclude_window_id: Optional[int] = None,
    ) -> List[Window]:
        # Subquery: window IDs that have mappings for the given role
        role_window_ids = (
            self._session.query(WindowRoleTemplateModel.window_id)
            .filter(WindowRoleTemplateModel.role_id == role_id)
            .subquery()
        )

        q = (
            self._session.query(InterviewSubmissionWindowModel)
            .filter(
                InterviewSubmissionWindowModel.organization_id == organization_id,
                InterviewSubmissionWindowModel.id.in_(role_window_ids),
                InterviewSubmissionWindowModel.start_time < end_time,
                InterviewSubmissionWindowModel.end_time > start_time,
            )
        )
        if exclude_window_id is not None:
            q = q.filter(InterviewSubmissionWindowModel.id != exclude_window_id)

        return [window_model_to_entity(r) for r in q.all()]

    # ── Mappings ───────────────────────────────────────────────────────

    def get_mappings(self, window_id: int) -> List[WindowRoleTemplate]:
        rows = (
            self._session.query(WindowRoleTemplateModel)
            .filter(WindowRoleTemplateModel.window_id == window_id)
            .all()
        )
        return [window_mapping_model_to_entity(r) for r in rows]

    def set_mappings(self, window_id: int, mappings: List[WindowRoleTemplate]) -> None:
        self._session.query(WindowRoleTemplateModel).filter(
            WindowRoleTemplateModel.window_id == window_id
        ).delete(synchronize_session="fetch")
        for m in mappings:
            model = window_mapping_entity_to_model(m)
            model.window_id = window_id
            self._session.add(model)
        self._session.flush()


# ═══════════════════════════════════════════════════════════════════════════
# Submission Repository (read-only)
# ═══════════════════════════════════════════════════════════════════════════

class SqlSubmissionRepository:
    """
    Implements SubmissionRepository protocol (read-only).

    Only existence checks — no mutations.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def template_is_in_use(self, template_id: int) -> bool:
        return (
            self._session.query(InterviewSubmissionModel.id)
            .filter(InterviewSubmissionModel.template_id == template_id)
            .first()
        ) is not None

    def rubric_is_in_use(self, rubric_id: int) -> bool:
        # Rubric is "in use" if any template referencing it has submissions
        template_ids = (
            self._session.query(InterviewTemplateRubricModel.interview_template_id)
            .filter(InterviewTemplateRubricModel.rubric_id == rubric_id)
            .subquery()
        )
        return (
            self._session.query(InterviewSubmissionModel.id)
            .filter(InterviewSubmissionModel.template_id.in_(template_ids))
            .first()
        ) is not None

    def role_is_in_use(self, role_id: int) -> bool:
        return (
            self._session.query(InterviewSubmissionModel.id)
            .filter(InterviewSubmissionModel.role_id == role_id)
            .first()
        ) is not None

    def window_has_submissions(self, window_id: int) -> bool:
        return (
            self._session.query(InterviewSubmissionModel.id)
            .filter(InterviewSubmissionModel.window_id == window_id)
            .first()
        ) is not None


# ═══════════════════════════════════════════════════════════════════════════
# Override Repository (generic for all 6 content types)
# ═══════════════════════════════════════════════════════════════════════════

class SqlOverrideRepository:
    """
    Implements OverrideRepository protocol.

    Uses OVERRIDE_MODEL_MAP to route to the correct table
    based on ContentType.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def _model_cls(self, content_type: ContentType):
        cls = OVERRIDE_MODEL_MAP.get(content_type.value)
        if cls is None:
            raise ValueError(f"Unknown override content type: {content_type}")
        return cls

    def get_override(
        self,
        organization_id: int,
        base_content_id: int,
        content_type: ContentType,
    ) -> Optional[OverrideRecord]:
        cls = self._model_cls(content_type)
        row = (
            self._session.query(cls)
            .filter(
                cls.organization_id == organization_id,
                cls.base_content_id == base_content_id,
            )
            .first()
        )
        return override_model_to_entity(row, content_type) if row else None

    def create_override(self, override: OverrideRecord) -> OverrideRecord:
        model = override_entity_to_model(override)
        self._session.add(model)
        self._session.flush()
        return override_model_to_entity(model, override.content_type)

    def update_override(self, override: OverrideRecord) -> OverrideRecord:
        cls = self._model_cls(override.content_type)
        model = self._session.get(cls, override.id)
        model.override_fields = override.override_fields
        model.is_active = override.is_active
        self._session.flush()
        return override_model_to_entity(model, override.content_type)

    def delete_override(
        self,
        organization_id: int,
        base_content_id: int,
        content_type: ContentType,
    ) -> bool:
        cls = self._model_cls(content_type)
        count = (
            self._session.query(cls)
            .filter(
                cls.organization_id == organization_id,
                cls.base_content_id == base_content_id,
            )
            .delete(synchronize_session="fetch")
        )
        self._session.flush()
        return count > 0

    def list_overrides_for_organization(
        self,
        organization_id: int,
        content_type: ContentType,
    ) -> List[OverrideRecord]:
        cls = self._model_cls(content_type)
        rows = (
            self._session.query(cls)
            .filter(cls.organization_id == organization_id)
            .all()
        )
        return [override_model_to_entity(r, content_type) for r in rows]

    def mark_overrides_stale(
        self,
        base_content_id: int,
        content_type: ContentType,
    ) -> int:
        cls = self._model_cls(content_type)
        count = (
            self._session.query(cls)
            .filter(
                cls.base_content_id == base_content_id,
                cls.is_active == True,  # noqa: E712
            )
            .update({"is_active": False}, synchronize_session="fetch")
        )
        self._session.flush()
        return count


# ═══════════════════════════════════════════════════════════════════════════
# Audit Log Repository (insert-only)
# ═══════════════════════════════════════════════════════════════════════════

class SqlAuditLogRepository:
    """Implements AuditLogRepository protocol (insert-only)."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def log(
        self,
        *,
        organization_id: Optional[int],
        actor_user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[int],
        old_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        model = AuditLogModel(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self._session.add(model)
        # No flush — audit logs are written along with the transaction
