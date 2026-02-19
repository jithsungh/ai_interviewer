"""
Request-Scoped Authentication Context

⚠️ DEPRECATED: This module is deprecated and will be removed.
Use models.py (IdentityContext, UserType, AdminRole) instead.

Migration Guide:
- AuthContext → IdentityContext
- UserRole → UserType (admin, candidate only)
- roles: Set[UserRole] → user_type: UserType + admin_role: Optional[AdminRole]

This file is kept for backward compatibility only.
"""

import warnings
from typing import Optional, Set
from dataclasses import dataclass
from enum import Enum


# Emit deprecation warning when module is imported
warnings.warn(
    "auth_context.context is deprecated. Use auth_context.models (IdentityContext) instead.",
    DeprecationWarning,
    stacklevel=2
)


class UserRole(str, Enum):
    """User roles for RBAC (FR-1.3)"""
    CANDIDATE = "candidate"
    INTERVIEWER = "interviewer"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
    READ_ONLY = "read_only"


@dataclass
class AuthContext:
    """
    Request-scoped authentication context.
    
    Created from JWT claims and attached to each request.
    Provides tenant-scoped identity for authorization checks.
    """
    
    # Identity
    user_id: int
    email: str
    roles: Set[UserRole]
    
    # Tenant (NFR-7.1: Multi-tenancy isolation)
    organization_id: Optional[int] = None
    
    # Candidate/Admin specific
    candidate_id: Optional[int] = None
    admin_id: Optional[int] = None
    
    # Metadata
    session_id: str = ""
    
    def is_candidate(self) -> bool:
        """Check if user is a candidate"""
        return UserRole.CANDIDATE in self.roles
    
    def is_admin(self) -> bool:
        """Check if user has admin privileges"""
        return any(role in self.roles for role in [
            UserRole.ADMIN,
            UserRole.SUPERADMIN
        ])
    
    def is_superadmin(self) -> bool:
        """Check if user is superadmin"""
        return UserRole.SUPERADMIN in self.roles
    
    def has_role(self, role: UserRole) -> bool:
        """Check if user has specific role"""
        return role in self.roles
    
    def can_access_organization(self, org_id: int) -> bool:
        """
        Check if user can access organization data.
        
        Enforces tenant isolation (NFR-7.1).
        Superadmins can access all organizations.
        """
        if self.is_superadmin():
            return True
        return self.organization_id == org_id
    
    def require_organization_access(self, org_id: int):
        """
        Require organization access or raise error.
        
        Enforces tenant isolation (NFR-7.1).
        """
        from app.shared.errors import TenantIsolationViolation
        
        if not self.can_access_organization(org_id):
            raise TenantIsolationViolation(
                f"User {self.user_id} cannot access organization {org_id}"
            )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for logging"""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "roles": [r.value for r in self.roles],
            "organization_id": self.organization_id,
            "candidate_id": self.candidate_id,
            "admin_id": self.admin_id,
            "session_id": self.session_id,
        }
