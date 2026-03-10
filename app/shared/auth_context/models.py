"""
Identity Context Models

Immutable identity models for request-scoped authentication context.
Enforces multi-tenant isolation and user type exclusivity.
"""

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Optional
import time


class UserType(str, Enum):
    """
    User type classification.
    
    A user is EITHER admin OR candidate, never both.
    Schema constraint: user exists in admins OR candidates table.
    """
    ADMIN = "admin"
    CANDIDATE = "candidate"


class AdminRole(str, Enum):
    """
    Admin role hierarchy.
    
    Maps to admin_role PostgreSQL ENUM.
    Only applicable when user_type=ADMIN.
    """
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    READ_ONLY = "read_only"


@dataclass(frozen=True)
class IdentityContext:
    """
    Immutable identity context for a request or connection.
    
    Built from validated JWT claims by auth module.
    Attached to request.state.identity by middleware.
    
    Invariants:
    - If user_type=ADMIN: organization_id and admin_role MUST be set
    - If user_type=CANDIDATE: organization_id and admin_role MUST be None
    - Context is immutable (frozen=True) for request lifetime
    - No DB queries allowed to build this (JWT claims only)
    
    Example Admin Context:
        IdentityContext(
            user_id=42,
            user_type=UserType.ADMIN,
            organization_id=1,
            admin_role=AdminRole.ADMIN,
            token_version=3,
            issued_at=1700000000,
            expires_at=1700003600
        )
    
    Example Candidate Context:
        IdentityContext(
            user_id=123,
            user_type=UserType.CANDIDATE,
            organization_id=None,
            admin_role=None,
            token_version=1,
            issued_at=1700000000,
            expires_at=1700003600
        )
    """
    
    # User identification
    user_id: int          # users.id (PK of users table)
    user_type: UserType

    # Token metadata (for revocation)
    token_version: int
    issued_at: int       # Unix timestamp
    expires_at: int      # Unix timestamp

    # Optional fields (must follow non-default fields)
    candidate_id: Optional[int] = None  # candidates.id — populated from JWT for candidate tokens

    # Tenant identification (admin only)
    organization_id: Optional[int] = None

    # Role information (admin only)
    admin_role: Optional[AdminRole] = None
    
    def __post_init__(self):
        """Validate invariants after initialization"""
        # Enforce admin constraints
        if self.user_type == UserType.ADMIN:
            if self.organization_id is None:
                raise ValueError("Admin user must have organization_id")
            if self.admin_role is None:
                raise ValueError("Admin user must have admin_role")
        
        # Enforce candidate constraints
        if self.user_type == UserType.CANDIDATE:
            if self.organization_id is not None:
                raise ValueError("Candidate user cannot have organization_id")
            if self.admin_role is not None:
                raise ValueError("Candidate user cannot have admin_role")
            if self.candidate_id is None:
                raise ValueError("Candidate user must have candidate_id")
        
        # Admins must not have candidate_id
        if self.user_type == UserType.ADMIN and self.candidate_id is not None:
            raise ValueError("Admin user cannot have candidate_id")
        
        # Validate token timestamps
        if self.issued_at >= self.expires_at:
            raise ValueError("Token issued_at must be before expires_at")
    
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.user_type == UserType.ADMIN
    
    def is_candidate(self) -> bool:
        """Check if user is candidate"""
        return self.user_type == UserType.CANDIDATE
    
    def is_superadmin(self) -> bool:
        """Check if user is superadmin"""
        return self.user_type == UserType.ADMIN and self.admin_role == AdminRole.SUPERADMIN
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        return int(time.time()) > self.expires_at
    
    def belongs_to_organization(self, org_id: int) -> bool:
        """
        Check if identity belongs to organization.
        
        Only admins can belong to organizations.
        Candidates always return False.
        """
        if not self.is_admin():
            return False
        return self.organization_id == org_id
    
    def can_access_organization(self, org_id: int) -> bool:
        """
        Check if identity can access organization data.
        
        Superadmins can access all organizations.
        Regular admins can only access their own organization.
        Candidates cannot access any organization.
        """
        if self.is_superadmin():
            return True
        if self.is_admin():
            return self.organization_id == org_id
        return False
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary for logging.
        
        Safe for structured logging (no sensitive data).
        """
        return {
            "user_id": self.user_id,
            "user_type": self.user_type.value,
            "organization_id": self.organization_id,
            "admin_role": self.admin_role.value if self.admin_role else None,
            "token_version": self.token_version,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }


@dataclass
class TaskContext:
    """
    Serializable context for async tasks.
    
    Subset of IdentityContext for background job propagation.
    Used with Celery/task queue to maintain identity across async boundaries.
    
    Example:
        task_context = TaskContext.from_identity(
            identity=identity,
            request_id="req_abc123",
            submission_id=456
        )
        
        # Serialize for Celery
        evaluate_task.delay(
            exchange_id=789,
            context=task_context.to_dict()
        )
    """
    
    # Request correlation
    request_id: str
    
    # User identification
    user_id: int
    user_type: str  # "admin" | "candidate" (serialized enum)
    
    # Tenant identification
    organization_id: Optional[int]
    
    # Domain context (optional)
    submission_id: Optional[int] = None
    
    @staticmethod
    def from_identity(
        identity: IdentityContext,
        request_id: str,
        submission_id: Optional[int] = None
    ) -> "TaskContext":
        """
        Build TaskContext from IdentityContext.
        
        Args:
            identity: Request-scoped identity context
            request_id: Request correlation ID
            submission_id: Optional submission ID for interview tasks
        
        Returns:
            Serializable TaskContext
        """
        return TaskContext(
            request_id=request_id,
            user_id=identity.user_id,
            user_type=identity.user_type.value,
            organization_id=identity.organization_id,
            submission_id=submission_id
        )
    
    def to_dict(self) -> dict:
        """Serialize for task queue"""
        return asdict(self)
