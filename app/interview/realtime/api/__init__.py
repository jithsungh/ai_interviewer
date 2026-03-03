"""
Realtime API Layer

Exposes the WebSocket endpoint for live interview sessions.

Public API:
- router: FastAPI APIRouter with WebSocket endpoint
"""

from .routes import router

__all__ = ["router"]
