"""
Custom Exception Types

Defines application-specific exceptions for error handling.
Maps to HTTP status codes for API responses.
"""

from typing import Optional, Dict, Any


class ApplicationError(Exception):
    """Base exception for all application errors"""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


# Authentication & Authorization Errors (4xx)

class AuthenticationError(ApplicationError):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed", **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class AuthorizationError(ApplicationError):
    """Raised when user lacks required permissions"""
    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(message, status_code=403, **kwargs)


class TenantIsolationViolation(ApplicationError):
    """Critical: Cross-tenant data access attempt (NFR-7.1)"""
    def __init__(self, message: str = "Tenant isolation violated", **kwargs):
        super().__init__(message, status_code=403, error_code="TENANT_VIOLATION", **kwargs)


# Resource Errors (4xx)

class NotFoundError(ApplicationError):
    """Raised when requested resource doesn't exist"""
    def __init__(self, resource: str, identifier: Any, **kwargs):
        message = f"{resource} with id '{identifier}' not found"
        super().__init__(message, status_code=404, **kwargs)


class ConflictError(ApplicationError):
    """Raised when operation conflicts with current state"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=409, **kwargs)


class ValidationError(ApplicationError):
    """Raised when input validation fails"""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        details = {"field": field} if field else {}
        super().__init__(message, status_code=422, details=details, **kwargs)


# Business Logic Errors (4xx)

class InterviewNotActiveError(ApplicationError):
    """Interview session is not in active state"""
    def __init__(self, submission_id: int, **kwargs):
        super().__init__(
            f"Interview submission {submission_id} is not active",
            status_code=400,
            **kwargs
        )


class InterviewWindowClosedError(ApplicationError):
    """Interview window is not currently open (FR-2.3)"""
    def __init__(self, window_id: int, **kwargs):
        super().__init__(
            f"Interview window {window_id} is closed",
            status_code=400,
            **kwargs
        )


class ConsentNotCapturedError(ApplicationError):
    """User consent not captured before interview (NFR-9)"""
    def __init__(self, **kwargs):
        super().__init__(
            "Explicit user consent required before interview",
            status_code=400,
            error_code="CONSENT_REQUIRED",
            **kwargs
        )


class ExchangeImmutabilityViolation(ApplicationError):
    """Attempt to modify immutable exchange (Architecture Invariant #1)"""
    def __init__(self, exchange_id: int, **kwargs):
        super().__init__(
            f"Interview exchange {exchange_id} is immutable after creation",
            status_code=400,
            error_code="EXCHANGE_IMMUTABLE",
            **kwargs
        )


class TemplateImmutabilityViolation(ApplicationError):
    """Attempt to modify template in use (Architecture Invariant #3)"""
    def __init__(self, template_id: int, **kwargs):
        super().__init__(
            f"Template {template_id} is immutable after use. Create new version.",
            status_code=400,
            error_code="TEMPLATE_IMMUTABLE",
            **kwargs
        )


# External Service Errors (5xx)

class AIProviderError(ApplicationError):
    """AI/LLM provider request failed"""
    def __init__(self, provider: str, message: str, **kwargs):
        super().__init__(
            f"AI Provider '{provider}' error: {message}",
            status_code=503,
            error_code="AI_PROVIDER_ERROR",
            **kwargs
        )


class AIProviderTimeoutError(ApplicationError):
    """AI/LLM provider request timeout (FM-1, NFR-2)"""
    def __init__(self, provider: str, timeout_s: int, **kwargs):
        super().__init__(
            f"AI Provider '{provider}' timeout after {timeout_s}s",
            status_code=504,
            error_code="AI_TIMEOUT",
            **kwargs
        )


class SandboxExecutionError(ApplicationError):
    """Code sandbox execution failed (FR-7.3)"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            f"Sandbox execution error: {message}",
            status_code=500,
            error_code="SANDBOX_ERROR",
            **kwargs
        )


class SandboxTimeoutError(ApplicationError):
    """Code execution timeout (FM-3, NFR-3)"""
    def __init__(self, timeout_s: int, **kwargs):
        super().__init__(
            f"Code execution timeout after {timeout_s}s",
            status_code=408,
            error_code="EXECUTION_TIMEOUT",
            **kwargs
        )


# System Errors (5xx)

class DatabaseError(ApplicationError):
    """Database operation failed"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=500, error_code="DATABASE_ERROR", **kwargs)


class CacheError(ApplicationError):
    """Cache operation failed"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=500, error_code="CACHE_ERROR", **kwargs)


class ConfigurationError(ApplicationError):
    """System misconfiguration detected"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=500, error_code="CONFIG_ERROR", **kwargs)
