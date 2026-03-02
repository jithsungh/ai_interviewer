"""
Qdrant Health Checks

Provides connectivity and collection health monitoring.
"""

import logging
import time
from typing import Dict, Any
from enum import Enum

from qdrant_client.http.exceptions import UnexpectedResponse

from .client import get_qdrant_client, get_collection_name, QdrantConnectionError
from .collections import get_collection_info

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Health check status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


def check_qdrant_connectivity() -> Dict[str, Any]:
    """
    Check basic Qdrant connectivity.
    
    Returns:
        Dictionary with connectivity status
    """
    try:
        client = get_qdrant_client()
        
        start_time = time.perf_counter()
        collections = client.get_collections()
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            "status": HealthStatus.HEALTHY,
            "message": "Qdrant connection successful",
            "collections_count": len(collections.collections),
            "latency_ms": round(latency_ms, 2),
        }
        
    except RuntimeError as e:
        # Client not initialized
        return {
            "status": HealthStatus.UNHEALTHY,
            "message": "Qdrant client not initialized",
            "error": str(e),
        }
        
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "message": "Qdrant connection failed",
            "error": str(e),
        }


def check_collection_health() -> Dict[str, Any]:
    """
    Check collection health (exists, schema valid, status).
    
    Returns:
        Dictionary with collection health status
    """
    try:
        collection_name = get_collection_name()
        collection_info = get_collection_info()
        
        # Determine health status
        status = HealthStatus.HEALTHY
        message = "Collection healthy"
        
        if collection_info["status"] != "green":
            status = HealthStatus.DEGRADED
            message = f"Collection status: {collection_info['status']}"
        
        if not collection_info["optimizer_status"]:
            status = HealthStatus.DEGRADED
            message = "Optimizer not OK"
        
        return {
            "status": status,
            "message": message,
            "collection": collection_name,
            "points_count": collection_info["points_count"],
            "vectors_count": collection_info["vectors_count"],
            "segments_count": collection_info["segments_count"],
            "vector_dimension": collection_info["vector_dimension"],
            "distance_metric": collection_info["distance_metric"],
        }
        
    except RuntimeError as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "message": "Qdrant client not initialized",
            "error": str(e),
        }
        
    except Exception as e:
        return {
            "status": HealthStatus.UNHEALTHY,
            "message": "Collection health check failed",
            "error": str(e),
        }


def check_qdrant_health() -> Dict[str, Any]:
    """
    Comprehensive Qdrant health check.
    
    Checks:
    - Connectivity to Qdrant server
    - Collection existence and status
    - Schema validation
    
    Returns:
        Dictionary with overall health status
    """
    connectivity = check_qdrant_connectivity()
    collection = check_collection_health()
    
    # Determine overall status (worst of the two)
    statuses = [connectivity["status"], collection["status"]]
    
    if HealthStatus.UNHEALTHY in statuses:
        overall_status = HealthStatus.UNHEALTHY
    elif HealthStatus.DEGRADED in statuses:
        overall_status = HealthStatus.DEGRADED
    else:
        overall_status = HealthStatus.HEALTHY
    
    return {
        "status": overall_status,
        "connectivity": connectivity,
        "collection": collection,
        "timestamp": time.time(),
    }


def get_health_check_endpoint_response() -> tuple[Dict[str, Any], int]:
    """
    Get health check response for FastAPI endpoint.
    
    Returns:
        Tuple of (response_dict, http_status_code)
    """
    health = check_qdrant_health()
    
    # Map health status to HTTP status code
    status_code_map = {
        HealthStatus.HEALTHY: 200,
        HealthStatus.DEGRADED: 200,  # Still operational
        HealthStatus.UNHEALTHY: 503,  # Service unavailable
    }
    
    http_status = status_code_map[health["status"]]
    
    return health, http_status


def log_qdrant_stats() -> None:
    """
    Log Qdrant statistics for monitoring.
    
    Called periodically by background task or health check.
    """
    try:
        health = check_qdrant_health()
        
        if health["status"] == HealthStatus.HEALTHY:
            logger.info(
                f"Qdrant health: {health['status'].value} | "
                f"Collection: {health['collection']['collection']} | "
                f"Points: {health['collection']['points_count']} | "
                f"Latency: {health['connectivity'].get('latency_ms', 'N/A')}ms"
            )
        else:
            logger.warning(
                f"Qdrant health: {health['status'].value} | "
                f"Message: {health.get('message', 'Unknown')}"
            )
            
    except Exception as e:
        logger.error(f"Failed to log Qdrant stats: {e}")
