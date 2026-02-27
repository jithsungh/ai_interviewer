"""
JWT Claim Type Definitions

TypedDict structures for JWT access token payloads.
These define the expected shape of claims embedded in JWT tokens.

Used by:
- JWTService (auth/domain/jwt_service.py) for token generation
- IdentityBuilder (shared/auth_context/builder.py) for claim parsing
- Token validation middleware

Claim key 'type' maps to UserType enum value ('admin' | 'candidate').
Claim key 'sub' is the user_id (int).
"""

from typing import TypedDict


class AdminAccessTokenClaims(TypedDict):
    """
    JWT claims for admin access tokens.

    Includes organization_id and role for tenant isolation and RBAC.
    """

    sub: int                # Subject (user_id)
    type: str               # "admin"
    admin_id: int           # Admin record ID
    organization_id: int    # Organization ID (tenant isolation)
    role: str               # "superadmin" | "admin" | "read_only"
    iat: int                # Issued at (UNIX timestamp)
    exp: int                # Expires at (UNIX timestamp)
    jti: str                # JWT ID (unique, for revocation)
    token_version: int      # For forced logout (matches users.token_version)


class CandidateAccessTokenClaims(TypedDict):
    """
    JWT claims for candidate access tokens.

    No organization_id or role — candidates are not tenant-scoped.
    """

    sub: int                # Subject (user_id)
    type: str               # "candidate"
    candidate_id: int       # Candidate record ID
    iat: int                # Issued at (UNIX timestamp)
    exp: int                # Expires at (UNIX timestamp)
    jti: str                # JWT ID (unique, for revocation)
    token_version: int      # For forced logout (matches users.token_version)
