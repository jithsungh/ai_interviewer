"""
Unit Tests for Qdrant Health Checks

Tests health check functions and status reporting.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from qdrant_client.models import CollectionStatus

from app.persistence.qdrant.health import (
    check_qdrant_connectivity,
    check_collection_health,
    check_qdrant_health,
    get_health_check_endpoint_response,
    log_qdrant_stats,
    HealthStatus,
)


@pytest.fixture
def mock_client():
    """Mock Qdrant client."""
    return MagicMock()


class TestConnectivityCheck:
    """Test connectivity health checks."""
    
    @patch('app.persistence.qdrant.health.get_qdrant_client')
    def test_connectivity_healthy(self, mock_get_client, mock_client):
        """Test healthy connectivity."""
        mock_get_client.return_value = mock_client
        
        mock_collections = MagicMock()
        mock_collections.collections = [MagicMock(), MagicMock()]
        mock_client.get_collections.return_value = mock_collections
        
        # Check connectivity
        result = check_qdrant_connectivity()
        
        # Verify healthy status
        assert result["status"] == HealthStatus.HEALTHY
        assert result["collections_count"] == 2
        assert "latency_ms" in result
    
    @patch('app.persistence.qdrant.health.get_qdrant_client')
    def test_connectivity_not_initialized(self, mock_get_client):
        """Test when client not initialized."""
        mock_get_client.side_effect = RuntimeError("Not initialized")
        
        # Check connectivity
        result = check_qdrant_connectivity()
        
        # Verify unhealthy status
        assert result["status"] == HealthStatus.UNHEALTHY
        assert "not initialized" in result["message"].lower()
    
    @patch('app.persistence.qdrant.health.get_qdrant_client')
    def test_connectivity_connection_failed(self, mock_get_client, mock_client):
        """Test when connection fails."""
        mock_get_client.return_value = mock_client
        mock_client.get_collections.side_effect = Exception("Connection refused")
        
        # Check connectivity
        result = check_qdrant_connectivity()
        
        # Verify unhealthy status
        assert result["status"] == HealthStatus.UNHEALTHY
        assert "connection failed" in result["message"].lower()


class TestCollectionHealth:
    """Test collection health checks."""
    
    @patch('app.persistence.qdrant.health.get_collection_info')
    @patch('app.persistence.qdrant.health.get_collection_name')
    def test_collection_healthy(self, mock_get_name, mock_get_info):
        """Test healthy collection."""
        mock_get_name.return_value = "test_collection"
        mock_get_info.return_value = {
            "name": "test_collection",
            "points_count": 1000,
            "vectors_count": 1000,
            "segments_count": 2,
            "status": "green",
            "optimizer_status": True,
            "vector_dimension": 768,
            "distance_metric": "Cosine",
        }
        
        # Check collection health
        result = check_collection_health()
        
        # Verify healthy status
        assert result["status"] == HealthStatus.HEALTHY
        assert result["collection"] == "test_collection"
        assert result["points_count"] == 1000
    
    @patch('app.persistence.qdrant.health.get_collection_info')
    @patch('app.persistence.qdrant.health.get_collection_name')
    def test_collection_degraded_status(self, mock_get_name, mock_get_info):
        """Test degraded collection (status not green)."""
        mock_get_name.return_value = "test_collection"
        mock_get_info.return_value = {
            "status": "yellow",  # Not green
            "optimizer_status": True,
            "points_count": 1000,
            "vectors_count": 1000,
            "segments_count": 2,
            "vector_dimension": 768,
            "distance_metric": "Cosine",
        }
        
        # Check collection health
        result = check_collection_health()
        
        # Verify degraded status
        assert result["status"] == HealthStatus.DEGRADED
        assert "status: yellow" in result["message"].lower()
    
    @patch('app.persistence.qdrant.health.get_collection_info')
    @patch('app.persistence.qdrant.health.get_collection_name')
    def test_collection_degraded_optimizer(self, mock_get_name, mock_get_info):
        """Test degraded collection (optimizer not OK)."""
        mock_get_name.return_value = "test_collection"
        mock_get_info.return_value = {
            "status": "green",
            "optimizer_status": False,  # Not OK
            "points_count": 1000,
            "vectors_count": 1000,
            "segments_count": 2,
            "vector_dimension": 768,
            "distance_metric": "Cosine",
        }
        
        # Check collection health
        result = check_collection_health()
        
        # Verify degraded status
        assert result["status"] == HealthStatus.DEGRADED
        assert "optimizer" in result["message"].lower()


class TestOverallHealth:
    """Test overall health checks."""
    
    @patch('app.persistence.qdrant.health.check_collection_health')
    @patch('app.persistence.qdrant.health.check_qdrant_connectivity')
    def test_overall_healthy(self, mock_connectivity, mock_collection):
        """Test when both connectivity and collection are healthy."""
        mock_connectivity.return_value = {
            "status": HealthStatus.HEALTHY,
            "message": "OK",
        }
        mock_collection.return_value = {
            "status": HealthStatus.HEALTHY,
            "message": "OK",
        }
        
        # Check overall health
        result = check_qdrant_health()
        
        # Verify healthy status
        assert result["status"] == HealthStatus.HEALTHY
    
    @patch('app.persistence.qdrant.health.check_collection_health')
    @patch('app.persistence.qdrant.health.check_qdrant_connectivity')
    def test_overall_degraded(self, mock_connectivity, mock_collection):
        """Test when one component is degraded."""
        mock_connectivity.return_value = {
            "status": HealthStatus.HEALTHY,
            "message": "OK",
        }
        mock_collection.return_value = {
            "status": HealthStatus.DEGRADED,
            "message": "Degraded",
        }
        
        # Check overall health
        result = check_qdrant_health()
        
        # Verify degraded status (worst of the two)
        assert result["status"] == HealthStatus.DEGRADED
    
    @patch('app.persistence.qdrant.health.check_collection_health')
    @patch('app.persistence.qdrant.health.check_qdrant_connectivity')
    def test_overall_unhealthy(self, mock_connectivity, mock_collection):
        """Test when one component is unhealthy."""
        mock_connectivity.return_value = {
            "status": HealthStatus.UNHEALTHY,
            "message": "Failed",
        }
        mock_collection.return_value = {
            "status": HealthStatus.HEALTHY,
            "message": "OK",
        }
        
        # Check overall health
        result = check_qdrant_health()
        
        # Verify unhealthy status (worst of the two)
        assert result["status"] == HealthStatus.UNHEALTHY


class TestHealthEndpoint:
    """Test health check endpoint response."""
    
    @patch('app.persistence.qdrant.health.check_qdrant_health')
    def test_endpoint_response_healthy(self, mock_health):
        """Test endpoint returns 200 for healthy status."""
        mock_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "connectivity": {"status": HealthStatus.HEALTHY},
            "collection": {"status": HealthStatus.HEALTHY},
        }
        
        # Get endpoint response
        response, status_code = get_health_check_endpoint_response()
        
        # Verify 200 status code
        assert status_code == 200
        assert response["status"] == HealthStatus.HEALTHY
    
    @patch('app.persistence.qdrant.health.check_qdrant_health')
    def test_endpoint_response_degraded(self, mock_health):
        """Test endpoint returns 200 for degraded status (still operational)."""
        mock_health.return_value = {
            "status": HealthStatus.DEGRADED,
            "connectivity": {"status": HealthStatus.HEALTHY},
            "collection": {"status": HealthStatus.DEGRADED},
        }
        
        # Get endpoint response
        response, status_code = get_health_check_endpoint_response()
        
        # Verify 200 status code (degraded but operational)
        assert status_code == 200
        assert response["status"] == HealthStatus.DEGRADED
    
    @patch('app.persistence.qdrant.health.check_qdrant_health')
    def test_endpoint_response_unhealthy(self, mock_health):
        """Test endpoint returns 503 for unhealthy status."""
        mock_health.return_value = {
            "status": HealthStatus.UNHEALTHY,
            "connectivity": {"status": HealthStatus.UNHEALTHY},
            "collection": {"status": HealthStatus.UNHEALTHY},
        }
        
        # Get endpoint response
        response, status_code = get_health_check_endpoint_response()
        
        # Verify 503 status code (service unavailable)
        assert status_code == 503
        assert response["status"] == HealthStatus.UNHEALTHY


class TestLogStats:
    """Test stats logging."""
    
    @patch('app.persistence.qdrant.health.logger')
    @patch('app.persistence.qdrant.health.check_qdrant_health')
    def test_log_stats_healthy(self, mock_health, mock_logger):
        """Test logging healthy stats."""
        mock_health.return_value = {
            "status": HealthStatus.HEALTHY,
            "connectivity": {"latency_ms": 15.3},
            "collection": {
                "collection": "test_collection",
                "points_count": 1000,
            },
        }
        
        # Log stats
        log_qdrant_stats()
        
        # Verify info log was called
        mock_logger.info.assert_called_once()
        log_message = mock_logger.info.call_args[0][0]
        assert "healthy" in log_message.lower()
    
    @patch('app.persistence.qdrant.health.logger')
    @patch('app.persistence.qdrant.health.check_qdrant_health')
    def test_log_stats_unhealthy(self, mock_health, mock_logger):
        """Test logging unhealthy stats."""
        mock_health.return_value = {
            "status": HealthStatus.UNHEALTHY,
            "message": "Connection failed",
        }
        
        # Log stats
        log_qdrant_stats()
        
        # Verify warning log was called
        mock_logger.warning.assert_called_once()
        log_message = mock_logger.warning.call_args[0][0]
        assert "unhealthy" in log_message.lower()
