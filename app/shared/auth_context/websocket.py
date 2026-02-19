"""
WebSocket Authentication

Helper functions for authenticating WebSocket connections.
Validates token and binds identity to connection.
"""

import logging
from typing import Callable
from fastapi import WebSocket

from .models import IdentityContext
from .builder import IdentityBuilder
# Note: connection_registry is available separately for registration
from app.shared.errors import AuthenticationError
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


async def authenticate_websocket(
    websocket: WebSocket,
    token: str,
    token_validator: Callable
) -> IdentityContext:
    """
    Authenticate WebSocket connection and return identity.
    
    Flow:
    1. Validate JWT token (via auth module)
    2. Build IdentityContext from claims
    3. Check token expiry
    4. Return identity
    
    Note: This does NOT register the connection.
    Registration happens in WebSocket handler after identity is established.
    
    Args:
        websocket: WebSocket connection instance
        token: Access token (from query param or header)
        token_validator: Function that validates JWT and returns claims
    
    Returns:
        IdentityContext if authentication succeeds
    
    Raises:
        AuthenticationError: If token invalid or expired
    
    Example:
        from app.shared.auth_context import ConnectionRegistry
        
        connection_registry = ConnectionRegistry()
        
        @app.websocket("/ws/interview/{submission_id}")
        async def interview_websocket(
            websocket: WebSocket,
            submission_id: int,
            token: str = Query(...)
        ):
            # Authenticate before accepting connection
            try:
                identity = await authenticate_websocket(
                    websocket,
                    token,
                    validate_access_token
                )
            except AuthenticationError:
                await websocket.close(code=1008, reason="Authentication failed")
                return
            
            # Accept connection
            await websocket.accept()
            
            # Register connection
            connection_id = generate_connection_id()
            await connection_registry.register(
                connection_id=connection_id,
                submission_id=submission_id,
                websocket=websocket,
                identity=identity
            )
            
            # Handle messages...
    """
    # Validate token
    try:
        claims = await token_validator(token)
    except AuthenticationError as e:
        logger.warning(
            f"WebSocket authentication failed: {e.message}",
            metadata={"error": str(e)}
        )
        raise
    except Exception as e:
        logger.error(
            f"WebSocket token validation error: {e}"
        )
        raise AuthenticationError(
            message="Token validation error",
            metadata={"error": str(e)}
        )
    
    # Build identity
    try:
        identity = IdentityBuilder.from_jwt_claims(claims)
    except (ValueError, KeyError) as e:
        logger.error(
            f"Failed to build IdentityContext for WebSocket: {e}",
            metadata={"claims": claims}
        )
        raise AuthenticationError(
            message=f"Invalid token claims: {e}",
            metadata={"error": str(e)}
        )
    
    # Check expiry
    if identity.is_expired():
        logger.warning(
            "Expired token in WebSocket authentication",
            metadata={
                "user_id": identity.user_id,
                "expires_at": identity.expires_at
            }
        )
        raise AuthenticationError(
            message="Token expired",
            metadata={
                "user_id": identity.user_id,
                "expires_at": identity.expires_at
            }
        )
    
    logger.info(
        "WebSocket authenticated",
        metadata={
            "user_id": identity.user_id,
            "user_type": identity.user_type.value,
            "organization_id": identity.organization_id
        }
    )
    
    return identity


def generate_connection_id() -> str:
    """
    Generate unique connection ID for WebSocket.
    
    Returns:
        Connection ID string (format: "conn_{uuid}")
    
    Example:
        connection_id = generate_connection_id()
        # "conn_abc123-def456-..."
    """
    import uuid
    return f"conn_{uuid.uuid4()}"
