# Redis Persistence Module - Human Testing Guide

## Overview

This guide provides step-by-step instructions for manually testing the Redis persistence module.

**Module:** `app.persistence.redis`  
**Purpose:** Infrastructure layer for Redis connectivity, caching, distributed locking  
**Dependencies:** Redis server running locally or remotely

---

## Prerequisites

### 1. Install Redis

**macOS (Homebrew):**

```bash
brew install redis
brew services start redis
```

**Ubuntu/Debian:**

```bash
sudo apt-get install redis-server
sudo systemctl start redis-server
```

**Windows (WSL2 or Docker):**

```bash
# Using Docker
docker run -d -p 6379:6379 --name redis-test redis:7-alpine
```

### 2. Verify Redis is Running

```bash
redis-cli ping
# Expected output: PONG
```

### 3. Install Python Dependencies

```bash
# From project root
pip install -r requirements.txt
```

---

## Testing Environment Setup

### 1. Configure Environment Variables

Create or update `.env` file:

```bash
# Redis Configuration
REDIS_URL=redis://localhost:6379/0
REDIS_DB=0
REDIS_MAX_CONNECTIONS=50
REDIS_CONNECTION_TIMEOUT=10
REDIS_SOCKET_TIMEOUT=5
REDIS_RETRY_ON_TIMEOUT=true
REDIS_MAX_RETRIES=3
REDIS_DECODE_RESPONSES=true
REDIS_SESSION_TTL=3600
REDIS_LOCK_TIMEOUT=10
REDIS_HEALTH_CHECK_INTERVAL=60
```

### 2. Start Python REPL

```bash
# From project root
python
```

---

## Manual Test Scenarios

### Test 1: Client Initialization

**Objective:** Verify Redis client initializes correctly.

```python
from app.config.settings import RedisSettings
from app.persistence.redis import init_redis_client, get_redis_client

# Create configuration
config = RedisSettings(
    redis_url="redis://localhost:6379/0",
    redis_db=0,
    redis_password=None,
    redis_max_connections=50,
    redis_connection_timeout=10,
    redis_socket_timeout=5,
    redis_retry_on_timeout=True,
    redis_max_retries=3,
    redis_decode_responses=True,
    redis_session_ttl=3600,
    redis_lock_timeout=10,
    redis_health_check_interval=60,
)

# Initialize client
client = init_redis_client(config)
print(f"✅ Client initialized: {client}")

# Get client (should return same instance)
client2 = get_redis_client()
print(f"✅ Client retrieved: {client2 is client}")
```

**Expected Output:**

```
✅ Client initialized: <redis.client.Redis object at 0x...>
✅ Client retrieved: True
```

---

### Test 2: Basic Key-Value Operations

**Objective:** Test setting, getting, and deleting values.

```python
from app.persistence.redis import set_value, get_value, delete_key, exists

# Set a value
set_value("test:user:123", "John Doe")
print("✅ Value set")

# Get the value
value = get_value("test:user:123")
print(f"✅ Retrieved value: {value}")

# Check if key exists
key_exists = exists("test:user:123")
print(f"✅ Key exists: {key_exists}")

# Delete the key
delete_key("test:user:123")
print("✅ Key deleted")

# Verify deletion
key_exists_after = exists("test:user:123")
print(f"✅ Key exists after delete: {key_exists_after}")
```

**Expected Output:**

```
✅ Value set
✅ Retrieved value: John Doe
✅ Key exists: True
✅ Key deleted
✅ Key exists after delete: False
```

---

### Test 3: TTL Management

**Objective:** Test time-to-live functionality.

```python
import time
from app.persistence.redis import set_value, get_value, get_ttl

# Set value with TTL
set_value("test:session:abc", "active", ttl_seconds=5)
print("✅ Value set with 5-second TTL")

# Check TTL
ttl = get_ttl("test:session:abc")
print(f"✅ Remaining TTL: {ttl} seconds")

# Verify value exists
value = get_value("test:session:abc")
print(f"✅ Value before expiry: {value}")

# Wait for expiration
print("⏳ Waiting 6 seconds for expiration...")
time.sleep(6)

# Verify value expired
value_after = get_value("test:session:abc", default="expired")
print(f"✅ Value after expiry: {value_after}")
```

**Expected Output:**

```
✅ Value set with 5-second TTL
✅ Remaining TTL: 5 seconds (or 4, 3...)
✅ Value before expiry: active
⏳ Waiting 6 seconds for expiration...
✅ Value after expiry: expired
```

---

### Test 4: Hash Operations

**Objective:** Test hash (field-value) operations.

```python
from app.persistence.redis import hash_set, hash_get, hash_get_all

# Set hash fields
session_data = {
    "user_id": "123",
    "status": "in_progress",
    "started_at": "2024-01-15T10:30:00Z",
}

hash_set("test:interview:session:456", session_data)
print("✅ Hash set with 3 fields")

# Get single field
user_id = hash_get("test:interview:session:456", "user_id")
print(f"✅ Retrieved user_id: {user_id}")

# Get all fields
all_data = hash_get_all("test:interview:session:456")
print(f"✅ Retrieved all fields: {all_data}")

# Cleanup
from app.persistence.redis import delete_key
delete_key("test:interview:session:456")
print("✅ Hash deleted")
```

**Expected Output:**

```
✅ Hash set with 3 fields
✅ Retrieved user_id: 123
✅ Retrieved all fields: {'user_id': '123', 'status': 'in_progress', 'started_at': '2024-01-15T10:30:00Z'}
✅ Hash deleted
```

---

### Test 5: Counters and Rate Limiting

**Objective:** Test atomic counter operations.

```python
from app.persistence.redis import increment_counter, get_value, delete_key

# Increment counter
count1 = increment_counter("test:rate_limit:user:789:api_calls", amount=1, ttl_seconds=60)
print(f"✅ Counter after 1st increment: {count1}")

count2 = increment_counter("test:rate_limit:user:789:api_calls", amount=1)
print(f"✅ Counter after 2nd increment: {count2}")

count3 = increment_counter("test:rate_limit:user:789:api_calls", amount=3)
print(f"✅ Counter after 3rd increment (+3): {count3}")

# Verify final value
final_count = get_value("test:rate_limit:user:789:api_calls")
print(f"✅ Final counter value: {final_count}")

# Cleanup
delete_key("test:rate_limit:user:789:api_calls")
print("✅ Counter deleted")
```

**Expected Output:**

```
✅ Counter after 1st increment: 1
✅ Counter after 2nd increment: 2
✅ Counter after 3rd increment (+3): 5
✅ Final counter value: 5
✅ Counter deleted
```

---

### Test 6: Distributed Locks

**Objective:** Test lock acquisition, release, and race condition prevention.

```python
from app.persistence.redis import acquire_lock, is_locked, LockAcquisitionError
import threading
import time

# Test 1: Basic lock acquisition
print("=== Test 1: Basic Lock ===")
lock_key = "test:interview:lock:submission:123:sequence:5"

with acquire_lock(lock_key, timeout_seconds=10):
    print("✅ Lock acquired")
    print(f"✅ Lock is held: {is_locked(lock_key)}")

print(f"✅ Lock released: {not is_locked(lock_key)}")

# Test 2: Race condition prevention
print("\n=== Test 2: Race Condition ===")

def try_acquire_in_thread(thread_id):
    try:
        with acquire_lock(lock_key, timeout_seconds=2, retry_interval=0.1):
            print(f"Thread {thread_id} acquired lock")
            time.sleep(1)  # Hold lock briefly
    except LockAcquisitionError:
        print(f"Thread {thread_id} FAILED to acquire lock (expected)")

# Start two threads trying to acquire same lock
thread1 = threading.Thread(target=try_acquire_in_thread, args=(1,))
thread2 = threading.Thread(target=try_acquire_in_thread, args=(2,))

thread1.start()
time.sleep(0.1)  # Start thread2 slightly after thread1
thread2.start()

thread1.join()
thread2.join()

print("✅ Only one thread should have acquired the lock")
```

**Expected Output:**

```
=== Test 1: Basic Lock ===
✅ Lock acquired
✅ Lock is held: True
✅ Lock released: True

=== Test 2: Race Condition ===
Thread 1 acquired lock
Thread 2 FAILED to acquire lock (expected)
✅ Only one thread should have acquired the lock
```

---

### Test 7: Batch Operations

**Objective:** Test efficient batch set/get operations.

```python
from app.persistence.redis import batch_set, batch_get, batch_delete

# Batch set
data = {
    "test:batch:key1": "value1",
    "test:batch:key2": "value2",
    "test:batch:key3": "value3",
}

batch_set(data)
print("✅ Batch set 3 keys")

# Batch get
keys = ["test:batch:key1", "test:batch:key2", "test:batch:key3"]
result = batch_get(keys)
print(f"✅ Batch get result: {result}")

# Batch delete
deleted_count = batch_delete(keys)
print(f"✅ Batch delete: {deleted_count} keys deleted")
```

**Expected Output:**

```
✅ Batch set 3 keys
✅ Batch get result: {'test:batch:key1': 'value1', 'test:batch:key2': 'value2', 'test:batch:key3': 'value3'}
✅ Batch delete: 3 keys deleted
```

---

### Test 8: Health Checks

**Objective:** Test health check functionality.

```python
from app.persistence.redis import check_redis_health, check_redis_connectivity, get_pool_status

# Simple connectivity check
is_connected = check_redis_connectivity()
print(f"✅ Redis connected: {is_connected}")

# Comprehensive health check
health = check_redis_health()
print(f"\n=== Health Check ===")
print(f"Status: {health['status']}")
print(f"Latency: {health['latency_ms']}ms")
print(f"Redis Version: {health['info']['redis_version']}")
print(f"Connected Clients: {health['info']['connected_clients']}")
print(f"Memory Used: {health['info']['used_memory_human']}")
print(f"Uptime: {health['info']['uptime_in_days']} days")
print(f"Ops/sec: {health['info']['instantaneous_ops_per_sec']}")

# Pool status
pool_status = get_pool_status()
print(f"\n=== Connection Pool ===")
print(f"Max Connections: {pool_status['max_connections']}")
print(f"In Use: {pool_status['in_use_connections']}")
print(f"Available: {pool_status['available_connections']}")
```

**Expected Output:**

```
✅ Redis connected: True

=== Health Check ===
Status: healthy
Latency: 0.52ms
Redis Version: 7.0.0
Connected Clients: 2
Memory Used: 1.5M
Uptime: 7 days
Ops/sec: 150

=== Connection Pool ===
Max Connections: 50
In Use: 1
Available: 49
```

---

### Test 9: JSON Serialization

**Objective:** Test automatic JSON serialization for complex types.

```python
from app.persistence.redis import set_value, get_value, delete_key

# Complex nested object
interview_state = {
    "submission_id": 12345,
    "candidate_id": 789,
    "status": "in_progress",
    "current_sequence": 5,
    "questions_completed": [1, 2, 3, 4],
    "metadata": {
        "started_at": "2024-01-15T10:30:00Z",
        "ip_address": "192.168.1.1",
    }
}

# Store complex object
set_value("test:interview:state:12345", interview_state)
print("✅ Complex object stored")

# Retrieve and deserialize
retrieved = get_value("test:interview:state:12345", deserialize_json=True)
print(f"✅ Retrieved object type: {type(retrieved)}")
print(f"✅ Submission ID: {retrieved['submission_id']}")
print(f"✅ Current sequence: {retrieved['current_sequence']}")
print(f"✅ Metadata: {retrieved['metadata']}")

# Cleanup
delete_key("test:interview:state:12345")
print("✅ Object deleted")
```

**Expected Output:**

```
✅ Complex object stored
✅ Retrieved object type: <class 'dict'>
✅ Submission ID: 12345
✅ Current sequence: 5
✅ Metadata: {'started_at': '2024-01-15T10:30:00Z', 'ip_address': '192.168.1.1'}
✅ Object deleted
```

---

### Test 10: Cleanup

**Objective:** Test graceful cleanup.

```python
from app.persistence.redis import cleanup_redis, get_redis_client

# Cleanup should close connections
cleanup_redis()
print("✅ Redis connections cleaned up")

# Attempting to get client should fail
try:
    client = get_redis_client()
    print("❌ ERROR: Should have raised RuntimeError")
except RuntimeError as e:
    print(f"✅ Expected error: {e}")
```

**Expected Output:**

```
✅ Redis connections cleaned up
✅ Expected error: Redis client not initialized. Call init_redis_client() first.
```

---

## Running Automated Tests

### Unit Tests (Mocked, No Redis Required)

```bash
# Run all Redis unit tests
pytest tests/unit/persistence/redis/ -v

# Run specific test file
pytest tests/unit/persistence/redis/test_client.py -v
pytest tests/unit/persistence/redis/test_operations.py -v
pytest tests/unit/persistence/redis/test_locks.py -v
pytest tests/unit/persistence/redis/test_health.py -v

# Run with coverage
pytest tests/unit/persistence/redis/ --cov=app.persistence.redis --cov-report=term-missing
```

### Integration Tests (Requires Running Redis)

```bash
# Ensure Redis is running
redis-cli ping

# Run integration tests
pytest tests/integration/persistence/redis/ -v

# Run integration tests with output
pytest tests/integration/persistence/redis/ -v -s
```

---

## Monitoring Redis During Tests

### View All Keys

```bash
redis-cli keys "test:*"
```

### Monitor Commands in Real-Time

```bash
redis-cli monitor
```

### Check Memory Usage

```bash
redis-cli INFO memory
```

### Check Connected Clients

```bash
redis-cli CLIENT LIST
```

### Clear Test Database

```bash
# Clear test database (db=1)
redis-cli -n 1 FLUSHDB

# Or clear all databases (use with caution)
redis-cli FLUSHALL
```

---

## Troubleshooting

### Issue: "Connection refused"

**Cause:** Redis server not running.

**Solution:**

```bash
# Check if Redis is running
redis-cli ping

# Start Redis
brew services start redis  # macOS
sudo systemctl start redis-server  # Linux
docker start redis-test  # Docker
```

### Issue: "MISCONF Redis is configured to save RDB snapshots"

**Cause:** Redis disk write error.

**Solution:**

```bash
redis-cli CONFIG SET stop-writes-on-bgsave-error no
```

### Issue: "Too many connections"

**Cause:** Connection pool exhausted.

**Solution:**

```bash
# Check max connections
redis-cli CONFIG GET maxclients

# Increase if needed
redis-cli CONFIG SET maxclients 10000
```

### Issue: High latency

**Cause:** Redis overloaded or network issues.

**Solution:**

```bash
# Check latency
redis-cli --latency

# Check slow queries
redis-cli SLOWLOG GET 10
```

---

## Expected Test Results Summary

| Test                  | Expected Result                      |
| --------------------- | ------------------------------------ |
| Client Initialization | ✅ Client initialized successfully   |
| Basic Operations      | ✅ Set, get, delete working          |
| TTL Management        | ✅ Keys expire after TTL             |
| Hash Operations       | ✅ Field-value pairs stored          |
| Counters              | ✅ Atomic increments working         |
| Distributed Locks     | ✅ Only one holder at a time         |
| Batch Operations      | ✅ Multiple keys in single call      |
| Health Checks         | ✅ Status "healthy", latency < 100ms |
| JSON Serialization    | ✅ Complex objects stored/retrieved  |
| Cleanup               | ✅ Connections closed gracefully     |

---

## Integration with Other Modules

### Interview Module Usage Example

```python
from app.persistence.redis import acquire_lock, set_value, get_value, hash_set

# Example: Exchange creation with lock (prevents race conditions)
def create_exchange_with_lock(submission_id, sequence_order):
    lock_key = f"interview:lock:{submission_id}:{sequence_order}"

    with acquire_lock(lock_key, timeout_seconds=10):
        # Check if exchange already exists (idempotency)
        # ... database check ...

        # Create exchange in database
        # ... database write ...

        # Update Redis session state
        session_key = f"interview:session:{submission_id}"
        hash_set(session_key, {
            "current_sequence": sequence_order,
            "status": "in_progress"
        }, ttl_seconds=3900)

    return "Exchange created successfully"
```

---

## Performance Benchmarks

Expected performance metrics (local Redis):

- **SET operation:** < 1ms
- **GET operation:** < 1ms
- **HSET (5 fields):** < 2ms
- **Lock acquisition:** < 5ms
- **Batch operations (100 keys):** < 10ms
- **Health check:** < 50ms

---

## Notes

- Always use `test:` prefix for test keys to avoid interfering with production data
- Clean up test keys after manual testing
- Use database 1 (`REDIS_DB=1`) for testing to isolate from development data
- Distributed locks automatically expire after timeout (prevents deadlocks)
- All operations include graceful error handling

---

**End of Human Testing Guide**
