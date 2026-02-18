"""
Integration Tests for Redis Persistence

Tests Redis operations against actual Redis instance.
Requires Redis server to be running (configured via REDIS_URL env var).

Run with: pytest tests/integration/persistence/redis/test_redis_integration.py
"""

import pytest
import os
import time
from typing import Generator

from app.config.settings import RedisSettings
from app.persistence.redis import (
    init_redis_client,
    get_redis_client,
    cleanup_redis,
    set_value,
    get_value,
    delete_key,
    exists,
    set_ttl,
    get_ttl,
    hash_set,
    hash_get,
    hash_get_all,
    increment_counter,
    batch_set,
    batch_get,
    acquire_lock,
    try_acquire_lock,
    release_lock,
    is_locked,
    check_redis_health,
    check_redis_connectivity,
    LockAcquisitionError,
)


@pytest.fixture(scope="module")
def redis_config() -> RedisSettings:
    """Redis configuration for integration tests."""
    # Use test database (db=1) to avoid interfering with dev data
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    
    return RedisSettings(
        redis_url=redis_url,
        redis_db=1,  # Test database
        redis_password=None,
        redis_max_connections=10,
        redis_connection_timeout=5,
        redis_socket_timeout=3,
        redis_retry_on_timeout=True,
        redis_max_retries=3,
        redis_decode_responses=True,
        redis_session_ttl=3600,
        redis_lock_timeout=10,
        redis_health_check_interval=60,
    )


@pytest.fixture(scope="module")
def redis_client(redis_config):
    """Initialize Redis client for tests."""
    try:
        client = init_redis_client(redis_config)
        yield client
    finally:
        # Cleanup all test keys
        test_keys = client.keys("test:*")
        if test_keys:
            client.delete(*test_keys)
        cleanup_redis()


@pytest.fixture(autouse=True)
def cleanup_test_keys(redis_client):
    """Clean up test keys after each test."""
    yield
    # Delete all test keys
    test_keys = redis_client.keys("test:*")
    if test_keys:
        redis_client.delete(*test_keys)


class TestBasicOperations:
    """Test basic Redis operations."""
    
    def test_set_and_get_value(self, redis_client):
        """Test setting and getting value."""
        set_value("test:key1", "value1", client=redis_client)
        
        result = get_value("test:key1", client=redis_client)
        
        assert result == "value1"
    
    def test_set_with_ttl(self, redis_client):
        """Test setting value with TTL."""
        set_value("test:ttl_key", "expires", ttl_seconds=2, client=redis_client)
        
        # Should exist initially
        assert get_value("test:ttl_key", client=redis_client) == "expires"
        
        # Wait for expiration
        time.sleep(3)
        
        # Should be gone
        assert get_value("test:ttl_key", default="not_found", client=redis_client) == "not_found"
    
    def test_delete_key(self, redis_client):
        """Test deleting key."""
        set_value("test:delete_key", "to_delete", client=redis_client)
        
        # Verify exists
        assert exists("test:delete_key", client=redis_client) is True
        
        # Delete
        delete_key("test:delete_key", client=redis_client)
        
        # Verify deleted
        assert exists("test:delete_key", client=redis_client) is False
    
    def test_json_serialization(self, redis_client):
        """Test JSON serialization of complex objects."""
        data = {"name": "test", "count": 42, "items": [1, 2, 3]}
        
        set_value("test:json_key", data, client=redis_client)
        
        result = get_value("test:json_key", deserialize_json=True, client=redis_client)
        
        assert result == data


class TestHashOperations:
    """Test hash operations."""
    
    def test_hash_operations(self, redis_client):
        """Test hash set and get operations."""
        mapping = {
            "field1": "value1",
            "field2": "value2",
            "field3": "value3",
        }
        
        hash_set("test:hash1", mapping, client=redis_client)
        
        # Get single field
        assert hash_get("test:hash1", "field1", client=redis_client) == "value1"
        
        # Get all fields
        result = hash_get_all("test:hash1", client=redis_client)
        assert result == mapping
    
    def test_hash_with_ttl(self, redis_client):
        """Test hash with TTL."""
        hash_set("test:hash_ttl", {"field1": "value1"}, ttl_seconds=2, client=redis_client)
        
        # Should exist
        assert hash_get("test:hash_ttl", "field1", client=redis_client) == "value1"
        
        # Wait for expiration
        time.sleep(3)
        
        # Should be gone
        assert hash_get("test:hash_ttl", "field1", default="gone", client=redis_client) == "gone"


class TestCounters:
    """Test counter operations."""
    
    def test_increment_counter(self, redis_client):
        """Test counter increment."""
        # First increment
        result1 = increment_counter("test:counter1", client=redis_client)
        assert result1 == 1
        
        # Second increment
        result2 = increment_counter("test:counter1", client=redis_client)
        assert result2 == 2
        
        # Increment by 5
        result3 = increment_counter("test:counter1", amount=5, client=redis_client)
        assert result3 == 7
    
    def test_counter_with_ttl(self, redis_client):
        """Test counter with TTL."""
        # First increment sets TTL
        increment_counter("test:counter_ttl", ttl_seconds=2, client=redis_client)
        
        # Verify TTL is set
        ttl = get_ttl("test:counter_ttl", client=redis_client)
        assert ttl > 0 and ttl <= 2
        
        # Wait for expiration
        time.sleep(3)
        
        # Counter should be gone
        assert exists("test:counter_ttl", client=redis_client) is False


class TestBatchOperations:
    """Test batch operations."""
    
    def test_batch_operations(self, redis_client):
        """Test batch set and get."""
        data = {
            "test:batch1": "value1",
            "test:batch2": "value2",
            "test:batch3": "value3",
        }
        
        # Batch set
        batch_set(data, client=redis_client)
        
        # Batch get
        keys = list(data.keys())
        result = batch_get(keys, client=redis_client)
        
        assert result["test:batch1"] == "value1"
        assert result["test:batch2"] == "value2"
        assert result["test:batch3"] == "value3"


class TestDistributedLocks:
    """Test distributed locking."""
    
    def test_acquire_and_release_lock(self, redis_client):
        """Test acquiring and releasing lock."""
        lock_key = "test:lock1"
        
        # Acquire lock
        with acquire_lock(lock_key, timeout_seconds=5, client=redis_client):
            # Lock should be held
            assert is_locked(lock_key, client=redis_client) is True
        
        # Lock should be released
        assert is_locked(lock_key, client=redis_client) is False
    
    def test_lock_prevents_concurrent_access(self, redis_client):
        """Test lock prevents concurrent access."""
        lock_key = "test:lock2"
        
        # First lock acquired
        with acquire_lock(lock_key, timeout_seconds=5, client=redis_client):
            # Second lock should fail immediately
            with pytest.raises(LockAcquisitionError):
                with acquire_lock(lock_key, timeout_seconds=1, retry_interval=0.1, client=redis_client):
                    pass
    
    def test_try_acquire_lock(self, redis_client):
        """Test non-blocking lock acquisition."""
        lock_key = "test:lock3"
        
        # First acquisition succeeds
        lock_value1 = try_acquire_lock(lock_key, timeout_seconds=5, client=redis_client)
        assert lock_value1 is not None
        
        # Second acquisition fails (lock held)
        lock_value2 = try_acquire_lock(lock_key, timeout_seconds=5, client=redis_client)
        assert lock_value2 is None
        
        # Release manually
        release_lock(lock_key, lock_value1, client=redis_client)
        
        # Third acquisition succeeds (lock released)
        lock_value3 = try_acquire_lock(lock_key, timeout_seconds=5, client=redis_client)
        assert lock_value3 is not None
        
        # Cleanup
        release_lock(lock_key, lock_value3, client=redis_client)
    
    def test_lock_expires_automatically(self, redis_client):
        """Test lock expires after timeout."""
        lock_key = "test:lock4"
        
        # Acquire lock with short timeout
        lock_value = try_acquire_lock(lock_key, timeout_seconds=2, client=redis_client)
        assert lock_value is not None
        assert is_locked(lock_key, client=redis_client) is True
        
        # Wait for expiration
        time.sleep(3)
        
        # Lock should be released automatically
        assert is_locked(lock_key, client=redis_client) is False
        
        # Should be able to acquire again
        lock_value2 = try_acquire_lock(lock_key, timeout_seconds=2, client=redis_client)
        assert lock_value2 is not None
        
        # Cleanup
        release_lock(lock_key, lock_value2, client=redis_client)


class TestHealthChecks:
    """Test health check functionality."""
    
    def test_connectivity_check(self, redis_client):
        """Test Redis connectivity check."""
        result = check_redis_connectivity(redis_client)
        
        assert result is True
    
    def test_health_check(self, redis_client):
        """Test comprehensive health check."""
        result = check_redis_health(redis_client)
        
        assert result["status"] in ["healthy", "degraded"]
        assert result["latency_ms"] is not None
        assert result["latency_ms"] < 1000  # Should be fast
        assert result["info"] is not None
        assert "connected_clients" in result["info"]
        assert "redis_version" in result["info"]


class TestRaceConditions:
    """Test race condition prevention."""
    
    def test_idempotent_lock_acquisition(self, redis_client):
        """Test lock acquisition is idempotent."""
        lock_key = "test:lock_race"
        
        # Acquire lock
        with acquire_lock(lock_key, timeout_seconds=5, client=redis_client):
            # Attempt to acquire same lock (should fail)
            with pytest.raises(LockAcquisitionError):
                with acquire_lock(lock_key, timeout_seconds=1, retry_interval=0.1, client=redis_client):
                    pass
        
        # Lock released, should be able to acquire again
        with acquire_lock(lock_key, timeout_seconds=5, client=redis_client):
            assert is_locked(lock_key, client=redis_client) is True


class TestGracefulDegradation:
    """Test graceful degradation on errors."""
    
    def test_get_with_fallback(self, redis_client):
        """Test get operation returns fallback for missing keys."""
        result = get_value("test:nonexistent", default="fallback", client=redis_client)
        
        assert result == "fallback"


@pytest.mark.skip(reason="Requires Redis cluster setup")
class TestFailover:
    """Test Redis failover scenarios (requires cluster setup)."""
    
    def test_reconnection_after_restart(self):
        """Test client reconnects after Redis restart."""
        # This would require stopping and restarting Redis
        pass
