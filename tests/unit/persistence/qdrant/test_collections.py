"""
Unit Tests for Qdrant Collections

Tests collection creation, validation, and management.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from qdrant_client.models import CollectionStatus

from app.persistence.qdrant.collections import (
    create_collection_if_not_exists,
    validate_collection_schema,
    delete_collection,
    get_collection_info,
)
from app.persistence.qdrant.client import QdrantCollectionError


@pytest.fixture
def mock_client():
    """Mock Qdrant client."""
    return MagicMock()


class TestCreateCollection:
    """Test collection creation."""
    
    @patch('app.persistence.qdrant.collections.get_vector_dimension')
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_create_collection_success(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_get_dimension,
        mock_client
    ):
        """Test creating new collection successfully."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        mock_get_dimension.return_value = 768
        
        # Mock no existing collections
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        
        # Create collection
        create_collection_if_not_exists()
        
        # Verify create_collection was called
        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args[1]
        assert call_kwargs["collection_name"] == "test_collection"
        assert call_kwargs["vectors_config"].size == 768
    
    @patch('app.persistence.qdrant.collections.validate_collection_schema')
    @patch('app.persistence.qdrant.collections.get_vector_dimension')
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_create_collection_already_exists(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_get_dimension,
        mock_validate,
        mock_client
    ):
        """Test when collection already exists."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        mock_get_dimension.return_value = 768
        
        # Mock existing collection
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        mock_collections = MagicMock()
        mock_collections.collections = [mock_collection]
        mock_client.get_collections.return_value = mock_collections
        
        # Create collection (should skip)
        create_collection_if_not_exists()
        
        # Verify create_collection was NOT called
        mock_client.create_collection.assert_not_called()
        
        # Verify validation was called
        mock_validate.assert_called_once()
    
    @patch('app.persistence.qdrant.collections.get_vector_dimension')
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_create_collection_error(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_get_dimension,
        mock_client
    ):
        """Test collection creation error handling."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        mock_get_dimension.return_value = 768
        
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        mock_client.create_collection.side_effect = Exception("Creation failed")
        
        # Should raise QdrantCollectionError
        with pytest.raises(QdrantCollectionError) as exc_info:
            create_collection_if_not_exists()
        
        assert "creation failed" in str(exc_info.value).lower()


class TestValidateSchema:
    """Test collection schema validation."""
    
    @patch('app.persistence.qdrant.collections.get_vector_dimension')
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_validate_schema_success(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_get_dimension,
        mock_client
    ):
        """Test schema validation succeeds."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        mock_get_dimension.return_value = 768
        
        # Mock collection info
        mock_info = MagicMock()
        mock_info.config.params.vectors.size = 768
        mock_info.status = CollectionStatus.GREEN
        mock_info.points_count = 100
        mock_client.get_collection.return_value = mock_info
        
        # Should not raise
        validate_collection_schema()
    
    @patch('app.persistence.qdrant.collections.get_vector_dimension')
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_validate_schema_dimension_mismatch(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_get_dimension,
        mock_client
    ):
        """Test schema validation fails on dimension mismatch."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        mock_get_dimension.return_value = 768
        
        # Mock collection with wrong dimension
        mock_info = MagicMock()
        mock_info.config.params.vectors.size = 1536  # Wrong dimension
        mock_client.get_collection.return_value = mock_info
        
        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            validate_collection_schema()
        
        assert "dimension mismatch" in str(exc_info.value).lower()


class TestDeleteCollection:
    """Test collection deletion."""
    
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_delete_collection_success(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_client
    ):
        """Test successful collection deletion."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        
        # Delete collection
        delete_collection()
        
        # Verify delete_collection was called
        mock_client.delete_collection.assert_called_once_with("test_collection")
    
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_delete_collection_error(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_client
    ):
        """Test collection deletion error handling."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        mock_client.delete_collection.side_effect = Exception("Deletion failed")
        
        # Should raise QdrantCollectionError
        with pytest.raises(QdrantCollectionError) as exc_info:
            delete_collection()
        
        assert "deletion failed" in str(exc_info.value).lower()


class TestGetCollectionInfo:
    """Test getting collection information."""
    
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_get_collection_info_success(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_client
    ):
        """Test retrieving collection info successfully."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        
        # Mock collection info
        mock_info = MagicMock()
        mock_info.points_count = 1000
        mock_info.vectors_count = 1000
        mock_info.segments_count = 2
        mock_info.status = CollectionStatus.GREEN
        mock_info.optimizer_status.ok = True
        mock_info.config.params.vectors.size = 768
        mock_info.config.params.vectors.distance.value = "Cosine"
        mock_client.get_collection.return_value = mock_info
        
        # Get info
        info = get_collection_info()
        
        # Verify info structure
        assert info["name"] == "test_collection"
        assert info["points_count"] == 1000
        assert info["vector_dimension"] == 768
        assert info["status"] == "green"
        assert info["optimizer_status"] is True
    
    @patch('app.persistence.qdrant.collections.get_collection_name')
    @patch('app.persistence.qdrant.collections.get_qdrant_client')
    def test_get_collection_info_error(
        self,
        mock_get_client,
        mock_get_collection_name,
        mock_client
    ):
        """Test error handling when getting collection info."""
        mock_get_client.return_value = mock_client
        mock_get_collection_name.return_value = "test_collection"
        mock_client.get_collection.side_effect = Exception("Info retrieval failed")
        
        # Should raise QdrantCollectionError
        with pytest.raises(QdrantCollectionError) as exc_info:
            get_collection_info()
        
        assert "info retrieval failed" in str(exc_info.value).lower()
