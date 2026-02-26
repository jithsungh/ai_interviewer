"""
Database Engine Creation

Handles SQLAlchemy engine initialization with connection pooling,
retry logic, and graceful error handling.
"""

import time
import logging
import atexit
import signal
from typing import Optional

from sqlalchemy import create_engine, Engine, event, text
from sqlalchemy.exc import OperationalError, DatabaseError
from sqlalchemy.pool import QueuePool

from app.config.settings import DatabaseSettings
from .base import Base, import_all_models

logger = logging.getLogger(__name__)

# Infrastructure constants
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

# Global engine instance (initialized once)
_engine: Optional[Engine] = None


def create_db_engine(config: DatabaseSettings) -> Engine:
    """
    Create SQLAlchemy engine with connection pooling and retry logic.
    
    Configuration:
    - Connection pooling (pool_size, max_overflow)
    - Pool pre-ping (detect stale connections)
    - Query timeout (prevent runaway queries)
    - Exponential backoff retry on connection failure
    
    Args:
        config: DatabaseSettings instance from app.config.settings
        
    Returns:
        SQLAlchemy Engine instance
        
    Raises:
        OperationalError: If all connection retries fail
    """
    logger.info("Initializing PostgreSQL engine...")
    
    # Attempt connection with retry logic
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Creating database engine (attempt {attempt}/{MAX_RETRIES})"
            )
            
            # Build connect_args with query timeout
            # For asyncpg, use server_settings instead of options
            if "asyncpg" in config.database_url:
                connect_args = {
                    "server_settings": {
                        "statement_timeout": str(config.db_query_timeout * 1000),  # Convert to ms
                    }
                }
            else:
                # For psycopg2/psycopg3, use options
                connect_args = {
                    "options": f"-c statement_timeout={config.db_query_timeout * 1000}",
                }
            
            engine = create_engine(
                config.database_url,
                # Connection pooling
                poolclass=QueuePool,
                pool_size=config.db_pool_size,
                max_overflow=config.db_max_overflow,
                pool_timeout=config.db_pool_timeout,
                pool_recycle=config.db_pool_recycle,
                pool_pre_ping=config.db_pool_pre_ping,
                # Logging
                echo=config.db_echo,
                # Connection args (timeouts)
                connect_args=connect_args,
                # Performance
                future=True,  # Use SQLAlchemy 2.0 style
            )
            
            # Test connection
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            
            logger.info(
                f"Database engine created successfully "
                f"(pool_size={config.db_pool_size}, max_overflow={config.db_max_overflow})"
            )
            
            # Register pool event listeners for monitoring
            _register_pool_listeners(engine)
            
            return engine
            
        except (OperationalError, DatabaseError) as e:
            if attempt < MAX_RETRIES:
                backoff_seconds = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"Database connection failed (attempt {attempt}/{MAX_RETRIES}): {e}. "
                    f"Retrying in {backoff_seconds}s..."
                )
                time.sleep(backoff_seconds)
            else:
                logger.error(
                    f"Database connection failed after {MAX_RETRIES} attempts: {e}"
                )
                raise OperationalError(
                    "Database unavailable after all retry attempts",
                    params=None,
                    orig=e
                )


def _register_pool_listeners(engine: Engine):
    """
    Register SQLAlchemy pool event listeners for monitoring.
    
    Logs pool checkout, checkin, and connection events for observability.
    
    Args:
        engine: SQLAlchemy Engine instance
    """
    
    @event.listens_for(engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        """Log when new connection is created."""
        logger.debug("Database connection established")
    
    @event.listens_for(engine, "checkout")
    def receive_checkout(dbapi_conn, connection_record, connection_proxy):
        """Log when connection is checked out from pool."""
        pool = engine.pool
        logger.debug(
            f"Connection checked out from pool "
            f"(checked_out={pool.checkedout()}, size={pool.size()})"
        )
    
    @event.listens_for(engine, "checkin")
    def receive_checkin(dbapi_conn, connection_record):
        """Log when connection is returned to pool."""
        logger.debug("Connection returned to pool")


def init_engine(config: DatabaseSettings) -> Engine:
    """
    Initialize the global database engine.
    
    This function should be called once during application startup.
    Subsequent calls return the existing engine instance.
    
    Args:
        config: DatabaseSettings instance from app.config.settings
        
    Returns:
        Initialized Engine instance
    """
    global _engine
    
    if _engine is not None:
        logger.warning("Engine already initialized, returning existing instance")
        return _engine
    
    # Import all models to register with Base.metadata
    import_all_models()
    
    # Create engine
    _engine = create_db_engine(config)
    
    # Register cleanup handlers
    atexit.register(cleanup_engine)
    signal.signal(signal.SIGTERM, lambda sig, frame: cleanup_engine())
    signal.signal(signal.SIGINT, lambda sig, frame: cleanup_engine())
    
    return _engine


def get_engine() -> Engine:
    """
    Get the initialized database engine.
    
    Returns:
        Global Engine instance
        
    Raises:
        RuntimeError: If engine not yet initialized
    """
    if _engine is None:
        raise RuntimeError(
            "Database engine not initialized. Call init_engine() first."
        )
    return _engine


def cleanup_engine():
    """
    Cleanup database connections on application shutdown.
    
    Disposes the engine, closing all pooled connections.
    This function is registered with atexit and signal handlers.
    """
    global _engine
    
    if _engine is None:
        return
    
    logger.info("Cleaning up PostgreSQL connections...")
    
    try:
        # Dispose engine (close all pooled connections)
        _engine.dispose()
        logger.info("PostgreSQL cleanup complete")
    except Exception as e:
        logger.error(f"Error during PostgreSQL cleanup: {e}")
    finally:
        _engine = None


def create_tables():
    """
    Create all tables defined in models.
    
    ⚠️ WARNING: Only use this in development/testing.
    In production, use Alembic migrations instead.
    
    Raises:
        RuntimeError: If engine not initialized
    """
    engine = get_engine()
    
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    logger.info(f"Created {len(Base.metadata.tables)} tables")


def drop_tables():
    """
    Drop all tables defined in models.
    
    ⚠️ DANGER: This permanently deletes all data.
    Only use in dev/test environments.
    
    Raises:
        RuntimeError: If engine not initialized
    """
    engine = get_engine()
    
    logger.warning("Dropping all database tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("All tables dropped")


def get_pool_status() -> dict:
    """
    Get current connection pool status for monitoring.
    
    Returns:
        Dictionary containing:
        - pool_size: Total pool size
        - checked_out: Currently checked out connections
        - overflow: Overflow connections in use
        - total_connections: pool_size + overflow
        
    Raises:
        RuntimeError: If engine not initialized
    """
    engine = get_engine()
    pool = engine.pool
    
    return {
        "pool_size": pool.size(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "total_connections": pool.size() + pool.overflow(),
    }
