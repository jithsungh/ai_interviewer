"""
Unit Tests for Qdrant Operations

Tests vector storage, search, update, and delete operations.
Uses mocks to avoid actual Qdrant operations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.persistence.qdrant.operations import (
    validate_vector_dimension,
    store_embedding,
    store_embeddings_batch,
    search_embeddings,
    update_embedding_metadata,
    delete_embedding,
    delete_embeddings_by_source,
    get_embedding_by_id,
)
from app.persistence.qdrant.client import QdrantCollectionError
from app.shared.errors import ValidationError


@pytest.fixture
def mock_client():
    """Mock Qdrant client."""
    return MagicMock()


@pytest.fixture
def sample_vector():
    """Sample 768-dimensional vector."""
    return [0.1] * 768


@pytest.fixture
def sample_metadata():
    """Sample metadata for embedding."""
    return {
        "organization_id": 1,
        "source_type": "question",
        "source_id": 100,
        "model_name": "all-mpnet-base-v2",
        "model_version": "v2",
        "difficulty": "medium",
        "topic_id": 5,
        "scope": "public",
    }


class TestVectorValidation:
    """Test vector dimension validation."""
    
    @patch('app.persistence.qdrant.operations.get_vector_dimension')
    def test_validate_correct_dimension(self, mock_get_dimension, sample_vector):
        """Test validation passes with correct dimension."""
        mock_get_dimension.return_value = 768
        
        # Should not raise
        validate_vector_dimension(sample_vector)
    
    @patch('app.persistence.qdrant.operations.get_vector_dimension')
    def test_validate_incorrect_dimension(self, mock_get_dimension):
        """Test validation fails with incorrect dimension."""
        mock_get_dimension.return_value = 768
        wrong_vector = [0.1] * 1536  # Wrong dimension
        
        with pytest.raises(ValidationError) as exc_info:
            validate_vector_dimension(wrong_vector)
        
        assert "dimension mismatch" in str(exc_info.value).lower()
        assert exc_info.value.status_code == 422


class TestStoreEmbedding:
    """Test storing single embedding."""
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    @patch('app.persistence.qdrant.operations.validate_vector_dimension')
    def test_store_embedding_success(
        self,
        mock_validate,
        mock_get_client,
        mock_get_collection,
        mock_client,
        sample_vector,
        sample_metadata
    ):
        """Test successful embedding storage."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Store embedding
        point_id = store_embedding(
            vector=sample_vector,
            **sample_metadata
        )
        
        # Verify point_id is UUID
        assert isinstance(point_id, str)
        assert len(point_id) > 0
        
        # Verify validation was called
        mock_validate.assert_called_once_with(sample_vector)
        
        # Verify upsert was called
        mock_client.upsert.assert_called_once()
        call_args = mock_client.upsert.call_args
        assert call_args[1]["collection_name"] == "test_collection"
        assert len(call_args[1]["points"]) == 1
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    @patch('app.persistence.qdrant.operations.validate_vector_dimension')
    def test_store_embedding_with_optional_fields(
        self,
        mock_validate,
        mock_get_client,
        mock_get_collection,
        mock_client,
        sample_vector
    ):
        """Test storing embedding with only required fields."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Store with minimal metadata
        point_id = store_embedding(
            vector=sample_vector,
            organization_id=1,
            source_type="question",
            source_id=100,
            model_name="test-model",
            model_version="v1",
        )
        
        assert point_id is not None
        mock_client.upsert.assert_called_once()
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    @patch('app.persistence.qdrant.operations.validate_vector_dimension')
    def test_store_embedding_client_error(
        self,
        mock_validate,
        mock_get_client,
        mock_get_collection,
        mock_client,
        sample_vector,
        sample_metadata
    ):
        """Test store embedding handles client errors."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        mock_client.upsert.side_effect = Exception("Qdrant error")
        
        with pytest.raises(QdrantCollectionError) as exc_info:
            store_embedding(vector=sample_vector, **sample_metadata)
        
        assert "storage failed" in str(exc_info.value).lower()


class TestStoreEmbeddingsBatch:
    """Test batch embedding storage."""
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    @patch('app.persistence.qdrant.operations.validate_vector_dimension')
    def test_store_batch_success(
        self,
        mock_validate,
        mock_get_client,
        mock_get_collection,
        mock_client,
        sample_vector,
        sample_metadata
    ):
        """Test successful batch storage."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Create batch of 3 embeddings
        embeddings = [
            {"vector": sample_vector, **sample_metadata},
            {"vector": sample_vector, **sample_metadata},
            {"vector": sample_vector, **sample_metadata},
        ]
        
        # Store batch
        point_ids = store_embeddings_batch(embeddings)
        
        # Verify returned 3 point_ids
        assert len(point_ids) == 3
        assert all(isinstance(pid, str) for pid in point_ids)
        
        # Verify upsert was called once (batch_size default is 100)
        mock_client.upsert.assert_called_once()
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    @patch('app.persistence.qdrant.operations.validate_vector_dimension')
    def test_store_batch_multiple_batches(
        self,
        mock_validate,
        mock_get_client,
        mock_get_collection,
        mock_client,
        sample_vector,
        sample_metadata
    ):
        """Test batch storage splits into multiple batches."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Create 250 embeddings (should split into 3 batches of 100)
        embeddings = [
            {"vector": sample_vector, **sample_metadata}
            for _ in range(250)
        ]
        
        # Store batch with batch_size=100
        point_ids = store_embeddings_batch(embeddings, batch_size=100)
        
        # Verify returned 250 point_ids
        assert len(point_ids) == 250
        
        # Verify upsert called 3 times (3 batches)
        assert mock_client.upsert.call_count == 3


class TestSearchEmbeddings:
    """Test embedding search."""
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    @patch('app.persistence.qdrant.operations.validate_vector_dimension')
    def test_search_basic(
        self,
        mock_validate,
        mock_get_client,
        mock_get_collection,
        mock_client,
        sample_vector
    ):
        """Test basic search without filters."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Mock search results
        mock_result = MagicMock()
        mock_result.id = "point-1"
        mock_result.score = 0.95
        mock_result.payload = {
            "organization_id": 1,
            "source_type": "question",
            "source_id": 100,
            "model_name": "test-model",
            "model_version": "v1",
        }
        mock_client.search.return_value = [mock_result]
        
        # Search
        results = search_embeddings(
            query_vector=sample_vector,
            organization_id=1,
            top_k=10,
        )
        
        # Verify results
        assert len(results) == 1
        assert results[0]["point_id"] == "point-1"
        assert results[0]["score"] == 0.95
        assert results[0]["organization_id"] == 1
        
        # Verify search was called with organization filter
        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args[1]
        assert call_kwargs["query_filter"] is not None
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    @patch('app.persistence.qdrant.operations.validate_vector_dimension')
    def test_search_with_filters(
        self,
        mock_validate,
        mock_get_client,
        mock_get_collection,
        mock_client,
        sample_vector
    ):
        """Test search with multiple filters."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        mock_client.search.return_value = []
        
        # Search with filters
        results = search_embeddings(
            query_vector=sample_vector,
            organization_id=1,
            source_type="question",
            difficulty="medium",
            topic_id=5,
            scope="public",
        )
        
        # Verify search called with filters
        mock_client.search.assert_called_once()
        call_kwargs = mock_client.search.call_args[1]
        
        # Verify filter includes all conditions
        filter_obj = call_kwargs["query_filter"]
        assert filter_obj is not None
        # Should have 5 conditions (org + source_type + difficulty + topic + scope)
        assert len(filter_obj.must) == 5


class TestDeleteOperations:
    """Test delete operations."""
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    def test_delete_embedding(
        self,
        mock_get_client,
        mock_get_collection,
        mock_client
    ):
        """Test deleting single embedding."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Delete
        delete_embedding("point-123")
        
        # Verify delete called
        mock_client.delete.assert_called_once()
        call_kwargs = mock_client.delete.call_args[1]
        assert call_kwargs["collection_name"] == "test_collection"
        assert "point-123" in call_kwargs["points_selector"]
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    def test_delete_by_source(
        self,
        mock_get_client,
        mock_get_collection,
        mock_client
    ):
        """Test bulk delete by source."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Delete by source
        delete_embeddings_by_source(
            source_type="question",
            source_id=100,
            organization_id=1
        )
        
        # Verify delete called with filter
        mock_client.delete.assert_called_once()
        call_kwargs = mock_client.delete.call_args[1]
        
        # Verify filter includes org, source_type, and source_id
        filter_obj = call_kwargs["points_selector"]
        assert filter_obj is not None
        assert len(filter_obj.must) == 3


class TestUpdateMetadata:
    """Test metadata updates."""
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    def test_update_metadata(
        self,
        mock_get_client,
        mock_get_collection,
        mock_client
    ):
        """Test updating embedding metadata."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Update metadata
        updates = {"difficulty": "hard", "updated_at": datetime.utcnow().isoformat()}
        update_embedding_metadata("point-123", updates)
        
        # Verify set_payload called
        mock_client.set_payload.assert_called_once()
        call_kwargs = mock_client.set_payload.call_args[1]
        assert call_kwargs["payload"] == updates
        assert "point-123" in call_kwargs["points"]


class TestGetEmbedding:
    """Test retrieving embedding metadata."""
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    def test_get_existing_embedding(
        self,
        mock_get_client,
        mock_get_collection,
        mock_client
    ):
        """Test retrieving existing embedding."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        
        # Mock retrieve result
        mock_point = MagicMock()
        mock_point.id = "point-123"
        mock_point.payload = {
            "organization_id": 1,
            "source_type": "question",
            "source_id": 100,
        }
        mock_client.retrieve.return_value = [mock_point]
        
        # Get embedding
        result = get_embedding_by_id("point-123")
        
        # Verify result
        assert result is not None
        assert result["point_id"] == "point-123"
        assert result["organization_id"] == 1
        
        # Verify retrieve called without vectors
        mock_client.retrieve.assert_called_once()
        call_kwargs = mock_client.retrieve.call_args[1]
        assert call_kwargs["with_vectors"] is False
    
    @patch('app.persistence.qdrant.operations.get_collection_name')
    @patch('app.persistence.qdrant.operations.get_qdrant_client')
    def test_get_nonexistent_embedding(
        self,
        mock_get_client,
        mock_get_collection,
        mock_client
    ):
        """Test retrieving non-existent embedding returns None."""
        mock_get_client.return_value = mock_client
        mock_get_collection.return_value = "test_collection"
        mock_client.retrieve.return_value = []
        
        # Get embedding
        result = get_embedding_by_id("nonexistent")
        
        # Verify None returned
        assert result is None
