"""
Admin Persistence Mappers

Bidirectional conversion between domain entities (dataclasses)
and SQLAlchemy ORM models.  Keeps the domain layer free of
ORM dependencies per REQUIREMENTS.md § 6.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

from app.admin.domain.entities import (
    CodingProblem,
    CodingTopic,
    ContentType,
    DifficultyLevel,
    InterviewScope,
    OverrideRecord,
    Question,
    QuestionType,
    CodingTopicType,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateRole,
    TemplateRubric,
    TemplateScope,
    Topic,
    Window,
    WindowRoleTemplate,
)

from .models import (
    AuditLogModel,
    CodingProblemModel,
    CodingProblemOverrideModel,
    CodingTopicModel,
    InterviewSubmissionWindowModel,
    InterviewTemplateModel,
    InterviewTemplateRoleModel,
    InterviewTemplateRubricModel,
    OVERRIDE_MODEL_MAP,
    QuestionModel,
    QuestionOverrideModel,
    RoleModel,
    RoleOverrideModel,
    RubricDimensionModel,
    RubricModel,
    RubricOverrideModel,
    TemplateOverrideModel,
    TopicModel,
    TopicOverrideModel,
    WindowRoleTemplateModel,
)


# ═══════════════════════════════════════════════════════════════════════════
# Template
# ═══════════════════════════════════════════════════════════════════════════

def template_model_to_entity(m: InterviewTemplateModel) -> Template:
    return Template(
        id=m.id,
        name=m.name,
        description=m.description,
        scope=TemplateScope(m.scope),
        organization_id=m.organization_id,
        template_structure=m.template_structure or {},
        rules=m.rules,
        total_estimated_time_minutes=m.total_estimated_time_minutes,
        version=m.version,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def template_entity_to_model(e: Template, model: Optional[InterviewTemplateModel] = None) -> InterviewTemplateModel:
    if model is None:
        model = InterviewTemplateModel()
    model.name = e.name
    model.description = e.description
    model.scope = e.scope.value if isinstance(e.scope, TemplateScope) else e.scope
    model.organization_id = e.organization_id
    model.template_structure = e.template_structure
    model.rules = e.rules
    model.total_estimated_time_minutes = e.total_estimated_time_minutes
    model.version = e.version
    model.is_active = e.is_active
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Template Role
# ═══════════════════════════════════════════════════════════════════════════

def template_role_model_to_entity(m: InterviewTemplateRoleModel) -> TemplateRole:
    return TemplateRole(
        interview_template_id=m.interview_template_id,
        role_id=m.role_id,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Template Rubric
# ═══════════════════════════════════════════════════════════════════════════

def template_rubric_model_to_entity(m: InterviewTemplateRubricModel) -> TemplateRubric:
    return TemplateRubric(
        id=m.id,
        interview_template_id=m.interview_template_id,
        rubric_id=m.rubric_id,
        section_name=m.section_name,
    )


def template_rubric_entity_to_model(
    e: TemplateRubric, model: Optional[InterviewTemplateRubricModel] = None
) -> InterviewTemplateRubricModel:
    if model is None:
        model = InterviewTemplateRubricModel()
    model.interview_template_id = e.interview_template_id
    model.rubric_id = e.rubric_id
    model.section_name = e.section_name
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Rubric
# ═══════════════════════════════════════════════════════════════════════════

def rubric_model_to_entity(m: RubricModel) -> Rubric:
    return Rubric(
        id=m.id,
        organization_id=m.organization_id,
        name=m.name,
        description=m.description,
        scope=TemplateScope(m.scope),
        schema=m.schema,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def rubric_entity_to_model(e: Rubric, model: Optional[RubricModel] = None) -> RubricModel:
    if model is None:
        model = RubricModel()
    model.name = e.name
    model.description = e.description
    model.scope = e.scope.value if isinstance(e.scope, TemplateScope) else e.scope
    model.organization_id = e.organization_id
    model.schema = e.schema
    model.is_active = e.is_active
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Rubric Dimension
# ═══════════════════════════════════════════════════════════════════════════

def dimension_model_to_entity(m: RubricDimensionModel) -> RubricDimension:
    return RubricDimension(
        id=m.id,
        rubric_id=m.rubric_id,
        dimension_name=m.dimension_name,
        description=m.description,
        max_score=Decimal(str(m.max_score)),
        weight=Decimal(str(m.weight)),
        criteria=m.criteria,
        sequence_order=m.sequence_order,
    )


def dimension_entity_to_model(
    e: RubricDimension, model: Optional[RubricDimensionModel] = None
) -> RubricDimensionModel:
    if model is None:
        model = RubricDimensionModel()
    model.rubric_id = e.rubric_id
    model.dimension_name = e.dimension_name
    model.description = e.description
    model.max_score = e.max_score
    model.weight = e.weight
    model.criteria = e.criteria
    model.sequence_order = e.sequence_order
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Role
# ═══════════════════════════════════════════════════════════════════════════

def role_model_to_entity(m: RoleModel) -> Role:
    return Role(
        id=m.id,
        name=m.name,
        description=m.description,
        scope=TemplateScope(m.scope),
        organization_id=m.organization_id,
    )


def role_entity_to_model(e: Role, model: Optional[RoleModel] = None) -> RoleModel:
    if model is None:
        model = RoleModel()
    model.name = e.name
    model.description = e.description
    model.scope = e.scope.value if isinstance(e.scope, TemplateScope) else e.scope
    model.organization_id = e.organization_id
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Topic
# ═══════════════════════════════════════════════════════════════════════════

def topic_model_to_entity(m: TopicModel) -> Topic:
    return Topic(
        id=m.id,
        name=m.name,
        description=m.description,
        parent_topic_id=m.parent_topic_id,
        scope=TemplateScope(m.scope),
        organization_id=m.organization_id,
        estimated_time_minutes=m.estimated_time_minutes,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def topic_entity_to_model(e: Topic, model: Optional[TopicModel] = None) -> TopicModel:
    if model is None:
        model = TopicModel()
    model.name = e.name
    model.description = e.description
    model.parent_topic_id = e.parent_topic_id
    model.scope = e.scope.value if isinstance(e.scope, TemplateScope) else e.scope
    model.organization_id = e.organization_id
    model.estimated_time_minutes = e.estimated_time_minutes
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Coding Topic
# ═══════════════════════════════════════════════════════════════════════════

def coding_topic_model_to_entity(m: CodingTopicModel) -> CodingTopic:
    return CodingTopic(
        id=m.id,
        name=m.name,
        description=m.description,
        topic_type=CodingTopicType(m.topic_type),
        parent_topic_id=m.parent_topic_id,
        scope=TemplateScope(m.scope),
        organization_id=m.organization_id,
        display_order=m.display_order,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def coding_topic_entity_to_model(
    e: CodingTopic, model: Optional[CodingTopicModel] = None
) -> CodingTopicModel:
    if model is None:
        model = CodingTopicModel()
    model.name = e.name
    model.description = e.description
    model.topic_type = e.topic_type.value if isinstance(e.topic_type, CodingTopicType) else e.topic_type
    model.parent_topic_id = e.parent_topic_id
    model.scope = e.scope.value if isinstance(e.scope, TemplateScope) else e.scope
    model.organization_id = e.organization_id
    model.display_order = e.display_order
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Question
# ═══════════════════════════════════════════════════════════════════════════

def question_model_to_entity(m: QuestionModel) -> Question:
    return Question(
        id=m.id,
        question_text=m.question_text,
        answer_text=m.answer_text,
        question_type=QuestionType(m.question_type),
        difficulty=DifficultyLevel(m.difficulty),
        scope=TemplateScope(m.scope),
        organization_id=m.organization_id,
        source_type=m.source_type,
        estimated_time_minutes=m.estimated_time_minutes,
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def question_entity_to_model(e: Question, model: Optional[QuestionModel] = None) -> QuestionModel:
    if model is None:
        model = QuestionModel()
    model.question_text = e.question_text
    model.answer_text = e.answer_text
    model.question_type = e.question_type.value if isinstance(e.question_type, QuestionType) else e.question_type
    model.difficulty = e.difficulty.value if isinstance(e.difficulty, DifficultyLevel) else e.difficulty
    model.scope = e.scope.value if isinstance(e.scope, TemplateScope) else e.scope
    model.organization_id = e.organization_id
    model.source_type = e.source_type
    model.estimated_time_minutes = e.estimated_time_minutes
    model.is_active = e.is_active
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Coding Problem
# ═══════════════════════════════════════════════════════════════════════════

def coding_problem_model_to_entity(m: CodingProblemModel) -> CodingProblem:
    return CodingProblem(
        id=m.id,
        title=m.title,
        body=m.body,
        difficulty=DifficultyLevel(m.difficulty),
        scope=TemplateScope(m.scope),
        organization_id=m.organization_id,
        description=m.description,
        constraints=m.constraints,
        estimated_time_minutes=m.estimated_time_minutes,
        is_active=m.is_active,
        source_name=m.source_name,
        source_id=m.source_id,
        source_slug=m.source_slug,
        raw_content=m.raw_content,
        examples=m.examples,
        constraints_structured=m.constraints_structured,
        hints=m.hints,
        stats=m.stats,
        code_snippets=m.code_snippets,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def coding_problem_entity_to_model(
    e: CodingProblem, model: Optional[CodingProblemModel] = None
) -> CodingProblemModel:
    if model is None:
        model = CodingProblemModel()
    model.title = e.title
    model.body = e.body
    model.difficulty = e.difficulty.value if isinstance(e.difficulty, DifficultyLevel) else e.difficulty
    model.scope = e.scope.value if isinstance(e.scope, TemplateScope) else e.scope
    model.organization_id = e.organization_id
    model.description = e.description
    model.constraints = e.constraints
    model.estimated_time_minutes = e.estimated_time_minutes
    model.is_active = e.is_active
    model.source_name = e.source_name
    model.source_id = e.source_id
    model.source_slug = e.source_slug
    model.raw_content = e.raw_content
    model.examples = e.examples
    model.constraints_structured = e.constraints_structured
    model.hints = e.hints
    model.stats = e.stats
    model.code_snippets = e.code_snippets
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Window
# ═══════════════════════════════════════════════════════════════════════════

def window_model_to_entity(m: InterviewSubmissionWindowModel) -> Window:
    return Window(
        id=m.id,
        organization_id=m.organization_id,
        admin_id=m.admin_id,
        name=m.name,
        scope=InterviewScope(m.scope),
        start_time=m.start_time,
        end_time=m.end_time,
        timezone=m.timezone,
        max_allowed_submissions=m.max_allowed_submissions,
        allow_after_end_time=m.allow_after_end_time,
        allow_resubmission=m.allow_resubmission,
    )


def window_entity_to_model(
    e: Window, model: Optional[InterviewSubmissionWindowModel] = None
) -> InterviewSubmissionWindowModel:
    if model is None:
        model = InterviewSubmissionWindowModel()
    model.organization_id = e.organization_id
    model.admin_id = e.admin_id
    model.name = e.name
    model.scope = e.scope.value if isinstance(e.scope, InterviewScope) else e.scope
    model.start_time = e.start_time
    model.end_time = e.end_time
    model.timezone = e.timezone
    model.max_allowed_submissions = e.max_allowed_submissions
    model.allow_after_end_time = e.allow_after_end_time
    model.allow_resubmission = e.allow_resubmission
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Window Role Template
# ═══════════════════════════════════════════════════════════════════════════

def window_mapping_model_to_entity(m: WindowRoleTemplateModel) -> WindowRoleTemplate:
    return WindowRoleTemplate(
        id=m.id,
        window_id=m.window_id,
        role_id=m.role_id,
        template_id=m.template_id,
        selection_weight=m.selection_weight,
    )


def window_mapping_entity_to_model(
    e: WindowRoleTemplate, model: Optional[WindowRoleTemplateModel] = None
) -> WindowRoleTemplateModel:
    if model is None:
        model = WindowRoleTemplateModel()
    model.window_id = e.window_id
    model.role_id = e.role_id
    model.template_id = e.template_id
    model.selection_weight = e.selection_weight
    return model


# ═══════════════════════════════════════════════════════════════════════════
# Override (generic — works for all 6 override tables)
# ═══════════════════════════════════════════════════════════════════════════

def override_model_to_entity(m: Any, content_type: ContentType) -> OverrideRecord:
    return OverrideRecord(
        id=m.id,
        organization_id=m.organization_id,
        base_content_id=m.base_content_id,
        content_type=content_type,
        override_fields=m.override_fields or {},
        is_active=m.is_active,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def override_entity_to_model(e: OverrideRecord) -> Any:
    ct_value = e.content_type.value if isinstance(e.content_type, ContentType) else str(e.content_type)
    model_cls = OVERRIDE_MODEL_MAP.get(ct_value)
    if model_cls is None:
        raise ValueError(f"Unknown override content type: {e.content_type}")
    model = model_cls()
    model.organization_id = e.organization_id
    model.base_content_id = e.base_content_id
    model.override_fields = e.override_fields
    model.is_active = e.is_active
    return model
