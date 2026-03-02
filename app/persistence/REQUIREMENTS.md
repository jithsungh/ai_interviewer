# Persistence Module - Infrastructure-Only Database & Cache Connectors

## 1. Purpose

The **Persistence** module provides:

- PostgreSQL connection and session management (SQLAlchemy)
- Redis client and session utilities (caching, locks, TTL)
- Qdrant vector database integration (embeddings storage/retrieval)

**Critical responsibility:** This is the **infrastructure backbone**. It must:

- Initialize and expose infrastructure clients
- Provide safe session lifecycle management
- Centralize connection configuration
- Support connection health validation
- **Remain business-logic free**

**Architectural philosophy:**

> **Persistence is DUMB PLUMBING. It connects. It does not decide.**
> **If this layer becomes "smart," your modular boundaries collapse.**

---

## 2. What This Module IS

**Infrastructure-only:**

- PostgreSQL engine & session factory
- Redis connection pool & client wrapper
- Qdrant client initialization & vector operations
- Connection health checks
- Graceful shutdown cleanup

**Pure primitives:**

- `get_db_session()` - database session
- `get_redis_client()` - Redis connection
- `store_embedding()` - vector storage
- `search_vectors()` - vector retrieval
- Connection retry logic
- Transaction management (commit/rollback only)

---

## 3. What This Module IS NOT

**FORBIDDEN - This module must NEVER contain:**

❌ **Domain rules** (state transitions, validation, business constraints)
❌ **Repository logic** (domain-specific queries belong in domain modules)
❌ **Multi-tenant filtering** (belongs in repositories, not infrastructure)
❌ **RBAC enforcement** (belongs in auth module)
❌ **Scoring logic** (belongs in evaluation module)
❌ **Template resolution** (belongs in interview module)
❌ **AI model calls** (belongs in AI module)
❌ **Cross-module decisions** (orchestration belongs elsewhere)

**Examples of violations:**

```python
# ❌ FORBIDDEN - Domain logic in persistence
def get_db_session():
    session = SessionLocal()
    if not user.has_permission():  # ❌ RBAC in infrastructure
        raise PermissionError()
    return session

# ❌ FORBIDDEN - Business rules in persistence
def store_embedding(vector):
    if difficulty == "hard":  # ❌ Domain decision
        collection = "hard_questions"
    else:
        collection = "easy_questions"
    qdrant.store(collection, vector)

# ✅ CORRECT - Pure infrastructure
def get_db_session():
    session = SessionLocal()
    return session

# ✅ CORRECT - Pure storage
def store_embedding(collection_name, vector, metadata):
    qdrant.store(collection_name, vector, metadata)
```

---

## 4. Module Structure

```
persistence/
├── REQUIREMENTS.md           # This file (module overview)
├── postgres/
│   └── REQUIREMENTS.md       # SQLAlchemy engine, session factory, base models
├── redis/
│   └── REQUIREMENTS.md       # Redis client wrapper, locks, TTL utilities
└── qdrant/
    └── REQUIREMENTS.md       # Qdrant client, embedding storage/retrieval
```

---

## 5. Dependency Rules

### Import Direction (STRICT)

**Persistence imports FROM:**

- Standard library
- Third-party libraries (SQLAlchemy, redis-py, qdrant-client)
- Config module (connection strings, pool sizes)

**Persistence MUST NOT import FROM:**

- ❌ `interview` module
- ❌ `evaluation` module
- ❌ `auth` module
- ❌ `admin` module
- ❌ `coding` module
- ❌ `audio` module
- ❌ ANY domain module

**Higher modules import persistence:**

```python
# ✅ CORRECT - Domain imports infrastructure
from app.persistence.postgres import get_db_session
from app.persistence.redis import get_redis_client

# ❌ FORBIDDEN - Infrastructure imports domain
from app.interview.repositories import SubmissionRepository  # NEVER
```

---

## 6. Core Responsibilities

### 6.1 PostgreSQL (SQLAlchemy)

**Provides:**

- Engine initialization with connection pooling
- Session factory (`get_db_session()`)
- Transaction management (commit/rollback)
- Base model registration (if using ORM)
- Health checks (SELECT 1 test)

**See:** [postgres/REQUIREMENTS.md](postgres/REQUIREMENTS.md)

---

### 6.2 Redis

**Provides:**

- Connection pool initialization
- Client wrapper (`get_redis_client()`)
- Key namespacing patterns (interview:session:{id}, rate_limit:{user_id})
- TTL management (set with expiration, reset TTL)
- Distributed locks (acquire_lock, release_lock)
- Atomic operations (INCR, GETSET, Lua scripts)

**See:** [redis/REQUIREMENTS.md](redis/REQUIREMENTS.md)

---

### 6.3 Qdrant (Vector Database)

**Provides:**

- Client initialization (collection name, vector dimensions)
- Collection management (create if not exists, validate schema)
- Embedding storage (store vector + metadata)
- Similarity search (query vector, filters, top_k)
- No AI logic (AI module generates embeddings, persistence stores them)

**See:** [qdrant/REQUIREMENTS.md](qdrant/REQUIREMENTS.md)

---

## 7. Infrastructure Safety Requirements

### 7.1 Connection Retry Strategy

**Must implement:**

- Exponential backoff on connection failure (1s, 2s, 4s, 8s, max 30s)
- Max retry attempts (default: 3)
- Fail fast if all retries exhausted
- Log connection failures (include timestamp, service, error)

**Example: PostgreSQL retry**

```python
def create_engine_with_retry():
    for attempt in range(MAX_RETRIES):
        try:
            engine = create_engine(DATABASE_URL, **engine_config)
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return engine
        except OperationalError as e:
            if attempt == MAX_RETRIES - 1:
                raise ConnectionError(f"Failed to connect after {MAX_RETRIES} attempts: {e}")
            sleep_time = 2 ** attempt
            logger.warning(f"DB connection failed, retrying in {sleep_time}s... ({attempt+1}/{MAX_RETRIES})")
            time.sleep(sleep_time)
```

---

### 7.2 Timeout Configuration

**Must configure timeouts for:**

- PostgreSQL query timeout (default: 30s)
- Redis command timeout (default: 5s)
- Qdrant search timeout (default: 10s)
- Connection timeout (default: 10s)

**Rationale:** Prevent resource exhaustion from hanging connections.

---

### 7.3 Connection Pool Monitoring

**Must expose metrics:**

- Pool size (current active connections)
- Pool overflow (connections beyond pool_size)
- Checked-out connections
- Connection checkout time (avg, p95)

**Use for:**

- Detecting connection leaks (checked-out never returned)
- Sizing pool correctly (overflow indicates undersized pool)

---

### 7.4 Graceful Shutdown Cleanup

**On application shutdown, must:**

1. Close all active sessions
2. Dispose database engine
3. Close Redis connection pool
4. Close Qdrant client
5. Wait for in-flight operations (max 5 seconds)
6. Log cleanup completion

**Example:**

```python
import atexit

def cleanup_persistence():
    logger.info("Shutting down persistence layer...")
    # Close all database sessions
    SessionLocal.close_all()
    # Dispose engine
    engine.dispose()
    # Close Redis pool
    redis_pool.disconnect()
    # Close Qdrant client
    qdrant_client.close()
    logger.info("Persistence layer shutdown complete")

atexit.register(cleanup_persistence)
```

---

### 7.5 Prevent Connection Leakage

**Common leak scenarios:**

**Scenario 1: Session not closed**

```python
# ❌ LEAK - Session never closed
def get_data():
    session = get_db_session()
    return session.query(Model).all()
    # Session leaked!

# ✅ CORRECT - Context manager
def get_data():
    with get_db_session() as session:
        return session.query(Model).all()
```

**Scenario 2: Exception during transaction**

```python
# ❌ LEAK - Session not closed on error
def update_data():
    session = get_db_session()
    session.add(obj)
    session.commit()  # Raises error, session never closed

# ✅ CORRECT - Try/finally or context manager
def update_data():
    session = get_db_session()
    try:
        session.add(obj)
        session.commit()
    finally:
        session.close()
```

**Prevention:**

- Use context managers (`with` statement)
- Dependency injection framework auto-cleanup (FastAPI Depends)
- Monitor checked-out connection count

---

### 7.6 Handle Database Failover (Future)

**Design for:**

- Primary/replica topology (read from replica, write to primary)
- Automatic failover (reconnect to new primary on failure)
- Connection pool refresh (discard stale connections)

**Not required for V1, but design must not preclude it.**

---

## 8. Configuration

### 8.1 PostgreSQL Configuration

```python
class PostgresConfig(BaseModel):
    """PostgreSQL connection configuration."""

    # Connection
    database_url: str = Field(..., description="PostgreSQL connection string")

    # Pool settings
    pool_size: int = Field(20, description="Connection pool size")
    max_overflow: int = Field(10, description="Max connections beyond pool_size")
    pool_timeout: int = Field(30, description="Max seconds to wait for connection")
    pool_recycle: int = Field(3600, description="Recycle connections after N seconds")

    # Query settings
    query_timeout: int = Field(30, description="Max query execution time (seconds)")

    # Features
    echo: bool = Field(False, description="Log all SQL statements")
    echo_pool: bool = Field(False, description="Log pool checkout/checkin")

    # SSL (production)
    ssl_mode: str = Field("require", description="SSL mode: disable, allow, prefer, require")

    # Health check
    health_check_interval: int = Field(60, description="Health check interval (seconds)")
```

---

### 8.2 Redis Configuration

```python
class RedisConfig(BaseModel):
    """Redis connection configuration."""

    # Connection
    redis_url: str = Field(..., description="Redis connection string")

    # Pool settings
    max_connections: int = Field(50, description="Max connections in pool")
    connection_timeout: int = Field(10, description="Connection timeout (seconds)")
    socket_timeout: int = Field(5, description="Socket read/write timeout (seconds)")

    # Retry
    retry_on_timeout: bool = Field(True, description="Retry commands on timeout")
    max_retries: int = Field(3, description="Max command retries")

    # Features
    decode_responses: bool = Field(True, description="Decode bytes to strings")

    # Health check
    health_check_interval: int = Field(60, description="Health check interval (seconds)")
```

---

### 8.3 Qdrant Configuration

```python
class QdrantConfig(BaseModel):
    """Qdrant vector database configuration."""

    # Connection
    qdrant_url: str = Field(..., description="Qdrant server URL")
    qdrant_api_key: Optional[str] = Field(None, description="API key for cloud Qdrant")

    # Collections
    collection_name: str = Field("embeddings", description="Default collection name")
    vector_dimension: int = Field(1536, description="Embedding vector dimension")

    # Search
    search_timeout: int = Field(10, description="Search timeout (seconds)")
    default_top_k: int = Field(10, description="Default top_k for searches")

    # Features
    prefer_grpc: bool = Field(True, description="Use gRPC instead of REST")

    # Health check
    health_check_interval: int = Field(60, description="Health check interval (seconds)")
```

---

## 9. Health Checks

### 9.1 PostgreSQL Health Check

```python
def check_postgres_health() -> HealthStatus:
    """
    Check PostgreSQL connectivity.

    Returns:
        HealthStatus with status (healthy/unhealthy) and latency
    """
    try:
        start = time.perf_counter()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start) * 1000

        return HealthStatus(
            service="postgres",
            status="healthy",
            latency_ms=latency_ms,
            details={"pool_size": engine.pool.size()}
        )
    except Exception as e:
        return HealthStatus(
            service="postgres",
            status="unhealthy",
            error=str(e)
        )
```

---

### 9.2 Redis Health Check

```python
def check_redis_health() -> HealthStatus:
    """
    Check Redis connectivity.

    Returns:
        HealthStatus with status and latency
    """
    try:
        start = time.perf_counter()
        redis_client.ping()
        latency_ms = (time.perf_counter() - start) * 1000

        return HealthStatus(
            service="redis",
            status="healthy",
            latency_ms=latency_ms,
            details={"connected_clients": redis_client.info().get("connected_clients")}
        )
    except Exception as e:
        return HealthStatus(
            service="redis",
            status="unhealthy",
            error=str(e)
        )
```

---

### 9.3 Qdrant Health Check

```python
def check_qdrant_health() -> HealthStatus:
    """
    Check Qdrant connectivity.

    Returns:
        HealthStatus with status and collection info
    """
    try:
        start = time.perf_counter()
        collections = qdrant_client.get_collections()
        latency_ms = (time.perf_counter() - start) * 1000

        return HealthStatus(
            service="qdrant",
            status="healthy",
            latency_ms=latency_ms,
            details={"collections": [c.name for c in collections.collections]}
        )
    except Exception as e:
        return HealthStatus(
            service="qdrant",
            status="unhealthy",
            error=str(e)
        )
```

---

## 10. Error Handling

### 10.1 Database Exceptions

**Must handle:**

- `OperationalError` - Connection failures, timeouts
- `IntegrityError` - Constraint violations (unique, foreign key)
- `DataError` - Invalid data types, out of range
- `ProgrammingError` - SQL syntax errors

**Must NOT:**

- Swallow exceptions silently
- Auto-retry on IntegrityError (indicates application bug)
- Expose raw SQL in error messages (security risk)

**Example:**

```python
from sqlalchemy.exc import OperationalError, IntegrityError

def execute_query(session, query):
    try:
        result = session.execute(query)
        session.commit()
        return result
    except IntegrityError as e:
        session.rollback()
        logger.error(f"Integrity error: {e}")
        raise  # Let caller handle (indicates bug)
    except OperationalError as e:
        session.rollback()
        logger.error(f"Database operation failed: {e}")
        raise ConnectionError("Database unavailable") from e
    except Exception as e:
        session.rollback()
        logger.error(f"Unexpected database error: {e}")
        raise
```

---

### 10.2 Redis Exceptions

**Must handle:**

- `ConnectionError` - Redis unavailable
- `TimeoutError` - Command timeout
- `ResponseError` - Command execution error

**Must NOT:**

- Treat Redis as persistent store (it's ephemeral cache)
- Crash application if Redis unavailable (graceful degradation)

---

### 10.3 Qdrant Exceptions

**Must handle:**

- Connection timeout
- Collection not found
- Dimension mismatch (vector size != expected)
- Search errors

---

## 11. Testing Requirements

### 11.1 Unit Tests

1. **PostgreSQL:**
   - Engine creation with valid config
   - Engine creation with invalid config (raises error)
   - Session lifecycle (open → use → close)
   - Transaction commit/rollback
   - Connection retry on failure
   - Health check success/failure

2. **Redis:**
   - Client initialization
   - Set/get operations
   - TTL expiration
   - Lock acquire/release
   - Key collision prevention (namespacing)
   - Health check success/failure

3. **Qdrant:**
   - Client initialization
   - Collection creation
   - Embedding storage
   - Similarity search
   - Metadata filtering
   - Health check success/failure

---

### 11.2 Integration Tests

1. **Database connection pooling:**
   - Concurrent session checkouts (no pool exhaustion)
   - Session leak detection (all sessions returned)
   - Pool recycle (stale connections removed)

2. **Redis concurrency:**
   - Lock contention (two processes acquire lock, only one succeeds)
   - TTL expiration (key deleted after timeout)

3. **Qdrant search:**
   - Store embeddings with metadata
   - Search with filters (organization_id, difficulty)
   - Top-k results returned

---

### 11.3 Failure Tests

1. **Database unavailable:**
   - Application startup fails gracefully
   - Retry logic attempts reconnection
   - Health check reports unhealthy

2. **Redis unavailable:**
   - Application continues (graceful degradation)
   - Session state falls back to PostgreSQL

3. **Qdrant unavailable:**
   - Vector search disabled
   - Application continues (if optional)

---

## 12. Critical Risks

1. **Long-running database session not closed:**
   - Risk: Connection pool exhaustion
   - Mitigation: Use context managers, monitor pool metrics

2. **Redis key collision:**
   - Risk: Two modules use same key, data corruption
   - Mitigation: Strict key namespacing (interview:, auth:, coding:)

3. **Qdrant dimension mismatch:**
   - Risk: Store 768-dim vector in 1536-dim collection, query fails
   - Mitigation: Validate dimensions at storage time

4. **Blocking database call in async context:**
   - Risk: Event loop blocked, application unresponsive
   - Mitigation: Use async SQLAlchemy or run_in_executor

5. **Silent auto-commit:**
   - Risk: Partial transaction committed, data inconsistency
   - Mitigation: Explicit commit/rollback, disable autocommit

6. **Using Redis as persistent store:**
   - Risk: Data loss on eviction/restart
   - Mitigation: Treat Redis as cache only, persist to PostgreSQL

---

## 13. Observability

### 13.1 Metrics

**Must expose:**

- Database connection pool size (gauge)
- Database query count (counter)
- Database query latency (histogram)
- Redis command count (counter)
- Redis command latency (histogram)
- Qdrant search count (counter)
- Qdrant search latency (histogram)

---

### 13.2 Logging

**Must log:**

- Connection establishment (INFO)
- Connection failure (ERROR with retry count)
- Query timeouts (WARNING)
- Pool exhaustion (CRITICAL)
- Health check failures (WARNING)
- Graceful shutdown (INFO)

**Must NOT log:**

- Sensitive data (passwords, tokens, personal info)
- Full SQL queries with user data (log parameterized queries only)

---

## 14. Future Enhancements

1. **Read replicas:** Route read queries to replica database (performance)
2. **Connection pooling per tenant:** Isolate tenants at connection level
3. **Query result caching:** Cache frequent queries in Redis (performance)
4. **Database sharding:** Distribute data across multiple databases (scale)
5. **Redis Cluster:** Multi-node Redis for high availability
6. **Qdrant collections per tenant:** Tenant-specific vector collections

---

## 15. Acceptance Criteria

**Core persistence module is complete when:**

✅ PostgreSQL connection established with retry logic
✅ Session factory provides request-scoped sessions
✅ Context manager pattern prevents session leaks
✅ Redis client initialized with connection pooling
✅ Redis key namespacing prevents collisions
✅ Distributed locks prevent concurrent operations
✅ Qdrant client initialized and collection created
✅ Embedding storage and search working
✅ Health checks implemented for all services
✅ Graceful shutdown cleanup implemented
✅ Connection pool monitoring metrics exposed
✅ No domain logic in any persistence module
✅ All tests passing (unit, integration, failure)

---

**End of Persistence Module Requirements**
