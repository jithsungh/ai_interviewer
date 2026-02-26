"""
Role-Based Access Control (RBAC) Enforcer

Provides permission checking for admin roles.
Enforces permission matrix: superadmin > admin > read_only
"""

from enum import Enum
from typing import Set

from app.shared.auth_context import IdentityContext,AdminRole
from app.shared.errors import AuthorizationError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class Permission(str, Enum):
    """
    Permission definitions for admin actions.
    
    These map to specific operations in the system.
    """
    # Admin management
    MANAGE_ADMINS = "manage_admins"
    MANAGE_ORGANIZATION = "manage_organization"
    
    # Template management
    CREATE_TEMPLATES = "create_templates"
    EDIT_TEMPLATES = "edit_templates"
    DELETE_TEMPLATES = "delete_templates"
    
    # Interview management
    CREATE_INTERVIEWS = "create_interviews"
    VIEW_SUBMISSIONS = "view_submissions"
    DOWNLOAD_REPORTS = "download_reports"
    
    # Candidate management
    MANAGE_CANDIDATES = "manage_candidates"
    
    # Analytics
    VIEW_ANALYTICS = "view_analytics"


class RBACEnforcer:
    """
    Role-Based Access Control enforcement.
    
    Defines permission matrix and provides permission checking.
    """
    
    # Permission matrix: role -> set of permissions
    PERMISSION_MATRIX: dict[str, Set[Permission]] = {
        AdminRole.SUPERADMIN.value: {
            Permission.MANAGE_ADMINS,
            Permission.MANAGE_ORGANIZATION,
            Permission.CREATE_TEMPLATES,
            Permission.EDIT_TEMPLATES,
            Permission.DELETE_TEMPLATES,
            Permission.CREATE_INTERVIEWS,
            Permission.VIEW_SUBMISSIONS,
            Permission.DOWNLOAD_REPORTS,
            Permission.MANAGE_CANDIDATES,
            Permission.VIEW_ANALYTICS,
        },
        AdminRole.ADMIN.value: {
            Permission.CREATE_TEMPLATES,
            Permission.EDIT_TEMPLATES,
            Permission.CREATE_INTERVIEWS,
            Permission.VIEW_SUBMISSIONS,
            Permission.DOWNLOAD_REPORTS,
            Permission.MANAGE_CANDIDATES,
            Permission.VIEW_ANALYTICS,
        },
        AdminRole.READ_ONLY.value: {
            Permission.VIEW_SUBMISSIONS,
            Permission.DOWNLOAD_REPORTS,
            Permission.VIEW_ANALYTICS,
        },
    }
    
    def __init__(self):
        """Initialize RBAC enforcer."""
        logger.info(
            "RBACEnforcer initialized",
            extra={
                "event_type": "rbac.initialized",
                "roles": list(self.PERMISSION_MATRIX.keys())
            }
        )
    
    def has_permission(self, identity: IdentityContext, permission: Permission) -> bool:
        """
        Check if identity has a specific permission.
        
        Args:
            identity: IdentityContext from authenticated request
            permission: Permission to check
            
        Returns:
            True if identity has permission, False otherwise
        """
        # Candidates have no permissions
        if identity.user_type.value != "admin":
            return False
        
        # Get permissions for admin role
        admin_role = identity.admin_role.value if identity.admin_role else None
        if not admin_role:
            return False
        
        allowed_permissions = self.PERMISSION_MATRIX.get(admin_role, set())
        return permission in allowed_permissions
    
    def require_permission(self, identity: IdentityContext, permission: Permission) -> None:
        """
        Require identity to have a specific permission.
        
        Args:
            identity: IdentityContext from authenticated request
            permission: Permission to require
            
        Raises:
            AuthorizationError: If identity lacks permission
        """
        if not self.has_permission(identity, permission):
            logger.warning(
                "Permission denied",
                extra={
                    "user_id": identity.user_id,
                    "user_type": identity.user_type.value,
                    "admin_role": identity.admin_role.value if identity.admin_role else None,
                    "required_permission": permission.value,
                    "event_type": "rbac.permission_denied"
                }
            )
            
            raise AuthorizationError(
                message=f"Insufficient permissions: {permission.value} required",
                metadata={
                    "user_id": identity.user_id,
                    "user_type": identity.user_type.value,
                    "admin_role": identity.admin_role.value if identity.admin_role else None,
                    "required_permission": permission.value
                }
            )
        
        logger.debug(
            "Permission granted",
            extra={
                "user_id": identity.user_id,
                "admin_role": identity.admin_role.value if identity.admin_role else None,
                "permission": permission.value,
                "event_type": "rbac.permission_granted"
            }
        )
    
    def get_permissions(self, admin_role: str) -> Set[Permission]:
        """
        Get all permissions for a specific admin role.
        
        Args:
            admin_role: Admin role (superadmin, admin, read_only)
            
        Returns:
            Set of permissions for the role
        """
        return self.PERMISSION_MATRIX.get(admin_role, set())
