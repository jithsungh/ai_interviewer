"""
Global Exception Handlers

Registers exception handlers for consistent error responses across all endpoints.

Handles:
- Application errors (BaseError and subclasses)
- Pydantic validation errors
- FastAPI HTTP exceptions
- Unexpected Python exceptions (500)
"""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.shared.errors import BaseError, ValidationError as AppValidationError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


async def base_error_handler(request: Request, exc: BaseError) -> JSONResponse:
    """
    Handle all application errors extending BaseError.
    
    Returns structured JSON response with:
    - error_code: Machine-readable error identifier
    - message: Human-readable error description
    - request_id: Request correlation ID
    - metadata: Additional context (if provided)
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Enrich error with request_id if not already set
    if not exc.request_id:
        exc.request_id = request_id
    
    # Log error
    logger.error(
        f"Application error: {exc.error_code} - {exc.message}",
        event_type=f"error.{exc.error_code}",
        metadata={
            "error_code": exc.error_code,
            "http_status_code": exc.http_status_code,
            "request_id": exc.request_id,
            "error_metadata": exc.metadata
        }
    )
    
    # Return structured error response
    return JSONResponse(
        status_code=exc.http_status_code,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "request_id": exc.request_id,
                "metadata": exc.metadata or {}
            }
        }
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors from request body/query/path params.
    
    Converts Pydantic errors to structured ValidationError format.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Extract validation errors
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    # Log validation error
    logger.warning(
        f"Validation error: {len(errors)} field(s) invalid",
        event_type="error.validation",
        metadata={
            "request_id": request_id,
            "errors": errors,
            "url": str(request.url)
        }
    )
    
    # Return structured validation error
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "request_id": request_id,
                "metadata": {
                    "errors": errors
                }
            }
        }
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """
    Handle FastAPI HTTP exceptions (raised by framework or manually).
    
    Wraps in consistent error format.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log HTTP exception
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        event_type="error.http_exception",
        metadata={
            "status_code": exc.status_code,
            "detail": exc.detail,
            "request_id": request_id
        }
    )
    
    # Return structured error
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"http_{exc.status_code}",
                "message": exc.detail,
                "request_id": request_id,
                "metadata": {}
            }
        }
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected Python exceptions.
    
    Returns 500 Internal Server Error without exposing internal details.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log unexpected error with full traceback
    logger.critical(
        f"Unhandled exception: {type(exc).__name__} - {str(exc)}",
        event_type="error.unhandled",
        exc_info=True,
        metadata={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "request_id": request_id,
            "url": str(request.url)
        }
    )
    
    # Return generic 500 error (don't expose internals)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected error occurred. Please contact support.",
                "request_id": request_id,
                "metadata": {}
            }
        }
    )


def register_exception_handlers(app: FastAPI) -> None:
    """
    Register all global exception handlers.
    
    Args:
        app: FastAPI application instance
    
    Handler Priority:
    1. BaseError (most specific - application errors)
    2. RequestValidationError (Pydantic validation)
    3. HTTPException (FastAPI framework exceptions)
    4. Exception (catch-all for unexpected errors)
    """
    
    logger.info("Registering exception handlers...", event_type="exception_handlers.registration.begin")
    
    # 1. Application errors (BaseError and subclasses)
    app.add_exception_handler(BaseError, base_error_handler)
    logger.debug("✓ BaseError handler registered")
    
    # 2. Pydantic validation errors
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    logger.debug("✓ RequestValidationError handler registered")
    
    # 3. FastAPI HTTP exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    logger.debug("✓ HTTPException handler registered")
    
    # 4. Catch-all for unexpected errors
    app.add_exception_handler(Exception, unhandled_exception_handler)
    logger.debug("✓ Unhandled exception handler registered")
    
    logger.info(
        "✅ Exception handlers registration complete",
        event_type="exception_handlers.registration.complete",
        metadata={"handler_count": 4}
    )
