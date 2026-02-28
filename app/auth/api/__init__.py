"""
Auth API Layer

Exposes HTTP endpoints for authentication and identity management:
- Registration (admin, candidate)
- Login / Logout
- Token refresh
- Current user profile

All business logic delegated to domain layer (app.auth.domain).
"""

from .routes import router

__all__ = ["router"]
