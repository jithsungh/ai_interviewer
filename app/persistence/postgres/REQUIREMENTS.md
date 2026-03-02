# PostgreSQL - SQLAlchemy Engine & Session Management

## 1. Purpose

The **PostgreSQL** layer provides:

- SQLAlchemy engine initialization with connection pooling
- Session factory for request-scoped sessions
- Transaction management (commit/rollback)
- Base model registration (ORM metadata)
- Database health checks

**Critical responsibility:** This is **pure database connectivity**. It must:

- Create and manage database connections
- Provide safe session lifecycle
- Handle connection failures gracefully
- **Contain ZERO business logic**

---

## 2. Responsibilities

### 2.1 Engine Initialization

**Must create SQLAlchemy engine with:**

- Connection pooling (pool_size, max_overflow)
- SSL/TLS configuration (required in production)
- Connection timeout settings
- Pool pre-ping (detect stale connections)
- Statement timeout (prevent runaway queries)

**Example configuration:**

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def create_db_engine(config: PostgresConfig):
    """
    Create SQLAlchemy engine with connection pooling.

    Configuration:
    - pool_size: Number of persistent connections (default: 20)
    - max_overflow: Additional connections when pool exhausted (default: 10)
    - pool_timeout: Max wait time for connection (default: 30s)
    - pool_recycle: Recycle connections after N seconds (default: 3600s)
    - pool_pre_ping: Test connection before checkout (default: True)
    """
    engine = create_engine(
        config.database_url,
        poolclass=QueuePool,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=config.pool_timeout,
        pool_recycle=config.pool_recycle,
        pool_pre_ping=True,  # Test connection health before use
        echo=config.echo,  # Log SQL statements (dev only)
        echo_pool=config.echo_pool,  # Log pool checkout/checkin (dev only)
        connect_args={
            "sslmode": config.ssl_mode,  # require, verify-ca, verify-full
            "connect_timeout": 10,
            "options": f"-c statement_timeout={config.query_timeout * 1000}"  # milliseconds
        }
    )

    return engine
```

---

### 2.2 Session Factory

**Must provide:**

```python
def get_db_session() -> Iterator[Session]:
    """
    Dependency injection for database sessions.

    Usage (FastAPI):
        @app.get("/interviews")
        def list_interviews(db: Session = Depends(get_db_session)):
            return db.query(Interview).all()

    Lifecycle:
    - Session created on request start
    - Session closed on request end (even if error)
    - Auto-rollback on exception
    - Auto-commit if no exception (optional, prefer explicit)
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

**Session configuration:**

```python
from sqlalchemy.orm import sessionmaker

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,  # Explicit commit required
    autoflush=True,    # Auto-flush changes to DB (not committed)
    expire_on_commit=True  # Expire objects after commit
)
```

---

### 2.3 Transaction Management

**Must support explicit transactions:**

**Pattern 1: Context manager**

```python
def transfer_funds(db: Session, from_account: int, to_account: int, amount: float):
    """
    Explicit transaction with rollback on error.
    """
    try:
        # Debit
        account_from = db.query(Account).filter(Account.id == from_account).first()
        account_from.balance -= amount

        # Credit
        account_to = db.query(Account).filter(Account.id == to_account).first()
        account_to.balance += amount

        # Commit
        db.commit()
    except Exception as e:
        db.rollback()
        raise
```

**Pattern 2: Savepoints (nested transactions)**

```python
def update_with_savepoint(db: Session):
    """
    Use savepoint for partial rollback.
    """
    db.add(Object1())
    db.flush()

    savepoint = db.begin_nested()  # Create savepoint
    try:
        db.add(Object2())
        db.flush()
    except IntegrityError:
        savepoint.rollback()  # Rollback to savepoint, keep Object1

    db.commit()  # Commit Object1
```

---

### 2.4 Base Model Registration

**Must centralize SQLAlchemy Base:**

```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models to register with Base.metadata
from app.interview.models import InterviewSubmission, InterviewExchange
from app.evaluation.models import Evaluation, EvaluationDimensionScore
from app.auth.models import User, Role
from app.coding.models import CodeSubmission, TestCase
from app.audio.models import AudioRecording
# ... etc

def create_tables():
    """
    Create all tables defined in models.

    Call during application initialization.
    """
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """
    Drop all tables.

    ⚠️ DANGER: Only use in dev/test environments.
    """
    Base.metadata.drop_all(bind=engine)
```

**Rationale:**

- Avoid circular imports (models import Base from persistence)
- Centralize metadata (Base.metadata) for migrations
- Enable create_all/drop_all for testing

---

### 2.5 Health Checks

**Must implement database connectivity check:**

```python
from sqlalchemy import text
from typing import Dict, Any
import time

def check_postgres_health() -> Dict[str, Any]:
    """
    Check PostgreSQL connectivity and pool status.

    Returns:
        {
            "status": "healthy" | "unhealthy",
            "latency_ms": float,
            "pool": {
                "size": int,
                "checked_out": int,
                "overflow": int,
                "available": int
            },
            "error": str | None
        }
    """
    try:
        start = time.perf_counter()

        # Test query
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()

        latency_ms = (time.perf_counter() - start) * 1000

        # Pool metrics
        pool = engine.pool

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "pool": {
                "size": pool.size(),
                "checked_out": pool.checkedout(),
                "overflow": pool.overflow(),
                "available": pool.size() - pool.checkedout()
            },
            "error": None
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "latency_ms": None,
            "pool": None,
            "error": str(e)
        }
```

---

## 3. Connection Retry Logic

**Must implement retry on connection failure:**

```python
import time
from sqlalchemy.exc import OperationalError

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds

def create_engine_with_retry(config: PostgresConfig):
    """
    Create engine with connection retry logic.

    Retries on OperationalError (connection refused, timeout).
    Uses exponential backoff: 2s, 4s, 8s.
    """
    for attempt in range(MAX_RETRIES):
        try:
            engine = create_db_engine(config)

            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info("Database connection established")
            return engine

        except OperationalError as e:
            if attempt == MAX_RETRIES - 1:
                logger.critical(f"Failed to connect to database after {MAX_RETRIES} attempts")
                raise ConnectionError(f"Database unavailable: {e}") from e

            sleep_time = RETRY_BACKOFF_BASE ** attempt
            logger.warning(f"Database connection failed (attempt {attempt + 1}/{MAX_RETRIES}), retrying in {sleep_time}s...")
            time.sleep(sleep_time)
```

---

## 4. Graceful Shutdown

**Must cleanup resources on shutdown:**

```python
import atexit
import signal

def cleanup_postgres():
    """
    Close all sessions and dispose engine.

    Called on application shutdown.
    """
    logger.info("Cleaning up PostgreSQL connections...")

    # Close all sessions
    SessionLocal.close_all()

    # Dispose engine (close all pool connections)
    engine.dispose()

    logger.info("PostgreSQL cleanup complete")

# Register cleanup handlers
atexit.register(cleanup_postgres)
signal.signal(signal.SIGTERM, lambda sig, frame: cleanup_postgres())
signal.signal(signal.SIGINT, lambda sig, frame: cleanup_postgres())
```

---

## 5. Session Leak Prevention

### 5.1 Context Manager Pattern (Recommended)

```python
from contextlib import contextmanager

@contextmanager
def db_session_context():
    """
    Context manager for database sessions.

    Usage:
        with db_session_context() as session:
            session.query(Model).all()

    Guarantees:
    - Session closed on exit
    - Rollback on exception
    - No session leaks
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

---

### 5.2 Dependency Injection (FastAPI)

```python
from fastapi import Depends

def get_db():
    """
    FastAPI dependency for database sessions.

    Automatically:
    - Creates session on request start
    - Closes session on request end
    - Handles exceptions gracefully
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/interviews")
def list_interviews(db: Session = Depends(get_db)):
    return db.query(Interview).all()
```

---

### 5.3 Leak Detection (Testing)

```python
def test_session_leak():
    """
    Test for session leaks.

    Checks that all sessions are returned to pool after use.
    """
    initial_checked_out = engine.pool.checkedout()

    # Perform operations
    with db_session_context() as session:
        session.query(Interview).all()

    final_checked_out = engine.pool.checkedout()

    # Assert no session leak
    assert final_checked_out == initial_checked_out, "Session leak detected"
```

---

## 6. Query Timeout Enforcement

**Must prevent runaway queries:**

```python
# Method 1: Connection-level timeout (recommended)
connect_args = {
    "options": "-c statement_timeout=30000"  # 30 seconds in milliseconds
}

# Method 2: Per-query timeout
from sqlalchemy import text

def query_with_timeout(session, query_str, timeout_seconds=30):
    """
    Execute query with explicit timeout.
    """
    session.execute(text(f"SET statement_timeout = {timeout_seconds * 1000}"))
    result = session.execute(text(query_str))
    session.execute(text("RESET statement_timeout"))
    return result
```

---

## 7. SSL/TLS Configuration

**Must enforce SSL in production:**

```python
# Development (no SSL)
DATABASE_URL = "postgresql://user:pass@localhost/db"
SSL_MODE = "disable"

# Production (require SSL)
DATABASE_URL = "postgresql://user:pass@prod.example.com/db"
SSL_MODE = "require"  # or "verify-ca", "verify-full"

connect_args = {
    "sslmode": SSL_MODE,
    "sslrootcert": "/path/to/ca-cert.pem",  # If verify-ca or verify-full
}
```

---

## 8. Error Handling

### 8.1 Exception Types

**Must handle:**

1. **OperationalError** - Connection failures, timeouts
   - Retry with backoff
   - Log error with context
   - Raise ConnectionError to caller

2. **IntegrityError** - Constraint violations (unique, foreign key)
   - Do NOT retry (indicates application bug)
   - Rollback transaction
   - Raise to caller with sanitized message

3. **DataError** - Invalid data types, out of range
   - Do NOT retry
   - Raise to caller with validation message

4. **ProgrammingError** - SQL syntax errors
   - Do NOT retry (indicates code bug)
   - Log full error (for debugging)
   - Raise to caller

---

### 8.2 Error Handling Example

```python
from sqlalchemy.exc import (
    OperationalError,
    IntegrityError,
    DataError,
    ProgrammingError
)

def execute_with_error_handling(session, query):
    """
    Execute query with comprehensive error handling.
    """
    try:
        result = session.execute(query)
        session.commit()
        return result

    except IntegrityError as e:
        session.rollback()
        logger.error(f"Integrity constraint violated: {e}")
        # Parse error for user-friendly message
        if "unique constraint" in str(e).lower():
            raise ValueError("Duplicate record") from e
        elif "foreign key constraint" in str(e).lower():
            raise ValueError("Referenced record does not exist") from e
        else:
            raise ValueError("Data integrity error") from e

    except OperationalError as e:
        session.rollback()
        logger.error(f"Database operation failed: {e}")
        raise ConnectionError("Database unavailable") from e

    except DataError as e:
        session.rollback()
        logger.error(f"Data validation failed: {e}")
        raise ValueError("Invalid data") from e

    except ProgrammingError as e:
        session.rollback()
        logger.critical(f"SQL programming error: {e}")
        raise RuntimeError("Query execution error") from e

    except Exception as e:
        session.rollback()
        logger.error(f"Unexpected database error: {e}")
        raise
```

---

## 9. Connection Pool Tuning

### 9.1 Pool Size Calculation

**Formula:**

```
pool_size = (number of application instances) × (threads per instance) × (concurrent DB operations per thread)
```

**Example:**

- 4 application instances
- 10 worker threads per instance
- 2 concurrent DB operations per thread (typical)
- pool_size = 4 × 10 × 2 = 80 connections

**Recommendations:**

- Start with `pool_size=20`, `max_overflow=10`
- Monitor pool exhaustion (checked_out == pool_size + max_overflow)
- Increase if exhaustion > 1% of requests
- Decrease if utilization < 20%

---

### 9.2 Pool Monitoring

```python
def log_pool_stats():
    """
    Log connection pool statistics.

    Call periodically (every 60 seconds).
    """
    pool = engine.pool

    logger.info(
        f"DB Pool Stats: "
        f"size={pool.size()}, "
        f"checked_out={pool.checkedout()}, "
        f"overflow={pool.overflow()}, "
        f"available={pool.size() - pool.checkedout()}"
    )

    # Alert if pool exhausted
    if pool.checkedout() >= pool.size() + pool.overflow():
        logger.warning("Database connection pool exhausted!")
```

---

## 10. Testing Requirements

### 10.1 Unit Tests

1. **Engine creation:** Valid config → engine created
2. **Engine creation failure:** Invalid URL → raises error
3. **Session lifecycle:** Session created → used → closed
4. **Transaction commit:** Changes persisted to DB
5. **Transaction rollback:** Changes not persisted
6. **Connection retry:** Retry on OperationalError
7. **Health check:** Returns status and metrics

---

### 10.2 Integration Tests

1. **Concurrent sessions:** 100 concurrent sessions → no pool exhaustion
2. **Session leak detection:** Session not closed → detected
3. **Query timeout:** Long query → timeout after 30s
4. **Integrity error handling:** Duplicate insert → IntegrityError raised
5. **Connection loss:** Database restarted → reconnects successfully

---

## 11. Configuration

```python
from pydantic import BaseModel, Field, field_validator

class PostgresConfig(BaseModel):
    """PostgreSQL connection configuration."""

    # Connection
    database_url: str = Field(..., description="PostgreSQL connection string")

    # Pool
    pool_size: int = Field(20, ge=1, le=100, description="Connection pool size")
    max_overflow: int = Field(10, ge=0, le=50, description="Max overflow connections")
    pool_timeout: int = Field(30, ge=1, le=300, description="Pool checkout timeout (seconds)")
    pool_recycle: int = Field(3600, ge=300, le=7200, description="Recycle connections (seconds)")

    # Query
    query_timeout: int = Field(30, ge=1, le=300, description="Query timeout (seconds)")

    # Features
    echo: bool = Field(False, description="Log SQL statements")
    echo_pool: bool = Field(False, description="Log pool events")

    # SSL
    ssl_mode: str = Field("require", description="SSL mode")

    @field_validator("ssl_mode")
    def validate_ssl_mode(cls, v):
        allowed = ["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]
        if v not in allowed:
            raise ValueError(f"ssl_mode must be one of: {allowed}")
        return v
```

---

## 12. Critical Risks

1. **Session not closed:** Connection pool exhaustion, memory leak
2. **No query timeout:** Runaway queries block worker threads
3. **No SSL in production:** Man-in-the-middle attacks, credential theft
4. **Auto-commit enabled:** Partial transactions committed, data inconsistency
5. **Pool too small:** High latency, request timeouts
6. **Pool too large:** Database overload, connection limit exceeded

---

## 13. Observability

### 13.1 Metrics

**Must expose:**

- `db_pool_size` (gauge) - Connection pool size
- `db_pool_checked_out` (gauge) - Currently checked-out connections
- `db_pool_overflow` (gauge) - Overflow connections in use
- `db_query_count` (counter) - Total queries executed
- `db_query_duration_seconds` (histogram) - Query latency distribution

---

### 13.2 Logging

**Must log:**

- Connection established (INFO)
- Connection retry (WARNING with attempt count)
- Connection failure (ERROR after all retries)
- Query timeout (WARNING with query details)
- Pool exhaustion (CRITICAL with stats)
- IntegrityError (ERROR with sanitized message)

**Must NOT log:**

- User passwords or tokens
- Full SQL with sensitive data (log parameterized queries only)

---

## 14. Acceptance Criteria

**PostgreSQL module is complete when:**

✅ Engine created with connection pooling
✅ Session factory provides request-scoped sessions
✅ Context manager prevents session leaks
✅ Transaction commit/rollback working
✅ Connection retry with exponential backoff
✅ Health check returns status and metrics
✅ Graceful shutdown cleanup implemented
✅ Query timeout enforced (30s default)
✅ SSL required in production environment
✅ Error handling for all exception types
✅ Pool monitoring metrics exposed
✅ No business logic in module
✅ All tests passing

---

**End of PostgreSQL Requirements**
