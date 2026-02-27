"""
Unit Tests — Auth Contracts: Request Schemas

Validates Pydantic request schema validation, password complexity,
field constraints, and edge cases.
"""

import pytest
from pydantic import ValidationError

from app.auth.contracts.schemas import (
    AdminRegistrationRequest,
    CandidateRegistrationRequest,
    LoginRequest,
    RefreshTokenRequest,
    LogoutRequest,
)


# ============================================================================
# AdminRegistrationRequest
# ============================================================================

class TestAdminRegistrationRequest:
    """Tests for AdminRegistrationRequest schema."""

    def test_valid_admin_registration(self):
        req = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
            full_name="John Doe",
        )
        assert req.email == "admin@company.com"
        assert req.password == "SecurePass123!"
        assert req.organization_id == 1
        assert req.admin_role == "admin"
        assert req.full_name == "John Doe"

    def test_valid_admin_registration_read_only(self):
        req = AdminRegistrationRequest(
            email="viewer@company.com",
            password="ViewerPass1!",
            organization_id=5,
            admin_role="read_only",
        )
        assert req.admin_role == "read_only"
        assert req.full_name is None

    def test_rejects_superadmin_role(self):
        with pytest.raises(ValidationError) as exc_info:
            AdminRegistrationRequest(
                email="admin@company.com",
                password="SecurePass123!",
                organization_id=1,
                admin_role="superadmin",
            )
        errors = exc_info.value.errors()
        assert any("admin_role" in str(e.get("loc", "")) for e in errors)

    def test_rejects_invalid_role(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="admin@company.com",
                password="SecurePass123!",
                organization_id=1,
                admin_role="manager",
            )

    def test_rejects_missing_email(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                password="SecurePass123!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="not-an-email",
                password="SecurePass123!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_missing_password(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="admin@company.com",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_short_password(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="admin@company.com",
                password="Sh1!",
                organization_id=1,
                admin_role="admin",
            )

    def test_rejects_password_no_uppercase(self):
        with pytest.raises(ValidationError) as exc_info:
            AdminRegistrationRequest(
                email="admin@company.com",
                password="lowercase123!",
                organization_id=1,
                admin_role="admin",
            )
        assert "uppercase" in str(exc_info.value).lower()

    def test_rejects_password_no_lowercase(self):
        with pytest.raises(ValidationError) as exc_info:
            AdminRegistrationRequest(
                email="admin@company.com",
                password="UPPERCASE123!",
                organization_id=1,
                admin_role="admin",
            )
        assert "lowercase" in str(exc_info.value).lower()

    def test_rejects_password_no_digit(self):
        with pytest.raises(ValidationError) as exc_info:
            AdminRegistrationRequest(
                email="admin@company.com",
                password="NoDigitHere!",
                organization_id=1,
                admin_role="admin",
            )
        assert "digit" in str(exc_info.value).lower()

    def test_rejects_password_no_special(self):
        with pytest.raises(ValidationError) as exc_info:
            AdminRegistrationRequest(
                email="admin@company.com",
                password="NoSpecial123",
                organization_id=1,
                admin_role="admin",
            )
        assert "special" in str(exc_info.value).lower()

    def test_rejects_zero_organization_id(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="admin@company.com",
                password="SecurePass123!",
                organization_id=0,
                admin_role="admin",
            )

    def test_rejects_negative_organization_id(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="admin@company.com",
                password="SecurePass123!",
                organization_id=-1,
                admin_role="admin",
            )

    def test_rejects_missing_organization_id(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="admin@company.com",
                password="SecurePass123!",
                admin_role="admin",
            )

    def test_full_name_optional(self):
        req = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
        )
        assert req.full_name is None

    def test_full_name_max_length(self):
        with pytest.raises(ValidationError):
            AdminRegistrationRequest(
                email="admin@company.com",
                password="SecurePass123!",
                organization_id=1,
                admin_role="admin",
                full_name="A" * 256,
            )

    def test_email_normalized(self):
        """EmailStr normalizes domain to lowercase."""
        req = AdminRegistrationRequest(
            email="Admin@Company.COM",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
        )
        assert req.email == "Admin@company.com"

    def test_json_serialization(self):
        req = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
        )
        data = req.model_dump()
        assert isinstance(data, dict)
        assert data["email"] == "admin@company.com"
        assert data["organization_id"] == 1


# ============================================================================
# CandidateRegistrationRequest
# ============================================================================

class TestCandidateRegistrationRequest:
    """Tests for CandidateRegistrationRequest schema."""

    def test_valid_candidate_registration(self):
        req = CandidateRegistrationRequest(
            email="candidate@example.com",
            password="SecurePass123!",
            full_name="Jane Smith",
            phone="+1-555-0123",
        )
        assert req.email == "candidate@example.com"
        assert req.full_name == "Jane Smith"
        assert req.phone == "+1-555-0123"

    def test_minimal_candidate_registration(self):
        req = CandidateRegistrationRequest(
            email="candidate@example.com",
            password="SecurePass123!",
        )
        assert req.full_name is None
        assert req.phone is None

    def test_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            CandidateRegistrationRequest(
                email="bad-email",
                password="SecurePass123!",
            )

    def test_password_complexity_enforced(self):
        with pytest.raises(ValidationError):
            CandidateRegistrationRequest(
                email="c@example.com",
                password="toosimple",
            )

    def test_phone_max_length(self):
        with pytest.raises(ValidationError):
            CandidateRegistrationRequest(
                email="c@example.com",
                password="SecurePass123!",
                phone="+" + "1" * 50,
            )

    def test_full_name_max_length(self):
        with pytest.raises(ValidationError):
            CandidateRegistrationRequest(
                email="c@example.com",
                password="SecurePass123!",
                full_name="A" * 256,
            )


# ============================================================================
# LoginRequest
# ============================================================================

class TestLoginRequest:
    """Tests for LoginRequest schema."""

    def test_valid_login(self):
        req = LoginRequest(
            email="user@example.com",
            password="MyPassword123!",
        )
        assert req.email == "user@example.com"
        assert req.password == "MyPassword123!"

    def test_rejects_missing_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(password="MyPassword123!")

    def test_rejects_missing_password(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com")

    def test_rejects_invalid_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="not-email", password="pass")

    def test_rejects_empty_password(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="user@example.com", password="")

    def test_no_password_complexity_on_login(self):
        """Login should NOT enforce password complexity — only minimum length=1."""
        req = LoginRequest(
            email="user@example.com",
            password="x",
        )
        assert req.password == "x"


# ============================================================================
# RefreshTokenRequest
# ============================================================================

class TestRefreshTokenRequest:
    """Tests for RefreshTokenRequest schema."""

    def test_valid_refresh_token(self):
        token = "a" * 64
        req = RefreshTokenRequest(refresh_token=token)
        assert req.refresh_token == token

    def test_rejects_short_token(self):
        with pytest.raises(ValidationError):
            RefreshTokenRequest(refresh_token="short")

    def test_rejects_too_long_token(self):
        with pytest.raises(ValidationError):
            RefreshTokenRequest(refresh_token="a" * 257)

    def test_minimum_length_boundary(self):
        token = "a" * 32
        req = RefreshTokenRequest(refresh_token=token)
        assert len(req.refresh_token) == 32

    def test_maximum_length_boundary(self):
        token = "a" * 256
        req = RefreshTokenRequest(refresh_token=token)
        assert len(req.refresh_token) == 256

    def test_rejects_missing_token(self):
        with pytest.raises(ValidationError):
            RefreshTokenRequest()


# ============================================================================
# LogoutRequest
# ============================================================================

class TestLogoutRequest:
    """Tests for LogoutRequest schema."""

    def test_valid_logout(self):
        token = "b" * 64
        req = LogoutRequest(refresh_token=token)
        assert req.refresh_token == token

    def test_rejects_short_token(self):
        with pytest.raises(ValidationError):
            LogoutRequest(refresh_token="x" * 10)

    def test_rejects_too_long_token(self):
        with pytest.raises(ValidationError):
            LogoutRequest(refresh_token="x" * 257)
