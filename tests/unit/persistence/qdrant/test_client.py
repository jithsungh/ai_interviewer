"""
Unit Tests for Qdrant Client

Tests client initialization, retry logic, and error handling.
Uses mocks to avoid actual Qdrant connections.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from app.config.settings import QdrantSettings
from app.persistence.qdrant.client import (
    create_qdrant_client,
    init_qdrant_client,
    get_qdrant_client,
    get_collection_name,
    get_vector_dimension,
    cleanup_qdrant,
    QdrantConnectionError,
)


@pytest.fixture
def test_config():
    """Fixture providing test configuration."""
    return QdrantSettings(
        qdrant_url="http://100.95.213.103:6333",
        qdrant_api_key=None,
        qdrant_collection_name="test_collection",
        qdrant_embedding_dim=768,
        qdrant_search_timeout=10,
    )


@pytest.fixture(autouse=True)
def reset_global_client():
    """Reset global client state before each test."""
    import app.persistence.qdrant.client as client_module
    client_module._client = None
    client_module._collection_name = None
    client_module._vector_dimension = None
    yield
    client_module._client = None
    client_module._collection_name = None
    client_module._vector_dimension = None


class TestClientCreation:
    """Test Qdrant client creation."""
    
    @patch('app.persistence.qdrant.client.QdrantClient')
    def test_create_client_success(self, mock_qdrant_client, test_config):
        """Test successful client creation."""
        # Mock client and collections response
        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        
        mock_qdrant_client.return_value = mock_client
        
        # Create client
        client = create_qdrant_client(test_config)
        
        # Verify client was created
        assert client is not None
        mock_qdrant_client.assert_called_once()
        mock_client.get_collections.assert_called_once()
    
    @patch('app.persistence.qdrant.client.QdrantClient')
    def test_create_client_with_api_key(self, mock_qdrant_client, test_config):
        """Test client creation with API key."""
        test_config.qdrant_api_key = "test-api-key"
        
        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        
        mock_qdrant_client.return_value = mock_client
        
        # Create client
        client = create_qdrant_client(test_config)
        
        # Verify API key was passed
        call_kwargs = mock_qdrant_client.call_args[1]
        assert "api_key" in call_kwargs
        assert call_kwargs["api_key"] == "test-api-key"
    
    @patch('app.persistence.qdrant.client.QdrantClient')
    @patch('app.persistence.qdrant.client.time.sleep')
    def test_create_client_retry_success(self, mock_sleep, mock_qdrant_client, test_config):
        """Test client creation succeeds after retry."""
        # First attempt fails, second succeeds
        mock_client = MagicMock()
        mock_collections = MagicMock()
        mock_collections.collections = []
        
        # First call raises error, second call succeeds
        mock_client.get_collections.side_effect = [
            Exception("Connection refused"),
            mock_collections
        ]
        mock_qdrant_client.return_value = mock_client
        
        # Create client (should succeed on retry)
        client = create_qdrant_client(test_config)
        
        assert client is not None
        assert mock_sleep.call_count >= 1
    
    @patch('app.persistence.qdrant.client.QdrantClient')
    @patch('app.persistence.qdrant.client.time.sleep')
    def test_create_client_all_retries_fail(self, mock_sleep, mock_qdrant_client, test_config):
        """Test client creation fails after all retries."""
        # All attempts fail
        mock_client = MagicMock()
        mock_client.get_collections.side_effect = Exception("Connection refused")
        mock_qdrant_client.return_value = mock_client
        
        # Should raise QdrantConnectionError after retries
        with pytest.raises(QdrantConnectionError) as exc_info:
            create_qdrant_client(test_config)
        
        assert "unavailable" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 503
    
    @patch('app.persistence.qdrant.client.create_qdrant_client')
    def test_init_client(self, mock_create_client, test_config):
        """Test global client initialization."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Initialize client
        client = init_qdrant_client(test_config)
        
        assert client is not None
        assert client == mock_client
    
    @patch('app.persistence.qdrant.client.create_qdrant_client')
    def test_init_client_already_initialized(self, mock_create_client, test_config):
        """Test initializing client twice returns same instance."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # First initialization
        client1 = init_qdrant_client(test_config)
        
        # Second initialization (should not create new client)
        client2 = init_qdrant_client(test_config)
        
        assert client1 == client2
        # Should only create once
        mock_create_client.assert_called_once()


class TestClientGetters:
    """Test client getter functions."""
    
    @patch('app.persistence.qdrant.client.create_qdrant_client')
    def test_get_client_initialized(self, mock_create_client, test_config):
        """Test getting initialized client."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Initialize first
        init_qdrant_client(test_config)
        
        # Get client
        client = get_qdrant_client()
        assert client == mock_client
    
    def test_get_client_not_initialized(self):
        """Test getting client before initialization raises error."""
        with pytest.raises(RuntimeError) as exc_info:
            get_qdrant_client()
        
        assert "not initialized" in str(exc_info.value).lower()
    
    @patch('app.persistence.qdrant.client.create_qdrant_client')
    def test_get_collection_name(self, mock_create_client, test_config):
        """Test getting collection name after initialization."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Initialize
        init_qdrant_client(test_config)
        
        # Get collection name
        collection_name = get_collection_name()
        assert isinstance(collection_name, str)
        assert len(collection_name) > 0
    
    def test_get_collection_name_not_initialized(self):
        """Test getting collection name before initialization raises error."""
        with pytest.raises(RuntimeError) as exc_info:
            get_collection_name()
        
        assert "not initialized" in str(exc_info.value).lower()
    
    @patch('app.persistence.qdrant.client.create_qdrant_client')
    def test_get_vector_dimension(self, mock_create_client, test_config):
        """Test getting vector dimension after initialization."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Initialize
        init_qdrant_client(test_config)
        
        # Get dimension
        dimension = get_vector_dimension()
        assert dimension == test_config.qdrant_embedding_dim
    
    def test_get_vector_dimension_not_initialized(self):
        """Test getting dimension before initialization raises error."""
        with pytest.raises(RuntimeError) as exc_info:
            get_vector_dimension()
        
        assert "not initialized" in str(exc_info.value).lower()


class TestClientCleanup:
    """Test client cleanup."""
    
    @patch('app.persistence.qdrant.client.create_qdrant_client')
    def test_cleanup(self, mock_create_client):
        """Test cleanup clears global client."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        test_config = QdrantSettings(
            qdrant_url="http://localhost:6333",
            qdrant_collection_name="test",
            qdrant_embedding_dim=768,
        )
        
        # Initialize
        init_qdrant_client(test_config)
        
        # Verify initialized
        assert get_qdrant_client() is not None
        
        # Cleanup
        cleanup_qdrant()
        
        # Verify cleared
        with pytest.raises(RuntimeError):
            get_qdrant_client()
    
    def test_cleanup_not_initialized(self):
        """Test cleanup when not initialized doesn't raise error."""
        # Should not raise
        cleanup_qdrant()
