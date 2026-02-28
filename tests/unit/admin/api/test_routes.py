"""
Unit Tests for Admin API Routes

Tests the FastAPI router endpoints with mocked domain layer.
Validates:
- Correct domain service method calls
- Response mapping (domain entity → API response)
- Error propagation (domain errors → pytest.raises)
- Pagination computation
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from starlette.responses import Response

from app.admin.api.routes import (
    # Helpers
    _meta,
    _pagination,
    _template_to_response,
    _rubric_to_response,
    _dimension_to_response,
    _role_to_response,
    _topic_to_response,
    _question_to_response,
    _coding_problem_to_response,
    _window_to_response,
    _override_to_response,
    # Template routes
    list_templates,
    create_template,
    get_template,
    update_template,
    delete_template,
    activate_template,
    create_template_override,
    get_template_override,
    update_template_override,
    delete_template_override,
    # Rubric routes
    list_rubrics,
    create_rubric,
    get_rubric,
    update_rubric,
    delete_rubric,
    get_rubric_dimensions,
    # Role routes
    list_roles,
    create_role,
    get_role,
    update_role,
    # Topic routes
    list_topics,
    create_topic,
    get_topic,
    update_topic,
    # Question routes
    list_questions,
    create_question,
    get_question,
    update_question,
    delete_question,
    create_question_override,
    # Coding problem routes
    list_coding_problems,
    create_coding_problem,
    get_coding_problem,
    update_coding_problem,
    delete_coding_problem,
    # Window routes
    list_windows,
    create_window,
    get_window,
    update_window,
)
from app.admin.api.contracts import (
    TemplateCreateRequest,
    TemplateUpdateRequest,
    TemplateDetailResponse,
    TemplateListResponse,
    RubricCreateRequest,
    RubricUpdateRequest,
    RubricDetailResponse,
    RubricListResponse,
    DimensionRequest,
    DimensionListResponse,
    RoleCreateRequest,
    RoleUpdateRequest,
    RoleDetailResponse,
    RoleListResponse,
    TopicCreateRequest,
    TopicUpdateRequest,
    TopicDetailResponse,
    TopicListResponse,
    QuestionCreateRequest,
    QuestionUpdateRequest,
    QuestionDetailResponse,
    QuestionListResponse,
    CodingProblemCreateRequest,
    CodingProblemUpdateRequest,
    CodingProblemDetailResponse,
    CodingProblemListResponse,
    WindowCreateRequest,
    WindowUpdateRequest,
    WindowDetailResponse,
    WindowListResponse,
    WindowMappingRequest,
    OverrideCreateRequest,
    OverrideUpdateRequest,
    OverrideDetailResponse,
)
from app.admin.domain.entities import (
    CodingProblem,
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
    TemplateScope,
    Topic,
    Window,
    WindowRoleTemplate,
)
from app.shared.errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)


# =============================================================================
# Fixtures & Helpers
# =============================================================================


NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _mock_request(request_id="req-123"):
    r = MagicMock()
    r.state.request_id = request_id
    return r


def _mock_identity():
    identity = MagicMock()
    identity.user_id = 1
    identity.organization_id = 100
    identity.is_superadmin.return_value = False
    return identity


def _sample_template(**overrides):
    defaults = dict(
        id=1,
        name="Backend Template",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        template_structure={"sections": []},
        rules=None,
        total_estimated_time_minutes=60,
        version=1,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return Template(**defaults)


def _sample_rubric(**overrides):
    defaults = dict(
        id=1,
        organization_id=1,
        name="Tech Rubric",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        schema=None,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return Rubric(**defaults)


def _sample_dimension(**overrides):
    defaults = dict(
        id=1,
        rubric_id=1,
        dimension_name="Communication",
        description="Desc",
        max_score=Decimal("10"),
        weight=Decimal("0.5"),
        criteria=None,
        sequence_order=0,
        created_at=NOW,
    )
    defaults.update(overrides)
    return RubricDimension(**defaults)


def _sample_role(**overrides):
    defaults = dict(
        id=1,
        name="Software Engineer",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return Role(**defaults)


def _sample_topic(**overrides):
    defaults = dict(
        id=1,
        name="Algorithms",
        description="Desc",
        parent_topic_id=None,
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        estimated_time_minutes=15,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return Topic(**defaults)


def _sample_question(**overrides):
    defaults = dict(
        id=1,
        question_text="Tell me about yourself",
        answer_text=None,
        question_type=QuestionType.BEHAVIORAL,
        difficulty=DifficultyLevel.EASY,
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        source_type=None,
        estimated_time_minutes=5,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return Question(**defaults)


def _sample_coding_problem(**overrides):
    defaults = dict(
        id=1,
        title="Two Sum",
        body="Given an array...",
        difficulty=DifficultyLevel.EASY,
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        description=None,
        constraints=None,
        estimated_time_minutes=30,
        is_active=True,
        examples=[],
        hints=[],
        code_snippets={},
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return CodingProblem(**defaults)


def _sample_window(**overrides):
    defaults = dict(
        id=1,
        organization_id=100,
        admin_id=1,
        name="Spring 2024",
        scope=InterviewScope.GLOBAL,
        start_time=datetime(2024, 3, 1, tzinfo=timezone.utc),
        end_time=datetime(2024, 3, 15, tzinfo=timezone.utc),
        timezone="UTC",
        max_allowed_submissions=None,
        allow_after_end_time=False,
        allow_resubmission=False,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return Window(**defaults)


def _sample_override(**overrides):
    defaults = dict(
        id=1,
        organization_id=100,
        base_content_id=1,
        content_type=ContentType.TEMPLATE,
        override_fields={"name": "Custom"},
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return OverrideRecord(**defaults)


# =============================================================================
# Helper Tests
# =============================================================================


class TestPagination:
    def test_basic(self):
        p = _pagination(1, 20, 100)
        assert p.page == 1
        assert p.per_page == 20
        assert p.total == 100
        assert p.total_pages == 5

    def test_single_page(self):
        p = _pagination(1, 20, 5)
        assert p.total_pages == 1

    def test_empty(self):
        p = _pagination(1, 20, 0)
        assert p.total_pages == 1  # min 1

    def test_exact_fit(self):
        p = _pagination(1, 10, 30)
        assert p.total_pages == 3

    def test_partial_page(self):
        p = _pagination(1, 10, 25)
        assert p.total_pages == 3


class TestMeta:
    def test_request_id_extracted(self):
        req = _mock_request("abc-123")
        m = _meta(req)
        assert m.request_id == "abc-123"


class TestTemplateMapper:
    def test_maps_all_fields(self):
        t = _sample_template()
        r = _template_to_response(t)
        assert r.id == 1
        assert r.name == "Backend Template"
        assert r.scope == "public"
        assert r.is_active is True


class TestRubricMapper:
    def test_maps_all_fields(self):
        rb = _sample_rubric()
        r = _rubric_to_response(rb)
        assert r.id == 1
        assert r.name == "Tech Rubric"


class TestDimensionMapper:
    def test_maps_all_fields(self):
        d = _sample_dimension()
        r = _dimension_to_response(d)
        assert r.dimension_name == "Communication"
        assert r.weight == Decimal("0.5")


class TestRoleMapper:
    def test_maps_all_fields(self):
        role = _sample_role()
        r = _role_to_response(role)
        assert r.name == "Software Engineer"


class TestTopicMapper:
    def test_maps_all_fields(self):
        t = _sample_topic()
        r = _topic_to_response(t)
        assert r.name == "Algorithms"
        assert r.parent_topic_id is None


class TestQuestionMapper:
    def test_maps_all_fields(self):
        q = _sample_question()
        r = _question_to_response(q)
        assert r.question_text == "Tell me about yourself"
        assert r.question_type == "behavioral"


class TestCodingProblemMapper:
    def test_maps_all_fields(self):
        p = _sample_coding_problem()
        r = _coding_problem_to_response(p)
        assert r.title == "Two Sum"
        assert r.difficulty == "easy"


class TestWindowMapper:
    def test_maps_all_fields(self):
        w = _sample_window()
        r = _window_to_response(w)
        assert r.name == "Spring 2024"
        assert r.scope == "global"


class TestOverrideMapper:
    def test_maps_all_fields(self):
        o = _sample_override()
        r = _override_to_response(o)
        assert r.base_content_id == 1
        assert r.content_type == "template"


# =============================================================================
# Template Route Tests
# =============================================================================


class TestListTemplates:
    @patch("app.admin.api.routes.build_template_service")
    def test_returns_paginated_list(self, mock_build):
        svc = MagicMock()
        svc.list_templates.return_value = ([_sample_template()], 1)
        mock_build.return_value = svc

        result = list_templates(
            request=_mock_request(),
            page=1,
            per_page=20,
            is_active=None,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TemplateListResponse)
        assert len(result.data) == 1
        assert result.pagination.total == 1
        svc.list_templates.assert_called_once()

    @patch("app.admin.api.routes.build_template_service")
    def test_passes_filters_to_service(self, mock_build):
        svc = MagicMock()
        svc.list_templates.return_value = ([], 0)
        mock_build.return_value = svc

        identity = _mock_identity()
        list_templates(
            request=_mock_request(),
            page=2,
            per_page=10,
            is_active=True,
            identity=identity,
            db=MagicMock(),
        )

        svc.list_templates.assert_called_once_with(
            identity, is_active=True, page=2, per_page=10,
        )


class TestCreateTemplate:
    @patch("app.admin.api.routes.build_template_service")
    def test_returns_created_template(self, mock_build):
        svc = MagicMock()
        svc.create_template.return_value = _sample_template()
        mock_build.return_value = svc

        body = TemplateCreateRequest(
            name="Test",
            scope=TemplateScope.PUBLIC,
            template_structure={"sections": []},
        )

        result = create_template(
            request=_mock_request(),
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TemplateDetailResponse)
        assert result.data.name == "Backend Template"  # from mock return

    @patch("app.admin.api.routes.build_template_service")
    def test_propagates_conflict_error(self, mock_build):
        svc = MagicMock()
        svc.create_template.side_effect = ConflictError(message="Duplicate")
        mock_build.return_value = svc

        body = TemplateCreateRequest(
            name="Dup",
            scope=TemplateScope.PUBLIC,
            template_structure={},
        )

        with pytest.raises(ConflictError):
            create_template(
                request=_mock_request(),
                body=body,
                identity=_mock_identity(),
                db=MagicMock(),
            )


class TestGetTemplate:
    @patch("app.admin.api.routes.build_template_service")
    def test_returns_template(self, mock_build):
        svc = MagicMock()
        svc.get_template.return_value = _sample_template()
        mock_build.return_value = svc

        result = get_template(
            request=_mock_request(),
            template_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TemplateDetailResponse)
        assert result.data.id == 1

    @patch("app.admin.api.routes.build_template_service")
    def test_propagates_not_found(self, mock_build):
        svc = MagicMock()
        svc.get_template.side_effect = NotFoundError(resource_type="Template", resource_id=999)
        mock_build.return_value = svc

        with pytest.raises(NotFoundError):
            get_template(
                request=_mock_request(),
                template_id=999,
                identity=_mock_identity(),
                db=MagicMock(),
            )


class TestUpdateTemplate:
    @patch("app.admin.api.routes.build_template_service")
    def test_passes_changes_dict(self, mock_build):
        svc = MagicMock()
        svc.update_template.return_value = _sample_template(name="Updated")
        mock_build.return_value = svc

        body = TemplateUpdateRequest(name="Updated")

        result = update_template(
            request=_mock_request(),
            template_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TemplateDetailResponse)
        # Verify service was called with changes dict
        call_args = svc.update_template.call_args
        assert call_args[0][0] == 1  # template_id
        assert "name" in call_args[0][1]  # changes dict


class TestDeleteTemplate:
    @patch("app.admin.api.routes.build_template_service")
    def test_calls_deactivate(self, mock_build):
        svc = MagicMock()
        svc.deactivate_template.return_value = _sample_template(is_active=False)
        mock_build.return_value = svc

        result = delete_template(
            template_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, Response)
        assert result.status_code == 204
        svc.deactivate_template.assert_called_once()


class TestActivateTemplate:
    @patch("app.admin.api.routes.build_template_service")
    def test_returns_activated(self, mock_build):
        svc = MagicMock()
        svc.activate_template.return_value = _sample_template(is_active=True)
        mock_build.return_value = svc

        result = activate_template(
            request=_mock_request(),
            template_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TemplateDetailResponse)
        assert result.data.is_active is True


class TestCreateTemplateOverride:
    @patch("app.admin.api.routes.build_template_service")
    def test_creates_override(self, mock_build):
        svc = MagicMock()
        svc.create_template_override.return_value = _sample_override()
        mock_build.return_value = svc

        body = OverrideCreateRequest(override_fields={"name": "Custom"})

        result = create_template_override(
            request=_mock_request(),
            template_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, OverrideDetailResponse)
        svc.create_template_override.assert_called_once()


class TestGetTemplateOverride:
    @patch("app.admin.api.routes.build_template_service")
    def test_returns_override(self, mock_build):
        svc = MagicMock()
        svc.get_effective_template.return_value = (_sample_template(), _sample_override())
        mock_build.return_value = svc

        result = get_template_override(
            request=_mock_request(),
            template_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, OverrideDetailResponse)

    @patch("app.admin.api.routes.build_template_service")
    def test_raises_not_found_when_no_override(self, mock_build):
        svc = MagicMock()
        svc.get_effective_template.return_value = (_sample_template(), None)
        mock_build.return_value = svc

        with pytest.raises(NotFoundError):
            get_template_override(
                request=_mock_request(),
                template_id=1,
                identity=_mock_identity(),
                db=MagicMock(),
            )


class TestUpdateTemplateOverride:
    @patch("app.admin.api.routes.build_template_service")
    def test_updates_override(self, mock_build):
        svc = MagicMock()
        svc.update_template_override.return_value = _sample_override()
        mock_build.return_value = svc

        body = OverrideUpdateRequest(override_fields={"name": "Updated"})

        result = update_template_override(
            request=_mock_request(),
            template_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, OverrideDetailResponse)


class TestDeleteTemplateOverride:
    @patch("app.admin.api.routes.build_template_service")
    def test_deletes_override(self, mock_build):
        svc = MagicMock()
        mock_build.return_value = svc

        result = delete_template_override(
            template_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, Response)
        assert result.status_code == 204
        svc.delete_template_override.assert_called_once()


# =============================================================================
# Rubric Route Tests
# =============================================================================


class TestListRubrics:
    @patch("app.admin.api.routes.build_rubric_service")
    def test_returns_paginated_list(self, mock_build):
        svc = MagicMock()
        svc.list_rubrics.return_value = ([_sample_rubric()], 1)
        mock_build.return_value = svc

        result = list_rubrics(
            request=_mock_request(),
            page=1,
            per_page=20,
            is_active=None,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RubricListResponse)
        assert len(result.data) == 1


class TestCreateRubric:
    @patch("app.admin.api.routes.build_rubric_service")
    def test_creates_rubric(self, mock_build):
        svc = MagicMock()
        svc.create_rubric.return_value = _sample_rubric()
        mock_build.return_value = svc

        body = RubricCreateRequest(
            name="Tech Rubric",
            scope=TemplateScope.PUBLIC,
            dimensions=[
                DimensionRequest(
                    dimension_name="Comm",
                    max_score=Decimal("10"),
                    weight=Decimal("1.0"),
                ),
            ],
        )

        result = create_rubric(
            request=_mock_request(),
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RubricDetailResponse)
        svc.create_rubric.assert_called_once()


class TestGetRubric:
    @patch("app.admin.api.routes.build_rubric_service")
    def test_returns_rubric(self, mock_build):
        svc = MagicMock()
        svc.get_rubric.return_value = _sample_rubric()
        mock_build.return_value = svc

        result = get_rubric(
            request=_mock_request(),
            rubric_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RubricDetailResponse)


class TestUpdateRubric:
    @patch("app.admin.api.routes.build_rubric_service")
    def test_passes_changes_and_dimensions(self, mock_build):
        svc = MagicMock()
        svc.update_rubric.return_value = _sample_rubric()
        mock_build.return_value = svc

        body = RubricUpdateRequest(name="Updated", dimensions=[
            DimensionRequest(
                dimension_name="New Dim",
                max_score=Decimal("10"),
                weight=Decimal("1.0"),
            ),
        ])

        result = update_rubric(
            request=_mock_request(),
            rubric_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RubricDetailResponse)
        call_args = svc.update_rubric.call_args
        # rubric_id, changes, dimensions, identity
        assert call_args[0][0] == 1


class TestDeleteRubric:
    @patch("app.admin.api.routes.build_rubric_service")
    def test_calls_deactivate(self, mock_build):
        svc = MagicMock()
        svc.deactivate_rubric.return_value = _sample_rubric(is_active=False)
        mock_build.return_value = svc

        result = delete_rubric(
            rubric_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, Response)
        assert result.status_code == 204


class TestGetRubricDimensions:
    @patch("app.admin.api.routes.build_rubric_service")
    def test_returns_dimensions(self, mock_build):
        svc = MagicMock()
        svc.get_dimensions.return_value = [_sample_dimension()]
        mock_build.return_value = svc

        result = get_rubric_dimensions(
            request=_mock_request(),
            rubric_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, DimensionListResponse)
        assert len(result.data) == 1


# =============================================================================
# Role Route Tests
# =============================================================================


class TestListRoles:
    @patch("app.admin.api.routes.build_role_service")
    def test_returns_paginated_list(self, mock_build):
        svc = MagicMock()
        svc.list_roles.return_value = ([_sample_role()], 1)
        mock_build.return_value = svc

        result = list_roles(
            request=_mock_request(),
            page=1,
            per_page=20,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RoleListResponse)
        assert result.pagination.total == 1


class TestCreateRole:
    @patch("app.admin.api.routes.build_role_service")
    def test_creates_role(self, mock_build):
        svc = MagicMock()
        svc.create_role.return_value = _sample_role()
        mock_build.return_value = svc

        body = RoleCreateRequest(name="SWE", scope=TemplateScope.PUBLIC)

        result = create_role(
            request=_mock_request(),
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RoleDetailResponse)


class TestGetRole:
    @patch("app.admin.api.routes.build_role_service")
    def test_returns_role(self, mock_build):
        svc = MagicMock()
        svc.get_role.return_value = _sample_role()
        mock_build.return_value = svc

        result = get_role(
            request=_mock_request(),
            role_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RoleDetailResponse)


class TestUpdateRole:
    @patch("app.admin.api.routes.build_role_service")
    def test_updates_role(self, mock_build):
        svc = MagicMock()
        svc.update_role.return_value = _sample_role()
        mock_build.return_value = svc

        body = RoleUpdateRequest(name="Updated")

        result = update_role(
            request=_mock_request(),
            role_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, RoleDetailResponse)


# =============================================================================
# Topic Route Tests
# =============================================================================


class TestListTopics:
    @patch("app.admin.api.routes.build_topic_service")
    def test_returns_paginated_list(self, mock_build):
        svc = MagicMock()
        svc.list_topics.return_value = ([_sample_topic()], 1)
        mock_build.return_value = svc

        result = list_topics(
            request=_mock_request(),
            page=1,
            per_page=20,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TopicListResponse)


class TestCreateTopic:
    @patch("app.admin.api.routes.build_topic_service")
    def test_creates_topic(self, mock_build):
        svc = MagicMock()
        svc.create_topic.return_value = _sample_topic()
        mock_build.return_value = svc

        body = TopicCreateRequest(name="Sorting")

        result = create_topic(
            request=_mock_request(),
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TopicDetailResponse)


class TestGetTopic:
    @patch("app.admin.api.routes.build_topic_service")
    def test_returns_topic(self, mock_build):
        svc = MagicMock()
        svc.get_topic.return_value = _sample_topic()
        mock_build.return_value = svc

        result = get_topic(
            request=_mock_request(),
            topic_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TopicDetailResponse)


class TestUpdateTopic:
    @patch("app.admin.api.routes.build_topic_service")
    def test_updates_topic(self, mock_build):
        svc = MagicMock()
        svc.update_topic.return_value = _sample_topic()
        mock_build.return_value = svc

        body = TopicUpdateRequest(name="Updated")

        result = update_topic(
            request=_mock_request(),
            topic_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, TopicDetailResponse)


# =============================================================================
# Question Route Tests
# =============================================================================


class TestListQuestions:
    @patch("app.admin.api.routes.build_question_service")
    def test_returns_paginated_list(self, mock_build):
        svc = MagicMock()
        svc.list_questions.return_value = ([_sample_question()], 1)
        mock_build.return_value = svc

        result = list_questions(
            request=_mock_request(),
            page=1,
            per_page=20,
            is_active=None,
            question_type=None,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, QuestionListResponse)


class TestCreateQuestion:
    @patch("app.admin.api.routes.build_question_service")
    def test_creates_question(self, mock_build):
        svc = MagicMock()
        svc.create_question.return_value = _sample_question()
        mock_build.return_value = svc

        body = QuestionCreateRequest(
            question_text="Describe recursion",
            question_type=QuestionType.TECHNICAL,
            difficulty=DifficultyLevel.MEDIUM,
            scope=TemplateScope.PUBLIC,
        )

        result = create_question(
            request=_mock_request(),
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, QuestionDetailResponse)


class TestGetQuestion:
    @patch("app.admin.api.routes.build_question_service")
    def test_returns_question(self, mock_build):
        svc = MagicMock()
        svc.get_question.return_value = _sample_question()
        mock_build.return_value = svc

        result = get_question(
            request=_mock_request(),
            question_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, QuestionDetailResponse)


class TestUpdateQuestion:
    @patch("app.admin.api.routes.build_question_service")
    def test_updates_question(self, mock_build):
        svc = MagicMock()
        svc.update_question.return_value = _sample_question()
        mock_build.return_value = svc

        body = QuestionUpdateRequest(question_text="Updated text")

        result = update_question(
            request=_mock_request(),
            question_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, QuestionDetailResponse)


class TestDeleteQuestion:
    @patch("app.admin.api.routes.build_question_service")
    def test_deactivates_question(self, mock_build):
        svc = MagicMock()
        svc.update_question.return_value = _sample_question(is_active=False)
        mock_build.return_value = svc

        identity = _mock_identity()
        result = delete_question(
            question_id=1,
            identity=identity,
            db=MagicMock(),
        )

        assert isinstance(result, Response)
        assert result.status_code == 204
        svc.update_question.assert_called_once_with(1, {"is_active": False}, identity)


class TestCreateQuestionOverride:
    @patch("app.admin.api.routes.build_question_service")
    def test_creates_override(self, mock_build):
        svc = MagicMock()
        svc.create_question_override.return_value = _sample_override(content_type=ContentType.QUESTION)
        mock_build.return_value = svc

        body = OverrideCreateRequest(override_fields={"question_text": "Custom"})

        result = create_question_override(
            request=_mock_request(),
            question_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, OverrideDetailResponse)


# =============================================================================
# Coding Problem Route Tests
# =============================================================================


class TestListCodingProblems:
    @patch("app.admin.api.routes.build_coding_problem_service")
    def test_returns_paginated_list(self, mock_build):
        svc = MagicMock()
        svc.list_problems.return_value = ([_sample_coding_problem()], 1)
        mock_build.return_value = svc

        result = list_coding_problems(
            request=_mock_request(),
            page=1,
            per_page=20,
            is_active=None,
            difficulty=None,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, CodingProblemListResponse)


class TestCreateCodingProblem:
    @patch("app.admin.api.routes.build_coding_problem_service")
    def test_creates_problem(self, mock_build):
        svc = MagicMock()
        svc.create_problem.return_value = _sample_coding_problem()
        mock_build.return_value = svc

        body = CodingProblemCreateRequest(
            title="Merge Sort",
            body="Implement...",
            difficulty=DifficultyLevel.MEDIUM,
            scope=TemplateScope.PUBLIC,
        )

        result = create_coding_problem(
            request=_mock_request(),
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, CodingProblemDetailResponse)


class TestGetCodingProblem:
    @patch("app.admin.api.routes.build_coding_problem_service")
    def test_returns_problem(self, mock_build):
        svc = MagicMock()
        svc.get_problem.return_value = _sample_coding_problem()
        mock_build.return_value = svc

        result = get_coding_problem(
            request=_mock_request(),
            problem_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, CodingProblemDetailResponse)


class TestUpdateCodingProblem:
    @patch("app.admin.api.routes.build_coding_problem_service")
    def test_updates_problem(self, mock_build):
        svc = MagicMock()
        svc.update_problem.return_value = _sample_coding_problem()
        mock_build.return_value = svc

        body = CodingProblemUpdateRequest(title="Updated")

        result = update_coding_problem(
            request=_mock_request(),
            problem_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, CodingProblemDetailResponse)


class TestDeleteCodingProblem:
    @patch("app.admin.api.routes.build_coding_problem_service")
    def test_deactivates_problem(self, mock_build):
        svc = MagicMock()
        svc.update_problem.return_value = _sample_coding_problem(is_active=False)
        mock_build.return_value = svc

        result = delete_coding_problem(
            problem_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, Response)
        assert result.status_code == 204


# =============================================================================
# Window Route Tests
# =============================================================================


class TestListWindows:
    @patch("app.admin.api.routes.build_window_service")
    def test_returns_paginated_list(self, mock_build):
        svc = MagicMock()
        svc.list_windows.return_value = ([_sample_window()], 1)
        mock_build.return_value = svc

        result = list_windows(
            request=_mock_request(),
            page=1,
            per_page=20,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, WindowListResponse)
        assert len(result.data) == 1


class TestCreateWindow:
    @patch("app.admin.api.routes.build_window_service")
    def test_creates_window(self, mock_build):
        svc = MagicMock()
        svc.create_window.return_value = _sample_window()
        mock_build.return_value = svc

        body = WindowCreateRequest(
            name="Fall 2024",
            scope=InterviewScope.GLOBAL,
            start_time=datetime(2024, 9, 1, tzinfo=timezone.utc),
            end_time=datetime(2024, 9, 15, tzinfo=timezone.utc),
            timezone="UTC",
            mappings=[WindowMappingRequest(role_id=1, template_id=1)],
        )

        result = create_window(
            request=_mock_request(),
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, WindowDetailResponse)
        svc.create_window.assert_called_once()


class TestGetWindow:
    @patch("app.admin.api.routes.build_window_service")
    def test_returns_window(self, mock_build):
        svc = MagicMock()
        svc.get_window.return_value = _sample_window()
        mock_build.return_value = svc

        result = get_window(
            request=_mock_request(),
            window_id=1,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, WindowDetailResponse)


class TestUpdateWindow:
    @patch("app.admin.api.routes.build_window_service")
    def test_updates_window(self, mock_build):
        svc = MagicMock()
        svc.update_window.return_value = _sample_window()
        mock_build.return_value = svc

        body = WindowUpdateRequest(name="Updated Window")

        result = update_window(
            request=_mock_request(),
            window_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        assert isinstance(result, WindowDetailResponse)

    @patch("app.admin.api.routes.build_window_service")
    def test_passes_mappings_when_present(self, mock_build):
        svc = MagicMock()
        svc.update_window.return_value = _sample_window()
        mock_build.return_value = svc

        body = WindowUpdateRequest(
            name="Updated",
            mappings=[WindowMappingRequest(role_id=2, template_id=3)],
        )

        update_window(
            request=_mock_request(),
            window_id=1,
            body=body,
            identity=_mock_identity(),
            db=MagicMock(),
        )

        call_args = svc.update_window.call_args
        # window_id, changes, mappings, identity
        mappings_arg = call_args[0][2]
        assert mappings_arg is not None
        assert len(mappings_arg) == 1

    @patch("app.admin.api.routes.build_window_service")
    def test_propagates_validation_error(self, mock_build):
        svc = MagicMock()
        svc.update_window.side_effect = ValidationError(message="end < start")
        mock_build.return_value = svc

        body = WindowUpdateRequest(name="Bad")

        with pytest.raises(ValidationError):
            update_window(
                request=_mock_request(),
                window_id=1,
                body=body,
                identity=_mock_identity(),
                db=MagicMock(),
            )
