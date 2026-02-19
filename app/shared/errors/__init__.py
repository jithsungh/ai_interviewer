"""
Unified Error Handling Module

Provides:
- Structured exception hierarchy (BaseError and subclasses)
- Error serialization for REST API and WebSocket protocols
- Error classification (fatal vs recoverable)
- Error configuration (logging, serialization, WebSocket behavior)

Public API:
- Exception classes: BaseError, ApplicationError, etc.
- Serialization: serialize_rest_error, serialize_websocket_error
- Classification: is_fatal_error, get_log_level
- Configuration: ErrorConfig, error_config
"""

# Exception classes
from .exceptions import (
    # Base classes
    BaseError,
    ApplicationError,  # Backward compatibility alias
    
    # Client errors (4xx)
    AuthenticationError,
    AuthorizationError,
    TenantIsolationViolation,
    NotFoundError,
    ConflictError,
    ValidationError,
    RateLimitExceeded,
    
    # Business logic errors
    InterviewNotActiveError,
    InterviewWindowClosedError,
    ConsentNotCapturedError,
    
    # Domain errors
    ExchangeImmutabilityViolation,
    TemplateImmutabilityViolation,
    DomainInvariantViolation,
    ProctoringViolation,
    
    # External service errors (5xx)
    AIProviderError,
    AIProviderTimeoutError,
    SandboxExecutionError,
    SandboxTimeoutError,
    
    # System errors (5xx)
    InfrastructureError,
    DatabaseError,
    CacheError,
    ConfigurationError,
    InternalServerError,
)

# Serialization functions
from .serializers import (
    serialize_rest_error,
    serialize_websocket_error,
    serialize_error_for_logging,
)

# Classification functions
from .classification import (
    is_fatal_error,
    get_log_level,
    should_send_to_client,
)

# Configuration
from .config import (
    ErrorConfig,
    error_config,
)

__all__ = [
    # Base classes
    "BaseError",
    "ApplicationError",
    
    # Client errors (4xx)
    "AuthenticationError",
    "AuthorizationError",
    "TenantIsolationViolation",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "RateLimitExceeded",
    
    # Business logic errors
    "InterviewNotActiveError",
    "InterviewWindowClosedError",
    "ConsentNotCapturedError",
    
    # Domain errors
    "ExchangeImmutabilityViolation",
    "TemplateImmutabilityViolation",
    "DomainInvariantViolation",
    "ProctoringViolation",
    
    # External service errors
    "AIProviderError",
    "AIProviderTimeoutError",
    "SandboxExecutionError",
    "SandboxTimeoutError",
    
    # System errors
    "InfrastructureError",
    "DatabaseError",
    "CacheError",
    "ConfigurationError",
    "InternalServerError",
    
    # Serialization
    "serialize_rest_error",
    "serialize_websocket_error",
    "serialize_error_for_logging",
    
    # Classification
    "is_fatal_error",
    "get_log_level",
    "should_send_to_client",
    
    # Configuration
    "ErrorConfig",
    "error_config",
]
