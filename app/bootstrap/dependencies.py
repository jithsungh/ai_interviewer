"""
Dependency Injection Helpers

Re-exports commonly used dependencies for convenient imports.

Instead of:
    from app.persistence.postgres import get_db_session
    from app.shared.auth_context.dependencies import get_identity, require_admin

You can use:
    from app.bootstrap.dependencies import get_db_session, get_identity, require_admin

This is purely for developer convenience and doesn't add new functionality.
"""

# ==========================================
# Database Dependencies
# ==========================================

from app.persistence.postgres import (
    get_db_session,
    get_db_session_with_commit,
)


# ==========================================
# Authentication Dependencies
# ==========================================

from app.shared.auth_context.dependencies import (
    get_identity,
    get_optional_identity,
    require_admin,
    require_candidate,
    require_superadmin,
)


# ==========================================
# Public API
# ==========================================

__all__ = [
    # Database
    "get_db_session",
    "get_db_session_with_commit",
    
    # Authentication
    "get_identity",
    "get_optional_identity",
    "require_admin",
    "require_candidate",
    "require_superadmin",
]
