"""
Identity Injection Middleware

FastAPI middleware to inject IdentityContext into request state.
Extracts JWT from Authorization header, validates, and builds identity.
"""

import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .builder import IdentityBuilder
from .models import IdentityContext
from app.shared.errors import AuthenticationError
from app.shared.observability import get_context_logger
from app.shared.observability.tracing import extract_request_id

logger = get_context_logger(__name__)


class IdentityInjectionMiddleware(BaseHTTPMiddleware):
    """
    Inject IdentityContext into request state.
    
    Flow:
    1. Extract Authorization header (Bearer token)
    2. Validate JWT (via injected token_validator)
    3. Build IdentityContext from claims
    4. Attach to request.state.identity
    5. Continue request processing
    
    If token missing or invalid:
    - Request proceeds WITHOUT identity
    - Endpoints using Depends(get_identity) will raise AuthenticationError
    - Endpoints using Depends(get_optional_identity) will receive None
    
    This allows public endpoints to coexist with protected endpoints.
    
    Configuration:
    - token_validator: Callable injected from auth module
    - require_authentication: If True, raise 401 for missing/invalid tokens
    
    Usage:
        app.add_middleware(
            IdentityInjectionMiddleware,
            token_validator=validate_access_token,
            require_authentication=False  # Allow public endpoints
        )
    """
    
    def __init__(
        self,
        app: ASGIApp,
        token_validator: Callable,
        require_authentication: bool = False
    ):
        """
        Initialize middleware.
        
        Args:
            app: ASGI application
            token_validator: Async function that validates JWT and returns claims
            require_authentication: If True, reject requests without valid token
        """
        super().__init__(app)
        self.token_validator = token_validator
        self.require_authentication = require_authentication
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and inject identity.
        
        Args:
            request: FastAPI Request
            call_next: Next middleware/endpoint
        
        Returns:
            Response from downstream handler
        """
        # Extract request ID for correlation
        request_id = extract_request_id(request)
        request.state.request_id = request_id
        
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        
        # Skip identity injection if no auth header
        if not auth_header:
            if self.require_authentication:
                logger.warning(
                    "Missing Authorization header",
                    metadata={"request_id": request_id, "path": request.url.path}
                )
                raise AuthenticationError(
                    message="Missing Authorization header",
                    request_id=request_id
                )
            
            # Allow anonymous access
            return await call_next(request)
        
        # Extract Bearer token
        if not auth_header.startswith("Bearer "):
            if self.require_authentication:
                logger.warning(
                    "Invalid Authorization header format",
                    metadata={"request_id": request_id, "path": request.url.path}
                )
                raise AuthenticationError(
                    message="Invalid Authorization header format. Expected: Bearer <token>",
                    request_id=request_id
                )
            
            return await call_next(request)
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate token and get claims
        try:
            claims = await self.token_validator(token)
        except AuthenticationError:
            # Token validation failed
            if self.require_authentication:
                raise
            
            # Log warning but allow request to proceed
            logger.warning(
                "Token validation failed",
                metadata={"request_id": request_id, "path": request.url.path}
            )
            return await call_next(request)
        except Exception as e:
            # Unexpected error during validation
            logger.error(
                f"Token validation error: {e}",
                metadata={"request_id": request_id, "path": request.url.path},
                exc_info=True
            )
            
            if self.require_authentication:
                raise AuthenticationError(
                    message="Token validation error",
                    request_id=request_id
                )
            
            return await call_next(request)
        
        # Build IdentityContext from validated claims
        try:
            identity = IdentityBuilder.from_jwt_claims(claims)
        except (ValueError, KeyError) as e:
            logger.error(
                f"Failed to build IdentityContext: {e}",
                metadata={"request_id": request_id, "claims": claims},
                exc_info=True
            )
            
            if self.require_authentication:
                raise AuthenticationError(
                    message=f"Invalid token claims: {e}",
                    request_id=request_id
                )
            
            return await call_next(request)
        
        # Check token expiry
        if identity.is_expired():
            logger.warning(
                "Expired token",
                metadata={
                    "request_id": request_id,
                    "user_id": identity.user_id,
                    "expires_at": identity.expires_at
                }
            )
            
            if self.require_authentication:
                raise AuthenticationError(
                    message="Token expired",
                    request_id=request_id
                )
            
            return await call_next(request)
        
        # Attach identity to request state
        request.state.identity = identity
        
        # Log identity injection (INFO level)
        logger.info(
            "Identity injected",
            metadata={
                "request_id": request_id,
                "user_id": identity.user_id,
                "user_type": identity.user_type.value,
                "organization_id": identity.organization_id,
                "path": request.url.path
            }
        )
        
        # Proceed to next handler
        try:
            response = await call_next(request)
        except RuntimeError as exc:
            if str(exc) == "No response returned.":
                # Starlette BaseHTTPMiddleware bug: the response was already
                # sent (e.g. by an exception handler) but call_next lost
                # track of it due to dependency-generator cleanup re-raising.
                # Return a fallback 500 so the middleware chain doesn't crash.
                from starlette.responses import Response as StarletteResponse
                logger.warning(
                    "Caught 'No response returned' from call_next; "
                    "response was likely already sent by an exception handler.",
                    metadata={"request_id": request_id, "path": request.url.path},
                )
                return StarletteResponse(status_code=500)
            raise
        
        return response
