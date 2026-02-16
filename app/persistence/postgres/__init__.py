"""
PostgreSQL Persistence Layer

Pure infrastructure module for database connectivity.
Provides SQLAlchemy engine, session management, and health checks.

⚠️ CONTAINS ZERO BUSINESS LOGIC ⚠️

Public API:
- init_postgres(): Initialize engine and session factory
- get_db_session(): FastAPI dependency for sessions
- cleanup_postgres(): Graceful shutdown cleanup
- check_postgres_health(): Health check
- Base: SQLAlchemy declarative base for models
"""

from .base import Base, get_table_names
from .engine import (
    init_engine,
    get_engine,
    cleanup_engine,
    create_tables,
    drop_tables,
    get_pool_status,
)
from .session import (
    init_session_factory,
    get_db_session,
    get_db_session_with_commit,
    db_session_context,
    execute_with_retry,
)
from .health import (
    check_postgres_health,
    check_postgres_connectivity,
    log_pool_stats,
    get_health_check_endpoint_response,
    HealthStatus,
)

__all__ = [
    # Base model
    "Base",
    "get_table_names",
    
    # Engine management
    "init_engine",
    "get_engine",
    "cleanup_engine",
    "create_tables",
    "drop_tables",
    "get_pool_status",
    
    # Session management
    "init_session_factory",
    "get_db_session",
    "get_db_session_with_commit",
    "db_session_context",
    "execute_with_retry",
    
    # Health checks
    "check_postgres_health",
    "check_postgres_connectivity",
    "log_pool_stats",
    "get_health_check_endpoint_response",
    "HealthStatus",
    
    # Convenience initialization
    "init_postgres",
    "cleanup_postgres",
]


def init_postgres(config):
    """
    Initialize PostgreSQL infrastructure.
    
    Call this once during application startup.
    Sets up engine and session factory.
    
    Args:
        config: DatabaseSettings instance from app.config.settings
        
    Example:
        from app.persistence.postgres import init_postgres
        from app.config.settings import DatabaseSettings
        
        # At application startup
        db_settings = DatabaseSettings()
        init_postgres(db_settings)
    """
    init_engine(config)
    init_session_factory()


def cleanup_postgres():
    """
    Cleanup PostgreSQL resources.
    
    Disposes engine and closes all pooled connections.
    Called automatically on application shutdown via atexit.
    """
    cleanup_engine()
