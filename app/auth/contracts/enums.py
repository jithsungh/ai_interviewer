"""
Auth Error Code Enumeration

Machine-readable error codes for all auth-related error responses.
Used in ErrorResponse.error field for programmatic client-side handling.

These error codes are STABLE — adding new codes is allowed,
renaming or removing existing ones requires API version bump.
"""

from enum import Enum


class AuthErrorCode(str, Enum):
    """
    Auth-specific error codes.

    Each code maps to a specific failure scenario in the auth flow.
    Clients should match on these codes for programmatic error handling.
    """

    # Authentication errors (401)
    INVALID_CREDENTIALS = "invalid_credentials"
    USER_INACTIVE = "user_inactive"
    USER_BANNED = "user_banned"
    ADMIN_INACTIVE = "admin_inactive"
    ORG_SUSPENDED = "organization_suspended"
    ORG_INACTIVE = "organization_inactive"

    # Token errors (401)
    TOKEN_EXPIRED = "token_expired"
    TOKEN_INVALID = "token_invalid"
    TOKEN_REVOKED = "token_revoked"
    REFRESH_TOKEN_INVALID = "refresh_token_invalid"
    REFRESH_TOKEN_EXPIRED = "refresh_token_expired"

    # Registration errors (409/422)
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    PASSWORD_TOO_WEAK = "password_too_weak"
    ORG_NOT_FOUND = "organization_not_found"

    # Authorization errors (403)
    INSUFFICIENT_PERMISSIONS = "insufficient_permissions"
    MISSING_TOKEN = "missing_token"

    # Security errors (429)
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
