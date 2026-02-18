"""
Unit Tests for Redis Distributed Locks

Tests lock acquisition, release, retry logic, and safety guarantees.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import time

from app.persistence.redis.locks import (
    acquire_lock,
    try_acquire_lock,
    release_lock,
    is_locked,
    get_lock_ttl,
    create_interview_lock_key,
    create_session_lock_key,
    create_rate_limit_lock_key,
    LockAcquisitionError,
    LockReleaseError,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    return MagicMock()


class TestLockAcquisition:
    """Test lock acquisition."""
    
    def test_acquire_lock_success(self, mock_redis):
        """Test acquiring lock successfully."""
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1  # Lock released
        
        with acquire_lock("test_lock", timeout_seconds=10, client=mock_redis):
            # Lock held here
            pass
        
        # Verify lock was acquired with SET NX
        assert mock_redis.set.call_count >= 1
        call_kwargs = mock_redis.set.call_args[1]
        assert call_kwargs["nx"] is True
        assert call_kwargs["ex"] == 10
        
        # Verify lock was released
        mock_redis.eval.assert_called_once()
    
    @patch('app.persistence.redis.locks.time.sleep')
    def test_acquire_lock_retry_success(self, mock_sleep, mock_redis):
        """Test acquiring lock after retry."""
        # First attempt fails, second succeeds
        mock_redis.set.side_effect = [False, True]
        mock_redis.eval.return_value = 1
        
        with acquire_lock("test_lock", timeout_seconds=10, retry_interval=0.1, client=mock_redis):
            pass
        
        # Should have retried
        assert mock_redis.set.call_count == 2
        assert mock_sleep.call_count >= 1
    
    @patch('app.persistence.redis.locks.time.sleep')
    @patch('app.persistence.redis.locks.time.time')
    def test_acquire_lock_timeout(self, mock_time, mock_sleep, mock_redis):
        """Test lock acquisition timeout."""
        # Simulate time passing - need enough values for: start_time, while checks, elapsed
        mock_time.side_effect = [0, 0.1, 0.2, 0.3, 11, 11, 11]  # Exceeds 10s timeout
        
        # Lock never acquired
        mock_redis.set.return_value = False
        
        with pytest.raises(LockAcquisitionError) as exc_info:
            with acquire_lock("test_lock", timeout_seconds=10, client=mock_redis):
                pass
        
        assert "test_lock" in str(exc_info.value)
        assert exc_info.value.status_code == 409
    
    def test_acquire_lock_release_on_exception(self, mock_redis):
        """Test lock is released even when exception occurs."""
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        with pytest.raises(ValueError):
            with acquire_lock("test_lock", timeout_seconds=10, client=mock_redis):
                raise ValueError("Test error")
        
        # Lock should still be released
        mock_redis.eval.assert_called_once()
    
    def test_acquire_lock_not_released_if_not_acquired(self, mock_redis):
        """Test lock release not attempted if never acquired."""
        mock_redis.set.return_value = False
        
        # Mock time to immediately timeout - need enough values for all calls
        with patch('app.persistence.redis.locks.time.time') as mock_time:
            mock_time.side_effect = [0, 11, 11, 11]  # Start, check (immediate timeout), elapsed, extra
            
            with pytest.raises(LockAcquisitionError):
                with acquire_lock("test_lock", timeout_seconds=10, client=mock_redis):
                    pass
            
            # Release should not be called
            mock_redis.eval.assert_not_called()


class TestTryAcquireLock:
    """Test non-blocking lock acquisition."""
    
    def test_try_acquire_lock_success(self, mock_redis):
        """Test non-blocking lock acquisition succeeds."""
        mock_redis.set.return_value = True
        
        lock_value = try_acquire_lock("test_lock", timeout_seconds=10, client=mock_redis)
        
        assert lock_value is not None
        assert isinstance(lock_value, str)
        
        # Verify SET NX called
        call_kwargs = mock_redis.set.call_args[1]
        assert call_kwargs["nx"] is True
        assert call_kwargs["ex"] == 10
    
    def test_try_acquire_lock_fails(self, mock_redis):
        """Test non-blocking lock acquisition fails."""
        mock_redis.set.return_value = False
        
        lock_value = try_acquire_lock("test_lock", timeout_seconds=10, client=mock_redis)
        
        assert lock_value is None


class TestReleaseLock:
    """Test lock release."""
    
    def test_release_lock_success(self, mock_redis):
        """Test releasing lock successfully."""
        mock_redis.eval.return_value = 1  # Lock deleted
        
        result = release_lock("test_lock", "lock_value_uuid", client=mock_redis)
        
        assert result is True
        mock_redis.eval.assert_called_once()
    
    def test_release_lock_not_owned(self, mock_redis):
        """Test releasing lock not owned (already expired)."""
        mock_redis.eval.return_value = 0  # Lock not deleted
        
        result = release_lock("test_lock", "lock_value_uuid", client=mock_redis)
        
        assert result is False
    
    def test_release_lock_error(self, mock_redis):
        """Test release lock handles Redis errors."""
        from redis.exceptions import RedisError
        mock_redis.eval.side_effect = RedisError("Redis error")
        
        with pytest.raises(LockReleaseError) as exc_info:
            release_lock("test_lock", "lock_value_uuid", client=mock_redis)
        
        assert "test_lock" in str(exc_info.value)


class TestLockHelpers:
    """Test lock helper functions."""
    
    def test_is_locked_true(self, mock_redis):
        """Test checking if lock is held."""
        mock_redis.exists.return_value = 1
        
        result = is_locked("test_lock", client=mock_redis)
        
        assert result is True
        mock_redis.exists.assert_called_once_with("test_lock")
    
    def test_is_locked_false(self, mock_redis):
        """Test checking if lock is not held."""
        mock_redis.exists.return_value = 0
        
        result = is_locked("test_lock", client=mock_redis)
        
        assert result is False
    
    def test_get_lock_ttl(self, mock_redis):
        """Test getting lock TTL."""
        mock_redis.ttl.return_value = 5
        
        result = get_lock_ttl("test_lock", client=mock_redis)
        
        assert result == 5
        mock_redis.ttl.assert_called_once_with("test_lock")


class TestLockKeyHelpers:
    """Test lock key pattern helpers."""
    
    def test_create_interview_lock_key(self):
        """Test creating interview lock key."""
        key = create_interview_lock_key(12345, 5)
        
        assert key == "interview:lock:12345:5"
    
    def test_create_session_lock_key(self):
        """Test creating session lock key."""
        key = create_session_lock_key(12345)
        
        assert key == "interview:session:lock:12345"
    
    def test_create_rate_limit_lock_key(self):
        """Test creating rate limit lock key."""
        key = create_rate_limit_lock_key(456, "start_interview")
        
        assert key == "rate_limit:lock:456:start_interview"


class TestLockSafety:
    """Test lock safety guarantees."""
    
    def test_lock_uses_unique_value(self, mock_redis):
        """Test each lock uses unique UUID."""
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        with acquire_lock("test_lock", timeout_seconds=10, client=mock_redis):
            pass
        
        # Verify unique UUID was used
        set_call = mock_redis.set.call_args
        lock_value = set_call[0][1]
        
        # UUID format check (36 chars with hyphens)
        assert len(lock_value) == 36
        assert lock_value.count('-') == 4
    
    def test_lock_release_script_safety(self, mock_redis):
        """Test lock release uses Lua script for atomicity."""
        mock_redis.set.return_value = True
        mock_redis.eval.return_value = 1
        
        with acquire_lock("test_lock", timeout_seconds=10, client=mock_redis):
            pass
        
        # Verify Lua script was used for release
        eval_call = mock_redis.eval.call_args
        lua_script = eval_call[0][0]
        
        # Should check if lock value matches before deleting
        assert "GET" in lua_script
        assert "DEL" in lua_script
        assert "KEYS[1]" in lua_script
        assert "ARGV[1]" in lua_script
