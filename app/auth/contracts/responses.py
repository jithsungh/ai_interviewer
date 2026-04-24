"""
Auth Response Schemas

Pydantic models for auth API response payloads.
These are the public contracts returned to API consumers.

SECURITY INVARIANTS:
- No response schema contains `password` or `password_hash`
- Token fields should never be logged (handled by observability/redaction)
"""

from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field


class UserProfileResponse(BaseModel):
    """
    User profile embedded in auth responses.

    Fields are conditionally populated based on user_type:
    - admin: admin_id, organization_id, admin_role are set
    - candidate: candidate_id, full_name are set
    """

    user_id: int = Field(..., description="User primary key")
    email: str = Field(..., description="User email address")
    user_type: Literal["admin", "candidate"] = Field(
        ..., description="User classification"
    )

    # Admin-specific fields (None for candidates)
    admin_id: Optional[int] = Field(
        None, description="Admin record ID (admin only)"
    )
    organization_id: Optional[int] = Field(
        None, description="Organization ID (admin only)"
    )
    admin_role: Optional[Literal["superadmin", "admin", "read_only"]] = Field(
        None, description="Admin role (admin only)"
    )

    # Candidate-specific fields (None for admins)
    candidate_id: Optional[int] = Field(
        None, description="Candidate record ID (candidate only)"
    )
    full_name: Optional[str] = Field(
        None, description="Candidate display name (candidate only)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": 123,
                    "email": "admin@company.com",
                    "user_type": "admin",
                    "admin_id": 1,
                    "organization_id": 1,
                    "admin_role": "admin",
                    "candidate_id": None,
                    "full_name": None,
                }
            ]
        }
    }


class RegistrationResponse(BaseModel):
    """
    Response returned after successful user registration.
    """

    user_id: int = Field(..., description="Newly created user ID")
    email: str = Field(..., description="Registered email address")
    user_type: Literal["admin", "candidate"] = Field(
        ..., description="Registered user type"
    )
    message: str = Field(
        default="Registration successful",
        description="Human-readable confirmation message",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": 123,
                    "email": "user@example.com",
                    "user_type": "admin",
                    "message": "Registration successful",
                }
            ]
        }
    }


class LoginResponse(BaseModel):
    """
    Response returned after successful login.

    Contains JWT access token, opaque refresh token, and user profile.
    """

    access_token: str = Field(
        ..., description="JWT access token (short-lived)"
    )
    refresh_token: str = Field(
        ..., description="Opaque refresh token (long-lived)"
    )
    token_type: str = Field(
        default="Bearer", description="Token type for Authorization header"
    )
    expires_in: int = Field(
        ..., description="Seconds until access token expires"
    )
    user: UserProfileResponse = Field(
        ..., description="Authenticated user profile"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
                    "token_type": "Bearer",
                    "expires_in": 900,
                    "user": {
                        "user_id": 123,
                        "email": "admin@company.com",
                        "user_type": "admin",
                        "admin_id": 1,
                        "organization_id": 1,
                        "admin_role": "admin",
                    },
                }
            ]
        }
    }


class TokenRefreshResponse(BaseModel):
    """
    Response returned after successful token refresh.

    If refresh token rotation is enabled, a new refresh_token is issued.
    """

    access_token: str = Field(
        ..., description="New JWT access token"
    )
    refresh_token: str = Field(
        ..., description="New refresh token (if rotation enabled, same otherwise)"
    )
    token_type: str = Field(
        default="Bearer", description="Token type for Authorization header"
    )
    expires_in: int = Field(
        ..., description="Seconds until new access token expires"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2",
                    "token_type": "Bearer",
                    "expires_in": 900,
                }
            ]
        }
    }


class ChangePasswordResponse(BaseModel):
    """Response returned after successful password change."""

    message: str = Field(
        default="Password updated successfully",
        description="Human-readable confirmation message",
    )


class CurrentUserResponse(BaseModel):
    """
    Response for /me endpoint — full user profile with status fields.

    Extends UserProfileResponse with status and timestamp fields.
    """

    user_id: int = Field(..., description="User primary key")
    email: str = Field(..., description="User email address")
    user_type: Literal["admin", "candidate"] = Field(
        ..., description="User classification"
    )
    user_status: Literal["active", "inactive", "banned"] = Field(
        ..., description="Current user account status"
    )

    # Admin context (None for candidates)
    admin_id: Optional[int] = Field(
        None, description="Admin record ID (admin only)"
    )
    organization_id: Optional[int] = Field(
        None, description="Organization ID (admin only)"
    )
    admin_role: Optional[Literal["superadmin", "admin", "read_only"]] = Field(
        None, description="Admin role (admin only)"
    )
    admin_status: Optional[Literal["active", "inactive", "suspended"]] = Field(
        None, description="Admin account status (admin only)"
    )

    # Candidate context (None for admins)
    candidate_id: Optional[int] = Field(
        None, description="Candidate record ID (candidate only)"
    )
    full_name: Optional[str] = Field(
        None, description="Candidate display name (candidate only)"
    )
    candidate_status: Optional[Literal["active", "inactive", "banned"]] = Field(
        None, description="Candidate account status (candidate only)"
    )

    last_login_at: Optional[datetime] = Field(
        None, description="Timestamp of last successful login (ISO 8601)"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": 123,
                    "email": "admin@company.com",
                    "user_type": "admin",
                    "user_status": "active",
                    "admin_id": 1,
                    "organization_id": 1,
                    "admin_role": "admin",
                    "admin_status": "active",
                    "last_login_at": "2026-02-13T10:30:00Z",
                }
            ]
        }
    }


class ErrorResponse(BaseModel):
    """
    Structured error response for auth endpoints.

    Compatible with shared error serializer format.
    The 'error' field contains a machine-readable AuthErrorCode value.
    """

    error: str = Field(
        ..., description="Machine-readable error code (AuthErrorCode value)"
    )
    message: str = Field(
        ..., description="Human-readable error description"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional additional context (never contains stack traces in production)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "invalid_credentials",
                    "message": "Email or password is incorrect",
                    "details": None,
                }
            ]
        }
    }
