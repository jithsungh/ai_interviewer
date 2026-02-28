"""
Integration Tests — RetrievalCacheRepository

Tests actual Redis cache operations for retrieval results.

Requires: Running Redis instance (REDIS_URL env var).
"""

import os
import time

import dotenv
import pytest

dotenv.load_dotenv()

from app.config.settings import RedisSettings

# Skip if Redis not available
pytestmark = pytest.mark.skipif(
    os.getenv("REDIS_URL") is None and os.getenv("CI") is not None,
    reason="Redis not available in CI environment",
)


@pytest.fixture(scope="module")
def redis_config():
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/2")
    return RedisSettings(
        redis_url=redis_url,
        redis_db=2,  # Test database
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
def setup_redis(redis_config):
    from app.persistence.redis import init_redis_client, cleanup_redis

    try:
        init_redis_client(redis_config)
    except Exception:
        pytest.skip("Cannot connect to Redis")

    yield

    # Clean up test keys
    try:
        from app.persistence.redis import get_redis_client

        client = get_redis_client()
        for key in client.scan_iter("question_search:*"):
            client.delete(key)
    except Exception:
        pass
    cleanup_redis()


# ═══════════════════════════════════════════════════════════════════════
# Cache Round-Trip
# ═══════════════════════════════════════════════════════════════════════


class TestCacheRoundTrip:
    """Tests for store → get_cached → invalidate cycle."""

    def test_store_and_retrieve(self):
        from app.question.retrieval.contracts import (
            QuestionCandidate,
            RetrievalResult,
            RetrievalStrategy,
        )
        from app.question.retrieval.persistence.cache_repository import (
            RetrievalCacheRepository,
        )

        repo = RetrievalCacheRepository(ttl_seconds=60)

        result = RetrievalResult(
            candidates=[
                QuestionCandidate(question_id=1, similarity_score=0.9),
                QuestionCandidate(question_id=2, similarity_score=0.8),
            ],
            strategy_used=RetrievalStrategy.SEMANTIC,
            total_found=2,
            search_duration_ms=12.5,
        )

        vector_hash = repo.compute_vector_hash([0.1, 0.2, 0.3])

        repo.store(
            organization_id=1,
            difficulty="medium",
            topic_ids=[5, 10],
            vector_hash=vector_hash,
            result=result,
        )

        cached = repo.get_cached(
            organization_id=1,
            difficulty="medium",
            topic_ids=[5, 10],
            vector_hash=vector_hash,
        )

        assert cached is not None
        assert cached.cache_hit is True
        assert cached.total_found == 2
        assert len(cached.candidates) == 2
        assert cached.candidates[0].question_id == 1

    def test_cache_miss(self):
        from app.question.retrieval.persistence.cache_repository import (
            RetrievalCacheRepository,
        )

        repo = RetrievalCacheRepository()
        result = repo.get_cached(
            organization_id=99999,
            difficulty="easy",
            topic_ids=None,
            vector_hash="nonexistent",
        )
        assert result is None

    def test_invalidate_removes_entry(self):
        from app.question.retrieval.contracts import (
            QuestionCandidate,
            RetrievalResult,
            RetrievalStrategy,
        )
        from app.question.retrieval.persistence.cache_repository import (
            RetrievalCacheRepository,
        )

        repo = RetrievalCacheRepository(ttl_seconds=60)

        result = RetrievalResult(
            candidates=[QuestionCandidate(question_id=42, similarity_score=0.7)],
            strategy_used=RetrievalStrategy.SEMANTIC,
            total_found=1,
            search_duration_ms=5.0,
        )

        repo.store(
            organization_id=2,
            difficulty=None,
            topic_ids=None,
            vector_hash="testhash",
            result=result,
        )

        # Verify stored
        cached = repo.get_cached(
            organization_id=2,
            difficulty=None,
            topic_ids=None,
            vector_hash="testhash",
        )
        assert cached is not None

        # Invalidate
        repo.invalidate(
            organization_id=2,
            difficulty=None,
            topic_ids=None,
            vector_hash="testhash",
        )

        # Verify gone
        cached = repo.get_cached(
            organization_id=2,
            difficulty=None,
            topic_ids=None,
            vector_hash="testhash",
        )
        assert cached is None

    def test_does_not_cache_fallback_results(self):
        from app.question.retrieval.contracts import (
            RetrievalResult,
            RetrievalStrategy,
        )
        from app.question.retrieval.persistence.cache_repository import (
            RetrievalCacheRepository,
        )

        repo = RetrievalCacheRepository(ttl_seconds=60)

        fallback_result = RetrievalResult(
            candidates=[],
            strategy_used=RetrievalStrategy.STATIC_FALLBACK,
            total_found=0,
            search_duration_ms=1.0,
            fallback_activated=True,
            fallback_reason="test",
        )

        repo.store(
            organization_id=3,
            difficulty=None,
            topic_ids=None,
            vector_hash="fallback_hash",
            result=fallback_result,
        )

        cached = repo.get_cached(
            organization_id=3,
            difficulty=None,
            topic_ids=None,
            vector_hash="fallback_hash",
        )
        assert cached is None  # Fallback results should not be cached


# ═══════════════════════════════════════════════════════════════════════
# Vector Hash
# ═══════════════════════════════════════════════════════════════════════


class TestVectorHash:
    """Tests for hash determinism."""

    def test_same_vector_same_hash(self):
        from app.question.retrieval.persistence.cache_repository import (
            RetrievalCacheRepository,
        )

        vec = [0.123456789, 0.987654321, 0.555555555]
        h1 = RetrievalCacheRepository.compute_vector_hash(vec)
        h2 = RetrievalCacheRepository.compute_vector_hash(vec)
        assert h1 == h2

    def test_different_vectors_different_hash(self):
        from app.question.retrieval.persistence.cache_repository import (
            RetrievalCacheRepository,
        )

        h1 = RetrievalCacheRepository.compute_vector_hash([0.1, 0.2])
        h2 = RetrievalCacheRepository.compute_vector_hash([0.3, 0.4])
        assert h1 != h2
