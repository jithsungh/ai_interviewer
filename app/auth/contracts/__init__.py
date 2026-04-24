"""
Auth Contracts Layer

Defines strict Pydantic schemas for all auth-related API request/response contracts.
This is the single source of truth for auth API data transfer objects.

Public API:
- Request schemas: AdminRegistrationRequest, CandidateRegistrationRequest, LoginRequest,
  RefreshTokenRequest, LogoutRequest
- Response schemas: RegistrationResponse, LoginResponse, TokenRefreshResponse,
  CurrentUserResponse, UserProfileResponse, ErrorResponse
- JWT claim types: AdminAccessTokenClaims, CandidateAccessTokenClaims
- Error codes: AuthErrorCode

Dependencies:
- Pydantic: Schema validation
- app.config.constants: Password policy constants
- app.shared.auth_context: UserType, AdminRole (reuse existing enums)
"""

from .schemas import (
    # Request schemas
    AdminRegistrationRequest,
    CandidateRegistrationRequest,
    LoginRequest,
    RefreshTokenRequest,
    LogoutRequest,
    ChangePasswordRequest,
)

from .responses import (
    # Response schemas
    RegistrationResponse,
    UserProfileResponse,
    LoginResponse,
    TokenRefreshResponse,
    ChangePasswordResponse,
    CurrentUserResponse,
    ErrorResponse,
)

from .enums import AuthErrorCode

from .claims import (
    AdminAccessTokenClaims,
    CandidateAccessTokenClaims,
)

__all__ = [
    # Request schemas
    "AdminRegistrationRequest",
    "CandidateRegistrationRequest",
    "LoginRequest",
    "RefreshTokenRequest",
    "LogoutRequest",
    "ChangePasswordRequest",
    # Response schemas
    "RegistrationResponse",
    "UserProfileResponse",
    "LoginResponse",
    "TokenRefreshResponse",
    "ChangePasswordResponse",
    "CurrentUserResponse",
    "ErrorResponse",
    # Enums
    "AuthErrorCode",
    # JWT claims
    "AdminAccessTokenClaims",
    "CandidateAccessTokenClaims",
]
