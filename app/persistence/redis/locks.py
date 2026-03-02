"""
Redis Distributed Locks

Safe distributed locking implementation to prevent race conditions.
Critical for: exchange creation, state transitions, concurrent operations.
"""

import logging
import time
import uuid
from contextlib import contextmanager
from typing import Optional

from redis import Redis
from redis.exceptions import RedisError

from .client import get_redis_client
from app.shared.errors import ApplicationError

logger = logging.getLogger(__name__)


class LockAcquisitionError(ApplicationError):
    """Failed to acquire distributed lock within timeout"""
    def __init__(self, lock_key: str, timeout: int, **kwargs):
        message = f"Failed to acquire lock '{lock_key}' within {timeout}s"
        super().__init__(message, status_code=409, error_code="LOCK_ACQUISITION_FAILED", **kwargs)


class LockReleaseError(ApplicationError):
    """Failed to release distributed lock"""
    def __init__(self, lock_key: str, **kwargs):
        message = f"Failed to release lock '{lock_key}'"
        super().__init__(message, status_code=500, error_code="LOCK_RELEASE_FAILED", **kwargs)


@contextmanager
def acquire_lock(
    lock_key: str,
    timeout_seconds: int = 10,
    retry_interval: float = 0.1,
    client: Optional[Redis] = None
):
    """
    Acquire distributed lock with automatic release.
    
    Usage:
        with acquire_lock("interview:lock:12345:5", timeout_seconds=10):
            # Critical section (only one process executes)
            create_exchange(...)
    
    Features:
    - Automatic retry with configurable interval
    - Expiration timeout (prevents deadlock if process crashes)
    - Safe release using Lua script (only holder can release)
    - Context manager ensures release even on exception
    
    Args:
        lock_key: Unique lock identifier (e.g., "interview:lock:{id}:{seq}")
        timeout_seconds: Lock expiration time (prevents deadlock)
        retry_interval: Time between retry attempts (seconds)
        client: Redis client (uses global if None)
        
    Yields:
        Lock is held during yield
        
    Raises:
        LockAcquisitionError: Failed to acquire lock within timeout
    """
    if client is None:
        client = get_redis_client()
    
    # Unique identifier for this lock holder
    lock_value = str(uuid.uuid4())
    acquired = False
    start_time = time.perf_counter()
    
    try:
        # Try to acquire lock with retry
        while time.perf_counter() - start_time < timeout_seconds:
            # SET NX (set if not exists) with expiration
            acquired = client.set(
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
            elapsed = time.perf_counter() - start_time
            logger.warning(f"Lock acquisition timeout: {lock_key} ({elapsed:.2f}s)")
            raise LockAcquisitionError(lock_key, timeout_seconds)
        
        # Critical section executes here
        yield
        
    finally:
        # Release lock (only if we hold it)
        if acquired:
            try:
                # Lua script ensures we only delete our own lock
                release_script = """
                if redis.call("GET", KEYS[1]) == ARGV[1] then
                    return redis.call("DEL", KEYS[1])
                else
                    return 0
                end
                """
                result = client.eval(release_script, 1, lock_key, lock_value)
                
                if result == 1:
                    logger.debug(f"Lock released: {lock_key}")
                else:
                    logger.warning(f"Lock already expired or released: {lock_key}")
                    
            except RedisError as e:
                logger.error(f"Failed to release lock '{lock_key}': {e}")
                # Don't raise - lock will expire automatically


def try_acquire_lock(
    lock_key: str,
    timeout_seconds: int = 10,
    client: Optional[Redis] = None
) -> Optional[str]:
    """
    Try to acquire lock once (non-blocking).
    
    Use this for non-critical operations where failure is acceptable.
    
    Args:
        lock_key: Unique lock identifier
        timeout_seconds: Lock expiration time
        client: Redis client (uses global if None)
        
    Returns:
        Lock value (UUID) if acquired, None if lock held by another process
    """
    if client is None:
        client = get_redis_client()
    
    lock_value = str(uuid.uuid4())
    
    try:
        acquired = client.set(
            lock_key,
            lock_value,
            nx=True,
            ex=timeout_seconds
        )
        
        if acquired:
            logger.debug(f"Lock acquired (non-blocking): {lock_key}")
            return lock_value
        else:
            logger.debug(f"Lock held by another process: {lock_key}")
            return None
            
    except RedisError as e:
        logger.error(f"Lock acquisition error: {e}")
        return None


def release_lock(
    lock_key: str,
    lock_value: str,
    client: Optional[Redis] = None
) -> bool:
    """
    Manually release lock.
    
    Only use if you acquired lock with try_acquire_lock().
    Prefer acquire_lock() context manager for automatic release.
    
    Args:
        lock_key: Lock identifier
        lock_value: Lock value (UUID) returned by try_acquire_lock()
        client: Redis client (uses global if None)
        
    Returns:
        True if lock released successfully, False if lock not owned
        
    Raises:
        LockReleaseError: If Redis operation fails
    """
    if client is None:
        client = get_redis_client()
    
    try:
        # Lua script ensures we only delete our own lock
        release_script = """
        if redis.call("GET", KEYS[1]) == ARGV[1] then
            return redis.call("DEL", KEYS[1])
        else
            return 0
        end
        """
        result = client.eval(release_script, 1, lock_key, lock_value)
        
        if result == 1:
            logger.debug(f"Lock released manually: {lock_key}")
            return True
        else:
            logger.warning(f"Lock not owned or expired: {lock_key}")
            return False
            
    except RedisError as e:
        logger.error(f"Failed to release lock '{lock_key}': {e}")
        raise LockReleaseError(lock_key) from e


def is_locked(
    lock_key: str,
    client: Optional[Redis] = None
) -> bool:
    """
    Check if lock is currently held.
    
    Args:
        lock_key: Lock identifier
        client: Redis client (uses global if None)
        
    Returns:
        True if lock is held, False otherwise
    """
    if client is None:
        client = get_redis_client()
    
    try:
        return client.exists(lock_key) > 0
    except RedisError as e:
        logger.error(f"Failed to check lock status for '{lock_key}': {e}")
        return False


def get_lock_ttl(
    lock_key: str,
    client: Optional[Redis] = None
) -> int:
    """
    Get remaining TTL for lock.
    
    Args:
        lock_key: Lock identifier
        client: Redis client (uses global if None)
        
    Returns:
        Remaining seconds (-1 if no expiry, -2 if lock not held)
    """
    if client is None:
        client = get_redis_client()
    
    try:
        ttl = client.ttl(lock_key)
        return ttl
    except RedisError as e:
        logger.error(f"Failed to get lock TTL for '{lock_key}': {e}")
        return -2


# ==================
# Key Patterns
# ==================

def create_interview_lock_key(submission_id: int, sequence_order: int) -> str:
    """
    Create lock key for interview exchange creation.
    
    Pattern: interview:lock:{submission_id}:{sequence_order}
    
    Args:
        submission_id: Interview submission ID
        sequence_order: Exchange sequence number
        
    Returns:
        Lock key string
    """
    return f"interview:lock:{submission_id}:{sequence_order}"


def create_session_lock_key(submission_id: int) -> str:
    """
    Create lock key for interview session operations.
    
    Pattern: interview:session:lock:{submission_id}
    
    Args:
        submission_id: Interview submission ID
        
    Returns:
        Lock key string
    """
    return f"interview:session:lock:{submission_id}"


def create_rate_limit_lock_key(user_id: int, action: str) -> str:
    """
    Create lock key for rate limiting operations.
    
    Pattern: rate_limit:lock:{user_id}:{action}
    
    Args:
        user_id: User ID
        action: Action being rate-limited
        
    Returns:
        Lock key string
    """
    return f"rate_limit:lock:{user_id}:{action}"
