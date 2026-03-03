"""
Interview Realtime Module

WebSocket protocol handlers and event contracts for live interview sessions.

Responsibilities:
- WebSocket connection lifecycle (connect, active, disconnect, reconnect)
- Bidirectional event protocol (client ↔ server)
- JWT authentication for WebSocket connections
- Single active connection per submission (Redis-backed)
- Connection replacement (multi-tab detection)
- Heartbeat mechanism (60s TTL, 30s refresh interval)
- Event validation and structured error responses

Public API:
- router: FastAPI APIRouter with /ws/interview/{submission_id} endpoint
- ConnectionManager: In-process + Redis connection tracking
- RealtimeEventHandler: Event processing business logic
- Contracts: All event Pydantic models (client→server, server→client)

Dependencies:
- app.interview.session: Submission state and repository
- app.interview.orchestration: Question sequencing, exchange creation
- app.interview.exchanges: Exchange repository (via orchestration)
- app.shared.auth_context: JWT validation, WebSocket authentication
- app.shared.errors: Error types and serialization
- app.shared.observability: Structured logging
- app.persistence.redis: Connection state tracking
- app.persistence.postgres: Database session management
"""

from .api import router
from .domain import ConnectionManager, RealtimeEventHandler

__all__ = [
    "router",
    "ConnectionManager",
    "RealtimeEventHandler",
]
