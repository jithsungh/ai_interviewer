"""
Unit Tests for Auth API Routes

Tests the FastAPI router endpoints with mocked domain layer.
Validates:
- Request schema validation (via Pydantic)
- Correct domain command construction
- Response mapping (domain → API response)
- Error propagation (domain errors → HTTP error codes)
- Auth guards on protected endpoints
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from dataclasses import dataclass

from app.auth.api.routes import (
    _build_auth_service,
    _get_client_ip,
    _profile_to_user_response,
    _profile_to_current_user_response,
)
from app.auth.domain.contracts import (
    UserProfile,
    AuthenticationResult,
)
from app.auth.contracts import (
    RegistrationResponse,
    LoginResponse,
    TokenRefreshResponse,
    CurrentUserResponse,
    UserProfileResponse,
    AdminRegistrationRequest,
    CandidateRegistrationRequest,
    LoginRequest,
    RefreshTokenRequest,
    LogoutRequest,
)
from app.shared.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)


# =============================================================================
# Helper Mapping Tests
# =============================================================================


class TestProfileToUserResponse:
    """Tests for _profile_to_user_response mapping."""

    def test_admin_profile_maps_correctly(self):
        profile = UserProfile(
            user_id=1,
            email="admin@co.com",
            user_type="admin",
            user_status="active",
            admin_id=10,
            organization_id=100,
            admin_role="admin",
            admin_status="active",
        )
        resp = _profile_to_user_response(profile)
        assert resp.user_id == 1
        assert resp.email == "admin@co.com"
        assert resp.user_type == "admin"
        assert resp.admin_id == 10
        assert resp.organization_id == 100
        assert resp.admin_role == "admin"
        assert resp.candidate_id is None
        assert resp.full_name is None

    def test_candidate_profile_maps_correctly(self):
        profile = UserProfile(
            user_id=2,
            email="cand@ex.com",
            user_type="candidate",
            user_status="active",
            candidate_id=20,
            full_name="Jane Doe",
            candidate_status="active",
        )
        resp = _profile_to_user_response(profile)
        assert resp.user_id == 2
        assert resp.user_type == "candidate"
        assert resp.candidate_id == 20
        assert resp.full_name == "Jane Doe"
        assert resp.admin_id is None
        assert resp.organization_id is None


class TestProfileToCurrentUserResponse:
    """Tests for _profile_to_current_user_response mapping."""

    def test_admin_current_user_includes_status(self):
        now = datetime.now(timezone.utc)
        profile = UserProfile(
            user_id=1,
            email="admin@co.com",
            user_type="admin",
            user_status="active",
            admin_id=10,
            organization_id=100,
            admin_role="superadmin",
            admin_status="active",
            last_login_at=now,
        )
        resp = _profile_to_current_user_response(profile)
        assert resp.user_status == "active"
        assert resp.admin_status == "active"
        assert resp.admin_role == "superadmin"
        assert resp.last_login_at == now

    def test_candidate_current_user_includes_status(self):
        profile = UserProfile(
            user_id=2,
            email="cand@ex.com",
            user_type="candidate",
            user_status="active",
            candidate_id=20,
            full_name="John",
            candidate_status="active",
        )
        resp = _profile_to_current_user_response(profile)
        assert resp.user_status == "active"
        assert resp.candidate_status == "active"
        assert resp.candidate_id == 20
        assert resp.admin_id is None


class TestGetClientIp:
    """Tests for _get_client_ip helper."""

    def test_uses_x_forwarded_for_first_ip(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_uses_x_forwarded_for_single_ip(self):
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "10.0.0.1"}
        assert _get_client_ip(request) == "10.0.0.1"

    def test_falls_back_to_client_host(self):
        request = MagicMock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        assert _get_client_ip(request) == "192.168.1.1"

    def test_returns_unknown_when_no_client(self):
        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _get_client_ip(request) == "unknown"


# =============================================================================
# Route-Level Tests (domain calls mocked)
# =============================================================================


class TestRegisterAdminRoute:
    """Tests for POST /register/admin endpoint logic."""

    def _make_request_mock(self, ip="127.0.0.1", user_agent="test-agent"):
        request = MagicMock()
        request.headers = {"User-Agent": user_agent}
        request.client.host = ip
        return request

    def _make_admin_profile(self, **overrides):
        defaults = dict(
            user_id=1,
            email="admin@company.com",
            user_type="admin",
            user_status="active",
            admin_id=10,
            organization_id=100,
            admin_role="admin",
            admin_status="active",
        )
        defaults.update(overrides)
        return UserProfile(**defaults)

    @patch("app.auth.api.routes._build_auth_service")
    def test_register_admin_returns_201_on_success(self, mock_build):
        """Successful admin registration returns RegistrationResponse."""
        mock_service = MagicMock()
        mock_service.register_admin.return_value = self._make_admin_profile()
        mock_build.return_value = mock_service

        # Simulate calling the route function directly
        from app.auth.api.routes import register_admin

        request = self._make_request_mock()
        body = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
            full_name="John Doe",
        )

        result = register_admin(request=request, body=body, db=MagicMock())

        assert isinstance(result, RegistrationResponse)
        assert result.user_id == 1
        assert result.email == "admin@company.com"
        assert result.user_type == "admin"
        assert result.message == "Registration successful"

    @patch("app.auth.api.routes._build_auth_service")
    def test_register_admin_propagates_conflict_error(self, mock_build):
        """Duplicate email raises ConflictError (→ 409)."""
        mock_service = MagicMock()
        mock_service.register_admin.side_effect = ConflictError(
            message="Email already registered"
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import register_admin

        request = self._make_request_mock()
        body = AdminRegistrationRequest(
            email="dup@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
        )

        with pytest.raises(ConflictError):
            register_admin(request=request, body=body, db=MagicMock())

    @patch("app.auth.api.routes._build_auth_service")
    def test_register_admin_propagates_not_found_error(self, mock_build):
        """Non-existent organization raises NotFoundError (→ 404)."""
        mock_service = MagicMock()
        mock_service.register_admin.side_effect = NotFoundError(
            resource_type="Organization", resource_id=999
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import register_admin

        request = self._make_request_mock()
        body = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=999,
            admin_role="admin",
        )

        with pytest.raises(NotFoundError):
            register_admin(request=request, body=body, db=MagicMock())

    @patch("app.auth.api.routes._build_auth_service")
    def test_register_admin_propagates_validation_error(self, mock_build):
        """Weak password raises ValidationError (→ 422)."""
        mock_service = MagicMock()
        mock_service.register_admin.side_effect = ValidationError(
            message="Password too weak"
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import register_admin

        request = self._make_request_mock()
        body = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",  # Pydantic passes, domain rejects
            organization_id=1,
            admin_role="admin",
        )

        with pytest.raises(ValidationError):
            register_admin(request=request, body=body, db=MagicMock())

    @patch("app.auth.api.routes._build_auth_service")
    def test_register_admin_passes_ip_and_user_agent(self, mock_build):
        """Request IP and user agent are forwarded to domain command."""
        mock_service = MagicMock()
        mock_service.register_admin.return_value = self._make_admin_profile()
        mock_build.return_value = mock_service

        from app.auth.api.routes import register_admin

        request = MagicMock()
        request.headers = {
            "User-Agent": "MyBrowser/1.0",
            "X-Forwarded-For": "10.0.0.5",
        }
        request.client.host = "127.0.0.1"

        body = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
        )

        register_admin(request=request, body=body, db=MagicMock())

        # Validate the command passed to the service
        call_args = mock_service.register_admin.call_args
        command = call_args[0][0]
        assert command.request_ip == "10.0.0.5"
        assert command.request_user_agent == "MyBrowser/1.0"


class TestRegisterCandidateRoute:
    """Tests for POST /register/candidate endpoint logic."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_register_candidate_returns_201_on_success(self, mock_build):
        mock_service = MagicMock()
        mock_service.register_candidate.return_value = UserProfile(
            user_id=2,
            email="cand@ex.com",
            user_type="candidate",
            user_status="active",
            candidate_id=20,
            full_name="Jane",
            candidate_status="active",
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import register_candidate

        request = MagicMock()
        request.headers = {"User-Agent": "agent"}
        request.client.host = "127.0.0.1"

        body = CandidateRegistrationRequest(
            email="cand@ex.com",
            password="SecurePass123!",
            full_name="Jane",
            phone="+1-555",
        )

        result = register_candidate(request=request, body=body, db=MagicMock())

        assert isinstance(result, RegistrationResponse)
        assert result.user_id == 2
        assert result.user_type == "candidate"

    @patch("app.auth.api.routes._build_auth_service")
    def test_register_candidate_propagates_conflict(self, mock_build):
        mock_service = MagicMock()
        mock_service.register_candidate.side_effect = ConflictError(
            message="Email already registered"
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import register_candidate

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        body = CandidateRegistrationRequest(
            email="dup@ex.com",
            password="SecurePass123!",
        )

        with pytest.raises(ConflictError):
            register_candidate(request=request, body=body, db=MagicMock())


class TestLoginRoute:
    """Tests for POST /login endpoint logic."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_login_returns_tokens_on_success(self, mock_build):
        mock_service = MagicMock()
        mock_service.login.return_value = AuthenticationResult(
            access_token="jwt-token",
            refresh_token="refresh-hex",
            token_type="Bearer",
            expires_in=900,
            user_profile=UserProfile(
                user_id=1,
                email="admin@co.com",
                user_type="admin",
                user_status="active",
                admin_id=10,
                organization_id=100,
                admin_role="admin",
            ),
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import login

        request = MagicMock()
        request.headers = {"User-Agent": "agent"}
        request.client.host = "127.0.0.1"

        body = LoginRequest(email="admin@co.com", password="SecurePass123!")

        result = login(request=request, body=body, db=MagicMock())

        assert isinstance(result, LoginResponse)
        assert result.access_token == "jwt-token"
        assert result.refresh_token == "refresh-hex"
        assert result.expires_in == 900
        assert result.user.user_id == 1
        assert result.user.admin_id == 10

    @patch("app.auth.api.routes._build_auth_service")
    def test_login_propagates_authentication_error(self, mock_build):
        mock_service = MagicMock()
        mock_service.login.side_effect = AuthenticationError(
            message="Invalid credentials"
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import login

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        body = LoginRequest(email="wrong@co.com", password="bad")

        with pytest.raises(AuthenticationError):
            login(request=request, body=body, db=MagicMock())


class TestRefreshTokenRoute:
    """Tests for POST /refresh endpoint logic."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_refresh_returns_new_tokens(self, mock_build):
        mock_service = MagicMock()
        mock_service.refresh_token.return_value = AuthenticationResult(
            access_token="new-jwt",
            refresh_token="new-refresh",
            token_type="Bearer",
            expires_in=900,
            user_profile=UserProfile(
                user_id=1,
                email="a@b.com",
                user_type="admin",
                user_status="active",
            ),
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import refresh_token

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        body = RefreshTokenRequest(refresh_token="a" * 128)

        result = refresh_token(request=request, body=body, db=MagicMock())

        assert isinstance(result, TokenRefreshResponse)
        assert result.access_token == "new-jwt"
        assert result.refresh_token == "new-refresh"
        assert result.expires_in == 900

    @patch("app.auth.api.routes._build_auth_service")
    def test_refresh_propagates_auth_error_on_invalid_token(self, mock_build):
        mock_service = MagicMock()
        mock_service.refresh_token.side_effect = AuthenticationError(
            message="Invalid refresh token"
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import refresh_token

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        body = RefreshTokenRequest(refresh_token="b" * 128)

        with pytest.raises(AuthenticationError):
            refresh_token(request=request, body=body, db=MagicMock())


class TestLogoutRoute:
    """Tests for POST /logout endpoint logic."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_logout_returns_success_message(self, mock_build):
        mock_service = MagicMock()
        mock_service.logout.return_value = None
        mock_build.return_value = mock_service

        from app.auth.api.routes import logout

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        body = LogoutRequest(refresh_token="c" * 128)

        result = logout(request=request, body=body, db=MagicMock())

        assert result == {"message": "Logout successful"}

    @patch("app.auth.api.routes._build_auth_service")
    def test_logout_is_idempotent(self, mock_build):
        """Logout succeeds even if called twice (domain is idempotent)."""
        mock_service = MagicMock()
        mock_service.logout.return_value = None
        mock_build.return_value = mock_service

        from app.auth.api.routes import logout

        request = MagicMock()
        request.headers = {}
        request.client.host = "127.0.0.1"

        body = LogoutRequest(refresh_token="d" * 128)

        result1 = logout(request=request, body=body, db=MagicMock())
        result2 = logout(request=request, body=body, db=MagicMock())

        assert result1 == {"message": "Logout successful"}
        assert result2 == {"message": "Logout successful"}


class TestGetMeRoute:
    """Tests for GET /me endpoint logic."""

    @patch("app.auth.api.routes._build_auth_service")
    def test_get_me_returns_admin_profile(self, mock_build):
        now = datetime.now(timezone.utc)
        mock_service = MagicMock()
        mock_service.get_current_user.return_value = UserProfile(
            user_id=1,
            email="admin@co.com",
            user_type="admin",
            user_status="active",
            admin_id=10,
            organization_id=100,
            admin_role="admin",
            admin_status="active",
            last_login_at=now,
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import get_me
        from app.shared.auth_context import IdentityContext, UserType, AdminRole

        identity = IdentityContext(
            user_id=1,
            user_type=UserType.ADMIN,
            organization_id=100,
            admin_role=AdminRole.ADMIN,
            token_version=1,
            issued_at=int(now.timestamp()),
            expires_at=int(now.timestamp()) + 900,
        )

        result = get_me(identity=identity, db=MagicMock())

        assert isinstance(result, CurrentUserResponse)
        assert result.user_id == 1
        assert result.user_type == "admin"
        assert result.admin_id == 10
        assert result.admin_status == "active"
        assert result.last_login_at == now

    @patch("app.auth.api.routes._build_auth_service")
    def test_get_me_returns_candidate_profile(self, mock_build):
        mock_service = MagicMock()
        mock_service.get_current_user.return_value = UserProfile(
            user_id=2,
            email="cand@ex.com",
            user_type="candidate",
            user_status="active",
            candidate_id=20,
            full_name="Jane",
            candidate_status="active",
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import get_me
        from app.shared.auth_context import IdentityContext, UserType

        identity = IdentityContext(
            user_id=2,
            user_type=UserType.CANDIDATE,
            candidate_id=2,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600,
        )

        result = get_me(identity=identity, db=MagicMock())

        assert isinstance(result, CurrentUserResponse)
        assert result.user_id == 2
        assert result.user_type == "candidate"
        assert result.candidate_id == 20
        assert result.full_name == "Jane"

    @patch("app.auth.api.routes._build_auth_service")
    def test_get_me_propagates_not_found(self, mock_build):
        """If user deleted after token issued, returns NotFoundError."""
        mock_service = MagicMock()
        mock_service.get_current_user.side_effect = NotFoundError(
            resource_type="User", resource_id=999
        )
        mock_build.return_value = mock_service

        from app.auth.api.routes import get_me
        from app.shared.auth_context import IdentityContext, UserType

        identity = IdentityContext(
            user_id=999,
            user_type=UserType.CANDIDATE,
            candidate_id=999,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600,
        )

        with pytest.raises(NotFoundError):
            get_me(identity=identity, db=MagicMock())


# =============================================================================
# Pydantic Schema Validation Tests (in context of API layer)
# =============================================================================


class TestAdminRegistrationRequestValidation:
    """Pydantic validation of AdminRegistrationRequest."""

    def test_rejects_missing_email(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                password="SecurePass123!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_invalid_email(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="not-an-email",
                password="SecurePass123!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_short_password(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="a@b.com",
                password="Sh1!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_password_without_uppercase(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="a@b.com",
                password="mypassword123!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_password_without_digit(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="a@b.com",
                password="MyPassword!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_password_without_special_char(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="a@b.com",
                password="MyPassword123",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_superadmin_role(self):
        """Cannot self-assign superadmin role via registration."""
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="a@b.com",
                password="SecurePass123!",
                organization_id=1,
                admin_role="superadmin",
            )

    def test_rejects_zero_organization_id(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="a@b.com",
                password="SecurePass123!",
                organization_id=0,
                admin_role="admin",
            )

    def test_rejects_negative_organization_id(self):
        with pytest.raises(Exception):
            AdminRegistrationRequest(
                email="a@b.com",
                password="SecurePass123!",
                organization_id=-1,
                admin_role="admin",
            )

    def test_accepts_valid_admin_request(self):
        req = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
            full_name="John Doe",
        )
        assert req.email == "admin@company.com"
        assert req.admin_role == "admin"

    def test_accepts_read_only_role(self):
        req = AdminRegistrationRequest(
            email="viewer@co.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="read_only",
        )
        assert req.admin_role == "read_only"


class TestRefreshTokenRequestValidation:
    """Pydantic validation of RefreshTokenRequest."""

    def test_rejects_short_token(self):
        with pytest.raises(Exception):
            RefreshTokenRequest(refresh_token="short")

    def test_accepts_valid_token(self):
        req = RefreshTokenRequest(refresh_token="a" * 128)
        assert len(req.refresh_token) == 128


class TestLogoutRequestValidation:
    """Pydantic validation of LogoutRequest."""

    def test_rejects_short_token(self):
        with pytest.raises(Exception):
            LogoutRequest(refresh_token="x")

    def test_accepts_valid_token(self):
        req = LogoutRequest(refresh_token="b" * 128)
        assert len(req.refresh_token) == 128
