"""
Unit Tests for Redis Health Checks

Tests health check functionality and monitoring.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import time

from app.persistence.redis.health import (
    check_redis_health,
    check_redis_connectivity,
    get_pool_status,
    log_redis_stats,
    get_health_check_endpoint_response,
    HealthStatus,
)


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    client = MagicMock()
    # Mock connection pool
    pool = MagicMock()
    pool.max_connections = 50
    pool._in_use_connections = []
    pool._available_connections = [Mock()] * 48
    client.connection_pool = pool
    return client


class TestHealthCheck:
    """Test health check functionality."""
    
    def test_health_check_healthy(self, mock_redis):
        """Test health check when Redis is healthy."""
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "connected_clients": 5,
            "used_memory_human": "1.5M",
            "used_memory_peak_human": "2.0M",
            "uptime_in_seconds": 3600,
            "uptime_in_days": 0,
            "redis_version": "7.0.0",
            "role": "master",
            "instantaneous_ops_per_sec": 100,
            "maxclients": 10000,
        }
        
        result = check_redis_health(mock_redis)
        
        assert result["status"] == HealthStatus.HEALTHY.value
        assert result["latency_ms"] is not None
        assert result["latency_ms"] < 100  # Should be fast for mock
        assert result["info"]["connected_clients"] == 5
        assert result["info"]["redis_version"] == "7.0.0"
        assert result["errors"] is None
    
    def test_health_check_degraded_latency(self, mock_redis):
        """Test health check degraded due to high latency."""
        # Simulate slow ping
        def slow_ping():
            time.sleep(0.15)  # > 100ms threshold
            return True
        
        mock_redis.ping.side_effect = slow_ping
        mock_redis.info.return_value = {
            "connected_clients": 5,
            "used_memory_human": "1.5M",
            "used_memory_peak_human": "2.0M",
            "uptime_in_seconds": 3600,
            "uptime_in_days": 0,
            "redis_version": "7.0.0",
            "role": "master",
            "instantaneous_ops_per_sec": 100,
            "maxclients": 10000,
        }
        
        result = check_redis_health(mock_redis)
        
        # Should still be healthy (warning threshold)
        assert result["status"] in [HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value]
        assert result["latency_ms"] > 100
    
    def test_health_check_degraded_memory(self, mock_redis):
        """Test health check degraded due to high memory usage."""
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "connected_clients": 5,
            "used_memory": 950_000_000,  # 950MB
            "maxmemory": 1_000_000_000,  # 1GB (95% usage)
            "used_memory_human": "950M",
            "used_memory_peak_human": "1.0G",
            "uptime_in_seconds": 3600,
            "uptime_in_days": 0,
            "redis_version": "7.0.0",
            "role": "master",
            "instantaneous_ops_per_sec": 100,
            "maxclients": 10000,
        }
        
        result = check_redis_health(mock_redis)
        
        assert result["status"] == HealthStatus.DEGRADED.value
        assert "memory" in str(result["errors"]).lower()
    
    def test_health_check_degraded_connections(self, mock_redis):
        """Test health check degraded due to high connection usage."""
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "connected_clients": 8500,  # 85% of max
            "maxclients": 10000,
            "used_memory_human": "1.5M",
            "used_memory_peak_human": "2.0M",
            "uptime_in_seconds": 3600,
            "uptime_in_days": 0,
            "redis_version": "7.0.0",
            "role": "master",
            "instantaneous_ops_per_sec": 100,
        }
        
        result = check_redis_health(mock_redis)
        
        assert result["status"] == HealthStatus.DEGRADED.value
        assert "client" in str(result["errors"]).lower()
    
    def test_health_check_unhealthy_connection_error(self, mock_redis):
        """Test health check unhealthy due to connection error."""
        from redis.exceptions import ConnectionError as RedisConnectionError
        mock_redis.ping.side_effect = RedisConnectionError("Connection refused")
        
        result = check_redis_health(mock_redis)
        
        assert result["status"] == HealthStatus.UNHEALTHY.value
        assert result["latency_ms"] is None
        assert result["info"] is None
        assert result["errors"] is not None
        assert "connection" in str(result["errors"]).lower()
    
    def test_health_check_client_not_initialized(self):
        """Test health check when client not initialized."""
        with patch('app.persistence.redis.health.get_redis_client') as mock_get:
            mock_get.side_effect = RuntimeError("Client not initialized")
            
            result = check_redis_health()
            
            assert result["status"] == HealthStatus.UNHEALTHY.value
            assert "not initialized" in str(result["errors"]).lower()


class TestConnectivityCheck:
    """Test simple connectivity check."""
    
    def test_connectivity_check_success(self, mock_redis):
        """Test connectivity check succeeds."""
        mock_redis.ping.return_value = True
        
        result = check_redis_connectivity(mock_redis)
        
        assert result is True
        mock_redis.ping.assert_called_once()
    
    def test_connectivity_check_failure(self, mock_redis):
        """Test connectivity check fails."""
        from redis.exceptions import ConnectionError as RedisConnectionError
        mock_redis.ping.side_effect = RedisConnectionError("Connection refused")
        
        result = check_redis_connectivity(mock_redis)
        
        assert result is False


class TestPoolStatus:
    """Test connection pool status."""
    
    def test_get_pool_status(self, mock_redis):
        """Test getting pool status."""
        result = get_pool_status(mock_redis)
        
        assert result["max_connections"] == 50
        assert result["available_connections"] == 48
        assert result["in_use_connections"] == 0
    
    def test_get_pool_status_not_initialized(self):
        """Test pool status when client not initialized."""
        with patch('app.persistence.redis.health.get_redis_client') as mock_get:
            mock_get.side_effect = RuntimeError("Client not initialized")
            
            result = get_pool_status()
            
            assert result["max_connections"] == 0
            assert "error" in result


class TestLogStats:
    """Test stats logging."""
    
    def test_log_redis_stats(self, mock_redis):
        """Test logging Redis stats."""
        mock_redis.info.return_value = {
            "connected_clients": 5,
            "used_memory_human": "1.5M",
            "instantaneous_ops_per_sec": 100,
            "uptime_in_days": 7,
        }
        
        # Should not raise error
        log_redis_stats(mock_redis)
        
        mock_redis.info.assert_called_once()
    
    def test_log_redis_stats_not_initialized(self):
        """Test logging stats when client not initialized."""
        with patch('app.persistence.redis.health.get_redis_client') as mock_get:
            mock_get.side_effect = RuntimeError("Client not initialized")
            
            # Should not raise error (logs warning)
            log_redis_stats()


class TestHealthEndpointResponse:
    """Test health check endpoint response formatting."""
    
    def test_health_endpoint_response(self, mock_redis):
        """Test health endpoint response format."""
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "connected_clients": 5,
            "used_memory_human": "1.5M",
            "used_memory_peak_human": "2.0M",
            "uptime_in_seconds": 3600,
            "uptime_in_days": 7,
            "redis_version": "7.0.0",
            "role": "master",
            "instantaneous_ops_per_sec": 100,
            "maxclients": 10000,
        }
        
        result = get_health_check_endpoint_response(mock_redis)
        
        assert result["service"] == "redis"
        assert result["status"] == HealthStatus.HEALTHY.value
        assert "latency_ms" in result
        assert "timestamp" in result
        assert "details" in result
        assert result["details"]["connected_clients"] == 5
        assert result["details"]["uptime_days"] == 7
    
    def test_health_endpoint_response_with_errors(self, mock_redis):
        """Test health endpoint response includes errors."""
        from redis.exceptions import ConnectionError as RedisConnectionError
        mock_redis.ping.side_effect = RedisConnectionError("Connection refused")
        
        result = get_health_check_endpoint_response(mock_redis)
        
        assert result["status"] == HealthStatus.UNHEALTHY.value
        assert "errors" in result
        assert len(result["errors"]) > 0
