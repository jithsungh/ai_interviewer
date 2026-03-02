"""
Unit Tests for Health Checks

Tests health check logic, status determination, and monitoring.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.exc import OperationalError

from app.persistence.postgres.health import (
    check_postgres_health,
    check_postgres_connectivity,
    log_pool_stats,
    get_health_check_endpoint_response,
    HealthStatus,
)


class TestHealthCheckStatus:
    """Test health check status determination."""
    
    @patch('app.persistence.postgres.health.get_pool_status')
    @patch('app.persistence.postgres.health.get_engine')
    def test_health_check_healthy(self, mock_get_engine, mock_get_pool_status):
        """Test health check returns healthy when all checks pass."""
        # Mock pool status (good)
        mock_get_pool_status.return_value = {
            "pool_size": 10,
            "checked_out": 2,
            "overflow": 0,
            "total_connections": 10,
        }
        
        # Mock successful connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine
        
        health = check_postgres_health()
        
        assert health["status"] == HealthStatus.HEALTHY.value
        assert health["latency_ms"] is not None
        assert health["latency_ms"] < 1000
        assert "errors" not in health or len(health["errors"]) == 0
    
    @patch('app.persistence.postgres.health.get_pool_status')
    @patch('app.persistence.postgres.health.get_engine')
    def test_health_check_degraded_high_latency(self, mock_get_engine, mock_get_pool_status):
        """Test health check returns degraded when latency is high."""
        # Mock pool status (good)
        mock_get_pool_status.return_value = {
            "pool_size": 10,
            "checked_out": 2,
            "overflow": 0,
            "total_connections": 10,
        }
        
        # Mock slow connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine
        
        # Mock time to simulate high latency
        with patch('app.persistence.postgres.health.time.perf_counter') as mock_perf:
            mock_perf.side_effect = [0, 1.5]  # 1.5 second latency
            health = check_postgres_health()
        
        assert health["status"] == HealthStatus.DEGRADED.value
        assert health["latency_ms"] > 1000
        assert "errors" in health
        assert any("latency" in err.lower() for err in health["errors"])
    
    @patch('app.persistence.postgres.health.get_pool_status')
    @patch('app.persistence.postgres.health.get_engine')
    def test_health_check_degraded_pool_exhausted(self, mock_get_engine, mock_get_pool_status):
        """Test health check returns degraded when pool is exhausted."""
        # Mock pool status (exhausted)
        mock_get_pool_status.return_value = {
            "pool_size": 10,
            "checked_out": 10,  # All connections in use
            "overflow": 0,
            "total_connections": 10,
        }
        
        # Mock successful connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine
        
        health = check_postgres_health()
        
        assert health["status"] == HealthStatus.DEGRADED.value
        assert "errors" in health
        assert any("pool exhausted" in err.lower() for err in health["errors"])
    
    @patch('app.persistence.postgres.health.get_pool_status')
    @patch('app.persistence.postgres.health.get_engine')
    def test_health_check_degraded_high_pool_utilization(self, mock_get_engine, mock_get_pool_status):
        """Test health check returns degraded when pool utilization > 80%."""
        # Mock pool status (high utilization)
        mock_get_pool_status.return_value = {
            "pool_size": 10,
            "checked_out": 9,  # 90% utilization
            "overflow": 0,
            "total_connections": 10,
        }
        
        # Mock successful connection
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        mock_conn.execute.return_value = mock_result
        
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine
        
        health = check_postgres_health()
        
        assert health["status"] == HealthStatus.DEGRADED.value
        assert "errors" in health
    
    @patch('app.persistence.postgres.health.get_pool_status')
    @patch('app.persistence.postgres.health.get_engine')
    def test_health_check_unhealthy_connection_failure(self, mock_get_engine, mock_get_pool_status):
        """Test health check returns unhealthy when connection fails."""
        # Mock pool status
        mock_get_pool_status.return_value = {
            "pool_size": 10,
            "checked_out": 2,
            "overflow": 0,
            "total_connections": 10,
        }
        
        # Mock connection failure
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("Connection refused", None, None)
        mock_get_engine.return_value = mock_engine
        
        health = check_postgres_health()
        
        assert health["status"] == HealthStatus.UNHEALTHY.value
        assert "errors" in health
        assert any("connectivity" in err.lower() for err in health["errors"])


class TestConnectivityCheck:
    """Test simple connectivity check."""
    
    @patch('app.persistence.postgres.health.get_engine')
    def test_connectivity_check_success(self, mock_get_engine):
        """Test connectivity check returns True when connected."""
        mock_conn = MagicMock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        mock_engine = MagicMock()
        mock_engine.connect.return_value = mock_conn
        mock_get_engine.return_value = mock_engine
        
        result = check_postgres_connectivity()
        
        assert result is True
    
    @patch('app.persistence.postgres.health.get_engine')
    def test_connectivity_check_failure(self, mock_get_engine):
        """Test connectivity check returns False when connection fails."""
        mock_engine = MagicMock()
        mock_engine.connect.side_effect = OperationalError("Connection refused", None, None)
        mock_get_engine.return_value = mock_engine
        
        result = check_postgres_connectivity()
        
        assert result is False


class TestPoolStatsLogging:
    """Test pool statistics logging."""
    
    @patch('app.persistence.postgres.health.get_pool_status')
    @patch('app.persistence.postgres.health.logger')
    def test_log_pool_stats_normal(self, mock_logger, mock_get_pool_status):
        """Test logging pool stats under normal conditions."""
        mock_get_pool_status.return_value = {
            "pool_size": 10,
            "checked_out": 3,
            "overflow": 1,
            "total_connections": 11,
        }
        
        log_pool_stats()
        
        # Should log info
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "size=10" in log_message
        assert "checked_out=3" in log_message
    
    @patch('app.persistence.postgres.health.get_pool_status')
    @patch('app.persistence.postgres.health.logger')
    def test_log_pool_stats_exhausted(self, mock_logger, mock_get_pool_status):
        """Test logging pool stats when pool is exhausted."""
        mock_get_pool_status.return_value = {
            "pool_size": 10,
            "checked_out": 10,
            "overflow": 0,
            "total_connections": 10,
        }
        
        log_pool_stats()
        
        # Should log critical alert
        mock_logger.critical.assert_called_once()
        log_message = mock_logger.critical.call_args[0][0]
        assert "EXHAUSTED" in log_message


class TestHealthCheckEndpointResponse:
    """Test health check endpoint response formatting."""
    
    @patch('app.persistence.postgres.health.check_postgres_health')
    def test_endpoint_response_healthy(self, mock_check_health):
        """Test endpoint response format when healthy."""
        mock_check_health.return_value = {
            "status": "healthy",
            "latency_ms": 15.5,
            "pool": {
                "pool_size": 10,
                "checked_out": 2,
                "overflow": 0,
                "total_connections": 10,
            },
            "timestamp": 1234567890.0,
        }
        
        response = get_health_check_endpoint_response()
        
        assert response["service"] == "postgresql"
        assert response["status"] == "healthy"
        assert response["checks"]["connectivity"] == "pass"
        assert response["checks"]["latency"]["value_ms"] == 15.5
        assert response["checks"]["latency"]["status"] == "pass"
        assert response["checks"]["pool"]["utilization"] == 20.0  # 2/10 * 100
    
    @patch('app.persistence.postgres.health.check_postgres_health')
    def test_endpoint_response_with_errors(self, mock_check_health):
        """Test endpoint response includes errors."""
        mock_check_health.return_value = {
            "status": "unhealthy",
            "latency_ms": None,
            "pool": None,
            "timestamp": 1234567890.0,
            "errors": ["Database connectivity error: Connection refused"],
        }
        
        response = get_health_check_endpoint_response()
        
        assert response["status"] == "unhealthy"
        assert response["checks"]["connectivity"] == "fail"
        assert len(response["errors"]) == 1


class TestHealthStatusEnum:
    """Test HealthStatus enum."""
    
    def test_health_status_values(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
