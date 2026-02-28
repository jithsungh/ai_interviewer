"""
Unit Tests — Auth Contracts: Response Schemas

Validates Pydantic response schema construction, serialization,
field constraints, and security invariants.
"""

import pytest
from datetime import datetime, timezone
from pydantic import ValidationError

from app.auth.contracts.responses import (
    RegistrationResponse,
    UserProfileResponse,
    LoginResponse,
    TokenRefreshResponse,
    CurrentUserResponse,
    ErrorResponse,
)


# ============================================================================
# UserProfileResponse
# ============================================================================

class TestUserProfileResponse:
    """Tests for UserProfileResponse schema."""

    def test_admin_profile(self):
        profile = UserProfileResponse(
            user_id=1,
            email="admin@company.com",
            user_type="admin",
            admin_id=10,
            organization_id=5,
            admin_role="admin",
        )
        assert profile.user_id == 1
        assert profile.user_type == "admin"
        assert profile.admin_id == 10
        assert profile.organization_id == 5
        assert profile.admin_role == "admin"
        assert profile.candidate_id is None
        assert profile.full_name is None

    def test_candidate_profile(self):
        profile = UserProfileResponse(
            user_id=2,
            email="candidate@example.com",
            user_type="candidate",
            candidate_id=20,
            full_name="Jane Smith",
        )
        assert profile.user_type == "candidate"
        assert profile.candidate_id == 20
        assert profile.full_name == "Jane Smith"
        assert profile.admin_id is None
        assert profile.organization_id is None
        assert profile.admin_role is None

    def test_superadmin_profile(self):
        profile = UserProfileResponse(
            user_id=3,
            email="super@company.com",
            user_type="admin",
            admin_id=1,
            organization_id=1,
            admin_role="superadmin",
        )
        assert profile.admin_role == "superadmin"

    def test_rejects_invalid_user_type(self):
        with pytest.raises(ValidationError):
            UserProfileResponse(
                user_id=1,
                email="x@x.com",
                user_type="manager",
            )

    def test_rejects_invalid_admin_role(self):
        with pytest.raises(ValidationError):
            UserProfileResponse(
                user_id=1,
                email="x@x.com",
                user_type="admin",
                admin_role="owner",
            )

    def test_json_serialization(self):
        profile = UserProfileResponse(
            user_id=1,
            email="admin@company.com",
            user_type="admin",
        )
        data = profile.model_dump()
        assert isinstance(data, dict)
        assert data["user_id"] == 1

    def test_json_round_trip(self):
        profile = UserProfileResponse(
            user_id=1,
            email="admin@company.com",
            user_type="admin",
            admin_id=10,
            organization_id=5,
            admin_role="admin",
        )
        json_str = profile.model_dump_json()
        reconstructed = UserProfileResponse.model_validate_json(json_str)
        assert reconstructed.user_id == profile.user_id
        assert reconstructed.admin_role == profile.admin_role

    def test_no_password_field(self):
        """Security invariant: no password in response schemas."""
        fields = UserProfileResponse.model_fields
        assert "password" not in fields
        assert "password_hash" not in fields


# ============================================================================
# RegistrationResponse
# ============================================================================

class TestRegistrationResponse:
    """Tests for RegistrationResponse schema."""

    def test_admin_registration_response(self):
        resp = RegistrationResponse(
            user_id=42,
            email="admin@company.com",
            user_type="admin",
        )
        assert resp.user_id == 42
        assert resp.message == "Registration successful"

    def test_candidate_registration_response(self):
        resp = RegistrationResponse(
            user_id=43,
            email="c@example.com",
            user_type="candidate",
            message="Welcome!",
        )
        assert resp.message == "Welcome!"

    def test_rejects_invalid_user_type(self):
        with pytest.raises(ValidationError):
            RegistrationResponse(
                user_id=1,
                email="x@x.com",
                user_type="unknown",
            )

    def test_no_password_field(self):
        fields = RegistrationResponse.model_fields
        assert "password" not in fields
        assert "password_hash" not in fields


# ============================================================================
# LoginResponse
# ============================================================================

class TestLoginResponse:
    """Tests for LoginResponse schema."""

    def test_valid_login_response(self):
        resp = LoginResponse(
            access_token="jwt.token.here",
            refresh_token="a" * 64,
            expires_in=900,
            user=UserProfileResponse(
                user_id=1,
                email="admin@company.com",
                user_type="admin",
                admin_id=10,
                organization_id=5,
                admin_role="admin",
            ),
        )
        assert resp.access_token == "jwt.token.here"
        assert resp.token_type == "Bearer"
        assert resp.expires_in == 900
        assert resp.user.user_id == 1
        assert resp.user.admin_role == "admin"

    def test_default_token_type(self):
        resp = LoginResponse(
            access_token="jwt",
            refresh_token="r" * 64,
            expires_in=900,
            user=UserProfileResponse(
                user_id=1,
                email="u@x.com",
                user_type="candidate",
            ),
        )
        assert resp.token_type == "Bearer"

    def test_rejects_missing_user(self):
        with pytest.raises(ValidationError):
            LoginResponse(
                access_token="jwt",
                refresh_token="r" * 64,
                expires_in=900,
            )

    def test_rejects_missing_access_token(self):
        with pytest.raises(ValidationError):
            LoginResponse(
                refresh_token="r" * 64,
                expires_in=900,
                user=UserProfileResponse(
                    user_id=1, email="u@x.com", user_type="candidate"
                ),
            )

    def test_json_serialization(self):
        resp = LoginResponse(
            access_token="jwt.token",
            refresh_token="r" * 64,
            expires_in=900,
            user=UserProfileResponse(
                user_id=1,
                email="admin@company.com",
                user_type="admin",
            ),
        )
        data = resp.model_dump()
        assert "user" in data
        assert data["user"]["user_id"] == 1

    def test_no_password_field(self):
        fields = LoginResponse.model_fields
        assert "password" not in fields
        assert "password_hash" not in fields


# ============================================================================
# TokenRefreshResponse
# ============================================================================

class TestTokenRefreshResponse:
    """Tests for TokenRefreshResponse schema."""

    def test_valid_refresh_response(self):
        resp = TokenRefreshResponse(
            access_token="new.jwt.token",
            refresh_token="new-refresh-" + "x" * 52,
            expires_in=900,
        )
        assert resp.access_token == "new.jwt.token"
        assert resp.token_type == "Bearer"
        assert resp.expires_in == 900

    def test_rejects_missing_access_token(self):
        with pytest.raises(ValidationError):
            TokenRefreshResponse(
                refresh_token="r" * 64,
                expires_in=900,
            )

    def test_rejects_missing_refresh_token(self):
        with pytest.raises(ValidationError):
            TokenRefreshResponse(
                access_token="jwt",
                expires_in=900,
            )


# ============================================================================
# CurrentUserResponse
# ============================================================================

class TestCurrentUserResponse:
    """Tests for CurrentUserResponse schema."""

    def test_admin_current_user(self):
        resp = CurrentUserResponse(
            user_id=1,
            email="admin@company.com",
            user_type="admin",
            user_status="active",
            admin_id=10,
            organization_id=5,
            admin_role="admin",
            admin_status="active",
            last_login_at=datetime(2026, 2, 13, 10, 30, 0, tzinfo=timezone.utc),
        )
        assert resp.user_status == "active"
        assert resp.admin_status == "active"
        assert resp.last_login_at is not None

    def test_candidate_current_user(self):
        resp = CurrentUserResponse(
            user_id=2,
            email="c@example.com",
            user_type="candidate",
            user_status="active",
            candidate_id=20,
            full_name="Jane",
            candidate_status="active",
        )
        assert resp.candidate_id == 20
        assert resp.admin_id is None

    def test_rejects_invalid_user_status(self):
        with pytest.raises(ValidationError):
            CurrentUserResponse(
                user_id=1,
                email="x@x.com",
                user_type="admin",
                user_status="deleted",
            )

    def test_rejects_invalid_admin_status(self):
        with pytest.raises(ValidationError):
            CurrentUserResponse(
                user_id=1,
                email="x@x.com",
                user_type="admin",
                user_status="active",
                admin_status="deleted",
            )

    def test_banned_user_status(self):
        resp = CurrentUserResponse(
            user_id=1,
            email="bad@x.com",
            user_type="candidate",
            user_status="banned",
        )
        assert resp.user_status == "banned"

    def test_last_login_at_optional(self):
        resp = CurrentUserResponse(
            user_id=1,
            email="x@x.com",
            user_type="candidate",
            user_status="active",
        )
        assert resp.last_login_at is None

    def test_datetime_serialization(self):
        dt = datetime(2026, 2, 13, 10, 30, 0, tzinfo=timezone.utc)
        resp = CurrentUserResponse(
            user_id=1,
            email="x@x.com",
            user_type="admin",
            user_status="active",
            last_login_at=dt,
        )
        data = resp.model_dump(mode="json")
        assert isinstance(data["last_login_at"], str)

    def test_no_password_field(self):
        fields = CurrentUserResponse.model_fields
        assert "password" not in fields
        assert "password_hash" not in fields


# ============================================================================
# ErrorResponse
# ============================================================================

class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_basic_error(self):
        resp = ErrorResponse(
            error="invalid_credentials",
            message="Email or password is incorrect",
        )
        assert resp.error == "invalid_credentials"
        assert resp.details is None

    def test_error_with_details(self):
        resp = ErrorResponse(
            error="validation_error",
            message="Password too weak",
            details={"field": "password", "constraint": "min_length"},
        )
        assert resp.details["field"] == "password"

    def test_json_serialization(self):
        resp = ErrorResponse(
            error="token_expired",
            message="Access token has expired",
        )
        data = resp.model_dump()
        assert data["error"] == "token_expired"
        assert data["details"] is None

    def test_rejects_missing_error(self):
        with pytest.raises(ValidationError):
            ErrorResponse(message="Something went wrong")

    def test_rejects_missing_message(self):
        with pytest.raises(ValidationError):
            ErrorResponse(error="some_error")
