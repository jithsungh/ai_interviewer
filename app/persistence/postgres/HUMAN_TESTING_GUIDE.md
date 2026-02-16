# PostgreSQL Persistence Module - Human Testing Guide

## Overview

This guide helps you manually test the PostgreSQL persistence layer to verify:

- Database connectivity
- Connection pooling
- Session management
- Health checks
- Transaction handling

The PostgreSQL module is **pure infrastructure** - it provides database connectivity with no business logic.

---

## Prerequisites

### 1. Environment Setup

Ensure your `.env` file has valid database credentials:

```bash
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/interviewer
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_ECHO=false
DB_POOL_PRE_PING=true
DB_QUERY_TIMEOUT=30
```

### 2. Start PostgreSQL

Ensure PostgreSQL is running:

```bash
# Check if PostgreSQL is running
pg_isready -h localhost -p 5432

# Or using Docker
docker ps | grep postgres
```

### 3. Verify Database Exists

```bash
psql -h localhost -U postgres -l | grep interviewer
```

---

## Testing Scenarios

### Test 1: Initialize PostgreSQL Infrastructure

**Objective:** Verify engine and session factory initialize correctly

**Steps:**

1. Create a test script `test_init.py`:

```python
from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres, cleanup_postgres

# Load config
config = DatabaseSettings()

# Initialize
print(f"Initializing with database: {config.database_url}")
init_postgres(config)
print("✅ PostgreSQL initialized successfully")

# Cleanup
cleanup_postgres()
print("✅ PostgreSQL cleaned up successfully")
```

2. Run the script:

```bash
python test_init.py
```

**Expected Output:**

```
Initializing with database: postgresql+asyncpg://...
Database engine created successfully (pool_size=20, max_overflow=10)
Session factory initialized
✅ PostgreSQL initialized successfully
Cleaning up PostgreSQL connections...
PostgreSQL cleanup complete
✅ PostgreSQL cleaned up successfully
```

**Success Criteria:**

- ✅ No errors or exceptions
- ✅ Engine created message appears
- ✅ Session factory initialized message appears
- ✅ Cleanup completes without errors

---

### Test 2: Database Connectivity

**Objective:** Verify ability to connect and execute queries

**Steps:**

1. Create `test_connectivity.py`:

```python
from sqlalchemy import text
from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres, get_engine, cleanup_postgres

# Initialize
config = DatabaseSettings()
init_postgres(config)

# Test connection
engine = get_engine()
with engine.connect() as conn:
    result = conn.execute(text("SELECT version()"))
    version = result.fetchone()[0]
    print(f"✅ Connected to: {version}")

    # Test simple query
    result = conn.execute(text("SELECT 1 + 1 AS sum"))
    assert result.fetchone()[0] == 2
    print("✅ Query execution works")

cleanup_postgres()
```

2. Run:

```bash
python test_connectivity.py
```

**Expected Output:**

```
✅ Connected to: PostgreSQL 16.11 on ...
✅ Query execution works
```

**Success Criteria:**

- ✅ PostgreSQL version printed
- ✅ Query returns correct result
- ✅ No connection errors

---

### Test 3: Session Management

**Objective:** Verify FastAPI dependency injection works

**Steps:**

1. Create `test_session.py`:

```python
from sqlalchemy import text
from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres, get_db_session, cleanup_postgres

# Initialize
config = DatabaseSettings()
init_postgres(config)

# Get session via dependency
session_gen = get_db_session()
session = next(session_gen)

try:
    # Execute query using session
    result = session.execute(text("SELECT current_database()"))
    db_name = result.fetchone()[0]
    print(f"✅ Connected to database: {db_name}")

    # Test another query
    result = session.execute(text("SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'"))
    table_count = result.fetchone()[0]
    print(f"✅ Found {table_count} tables in public schema")

finally:
    # Close session
    try:
        next(session_gen)
    except StopIteration:
        pass
    print("✅ Session closed properly")

cleanup_postgres()
```

2. Run:

```bash
python test_session.py
```

**Expected Output:**

```
✅ Connected to database: ai_interviewer
✅ Found X tables in public schema
✅ Session closed properly
```

**Success Criteria:**

- ✅ Session creates successfully
- ✅ Queries execute
- ✅ Session closes without errors

---

### Test 4: Connection Pool Status

**Objective:** Verify pool monitoring works

**Steps:**

1. Create `test_pool.py`:

```python
from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    get_engine,
    get_pool_status,
    log_pool_stats,
    cleanup_postgres
)

# Initialize
config = DatabaseSettings()
init_postgres(config)

# Check initial pool status
status = get_pool_status()
print(f"Pool Size: {status['pool_size']}")
print(f"Checked Out: {status['checked_out']}")
print(f"Overflow: {status['overflow']}")
print(f"Total Connections: {status['total_connections']}")

# Log pool stats
log_pool_stats()

# Check out some connections
engine = get_engine()
connections = []
for i in range(3):
    conn = engine.connect()
    connections.append(conn)
    print(f"✅ Checked out connection {i+1}")

# Check status again
status = get_pool_status()
print(f"\nAfter checkout:")
print(f"Checked Out: {status['checked_out']}")

# Return connections
for conn in connections:
    conn.close()
print(f"\n✅ Returned {len(connections)} connections")

# Final status
status = get_pool_status()
print(f"Final Checked Out: {status['checked_out']}")

cleanup_postgres()
```

2. Run:

```bash
python test_pool.py
```

**Expected Output:**

```
Pool Size: 20
Checked Out: 0
Overflow: 0
Total Connections: 20
✅ Checked out connection 1
✅ Checked out connection 2
✅ Checked out connection 3

After checkout:
Checked Out: 3

✅ Returned 3 connections
Final Checked Out: 0
```

**Success Criteria:**

- ✅ Initial checked_out is 0
- ✅ Checked_out increases when connections are taken
- ✅ Checked_out decreases when connections returned
- ✅ No connection leaks

---

### Test 5: Health Checks

**Objective:** Verify health check API works

**Steps:**

1. Create `test_health.py`:

```python
import json
from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    check_postgres_health,
    check_postgres_connectivity,
    get_health_check_endpoint_response,
    cleanup_postgres
)

# Initialize
config = DatabaseSettings()
init_postgres(config)

# Test simple connectivity check
is_healthy = check_postgres_connectivity()
print(f"✅ Connectivity check: {is_healthy}")

# Test full health check
health = check_postgres_health()
print(f"\nHealth Status: {health['status']}")
print(f"Latency: {health['latency_ms']}ms")
print(f"Pool checked out: {health['pool']['checked_out']}/{health['pool']['pool_size']}")

if 'errors' in health:
    print(f"Errors: {health['errors']}")

# Test endpoint response format
endpoint_response = get_health_check_endpoint_response()
print(f"\nEndpoint Response:")
print(json.dumps(endpoint_response, indent=2))

cleanup_postgres()
```

2. Run:

```bash
python test_health.py
```

**Expected Output:**

```
✅ Connectivity check: True

Health Status: healthy
Latency: 12.5ms
Pool checked out: 0/20

Endpoint Response:
{
  "service": "postgresql",
  "status": "healthy",
  "checks": {
    "connectivity": "pass",
    "latency": {
      "value_ms": 12.5,
      "threshold_ms": 1000,
      "status": "pass"
    },
    "pool": {
      "size": 20,
      "checked_out": 0,
      "utilization": 0.0
    }
  },
  "timestamp": 1708123456.789,
  "errors": []
}
```

**Success Criteria:**

- ✅ Connectivity returns `true`
- ✅ Health status is "healthy" or "degraded"
- ✅ Latency is measured and reasonable (<1000ms for local)
- ✅ Pool metrics are present
- ✅ Endpoint response has correct structure

---

### Test 6: Transaction Handling

**Objective:** Verify commit and rollback work

**Steps:**

1. First create a test table:

```sql
CREATE TABLE test_transactions (
    id SERIAL PRIMARY KEY,
    value TEXT
);
```

2. Create `test_transactions.py`:

```python
from sqlalchemy import text
from app.config.settings import DatabaseSettings
from app.persistence.postgres import (
    init_postgres,
    get_engine,
    db_session_context,
    cleanup_postgres
)

# Initialize
config = DatabaseSettings()
init_postgres(config)
engine = get_engine()

# Test 1: Commit transaction
print("Test 1: Commit")
with db_session_context() as session:
    session.execute(
        text("INSERT INTO test_transactions (value) VALUES (:val)"),
        {"val": "test_commit"}
    )
    print("✅ Data inserted")

# Verify persisted
with engine.connect() as conn:
    result = conn.execute(text("SELECT value FROM test_transactions WHERE value = 'test_commit'"))
    assert result.fetchone() is not None
    print("✅ Transaction committed successfully")

# Test 2: Rollback on error
print("\nTest 2: Rollback")
try:
    with db_session_context() as session:
        session.execute(
            text("INSERT INTO test_transactions (value) VALUES (:val)"),
            {"val": "test_rollback"}
        )
        raise ValueError("Intentional error")
except ValueError:
    print("✅ Exception raised")

# Verify NOT persisted
with engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM test_transactions WHERE value = 'test_rollback'"))
    assert result.fetchone()[0] == 0
    print("✅ Transaction rolled back successfully")

# Cleanup
with engine.begin() as conn:
    conn.execute(text("DROP TABLE test_transactions"))
    print("\n✅ Test table dropped")

cleanup_postgres()
```

3. Run:

```bash
python test_transactions.py
```

**Expected Output:**

```
Test 1: Commit
✅ Data inserted
✅ Transaction committed successfully

Test 2: Rollback
✅ Exception raised
✅ Transaction rolled back successfully

✅ Test table dropped
```

**Success Criteria:**

- ✅ Committed data persists
- ✅ Rolled back data does not persist
- ✅ Exceptions trigger automatic rollback

---

### Test 7: Connection Retry Logic

**Objective:** Verify retry works when database temporarily unavailable

**Steps:**

1. This test requires stopping and starting PostgreSQL, so do this manually

2. Create `test_retry.py`:

```python
import time
from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres, cleanup_postgres

print("Testing retry logic...")
print("⚠️  Stop PostgreSQL now, then start it within 10 seconds")
time.sleep(5)

# Try to initialize (will retry if DB is down)
config = DatabaseSettings()

try:
    init_postgres(config)
    print("✅ Connected (possibly after retries)")
    cleanup_postgres()
except Exception as e:
    print(f"❌ Failed to connect after retries: {e}")
```

3. In one terminal, run:

```bash
python test_retry.py
```

4. In another terminal, stop then start PostgreSQL:

```bash
# Stop
sudo systemctl stop postgresql
# Or: docker stop postgres-container

# Wait 3 seconds, then start
sleep 3
sudo systemctl start postgresql
# Or: docker start postgres-container
```

**Expected Output:**

```
Testing retry logic...
⚠️  Stop PostgreSQL now, then start it within 10 seconds
Database connection failed (attempt 1/3): ...
Retrying in 2s...
Database connection failed (attempt 2/3): ...
Retrying in 4s...
✅ Connected (possibly after retries)
```

**Success Criteria:**

- ✅ Retries connection automatically
- ✅ Eventually succeeds when database comes back
- ✅ Uses exponential backoff (2s, 4s, 8s)

---

## Integration with FastAPI

### Example: Health Check Endpoint

Add to your FastAPI app:

```python
from fastapi import FastAPI
from app.persistence.postgres import get_health_check_endpoint_response

app = FastAPI()

@app.get("/health/database")
def database_health():
    """Database health check endpoint"""
    return get_health_check_endpoint_response()
```

**Test:**

```bash
curl http://localhost:8000/health/database
```

**Expected Response:**

```json
{
  "service": "postgresql",
  "status": "healthy",
  "checks": {
    "connectivity": "pass",
    "latency": {
      "value_ms": 12.5,
      "threshold_ms": 1000,
      "status": "pass"
    },
    "pool": {
      "size": 20,
      "checked_out": 2,
      "utilization": 10.0
    }
  },
  "timestamp": 1708123456.789,
  "errors": []
}
```

---

## Troubleshooting

### Problem: "Engine not initialized"

**Cause:** `init_postgres()` not called before using database

**Solution:**

```python
from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres

config = DatabaseSettings()
init_postgres(config)  # Call this first!
```

---

### Problem: Connection pool exhausted

**Symptom:** Requests hang or timeout

**Cause:** Sessions not being closed properly

**Solution:** Always use dependency injection or context managers:

```python
# ✅ Good - auto-closes
with db_session_context() as session:
    ...

# ✅ Good - FastAPI dependency
def my_endpoint(db: Session = Depends(get_db_session)):
    ...

# ❌ Bad - manual session management
session = SessionLocal()
# ... (might not close)
```

---

### Problem: "Connection refused"

**Cause:** PostgreSQL not running or wrong credentials

**Check:**

1. Is PostgreSQL running? `pg_isready -h localhost`
2. Are credentials correct in `.env`?
3. Can you connect with psql? `psql -h localhost -U postgres -d ai_interviewer`

---

### Problem: High latency warnings

**Cause:** Database is slow or under load

**Check:**

1. Run `check_postgres_health()` - check `latency_ms`
2. If consistently > 100ms, investigate:
   - Database server load
   - Network latency
   - Query performance
3. Check pool utilization - might need to increase pool size

---

## Automated Tests

Run the included test suites:

### Unit Tests (No database required):

```bash
pytest tests/unit/persistence/postgres/ -v
```

### Integration Tests (Requires running database):

```bash
# Set test database URL
export TEST_DATABASE_URL="postgresql://postgres:password@localhost:5432/ai_interviewer_test"

# Run integration tests
pytest tests/integration/persistence/postgres/ -v
```

---

## Summary Checklist

After completing all tests, verify:

- [ ] ✅ Engine initializes successfully
- [ ] ✅ Database connectivity works
- [ ] ✅ Sessions create and close properly
- [ ] ✅ Connection pool status is monitored
- [ ] ✅ Health checks return correct data
- [ ] ✅ Transactions commit and rollback correctly
- [ ] ✅ Connection retry logic works
- [ ] ✅ FastAPI integration works
- [ ] ✅ No connection leaks detected
- [ ] ✅ Cleanup completes without errors

---

**Module Status: ✅ READY FOR INTEGRATION**

The PostgreSQL persistence module is pure infrastructure with no business logic. It provides the foundation for all database operations in the application.
