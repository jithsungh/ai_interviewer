"""
WebSocket Endpoint for Live Interview Sessions

Route: /ws/interview/{submission_id}?token=<JWT>

Connection lifecycle:
1. Client connects with JWT token as query parameter
2. Server validates token, checks submission ownership
3. Server accepts connection, registers in Redis, sends connection_established
4. Client sends join_session → server responds with session state
5. Client sends events (request_next_question, submit_answer, submit_code, heartbeat)
6. Server responds with events (question_payload, answer_accepted, progress_update, etc.)
7. On disconnect: cleanup Redis, remove from in-memory tracking

Authentication:
- JWT from query param `token`
- Validated via shared auth_context.authenticate_websocket()
- Only candidates allowed (user_type = candidate)

Connection Discipline:
- One active connection per submission_id (Redis enforced)
- New connection replaces old (connection_replaced event sent to old)
- Heartbeat every 30s refreshes Redis TTL (60s)
- No heartbeat for 60s → Redis key expires → considered disconnected
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.interview.realtime.contracts.events import (
    ConnectionEstablishedEvent,
    ErrorEvent,
    parse_client_event,
    HeartbeatEvent,
    JoinSessionEvent,
    RequestNextQuestionEvent,
    SubmitAnswerEvent,
    SubmitCodeEvent,
)
from app.interview.realtime.domain.connection_manager import ConnectionManager
from app.interview.realtime.domain.event_handler import RealtimeEventHandler
from app.persistence.postgres.session import get_session_factory
from app.persistence.redis.client import get_redis_client
from app.shared.auth_context import (
    UserType,
    authenticate_websocket,
    generate_connection_id,
    get_token_validator,
)
from app.shared.errors import (
    AuthenticationError,
    BaseError,
    is_fatal_error,
    serialize_websocket_error,
)
from app.shared.observability import get_context_logger

router = APIRouter()

# Module-level connection manager (shared across all WebSocket connections in this process)
_manager: Optional[ConnectionManager] = None


def _get_manager() -> ConnectionManager:
    """Lazily initialize the connection manager."""
    global _manager
    if _manager is None:
        _manager = ConnectionManager(redis=get_redis_client())
    return _manager


@router.websocket("/ws/interview/{submission_id}")
async def interview_websocket(
    websocket: WebSocket,
    submission_id: int,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """
    WebSocket endpoint for live interview sessions.

    Path: /ws/interview/{submission_id}?token=<JWT>

    Flow:
    1. Authenticate JWT from query parameter
    2. Verify user is candidate type
    3. Accept connection (replace existing if any)
    4. Send connection_established
    5. Enter message loop (dispatch events to handler)
    6. Cleanup on disconnect

    Close codes:
    - 1000: Normal close (interview completed, connection replaced)
    - 1008: Policy violation (auth failure, unauthorized)
    - 1011: Server error (unexpected failure)
    """
    connection_id = generate_connection_id()
    ws_logger = get_context_logger(
        connection_id=connection_id,
        submission_id=submission_id,
    )

    # ──────────────────────────────────────────────────────────
    # Step 1: Authenticate
    # ──────────────────────────────────────────────────────────
    try:
        token_validator = get_token_validator()
        identity = await authenticate_websocket(websocket, token, token_validator)
    except AuthenticationError as e:
        ws_logger.warning(
            f"WebSocket auth failed for submission {submission_id}: {e.message}",
            event_type="ws.auth.failed",
        )
        # Reject connection — must accept before close per ASGI spec
        await websocket.accept()
        await websocket.close(code=1008, reason="Authentication failed")
        return
    except Exception as e:
        ws_logger.error(
            f"Unexpected auth error for submission {submission_id}: {e}",
            event_type="ws.auth.error",
            exc_info=True,
        )
        await websocket.accept()
        await websocket.close(code=1008, reason="Authentication error")
        return

    # ──────────────────────────────────────────────────────────
    # Step 2: Verify candidate type
    # ──────────────────────────────────────────────────────────
    if identity.user_type != UserType.CANDIDATE:
        ws_logger.warning(
            f"Non-candidate user {identity.user_id} attempted WS connection",
            event_type="ws.auth.not_candidate",
        )
        await websocket.accept()
        await websocket.close(code=1008, reason="Candidate access required")
        return

    candidate_id = identity.candidate_id  # candidates.id, not users.id

    ws_logger = get_context_logger(
        connection_id=connection_id,
        submission_id=submission_id,
        user_id=identity.user_id,
    )

    # ──────────────────────────────────────────────────────────
    # Step 3: Accept & Register connection
    # ──────────────────────────────────────────────────────────
    manager = _get_manager()

    try:
        replaced = await manager.connect(
            websocket=websocket,
            submission_id=submission_id,
            connection_id=connection_id,
            user_id=candidate_id,
        )
        if replaced:
            ws_logger.info(
                f"Replaced connection {replaced}",
                event_type="ws.connection.replaced",
            )
    except Exception as e:
        ws_logger.error(
            f"Failed to register connection: {e}",
            event_type="ws.connection.register_failed",
            exc_info=True,
        )
        try:
            await websocket.close(code=1011, reason="Connection registration failed")
        except Exception:
            pass
        return

    # ──────────────────────────────────────────────────────────
    # Step 4: Send connection_established
    # ──────────────────────────────────────────────────────────
    established_event = ConnectionEstablishedEvent(
        submission_id=submission_id,
        connection_id=connection_id,
        server_time=datetime.now(timezone.utc).isoformat(),
    )
    await manager.send_event(submission_id, established_event.model_dump())

    ws_logger.info(
        "WebSocket connection established",
        event_type="ws.connection.established",
    )

    # ──────────────────────────────────────────────────────────
    # Step 5: Message loop
    # ──────────────────────────────────────────────────────────
    try:
        while True:
            raw = await websocket.receive_text()
            await _dispatch_event(
                raw_message=raw,
                submission_id=submission_id,
                candidate_id=candidate_id,
                connection_id=connection_id,
                manager=manager,
                ws_logger=ws_logger,
            )
    except WebSocketDisconnect as e:
        ws_logger.info(
            f"WebSocket disconnected (code={e.code})",
            event_type="ws.connection.disconnected",
            metadata={"close_code": e.code},
        )
    except Exception as e:
        ws_logger.error(
            f"Unexpected WebSocket error: {e}",
            event_type="ws.error.unexpected",
            exc_info=True,
        )
        try:
            error_event = ErrorEvent(
                error_code="SERVER_ERROR",
                message="Internal server error",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            await manager.send_event(submission_id, error_event.model_dump())
            await websocket.close(code=1011, reason="Internal server error")
        except Exception:
            pass
    finally:
        # ──────────────────────────────────────────────────────
        # Step 6: Cleanup
        # ──────────────────────────────────────────────────────
        await manager.disconnect(submission_id, connection_id)
        ws_logger.info(
            "WebSocket connection cleaned up",
            event_type="ws.connection.cleanup",
        )


async def _dispatch_event(
    raw_message: str,
    submission_id: int,
    candidate_id: int,
    connection_id: str,
    manager: ConnectionManager,
    ws_logger,
) -> None:
    """
    Parse, validate, and dispatch a single client event.

    Creates a fresh DB session per event (auto-commit on success).
    Catches all errors and sends ErrorEvent to client.
    Fatal errors close the connection.
    """
    try:
        data = json.loads(raw_message)
    except json.JSONDecodeError as e:
        error_event = ErrorEvent(
            error_code="VALIDATION_ERROR",
            message=f"Invalid JSON: {e}",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await manager.send_event(submission_id, error_event.model_dump())
        return

    try:
        event = parse_client_event(data)
    except (ValueError, Exception) as e:
        error_event = ErrorEvent(
            error_code="VALIDATION_ERROR",
            message=str(e),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await manager.send_event(submission_id, error_event.model_dump())
        return

    ws_logger.debug(
        f"Received event: {event.event_type}",
        event_type=f"ws.event.received.{event.event_type}",
    )

    # ── Heartbeat (no DB needed) ──────────────────────────────
    if isinstance(event, HeartbeatEvent):
        manager.refresh_heartbeat(submission_id, connection_id)
        db = get_session_factory()()
        try:
            handler = RealtimeEventHandler(
                db=db,
                redis=get_redis_client(),
                submission_id=submission_id,
                connection_id=connection_id,
            )
            response = handler.handle_heartbeat()
        finally:
            db.close()
        await manager.send_event(submission_id, response)
        return

    # ── Events that need DB session ───────────────────────────
    db = get_session_factory()()
    try:
        handler = RealtimeEventHandler(
            db=db,
            redis=get_redis_client(),
            submission_id=submission_id,
            connection_id=connection_id,
        )

        response: Optional[dict] = None

        if isinstance(event, JoinSessionEvent):
            response = handler.handle_join_session(candidate_id=candidate_id)

        elif isinstance(event, RequestNextQuestionEvent):
            response = handler.handle_request_next_question()

        elif isinstance(event, SubmitAnswerEvent):
            response = handler.handle_submit_answer(
                exchange_id=event.exchange_id,
                response_text=event.response_text,
                response_time_ms=event.response_time_ms,
            )

        elif isinstance(event, SubmitCodeEvent):
            response = handler.handle_submit_code(
                exchange_id=event.exchange_id,
                response_code=event.response_code,
                response_language=event.response_language,
                response_time_ms=event.response_time_ms,
            )

        # Commit DB changes (exchange creation, progress updates)
        db.commit()

        if response:
            await manager.send_event(submission_id, response)

    except BaseError as e:
        db.rollback()

        ws_logger.warning(
            f"Business error handling {event.event_type}: {e.message}",
            event_type=f"ws.event.error.{event.event_type}",
            metadata={"error_code": e.error_code},
        )

        error_event = ErrorEvent(
            error_code=e.error_code,
            message=e.message,
            details=e.metadata,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await manager.send_event(submission_id, error_event.model_dump())

        # Fatal errors close the connection
        if is_fatal_error(e):
            ws_logger.warning(
                f"Fatal error — closing connection: {e.error_code}",
                event_type="ws.connection.fatal_close",
            )
            try:
                await manager._active.get(submission_id, websocket).close(
                    code=1008, reason=e.message
                )
            except Exception:
                pass

    except Exception as e:
        db.rollback()

        ws_logger.error(
            f"Unexpected error handling {event.event_type}: {e}",
            event_type=f"ws.event.error.unexpected.{event.event_type}",
            exc_info=True,
        )

        error_event = ErrorEvent(
            error_code="SERVER_ERROR",
            message="Internal server error",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        await manager.send_event(submission_id, error_event.model_dump())

    finally:
        db.close()
