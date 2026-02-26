"""
Middleware Registration

Registers all middleware in the correct order for proper request processing.

Middleware Order (CRITICAL):
1. Request Context (first - injects request_id, timestamps)
2. Logging (logs all requests with context)
3. CORS (handles preflight, allows origins)
4. GZip Compression (optional performance)
5. Rate Limiting (protects endpoints)
6. Identity Injection (last - requires full context)
"""

import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.shared.observability import get_context_logger
from app.shared.auth_context.middleware import IdentityInjectionMiddleware
from app.shared.auth_context.dependencies import get_token_validator

logger = get_context_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Request Context Middleware (FIRST).
    
    Injects request metadata into request.state for downstream middleware/handlers:
    - request_id: Unique UUID for tracing
    - request_start_time: For latency calculation
    - user_id: Set later by identity middleware
    - organization_id: Set later by identity middleware
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate request ID
        request_id = str(uuid.uuid4())
        
        # Inject into request.state
        request.state.request_id = request_id
        request.state.request_start_time = time.perf_counter()
        request.state.user_id = None
        request.state.organization_id = None
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logging Middleware (SECOND).
    
    Logs all HTTP requests with:
    - Method, path, status code
    - Request ID, user ID (if authenticated)
    - Latency in milliseconds
    
    Redacts sensitive data from logs.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract context from request.state
        request_id = getattr(request.state, "request_id", "unknown")
        start_time = getattr(request.state, "request_start_time", time.perf_counter())
        
        # Process request
        response = await call_next(request)
        
        # Calculate latency
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # Extract identity (set by identity middleware, may be None)
        user_id = getattr(request.state, "user_id", None)
        organization_id = getattr(request.state, "organization_id", None)
        
        # Log request
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code}",
            event_type="http.request",
            latency_ms=latency_ms,
            metadata={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "request_id": request_id,
                "user_id": user_id,
                "organization_id": organization_id,
                "client_host": request.client.host if request.client else None
            }
        )
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate Limiting Middleware (FIFTH).
    
    Protects endpoints from abuse using Redis-backed rate limiting.
    
    TODO: Implement Redis-based rate limiting
    - Track requests per user/IP
    - Apply different limits per endpoint group
    - Return 429 when limit exceeded
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # TODO: Implement rate limiting logic
        # For now, pass through
        response = await call_next(request)
        return response


def register_middleware(app: FastAPI) -> None:
    """
    Register all middleware in the correct order.
    
    Args:
        app: FastAPI application instance
    
    Order matters! Do not change without careful review.
    """
    
    logger.info("Registering middleware...", event_type="middleware.registration.begin")
    
    # 1. Request Context (FIRST - needed by all subsequent middleware)
    app.add_middleware(RequestContextMiddleware)
    logger.debug("✓ RequestContextMiddleware registered")
    
    # 2. Logging (SECOND - logs all requests)
    app.add_middleware(LoggingMiddleware)
    logger.debug("✓ LoggingMiddleware registered")
    
    # 3. CORS (THIRD - must run before auth for OPTIONS requests)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure from settings
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    logger.debug("✓ CORSMiddleware registered")
    
    # 4. GZip Compression (FOURTH - optional performance)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    logger.debug("✓ GZipMiddleware registered")
    
    # 5. Rate Limiting (FIFTH - protects endpoints)
    app.add_middleware(RateLimitMiddleware)
    logger.debug("✓ RateLimitMiddleware registered (stub)")
    
    # 6. Identity Injection (LAST - requires all context)
    token_validator = get_token_validator()
    app.add_middleware(
        IdentityInjectionMiddleware,
        token_validator=token_validator,
        require_authentication=False  # Allow public endpoints
    )
    logger.debug("✓ IdentityInjectionMiddleware registered")
    
    logger.info(
        "✅ Middleware registration complete",
        event_type="middleware.registration.complete",
        metadata={"middleware_count": 6}
    )
