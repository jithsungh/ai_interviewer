"""
Unit Tests for Admin API Dependency Factories

Validates that each factory correctly wires repositories into services.
Uses mocked SQLAlchemy Session (DI factories only construct objects).
"""

import pytest
from unittest.mock import MagicMock

from app.admin.api.dependencies import (
    build_coding_problem_service,
    build_question_service,
    build_role_service,
    build_rubric_service,
    build_template_service,
    build_topic_service,
    build_window_service,
)
from app.admin.domain.services import (
    CodingProblemService,
    QuestionService,
    RoleService,
    RubricService,
    TemplateService,
    TopicService,
    WindowService,
)


@pytest.fixture
def mock_session():
    """Provide a mocked SQLAlchemy Session."""
    return MagicMock()


class TestBuildTemplateService:
    def test_returns_template_service(self, mock_session):
        svc = build_template_service(mock_session)
        assert isinstance(svc, TemplateService)

    def test_injects_all_repos(self, mock_session):
        svc = build_template_service(mock_session)
        assert svc._templates is not None
        assert svc._submissions is not None
        assert svc._overrides is not None
        assert svc._rubrics is not None
        assert svc._roles is not None
        assert svc._audit is not None


class TestBuildRubricService:
    def test_returns_rubric_service(self, mock_session):
        svc = build_rubric_service(mock_session)
        assert isinstance(svc, RubricService)

    def test_injects_all_repos(self, mock_session):
        svc = build_rubric_service(mock_session)
        assert svc._rubrics is not None
        assert svc._submissions is not None
        assert svc._overrides is not None
        assert svc._audit is not None


class TestBuildRoleService:
    def test_returns_role_service(self, mock_session):
        svc = build_role_service(mock_session)
        assert isinstance(svc, RoleService)


class TestBuildTopicService:
    def test_returns_topic_service(self, mock_session):
        svc = build_topic_service(mock_session)
        assert isinstance(svc, TopicService)


class TestBuildQuestionService:
    def test_returns_question_service(self, mock_session):
        svc = build_question_service(mock_session)
        assert isinstance(svc, QuestionService)


class TestBuildCodingProblemService:
    def test_returns_coding_problem_service(self, mock_session):
        svc = build_coding_problem_service(mock_session)
        assert isinstance(svc, CodingProblemService)


class TestBuildWindowService:
    def test_returns_window_service(self, mock_session):
        svc = build_window_service(mock_session)
        assert isinstance(svc, WindowService)

    def test_injects_all_repos(self, mock_session):
        svc = build_window_service(mock_session)
        assert svc._windows is not None
        assert svc._roles is not None
        assert svc._templates is not None
        assert svc._submissions is not None
        assert svc._audit is not None
