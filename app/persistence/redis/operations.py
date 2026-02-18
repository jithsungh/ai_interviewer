"""
Redis Operations

Core Redis operations: set, get, increment, TTL management, batch operations.
Pure infrastructure - contains zero business logic.
"""

import logging
from typing import Optional, Dict, Any, List
import json

from redis import Redis
from redis.exceptions import RedisError, ResponseError, TimeoutError as RedisTimeoutError

from .client import get_redis_client

logger = logging.getLogger(__name__)


# ==================
# Basic Operations
# ==================

def set_value(
    key: str,
    value: Any,
    ttl_seconds: Optional[int] = None,
    client: Optional[Redis] = None
) -> bool:
    """
    Set key-value pair with optional TTL.
    
    Args:
        key: Redis key
        value: Value to store (will be JSON-encoded if dict/list)
        ttl_seconds: Time to live in seconds (None = no expiration)
        client: Redis client (uses global if None)
        
    Returns:
        True if successful
        
    Raises:
        RedisError: If operation fails
    """
    if client is None:
        client = get_redis_client()
    
    try:
        # JSON-encode complex types
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        
        if ttl_seconds:
            client.setex(key, ttl_seconds, value)
        else:
            client.set(key, value)
        
        logger.debug(f"Redis SET: {key} (TTL: {ttl_seconds}s)")
        return True
        
    except RedisError as e:
        logger.error(f"Redis SET failed for key '{key}': {e}")
        raise


def get_value(
    key: str,
    default: Any = None,
    deserialize_json: bool = False,
    client: Optional[Redis] = None
) -> Any:
    """
    Get value by key with graceful fallback.
    
    Args:
        key: Redis key
        default: Default value if key not found
        deserialize_json: Attempt to JSON-decode value
        client: Redis client (uses global if None)
        
    Returns:
        Value associated with key, or default if not found
    """
    if client is None:
        client = get_redis_client()
    
    try:
        value = client.get(key)
        
        if value is None:
            logger.debug(f"Redis GET: {key} → NOT FOUND (default: {default})")
            return default
        
        # Attempt JSON deserialization if requested
        if deserialize_json:
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass  # Return as-is if not valid JSON
        
        logger.debug(f"Redis GET: {key} → found")
        return value
        
    except RedisTimeoutError:
        logger.warning(f"Redis GET timeout for key '{key}', using fallback")
        return default
    except RedisError as e:
        logger.error(f"Redis GET failed for key '{key}': {e}, using fallback")
        return default


def delete_key(
    key: str,
    client: Optional[Redis] = None
) -> int:
    """
    Delete key from Redis.
    
    Args:
        key: Redis key to delete
        client: Redis client (uses global if None)
        
    Returns:
        Number of keys deleted (0 or 1)
    """
    if client is None:
        client = get_redis_client()
    
    try:
        result = client.delete(key)
        logger.debug(f"Redis DEL: {key} → {result} keys deleted")
        return result
    except RedisError as e:
        logger.error(f"Redis DEL failed for key '{key}': {e}")
        raise


def exists(
    key: str,
    client: Optional[Redis] = None
) -> bool:
    """
    Check if key exists.
    
    Args:
        key: Redis key
        client: Redis client (uses global if None)
        
    Returns:
        True if key exists, False otherwise
    """
    if client is None:
        client = get_redis_client()
    
    try:
        return bool(client.exists(key))
    except RedisError as e:
        logger.error(f"Redis EXISTS failed for key '{key}': {e}")
        return False


# ==================
# TTL Management
# ==================

def set_ttl(
    key: str,
    ttl_seconds: int,
    client: Optional[Redis] = None
) -> bool:
    """
    Set TTL on existing key.
    
    Args:
        key: Redis key
        ttl_seconds: Time to live in seconds
        client: Redis client (uses global if None)
        
    Returns:
        True if TTL set successfully, False if key doesn't exist
    """
    if client is None:
        client = get_redis_client()
    
    try:
        result = client.expire(key, ttl_seconds)
        logger.debug(f"Redis EXPIRE: {key} → {ttl_seconds}s (success: {result})")
        return result
    except RedisError as e:
        logger.error(f"Redis EXPIRE failed for key '{key}': {e}")
        raise


def get_ttl(
    key: str,
    client: Optional[Redis] = None
) -> int:
    """
    Get remaining TTL for key.
    
    Args:
        key: Redis key
        client: Redis client (uses global if None)
        
    Returns:
        Remaining seconds (-1 if no expiry, -2 if key not found)
    """
    if client is None:
        client = get_redis_client()
    
    try:
        ttl = client.ttl(key)
        logger.debug(f"Redis TTL: {key} → {ttl}s")
        return ttl
    except RedisError as e:
        logger.error(f"Redis TTL failed for key '{key}': {e}")
        return -2


# ==================
# Hash Operations
# ==================

def hash_set(
    key: str,
    mapping: Dict[str, Any],
    ttl_seconds: Optional[int] = None,
    client: Optional[Redis] = None
) -> bool:
    """
    Store multiple field-value pairs in a hash.
    
    Args:
        key: Redis hash key
        mapping: Dictionary of field-value pairs
        ttl_seconds: Optional TTL for the hash
        client: Redis client (uses global if None)
        
    Returns:
        True if successful
    """
    if client is None:
        client = get_redis_client()
    
    try:
        # JSON-encode complex values
        encoded_mapping = {}
        for field, value in mapping.items():
            if isinstance(value, (dict, list)):
                encoded_mapping[field] = json.dumps(value)
            else:
                encoded_mapping[field] = value
        
        client.hset(key, mapping=encoded_mapping)
        
        if ttl_seconds:
            client.expire(key, ttl_seconds)
        
        logger.debug(f"Redis HSET: {key} → {len(mapping)} fields")
        return True
        
    except RedisError as e:
        logger.error(f"Redis HSET failed for key '{key}': {e}")
        raise


def hash_get(
    key: str,
    field: str,
    default: Any = None,
    deserialize_json: bool = False,
    client: Optional[Redis] = None
) -> Any:
    """
    Get single field from hash.
    
    Args:
        key: Redis hash key
        field: Field name
        default: Default value if field not found
        deserialize_json: Attempt to JSON-decode value
        client: Redis client (uses global if None)
        
    Returns:
        Field value, or default if not found
    """
    if client is None:
        client = get_redis_client()
    
    try:
        value = client.hget(key, field)
        
        if value is None:
            return default
        
        if deserialize_json:
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass
        
        return value
        
    except RedisError as e:
        logger.error(f"Redis HGET failed for key '{key}' field '{field}': {e}")
        return default


def hash_get_all(
    key: str,
    deserialize_json: bool = False,
    client: Optional[Redis] = None
) -> Dict[str, Any]:
    """
    Get all fields from hash.
    
    Args:
        key: Redis hash key
        deserialize_json: Attempt to JSON-decode values
        client: Redis client (uses global if None)
        
    Returns:
        Dictionary of all field-value pairs (empty dict if hash not found)
    """
    if client is None:
        client = get_redis_client()
    
    try:
        data = client.hgetall(key)
        
        if deserialize_json:
            decoded_data = {}
            for field, value in data.items():
                try:
                    decoded_data[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    decoded_data[field] = value
            return decoded_data
        
        return data
        
    except RedisError as e:
        logger.error(f"Redis HGETALL failed for key '{key}': {e}")
        return {}


# ==================
# Counters
# ==================

def increment_counter(
    key: str,
    amount: int = 1,
    ttl_seconds: Optional[int] = None,
    client: Optional[Redis] = None
) -> int:
    """
    Atomically increment counter.
    
    Args:
        key: Redis key
        amount: Amount to increment (default: 1)
        ttl_seconds: Set TTL on first increment
        client: Redis client (uses global if None)
        
    Returns:
        New counter value after increment
    """
    if client is None:
        client = get_redis_client()
    
    try:
        # If no TTL is requested, use a simple INCR for efficiency.
        if not ttl_seconds:
            new_value = client.incr(key, amount)
        else:
            # Use a Lua script to make INCR + conditional EXPIRE atomic.
            # Logic:
            #   local v = redis.call('INCRBY', KEYS[1], tonumber(ARGV[1]))
            #   if v == tonumber(ARGV[1]) and tonumber(ARGV[2]) > 0 then
            #       redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2]))
            #   end
            #   return v
            lua_script = (
                "local v = redis.call('INCRBY', KEYS[1], tonumber(ARGV[1])) "
                "if v == tonumber(ARGV[1]) and tonumber(ARGV[2]) > 0 then "
                "redis.call('EXPIRE', KEYS[1], tonumber(ARGV[2])) "
                "end "
                "return v"
            )
            new_value = client.eval(lua_script, 1, key, amount, int(ttl_seconds))
        
        logger.debug(f"Redis INCR: {key} → {new_value}")
        return new_value
        
    except RedisError as e:
        logger.error(f"Redis INCR failed for key '{key}': {e}")
        raise


def decrement_counter(
    key: str,
    amount: int = 1,
    client: Optional[Redis] = None
) -> int:
    """
    Atomically decrement counter.
    
    Args:
        key: Redis key
        amount: Amount to decrement (default: 1)
        client: Redis client (uses global if None)
        
    Returns:
        New counter value after decrement
    """
    if client is None:
        client = get_redis_client()
    
    try:
        new_value = client.decr(key, amount)
        logger.debug(f"Redis DECR: {key} → {new_value}")
        return new_value
        
    except RedisError as e:
        logger.error(f"Redis DECR failed for key '{key}': {e}")
        raise


# ==================
# Batch Operations
# ==================

def batch_set(
    key_values: Dict[str, Any],
    client: Optional[Redis] = None
) -> bool:
    """
    Set multiple keys in a single operation.
    
    Args:
        key_values: Dictionary of key-value pairs
        client: Redis client (uses global if None)
        
    Returns:
        True if successful
    """
    if client is None:
        client = get_redis_client()
    
    try:
        # JSON-encode complex values
        encoded_data = {}
        for key, value in key_values.items():
            if isinstance(value, (dict, list)):
                encoded_data[key] = json.dumps(value)
            else:
                encoded_data[key] = value
        
        client.mset(encoded_data)
        logger.debug(f"Redis MSET: {len(key_values)} keys")
        return True
        
    except RedisError as e:
        logger.error(f"Redis MSET failed: {e}")
        raise


def batch_get(
    keys: List[str],
    client: Optional[Redis] = None
) -> Dict[str, Any]:
    """
    Get multiple keys in a single operation.
    
    Args:
        keys: List of keys to retrieve
        client: Redis client (uses global if None)
        
    Returns:
        Dictionary mapping keys to values (None for missing keys)
    """
    if client is None:
        client = get_redis_client()
    
    try:
        values = client.mget(keys)
        result = dict(zip(keys, values))
        logger.debug(f"Redis MGET: {len(keys)} keys")
        return result
        
    except RedisError as e:
        logger.error(f"Redis MGET failed: {e}")
        return {key: None for key in keys}


def batch_delete(
    keys: List[str],
    client: Optional[Redis] = None
) -> int:
    """
    Delete multiple keys in a single operation.
    
    Args:
        keys: List of keys to delete
        client: Redis client (uses global if None)
        
    Returns:
        Number of keys deleted
    """
    if client is None:
        client = get_redis_client()
    
    try:
        count = client.delete(*keys)
        logger.debug(f"Redis DEL batch: {count}/{len(keys)} keys deleted")
        return count
        
    except RedisError as e:
        logger.error(f"Redis batch DEL failed: {e}")
        raise


# ==================
# Pipeline (Bulk Operations)
# ==================

# Allowlist of permitted Redis commands for security in execute_pipeline
_PIPELINE_ALLOWED_COMMANDS = {
    'set', 'get', 'del', 'delete', 'exists',
    'incr', 'incrby', 'decr', 'decrby',
    'hset', 'hget', 'hgetall', 'hdel',
    'expire', 'expireat', 'ttl', 'pttl',
    'setex', 'setnx', 'getset',
    'lpush', 'rpush', 'lpop', 'rpop', 'lrange',
    'sadd', 'srem', 'smembers', 'sismember',
    'zadd', 'zrem', 'zrange', 'zscore',
}

def execute_pipeline(
    operations: List[tuple],
    client: Optional[Redis] = None
) -> List[Any]:
    """
    Execute multiple operations in a pipeline (single round trip).
    
    ⚠️ SECURITY WARNING: This function is for INTERNAL USE ONLY.
    It should NEVER be called with untrusted user input. Commands are validated
    against an allowlist to prevent arbitrary Redis command execution.
    
    Args:
        operations: List of (command, args) tuples
                    Example: [("SET", ("key1", "value1")), ("GET", ("key2",))]
        client: Redis client (uses global if None)
        
    Returns:
        List of results for each operation
        
    Raises:
        ValueError: If an operation contains a disallowed command
        RedisError: If pipeline execution fails
    """
    if client is None:
        client = get_redis_client()
    
    # Validate all commands before executing any
    for command, args in operations:
        command_lower = command.lower()
        if command_lower not in _PIPELINE_ALLOWED_COMMANDS:
            raise ValueError(
                f"Command '{command}' is not in the allowlist. "
                f"Allowed commands: {sorted(_PIPELINE_ALLOWED_COMMANDS)}"
            )
    
    try:
        pipe = client.pipeline()
        
        for command, args in operations:
            getattr(pipe, command.lower())(*args)
        
        results = pipe.execute()
        logger.debug(f"Redis PIPELINE: {len(operations)} operations executed")
        return results
        
    except RedisError as e:
        logger.error(f"Redis pipeline execution failed: {e}")
        raise
