"""
Distributed Tracing

Provides request ID generation, connection ID management, and trace context propagation.
Supports REST, WebSocket, and WebRTC correlation.
"""

import uuid
from dataclasses import dataclass, asdict
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class TraceContext:
    """
    Trace context for propagation across async tasks.
    
    Contains correlation identifiers for distributed tracing:
    - request_id: HTTP request identifier
    - correlation_id: Multi-request flow identifier
    - parent_span_id: Parent span for nested operations
    
    Usage:
        context = TraceContext(request_id="req_abc123")
        
        # Pass to async task
        task.delay(data, trace_context=context.to_dict())
    """
    request_id: str
    correlation_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "TraceContext":
        """Create from dictionary"""
        return cls(**data)


def generate_request_id() -> str:
    """
    Generate unique request ID for HTTP requests.
    
    Format: req_{12_hex_chars}
    
    Returns:
        Unique request ID string
        
    Example:
        >>> generate_request_id()
        "req_a3f2c8d1b6e9"
    """
    return f"req_{uuid.uuid4().hex[:12]}"


def generate_connection_id() -> str:
    """
    Generate unique connection ID for WebSocket/WebRTC connections.
    
    Format: conn_{12_hex_chars}
    
    Returns:
        Unique connection ID string
        
    Example:
        >>> generate_connection_id()
        "conn_7d4b1e9f3c2a"
    """
    return f"conn_{uuid.uuid4().hex[:12]}"


def generate_session_id() -> str:
    """
    Generate unique session ID for WebRTC sessions.
    
    Format: session_{12_hex_chars}
    
    Returns:
        Unique session ID string
        
    Example:
        >>> generate_session_id()
        "session_9c5a2f8b1d3e"
    """
    return f"session_{uuid.uuid4().hex[:12]}"


def generate_correlation_id() -> str:
    """
    Generate unique correlation ID for multi-request flows.
    
    Format: corr_{12_hex_chars}
    
    Returns:
        Unique correlation ID string
        
    Example:
        >>> generate_correlation_id()
        "corr_4e8c1a6d2b9f"
    """
    return f"corr_{uuid.uuid4().hex[:12]}"


def extract_request_id(request: Request) -> str:
    """
    Extract request ID from header or generate new one.
    
    Checks for X-Request-ID header first, generates new ID if not present.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Request ID (extracted or generated)
        
    Example:
        @app.get("/api/users")
        async def get_users(request: Request):
            request_id = extract_request_id(request)
            logger.info(f"Request {request_id}: Fetching users")
    """
    request_id = request.headers.get("X-Request-ID")

    if not request_id:
        request_id = generate_request_id()

    return request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject request ID into request state and response headers.
    
    For each request:
    - Extracts X-Request-ID header or generates new ID
    - Injects into request.state.request_id
    - Adds X-Request-ID to response headers
    
    Usage:
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        
        @app.get("/api/users")
        async def get_users(request: Request):
            request_id = request.state.request_id
            logger.info(f"Request {request_id}: Fetching users")
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and inject request ID.
        
        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler
            
        Returns:
            Response with X-Request-ID header
        """
        # Extract or generate request ID
        request_id = extract_request_id(request)

        # Inject into request state
        request.state.request_id = request_id

        # Call next middleware
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


def create_trace_context_from_request(request: Request) -> TraceContext:
    """
    Create TraceContext from FastAPI request.
    
    Args:
        request: FastAPI Request object
        
    Returns:
        TraceContext with request_id
        
    Example:
        @app.post("/api/process")
        async def process_data(request: Request):
            context = create_trace_context_from_request(request)
            await async_task.delay(data, trace_context=context.to_dict())
    """
    request_id = getattr(request.state, "request_id", generate_request_id())
    
    return TraceContext(
        request_id=request_id,
        correlation_id=request.headers.get("X-Correlation-ID"),
    )
