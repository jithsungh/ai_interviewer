"""
Redis Health Checks

Provides health check functionality for Redis connectivity and performance monitoring.
"""

import time
import logging
from typing import Dict, Any
from enum import Enum

from redis import Redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from .client import get_redis_client

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status enum."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


def check_redis_health(client: Redis = None) -> Dict[str, Any]:
    """
    Comprehensive Redis health check.
    
    Checks:
    1. Redis connectivity (PING test)
    2. Command latency
    3. Connection pool status
    4. Memory usage
    5. Connected clients
    
    Args:
        client: Redis client (uses global if None)
        
    Returns:
        Dictionary containing:
        - status: "healthy" | "degraded" | "unhealthy"
        - latency_ms: PING round-trip time
        - info: Redis server information
        - timestamp: Check timestamp (Unix epoch)
        - errors: List of error messages (if any)
    """
    if client is None:
        try:
            client = get_redis_client()
        except RuntimeError as e:
            return {
                "status": HealthStatus.UNHEALTHY.value,
                "latency_ms": None,
                "info": None,
                "timestamp": time.time(),
                "errors": [str(e)]
            }
    
    errors = []
    latency_ms = None
    redis_info = None
    status = HealthStatus.HEALTHY
    
    try:
        # Test Redis connectivity with latency measurement
        start = time.perf_counter()
        client.ping()
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        
        # Check latency thresholds
        if latency_ms > 1000:  # > 1 second
            errors.append(f"High Redis latency: {latency_ms}ms")
            status = HealthStatus.DEGRADED
        elif latency_ms > 100:  # > 100ms
            logger.warning(f"Elevated Redis latency: {latency_ms}ms")
        
        # Get Redis server info
        info = client.info()
        
        redis_info = {
            "connected_clients": info.get("connected_clients", 0),
            "used_memory_human": info.get("used_memory_human", "unknown"),
            "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
            "uptime_in_seconds": info.get("uptime_in_seconds", 0),
            "uptime_in_days": info.get("uptime_in_days", 0),
            "redis_version": info.get("redis_version", "unknown"),
            "role": info.get("role", "unknown"),
            "instantaneous_ops_per_sec": info.get("instantaneous_ops_per_sec", 0),
        }
        
        # Check memory usage (warn if > 90%)
        if "maxmemory" in info and info["maxmemory"] > 0:
            memory_usage_pct = (info.get("used_memory", 0) / info["maxmemory"]) * 100
            if memory_usage_pct > 90:
                errors.append(f"High memory usage: {memory_usage_pct:.1f}%")
                status = HealthStatus.DEGRADED
        
        # Check connected clients (warn if approaching max)
        max_clients = info.get("maxclients", 10000)
        connected_clients = info.get("connected_clients", 0)
        client_usage_pct = (connected_clients / max_clients) * 100
        
        if client_usage_pct > 80:
            errors.append(f"High client connection usage: {client_usage_pct:.1f}%")
            status = HealthStatus.DEGRADED
        
    except RedisConnectionError as e:
        errors.append(f"Redis connection error: {str(e)}")
        status = HealthStatus.UNHEALTHY
        logger.error(f"Redis health check connection failed: {e}")
        
    except RedisError as e:
        errors.append(f"Redis error: {str(e)}")
        status = HealthStatus.UNHEALTHY
        logger.error(f"Redis health check failed: {e}")
        
    except Exception as e:
        errors.append(f"Unexpected health check error: {str(e)}")
        status = HealthStatus.UNHEALTHY
        logger.error(f"Unexpected error during Redis health check: {e}")
    
    result = {
        "status": status.value,
        "latency_ms": latency_ms,
        "info": redis_info,
        "timestamp": time.time(),
        "errors": errors if errors else None
    }
    
    return result


def check_redis_connectivity(client: Redis = None) -> bool:
    """
    Simple connectivity check (PING test).
    
    Args:
        client: Redis client (uses global if None)
        
    Returns:
        True if Redis is reachable, False otherwise
    """
    if client is None:
        try:
            client = get_redis_client()
        except RuntimeError:
            return False
    
    try:
        client.ping()
        return True
    except RedisError:
        return False


def get_pool_status(client: Redis = None) -> Dict[str, Any]:
    """
    Get Redis connection pool status.
    
    Args:
        client: Redis client (uses global if None)
        
    Returns:
        Dictionary with pool metrics:
        - max_connections: Pool size
        - in_use_connections: Currently checked out
        - available_connections: Available for checkout
    """
    if client is None:
        try:
            client = get_redis_client()
        except RuntimeError:
            return {
                "max_connections": 0,
                "in_use_connections": 0,
                "available_connections": 0,
                "error": "Redis client not initialized"
            }
    
    try:
        pool = client.connection_pool
        
        return {
            "max_connections": pool.max_connections,
            "in_use_connections": len(pool._in_use_connections) if hasattr(pool, '_in_use_connections') else 0,
            "available_connections": len(pool._available_connections) if hasattr(pool, '_available_connections') else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get pool status: {e}")
        return {
            "max_connections": 0,
            "in_use_connections": 0,
            "available_connections": 0,
            "error": str(e)
        }


def log_redis_stats(client: Redis = None):
    """
    Log Redis statistics for monitoring.
    
    Args:
        client: Redis client (uses global if None)
    """
    if client is None:
        try:
            client = get_redis_client()
        except RuntimeError:
            logger.warning("Cannot log Redis stats: client not initialized")
            return
    
    try:
        info = client.info()
        
        logger.info(
            f"Redis Stats: "
            f"clients={info.get('connected_clients', 0)}, "
            f"memory={info.get('used_memory_human', 'unknown')}, "
            f"ops/sec={info.get('instantaneous_ops_per_sec', 0)}, "
            f"uptime={info.get('uptime_in_days', 0)}d"
        )
        
        # Log pool stats
        pool_status = get_pool_status(client)
        logger.info(
            f"Redis Pool: "
            f"max={pool_status['max_connections']}, "
            f"in_use={pool_status['in_use_connections']}, "
            f"available={pool_status['available_connections']}"
        )
        
    except RedisError as e:
        logger.error(f"Failed to log Redis stats: {e}")


def get_health_check_endpoint_response(client: Redis = None) -> Dict[str, Any]:
    """
    Get health check response formatted for API endpoint.
    
    Args:
        client: Redis client (uses global if None)
        
    Returns:
        Formatted health check response for /health endpoint
    """
    health = check_redis_health(client)
    
    response = {
        "service": "redis",
        "status": health["status"],
        "latency_ms": health["latency_ms"],
        "timestamp": health["timestamp"],
    }
    
    if health["info"]:
        response["details"] = {
            "connected_clients": health["info"]["connected_clients"],
            "memory_used": health["info"]["used_memory_human"],
            "uptime_days": health["info"]["uptime_in_days"],
            "version": health["info"]["redis_version"],
        }
    
    if health["errors"]:
        response["errors"] = health["errors"]
    
    return response
