"""
FastAPI Dependencies

Dependency injection functions for identity context access.
Used in endpoint signatures to require authentication/authorization.
"""

from fastapi import Request, Depends
from typing import Callable, Optional

from .models import IdentityContext
from app.shared.errors import AuthenticationError, AuthorizationError


def get_identity(request: Request) -> IdentityContext:
    """
    Extract identity from request state.
    
    Dependency for endpoints requiring authenticated user (admin or candidate).
    Identity is attached to request.state by IdentityInjectionMiddleware.
    
    Args:
        request: FastAPI Request object
    
    Returns:
        IdentityContext from request state
    
    Raises:
        AuthenticationError: If identity not present (unauthenticated request)
    
    Usage:
        @app.get("/api/profile")
        async def get_profile(identity: IdentityContext = Depends(get_identity)):
            return {"user_id": identity.user_id}
    """
    identity = getattr(request.state, "identity", None)
    
    if not identity:
        raise AuthenticationError(
            message="Authentication required",
            request_id=getattr(request.state, "request_id", None)
        )
    
    return identity


def get_optional_identity(request: Request) -> Optional[IdentityContext]:
    """
    Extract optional identity from request state.
    
    Dependency for endpoints that work with OR without authentication.
    Returns None if user is not authenticated.
    
    Args:
        request: FastAPI Request object
    
    Returns:
        IdentityContext if authenticated, None otherwise
    
    Usage:
        @app.get("/api/public-resource")
        async def get_resource(identity: Optional[IdentityContext] = Depends(get_optional_identity)):
            if identity:
                # Personalized response
                return {"user_id": identity.user_id, ...}
            else:
                # Anonymous response
                return {"public": True, ...}
    """
    return getattr(request.state, "identity", None)


def require_admin(identity: IdentityContext = Depends(get_identity)) -> IdentityContext:
    """
    Require authenticated admin user.
    
    Dependency for admin-only endpoints.
    Raises 403 if user is not admin.
    
    Args:
        identity: IdentityContext from get_identity dependency
    
    Returns:
        IdentityContext (guaranteed to be admin)
    
    Raises:
        AuthorizationError: If user is not admin
    
    Usage:
        @app.get("/api/admin/submissions")
        async def list_submissions(identity: IdentityContext = Depends(require_admin)):
            # Identity is guaranteed to be admin
            org_id = identity.organization_id
            ...
    """
    if not identity.is_admin():
        raise AuthorizationError(
            message="Admin access required",
            request_id=None,  # request_id not available here
            metadata={"user_id": identity.user_id, "user_type": identity.user_type.value}
        )
    
    return identity


def require_candidate(identity: IdentityContext = Depends(get_identity)) -> IdentityContext:
    """
    Require authenticated candidate user.
    
    Dependency for candidate-only endpoints.
    Raises 403 if user is not candidate.
    
    Args:
        identity: IdentityContext from get_identity dependency
    
    Returns:
        IdentityContext (guaranteed to be candidate)
    
    Raises:
        AuthorizationError: If user is not candidate
    
    Usage:
        @app.get("/api/candidate/submissions")
        async def my_submissions(identity: IdentityContext = Depends(require_candidate)):
            # Identity is guaranteed to be candidate
            candidate_id = identity.candidate_id  # Use candidate_id, not user_id
            ...
    """
    if not identity.is_candidate():
        raise AuthorizationError(
            message="Candidate access required",
            request_id=None,
            metadata={"user_id": identity.user_id, "user_type": identity.user_type.value}
        )
    
    return identity


def require_superadmin(identity: IdentityContext = Depends(require_admin)) -> IdentityContext:
    """
    Require authenticated superadmin user.
    
    Dependency for superadmin-only endpoints.
    Raises 403 if user is not superadmin.
    
    Args:
        identity: IdentityContext from require_admin dependency
    
    Returns:
        IdentityContext (guaranteed to be superadmin)
    
    Raises:
        AuthorizationError: If user is not superadmin
    
    Usage:
        @app.post("/api/admin/organizations")
        async def create_organization(identity: IdentityContext = Depends(require_superadmin)):
            # Only superadmins can create organizations
            ...
    """
    if not identity.is_superadmin():
        raise AuthorizationError(
            message="Superadmin access required",
            request_id=None,
            metadata={
                "user_id": identity.user_id,
                "admin_role": identity.admin_role.value if identity.admin_role else None
            }
        )
    
    return identity


def get_token_validator() -> Callable:
    """
    Get token validator dependency (for DI).

    Returns function that validates JWT and returns claims dict.
    The claims are normalized so that IdentityBuilder can consume them:
    - 'type'  → 'user_type'
    - 'role'  → 'admin_role'

    In test mode (settings=None), returns a mock that raises NotImplementedError.

    Returns:
        Callable[[str], dict] - Async function: token → claims dict
    """
    from app.config import settings

    if settings is None:
        # Testing mode — no real validator available
        async def mock_validator(token: str) -> dict:
            raise NotImplementedError(
                "Token validator not available in test mode. "
                "Override get_token_validator in tests."
            )
        return mock_validator

    # --- Real validator ---
    # Lazy import to avoid circular dependency (shared → auth)
    from app.auth.domain.jwt_service import JWTService

    sec = settings.security

    # Resolve keys based on algorithm
    if sec.jwt_algorithm == "RS256":
        with open(sec.jwt_private_key_path, "r") as f:
            private_key = f.read()
        with open(sec.jwt_public_key_path, "r") as f:
            public_key = f.read()
    else:
        # HS256: symmetric secret used as both keys
        private_key = sec.jwt_secret_key
        public_key = sec.jwt_secret_key

    jwt_service = JWTService(
        private_key=private_key,
        public_key=public_key,
        algorithm=sec.jwt_algorithm,
        access_token_ttl_minutes=sec.access_token_expire_minutes,
        refresh_token_ttl_days=sec.refresh_token_expire_days,
    )

    async def validate_token(token: str) -> dict:
        """Verify JWT and normalize claims for IdentityBuilder."""
        claims = jwt_service.verify_access_token(token)

        # Normalize JWT claim keys → IdentityBuilder expected keys
        if "type" in claims and "user_type" not in claims:
            claims["user_type"] = claims["type"]
        if "role" in claims and "admin_role" not in claims:
            claims["admin_role"] = claims["role"]

        return claims

    return validate_token
