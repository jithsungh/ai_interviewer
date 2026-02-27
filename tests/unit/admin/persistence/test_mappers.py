"""
Unit Tests for Admin Persistence Mappers

Tests bidirectional conversion between domain entities and ORM models.
Uses plain model objects (no DB required) to verify correctness.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.admin.domain.entities import (
    CodingProblem,
    CodingTopic,
    CodingTopicType,
    ContentType,
    DifficultyLevel,
    InterviewScope,
    OverrideRecord,
    Question,
    QuestionType,
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
from app.admin.persistence.mappers import (
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
from app.admin.persistence.models import (
    CodingProblemModel,
    CodingTopicModel,
    InterviewSubmissionWindowModel,
    InterviewTemplateModel,
    InterviewTemplateRoleModel,
    InterviewTemplateRubricModel,
    QuestionModel,
    RoleModel,
    RubricDimensionModel,
    RubricModel,
    TemplateOverrideModel,
    TopicModel,
    WindowRoleTemplateModel,
)


NOW = datetime(2026, 2, 27, 12, 0, 0, tzinfo=timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# Template mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateMapper:
    def _make_model(self) -> InterviewTemplateModel:
        m = InterviewTemplateModel()
        m.id = 10
        m.name = "Backend Template"
        m.description = "For backend devs"
        m.scope = "organization"
        m.organization_id = 5
        m.template_structure = {"sections": []}
        m.rules = {"max_time": 60}
        m.total_estimated_time_minutes = 60
        m.version = 2
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        return m

    def _make_entity(self) -> Template:
        return Template(
            id=10,
            name="Backend Template",
            description="For backend devs",
            scope=TemplateScope.ORGANIZATION,
            organization_id=5,
            template_structure={"sections": []},
            rules={"max_time": 60},
            total_estimated_time_minutes=60,
            version=2,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )

    def test_model_to_entity(self):
        m = self._make_model()
        e = template_model_to_entity(m)
        assert e.id == 10
        assert e.name == "Backend Template"
        assert e.scope == TemplateScope.ORGANIZATION
        assert e.organization_id == 5
        assert e.template_structure == {"sections": []}
        assert e.version == 2

    def test_entity_to_model_new(self):
        e = self._make_entity()
        m = template_entity_to_model(e)
        assert isinstance(m, InterviewTemplateModel)
        assert m.name == "Backend Template"
        assert m.scope == "organization"
        assert m.version == 2

    def test_entity_to_model_update(self):
        existing = self._make_model()
        e = self._make_entity()
        e.name = "Updated"
        m = template_entity_to_model(e, model=existing)
        assert m is existing
        assert m.name == "Updated"

    def test_roundtrip(self):
        e = self._make_entity()
        m = template_entity_to_model(e)
        # Simulate DB setting id/timestamps
        m.id = 10
        m.created_at = NOW
        m.updated_at = NOW
        e2 = template_model_to_entity(m)
        assert e2.id == e.id
        assert e2.name == e.name
        assert e2.scope == e.scope

    def test_scope_enum_conversion(self):
        """Ensure string → enum on model_to_entity and enum → string on entity_to_model."""
        m = self._make_model()
        m.scope = "public"
        e = template_model_to_entity(m)
        assert e.scope == TemplateScope.PUBLIC

        e.scope = TemplateScope.PRIVATE
        m2 = template_entity_to_model(e)
        assert m2.scope == "private"

    def test_none_template_structure_becomes_empty_dict(self):
        m = self._make_model()
        m.template_structure = None
        e = template_model_to_entity(m)
        assert e.template_structure == {}


# ═══════════════════════════════════════════════════════════════════════════
# Template Role mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateRoleMapper:
    def test_model_to_entity(self):
        m = InterviewTemplateRoleModel()
        m.interview_template_id = 1
        m.role_id = 2
        e = template_role_model_to_entity(m)
        assert isinstance(e, TemplateRole)
        assert e.interview_template_id == 1
        assert e.role_id == 2


# ═══════════════════════════════════════════════════════════════════════════
# Template Rubric mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTemplateRubricMapper:
    def test_model_to_entity(self):
        m = InterviewTemplateRubricModel()
        m.id = 5
        m.interview_template_id = 1
        m.rubric_id = 3
        m.section_name = "Technical"
        e = template_rubric_model_to_entity(m)
        assert e.id == 5
        assert e.section_name == "Technical"

    def test_entity_to_model(self):
        e = TemplateRubric(id=None, interview_template_id=1, rubric_id=3, section_name="Behavioral")
        m = template_rubric_entity_to_model(e)
        assert isinstance(m, InterviewTemplateRubricModel)
        assert m.section_name == "Behavioral"

    def test_roundtrip(self):
        e = TemplateRubric(id=None, interview_template_id=1, rubric_id=3, section_name="Coding")
        m = template_rubric_entity_to_model(e)
        m.id = 99
        e2 = template_rubric_model_to_entity(m)
        assert e2.id == 99
        assert e2.section_name == "Coding"


# ═══════════════════════════════════════════════════════════════════════════
# Rubric mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRubricMapper:
    def _make_model(self) -> RubricModel:
        m = RubricModel()
        m.id = 20
        m.organization_id = 5
        m.name = "Technical Rubric"
        m.description = "Evaluates technical skills"
        m.scope = "public"
        m.schema = {"version": "1.0"}
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        return m

    def test_model_to_entity(self):
        m = self._make_model()
        e = rubric_model_to_entity(m)
        assert e.id == 20
        assert e.scope == TemplateScope.PUBLIC
        assert e.schema == {"version": "1.0"}

    def test_entity_to_model(self):
        e = Rubric(
            id=None, organization_id=5, name="R",
            description=None, scope=TemplateScope.ORGANIZATION,
        )
        m = rubric_entity_to_model(e)
        assert m.scope == "organization"

    def test_update_preserves_model_identity(self):
        existing = self._make_model()
        e = Rubric(
            id=20, organization_id=5, name="Updated",
            description="new desc", scope=TemplateScope.PRIVATE,
        )
        m = rubric_entity_to_model(e, model=existing)
        assert m is existing
        assert m.name == "Updated"
        assert m.scope == "private"


# ═══════════════════════════════════════════════════════════════════════════
# Rubric Dimension mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDimensionMapper:
    def _make_model(self) -> RubricDimensionModel:
        m = RubricDimensionModel()
        m.id = 30
        m.rubric_id = 20
        m.dimension_name = "Problem Solving"
        m.description = "Evaluates problem solving"
        m.max_score = 10.0
        m.weight = 0.4
        m.criteria = {"levels": [1, 2, 3]}
        m.sequence_order = 1
        return m

    def test_model_to_entity_converts_decimal(self):
        m = self._make_model()
        e = dimension_model_to_entity(m)
        assert isinstance(e.max_score, Decimal)
        assert isinstance(e.weight, Decimal)
        assert e.max_score == Decimal("10.0")

    def test_entity_to_model(self):
        e = RubricDimension(
            id=None, rubric_id=20, dimension_name="Communication",
            description=None, max_score=Decimal("5"), weight=Decimal("0.3"),
            sequence_order=2,
        )
        m = dimension_entity_to_model(e)
        assert m.dimension_name == "Communication"
        assert m.weight == Decimal("0.3")

    def test_roundtrip(self):
        e = RubricDimension(
            id=None, rubric_id=20, dimension_name="Code Quality",
            description="desc", max_score=Decimal("10"), weight=Decimal("0.6"),
            criteria={"k": "v"}, sequence_order=0,
        )
        m = dimension_entity_to_model(e)
        m.id = 42
        e2 = dimension_model_to_entity(m)
        assert e2.id == 42
        assert e2.criteria == {"k": "v"}


# ═══════════════════════════════════════════════════════════════════════════
# Role mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRoleMapper:
    def test_model_to_entity(self):
        m = RoleModel()
        m.id = 1
        m.name = "Software Engineer"
        m.description = "SE role"
        m.scope = "public"
        m.organization_id = None
        e = role_model_to_entity(m)
        assert e.scope == TemplateScope.PUBLIC
        assert e.organization_id is None

    def test_entity_to_model(self):
        e = Role(id=None, name="SE", description=None, scope=TemplateScope.ORGANIZATION, organization_id=5)
        m = role_entity_to_model(e)
        assert m.scope == "organization"
        assert m.organization_id == 5


# ═══════════════════════════════════════════════════════════════════════════
# Topic mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestTopicMapper:
    def test_model_to_entity(self):
        m = TopicModel()
        m.id = 1
        m.name = "Algorithms"
        m.description = "Algo questions"
        m.parent_topic_id = None
        m.scope = "public"
        m.organization_id = None
        m.estimated_time_minutes = 10
        m.created_at = NOW
        m.updated_at = NOW
        e = topic_model_to_entity(m)
        assert e.name == "Algorithms"
        assert e.scope == TemplateScope.PUBLIC

    def test_entity_to_model_with_parent(self):
        e = Topic(
            id=None, name="Sub", description=None,
            parent_topic_id=10, scope=TemplateScope.ORGANIZATION,
            organization_id=5,
        )
        m = topic_entity_to_model(e)
        assert m.parent_topic_id == 10


# ═══════════════════════════════════════════════════════════════════════════
# Coding Topic mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCodingTopicMapper:
    def test_model_to_entity(self):
        m = CodingTopicModel()
        m.id = 1
        m.name = "Binary Trees"
        m.description = "BT"
        m.topic_type = "data_structure"
        m.parent_topic_id = None
        m.scope = "public"
        m.organization_id = None
        m.display_order = 5
        m.created_at = NOW
        m.updated_at = NOW
        e = coding_topic_model_to_entity(m)
        assert e.topic_type == CodingTopicType.DATA_STRUCTURE
        assert e.display_order == 5

    def test_entity_to_model(self):
        e = CodingTopic(
            id=None, name="BFS", description="Breadth-first",
            topic_type=CodingTopicType.TRAVERSAL,
        )
        m = coding_topic_entity_to_model(e)
        assert m.topic_type == "traversal"


# ═══════════════════════════════════════════════════════════════════════════
# Question mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestQuestionMapper:
    def _make_model(self) -> QuestionModel:
        m = QuestionModel()
        m.id = 100
        m.question_text = "Tell me about yourself"
        m.answer_text = "..."
        m.question_type = "behavioral"
        m.difficulty = "easy"
        m.scope = "public"
        m.organization_id = None
        m.source_type = "manual"
        m.estimated_time_minutes = 5
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        return m

    def test_model_to_entity(self):
        m = self._make_model()
        e = question_model_to_entity(m)
        assert e.question_type == QuestionType.BEHAVIORAL
        assert e.difficulty == DifficultyLevel.EASY

    def test_entity_to_model(self):
        e = Question(
            id=None, question_text="text", answer_text=None,
            question_type=QuestionType.TECHNICAL, difficulty=DifficultyLevel.HARD,
            scope=TemplateScope.PRIVATE,
        )
        m = question_entity_to_model(e)
        assert m.question_type == "technical"
        assert m.difficulty == "hard"

    def test_roundtrip(self):
        m = self._make_model()
        e = question_model_to_entity(m)
        m2 = question_entity_to_model(e)
        m2.id = m.id
        m2.created_at = m.created_at
        m2.updated_at = m.updated_at
        e2 = question_model_to_entity(m2)
        assert e2.id == e.id
        assert e2.question_type == e.question_type


# ═══════════════════════════════════════════════════════════════════════════
# Coding Problem mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCodingProblemMapper:
    def _make_entity(self) -> CodingProblem:
        return CodingProblem(
            id=200,
            title="Two Sum",
            body="Given an array...",
            difficulty=DifficultyLevel.EASY,
            scope=TemplateScope.PUBLIC,
            organization_id=None,
            description="Find two numbers",
            examples=[{"input": "[2,7,11]", "output": "[0,1]"}],
            constraints_structured=[{"text": "n < 10^4"}],
            hints=[{"text": "Use a hashmap"}],
            stats={"accepted": 1000},
            code_snippets={"python": "def twoSum(...)"},
        )

    def test_entity_to_model(self):
        e = self._make_entity()
        m = coding_problem_entity_to_model(e)
        assert m.title == "Two Sum"
        assert m.difficulty == "easy"
        assert m.examples == [{"input": "[2,7,11]", "output": "[0,1]"}]

    def test_model_to_entity(self):
        m = CodingProblemModel()
        m.id = 200
        m.title = "Two Sum"
        m.body = "Given an array..."
        m.difficulty = "easy"
        m.scope = "public"
        m.organization_id = None
        m.description = "Find two"
        m.constraints = None
        m.estimated_time_minutes = 30
        m.is_active = True
        m.source_name = None
        m.source_id = None
        m.source_slug = None
        m.raw_content = None
        m.examples = []
        m.constraints_structured = []
        m.hints = []
        m.stats = None
        m.code_snippets = {}
        m.created_at = NOW
        m.updated_at = NOW
        e = coding_problem_model_to_entity(m)
        assert e.difficulty == DifficultyLevel.EASY
        assert e.title == "Two Sum"


# ═══════════════════════════════════════════════════════════════════════════
# Window mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestWindowMapper:
    def _make_model(self) -> InterviewSubmissionWindowModel:
        m = InterviewSubmissionWindowModel()
        m.id = 50
        m.organization_id = 5
        m.admin_id = 1
        m.name = "Spring 2026"
        m.scope = "global"
        m.start_time = NOW
        m.end_time = datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc)
        m.timezone = "UTC"
        m.max_allowed_submissions = 3
        m.allow_after_end_time = False
        m.allow_resubmission = True
        return m

    def test_model_to_entity(self):
        m = self._make_model()
        e = window_model_to_entity(m)
        assert e.scope == InterviewScope.GLOBAL
        assert e.name == "Spring 2026"
        assert e.allow_resubmission is True

    def test_entity_to_model(self):
        e = Window(
            id=None, organization_id=5, admin_id=1,
            name="W", scope=InterviewScope.LOCAL,
            start_time=NOW, end_time=NOW,
            timezone="US/Eastern",
        )
        m = window_entity_to_model(e)
        assert m.scope == "local"
        assert m.timezone == "US/Eastern"


# ═══════════════════════════════════════════════════════════════════════════
# Window Mapping mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestWindowMappingMapper:
    def test_model_to_entity(self):
        m = WindowRoleTemplateModel()
        m.id = 1
        m.window_id = 50
        m.role_id = 1
        m.template_id = 10
        m.selection_weight = 2
        e = window_mapping_model_to_entity(m)
        assert isinstance(e, WindowRoleTemplate)
        assert e.selection_weight == 2

    def test_entity_to_model(self):
        e = WindowRoleTemplate(id=None, window_id=50, role_id=1, template_id=10, selection_weight=3)
        m = window_mapping_entity_to_model(e)
        assert m.selection_weight == 3


# ═══════════════════════════════════════════════════════════════════════════
# Override mapper tests
# ═══════════════════════════════════════════════════════════════════════════


class TestOverrideMapper:
    def test_entity_to_model(self):
        e = OverrideRecord(
            id=None,
            organization_id=5,
            base_content_id=10,
            content_type=ContentType.TEMPLATE,
            override_fields={"name": "Custom Name"},
            is_active=True,
        )
        m = override_entity_to_model(e)
        assert isinstance(m, TemplateOverrideModel)
        assert m.override_fields == {"name": "Custom Name"}

    def test_model_to_entity(self):
        m = TemplateOverrideModel()
        m.id = 1
        m.organization_id = 5
        m.base_content_id = 10
        m.override_fields = {"name": "Override"}
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        e = override_model_to_entity(m, ContentType.TEMPLATE)
        assert e.content_type == ContentType.TEMPLATE
        assert e.override_fields == {"name": "Override"}

    def test_entity_to_model_unknown_type_raises(self):
        e = OverrideRecord(
            id=None, organization_id=5, base_content_id=10,
            content_type="nonexistent",  # type: ignore
            override_fields={},
        )
        with pytest.raises(ValueError, match="Unknown override"):
            override_entity_to_model(e)

    def test_none_override_fields_becomes_empty_dict(self):
        m = TemplateOverrideModel()
        m.id = 1
        m.organization_id = 5
        m.base_content_id = 10
        m.override_fields = None
        m.is_active = True
        m.created_at = NOW
        m.updated_at = NOW
        e = override_model_to_entity(m, ContentType.TEMPLATE)
        assert e.override_fields == {}

    @pytest.mark.parametrize("content_type", list(ContentType))
    def test_all_content_types_produce_correct_model(self, content_type: ContentType):
        """Every ContentType must resolve to a model class without raising."""
        e = OverrideRecord(
            id=None,
            organization_id=5,
            base_content_id=10,
            content_type=content_type,
            override_fields={"key": "val"},
        )
        m = override_entity_to_model(e)
        assert m.override_fields == {"key": "val"}
