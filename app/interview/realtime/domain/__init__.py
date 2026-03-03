"""
Realtime Domain Layer

Provides WebSocket connection management and event handling business logic.

Public API:
- ConnectionManager: In-process WebSocket tracking + Redis cross-process state
- RealtimeEventHandler: Business logic for handling WebSocket events
"""

from .connection_manager import ConnectionManager
from .event_handler import RealtimeEventHandler

__all__ = [
    "ConnectionManager",
    "RealtimeEventHandler",
]
