"""
Error Classification

Determines error severity and handling strategies.
Critical for WebSocket connection management (fatal vs recoverable).
"""

from typing import Type
from .exceptions import (
    BaseError,
    AuthenticationError,
    AuthorizationError,
    DomainInvariantViolation,
    TenantIsolationViolation,
)


def is_fatal_error(error: BaseError) -> bool:
    """
    Determine if error is fatal (requires WebSocket connection close).
    
    Fatal errors indicate the connection cannot continue:
    - AuthenticationError: Invalid/expired token → cannot authenticate
    - AuthorizationError: Insufficient permissions → cannot authorize
    - TenantIsolationViolation: Security violation → must close
    - DomainInvariantViolation: System bug → unsafe to continue
    
    Recoverable errors allow connection to remain open:
    - ValidationError: Invalid input → user can retry
    - NotFoundError: Resource not found → can try another action
    - ConflictError: State conflict → can resolve
    - ProctoringViolation: Advisory event → non-blocking
    
    Args:
        error: BaseError instance to classify
        
    Returns:
        True if error requires connection close, False otherwise
        
    Example:
        >>> error = AuthenticationError("Token expired")
        >>> is_fatal_error(error)
        True
        
        >>> error = ValidationError("Invalid field")
        >>> is_fatal_error(error)
        False
    """
    # Fatal error types
    fatal_types: tuple[Type[BaseError], ...] = (
        AuthenticationError,
        AuthorizationError,
        TenantIsolationViolation,
        DomainInvariantViolation,
    )
    
    return isinstance(error, fatal_types)


def get_log_level(error: BaseError) -> str:
    """
    Determine appropriate log level for error.
    
    Logging strategy:
    - CRITICAL: Domain invariant violations (system bugs)
    - ERROR: Server errors (5xx) - infrastructure failures
    - WARN: Client errors (4xx) - user errors
    - INFO: Advisory events (proctoring violations)
    
    Args:
        error: BaseError instance to classify
        
    Returns:
        Log level string ("DEBUG", "INFO", "WARN", "ERROR", "CRITICAL")
        
    Example:
        >>> error = DomainInvariantViolation("template_immutable", "Template modified")
        >>> get_log_level(error)
        "CRITICAL"
        
        >>> error = ValidationError("Invalid field")
        >>> get_log_level(error)
        "WARN"
    """
    # Critical: Domain invariant violations
    if isinstance(error, DomainInvariantViolation):
        return "CRITICAL"
    
    # Error: Server errors (5xx)
    if error.http_status_code >= 500:
        return "ERROR"
    
    # Warn: Client errors (4xx)
    if error.http_status_code >= 400:
        return "WARN"
    
    # Info: Advisory events (2xx)
    return "INFO"


def should_send_to_client(error: BaseError, is_production: bool) -> bool:
    """
    Determine if error details should be sent to client.
    
    Security considerations:
    - Production: Send minimal info for 5xx errors (no stack traces)
    - Development: Send full details for debugging
    - Always send full details for 4xx errors (user's fault)
    
    Args:
        error: BaseError instance to classify
        is_production: Whether running in production environment
        
    Returns:
        True if full error details should be sent to client
        
    Example:
        >>> error = InternalServerError("Database connection failed")
        >>> should_send_to_client(error, is_production=True)
        False  # Don't expose internal details in production
        
        >>> should_send_to_client(error, is_production=False)
        True  # Send details in development
    """
    # Always send 4xx errors (client's fault)
    if error.http_status_code < 500:
        return True
    
    # In development, send all error details
    if not is_production:
        return True
    
    # In production, don't expose 5xx error details
    return False
