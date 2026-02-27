"""
Integration Tests — Auth Contracts

Validates that Pydantic contract schemas integrate correctly with:
1. Domain layer data structures (AuthenticationResult, UserProfile)
2. JSON serialization/deserialization round-trips (simulating HTTP transport)
3. OpenAPI schema generation (FastAPI compatibility)
4. Cross-module contract compatibility with shared.auth_context enums

NOTE: auth/contracts is a pure schema layer with no database or persistence.
Integration tests focus on inter-layer compatibility, NOT DB operations.
"""

import json
import pytest
from datetime import datetime, timezone

from app.auth.contracts.schemas import (
    AdminRegistrationRequest,
    CandidateRegistrationRequest,
    LoginRequest,
    RefreshTokenRequest,
    LogoutRequest,
)
from app.auth.contracts.responses import (
    RegistrationResponse,
    UserProfileResponse,
    LoginResponse,
    TokenRefreshResponse,
    CurrentUserResponse,
    ErrorResponse,
)
from app.auth.contracts.enums import AuthErrorCode
from app.auth.contracts.claims import (
    AdminAccessTokenClaims,
    CandidateAccessTokenClaims,
)

# Domain layer imports — tests that contracts map correctly to domain types
from app.auth.domain.contracts import (
    RegisterAdminCommand,
    RegisterCandidateCommand,
    LoginCommand,
    RefreshTokenCommand,
    LogoutCommand,
    AuthenticationResult,
    UserProfile,
)
from app.shared.auth_context import UserType, AdminRole


# ============================================================================
# Contract ↔ Domain mapping tests
# ============================================================================

class TestContractToDomainMapping:
    """
    Verify that API contracts can be correctly mapped to domain commands.

    This is the integration boundary: API layer receives Pydantic models,
    maps them to frozen dataclass commands for the domain layer.
    """

    def test_admin_registration_to_command(self):
        """AdminRegistrationRequest maps to RegisterAdminCommand."""
        request = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
            full_name="John Doe",
        )

        command = RegisterAdminCommand(
            email=request.email,
            password=request.password,
            organization_id=request.organization_id,
            admin_role=request.admin_role,
            full_name=request.full_name,
            request_ip="127.0.0.1",
            request_user_agent="test-agent",
        )

        assert command.email == request.email
        assert command.password == request.password
        assert command.organization_id == request.organization_id
        assert command.admin_role == request.admin_role
        assert command.full_name == request.full_name

    def test_candidate_registration_to_command(self):
        """CandidateRegistrationRequest maps to RegisterCandidateCommand."""
        request = CandidateRegistrationRequest(
            email="candidate@example.com",
            password="SecurePass123!",
            full_name="Jane Smith",
            phone="+1-555-0123",
        )

        command = RegisterCandidateCommand(
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            phone=request.phone,
        )

        assert command.email == request.email
        assert command.full_name == request.full_name
        assert command.phone == request.phone

    def test_login_request_to_command(self):
        """LoginRequest maps to LoginCommand."""
        request = LoginRequest(
            email="user@example.com",
            password="MyPassword123!",
        )

        command = LoginCommand(
            email=request.email,
            password=request.password,
            request_ip="10.0.0.1",
            request_user_agent="Mozilla/5.0",
            device_info="Chrome 120",
        )

        assert command.email == request.email
        assert command.password == request.password

    def test_refresh_request_to_command(self):
        """RefreshTokenRequest maps to RefreshTokenCommand."""
        token = "a" * 64
        request = RefreshTokenRequest(refresh_token=token)

        command = RefreshTokenCommand(
            refresh_token=request.refresh_token,
            request_ip="10.0.0.1",
        )

        assert command.refresh_token == request.refresh_token

    def test_logout_request_to_command(self):
        """LogoutRequest maps to LogoutCommand."""
        token = "b" * 64
        request = LogoutRequest(refresh_token=token)

        command = LogoutCommand(
            refresh_token=request.refresh_token,
            request_ip="10.0.0.1",
        )

        assert command.refresh_token == request.refresh_token


# ============================================================================
# Domain → Response mapping tests
# ============================================================================

class TestDomainToResponseMapping:
    """
    Verify that domain results can be correctly mapped to response schemas.

    Domain layer returns frozen dataclasses; API layer converts to Pydantic.
    """

    def test_user_profile_to_response(self):
        """Domain UserProfile maps to UserProfileResponse."""
        profile = UserProfile(
            user_id=42,
            email="admin@company.com",
            user_type="admin",
            user_status="active",
            admin_id=10,
            organization_id=5,
            admin_role="admin",
            admin_status="active",
        )

        response = UserProfileResponse(
            user_id=profile.user_id,
            email=profile.email,
            user_type=profile.user_type,
            admin_id=profile.admin_id,
            organization_id=profile.organization_id,
            admin_role=profile.admin_role,
        )

        assert response.user_id == profile.user_id
        assert response.admin_role == profile.admin_role

    def test_auth_result_to_login_response(self):
        """Domain AuthenticationResult maps to LoginResponse."""
        domain_profile = UserProfile(
            user_id=1,
            email="admin@company.com",
            user_type="admin",
            user_status="active",
            admin_id=10,
            organization_id=5,
            admin_role="admin",
        )

        auth_result = AuthenticationResult(
            access_token="jwt.abc.def",
            refresh_token="x" * 64,
            token_type="Bearer",
            expires_in=900,
            user_profile=domain_profile,
        )

        response = LoginResponse(
            access_token=auth_result.access_token,
            refresh_token=auth_result.refresh_token,
            token_type=auth_result.token_type,
            expires_in=auth_result.expires_in,
            user=UserProfileResponse(
                user_id=domain_profile.user_id,
                email=domain_profile.email,
                user_type=domain_profile.user_type,
                admin_id=domain_profile.admin_id,
                organization_id=domain_profile.organization_id,
                admin_role=domain_profile.admin_role,
            ),
        )

        assert response.access_token == auth_result.access_token
        assert response.expires_in == auth_result.expires_in
        assert response.user.admin_role == "admin"

    def test_auth_result_to_token_refresh_response(self):
        """Domain AuthenticationResult maps to TokenRefreshResponse."""
        auth_result = AuthenticationResult(
            access_token="new.jwt.token",
            refresh_token="y" * 64,
            expires_in=900,
        )

        response = TokenRefreshResponse(
            access_token=auth_result.access_token,
            refresh_token=auth_result.refresh_token,
            expires_in=auth_result.expires_in,
        )

        assert response.access_token == auth_result.access_token


# ============================================================================
# JSON round-trip tests (simulating HTTP transport)
# ============================================================================

class TestJsonRoundTrip:
    """
    Validate that contracts survive JSON serialization/deserialization,
    as they would during actual HTTP request/response transport.
    """

    def test_admin_registration_request_round_trip(self):
        original = AdminRegistrationRequest(
            email="admin@company.com",
            password="SecurePass123!",
            organization_id=1,
            admin_role="admin",
            full_name="Test User",
        )
        json_str = original.model_dump_json()
        reconstructed = AdminRegistrationRequest.model_validate_json(json_str)
        assert reconstructed.email == original.email
        assert reconstructed.organization_id == original.organization_id
        assert reconstructed.admin_role == original.admin_role

    def test_login_response_round_trip(self):
        original = LoginResponse(
            access_token="jwt.token.value",
            refresh_token="r" * 64,
            expires_in=900,
            user=UserProfileResponse(
                user_id=42,
                email="admin@company.com",
                user_type="admin",
                admin_id=10,
                organization_id=5,
                admin_role="superadmin",
            ),
        )
        json_str = original.model_dump_json()
        reconstructed = LoginResponse.model_validate_json(json_str)
        assert reconstructed.user.user_id == 42
        assert reconstructed.user.admin_role == "superadmin"
        assert reconstructed.expires_in == 900

    def test_current_user_response_round_trip_with_datetime(self):
        dt = datetime(2026, 2, 13, 10, 30, 0, tzinfo=timezone.utc)
        original = CurrentUserResponse(
            user_id=1,
            email="admin@co.com",
            user_type="admin",
            user_status="active",
            admin_id=1,
            organization_id=1,
            admin_role="admin",
            admin_status="active",
            last_login_at=dt,
        )
        json_str = original.model_dump_json()
        reconstructed = CurrentUserResponse.model_validate_json(json_str)
        assert reconstructed.last_login_at is not None
        assert reconstructed.last_login_at.year == 2026

    def test_error_response_round_trip(self):
        original = ErrorResponse(
            error=AuthErrorCode.INVALID_CREDENTIALS.value,
            message="Bad credentials",
            details={"attempt": 3},
        )
        json_str = original.model_dump_json()
        reconstructed = ErrorResponse.model_validate_json(json_str)
        assert reconstructed.error == "invalid_credentials"
        assert reconstructed.details["attempt"] == 3

    def test_raw_json_deserialization(self):
        """Simulate receiving raw JSON from HTTP client."""
        raw_json = json.dumps({
            "email": "test@example.com",
            "password": "ValidPass123!",
        })
        request = LoginRequest.model_validate_json(raw_json)
        assert request.email == "test@example.com"


# ============================================================================
# Cross-module enum compatibility
# ============================================================================

class TestSharedEnumCompatibility:
    """
    Verify that contract Literal types align with shared.auth_context enums.

    The shared module defines UserType and AdminRole enums.
    Our Literal constraints must accept the same values.
    """

    def test_user_type_enum_values_match_profile_response(self):
        """UserType enum values accepted by UserProfileResponse.user_type."""
        for ut in UserType:
            profile = UserProfileResponse(
                user_id=1,
                email="test@example.com",
                user_type=ut.value,
            )
            assert profile.user_type == ut.value

    def test_admin_role_enum_values_accepted(self):
        """AdminRole enum values accepted by UserProfileResponse.admin_role."""
        for role in AdminRole:
            profile = UserProfileResponse(
                user_id=1,
                email="test@example.com",
                user_type="admin",
                admin_role=role.value,
            )
            assert profile.admin_role == role.value

    def test_admin_claims_role_values_match_enum(self):
        """AdminAccessTokenClaims role field accepts all AdminRole values."""
        for role in AdminRole:
            claims: AdminAccessTokenClaims = {
                "sub": 1,
                "type": "admin",
                "admin_id": 1,
                "organization_id": 1,
                "role": role.value,
                "iat": 1700000000,
                "exp": 1700003600,
                "jti": "test-jti",
                "token_version": 1,
            }
            assert claims["role"] == role.value


# ============================================================================
# OpenAPI schema generation
# ============================================================================

class TestOpenApiSchemaGeneration:
    """
    Verify that Pydantic models generate valid JSON schemas
    compatible with FastAPI's OpenAPI documentation.
    """

    def test_admin_registration_generates_schema(self):
        schema = AdminRegistrationRequest.model_json_schema()
        assert "properties" in schema
        assert "email" in schema["properties"]
        assert "password" in schema["properties"]
        assert "organization_id" in schema["properties"]
        assert "admin_role" in schema["properties"]

    def test_login_response_generates_schema(self):
        schema = LoginResponse.model_json_schema()
        assert "properties" in schema
        assert "access_token" in schema["properties"]
        assert "user" in schema["properties"]

    def test_error_response_generates_schema(self):
        schema = ErrorResponse.model_json_schema()
        assert "properties" in schema
        assert "error" in schema["properties"]
        assert "message" in schema["properties"]

    def test_current_user_response_generates_schema(self):
        schema = CurrentUserResponse.model_json_schema()
        props = schema["properties"]
        assert "last_login_at" in props
        assert "user_status" in props

    def test_all_request_schemas_have_required_fields(self):
        """All required Pydantic fields appear in JSON schema 'required'."""
        schema = AdminRegistrationRequest.model_json_schema()
        required = schema.get("required", [])
        assert "email" in required
        assert "password" in required
        assert "organization_id" in required
        assert "admin_role" in required
