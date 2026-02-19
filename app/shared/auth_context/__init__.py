"""
Authentication Context Module

Provides identity context and tenant isolation for request-scoped authentication.

Public Interfaces:
- IdentityContext: Immutable identity from validated JWT
- UserType: Enum (admin, candidate)
- AdminRole: Enum (superadmin, admin, read_only)
- TaskContext: Serializable context for async tasks

Dependencies (FastAPI):
- get_identity(): Extract identity from request
- get_optional_identity(): Optional identity extraction
- require_admin(): Admin-only dependency
- require_candidate(): Candidate-only dependency
- require_superadmin(): Superadmin-only dependency

Middleware:
- IdentityInjectionMiddleware: Inject identity into request.state

WebSocket:
- ConnectionRegistry: Redis-backed connection tracking
- authenticate_websocket(): Authenticate WebSocket connection
- generate_connection_id(): Generate unique connection ID

Scope Enforcement:
- enforce_organization_scope(): Tenant isolation for admins
- enforce_candidate_scope(): Resource ownership for candidates
- require_organization_admin(): Role-based access control

Builder:
- IdentityBuilder: Transform JWT claims to IdentityContext

Configuration:
- AuthContextConfig: Module configuration
"""

from .models import IdentityContext, UserType, AdminRole, TaskContext
from .builder import IdentityBuilder
from .dependencies import (
    get_identity,
    get_optional_identity,
    require_admin,
    require_candidate,
    require_superadmin,
    get_token_validator
)
from .middleware import IdentityInjectionMiddleware
# Lazy imports for Redis-dependent modules (to support unit testing without Redis)
# from .registry import ConnectionRegistry, connection_registry
from .websocket import authenticate_websocket, generate_connection_id
from .scope import (
    enforce_organization_scope,
    enforce_candidate_scope,
    require_organization_admin
)
from .config import AuthContextConfig, auth_context_config

# Deprecated: Old AuthContext (use IdentityContext instead)
# Kept for backward compatibility during migration
from .context import AuthContext, UserRole as OldUserRole


def __getattr__(name):
    """
    Lazy import for Redis-dependent modules.
    Allows unit tests to run without Redis installed.
    """
    if name == "ConnectionRegistry":
        from .registry import ConnectionRegistry
        return ConnectionRegistry
    elif name == "connection_registry":
        from .registry import connection_registry
        return connection_registry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Models
    "IdentityContext",
    "UserType",
    "AdminRole",
    "TaskContext",
    
    # Builder
    "IdentityBuilder",
    
    # Dependencies
    "get_identity",
    "get_optional_identity",
    "require_admin",
    "require_candidate",
    "require_superadmin",
    "get_token_validator",
    
    # Middleware
    "IdentityInjectionMiddleware",
    
    # WebSocket
    "ConnectionRegistry",
    "connection_registry",
    "authenticate_websocket",
    "generate_connection_id",
    
    # Scope Enforcement
    "enforce_organization_scope",
    "enforce_candidate_scope",
    "require_organization_admin",
    
    # Configuration
    "AuthContextConfig",
    "auth_context_config",
    
    # Deprecated (backward compatibility)
    "AuthContext",
    "OldUserRole",
]
