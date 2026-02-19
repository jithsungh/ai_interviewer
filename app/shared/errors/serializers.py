"""
Error Serialization

Provides consistent error serialization for REST API and WebSocket protocols.
Ensures errors are properly formatted for client consumption.
"""

from typing import Optional, Dict, Any
from .exceptions import BaseError


def serialize_rest_error(
    error: BaseError,
    request_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Serialize error for REST API response.
    
    Format:
    {
      "error": {
        "code": "ERROR_CODE",
        "message": "Human-readable message",
        "request_id": "req_abc123",
        "metadata": { ... }  # Optional
      }
    }
    
    Args:
        error: BaseError instance to serialize
        request_id: Request ID (overrides error.request_id if provided)
        
    Returns:
        Dictionary suitable for JSON response
        
    Example:
        >>> error = AuthenticationError("Token expired", request_id="req_123")
        >>> serialize_rest_error(error)
        {
          "error": {
            "code": "AUTHENTICATION_FAILED",
            "message": "Token expired",
            "request_id": "req_123"
          }
        }
    """
    error_dict: Dict[str, Any] = {
        "code": error.error_code,
        "message": error.message,
        "request_id": request_id or error.request_id
    }
    
    # Include metadata if present and non-empty
    if error.metadata:
        error_dict["metadata"] = error.metadata
    
    return {"error": error_dict}


def serialize_websocket_error(error: BaseError) -> Dict[str, Any]:
    """
    Serialize error for WebSocket event.
    
    Format:
    {
      "event": "error",
      "payload": {
        "code": "ERROR_CODE",
        "message": "Human-readable message",
        "metadata": { ... }  # Optional
      }
    }
    
    Note: Omits request_id (use connection_id for WebSocket tracing).
    
    Args:
        error: BaseError instance to serialize
        
    Returns:
        Dictionary suitable for WebSocket JSON message
        
    Example:
        >>> error = ValidationError("Invalid answer format")
        >>> serialize_websocket_error(error)
        {
          "event": "error",
          "payload": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid answer format"
          }
        }
    """
    payload: Dict[str, Any] = {
        "code": error.error_code,
        "message": error.message
    }
    
    # Include metadata if present and non-empty
    if error.metadata:
        payload["metadata"] = error.metadata
    
    return {
        "event": "error",
        "payload": payload
    }


def serialize_error_for_logging(
    error: BaseError,
    include_traceback: bool = False
) -> Dict[str, Any]:
    """
    Serialize error for structured logging.
    
    Includes all error fields for debugging and audit trails.
    
    Args:
        error: BaseError instance to serialize
        include_traceback: Whether to include traceback (dev/staging only)
        
    Returns:
        Dictionary suitable for structured logging
    """
    import traceback
    
    log_dict: Dict[str, Any] = {
        "error_code": error.error_code,
        "message": error.message,
        "http_status_code": error.http_status_code,
        "request_id": error.request_id,
        "error_type": error.__class__.__name__
    }
    
    # Include metadata if present
    if error.metadata:
        log_dict["metadata"] = error.metadata
    
    # Include traceback if requested
    if include_traceback:
        if error.__traceback__ is not None:
            # Format the traceback associated with this specific error
            log_dict["traceback"] = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
        else:
            # Fallback to current exception context if no traceback is attached
            log_dict["traceback"] = traceback.format_exc()
    
    return log_dict
