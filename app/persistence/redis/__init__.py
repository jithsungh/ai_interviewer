"""
Redis Persistence Layer

Pure infrastructure module for Redis connectivity and caching.
Provides client initialization, key-value operations, distributed locks, and health checks.

⚠️ CONTAINS ZERO BUSINESS LOGIC ⚠️

Public API:
- init_redis_client(): Initialize Redis client with connection pooling
- get_redis_client(): Get initialized client (dependency injection)
- cleanup_redis(): Graceful shutdown cleanup
- check_redis_health(): Health check for monitoring

Operations:
- set_value(), get_value(), delete_key(), exists()
- hash_set(), hash_get(), hash_get_all()
- increment_counter(), decrement_counter()
- batch_set(), batch_get(), batch_delete()
- set_ttl(), get_ttl()

Distributed Locks (CRITICAL for race condition prevention):
- acquire_lock(): Context manager for safe locking
- try_acquire_lock(): Non-blocking lock acquisition
- release_lock(): Manual lock release
- is_locked(), get_lock_ttl()

Key Pattern Helpers:
- create_interview_lock_key()
- create_session_lock_key()
- create_rate_limit_lock_key()
"""

from .client import (
    init_redis_client,
    get_redis_client,
    cleanup_redis,
    RedisClientError,
)

from .operations import (
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

from .locks import (
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

from .health import (
    check_redis_health,
    check_redis_connectivity,
    get_pool_status,
    log_redis_stats,
    get_health_check_endpoint_response,
    HealthStatus,
)

__all__ = [
    # Client management
    "init_redis_client",
    "get_redis_client",
    "cleanup_redis",
    
    # Exceptions
    "RedisClientError",
    "LockAcquisitionError",
    "LockReleaseError",
    
    # Basic operations
    "set_value",
    "get_value",
    "delete_key",
    "exists",
    
    # TTL management
    "set_ttl",
    "get_ttl",
    
    # Hash operations
    "hash_set",
    "hash_get",
    "hash_get_all",
    
    # Counters
    "increment_counter",
    "decrement_counter",
    
    # Batch operations
    "batch_set",
    "batch_get",
    "batch_delete",
    "execute_pipeline",
    
    # Distributed locks
    "acquire_lock",
    "try_acquire_lock",
    "release_lock",
    "is_locked",
    "get_lock_ttl",
    
    # Lock key helpers
    "create_interview_lock_key",
    "create_session_lock_key",
    "create_rate_limit_lock_key",
    
    # Health checks
    "check_redis_health",
    "check_redis_connectivity",
    "get_pool_status",
    "log_redis_stats",
    "get_health_check_endpoint_response",
    "HealthStatus",
    
    # Convenience initialization
    "init_redis",
]


def init_redis(config):
    """
    Initialize Redis infrastructure.
    
    Call this once during application startup.
    
    Args:
        config: RedisSettings instance from app.config.settings
        
    Returns:
        Initialized Redis client
        
    Example:
        from app.config.settings import settings
        from app.persistence.redis import init_redis
        
        redis_client = init_redis(settings.redis)
    """
    from app.config.settings import RedisSettings
    
    if not isinstance(config, RedisSettings):
        raise TypeError("config must be a RedisSettings instance")
    
    client = init_redis_client(config)
    
    return client
