"""
WebSocket Connection Manager

Manages active WebSocket connections with dual-layer tracking:
1. In-memory dict: Direct access to WebSocket instances for this process
2. Redis keys: Cross-process connection state (cluster-safe)

Redis Keys:
- active_websocket:{submission_id} → connection_id (TTL 60s, refreshed by heartbeat)
- websocket_session:{connection_id} → session metadata JSON (TTL 3900s)

Responsibilities:
- Connection acceptance and registration
- Connection replacement (single active connection per submission)
- Heartbeat TTL refresh
- Clean disconnect and resource cleanup
- Send message to specific submission

This is NOT a singleton — one instance per application process.
"""

from __future__ import annotations

import json
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import WebSocket
from redis import Redis

from app.shared.observability import get_context_logger

logger = get_context_logger()

# Redis key TTLs (seconds)
CONNECTION_TTL = 60           # Active connection TTL, refreshed by heartbeat
SESSION_METADATA_TTL = 3900   # Session metadata TTL (~65 minutes)


class ConnectionManager:
    """
    Dual-layer WebSocket connection manager.

    In-memory layer: Dict[submission_id, WebSocket] for direct message sending.
    Redis layer: Connection metadata for cross-process state and TTL tracking.

    Thread-safety:
    - Redis operations are atomic (SET NX, EXPIRE, DEL)
    - In-memory dict is per-process (no cross-thread contention in asyncio)

    Example:
        manager = ConnectionManager(redis=get_redis_client())
        await manager.connect(ws, submission_id=123, connection_id="conn_abc", user_id=42)
        await manager.send_event(123, {"event_type": "heartbeat_ack", ...})
        await manager.disconnect(123)
    """

    def __init__(self, redis: Redis) -> None:
        self._redis = redis
        self._active: Dict[int, WebSocket] = {}  # submission_id → WebSocket

    # ──────────────────────────────────────────────────────────────
    # Connection Lifecycle
    # ──────────────────────────────────────────────────────────────

    async def connect(
        self,
        websocket: WebSocket,
        submission_id: int,
        connection_id: str,
        user_id: int,
    ) -> Optional[str]:
        """
        Register a new WebSocket connection.

        Steps:
        1. Check for existing connection in Redis
        2. If exists, send connection_replaced to old WS and close it
        3. Accept new WebSocket
        4. Register in Redis + in-memory

        Args:
            websocket: New WebSocket connection (not yet accepted)
            submission_id: Interview submission ID
            connection_id: Unique connection ID (from generate_connection_id)
            user_id: Authenticated user ID

        Returns:
            Old connection_id if replacement occurred, None otherwise.
        """
        replaced_conn_id: Optional[str] = None
        key = f"active_websocket:{submission_id}"

        # 1. Check for existing connection
        existing_raw = self._redis.get(key)
        if existing_raw:
            replaced_conn_id = existing_raw
            old_ws = self._active.get(submission_id)
            if old_ws:
                # Send replacement notification to old connection
                try:
                    from app.interview.realtime.contracts.events import (
                        ConnectionReplacedEvent,
                    )

                    event = ConnectionReplacedEvent(
                        new_connection_id=connection_id,
                        timestamp=_now_iso(),
                    )
                    await old_ws.send_json(event.model_dump())
                    await old_ws.close(code=1000, reason="Connection replaced")
                except Exception:
                    # Old connection may already be dead
                    pass

            logger.warning(
                "Replacing existing WebSocket connection",
                event_type="ws.connection.replaced",
                metadata={
                    "submission_id": submission_id,
                    "old_connection_id": replaced_conn_id,
                    "new_connection_id": connection_id,
                    "user_id": user_id,
                },
            )

        # 2. Accept new connection
        await websocket.accept()

        # 3. Register in Redis
        self._redis.set(key, connection_id, ex=CONNECTION_TTL)

        # 4. Store session metadata in Redis
        session_key = f"websocket_session:{connection_id}"
        metadata = {
            "connection_id": connection_id,
            "submission_id": submission_id,
            "user_id": user_id,
            "connected_at": _now_iso(),
            "last_heartbeat_at": _now_iso(),
        }
        self._redis.set(session_key, json.dumps(metadata), ex=SESSION_METADATA_TTL)

        # 5. Register in-memory
        self._active[submission_id] = websocket

        logger.info(
            "WebSocket connection registered",
            event_type="ws.connection.registered",
            metadata={
                "connection_id": connection_id,
                "submission_id": submission_id,
                "user_id": user_id,
            },
        )

        return replaced_conn_id

    async def disconnect(self, submission_id: int, connection_id: str) -> None:
        """
        Unregister WebSocket connection on disconnect.

        Removes from both in-memory dict and Redis.
        Only removes Redis key if it matches the given connection_id
        (prevents deleting a replacement connection's key).

        Args:
            submission_id: Interview submission ID
            connection_id: Connection ID to unregister
        """
        # Remove from in-memory
        self._active.pop(submission_id, None)

        # Remove from Redis (only if we still own the key)
        key = f"active_websocket:{submission_id}"
        current = self._redis.get(key)
        if current == connection_id:
            self._redis.delete(key)

        # Clean up session metadata
        session_key = f"websocket_session:{connection_id}"
        self._redis.delete(session_key)

        logger.info(
            "WebSocket connection unregistered",
            event_type="ws.connection.unregistered",
            metadata={
                "connection_id": connection_id,
                "submission_id": submission_id,
            },
        )

    # ──────────────────────────────────────────────────────────────
    # Heartbeat
    # ──────────────────────────────────────────────────────────────

    def refresh_heartbeat(self, submission_id: int, connection_id: str) -> None:
        """
        Refresh connection TTL on heartbeat.

        Extends active_websocket key by CONNECTION_TTL seconds.
        Updates last_heartbeat_at in session metadata.

        Args:
            submission_id: Interview submission ID
            connection_id: Connection ID
        """
        key = f"active_websocket:{submission_id}"
        self._redis.expire(key, CONNECTION_TTL)

        # Update session metadata heartbeat timestamp
        session_key = f"websocket_session:{connection_id}"
        raw = self._redis.get(session_key)
        if raw:
            try:
                metadata = json.loads(raw)
                metadata["last_heartbeat_at"] = _now_iso()
                self._redis.set(
                    session_key, json.dumps(metadata), ex=SESSION_METADATA_TTL
                )
            except (json.JSONDecodeError, TypeError):
                pass

    # ──────────────────────────────────────────────────────────────
    # Messaging
    # ──────────────────────────────────────────────────────────────

    async def send_event(self, submission_id: int, event: Dict[str, Any]) -> bool:
        """
        Send event dict to specific submission's WebSocket.

        Args:
            submission_id: Target submission
            event: Event dict to send (already model_dump()'d)

        Returns:
            True if sent successfully, False if no active connection.
        """
        ws = self._active.get(submission_id)
        if ws is None:
            return False

        try:
            await ws.send_json(event)
            return True
        except Exception as e:
            logger.warning(
                f"Failed to send WebSocket event: {e}",
                event_type="ws.send.failed",
                metadata={
                    "submission_id": submission_id,
                    "event_type": event.get("event_type"),
                },
            )
            return False

    # ──────────────────────────────────────────────────────────────
    # Query
    # ──────────────────────────────────────────────────────────────

    def is_connected(self, submission_id: int) -> bool:
        """Check if submission has an active in-memory connection."""
        return submission_id in self._active

    def get_connection_metadata(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session metadata from Redis for a connection.

        Returns:
            Metadata dict if found, None otherwise.
        """
        session_key = f"websocket_session:{connection_id}"
        raw = self._redis.get(session_key)
        if raw:
            try:
                return json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                return None
        return None


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
