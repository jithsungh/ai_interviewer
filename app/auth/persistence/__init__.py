"""
Auth Persistence Layer

Provides ORM models and repository classes for auth-related database tables.
These models map to tables in the PostgreSQL database.

Repositories are the ONLY layer that directly accesses identity tables.
Domain logic never writes raw SQL or imports ORM models directly.
"""

from .models import (
    User,
    Admin,
    Candidate,
    RefreshToken,
    AuthAuditLog,
)
from .user_repository import UserRepository
from .admin_repository import AdminRepository
from .candidate_repository import CandidateRepository
from .refresh_token_repository import RefreshTokenRepository
from .audit_log_repository import AuthAuditLogRepository

__all__ = [
    # ORM Models
    "User",
    "Admin",
    "Candidate",
    "RefreshToken",
    "AuthAuditLog",
    # Repositories
    "UserRepository",
    "AdminRepository",
    "CandidateRepository",
    "RefreshTokenRepository",
    "AuthAuditLogRepository",
]
