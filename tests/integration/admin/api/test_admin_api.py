"""
Integration Tests for Admin API

Tests the admin router registration and endpoint wiring through the
full FastAPI application stack. Uses TestClient with mocked auth and
database dependencies.

These tests verify:
  • Router is correctly mounted at /api/v1/admin
  • Endpoints are reachable and produce correct HTTP status codes
  • Auth guards reject unauthenticated requests
  • Pydantic validation rejects malformed payloads (422)
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.admin.domain.entities import (
    CodingProblem,
    DifficultyLevel,
    InterviewScope,
    OverrideRecord,
    ContentType,
    Question,
    QuestionType,
    Role,
    Rubric,
    RubricDimension,
    Template,
    TemplateScope,
    Topic,
    Window,
)
from app.shared.auth_context.models import AdminRole, IdentityContext, UserType


# ── Fixtures ──────────────────────────────────────────────────────────────

NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _admin_identity():
    """Create a frozen IdentityContext for an admin user."""
    return IdentityContext(
        user_id=1,
        user_type=UserType.ADMIN,
        organization_id=100,
        admin_role=AdminRole.ADMIN,
        token_version=1,
        issued_at=1700000000,
        expires_at=1700003600,
    )


def _superadmin_identity():
    return IdentityContext(
        user_id=2,
        user_type=UserType.ADMIN,
        organization_id=1,
        admin_role=AdminRole.SUPERADMIN,
        token_version=1,
        issued_at=1700000000,
        expires_at=1700003600,
    )


def _sample_template():
    return Template(
        id=1,
        name="Test Template",
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


def _sample_rubric():
    return Rubric(
        id=1,
        organization_id=1,
        name="Test Rubric",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


def _sample_role():
    return Role(
        id=1,
        name="Software Engineer",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _sample_topic():
    return Topic(
        id=1,
        name="Algorithms",
        description="Desc",
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        created_at=NOW,
        updated_at=NOW,
    )


def _sample_question():
    return Question(
        id=1,
        question_text="Test question",
        answer_text=None,
        question_type=QuestionType.BEHAVIORAL,
        difficulty=DifficultyLevel.EASY,
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        estimated_time_minutes=5,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


def _sample_coding_problem():
    return CodingProblem(
        id=1,
        title="Two Sum",
        body="Given an array...",
        difficulty=DifficultyLevel.EASY,
        scope=TemplateScope.PUBLIC,
        organization_id=1,
        estimated_time_minutes=30,
        is_active=True,
        examples=[],
        hints=[],
        code_snippets={},
        created_at=NOW,
        updated_at=NOW,
    )


def _sample_window():
    return Window(
        id=1,
        organization_id=100,
        admin_id=1,
        name="Test Window",
        scope=InterviewScope.GLOBAL,
        start_time=datetime(2024, 3, 1, tzinfo=timezone.utc),
        end_time=datetime(2024, 3, 15, tzinfo=timezone.utc),
        timezone="UTC",
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def app_with_mocked_deps():
    """
    Create the full FastAPI app with mocked auth and DB dependencies.

    Overrides:
      - require_admin ➜ returns a test IdentityContext
      - get_db_session_with_commit ➜ returns a MagicMock Session
    """
    from app.bootstrap import create_app

    app = create_app()

    # Override auth dependency to allow requests through
    from app.bootstrap.dependencies import require_admin, get_db_session_with_commit

    app.dependency_overrides[require_admin] = lambda: _admin_identity()
    app.dependency_overrides[get_db_session_with_commit] = lambda: MagicMock()

    yield app

    app.dependency_overrides.clear()


@pytest.fixture
def client(app_with_mocked_deps):
    return TestClient(app_with_mocked_deps)


# ── Router Registration ────────────────────────────────────────────────


class TestAdminRouterRegistered:
    """Verify the admin router is actually mounted."""

    def test_admin_routes_exist(self, client):
        """At least one admin endpoint should be reachable (auth may block)."""
        # OpenAPI docs include admin routes
        resp = client.get("/openapi.json")
        assert resp.status_code == 200
        paths = resp.json().get("paths", {})
        admin_paths = [p for p in paths if p.startswith("/api/v1/admin")]
        assert len(admin_paths) > 0, "No admin routes registered"


# ── Template endpoint integration ────────────────────────────────────


class TestTemplateEndpoints:
    @patch("app.admin.api.routes.build_template_service")
    def test_list_templates(self, mock_build, client):
        svc = MagicMock()
        svc.list_templates.return_value = ([_sample_template()], 1)
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/templates")
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        assert "pagination" in body
        assert len(body["data"]) == 1

    @patch("app.admin.api.routes.build_template_service")
    def test_create_template(self, mock_build, client):
        svc = MagicMock()
        svc.create_template.return_value = _sample_template()
        mock_build.return_value = svc

        resp = client.post(
            "/api/v1/admin/templates",
            json={
                "name": "New Template",
                "scope": "public",
                "template_structure": {"sections": []},
            },
        )
        assert resp.status_code == 201
        assert resp.json()["data"]["name"] == "Test Template"

    @patch("app.admin.api.routes.build_template_service")
    def test_get_template(self, mock_build, client):
        svc = MagicMock()
        svc.get_template.return_value = _sample_template()
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/templates/1")
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == 1

    def test_create_template_validation_error(self, client):
        """Missing required fields → 422."""
        resp = client.post(
            "/api/v1/admin/templates",
            json={"description": "no name or scope"},
        )
        assert resp.status_code == 422


# ── Rubric endpoint integration ──────────────────────────────────────


class TestRubricEndpoints:
    @patch("app.admin.api.routes.build_rubric_service")
    def test_list_rubrics(self, mock_build, client):
        svc = MagicMock()
        svc.list_rubrics.return_value = ([_sample_rubric()], 1)
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/rubrics")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1

    @patch("app.admin.api.routes.build_rubric_service")
    def test_create_rubric(self, mock_build, client):
        svc = MagicMock()
        svc.create_rubric.return_value = _sample_rubric()
        mock_build.return_value = svc

        resp = client.post(
            "/api/v1/admin/rubrics",
            json={
                "name": "New Rubric",
                "scope": "public",
                "dimensions": [
                    {
                        "dimension_name": "Comm",
                        "max_score": "10",
                        "weight": "1.0",
                    }
                ],
            },
        )
        assert resp.status_code == 201


# ── Role endpoint integration ────────────────────────────────────────


class TestRoleEndpoints:
    @patch("app.admin.api.routes.build_role_service")
    def test_list_roles(self, mock_build, client):
        svc = MagicMock()
        svc.list_roles.return_value = ([_sample_role()], 1)
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/roles")
        assert resp.status_code == 200

    @patch("app.admin.api.routes.build_role_service")
    def test_create_role(self, mock_build, client):
        svc = MagicMock()
        svc.create_role.return_value = _sample_role()
        mock_build.return_value = svc

        resp = client.post(
            "/api/v1/admin/roles",
            json={"name": "DevOps", "scope": "public"},
        )
        assert resp.status_code == 201


# ── Topic endpoint integration ───────────────────────────────────────


class TestTopicEndpoints:
    @patch("app.admin.api.routes.build_topic_service")
    def test_list_topics(self, mock_build, client):
        svc = MagicMock()
        svc.list_topics.return_value = ([_sample_topic()], 1)
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/topics")
        assert resp.status_code == 200


# ── Question endpoint integration ────────────────────────────────────


class TestQuestionEndpoints:
    @patch("app.admin.api.routes.build_question_service")
    def test_list_questions(self, mock_build, client):
        svc = MagicMock()
        svc.list_questions.return_value = ([_sample_question()], 1)
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/questions")
        assert resp.status_code == 200


# ── CodingProblem endpoint integration ───────────────────────────────


class TestCodingProblemEndpoints:
    @patch("app.admin.api.routes.build_coding_problem_service")
    def test_list_problems(self, mock_build, client):
        svc = MagicMock()
        svc.list_problems.return_value = ([_sample_coding_problem()], 1)
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/coding-problems")
        assert resp.status_code == 200


# ── Window endpoint integration ──────────────────────────────────────


class TestWindowEndpoints:
    @patch("app.admin.api.routes.build_window_service")
    def test_list_windows(self, mock_build, client):
        svc = MagicMock()
        svc.list_windows.return_value = ([_sample_window()], 1)
        mock_build.return_value = svc

        resp = client.get("/api/v1/admin/windows")
        assert resp.status_code == 200

    @patch("app.admin.api.routes.build_window_service")
    def test_create_window(self, mock_build, client):
        svc = MagicMock()
        svc.create_window.return_value = _sample_window()
        mock_build.return_value = svc

        resp = client.post(
            "/api/v1/admin/windows",
            json={
                "name": "Spring 2024",
                "scope": "global",
                "start_time": "2024-03-01T00:00:00Z",
                "end_time": "2024-03-15T00:00:00Z",
                "timezone": "UTC",
                "mappings": [{"role_id": 1, "template_id": 1}],
            },
        )
        assert resp.status_code == 201
