"""
Interview API — Parent REST Endpoints

Provides the top-level interview REST API endpoints:
- GET  /{submission_id}/exchanges  — list exchanges (audit trail)
- GET  /{submission_id}/progress   — section-level progress breakdown

State-transition endpoints are handled by the session sub-module:
- POST /sessions/start             → app.interview.session.api.routes
- POST /sessions/complete          → app.interview.session.api.routes
- POST /sessions/cancel            → app.interview.session.api.routes
- POST /sessions/review            → app.interview.session.api.routes

WebSocket is handled by the realtime sub-module:
- WS  /ws/interview/{submission_id} → app.interview.realtime.api.routes

Public API:
- router: APIRouter for registration in router_registry
- Contracts: ExchangeListResponse, SectionProgressResponse, etc.
"""

from app.interview.api.routes import router

__all__ = ["router"]
