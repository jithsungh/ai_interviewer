"""
Auth Request Schemas

Pydantic models for auth API request payloads.
All validation rules enforced here — domain layer trusts these schemas.

Password complexity rules reuse constants from app.config.constants.
"""

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.config.constants import MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH

# Special characters accepted for password complexity validation
_SPECIAL_CHARS = set("!@#$%^&*()_+-=[]{}|;:,.<>?/~`'\"\\")


def _validate_password_complexity(v: str) -> str:
    """
    Validate password meets complexity requirements.

    Rules (from REQUIREMENTS.md §10):
    - Minimum 8 characters (MIN_PASSWORD_LENGTH)
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 digit
    - At least 1 special character

    Raises:
        ValueError: If password fails any complexity rule
    """
    if not any(c.isupper() for c in v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.islower() for c in v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isdigit() for c in v):
        raise ValueError("Password must contain at least one digit")
    if not any(c in _SPECIAL_CHARS for c in v):
        raise ValueError("Password must contain at least one special character")
    return v


class AdminRegistrationRequest(BaseModel):
    """
    Request schema for admin user registration.

    Constraints:
    - Cannot self-assign 'superadmin' role (requires existing superadmin approval)
    - organization_id must reference an existing, active organization
    - Email must be unique across all users
    """

    email: EmailStr = Field(
        ...,
        description="Valid email address, must be unique across all users",
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="Password meeting complexity requirements",
    )
    organization_id: int = Field(
        ...,
        gt=0,
        description="ID of the organization to join",
    )
    admin_role: Literal["admin", "read_only"] = Field(
        ...,
        description="Admin role assignment. Cannot be 'superadmin' via registration.",
    )
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional display name",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "admin@company.com",
                    "password": "SecurePass123!",
                    "organization_id": 1,
                    "admin_role": "admin",
                    "full_name": "John Doe",
                }
            ]
        }
    }


class CandidateRegistrationRequest(BaseModel):
    """
    Request schema for candidate user registration.

    Candidates are NOT associated with any organization.
    Step 1: Account (email, password) - required
    Step 2: Basic info (name, phone) - optional
    Step 3: Professional (experience, skills, etc.) - optional
    """

    # Step 1: Account (required)
    email: EmailStr = Field(
        ...,
        description="Valid email address, must be unique across all users",
    )
    password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="Password meeting complexity requirements",
    )

    # Step 2: Basic Info (optional)
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Candidate display name",
    )
    phone: Optional[str] = Field(
        None,
        max_length=50,
        description="Phone number (free-form, any format)",
    )
    location: Optional[str] = Field(
        None,
        max_length=255,
        description="City or location",
    )

    # Step 3: Professional Info (optional)
    bio: Optional[str] = Field(
        None,
        max_length=1000,
        description="Short bio or summary",
    )
    experience_years: Optional[int] = Field(
        None,
        ge=0,
        le=50,
        description="Years of experience",
    )
    skills: Optional[list[str]] = Field(
        None,
        max_length=20,
        description="List of skills (max 20)",
    )
    linkedin_url: Optional[str] = Field(
        None,
        max_length=500,
        description="LinkedIn profile URL",
    )
    github_url: Optional[str] = Field(
        None,
        max_length=500,
        description="GitHub profile URL",
    )

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "candidate@example.com",
                    "password": "SecurePass123!",
                    "full_name": "Jane Smith",
                    "phone": "+1-555-0123",
                }
            ]
        }
    }


class LoginRequest(BaseModel):
    """
    Request schema for user authentication.

    Email comparison is case-insensitive (handled by domain layer).
    """

    email: EmailStr = Field(
        ...,
        description="Registered email address",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="User password",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "user@example.com",
                    "password": "SecurePass123!",
                }
            ]
        }
    }


class RefreshTokenRequest(BaseModel):
    """
    Request schema for access token refresh.

    The refresh_token is the opaque token string (not the hash).
    Domain layer hashes it for lookup.
    """

    refresh_token: str = Field(
        ...,
        min_length=32,
        max_length=256,
        description="Refresh token issued during login",
    )


class LogoutRequest(BaseModel):
    """
    Request schema for user logout (token revocation).

    Idempotent — succeeds even if the token is already revoked.
    """

    refresh_token: str = Field(
        ...,
        min_length=32,
        max_length=256,
        description="Refresh token to revoke",
    )


class ChangePasswordRequest(BaseModel):
    """Request schema for authenticated password change."""

    current_password: str = Field(
        ...,
        min_length=1,
        max_length=MAX_PASSWORD_LENGTH,
        description="Existing account password",
    )
    new_password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="New password meeting complexity requirements",
    )
    confirm_password: str = Field(
        ...,
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description="Confirmation for the new password",
    )

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @field_validator("confirm_password")
    @classmethod
    def validate_confirm_password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Confirm password must match new password")
        return self
