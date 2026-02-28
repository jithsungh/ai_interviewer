"""
Unit Tests for Admin API Contracts

Validates Pydantic request/response schema validation rules.
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal


from app.admin.api.contracts import (
    # Templates
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateResponse,
    TemplateDetailResponse,
    TemplateListResponse,
    # Rubrics
    DimensionRequest,
    RubricCreateRequest,
    RubricUpdateRequest,
    RubricResponse,
    DimensionResponse,
    DimensionListResponse,
    # Roles
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleResponse,
    # Topics
    TopicCreateRequest,
    TopicUpdateRequest,
    TopicResponse,
    # Questions
    QuestionCreateRequest,
    QuestionUpdateRequest,
    QuestionResponse,
    # Coding Problems
    CodingProblemCreateRequest,
    CodingProblemUpdateRequest,
    CodingProblemResponse,
    # Windows
    WindowCreateRequest,
    WindowUpdateRequest,
    WindowMappingRequest,
    WindowResponse,
    # Overrides
    OverrideCreateRequest,
    OverrideUpdateRequest,
    OverrideResponse,
    # Shared
    PaginationMeta,
    MetaInfo,
    SuccessResponse,
)
from app.admin.domain.entities import (
    DifficultyLevel,
    InterviewScope,
    QuestionType,
    TemplateScope,
)


# ==========================================================================
# Template Contracts
# ==========================================================================


class TestTemplateCreateRequest:
    def test_valid_minimal(self):
        req = TemplateCreateRequest(
            name="Backend Engineer",
            scope=TemplateScope.PUBLIC,
            template_structure={"sections": []},
        )
        assert req.name == "Backend Engineer"
        assert req.scope == TemplateScope.PUBLIC
        assert req.description is None

    def test_valid_full(self):
        req = TemplateCreateRequest(
            name="Test",
            description="A description",
            scope=TemplateScope.ORGANIZATION,
            template_structure={"sections": [{"name": "intro"}]},
            rules={"max_time": 60},
            total_estimated_time_minutes=90,
        )
        assert req.total_estimated_time_minutes == 90
        assert req.rules == {"max_time": 60}

    def test_missing_name_raises(self):
        with pytest.raises(Exception):
            TemplateCreateRequest(
                scope=TemplateScope.PUBLIC,
                template_structure={},
            )

    def test_missing_scope_raises(self):
        with pytest.raises(Exception):
            TemplateCreateRequest(
                name="Test",
                template_structure={},
            )


class TestTemplateUpdateRequest:
    def test_partial_update(self):
        req = TemplateUpdateRequest(name="New Name")
        dumped = req.model_dump(exclude_unset=True)
        assert dumped == {"name": "New Name"}

    def test_empty_update(self):
        req = TemplateUpdateRequest()
        dumped = req.model_dump(exclude_unset=True)
        assert dumped == {}


class TestTemplateResponse:
    def test_full_response(self):
        resp = TemplateResponse(
            id=1,
            name="Test",
            scope="public",
            template_structure={"sections": []},
        )
        assert resp.id == 1
        assert resp.is_active is True
        assert resp.version == 1


# ==========================================================================
# Rubric Contracts
# ==========================================================================


class TestDimensionRequest:
    def test_valid(self):
        d = DimensionRequest(
            dimension_name="Communication",
            max_score=Decimal("10"),
            weight=Decimal("0.5"),
        )
        assert d.dimension_name == "Communication"

    def test_weight_must_be_positive(self):
        with pytest.raises(Exception):
            DimensionRequest(
                dimension_name="Test",
                max_score=Decimal("10"),
                weight=Decimal("0"),
            )

    def test_weight_cannot_exceed_one(self):
        with pytest.raises(Exception):
            DimensionRequest(
                dimension_name="Test",
                max_score=Decimal("10"),
                weight=Decimal("1.5"),
            )


class TestRubricCreateRequest:
    def test_valid_with_dimensions(self):
        req = RubricCreateRequest(
            name="Technical Rubric",
            scope=TemplateScope.PUBLIC,
            dimensions=[
                DimensionRequest(
                    dimension_name="Problem Solving",
                    max_score=Decimal("10"),
                    weight=Decimal("0.5"),
                ),
                DimensionRequest(
                    dimension_name="Communication",
                    max_score=Decimal("10"),
                    weight=Decimal("0.5"),
                ),
            ],
        )
        assert len(req.dimensions) == 2

    def test_schema_field_alias(self):
        """schema_ field accepts 'schema' as alias."""
        data = {
            "name": "Test",
            "scope": "public",
            "schema": {"type": "v2"},
        }
        req = RubricCreateRequest(**data)
        assert req.schema_ == {"type": "v2"}


class TestRubricUpdateRequest:
    def test_partial(self):
        req = RubricUpdateRequest(name="New Name")
        dumped = req.model_dump(exclude_unset=True, by_alias=False)
        assert "name" in dumped
        assert "dimensions" not in dumped


# ==========================================================================
# Role Contracts
# ==========================================================================


class TestRoleCreateRequest:
    def test_valid(self):
        req = RoleCreateRequest(name="Software Engineer", scope=TemplateScope.PUBLIC)
        assert req.name == "Software Engineer"
        assert req.description is None


class TestRoleUpdateRequest:
    def test_partial(self):
        req = RoleUpdateRequest(description="Updated description")
        dumped = req.model_dump(exclude_unset=True)
        assert dumped == {"description": "Updated description"}


# ==========================================================================
# Topic Contracts
# ==========================================================================


class TestTopicCreateRequest:
    def test_valid_with_defaults(self):
        req = TopicCreateRequest(name="Algorithms")
        assert req.scope == TemplateScope.PUBLIC
        assert req.parent_topic_id is None

    def test_with_parent(self):
        req = TopicCreateRequest(
            name="Sorting",
            parent_topic_id=1,
            scope=TemplateScope.ORGANIZATION,
            estimated_time_minutes=15,
        )
        assert req.parent_topic_id == 1


# ==========================================================================
# Question Contracts
# ==========================================================================


class TestQuestionCreateRequest:
    def test_valid(self):
        req = QuestionCreateRequest(
            question_text="Tell me about yourself",
            question_type=QuestionType.BEHAVIORAL,
            difficulty=DifficultyLevel.EASY,
            scope=TemplateScope.PUBLIC,
        )
        assert req.estimated_time_minutes == 5
        assert req.is_active is True

    def test_missing_question_type_raises(self):
        with pytest.raises(Exception):
            QuestionCreateRequest(
                question_text="Test",
                difficulty=DifficultyLevel.EASY,
                scope=TemplateScope.PUBLIC,
            )


# ==========================================================================
# CodingProblem Contracts
# ==========================================================================


class TestCodingProblemCreateRequest:
    def test_valid(self):
        req = CodingProblemCreateRequest(
            title="Two Sum",
            body="Given an array...",
            difficulty=DifficultyLevel.EASY,
            scope=TemplateScope.PUBLIC,
        )
        assert req.estimated_time_minutes == 30

    def test_with_optional_fields(self):
        req = CodingProblemCreateRequest(
            title="Two Sum",
            body="Given an array...",
            difficulty=DifficultyLevel.MEDIUM,
            scope=TemplateScope.PUBLIC,
            examples=[{"input": "[1,2]", "output": "3"}],
            hints=[{"text": "Use a hash map"}],
            code_snippets={"python": "def two_sum(nums, target):"},
        )
        assert len(req.examples) == 1
        assert len(req.hints) == 1


# ==========================================================================
# Window Contracts
# ==========================================================================


class TestWindowMappingRequest:
    def test_valid(self):
        m = WindowMappingRequest(role_id=1, template_id=2, selection_weight=3)
        assert m.selection_weight == 3

    def test_default_weight(self):
        m = WindowMappingRequest(role_id=1, template_id=2)
        assert m.selection_weight == 1

    def test_zero_role_id_rejected(self):
        with pytest.raises(Exception):
            WindowMappingRequest(role_id=0, template_id=1)


class TestWindowCreateRequest:
    def test_valid(self):
        req = WindowCreateRequest(
            name="Spring 2024",
            scope=InterviewScope.GLOBAL,
            start_time=datetime(2024, 3, 1, tzinfo=timezone.utc),
            end_time=datetime(2024, 3, 15, tzinfo=timezone.utc),
            timezone="UTC",
            mappings=[WindowMappingRequest(role_id=1, template_id=1)],
        )
        assert len(req.mappings) == 1

    def test_empty_mappings_rejected(self):
        with pytest.raises(Exception):
            WindowCreateRequest(
                name="Empty",
                scope=InterviewScope.GLOBAL,
                start_time=datetime(2024, 3, 1, tzinfo=timezone.utc),
                end_time=datetime(2024, 3, 15, tzinfo=timezone.utc),
                timezone="UTC",
                mappings=[],
            )


# ==========================================================================
# Override Contracts
# ==========================================================================


class TestOverrideCreateRequest:
    def test_valid(self):
        req = OverrideCreateRequest(override_fields={"name": "Custom Name"})
        assert req.override_fields == {"name": "Custom Name"}

    def test_empty_fields_rejected(self):
        """Empty override_fields still valid at Pydantic level (domain enforces)."""
        req = OverrideCreateRequest(override_fields={})
        assert req.override_fields == {}


# ==========================================================================
# Shared Contracts
# ==========================================================================


class TestPaginationMeta:
    def test_basic(self):
        p = PaginationMeta(page=1, per_page=20, total=100, total_pages=5)
        assert p.total_pages == 5


class TestMetaInfo:
    def test_default(self):
        m = MetaInfo()
        assert m.request_id is None

    def test_with_id(self):
        m = MetaInfo(request_id="abc-123")
        assert m.request_id == "abc-123"
