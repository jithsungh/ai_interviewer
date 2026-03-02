"""
Database Health Checks

Provides health check functionality for PostgreSQL connectivity
and pool monitoring.
"""

import time
import logging
from typing import Dict, Any
from enum import Enum

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .engine import get_engine, get_pool_status

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status enum."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


def check_postgres_health() -> Dict[str, Any]:
    """
    Comprehensive PostgreSQL health check.
    
    Checks:
    1. Database connectivity (SELECT 1 test)
    2. Query latency
    3. Connection pool status
    4. Pool exhaustion risk
    
    Returns:
        Dictionary containing:
        - status: "healthy" | "degraded" | "unhealthy"
        - latency_ms: Query round-trip time
        - pool: Connection pool metrics
        - timestamp: Check timestamp
        - errors: List of error messages (if any)
    """
    errors = []
    latency_ms = None
    pool_status = None
    status = HealthStatus.HEALTHY
    
    try:
        # Get pool status
        pool_status = get_pool_status()
        
        # Check pool exhaustion
        if pool_status["checked_out"] >= pool_status["total_connections"]:
            errors.append("Connection pool exhausted")
            status = HealthStatus.DEGRADED
        elif pool_status["checked_out"] / pool_status["total_connections"] > 0.8:
            errors.append("Connection pool utilization > 80%")
            status = HealthStatus.DEGRADED
        
    except Exception as e:
        errors.append(f"Failed to get pool status: {str(e)}")
        status = HealthStatus.DEGRADED
    
    try:
        # Test database connectivity with latency measurement
        engine = get_engine()
        
        start = time.perf_counter()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS health_check"))
            row = result.fetchone()
            
            if row[0] != 1:
                raise ValueError("Health check query returned unexpected value")
        
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        
        # Check latency thresholds
        if latency_ms > 1000:  # > 1 second
            errors.append(f"High database latency: {latency_ms}ms")
            status = HealthStatus.DEGRADED
        elif latency_ms > 100:  # > 100ms
            logger.warning(f"Elevated database latency: {latency_ms}ms")
        
    except SQLAlchemyError as e:
        errors.append(f"Database connectivity error: {str(e)}")
        status = HealthStatus.UNHEALTHY
        logger.error(f"Database health check failed: {e}")
        
    except Exception as e:
        errors.append(f"Unexpected health check error: {str(e)}")
        status = HealthStatus.UNHEALTHY
        logger.error(f"Unexpected error during health check: {e}")
    
    result = {
        "status": status.value,
        "latency_ms": latency_ms,
        "pool": pool_status,
        "timestamp": time.time(),
    }
    
    if errors:
        result["errors"] = errors
    
    return result


def check_postgres_connectivity() -> bool:
    """
    Simple connectivity check (returns boolean).
    
    Useful for fast startup checks or readiness probes.
    
    Returns:
        True if database is reachable, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Connectivity check failed: {e}")
        return False


def log_pool_stats():
    """
    Log current connection pool statistics.
    
    Call this periodically (e.g., every 60 seconds) for monitoring.
    Useful for detecting connection leaks and sizing issues.
    """
    try:
        pool_status = get_pool_status()
        
        logger.info(
            f"DB Pool Stats: "
            f"size={pool_status['pool_size']}, "
            f"checked_out={pool_status['checked_out']}, "
            f"overflow={pool_status['overflow']}, "
            f"total={pool_status['total_connections']}"
        )
        
        # Alert if pool is exhausted
        if pool_status["checked_out"] >= pool_status["total_connections"]:
            logger.critical(
                "⚠️ DATABASE CONNECTION POOL EXHAUSTED! "
                "All connections in use. Requests will block."
            )
            
    except Exception as e:
        logger.error(f"Failed to log pool stats: {e}")


def get_health_check_endpoint_response() -> Dict[str, Any]:
    """
    Format health check for API endpoint response.
    
    Returns standardized health check response for FastAPI endpoint.
    
    Returns:
        Dictionary with status and details
        
    Example:
        @app.get("/health/postgres")
        def postgres_health():
            return get_health_check_endpoint_response()
    """
    health = check_postgres_health()
    
    return {
        "service": "postgresql",
        "status": health["status"],
        "checks": {
            "connectivity": "pass" if health["latency_ms"] is not None else "fail",
            "latency": {
                "value_ms": health["latency_ms"],
                "threshold_ms": 1000,
                "status": "pass" if health["latency_ms"] and health["latency_ms"] < 1000 else "fail"
            },
            "pool": {
                "size": health["pool"]["pool_size"] if health["pool"] else None,
                "checked_out": health["pool"]["checked_out"] if health["pool"] else None,
                "utilization": round(
                    health["pool"]["checked_out"] / health["pool"]["total_connections"] * 100, 2
                ) if health["pool"] and health["pool"]["total_connections"] > 0 else None,
            }
        },
        "timestamp": health["timestamp"],
        "errors": health.get("errors", []),
    }
