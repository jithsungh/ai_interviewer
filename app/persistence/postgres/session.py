"""
Database Session Management

Provides session factory and FastAPI dependency injection for database sessions.
Ensures proper session lifecycle and prevents connection leaks.
"""

import logging
from typing import Iterator
from contextlib import contextmanager

from sqlalchemy.orm import sessionmaker, Session

from .engine import get_engine

logger = logging.getLogger(__name__)

# Session factory (initialized after engine)
SessionLocal: sessionmaker = None


def init_session_factory():
    """
    Initialize the session factory.
    
    Must be called after engine initialization.
    Creates a configured sessionmaker bound to the engine.
    """
    global SessionLocal
    
    if SessionLocal is not None:
        logger.warning("Session factory already initialized")
        return
    
    engine = get_engine()
    
    SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,  # Explicit commit required
        autoflush=True,    # Auto-flush changes to DB before query
        expire_on_commit=True,  # Expire objects after commit
        class_=Session,
    )
    
    logger.info("Session factory initialized")


def get_session_factory() -> sessionmaker:
    """
    Get the initialized session factory.
    
    Returns:
        Configured sessionmaker instance
        
    Raises:
        RuntimeError: If session factory not initialized
    """
    if SessionLocal is None:
        raise RuntimeError(
            "Session factory not initialized. Call init_session_factory() first."
        )
    return SessionLocal


@contextmanager
def db_session_context():
    """
    Context manager for database sessions.
    
    Provides automatic session management with commit/rollback:
    - Commits on successful completion
    - Rolls back on exception
    - Always closes session
    
    Usage:
        with db_session_context() as session:
            user = session.query(User).first()
            session.add(new_user)
            # Automatically committed
    
    Yields:
        SQLAlchemy Session instance
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Session rolled back due to error: {e}")
        raise
    finally:
        session.close()


def get_db_session() -> Iterator[Session]:
    """
    FastAPI dependency for database sessions.
    
    Provides request-scoped database session with automatic cleanup.
    Session is closed after request completes, even if error occurs.
    
    Usage (FastAPI):
        @app.get("/users")
        def get_users(db: Session = Depends(get_db_session)):
            return db.query(User).all()
    
    Yields:
        SQLAlchemy Session instance
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_db_session_with_commit() -> Iterator[Session]:
    """
    FastAPI dependency for database sessions with auto-commit.
    
    Similar to get_db_session() but automatically commits on success
    and rolls back on exception.
    
    Usage (FastAPI):
        @app.post("/users")
        def create_user(
            user_data: UserCreate,
            db: Session = Depends(get_db_session_with_commit)
        ):
            user = User(**user_data.dict())
            db.add(user)
            # Automatically committed
            return user
    
    Yields:
        SQLAlchemy Session instance
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction rolled back due to error: {e}")
        raise
    finally:
        session.close()


def execute_with_retry(session: Session, operation, max_retries: int = 3):
    """
    Execute a database operation with retry logic.
    
    Retries on transient errors (deadlock, connection loss).
    Does NOT retry on integrity errors (indicates application bug).
    
    Args:
        session: SQLAlchemy Session
        operation: Callable that performs database operation
        max_retries: Maximum retry attempts
        
    Returns:
        Result of operation()
        
    Raises:
        Exception: If all retries fail or non-retryable error occurs
    """
    from sqlalchemy.exc import OperationalError, DBAPIError
    
    for attempt in range(1, max_retries + 1):
        try:
            result = operation()
            session.commit()
            return result
            
        except OperationalError as e:
            session.rollback()
            if attempt < max_retries:
                logger.warning(
                    f"Retrying operation (attempt {attempt}/{max_retries}): {e}"
                )
            else:
                logger.error(
                    f"Operation failed after {max_retries} attempts: {e}"
                )
                raise
                
        except Exception as e:
            # Non-retryable error (IntegrityError, etc.)
            session.rollback()
            logger.error(f"Non-retryable error: {e}")
            raise
