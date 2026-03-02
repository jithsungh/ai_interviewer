"""
Integration Tests for Qdrant Vector Operations

Tests actual vector storage, search, update, and delete operations.
Requires running Qdrant instance.
"""

import pytest
import os
import random
from typing import List
import dotenv

dotenv.load_dotenv()

from app.config.settings import QdrantSettings
from app.persistence.qdrant import (
    init_qdrant,
    store_embedding,
    store_embeddings_batch,
    search_embeddings,
    update_embedding_metadata,
    delete_embedding,
    delete_embeddings_by_source,
    get_embedding_by_id,
    cleanup_qdrant,
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
        qdrant_collection_name="test_vector_ops_collection",
        qdrant_embedding_dim=128,
        qdrant_search_timeout=10,
    )


@pytest.fixture(scope="module", autouse=True)
def setup_teardown_qdrant(qdrant_config):
    """Initialize and cleanup Qdrant for all tests."""
    import app.persistence.qdrant.client as client_module
    client_module._client = None
    client_module._collection_name = None
    client_module._vector_dimension = None
    
    try:
        init_qdrant(qdrant_config)
        yield
    finally:
        # Cleanup collection and client
        from app.persistence.qdrant import delete_collection
        try:
            delete_collection()
        except:
            pass
        cleanup_qdrant()


def generate_random_vector(dim: int = 128) -> List[float]:
    """Generate random vector for testing."""
    return [random.uniform(-1.0, 1.0) for _ in range(dim)]


class TestStoreOperations:
    """Test storing embeddings."""
    
    def test_store_single_embedding(self):
        """Test storing a single embedding."""
        vector = generate_random_vector()
        
        point_id = store_embedding(
            vector=vector,
            organization_id=1,
            source_type="question",
            source_id=100,
            model_name="test-model",
            model_version="v1",
            difficulty="medium",
            topic_id=5,
        )
        
        # Verify point_id returned
        assert isinstance(point_id, str)
        assert len(point_id) > 0
        
        # Verify can retrieve
        result = get_embedding_by_id(point_id)
        assert result is not None
        assert result["organization_id"] == 1
        assert result["source_type"] == "question"
        assert result["source_id"] == 100
    
    def test_store_batch_embeddings(self):
        """Test storing batch of embeddings."""
        embeddings = [
            {
                "vector": generate_random_vector(),
                "organization_id": 1,
                "source_type": "question",
                "source_id": 200 + i,
                "model_name": "test-model",
                "model_version": "v1",
                "difficulty": "easy",
            }
            for i in range(10)
        ]
        
        point_ids = store_embeddings_batch(embeddings)
        
        # Verify 10 point_ids returned
        assert len(point_ids) == 10
        assert all(isinstance(pid, str) for pid in point_ids)
        
        # Verify first embedding can be retrieved
        result = get_embedding_by_id(point_ids[0])
        assert result is not None
        assert result["source_type"] == "question"


class TestSearchOperations:
    """Test searching embeddings."""
    
    @pytest.fixture(autouse=True, scope="class")
    def setup_search_data(self):
        """Setup test data for search."""
        # Store embeddings with different organizations and difficulties
        embeddings = []
        
        # Org 1 - easy questions
        for i in range(5):
            embeddings.append({
                "vector": generate_random_vector(),
                "organization_id": 1,
                "source_type": "question",
                "source_id": 1000 + i,
                "model_name": "test-model",
                "model_version": "v1",
                "difficulty": "easy",
                "topic_id": 1,
                "scope": "public",
            })
        
        # Org 1 - hard questions
        for i in range(5):
            embeddings.append({
                "vector": generate_random_vector(),
                "organization_id": 1,
                "source_type": "question",
                "source_id": 2000 + i,
                "model_name": "test-model",
                "model_version": "v1",
                "difficulty": "hard",
                "topic_id": 2,
                "scope": "public",
            })
        
        # Org 2 - questions
        for i in range(5):
            embeddings.append({
                "vector": generate_random_vector(),
                "organization_id": 2,
                "source_type": "question",
                "source_id": 3000 + i,
                "model_name": "test-model",
                "model_version": "v1",
                "difficulty": "medium",
                "topic_id": 1,
                "scope": "organization",
            })
        
        store_embeddings_batch(embeddings)
    
    def test_search_basic(self):
        """Test basic search without filters."""
        query_vector = generate_random_vector()
        
        results = search_embeddings(
            query_vector=query_vector,
            organization_id=1,
            top_k=10,
            score_threshold=0.0,  # Accept all results
        )
        
        # Should return results from org 1 only
        assert len(results) <= 10
        assert all(r["organization_id"] == 1 for r in results)
    
    def test_search_with_difficulty_filter(self):
        """Test search with difficulty filter."""
        query_vector = generate_random_vector()
        
        results = search_embeddings(
            query_vector=query_vector,
            organization_id=1,
            difficulty="easy",
            top_k=10,
            score_threshold=0.0,
        )
        
        # Should return only easy questions from org 1
        assert all(r["organization_id"] == 1 for r in results)
        assert all(r["difficulty"] == "easy" for r in results)
    
    def test_search_with_topic_filter(self):
        """Test search with topic filter."""
        query_vector = generate_random_vector()
        
        results = search_embeddings(
            query_vector=query_vector,
            organization_id=1,
            topic_id=1,
            top_k=10,
            score_threshold=0.0,
        )
        
        # Should return only topic 1 questions from org 1
        assert all(r["organization_id"] == 1 for r in results)
        assert all(r["topic_id"] == 1 for r in results)
    
    def test_search_tenant_isolation(self):
        """Test multi-tenant isolation in search."""
        query_vector = generate_random_vector()
        
        # Search org 1
        results_org1 = search_embeddings(
            query_vector=query_vector,
            organization_id=1,
            top_k=10,
            score_threshold=0.0,
        )
        
        # Search org 2
        results_org2 = search_embeddings(
            query_vector=query_vector,
            organization_id=2,
            top_k=10,
            score_threshold=0.0,
        )
        
        # Verify isolation
        assert all(r["organization_id"] == 1 for r in results_org1)
        assert all(r["organization_id"] == 2 for r in results_org2)
        
        # Verify no cross-org results
        org1_ids = {r["point_id"] for r in results_org1}
        org2_ids = {r["point_id"] for r in results_org2}
        assert org1_ids.isdisjoint(org2_ids)


class TestUpdateOperations:
    """Test updating embeddings."""
    
    def test_update_embedding_metadata(self):
        """Test updating embedding metadata."""
        # Store embedding
        vector = generate_random_vector()
        point_id = store_embedding(
            vector=vector,
            organization_id=1,
            source_type="question",
            source_id=9000,
            model_name="test-model",
            model_version="v1",
            difficulty="easy",
        )
        
        # Update metadata
        update_embedding_metadata(
            point_id=point_id,
            metadata_updates={"difficulty": "hard"}
        )
        
        # Verify updated
        result = get_embedding_by_id(point_id)
        assert result["difficulty"] == "hard"


class TestDeleteOperations:
    """Test deleting embeddings."""
    
    def test_delete_single_embedding(self):
        """Test deleting a single embedding."""
        # Store embedding
        vector = generate_random_vector()
        point_id = store_embedding(
            vector=vector,
            organization_id=1,
            source_type="question",
            source_id=8000,
            model_name="test-model",
            model_version="v1",
        )
        
        # Verify exists
        assert get_embedding_by_id(point_id) is not None
        
        # Delete
        delete_embedding(point_id)
        
        # Verify deleted
        assert get_embedding_by_id(point_id) is None
    
    def test_delete_by_source(self):
        """Test bulk delete by source."""
        # Store multiple embeddings for same source
        source_id = 7000
        point_ids = []
        
        for i in range(3):
            vector = generate_random_vector()
            point_id = store_embedding(
                vector=vector,
                organization_id=1,
                source_type="question",
                source_id=source_id,
                model_name="test-model",
                model_version="v1",
            )
            point_ids.append(point_id)
        
        # Verify all exist
        for point_id in point_ids:
            assert get_embedding_by_id(point_id) is not None
        
        # Delete by source
        delete_embeddings_by_source(
            source_type="question",
            source_id=source_id,
            organization_id=1
        )
        
        # Verify all deleted
        for point_id in point_ids:
            assert get_embedding_by_id(point_id) is None


class TestPerformance:
    """Test performance characteristics."""
    
    def test_batch_insert_performance(self):
        """Test batch insert can handle large volumes."""
        # Create 100 embeddings
        embeddings = [
            {
                "vector": generate_random_vector(),
                "organization_id": 10,
                "source_type": "question",
                "source_id": 10000 + i,
                "model_name": "test-model",
                "model_version": "v1",
            }
            for i in range(100)
        ]
        
        import time
        start_time = time.perf_counter()
        
        # Store batch (should be < 5 seconds)
        point_ids = store_embeddings_batch(embeddings, batch_size=50)
        
        elapsed = time.perf_counter() - start_time
        
        # Verify all stored
        assert len(point_ids) == 100
        
        # Verify reasonable performance (< 5s for 100 vectors)
        assert elapsed < 5.0, f"Batch insert took {elapsed:.2f}s (expected < 5s)"
    
    def test_search_performance(self):
        """Test search performance."""
        query_vector = generate_random_vector()
        
        import time
        start_time = time.perf_counter()
        
        # Search (should be < 1 second)
        results = search_embeddings(
            query_vector=query_vector,
            organization_id=10,
            top_k=10,
            score_threshold=0.0,
        )
        
        elapsed = time.perf_counter() - start_time
        
        # Verify reasonable performance (< 1s)
        assert elapsed < 1.0, f"Search took {elapsed:.2f}s (expected < 1s)"
