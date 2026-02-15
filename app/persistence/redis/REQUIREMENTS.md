# Redis - Client Wrapper & Session Utilities

## 1. Purpose

The **Redis** layer provides:

- Redis connection pool and client wrapper
- Key namespacing patterns (prevent collisions)
- TTL management for session state
- Distributed locks for concurrency control
- Atomic operations (INCR, GETSET, Lua scripts)

**Critical responsibility:** This is **pure caching infrastructure**. It must:

- Provide Redis connectivity with retry logic
- Manage key lifecycle (set, get, expire, delete)
- Implement distributed locks safely
- **Contain ZERO business logic**

**Architectural note:**

> **Redis is EPHEMERAL CACHE, not persistent storage.**
> All critical data must be persisted to PostgreSQL.
> Redis provides speed, not durability.

---

## 2. Responsibilities

### 2.1 Client Initialization

**Must create Redis client with:**

- Connection pooling (max_connections)
- Connection timeout (default: 10s)
- Socket timeout (default: 5s)
- Retry on timeout (default: True)
- Decode responses (default: True, return strings not bytes)

**Example configuration:**

```python
import redis
from redis import ConnectionPool

def create_redis_client(config: RedisConfig) -> redis.Redis:
    """
    Create Redis client with connection pooling.

    Configuration:
    - max_connections: Pool size (default: 50)
    - connection_timeout: Connect timeout (default: 10s)
    - socket_timeout: Read/write timeout (default: 5s)
    - retry_on_timeout: Retry commands on timeout (default: True)
    - decode_responses: Return strings instead of bytes (default: True)
    """
    pool = ConnectionPool.from_url(
        config.redis_url,
        max_connections=config.max_connections,
        socket_connect_timeout=config.connection_timeout,
        socket_timeout=config.socket_timeout,
        retry_on_timeout=config.retry_on_timeout,
        decode_responses=config.decode_responses
    )

    client = redis.Redis(connection_pool=pool)

    # Test connection
    try:
        client.ping()
        logger.info("Redis connection established")
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise ConnectionError("Redis unavailable") from e

    return client
```

---

### 2.2 Key Namespacing Patterns

**Must define strict key patterns to prevent collisions:**

| Pattern                          | Purpose                       | Example                          |
| -------------------------------- | ----------------------------- | -------------------------------- |
| `interview:session:{id}`         | Interview session state       | `interview:session:12345`        |
| `interview:lock:{id}:{seq}`      | Exchange creation lock        | `interview:lock:12345:5`         |
| `interview:progress:{id}`        | Progress tracking             | `interview:progress:12345`       |
| `ws:connection:{socket_id}`      | WebSocket connection metadata | `ws:connection:uuid-1234`        |
| `rate_limit:{user_id}:{action}`  | Rate limiting counters        | `rate_limit:456:start_interview` |
| `code:execution:{submission_id}` | Code execution status         | `code:execution:789`             |
| `audio:silence:{recording_id}`   | Audio silence detection state | `audio:silence:890`              |
| `evaluation:cache:{exchange_id}` | Cached evaluation results     | `evaluation:cache:567`           |

**Namespacing rules:**

1. Prefix with module name (`interview:`, `coding:`, `audio:`)
2. Use colons (`:`) as delimiters
3. Include unique identifier last
4. Document all patterns centrally

---

### 2.3 TTL Management

**Must support key expiration:**

**Set with TTL:**

```python
def set_session_state(session_id: int, data: dict, ttl_seconds: int):
    """
    Store session state with automatic expiration.

    Args:
        session_id: Interview submission ID
        data: Session state (status, current_sequence, etc.)
        ttl_seconds: Time to live (e.g., 3600 = 1 hour)
    """
    key = f"interview:session:{session_id}"
    redis_client.hset(key, mapping=data)
    redis_client.expire(key, ttl_seconds)
```

**Refresh TTL (on heartbeat):**

```python
def refresh_session_ttl(session_id: int, ttl_seconds: int):
    """
    Refresh session TTL (called on WebSocket heartbeat).

    Prevents active sessions from expiring.
    """
    key = f"interview:session:{session_id}"
    redis_client.expire(key, ttl_seconds)
```

**Get remaining TTL:**

```python
def get_session_ttl(session_id: int) -> int:
    """
    Get remaining TTL for session (seconds).

    Returns:
        Remaining seconds (or -1 if no expiry, -2 if key not found)
    """
    key = f"interview:session:{session_id}"
    return redis_client.ttl(key)
```

---

### 2.4 Distributed Locks

**Must implement safe distributed locking:**

**Purpose:** Prevent concurrent operations (e.g., duplicate exchange creation).

**Implementation:**

```python
from contextlib import contextmanager
import uuid
import time

@contextmanager
def acquire_lock(lock_key: str, timeout_seconds: int = 10, retry_interval: float = 0.1):
    """
    Acquire distributed lock with automatic release.

    Usage:
        with acquire_lock("interview:lock:12345:5", timeout_seconds=10):
            # Critical section (only one process executes)
            create_exchange(...)

    Args:
        lock_key: Unique lock identifier
        timeout_seconds: Lock expiration (prevents deadlock)
        retry_interval: Time between retry attempts (seconds)

    Raises:
        LockAcquisitionError: Failed to acquire lock within timeout
    """
    lock_value = str(uuid.uuid4())  # Unique identifier for this lock holder
    acquired = False
    start_time = time.time()

    try:
        # Try to acquire lock
        while time.time() - start_time < timeout_seconds:
            # SET NX (set if not exists) with expiration
            acquired = redis_client.set(
                lock_key,
                lock_value,
                nx=True,  # Only set if key doesn't exist
                ex=timeout_seconds  # Expiration time
            )

            if acquired:
                logger.debug(f"Lock acquired: {lock_key}")
                break

            # Lock held by another process, wait and retry
            time.sleep(retry_interval)

        if not acquired:
            raise LockAcquisitionError(f"Failed to acquire lock: {lock_key}")

        yield  # Critical section executes here

    finally:
        # Release lock (only if we hold it)
        if acquired:
            # Lua script ensures we only delete our own lock
            release_script = """
            if redis.call("GET", KEYS[1]) == ARGV[1] then
                return redis.call("DEL", KEYS[1])
            else
                return 0
            end
            """
            redis_client.eval(release_script, 1, lock_key, lock_value)
            logger.debug(f"Lock released: {lock_key}")
```

**Lock usage example:**

```python
def create_exchange_with_lock(submission_id: int, sequence_order: int):
    """
    Create exchange with distributed lock.

    Prevents race condition when audio and code complete simultaneously.
    """
    lock_key = f"interview:lock:{submission_id}:{sequence_order}"

    try:
        with acquire_lock(lock_key, timeout_seconds=10):
            # Check if exchange already exists (idempotency)
            existing = db.query(InterviewExchange).filter(
                InterviewExchange.interview_submission_id == submission_id,
                InterviewExchange.sequence_order == sequence_order
            ).first()

            if existing:
                return existing  # Idempotent return

            # Create exchange
            exchange = InterviewExchange(...)
            db.add(exchange)
            db.commit()
            return exchange

    except LockAcquisitionError:
        # Another process is creating exchange, check if it exists
        time.sleep(0.5)  # Wait for other process to finish
        existing = db.query(InterviewExchange).filter(...).first()
        if existing:
            return existing
        else:
            raise
```

---

### 2.5 Atomic Operations

**Must support atomic operations:**

**INCR (counter):**

```python
def increment_rate_limit(user_id: int, action: str) -> int:
    """
    Increment rate limit counter atomically.

    Returns:
        New counter value
    """
    key = f"rate_limit:{user_id}:{action}"
    count = redis_client.incr(key)

    # Set expiration on first increment
    if count == 1:
        redis_client.expire(key, 60)  # 1 minute window

    return count
```

**GETSET (atomic swap):**

```python
def atomic_swap_status(session_id: int, new_status: str) -> Optional[str]:
    """
    Atomically swap session status.

    Returns:
        Previous status (or None if key didn't exist)
    """
    key = f"interview:session:{session_id}:status"
    old_status = redis_client.getset(key, new_status)
    return old_status
```

**Lua script (complex atomic operation):**

```python
def atomic_increment_with_max(key: str, max_value: int) -> int:
    """
    Increment counter but cap at max_value.

    Atomic operation using Lua script.
    """
    script = """
    local current = redis.call("GET", KEYS[1])
    if current == false then
        current = 0
    else
        current = tonumber(current)
    end

    if current < tonumber(ARGV[1]) then
        current = current + 1
        redis.call("SET", KEYS[1], current)
    end

    return current
    """

    result = redis_client.eval(script, 1, key, max_value)
    return int(result)
```

---

### 2.6 Batch Operations

**Must support efficient batch operations:**

**Pipeline (reduce round trips):**

```python
def batch_set_session_data(session_id: int, updates: dict):
    """
    Update multiple session fields in single round trip.
    """
    key = f"interview:session:{session_id}"

    pipe = redis_client.pipeline()
    for field, value in updates.items():
        pipe.hset(key, field, value)
    pipe.expire(key, 3600)  # Refresh TTL
    pipe.execute()
```

**Multi-get:**

```python
def get_multiple_sessions(session_ids: list[int]) -> dict[int, dict]:
    """
    Fetch multiple session states efficiently.

    Returns:
        {session_id: session_data}
    """
    keys = [f"interview:session:{sid}" for sid in session_ids]

    pipe = redis_client.pipeline()
    for key in keys:
        pipe.hgetall(key)
    results = pipe.execute()

    return {sid: data for sid, data in zip(session_ids, results) if data}
```

---

### 2.7 Health Check

**Must implement Redis connectivity check:**

```python
import time
from typing import Dict, Any

def check_redis_health() -> Dict[str, Any]:
    """
    Check Redis connectivity and performance.

    Returns:
        {
            "status": "healthy" | "unhealthy",
            "latency_ms": float,
            "info": {
                "connected_clients": int,
                "used_memory_human": str,
                "uptime_in_seconds": int
            },
            "error": str | None
        }
    """
    try:
        start = time.time()

        # Ping test
        redis_client.ping()

        latency_ms = (time.time() - start) * 1000

        # Get info
        info = redis_client.info()

        return {
            "status": "healthy",
            "latency_ms": round(latency_ms, 2),
            "info": {
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "uptime_in_seconds": info.get("uptime_in_seconds", 0)
            },
            "error": None
        }

    except Exception as e:
        return {
            "status": "unhealthy",
            "latency_ms": None,
            "info": None,
            "error": str(e)
        }
```

---

## 3. Connection Retry Logic

**Must implement retry on connection failure:**

```python
def create_redis_client_with_retry(config: RedisConfig, max_retries: int = 3):
    """
    Create Redis client with connection retry.

    Retries on ConnectionError with exponential backoff.
    """
    for attempt in range(max_retries):
        try:
            pool = ConnectionPool.from_url(
                config.redis_url,
                max_connections=config.max_connections,
                socket_connect_timeout=config.connection_timeout,
                socket_timeout=config.socket_timeout
            )

            client = redis.Redis(connection_pool=pool)
            client.ping()  # Test connection

            logger.info("Redis connection established")
            return client

        except redis.ConnectionError as e:
            if attempt == max_retries - 1:
                logger.critical(f"Failed to connect to Redis after {max_retries} attempts")
                raise ConnectionError(f"Redis unavailable: {e}") from e

            sleep_time = 2 ** attempt
            logger.warning(f"Redis connection failed (attempt {attempt + 1}/{max_retries}), retrying in {sleep_time}s...")
            time.sleep(sleep_time)
```

---

## 4. Graceful Shutdown

**Must cleanup connections on shutdown:**

```python
import atexit

def cleanup_redis():
    """
    Close Redis connection pool.

    Called on application shutdown.
    """
    logger.info("Cleaning up Redis connections...")

    # Close all connections in pool
    redis_client.connection_pool.disconnect()

    logger.info("Redis cleanup complete")

atexit.register(cleanup_redis)
```

---

## 5. Error Handling

### 5.1 Exception Types

**Must handle:**

1. **ConnectionError** - Redis unavailable
   - Retry with backoff
   - Graceful degradation (fallback to PostgreSQL)

2. **TimeoutError** - Command timeout
   - Retry (up to max_retries)
   - Log warning

3. **ResponseError** - Command execution error
   - Log error
   - Raise to caller

4. **LockNotOwnedError** - Attempt to release lock not owned
   - Log warning (benign race condition)

---

### 5.2 Example Error Handling

```python
from redis.exceptions import ConnectionError, TimeoutError, ResponseError

def get_with_fallback(key: str, default=None):
    """
    Get value from Redis with fallback.

    Returns default if Redis unavailable (graceful degradation).
    """
    try:
        return redis_client.get(key)
    except (ConnectionError, TimeoutError) as e:
        logger.warning(f"Redis unavailable, using fallback: {e}")
        return default
    except ResponseError as e:
        logger.error(f"Redis command error: {e}")
        raise

def set_with_retry(key: str, value: str, retry_count: int = 3):
    """
    Set value with retry on timeout.
    """
    for attempt in range(retry_count):
        try:
            redis_client.set(key, value)
            return
        except TimeoutError:
            if attempt == retry_count - 1:
                raise
            logger.warning(f"Redis timeout, retrying... ({attempt + 1}/{retry_count})")
            time.sleep(0.1)
```

---

## 6. Testing Requirements

### 6.1 Unit Tests

1. **Client initialization:** Valid config → client created
2. **Ping test:** Redis available → ping returns True
3. **Set/get:** Store value → retrieve value
4. **TTL expiration:** Set key with TTL → key expires after timeout
5. **Lock acquisition:** Acquire lock → lock held
6. **Lock release:** Release lock → lock freed
7. **Lock contention:** Two processes acquire same lock → one succeeds, one waits

---

### 6.2 Integration Tests

1. **Concurrent locks:** 10 processes try to acquire same lock → only 1 succeeds
2. **Lock timeout:** Hold lock beyond timeout → lock auto-released
3. **Pipeline batch:** Update 100 keys in single pipeline → single round trip
4. **Rate limiting:** Increment counter 100 times → counter = 100

---

### 6.3 Failure Tests

1. **Redis unavailable:** Redis down → ConnectionError raised
2. **Connection timeout:** Redis slow → TimeoutError after 5s
3. **Graceful degradation:** Redis down → application continues (fallback to PostgreSQL)

---

## 7. Configuration

```python
from pydantic import BaseModel, Field

class RedisConfig(BaseModel):
    """Redis connection configuration."""

    # Connection
    redis_url: str = Field(..., description="Redis connection string (redis://host:port/db)")

    # Pool
    max_connections: int = Field(50, ge=1, le=200, description="Max connections in pool")
    connection_timeout: int = Field(10, ge=1, le=60, description="Connect timeout (seconds)")
    socket_timeout: int = Field(5, ge=1, le=30, description="Socket timeout (seconds)")

    # Retry
    retry_on_timeout: bool = Field(True, description="Retry commands on timeout")
    max_retries: int = Field(3, ge=1, le=10, description="Max command retries")

    # Features
    decode_responses: bool = Field(True, description="Decode bytes to strings")

    # Health check
    health_check_interval: int = Field(60, ge=10, le=300, description="Health check interval (seconds)")
```

---

## 8. Critical Risks

1. **Redis used as persistent store:** Data loss on eviction/restart
2. **Key collision:** Two modules use same key, data corruption
3. **Lock held indefinitely:** Process crashes while holding lock, deadlock
4. **No TTL on session keys:** Memory exhaustion
5. **Large value storage:** Redis becomes slow, memory exhaustion
6. **No connection pooling:** Connection exhaustion, latency

---

## 9. Observability

### 9.1 Metrics

**Must expose:**

- `redis_commands_total` (counter) - Total commands executed
- `redis_command_duration_seconds` (histogram) - Command latency
- `redis_pool_connections` (gauge) - Active connections
- `redis_lock_acquisitions_total` (counter) - Lock acquisitions
- `redis_lock_timeouts_total` (counter) - Lock acquisition timeouts

---

### 9.2 Logging

**Must log:**

- Connection established (INFO)
- Connection retry (WARNING)
- Connection failure (ERROR)
- Lock acquisition timeout (WARNING)
- Command timeout (WARNING)
- Key collision detected (ERROR)

---

## 10. Acceptance Criteria

**Redis module is complete when:**

✅ Redis client initialized with connection pooling
✅ Key namespacing prevents collisions
✅ TTL management working (set, refresh, expire)
✅ Distributed locks implemented safely
✅ Atomic operations supported (INCR, GETSET, Lua)
✅ Connection retry with exponential backoff
✅ Health check returns status and metrics
✅ Graceful shutdown cleanup
✅ Error handling with graceful degradation
✅ No business logic in module
✅ All tests passing

---

**End of Redis Requirements**
