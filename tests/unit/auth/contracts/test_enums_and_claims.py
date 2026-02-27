"""
Unit Tests — Auth Contracts: Enums and JWT Claims

Validates AuthErrorCode enum completeness, JWT claim type structures,
and contract invariants.
"""

import pytest

from app.auth.contracts.enums import AuthErrorCode
from app.auth.contracts.claims import (
    AdminAccessTokenClaims,
    CandidateAccessTokenClaims,
)


# ============================================================================
# AuthErrorCode
# ============================================================================

class TestAuthErrorCode:
    """Tests for AuthErrorCode enum."""

    def test_is_string_enum(self):
        """AuthErrorCode values are strings for JSON serialization."""
        assert isinstance(AuthErrorCode.INVALID_CREDENTIALS, str)
        assert AuthErrorCode.INVALID_CREDENTIALS == "invalid_credentials"

    def test_all_authentication_errors_present(self):
        auth_errors = [
            "INVALID_CREDENTIALS",
            "USER_INACTIVE",
            "USER_BANNED",
            "ADMIN_INACTIVE",
            "ORG_SUSPENDED",
            "ORG_INACTIVE",
        ]
        for name in auth_errors:
            assert hasattr(AuthErrorCode, name), f"Missing: {name}"

    def test_all_token_errors_present(self):
        token_errors = [
            "TOKEN_EXPIRED",
            "TOKEN_INVALID",
            "TOKEN_REVOKED",
            "REFRESH_TOKEN_INVALID",
            "REFRESH_TOKEN_EXPIRED",
        ]
        for name in token_errors:
            assert hasattr(AuthErrorCode, name), f"Missing: {name}"

    def test_all_registration_errors_present(self):
        reg_errors = [
            "EMAIL_ALREADY_EXISTS",
            "PASSWORD_TOO_WEAK",
            "ORG_NOT_FOUND",
        ]
        for name in reg_errors:
            assert hasattr(AuthErrorCode, name), f"Missing: {name}"

    def test_all_authorization_errors_present(self):
        assert hasattr(AuthErrorCode, "INSUFFICIENT_PERMISSIONS")
        assert hasattr(AuthErrorCode, "MISSING_TOKEN")

    def test_all_security_errors_present(self):
        assert hasattr(AuthErrorCode, "SUSPICIOUS_ACTIVITY")
        assert hasattr(AuthErrorCode, "RATE_LIMIT_EXCEEDED")

    def test_values_are_lowercase_snake_case(self):
        for member in AuthErrorCode:
            assert member.value == member.value.lower(), f"{member.name} value not lowercase"
            assert " " not in member.value, f"{member.name} value has spaces"

    def test_values_are_unique(self):
        values = [m.value for m in AuthErrorCode]
        assert len(values) == len(set(values)), "Duplicate enum values detected"

    def test_total_count(self):
        """Ensure we have all 18 error codes from requirements."""
        assert len(AuthErrorCode) == 18

    def test_enum_iteration(self):
        """AuthErrorCode should be iterable."""
        codes = list(AuthErrorCode)
        assert len(codes) > 0

    def test_lookup_by_value(self):
        code = AuthErrorCode("invalid_credentials")
        assert code == AuthErrorCode.INVALID_CREDENTIALS

    def test_lookup_by_name(self):
        code = AuthErrorCode["INVALID_CREDENTIALS"]
        assert code.value == "invalid_credentials"

    def test_invalid_lookup_raises(self):
        with pytest.raises(ValueError):
            AuthErrorCode("nonexistent_code")


# ============================================================================
# AdminAccessTokenClaims
# ============================================================================

class TestAdminAccessTokenClaims:
    """Tests for AdminAccessTokenClaims TypedDict."""

    def test_valid_admin_claims(self):
        claims: AdminAccessTokenClaims = {
            "sub": 42,
            "type": "admin",
            "admin_id": 10,
            "organization_id": 5,
            "role": "admin",
            "iat": 1700000000,
            "exp": 1700003600,
            "jti": "uuid-string-here",
            "token_version": 3,
        }
        assert claims["sub"] == 42
        assert claims["type"] == "admin"
        assert claims["organization_id"] == 5
        assert claims["role"] == "admin"
        assert claims["token_version"] == 3

    def test_superadmin_claims(self):
        claims: AdminAccessTokenClaims = {
            "sub": 1,
            "type": "admin",
            "admin_id": 1,
            "organization_id": 1,
            "role": "superadmin",
            "iat": 1700000000,
            "exp": 1700003600,
            "jti": "jti-1",
            "token_version": 1,
        }
        assert claims["role"] == "superadmin"

    def test_required_keys(self):
        """AdminAccessTokenClaims TypedDict has all expected keys."""
        expected_keys = {
            "sub", "type", "admin_id", "organization_id",
            "role", "iat", "exp", "jti", "token_version",
        }
        actual_keys = set(AdminAccessTokenClaims.__annotations__.keys())
        assert expected_keys == actual_keys


# ============================================================================
# CandidateAccessTokenClaims
# ============================================================================

class TestCandidateAccessTokenClaims:
    """Tests for CandidateAccessTokenClaims TypedDict."""

    def test_valid_candidate_claims(self):
        claims: CandidateAccessTokenClaims = {
            "sub": 123,
            "type": "candidate",
            "candidate_id": 50,
            "iat": 1700000000,
            "exp": 1700003600,
            "jti": "uuid-candidate",
            "token_version": 1,
        }
        assert claims["sub"] == 123
        assert claims["type"] == "candidate"
        assert claims["candidate_id"] == 50

    def test_required_keys(self):
        expected_keys = {
            "sub", "type", "candidate_id",
            "iat", "exp", "jti", "token_version",
        }
        actual_keys = set(CandidateAccessTokenClaims.__annotations__.keys())
        assert expected_keys == actual_keys

    def test_no_organization_id(self):
        """Candidate claims must NOT have organization_id."""
        assert "organization_id" not in CandidateAccessTokenClaims.__annotations__

    def test_no_admin_id(self):
        """Candidate claims must NOT have admin_id."""
        assert "admin_id" not in CandidateAccessTokenClaims.__annotations__

    def test_no_role(self):
        """Candidate claims must NOT have role."""
        assert "role" not in CandidateAccessTokenClaims.__annotations__


# ============================================================================
# Cross-contract invariants
# ============================================================================

class TestContractInvariants:
    """Tests for cross-contract security and consistency invariants."""

    def test_no_password_in_any_response(self):
        """INVARIANT: No response schema contains password or password_hash."""
        from app.auth.contracts.responses import (
            RegistrationResponse,
            UserProfileResponse,
            LoginResponse,
            TokenRefreshResponse,
            CurrentUserResponse,
            ErrorResponse,
        )

        response_models = [
            RegistrationResponse,
            UserProfileResponse,
            LoginResponse,
            TokenRefreshResponse,
            CurrentUserResponse,
            ErrorResponse,
        ]

        forbidden_fields = {"password", "password_hash", "secret", "private_key"}

        for model in response_models:
            model_fields = set(model.model_fields.keys())
            overlap = model_fields & forbidden_fields
            assert not overlap, (
                f"{model.__name__} contains forbidden field(s): {overlap}"
            )

    def test_admin_claims_have_organization_id(self):
        """INVARIANT: Admin tokens always have organization_id."""
        assert "organization_id" in AdminAccessTokenClaims.__annotations__

    def test_candidate_claims_lack_organization_id(self):
        """INVARIANT: Candidate tokens never have organization_id."""
        assert "organization_id" not in CandidateAccessTokenClaims.__annotations__

    def test_admin_claims_have_role(self):
        """INVARIANT: Admin tokens always have role."""
        assert "role" in AdminAccessTokenClaims.__annotations__

    def test_import_from_package(self):
        """All public contracts importable from app.auth.contracts."""
        from app.auth.contracts import (
            AdminRegistrationRequest,
            CandidateRegistrationRequest,
            LoginRequest,
            RefreshTokenRequest,
            LogoutRequest,
            RegistrationResponse,
            UserProfileResponse,
            LoginResponse,
            TokenRefreshResponse,
            CurrentUserResponse,
            ErrorResponse,
            AuthErrorCode,
            AdminAccessTokenClaims,
            CandidateAccessTokenClaims,
        )
        # If we get here, all imports succeeded
        assert AdminRegistrationRequest is not None
        assert AuthErrorCode is not None
