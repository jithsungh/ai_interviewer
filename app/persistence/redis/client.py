"""
Redis Client Initialization

Handles Redis client creation with connection pooling, retry logic,
and graceful error handling.
"""

import time
import logging
import atexit
from typing import Optional

import redis
from redis import ConnectionPool, Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config.settings import RedisSettings
from app.shared.errors import ApplicationError

logger = logging.getLogger(__name__)

# Infrastructure constants
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2

# Global client instance (initialized once)
_client: Optional[Redis] = None
_pool: Optional[ConnectionPool] = None


class RedisClientError(ApplicationError):
    """Redis client initialization or connection failed"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=503, error_code="REDIS_UNAVAILABLE", **kwargs)


def create_redis_client(config: RedisSettings) -> Redis:
    """
    Create Redis client with connection pooling and retry logic.
    
    Configuration:
    - Connection pooling (max_connections)
    - Connection timeout (prevent hanging connections)
    - Socket timeout (prevent slow operations)
    - Retry on timeout (automatic retry for transient failures)
    - Decode responses (return strings instead of bytes)
    
    Args:
        config: RedisSettings instance from app.config.settings
        
    Returns:
        Redis client instance
        
    Raises:
        RedisClientError: If all connection retries fail
    """
    logger.info("Initializing Redis client...")
    
    # Attempt connection with retry logic
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Creating Redis client (attempt {attempt}/{MAX_RETRIES})"
            )
            
            # Create connection pool
            pool = ConnectionPool.from_url(
                config.redis_url,
                max_connections=config.redis_max_connections,
                socket_connect_timeout=config.redis_connection_timeout,
                socket_timeout=config.redis_socket_timeout,
                retry_on_timeout=config.redis_retry_on_timeout,
                decode_responses=config.redis_decode_responses,
                # Add password if provided
                password=config.redis_password,
                db=config.redis_db,
            )
            
            client = Redis(connection_pool=pool)
            
            # Test connection with PING
            client.ping()
            
            logger.info(
                f"Redis client created successfully "
                f"(max_connections={config.redis_max_connections}, db={config.redis_db})"
            )
            
            return client
            
        except RedisConnectionError as e:
            if attempt < MAX_RETRIES:
                backoff_seconds = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"Redis connection failed (attempt {attempt}/{MAX_RETRIES}): {e}. "
                    f"Retrying in {backoff_seconds}s..."
                )
                time.sleep(backoff_seconds)
            else:
                logger.error(
                    f"Redis connection failed after {MAX_RETRIES} attempts: {e}"
                )
                raise RedisClientError(
                    f"Redis unavailable after {MAX_RETRIES} attempts: {e}"
                )
        except Exception as e:
            logger.error(f"Unexpected error creating Redis client: {e}")
            raise RedisClientError(f"Unexpected Redis error: {e}")


def init_redis_client(config: RedisSettings) -> Redis:
    """
    Initialize the global Redis client.
    
    This function should be called once during application startup.
    Subsequent calls return the existing client instance.
    
    Args:
        config: RedisSettings instance
        
    Returns:
        Redis client instance
    """
    global _client, _pool
    
    if _client is not None:
        logger.warning("Redis client already initialized")
        return _client
    
    _client = create_redis_client(config)
    _pool = _client.connection_pool
    
    logger.info("Redis client initialized")
    
    return _client


def get_redis_client() -> Redis:
    """
    Get the initialized Redis client.
    
    Returns:
        Redis client instance
        
    Raises:
        RuntimeError: If client not initialized
    """
    if _client is None:
        raise RuntimeError(
            "Redis client not initialized. Call init_redis_client() first."
        )
    return _client


def cleanup_redis():
    """
    Cleanup Redis resources.
    
    Closes connection pool gracefully.
    Called automatically at shutdown via atexit.
    """
    global _client, _pool
    
    if _client is None:
        return
    
    try:
        logger.info("Shutting down Redis client...")
        
        # Close all connections in pool
        if _pool:
            _pool.disconnect()
        
        _client = None
        _pool = None
        
        logger.info("Redis client shutdown complete")
    except Exception as e:
        logger.error(f"Error during Redis cleanup: {e}")


# Register cleanup on shutdown
atexit.register(cleanup_redis)
