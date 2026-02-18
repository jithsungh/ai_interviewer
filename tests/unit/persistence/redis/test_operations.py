"""
Unit Tests for Redis Operations

Tests key-value operations, TTL management, hash operations, counters, and batch operations.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import json

from app.persistence.redis.operations import (
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
    decrement_counter,
    batch_set,
    batch_get,
    batch_delete,
    execute_pipeline,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MagicMock()


class TestBasicOperations:
    """Test basic key-value operations."""
    
    def test_set_value_simple(self, mock_redis):
        """Test setting simple string value."""
        result = set_value("test_key", "test_value", client=mock_redis)
        
        assert result is True
        mock_redis.set.assert_called_once_with("test_key", "test_value")
    
    def test_set_value_with_ttl(self, mock_redis):
        """Test setting value with TTL."""
        result = set_value("test_key", "test_value", ttl_seconds=60, client=mock_redis)
        
        assert result is True
        mock_redis.setex.assert_called_once_with("test_key", 60, "test_value")
    
    def test_set_value_dict(self, mock_redis):
        """Test setting dictionary value (JSON-encoded)."""
        data = {"name": "test", "count": 42}
        result = set_value("test_key", data, client=mock_redis)
        
        assert result is True
        # Should JSON-encode dict
        expected_value = json.dumps(data)
        mock_redis.set.assert_called_once_with("test_key", expected_value)
    
    def test_get_value_exists(self, mock_redis):
        """Test getting existing value."""
        mock_redis.get.return_value = "test_value"
        
        result = get_value("test_key", client=mock_redis)
        
        assert result == "test_value"
        mock_redis.get.assert_called_once_with("test_key")
    
    def test_get_value_not_found(self, mock_redis):
        """Test getting non-existent key returns default."""
        mock_redis.get.return_value = None
        
        result = get_value("test_key", default="fallback", client=mock_redis)
        
        assert result == "fallback"
    
    def test_get_value_deserialize_json(self, mock_redis):
        """Test JSON deserialization."""
        data = {"name": "test", "count": 42}
        mock_redis.get.return_value = json.dumps(data)
        
        result = get_value("test_key", deserialize_json=True, client=mock_redis)
        
        assert result == data
    
    def test_delete_key(self, mock_redis):
        """Test deleting key."""
        mock_redis.delete.return_value = 1
        
        result = delete_key("test_key", client=mock_redis)
        
        assert result == 1
        mock_redis.delete.assert_called_once_with("test_key")
    
    def test_exists_true(self, mock_redis):
        """Test key exists."""
        mock_redis.exists.return_value = 1
        
        result = exists("test_key", client=mock_redis)
        
        assert result is True
        mock_redis.exists.assert_called_once_with("test_key")
    
    def test_exists_false(self, mock_redis):
        """Test key does not exist."""
        mock_redis.exists.return_value = 0
        
        result = exists("test_key", client=mock_redis)
        
        assert result is False


class TestTTLManagement:
    """Test TTL operations."""
    
    def test_set_ttl(self, mock_redis):
        """Test setting TTL on existing key."""
        mock_redis.expire.return_value = True
        
        result = set_ttl("test_key", 60, client=mock_redis)
        
        assert result is True
        mock_redis.expire.assert_called_once_with("test_key", 60)
    
    def test_get_ttl_existing(self, mock_redis):
        """Test getting TTL for key with expiration."""
        mock_redis.ttl.return_value = 120
        
        result = get_ttl("test_key", client=mock_redis)
        
        assert result == 120
        mock_redis.ttl.assert_called_once_with("test_key")
    
    def test_get_ttl_no_expiration(self, mock_redis):
        """Test getting TTL for key without expiration."""
        mock_redis.ttl.return_value = -1
        
        result = get_ttl("test_key", client=mock_redis)
        
        assert result == -1
    
    def test_get_ttl_key_not_found(self, mock_redis):
        """Test getting TTL for non-existent key."""
        mock_redis.ttl.return_value = -2
        
        result = get_ttl("test_key", client=mock_redis)
        
        assert result == -2


class TestHashOperations:
    """Test hash (field-value) operations."""
    
    def test_hash_set(self, mock_redis):
        """Test setting hash fields."""
        mapping = {"field1": "value1", "field2": "value2"}
        
        result = hash_set("test_hash", mapping, client=mock_redis)
        
        assert result is True
        mock_redis.hset.assert_called_once()
        call_kwargs = mock_redis.hset.call_args[1]
        assert call_kwargs["mapping"] == mapping
    
    def test_hash_set_with_ttl(self, mock_redis):
        """Test setting hash with TTL."""
        mapping = {"field1": "value1"}
        
        result = hash_set("test_hash", mapping, ttl_seconds=60, client=mock_redis)
        
        assert result is True
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once_with("test_hash", 60)
    
    def test_hash_get(self, mock_redis):
        """Test getting single hash field."""
        mock_redis.hget.return_value = "value1"
        
        result = hash_get("test_hash", "field1", client=mock_redis)
        
        assert result == "value1"
        mock_redis.hget.assert_called_once_with("test_hash", "field1")
    
    def test_hash_get_not_found(self, mock_redis):
        """Test getting non-existent field returns default."""
        mock_redis.hget.return_value = None
        
        result = hash_get("test_hash", "field1", default="fallback", client=mock_redis)
        
        assert result == "fallback"
    
    def test_hash_get_all(self, mock_redis):
        """Test getting all hash fields."""
        mock_redis.hgetall.return_value = {"field1": "value1", "field2": "value2"}
        
        result = hash_get_all("test_hash", client=mock_redis)
        
        assert result == {"field1": "value1", "field2": "value2"}
        mock_redis.hgetall.assert_called_once_with("test_hash")


class TestCounters:
    """Test counter operations."""
    
    def test_increment_counter(self, mock_redis):
        """Test incrementing counter."""
        mock_redis.incr.return_value = 5
        
        result = increment_counter("test_counter", amount=1, client=mock_redis)
        
        assert result == 5
        mock_redis.incr.assert_called_once_with("test_counter", 1)
    
    def test_increment_counter_with_ttl(self, mock_redis):
        """Test incrementing counter with TTL on first increment."""
        mock_redis.eval.return_value = 1  # Lua script returns incremented value
        
        result = increment_counter("test_counter", amount=1, ttl_seconds=60, client=mock_redis)
        
        assert result == 1
        # Verify Lua script was called (atomic INCR + EXPIRE)
        mock_redis.eval.assert_called_once()
    
    def test_increment_counter_no_ttl_after_first(self, mock_redis):
        """Test TTL not set on subsequent increments."""
        mock_redis.eval.return_value = 5  # Lua script returns value (not first increment)
        
        result = increment_counter("test_counter", amount=1, ttl_seconds=60, client=mock_redis)
        
        assert result == 5
        # Lua script handles conditional TTL (only sets on first increment)
        mock_redis.eval.assert_called_once()
    
    def test_decrement_counter(self, mock_redis):
        """Test decrementing counter."""
        mock_redis.decr.return_value = 3
        
        result = decrement_counter("test_counter", amount=1, client=mock_redis)
        
        assert result == 3
        mock_redis.decr.assert_called_once_with("test_counter", 1)


class TestBatchOperations:
    """Test batch operations."""
    
    def test_batch_set(self, mock_redis):
        """Test setting multiple keys."""
        data = {"key1": "value1", "key2": "value2"}
        
        result = batch_set(data, client=mock_redis)
        
        assert result is True
        mock_redis.mset.assert_called_once_with(data)
    
    def test_batch_get(self, mock_redis):
        """Test getting multiple keys."""
        mock_redis.mget.return_value = ["value1", "value2", None]
        
        result = batch_get(["key1", "key2", "key3"], client=mock_redis)
        
        assert result == {"key1": "value1", "key2": "value2", "key3": None}
        mock_redis.mget.assert_called_once_with(["key1", "key2", "key3"])
    
    def test_batch_delete(self, mock_redis):
        """Test deleting multiple keys."""
        mock_redis.delete.return_value = 2
        
        result = batch_delete(["key1", "key2"], client=mock_redis)
        
        assert result == 2
        mock_redis.delete.assert_called_once_with("key1", "key2")


class TestPipeline:
    """Test pipeline operations."""
    
    def test_execute_pipeline(self, mock_redis):
        """Test executing multiple operations in pipeline."""
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [True, "value1", 1]
        mock_redis.pipeline.return_value = mock_pipe
        
        operations = [
            ("SET", ("key1", "value1")),
            ("GET", ("key2",)),
            ("INCR", ("counter",)),
        ]
        
        results = execute_pipeline(operations, client=mock_redis)
        
        assert results == [True, "value1", 1]
        mock_redis.pipeline.assert_called_once()
        mock_pipe.execute.assert_called_once()
    
    def test_execute_pipeline_rejects_disallowed_command(self, mock_redis):
        """Test that pipeline rejects commands not in allowlist."""
        operations = [
            ("SET", ("key1", "value1")),
            ("FLUSHDB", ()),  # Dangerous command not in allowlist
        ]
        
        with pytest.raises(ValueError) as excinfo:
            execute_pipeline(operations, client=mock_redis)
        
        assert "flushdb" in str(excinfo.value).lower()
        assert "not in the allowlist" in str(excinfo.value)
        # Ensure pipeline was never created since validation happens first
        mock_redis.pipeline.assert_not_called()
    
    def test_execute_pipeline_rejects_eval_command(self, mock_redis):
        """Test that pipeline rejects EVAL command (code execution)."""
        operations = [
            ("EVAL", ("return redis.call('FLUSHALL')", 0)),
        ]
        
        with pytest.raises(ValueError) as excinfo:
            execute_pipeline(operations, client=mock_redis)
        
        assert "eval" in str(excinfo.value).lower()
        mock_redis.pipeline.assert_not_called()
    
    def test_execute_pipeline_case_insensitive_validation(self, mock_redis):
        """Test that command validation is case-insensitive."""
        mock_pipe = MagicMock()
        mock_pipe.execute.return_value = [True, "value2", 2]
        mock_redis.pipeline.return_value = mock_pipe
        
        # Mixed case commands should work
        operations = [
            ("set", ("key1", "value1")),
            ("GET", ("key2",)),
            ("InCr", ("counter",)),
        ]
        
        results = execute_pipeline(operations, client=mock_redis)
        assert results == [True, "value2", 2]
        assert len(results) == 3
