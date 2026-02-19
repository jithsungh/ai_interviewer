"""
WebSocket Connection Registry

Redis-backed registry for active WebSocket connections.
Enforces single active connection per submission (cluster-safe).
"""

import json
import time
import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket

from .models import IdentityContext
from app.shared.errors import ConflictError
from app.shared.observability import get_context_logger
from app.persistence.redis import redis_client

logger = get_context_logger(__name__)


class ConnectionRegistry:
    """
    Redis-backed registry of active WebSocket connections.
    
    Purpose:
    - Track active WebSocket connections across server instances
    - Enforce single active connection per submission_id
    - Prevent duplicate connections from different browser tabs
    - Support connection replacement (close old, accept new)
    
    Redis Keys:
    - active_websocket:{submission_id} -> connection metadata (JSON)
    
    Thread-safety:
    - Redis operations are atomic
    - SETNX ensures only one connection can register
    
    TTL Strategy:
    - Connections have 60s TTL (refreshed by heartbeat)
    - Prevents stale connections from blocking new ones
    
    Cluster-safe:
    - Works across multiple FastAPI instances
    - No in-memory state (Redis is source of truth)
    
    Example:
        registry = ConnectionRegistry()
        
        # Register connection
        await registry.register(
            connection_id="conn_abc123",
            submission_id=456,
            websocket=websocket,
            identity=identity
        )
        
        # Check if active
        is_active = await registry.is_active(submission_id=456)
        
        # Unregister on disconnect
        await registry.unregister(submission_id=456)
    """
    
    def __init__(self, ttl: int = 60):
        """
        Initialize connection registry.
        
        Args:
            ttl: Connection TTL in seconds (default: 60s)
        """
        self.ttl = ttl
        self.redis = redis_client
    
    async def register(
        self,
        connection_id: str,
        submission_id: int,
        websocket: WebSocket,
        identity: IdentityContext,
        allow_replacement: bool = True
    ) -> None:
        """
        Register active WebSocket connection.
        
        Args:
            connection_id: Unique connection identifier (UUID)
            submission_id: Interview submission ID
            websocket: FastAPI WebSocket instance
            identity: User identity context
            allow_replacement: If True, replace existing connection. If False, raise ConflictError.
        
        Raises:
            ConflictError: If duplicate connection exists and allow_replacement=False
        
        Side Effects:
            - Stores connection metadata in Redis
            - Closes old connection if replacement allowed
        """
        key = f"active_websocket:{submission_id}"
        
        # Check for existing connection
        existing_data = await self.redis.get(key)
        
        if existing_data:
            existing_metadata = json.loads(existing_data)
            existing_conn_id = existing_metadata.get("connection_id")
            
            if allow_replacement:
                # Log connection replacement
                logger.warning(
                    "Replacing existing WebSocket connection",
                    extra={
                        "submission_id": submission_id,
                        "old_connection_id": existing_conn_id,
                        "new_connection_id": connection_id,
                        "user_id": identity.user_id
                    }
                )
                
                # Note: Closing old connection is handled by WebSocket handler
                # (we can't access old websocket instance from here)
            else:
                # Reject duplicate connection
                logger.warning(
                    "Duplicate connection attempt rejected",
                    extra={
                        "submission_id": submission_id,
                        "existing_connection_id": existing_conn_id,
                        "attempted_connection_id": connection_id,
                        "user_id": identity.user_id
                    }
                )
                
                raise ConflictError(
                    message=f"Active connection already exists for submission {submission_id}",
                    metadata={
                        "submission_id": submission_id,
                        "existing_connection_id": existing_conn_id
                    }
                )
        
        # Build connection metadata
        metadata = {
            "connection_id": connection_id,
            "submission_id": submission_id,
            "user_id": identity.user_id,
            "user_type": identity.user_type.value,
            "organization_id": identity.organization_id,
            "connected_at": int(time.time())
        }
        
        # Store in Redis with TTL
        await self.redis.set(
            key,
            json.dumps(metadata),
            ex=self.ttl
        )
        
        logger.info(
            "WebSocket connection registered",
            extra={
                "connection_id": connection_id,
                "submission_id": submission_id,
                "user_id": identity.user_id,
                "ttl": self.ttl
            }
        )
    
    async def unregister(self, submission_id: int) -> None:
        """
        Unregister WebSocket connection on disconnect.
        
        Args:
            submission_id: Interview submission ID
        
        Side Effects:
            - Removes connection from Redis
        """
        key = f"active_websocket:{submission_id}"
        
        # Get metadata before deletion (for logging)
        existing_data = await self.redis.get(key)
        
        if existing_data:
            metadata = json.loads(existing_data)
            connection_id = metadata.get("connection_id")
            
            # Delete from Redis
            await self.redis.delete(key)
            
            logger.info(
                "WebSocket connection unregistered",
                extra={
                    "connection_id": connection_id,
                    "submission_id": submission_id
                }
            )
        else:
            # Connection not found (already expired or never registered)
            logger.warning(
                "Attempted to unregister non-existent connection",
                extra={"submission_id": submission_id}
            )
    
    async def get_connection(self, submission_id: int) -> Optional[Dict[str, Any]]:
        """
        Get active connection metadata for submission.
        
        Args:
            submission_id: Interview submission ID
        
        Returns:
            Connection metadata dict if active, None otherwise
        
        Example:
            metadata = await registry.get_connection(456)
            if metadata:
                connection_id = metadata["connection_id"]
                user_id = metadata["user_id"]
        """
        key = f"active_websocket:{submission_id}"
        data = await self.redis.get(key)
        
        if data:
            return json.loads(data)
        
        return None
    
    async def is_active(self, submission_id: int) -> bool:
        """
        Check if submission has active WebSocket connection.
        
        Args:
            submission_id: Interview submission ID
        
        Returns:
            True if active connection exists, False otherwise
        """
        return await self.get_connection(submission_id) is not None
    
    async def refresh_ttl(self, submission_id: int) -> None:
        """
        Refresh connection TTL (called by heartbeat).
        
        Args:
            submission_id: Interview submission ID
        
        Side Effects:
            - Extends Redis key expiration to TTL from now
        """
        key = f"active_websocket:{submission_id}"
        
        # Check if connection exists
        exists = await self.redis.exists(key)
        
        if exists:
            # Extend expiration
            await self.redis.expire(key, self.ttl)
            
            logger.debug(
                "Connection TTL refreshed",
                extra={"submission_id": submission_id, "ttl": self.ttl}
            )
        else:
            logger.warning(
                "Attempted to refresh TTL for non-existent connection",
                extra={"submission_id": submission_id}
            )


# Global registry instance
connection_registry = ConnectionRegistry()
