"""
Unified Error Semantics

Defines structured error type hierarchy for REST, WebSocket, and WebRTC protocols.
Provides consistent error handling with request correlation, metadata, and multi-protocol serialization.

Architecture:
- BaseError: Foundation class with request_id, metadata, http_status_code
- ApplicationError: Backward-compatible alias for BaseError
- Client Errors (4xx): Authentication, Authorization, Validation, NotFound, Conflict, RateLimit
- Server Errors (5xx): Infrastructure, AIProvider, Sandbox, InternalServer
- Domain Errors: DomainInvariantViolation, ProctoringViolation
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass, field


@dataclass
class BaseError(Exception):
    """
    Base exception for all application errors.
    
    Provides unified error structure with:
    - error_code: Machine-readable error identifier
    - message: Human-readable error description
    - request_id: Request correlation ID (for tracing)
    - metadata: Additional contextual information
    - http_status_code: HTTP status code for REST API responses
    
    All application errors should inherit from this class.
    """
    
    error_code: str
    message: str
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    http_status_code: int = 500
    
    def __post_init__(self):
        """Initialize Exception base class with message"""
        super().__init__(self.message)
        
        # Ensure metadata is initialized
        if self.metadata is None:
            self.metadata = {}
    
    # Backward compatibility properties
    @property
    def status_code(self) -> int:
        """Alias for http_status_code (backward compatibility)"""
        return self.http_status_code
    
    @property
    def details(self) -> Dict[str, Any]:
        """Alias for metadata (backward compatibility)"""
        return self.metadata or {}


# Backward compatibility alias
class ApplicationError(BaseError):
    """
    Backward-compatible alias for BaseError.
    
    Maintains compatibility with existing code that uses ApplicationError.
    Supports both old-style initialization (status_code, details) and new-style (http_status_code, metadata).
    """
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        http_status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None,
        **kwargs
    ):
        # Support both old and new parameter names
        final_status_code = http_status_code or status_code or 500
        final_metadata = metadata or details or {}
        final_error_code = error_code or self.__class__.__name__
        
        super().__init__(
            error_code=final_error_code,
            message=message,
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=final_status_code
        )


# ============================================================================
# CLIENT ERRORS (4xx)
# ============================================================================

class AuthenticationError(BaseError):
    """
    Raised when authentication fails.
    
    Examples:
    - Invalid token
    - Expired token
    - Missing token
    - Token signature invalid
    """
    
    def __init__(
        self,
        message: str = "Authentication failed",
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="AUTHENTICATION_FAILED",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=401
        )


class AuthorizationError(BaseError):
    """
    Raised when user lacks permission for resource.
    
    Examples:
    - Admin accessing another org's data
    - Candidate accessing admin endpoints
    - Insufficient role privilege
    """
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="AUTHORIZATION_FAILED",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=403
        )


class TenantIsolationViolation(BaseError):
    """
    Critical: Cross-tenant data access attempt (NFR-7.1).
    
    Raised when user attempts to access data from a different organization.
    This is a security violation and must be logged at CRITICAL level.
    """
    
    def __init__(
        self,
        message: str = "Tenant isolation violated",
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="TENANT_VIOLATION",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=403
        )


class NotFoundError(BaseError):
    """
    Raised when requested resource doesn't exist.
    
    Examples:
    - Submission not found
    - Question not found
    - Exchange not found
    """
    
    def __init__(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[Any] = None,
        request_id: Optional[str] = None,
        # Backward compatibility parameters
        resource: Optional[str] = None,
        identifier: Optional[Any] = None
    ):
        # Support old-style parameter names (resource/identifier)
        # and new-style (resource_type/resource_id)
        final_resource_type = resource_type or resource or "Resource"
        final_resource_id = resource_id if resource_id is not None else identifier if identifier is not None else "unknown"
        
        super().__init__(
            error_code="NOT_FOUND",
            message=f"{final_resource_type} with ID {final_resource_id} not found",
            request_id=request_id,
            metadata={
                "resource_type": final_resource_type,
                "resource_id": final_resource_id
            },
            http_status_code=404
        )


class ConflictError(BaseError):
    """
    Raised when operation conflicts with current state.
    
    Examples:
    - Interview already started
    - Submission already submitted
    - Duplicate active WebSocket connection
    """
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="CONFLICT",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=409
        )


class ValidationError(BaseError):
    """
    Raised when request payload is invalid.
    
    Examples:
    - Missing required field
    - Invalid field type
    - Field value out of range
    - Malformed JSON
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        # Merge field into metadata if provided
        final_metadata = metadata or {}
        if field:
            final_metadata["field"] = field
        
        super().__init__(
            error_code="VALIDATION_ERROR",
            message=message,
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=422
        )


class RateLimitExceeded(BaseError):
    """
    Raised when rate limit exceeded.
    
    Examples:
    - Too many API requests
    - Too many question generations
    - Too many sandbox executions
    """
    
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        retry_after_seconds: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit of {limit} requests per {window_seconds}s exceeded",
            request_id=request_id,
            metadata={
                "limit": limit,
                "window_seconds": window_seconds,
                "retry_after_seconds": retry_after_seconds
            },
            http_status_code=429
        )


# ============================================================================
# BUSINESS LOGIC ERRORS (4xx)
# ============================================================================

class InterviewNotActiveError(BaseError):
    """Interview session is not in active state"""
    
    def __init__(
        self,
        submission_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="INTERVIEW_NOT_ACTIVE",
            message=f"Interview submission {submission_id} is not active",
            request_id=request_id,
            metadata={"submission_id": submission_id},
            http_status_code=400
        )


class InterviewWindowClosedError(BaseError):
    """Interview window is not currently open (FR-2.3)"""
    
    def __init__(
        self,
        window_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="INTERVIEW_WINDOW_CLOSED",
            message=f"Interview window {window_id} is closed",
            request_id=request_id,
            metadata={"window_id": window_id},
            http_status_code=400
        )


class ConsentNotCapturedError(BaseError):
    """User consent not captured before interview (NFR-9)"""
    
    def __init__(self, request_id: Optional[str] = None):
        super().__init__(
            error_code="CONSENT_REQUIRED",
            message="Explicit user consent required before interview",
            request_id=request_id,
            http_status_code=400
        )


# ============================================================================
# DOMAIN ERRORS
# ============================================================================

class ExchangeImmutabilityViolation(BaseError):
    """
    Attempt to modify immutable exchange (Architecture Invariant #1).
    
    Exchanges are immutable after creation - modifications indicate a system bug.
    """
    
    def __init__(
        self,
        exchange_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="EXCHANGE_IMMUTABLE",
            message=f"Interview exchange {exchange_id} is immutable after creation",
            request_id=request_id,
            metadata={"exchange_id": exchange_id},
            http_status_code=400
        )


class TemplateImmutabilityViolation(BaseError):
    """
    Attempt to modify template in use (Architecture Invariant #3).
    
    Templates are immutable after first use - create new version instead.
    """
    
    def __init__(
        self,
        template_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="TEMPLATE_IMMUTABLE",
            message=f"Template {template_id} is immutable after use. Create new version.",
            request_id=request_id,
            metadata={"template_id": template_id},
            http_status_code=400
        )


class DomainInvariantViolation(BaseError):
    """
    Raised when business invariant is violated.
    
    Examples:
    - Template recalculated at runtime (must be immutable)
    - Exchange mutated after creation (must be immutable)
    - Submission state transition invalid
    
    NOTE: This is a 500 error (indicates system bug, not user error).
    Must be logged at CRITICAL level.
    """
    
    def __init__(
        self,
        invariant: str,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata["invariant"] = invariant
        
        super().__init__(
            error_code="DOMAIN_INVARIANT_VIOLATION",
            message=f"Invariant '{invariant}' violated: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=500
        )


class ProctoringViolation(BaseError):
    """
    Raised (or logged) when proctoring event detected.
    
    Examples:
    - Face not visible
    - Multiple faces detected
    - Audio silence detected
    
    NOTE: This is ADVISORY only, NOT punitive.
    System must NOT auto-fail interview on this error.
    
    Typically logged, not raised (non-blocking).
    """
    
    def __init__(
        self,
        event_type: str,
        message: str,
        risk_score: float,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "event_type": event_type,
            "risk_score": risk_score
        })
        
        super().__init__(
            error_code="PROCTORING_VIOLATION",
            message=message,
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=200  # Not an error response, just an event
        )


# ============================================================================
# EXTERNAL SERVICE ERRORS (5xx)
# ============================================================================

class AIProviderError(BaseError):
    """
    AI/LLM provider request failed.
    
    Examples:
    - OpenAI timeout
    - OpenAI rate limit (429)
    - Claude unavailable
    """
    
    def __init__(
        self,
        provider: str,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata["provider"] = provider
        
        super().__init__(
            error_code="AI_PROVIDER_ERROR",
            message=f"{provider} error: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=502
        )


class AIProviderTimeoutError(BaseError):
    """AI/LLM provider request timeout (FM-1, NFR-2)"""
    
    def __init__(
        self,
        provider: str,
        timeout_s: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="AI_TIMEOUT",
            message=f"AI Provider '{provider}' timeout after {timeout_s}s",
            request_id=request_id,
            metadata={
                "provider": provider,
                "timeout_seconds": timeout_s
            },
            http_status_code=504
        )


class SandboxExecutionError(BaseError):
    """
    Code sandbox execution failed (FR-7.3).
    
    Examples:
    - Execution timeout
    - Runtime error in candidate code
    - Memory limit exceeded
    """
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="SANDBOX_EXECUTION_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=500
        )


class SandboxTimeoutError(BaseError):
    """Code execution timeout (FM-3, NFR-3)"""
    
    def __init__(
        self,
        timeout_s: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="EXECUTION_TIMEOUT",
            message=f"Code execution timeout after {timeout_s}s",
            request_id=request_id,
            metadata={"timeout_seconds": timeout_s},
            http_status_code=408
        )


# ============================================================================
# SYSTEM ERRORS (5xx)
# ============================================================================

class InfrastructureError(BaseError):
    """
    Infrastructure component failed.
    
    Examples:
    - Redis connection timeout
    - Postgres connection failed
    - Qdrant unavailable
    """
    
    def __init__(
        self,
        component: str,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata["component"] = component
        
        super().__init__(
            error_code="INFRASTRUCTURE_ERROR",
            message=f"{component} error: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=500
        )


class DatabaseError(BaseError):
    """Database operation failed"""
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="DATABASE_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=500
        )


class CacheError(BaseError):
    """Cache operation failed"""
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="CACHE_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=500
        )


class ConfigurationError(BaseError):
    """System misconfiguration detected"""
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="CONFIG_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=500
        )


class InternalServerError(BaseError):
    """
    Raised for unknown server errors.
    
    Catch-all for unexpected exceptions.
    """
    
    def __init__(
        self,
        message: str = "Internal server error",
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="INTERNAL_SERVER_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=500
        )
