"""
Admin API Layer

RESTful HTTP endpoints for administrative CRUD operations.

Handles:
- HTTP request/response serialization
- Input validation (format, types) via Pydantic contracts
- Authentication/authorization enforcement (superadmin, admin, read_only)
- Error handling and structured response formatting
- Delegation to domain services (zero business logic here)

Public API:
- router: FastAPI APIRouter with all admin endpoints

Dependencies:
- app.admin.domain — Business logic services
- app.admin.persistence — Repository implementations
- app.shared.auth_context — Identity context, auth dependencies
- app.shared.errors — Structured error types
- app.shared.observability — Logging
"""

from .routes import router

__all__ = ["router"]
