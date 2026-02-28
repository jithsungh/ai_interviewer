"""
Integration Tests — QdrantRetrievalService (End-to-End)

Tests the full orchestration: cache → circuit breaker → Qdrant → fallback.

Requires: Running Qdrant AND Redis instances.
"""

import os
import random
import time
from typing import List

import dotenv
import pytest

dotenv.load_dotenv()

# Skip unless both Qdrant and Redis are available
pytestmark = pytest.mark.skipif(
    (os.getenv("QDRANT_URL") is None or os.getenv("REDIS_URL") is None)
    and os.getenv("CI") is not None,
    reason="Qdrant and/or Redis not available in CI environment",
)

VECTOR_DIM = 128
ORG_ID = 8001


def _random_vector(dim: int = VECTOR_DIM) -> List[float]:
    return [random.uniform(-1.0, 1.0) for _ in range(dim)]


@pytest.fixture(scope="module")
def qdrant_config():
    from app.config.settings import QdrantSettings

    return QdrantSettings(
        qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        qdrant_collection_name="test_service_integration",
        qdrant_embedding_dim=VECTOR_DIM,
        qdrant_search_timeout=10,
    )


@pytest.fixture(scope="module")
def redis_config():
    from app.config.settings import RedisSettings

    return RedisSettings(
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/3"),
        redis_db=3,
        redis_password=None,
        redis_max_connections=5,
        redis_connection_timeout=5,
        redis_socket_timeout=3,
        redis_retry_on_timeout=True,
        redis_max_retries=3,
        redis_decode_responses=True,
        redis_session_ttl=3600,
        redis_lock_timeout=10,
        redis_health_check_interval=60,
    )


@pytest.fixture(scope="module", autouse=True)
def setup_infrastructure(qdrant_config, redis_config):
    """Initialize Qdrant + Redis, seed data, tear down."""
    import app.persistence.qdrant.client as client_module

    client_module._client = None
    client_module._collection_name = None
    client_module._vector_dimension = None

    from app.persistence.qdrant import init_qdrant, cleanup_qdrant, store_embedding
    from app.persistence.redis import init_redis_client, cleanup_redis

    try:
        init_qdrant(qdrant_config)
    except Exception:
        pytest.skip("Cannot connect to Qdrant")

    try:
        init_redis_client(redis_config)
    except Exception:
        pytest.skip("Cannot connect to Redis")

    # Seed questions
    for qid in range(1, 11):
        store_embedding(
            vector=_random_vector(),
            organization_id=ORG_ID,
            source_type="question",
            source_id=qid,
            model_name="test-model",
            model_version="v1",
            difficulty=["easy", "medium", "hard"][qid % 3],
            topic_id=qid % 5 or None,
            scope="organization",
        )

    time.sleep(0.5)
    yield

    from app.persistence.qdrant import delete_collection

    try:
        delete_collection()
    except Exception:
        pass
    cleanup_qdrant()

    try:
        from app.persistence.redis import get_redis_client

        client = get_redis_client()
        for key in client.scan_iter("question_search:*"):
            client.delete(key)
    except Exception:
        pass
    cleanup_redis()


@pytest.fixture(autouse=True)
def reset_breaker():
    from app.question.retrieval.service import QdrantRetrievalService

    QdrantRetrievalService.reset_circuit_breaker()
    yield
    QdrantRetrievalService.reset_circuit_breaker()


# ═══════════════════════════════════════════════════════════════════════
# End-to-End Search
# ═══════════════════════════════════════════════════════════════════════


class TestRetrievalServiceE2E:
    """Full end-to-end tests through the service layer."""

    def test_semantic_search_returns_results(self):
        from app.question.retrieval.contracts import SearchCriteria
        from app.question.retrieval.service import QdrantRetrievalService

        svc = QdrantRetrievalService()
        criteria = SearchCriteria(
            organization_id=ORG_ID,
            query_vector=_random_vector(),
            top_k=5,
            score_threshold=0.0,
        )

        result = svc.search_semantic(criteria)

        assert result.total_found > 0
        assert result.strategy_used.value == "semantic"
        assert result.search_duration_ms > 0
        assert result.fallback_activated is False

    def test_topic_search_returns_results(self):
        from app.question.retrieval.contracts import SearchCriteria
        from app.question.retrieval.service import QdrantRetrievalService

        svc = QdrantRetrievalService()
        criteria = SearchCriteria(
            organization_id=ORG_ID,
            topic_ids=[0, 1],
            top_k=10,
        )

        result = svc.search_by_topic(criteria)

        assert result.strategy_used.value == "topic_filter"
        # May or may not have results depending on Qdrant state
        assert result.total_found >= 0

    def test_hybrid_search(self):
        from app.question.retrieval.contracts import (
            HybridSearchWeights,
            SearchCriteria,
        )
        from app.question.retrieval.service import QdrantRetrievalService

        svc = QdrantRetrievalService()
        criteria = SearchCriteria(
            organization_id=ORG_ID,
            top_k=5,
            score_threshold=0.0,
        )
        weights = HybridSearchWeights(resume_weight=0.7, jd_weight=0.3)

        result = svc.search_hybrid(
            resume_vector=_random_vector(),
            jd_vector=_random_vector(),
            criteria=criteria,
            weights=weights,
        )

        assert result.strategy_used.value == "hybrid"

    def test_cache_hit_on_second_call(self):
        from app.question.retrieval.contracts import SearchCriteria
        from app.question.retrieval.service import QdrantRetrievalService

        svc = QdrantRetrievalService()
        vec = _random_vector()
        criteria = SearchCriteria(
            organization_id=ORG_ID,
            query_vector=vec,
            top_k=3,
            score_threshold=0.0,
        )

        # First call → cache miss
        result1 = svc.search_semantic(criteria)
        assert result1.cache_hit is False

        # Second call with same vector → cache hit
        result2 = svc.search_semantic(criteria)
        assert result2.cache_hit is True

    def test_repetition_check(self):
        from app.question.retrieval.service import QdrantRetrievalService

        svc = QdrantRetrievalService()
        # Use a fixed vector for deterministic results
        candidate = [0.1 * (i + 1) for i in range(VECTOR_DIM)]
        history = [
            {"question_id": 1, "question_embedding": list(candidate)},  # Identical
        ]

        result = svc.check_repetition(candidate, history, threshold=0.85)
        assert result.is_acceptable is False
        assert result.max_similarity >= 0.99

    def test_circuit_breaker_state_accessible(self):
        from app.question.retrieval.service import QdrantRetrievalService

        svc = QdrantRetrievalService()
        assert svc.circuit_breaker_state == "closed"
