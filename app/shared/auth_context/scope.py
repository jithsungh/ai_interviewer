"""
Scope Enforcement

Multi-tenant isolation and candidate scope enforcement.
Prevents cross-tenant data access and unauthorized resource access.
"""

from .models import IdentityContext
from app.shared.errors import TenantIsolationViolation, AuthorizationError


def enforce_organization_scope(
    identity: IdentityContext,
    resource_organization_id: int
) -> None:
    """
    Enforce organization-level tenant isolation.
    
    Rules:
    - User must be admin
    - Admin can only access resources from their organization
    - Superadmins can access all organizations
    
    Args:
        identity: Request identity context
        resource_organization_id: Organization ID of resource being accessed
    
    Raises:
        AuthorizationError: If user is not admin
        TenantIsolationViolation: If admin tries to access different organization
    
    Example:
        @app.get("/api/admin/submissions/{submission_id}")
        async def get_submission(
            submission_id: int,
            identity: IdentityContext = Depends(require_admin)
        ):
            submission = await submission_service.get_by_id(submission_id)
            
            # Enforce tenant isolation
            enforce_organization_scope(identity, submission.organization_id)
            
            return submission
    """
    # Must be admin
    if not identity.is_admin():
        raise AuthorizationError(
            message="Admin access required for organization resources",
            metadata={
                "user_id": identity.user_id,
                "user_type": identity.user_type.value
            }
        )
    
    # Superadmins can access all organizations
    if identity.is_superadmin():
        return
    
    # Regular admins can only access their organization
    if identity.organization_id != resource_organization_id:
        raise TenantIsolationViolation(
            message=f"Cannot access resources from organization {resource_organization_id}",
            metadata={
                "user_id": identity.user_id,
                "user_organization_id": identity.organization_id,
                "resource_organization_id": resource_organization_id
            }
        )


def enforce_candidate_scope(
    identity: IdentityContext,
    resource_candidate_id: int
) -> None:
    """
    Enforce candidate-level resource ownership.
    
    Rules:
    - User must be candidate
    - Candidate can only access their own resources
    
    Args:
        identity: Request identity context
        resource_candidate_id: Candidate ID who owns the resource
    
    Raises:
        AuthorizationError: If user is not candidate or tries to access another candidate's resource
    
    Example:
        @app.get("/api/candidate/submissions/{submission_id}")
        async def get_submission(
            submission_id: int,
            identity: IdentityContext = Depends(require_candidate)
        ):
            submission = await submission_service.get_by_id(submission_id)
            
            # Enforce candidate scope
            enforce_candidate_scope(identity, submission.candidate_id)
            
            return submission
    """
    # Must be candidate
    if not identity.is_candidate():
        raise AuthorizationError(
            message="Candidate access required",
            metadata={
                "user_id": identity.user_id,
                "user_type": identity.user_type.value
            }
        )
    
    # Candidate can only access their own resources
    # identity.candidate_id is from candidates table, resource_candidate_id is also candidates.id
    if identity.candidate_id != resource_candidate_id:
        raise AuthorizationError(
            message=f"Cannot access resources belonging to candidate {resource_candidate_id}",
            metadata={
                "candidate_id": identity.candidate_id,
                "resource_candidate_id": resource_candidate_id
            }
        )


def require_organization_admin(
    identity: IdentityContext,
    organization_id: int,
    minimum_role: str = "admin"
) -> None:
    """
    Require admin with specific role level for organization.
    
    Role hierarchy (descending privilege):
    - superadmin: Can access all organizations, full privileges
    - admin: Can access own organization, full privileges
    - read_only: Can access own organization, read-only
    
    Args:
        identity: Request identity context
        organization_id: Required organization ID
        minimum_role: Minimum role required ("superadmin", "admin", or "read_only")
    
    Raises:
        AuthorizationError: If user lacks required role
        TenantIsolationViolation: If user tries to access different organization
    
    Example:
        @app.post("/api/admin/templates")
        async def create_template(
            template: TemplateCreate,
            identity: IdentityContext = Depends(require_admin)
        ):
            # Require admin role (not read_only)
            require_organization_admin(
                identity,
                template.organization_id,
                minimum_role="admin"
            )
            
            # Create template...
    """
    # Must be admin
    if not identity.is_admin():
        raise AuthorizationError(
            message="Admin access required",
            metadata={"user_id": identity.user_id}
        )
    
    # Check organization scope
    if not identity.is_superadmin():
        if identity.organization_id != organization_id:
            raise TenantIsolationViolation(
                message=f"Cannot access organization {organization_id}",
                metadata={
                    "user_id": identity.user_id,
                    "user_organization_id": identity.organization_id,
                    "required_organization_id": organization_id
                }
            )
    
    # Check role level
    role_hierarchy = {
        "superadmin": 3,
        "admin": 2,
        "read_only": 1
    }
    
    user_role_level = role_hierarchy.get(identity.admin_role.value, 0)
    required_role_level = role_hierarchy.get(minimum_role, 0)
    
    if user_role_level < required_role_level:
        raise AuthorizationError(
            message=f"Insufficient privileges. Required role: {minimum_role}",
            metadata={
                "user_id": identity.user_id,
                "user_role": identity.admin_role.value,
                "required_role": minimum_role
            }
        )
