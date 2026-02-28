"""
Integration Tests for Auth API Routes

Tests the full HTTP request/response cycle using FastAPI TestClient.
Validates:
- HTTP status codes for success and failure paths
- Request validation (422 on bad input)
- Error response format consistency
- Auth guard enforcement on /me endpoint
- Response schema conformance

IMPORTANT: These tests use mocked database and domain services.
Full end-to-end DB integration tests require a real Postgres instance
and are outside the scope of this suite. They validate HTTP-layer integration.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.api.routes import router
from app.auth.domain.contracts import UserProfile, AuthenticationResult
from app.shared.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
    InfrastructureError,
)
from app.shared.auth_context import IdentityContext, UserType, AdminRole
from app.bootstrap.exception_handlers import (
    base_error_handler,
    validation_error_handler,
)
from app.shared.errors import BaseError
from app.persistence.postgres.session import get_db_session, get_db_session_with_commit
from fastapi.exceptions import RequestValidationError


def _mock_db_session():
    """Yield a mock SQLAlchemy session for testing."""
    yield MagicMock(spec=Session)


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with auth router and exception handlers."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/auth", tags=["Authentication"])

    # Register the same error handlers used in production
    app.add_exception_handler(BaseError, base_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    # Override DB dependencies with mocks (no real DB in tests)
    app.dependency_overrides[get_db_session] = _mock_db_session
    app.dependency_overrides[get_db_session_with_commit] = _mock_db_session

    return app


def _admin_profile(**overrides) -> UserProfile:
    defaults = dict(
        user_id=1,
        email="admin@company.com",
        user_type="admin",
        user_status="active",
        admin_id=10,
        organization_id=100,
        admin_role="admin",
        admin_status="active",
        last_login_at=datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _candidate_profile(**overrides) -> UserProfile:
    defaults = dict(
        user_id=2,
        email="cand@example.com",
        user_type="candidate",
        user_status="active",
        candidate_id=20,
        full_name="Jane Doe",
        candidate_status="active",
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


def _auth_result(profile=None, **overrides) -> AuthenticationResult:
    defaults = dict(
        access_token="eyJhbGciOiJIUzI1NiJ9.test",
        refresh_token="a" * 128,
        token_type="Bearer",
        expires_in=900,
        user_profile=profile or _admin_profile(),
    )
    defaults.update(overrides)
    return AuthenticationResult(**defaults)


# =============================================================================
# REGISTRATION ENDPOINTS
# =============================================================================


class TestRegisterAdminIntegration:
    """Integration tests for POST /api/v1/auth/register/admin."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_success_returns_201(self, mock_build):
        mock_service = MagicMock()
        mock_service.register_admin.return_value = _admin_profile()
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "admin@company.com",
                "password": "SecurePass123!",
                "organization_id": 1,
                "admin_role": "admin",
                "full_name": "John Doe",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == 1
        assert data["email"] == "admin@company.com"
        assert data["user_type"] == "admin"
        assert data["message"] == "Registration successful"

    @patch("app.auth.api.routes._build_auth_service")
    def test_duplicate_email_returns_409(self, mock_build):
        mock_service = MagicMock()
        mock_service.register_admin.side_effect = ConflictError(
            message="Email already registered"
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "dup@company.com",
                "password": "SecurePass123!",
                "organization_id": 1,
                "admin_role": "admin",
            },
        )

        assert resp.status_code == 409
        body = resp.json()
        assert "error" in body

    @patch("app.auth.api.routes._build_auth_service")
    def test_missing_org_returns_404(self, mock_build):
        mock_service = MagicMock()
        mock_service.register_admin.side_effect = NotFoundError(
            resource_type="Organization", resource_id=999
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "admin@company.com",
                "password": "SecurePass123!",
                "organization_id": 999,
                "admin_role": "admin",
            },
        )

        assert resp.status_code == 404

    def test_invalid_email_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "not-an-email",
                "password": "SecurePass123!",
                "organization_id": 1,
                "admin_role": "admin",
            },
        )

        assert resp.status_code == 422

    def test_short_password_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "admin@co.com",
                "password": "Sh1!",
                "organization_id": 1,
                "admin_role": "admin",
            },
        )

        assert resp.status_code == 422

    def test_password_without_uppercase_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "admin@co.com",
                "password": "mypassword123!",
                "organization_id": 1,
                "admin_role": "admin",
            },
        )

        assert resp.status_code == 422

    def test_superadmin_role_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "admin@co.com",
                "password": "SecurePass123!",
                "organization_id": 1,
                "admin_role": "superadmin",
            },
        )

        assert resp.status_code == 422

    def test_missing_required_fields_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post("/api/v1/auth/register/admin", json={})
        assert resp.status_code == 422

    def test_zero_organization_id_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/admin",
            json={
                "email": "admin@co.com",
                "password": "SecurePass123!",
                "organization_id": 0,
                "admin_role": "admin",
            },
        )

        assert resp.status_code == 422


class TestRegisterCandidateIntegration:
    """Integration tests for POST /api/v1/auth/register/candidate."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_success_returns_201(self, mock_build):
        mock_service = MagicMock()
        mock_service.register_candidate.return_value = _candidate_profile()
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/candidate",
            json={
                "email": "cand@example.com",
                "password": "SecurePass123!",
                "full_name": "Jane Doe",
                "phone": "+1-555-0123",
            },
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == 2
        assert data["user_type"] == "candidate"

    @patch("app.auth.api.routes._build_auth_service")
    def test_duplicate_email_returns_409(self, mock_build):
        mock_service = MagicMock()
        mock_service.register_candidate.side_effect = ConflictError(
            message="Email already registered"
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/candidate",
            json={
                "email": "dup@example.com",
                "password": "SecurePass123!",
            },
        )

        assert resp.status_code == 409

    def test_missing_email_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/register/candidate",
            json={"password": "SecurePass123!"},
        )

        assert resp.status_code == 422


# =============================================================================
# LOGIN ENDPOINT
# =============================================================================


class TestLoginIntegration:
    """Integration tests for POST /api/v1/auth/login."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_success_returns_200_with_tokens(self, mock_build):
        mock_service = MagicMock()
        mock_service.login.return_value = _auth_result()
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@company.com", "password": "SecurePass123!"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 900
        assert data["user"]["user_id"] == 1
        assert data["user"]["email"] == "admin@company.com"

    @patch("app.auth.api.routes._build_auth_service")
    def test_invalid_credentials_returns_401(self, mock_build):
        mock_service = MagicMock()
        mock_service.login.side_effect = AuthenticationError(
            message="Invalid credentials"
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "wrong@co.com", "password": "bad"},
        )

        assert resp.status_code == 401

    @patch("app.auth.api.routes._build_auth_service")
    def test_banned_user_returns_401(self, mock_build):
        mock_service = MagicMock()
        mock_service.login.side_effect = AuthenticationError(
            message="User is banned"
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "banned@co.com", "password": "SecurePass123!"},
        )

        assert resp.status_code == 401

    def test_missing_password_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@co.com"},
        )

        assert resp.status_code == 422

    def test_empty_body_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


# =============================================================================
# REFRESH ENDPOINT
# =============================================================================


class TestRefreshTokenIntegration:
    """Integration tests for POST /api/v1/auth/refresh."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_success_returns_200_with_new_tokens(self, mock_build):
        mock_service = MagicMock()
        mock_service.refresh_token.return_value = _auth_result(
            access_token="new-jwt",
            refresh_token="b" * 128,
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "a" * 128},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["access_token"] == "new-jwt"
        assert data["refresh_token"] == "b" * 128

    @patch("app.auth.api.routes._build_auth_service")
    def test_invalid_token_returns_401(self, mock_build):
        mock_service = MagicMock()
        mock_service.refresh_token.side_effect = AuthenticationError(
            message="Invalid refresh token"
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "x" * 128},
        )

        assert resp.status_code == 401

    def test_short_token_returns_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "short"},
        )

        assert resp.status_code == 422


# =============================================================================
# LOGOUT ENDPOINT
# =============================================================================


class TestLogoutIntegration:
    """Integration tests for POST /api/v1/auth/logout."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_success_returns_200(self, mock_build):
        mock_service = MagicMock()
        mock_service.logout.return_value = None
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "c" * 128},
        )

        assert resp.status_code == 200
        assert resp.json() == {"message": "Logout successful"}

    @patch("app.auth.api.routes._build_auth_service")
    def test_idempotent_logout(self, mock_build):
        """Logout always succeeds (domain layer is idempotent)."""
        mock_service = MagicMock()
        mock_service.logout.return_value = None
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp1 = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "d" * 128},
        )
        resp2 = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "d" * 128},
        )

        assert resp1.status_code == 200
        assert resp2.status_code == 200


# =============================================================================
# ME ENDPOINT (PROTECTED)
# =============================================================================


class TestGetMeIntegration:
    """Integration tests for GET /api/v1/auth/me (requires auth)."""

    def test_missing_identity_returns_401(self):
        """Without IdentityInjectionMiddleware, identity is missing → 401."""
        app = _create_test_app()
        # Register error handler for BaseError
        client = TestClient(app)

        resp = client.get("/api/v1/auth/me")

        # Without middleware, get_identity raises AuthenticationError → 401
        assert resp.status_code == 401

    @patch("app.auth.api.routes._build_auth_service")
    @patch("app.auth.api.routes.get_identity")
    def test_authenticated_admin_returns_profile(self, mock_get_identity, mock_build):
        now = datetime.now(timezone.utc)

        # Mock identity dependency
        identity = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=100,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=int(now.timestamp()),
            expires_at=int(now.timestamp()) + 900,
        )
        mock_get_identity.return_value = identity

        # Mock auth service
        mock_service = MagicMock()
        mock_service.get_current_user.return_value = _admin_profile()
        mock_build.return_value = mock_service

        app = _create_test_app()

        # Override the get_identity dependency
        from app.bootstrap.dependencies import get_identity as real_get_identity
        app.dependency_overrides[real_get_identity] = lambda: identity

        client = TestClient(app)
        resp = client.get("/api/v1/auth/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 1
        assert data["user_type"] == "admin"
        assert data["admin_id"] == 10
        assert data["admin_status"] == "active"

        # Cleanup
        app.dependency_overrides.clear()

    @patch("app.auth.api.routes._build_auth_service")
    def test_authenticated_candidate_returns_profile(self, mock_build):
        now = datetime.now(timezone.utc)

        identity = IdentityContext(
            user_id=2,
            user_type=UserType.CANDIDATE,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=int(now.timestamp()),
            expires_at=int(now.timestamp()) + 900,
        )

        mock_service = MagicMock()
        mock_service.get_current_user.return_value = _candidate_profile()
        mock_build.return_value = mock_service

        app = _create_test_app()

        from app.bootstrap.dependencies import get_identity as real_get_identity
        app.dependency_overrides[real_get_identity] = lambda: identity

        client = TestClient(app)
        resp = client.get("/api/v1/auth/me")

        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == 2
        assert data["user_type"] == "candidate"
        assert data["candidate_id"] == 20
        assert data["full_name"] == "Jane Doe"

        app.dependency_overrides.clear()


# =============================================================================
# ERROR RESPONSE FORMAT
# =============================================================================


class TestErrorResponseFormat:
    """Verify error response structure matches shared error format."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_authentication_error_structure(self, mock_build):
        mock_service = MagicMock()
        mock_service.login.side_effect = AuthenticationError(
            message="Invalid credentials",
            metadata={"reason": "invalid_password"},
        )
        mock_build.return_value = mock_service

        app = _create_test_app()
        client = TestClient(app)

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "user@co.com", "password": "wrong"},
        )

        assert resp.status_code == 401
        body = resp.json()
        # Structured error format: {"error": {"code", "message", "request_id", "metadata"}}
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_validation_error_structure_422(self):
        app = _create_test_app()
        client = TestClient(app)

        resp = client.post("/api/v1/auth/login", json={})

        assert resp.status_code == 422
        body = resp.json()
        # Validation error format from exception handler
        assert "error" in body
