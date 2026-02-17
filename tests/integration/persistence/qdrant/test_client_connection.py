"""
Integration Tests for Qdrant Client

Tests actual Qdrant client initialization and connection.
Requires running Qdrant instance (localhost:6333).
"""

import pytest
import os
from unittest.mock import patch
import dotenv

dotenv.load_dotenv()

from app.config.settings import QdrantSettings
from app.persistence.qdrant import (
    init_qdrant,
    get_qdrant_client,
    get_collection_name,
    cleanup_qdrant,
    check_qdrant_connectivity,
    HealthStatus,
)


# Skip tests if Qdrant not available
pytestmark = pytest.mark.skipif(
    os.getenv("QDRANT_URL") is None and os.getenv("CI") is not None,
    reason="Qdrant not available in CI environment"
)


@pytest.fixture(scope="module")
def qdrant_config():
    """Fixture providing test Qdrant configuration."""
    return QdrantSettings(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        qdrant_collection_name="test_integration_collection",
        qdrant_embedding_dim=128,  # Smaller dimension for testing
        qdrant_search_timeout=10,
    )


@pytest.fixture(scope="module", autouse=True)
def setup_teardown_qdrant(qdrant_config):
    """Initialize and cleanup Qdrant for all tests."""
    # Reset global state
    import app.persistence.qdrant.client as client_module
    client_module._client = None
    client_module._collection_name = None
    client_module._vector_dimension = None
    
    # Initialize
    try:
        init_qdrant(qdrant_config)
        yield
    finally:
        # Cleanup
        cleanup_qdrant()


class TestClientConnection:
    """Test actual Qdrant client connection."""
    
    def test_client_initialized(self):
        """Test client is initialized."""
        client = get_qdrant_client()
        assert client is not None
    
    def test_connectivity_check(self):
        """Test connectivity check succeeds."""
        result = check_qdrant_connectivity()
        
        # Should be healthy
        assert result["status"] == HealthStatus.HEALTHY
        assert result["collections_count"] >= 0
        assert "latency_ms" in result
    
    def test_list_collections(self):
        """Test listing collections."""
        client = get_qdrant_client()
        collections = client.get_collections()
        
        # Should return collections list
        assert hasattr(collections, "collections")
        
        # Test collection should exist (with environment suffix)
        collection_names = [c.name for c in collections.collections]
        expected_collection = get_collection_name()
        assert expected_collection in collection_names
