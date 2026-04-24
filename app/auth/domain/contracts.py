"""
Domain Contracts (Data Transfer Objects)

Defines commands (inputs) and results (outputs) for auth domain operations.
These are immutable dataclasses with validation.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal
from datetime import datetime

from app.shared.auth_context import IdentityContext


# ============================================================================
# COMMANDS (INPUTS)
# ============================================================================

@dataclass(frozen=True)
class RegisterAdminCommand:
    """
    Command to register a new admin user.
    
    Cannot self-assign 'superadmin' role - requires existing superadmin approval.
    Organization must exist and be active.
    """
    email: str
    password: str
    organization_id: int
    admin_role: Literal["admin", "read_only"]
    full_name: Optional[str] = None
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None


@dataclass(frozen=True)
class RegisterCandidateCommand:
    """
    Command to register a new candidate user.
    
    Candidates are not associated with any organization.
    """
    email: str
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    experience_years: Optional[int] = None
    skills: Optional[list[str]] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None


@dataclass(frozen=True)
class LoginCommand:
    """
    Command to authenticate a user and issue tokens.
    
    Validates credentials, user status, admin status, organization status.
    """
    email: str
    password: str
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None
    device_info: Optional[str] = None


@dataclass(frozen=True)
class RefreshTokenCommand:
    """
    Command to refresh an access token using a refresh token.
    
    Validates refresh token, checks expiration, handles rotation.
    """
    refresh_token: str
    request_ip: Optional[str] = None


@dataclass(frozen=True)
class LogoutCommand:
    """
    Command to revoke a refresh token (logout).
    
    Idempotent - succeeds even if token already revoked.
    """
    refresh_token: str
    request_ip: Optional[str] = None


@dataclass(frozen=True)
class ChangePasswordCommand:
    """
    Command to change the current authenticated user's password.

    Requires current password verification and invalidates existing sessions.
    """
    current_password: str
    new_password: str
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None


@dataclass(frozen=True)
class ValidateTokenCommand:
    """
    Command to validate an access token.
    
    Verifies JWT signature, expiration, user status, and org status.
    """
    access_token: str


# ============================================================================
# RESULTS (OUTPUTS)
# ============================================================================

@dataclass(frozen=True)
class UserProfile:
    """
    User profile returned after registration or login.
    
    Contains user identity and role information.
    """
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]
    user_status: str
    
    # Admin-specific fields
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[str] = None
    admin_status: Optional[str] = None
    
    # Candidate-specific fields
    candidate_id: Optional[int] = None
    full_name: Optional[str] = None
    candidate_status: Optional[str] = None
    candidate_plan: Optional[str] = None
    
    # Metadata
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class AuthenticationResult:
    """
    Result of successful authentication (login or token refresh).
    
    Contains JWT access token, refresh token, and user profile.
    """
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int = 900  # seconds (15 minutes default)
    user_profile: Optional[UserProfile] = None


@dataclass(frozen=True)
class TokenValidationResult:
    """
    Result of JWT token validation.
    
    Indicates whether token is valid and provides auth context if valid.
    """
    valid: bool
    claims: Optional[Dict[str, Any]] = None
    error: Optional[str] = None  # 'expired', 'invalid_signature', 'user_inactive', 'org_suspended'
    auth_context: Optional[IdentityContext] = None
