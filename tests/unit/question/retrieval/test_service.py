"""
Unit Tests — QdrantRetrievalService

All external dependencies (Qdrant, Redis, PostgreSQL) are MOCKED.
Tests orchestration logic: cache hits, circuit breaker fallbacks,
hybrid computation, repetition delegation.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from app.question.retrieval.contracts import (
    DifficultyLevel,
    HybridSearchWeights,
    QuestionCandidate,
    RetrievalResult,
    RetrievalStrategy,
    SearchCriteria,
    SimilarityCheckResult,
)
from app.question.retrieval.domain.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)
from app.question.retrieval.service import QdrantRetrievalService


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════


def _make_candidate(question_id: int = 1, score: float = 0.9) -> QuestionCandidate:
    """Factory for test QuestionCandidates."""
    return QuestionCandidate(
        question_id=question_id,
        similarity_score=score,
        point_id=f"point-{question_id}",
        difficulty="medium",
        topic_id=10,
        scope="organization",
        metadata={"source_type": "question"},
    )


def _make_criteria(
    org_id: int = 1,
    query_vector: Optional[List[float]] = None,
    difficulty: Optional[str] = None,
    topic_ids: Optional[List[int]] = None,
    top_k: int = 10,
) -> SearchCriteria:
    """Factory for test SearchCriteria."""
    return SearchCriteria(
        organization_id=org_id,
        query_vector=query_vector,
        difficulty=difficulty,
        topic_ids=topic_ids,
        top_k=top_k,
    )


@pytest.fixture()
def mock_qdrant_repo():
    """Mocked QdrantQuestionRepository."""
    repo = MagicMock()
    repo.search_questions.return_value = [
        _make_candidate(1, 0.95),
        _make_candidate(2, 0.88),
    ]
    repo.scroll_questions_by_filter.return_value = [
        _make_candidate(3, 0.0),
    ]
    repo.get_embedding_vector.return_value = [0.1] * 768
    return repo


@pytest.fixture()
def mock_cache_repo():
    """Mocked RetrievalCacheRepository (always misses)."""
    repo = MagicMock()
    repo.get_cached.return_value = None
    repo.compute_vector_hash.return_value = "abc123"
    return repo


@pytest.fixture()
def mock_fallback_repo():
    """Mocked QuestionReadRepository (PostgreSQL fallback)."""
    repo = MagicMock()
    repo.get_random.return_value = [
        _make_candidate(100, 0.0),
    ]
    return repo


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Reset class-level circuit breaker before each test."""
    QdrantRetrievalService.reset_circuit_breaker()
    yield
    QdrantRetrievalService.reset_circuit_breaker()


@pytest.fixture()
def service(mock_qdrant_repo, mock_cache_repo, mock_fallback_repo):
    """Service with all mocked dependencies."""
    return QdrantRetrievalService(
        question_read_repo=mock_fallback_repo,
        qdrant_repo=mock_qdrant_repo,
        cache_repo=mock_cache_repo,
    )


# ═══════════════════════════════════════════════════════════════════════
# search_semantic — Happy Path
# ═══════════════════════════════════════════════════════════════════════


class TestSearchSemantic:
    """Tests for search_semantic()."""

    def test_returns_qdrant_results(self, service, mock_qdrant_repo, mock_cache_repo):
        criteria = _make_criteria(
            org_id=42, query_vector=[0.1] * 768, difficulty="medium"
        )
        result = service.search_semantic(criteria)

        assert result.strategy_used == RetrievalStrategy.SEMANTIC
        assert result.total_found == 2
        assert len(result.candidates) == 2
        assert result.candidates[0].question_id == 1
        assert result.fallback_activated is False
        assert result.cache_hit is False

        mock_qdrant_repo.search_questions.assert_called_once()
        mock_cache_repo.store.assert_called_once()

    def test_requires_query_vector(self, service):
        criteria = _make_criteria(org_id=1, query_vector=None)
        with pytest.raises(ValueError, match="query_vector is required"):
            service.search_semantic(criteria)

    def test_records_search_duration(self, service):
        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        result = service.search_semantic(criteria)
        assert result.search_duration_ms >= 0.0

    def test_passes_all_filters_to_qdrant(self, service, mock_qdrant_repo):
        criteria = _make_criteria(
            org_id=7,
            query_vector=[0.5] * 768,
            difficulty="hard",
            topic_ids=[1, 2],
            top_k=5,
        )
        criteria.exclude_question_ids = [10, 20]
        criteria.include_public = False

        service.search_semantic(criteria)

        call_kwargs = mock_qdrant_repo.search_questions.call_args.kwargs
        assert call_kwargs["organization_id"] == 7
        assert call_kwargs["difficulty"] == "hard"
        assert call_kwargs["topic_ids"] == [1, 2]
        assert call_kwargs["top_k"] == 5
        assert call_kwargs["exclude_question_ids"] == [10, 20]
        assert call_kwargs["include_public"] is False


# ═══════════════════════════════════════════════════════════════════════
# search_semantic — Cache
# ═══════════════════════════════════════════════════════════════════════


class TestSearchSemanticCache:
    """Tests for cache integration in search_semantic()."""

    def test_returns_cached_result(self, service, mock_cache_repo, mock_qdrant_repo):
        cached_result = RetrievalResult(
            candidates=[_make_candidate(99, 0.99)],
            strategy_used=RetrievalStrategy.SEMANTIC,
            total_found=1,
            search_duration_ms=0.0,
            cache_hit=True,
        )
        mock_cache_repo.get_cached.return_value = cached_result

        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        result = service.search_semantic(criteria)

        assert result.cache_hit is True
        assert result.candidates[0].question_id == 99
        mock_qdrant_repo.search_questions.assert_not_called()

    def test_stores_to_cache_on_success(self, service, mock_cache_repo):
        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        service.search_semantic(criteria)

        mock_cache_repo.store.assert_called_once()
        stored_result = mock_cache_repo.store.call_args.kwargs["result"]
        assert stored_result.total_found == 2


# ═══════════════════════════════════════════════════════════════════════
# search_semantic — Circuit Breaker & Fallback
# ═══════════════════════════════════════════════════════════════════════


class TestSearchSemanticFallback:
    """Tests for circuit breaker and fallback in search_semantic()."""

    def test_falls_back_when_circuit_breaker_open(
        self, mock_cache_repo, mock_fallback_repo, mock_qdrant_repo
    ):
        """Open circuit breaker → static fallback, Qdrant not called."""
        # Force circuit breaker open
        for _ in range(5):
            QdrantRetrievalService._circuit_breaker.record_failure()
        assert QdrantRetrievalService._circuit_breaker.state == CircuitBreakerState.OPEN

        svc = QdrantRetrievalService(
            question_read_repo=mock_fallback_repo,
            qdrant_repo=mock_qdrant_repo,
            cache_repo=mock_cache_repo,
        )
        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        result = svc.search_semantic(criteria)

        assert result.fallback_activated is True
        assert result.strategy_used == RetrievalStrategy.STATIC_FALLBACK
        assert "circuit_breaker_open" in result.fallback_reason
        mock_qdrant_repo.search_questions.assert_not_called()

    def test_falls_back_on_qdrant_exception(
        self, service, mock_qdrant_repo, mock_fallback_repo
    ):
        """Qdrant exception → fallback triggered, failure recorded."""
        mock_qdrant_repo.search_questions.side_effect = RuntimeError("Qdrant down")

        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        result = service.search_semantic(criteria)

        assert result.fallback_activated is True
        assert result.strategy_used == RetrievalStrategy.STATIC_FALLBACK
        assert "qdrant_error" in result.fallback_reason
        mock_fallback_repo.get_random.assert_called_once()

    def test_empty_fallback_when_no_db_session(self, mock_qdrant_repo, mock_cache_repo):
        """No DB session → empty fallback result."""
        mock_qdrant_repo.search_questions.side_effect = RuntimeError("fail")

        svc = QdrantRetrievalService(
            question_read_repo=None,  # No DB session
            qdrant_repo=mock_qdrant_repo,
            cache_repo=mock_cache_repo,
        )
        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        result = svc.search_semantic(criteria)

        assert result.fallback_activated is True
        assert result.total_found == 0
        assert "no DB session" in result.fallback_reason

    def test_fallback_relaxes_difficulty(
        self, service, mock_fallback_repo, mock_qdrant_repo
    ):
        """Fallback relaxes difficulty filter when no results."""
        mock_qdrant_repo.search_questions.side_effect = RuntimeError("fail")
        mock_fallback_repo.get_random.side_effect = [
            [],  # First call with difficulty → empty
            [_make_candidate(200, 0.0)],  # Second call without difficulty
        ]

        criteria = _make_criteria(
            org_id=1,
            query_vector=[0.1] * 768,
            difficulty="hard",
        )
        result = service.search_semantic(criteria)

        assert result.total_found == 1
        assert mock_fallback_repo.get_random.call_count == 2

    def test_fallback_db_error_returns_empty(
        self, service, mock_fallback_repo, mock_qdrant_repo
    ):
        """Fallback DB error → empty result (no exception propagated)."""
        mock_qdrant_repo.search_questions.side_effect = RuntimeError("qdrant fail")
        mock_fallback_repo.get_random.side_effect = RuntimeError("DB error")

        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        result = service.search_semantic(criteria)

        assert result.total_found == 0
        assert result.fallback_activated is True
        assert "DB error" in result.fallback_reason


# ═══════════════════════════════════════════════════════════════════════
# search_by_topic
# ═══════════════════════════════════════════════════════════════════════


class TestSearchByTopic:
    """Tests for search_by_topic()."""

    def test_returns_scroll_results(self, service, mock_qdrant_repo):
        criteria = _make_criteria(org_id=1, topic_ids=[5, 6])
        result = service.search_by_topic(criteria)

        assert result.strategy_used == RetrievalStrategy.TOPIC_FILTER
        assert result.total_found == 1
        mock_qdrant_repo.scroll_questions_by_filter.assert_called_once()

    def test_falls_back_on_scroll_failure(
        self, service, mock_qdrant_repo, mock_fallback_repo
    ):
        mock_qdrant_repo.scroll_questions_by_filter.side_effect = RuntimeError("fail")

        criteria = _make_criteria(org_id=1, topic_ids=[5])
        result = service.search_by_topic(criteria)

        assert result.fallback_activated is True
        mock_fallback_repo.get_random.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════
# search_hybrid
# ═══════════════════════════════════════════════════════════════════════


class TestSearchHybrid:
    """Tests for search_hybrid()."""

    def test_computes_hybrid_and_delegates_to_semantic(
        self, service, mock_qdrant_repo
    ):
        resume_vec = [1.0, 0.0]
        jd_vec = [0.0, 1.0]
        criteria = _make_criteria(org_id=1)

        result = service.search_hybrid(resume_vec, jd_vec, criteria)

        assert result.strategy_used == RetrievalStrategy.HYBRID
        # search_questions was called with the hybrid vector
        call_kwargs = mock_qdrant_repo.search_questions.call_args.kwargs
        assert call_kwargs["query_vector"] is not None
        assert len(call_kwargs["query_vector"]) == 2

    def test_uses_default_weights(self, service, mock_qdrant_repo):
        resume_vec = [1.0, 0.0]
        jd_vec = [0.0, 1.0]
        criteria = _make_criteria(org_id=1)

        result = service.search_hybrid(resume_vec, jd_vec, criteria)
        # Default weights are 0.6/0.4 → hybrid is weighted sum
        assert result.strategy_used == RetrievalStrategy.HYBRID

    def test_custom_weights(self, service, mock_qdrant_repo):
        resume_vec = [1.0, 0.0]
        jd_vec = [0.0, 1.0]
        criteria = _make_criteria(org_id=1)
        weights = HybridSearchWeights(resume_weight=0.8, jd_weight=0.2)

        result = service.search_hybrid(resume_vec, jd_vec, criteria, weights)
        assert result.strategy_used == RetrievalStrategy.HYBRID

    def test_does_not_mutate_original_criteria(self, service):
        criteria = _make_criteria(org_id=1, query_vector=None)
        resume_vec = [1.0, 0.0]
        jd_vec = [0.0, 1.0]

        service.search_hybrid(resume_vec, jd_vec, criteria)
        # Original criteria is not mutated
        assert criteria.query_vector is None


# ═══════════════════════════════════════════════════════════════════════
# check_repetition
# ═══════════════════════════════════════════════════════════════════════


class TestCheckRepetition:
    """Tests for check_repetition()."""

    def test_delegates_to_domain(self, service):
        candidate = [1.0, 0.0, 0.0]
        history = [
            {"question_id": 1, "question_embedding": [0.0, 1.0, 0.0]},
        ]

        result = service.check_repetition(candidate, history, threshold=0.85)

        assert isinstance(result, SimilarityCheckResult)
        assert result.is_acceptable is True

    def test_identical_detected(self, service):
        vec = [1.0, 0.0, 0.0]
        history = [
            {"question_id": 42, "question_embedding": vec},
        ]

        result = service.check_repetition(vec, history, threshold=0.85)
        assert result.is_acceptable is False
        assert result.most_similar_question_id == 42


# ═══════════════════════════════════════════════════════════════════════
# get_embedding_vector
# ═══════════════════════════════════════════════════════════════════════


class TestGetEmbeddingVector:
    """Tests for get_embedding_vector()."""

    def test_returns_vector(self, service, mock_qdrant_repo):
        result = service.get_embedding_vector("question", 42, 1)
        assert result is not None
        assert len(result) == 768
        mock_qdrant_repo.get_embedding_vector.assert_called_once_with(
            source_type="question", source_id=42, organization_id=1
        )

    def test_returns_none_when_not_found(self, service, mock_qdrant_repo):
        mock_qdrant_repo.get_embedding_vector.return_value = None
        result = service.get_embedding_vector("question", 999, 1)
        assert result is None

    def test_returns_none_when_circuit_breaker_open(self, service):
        for _ in range(5):
            QdrantRetrievalService._circuit_breaker.record_failure()

        result = service.get_embedding_vector("question", 42, 1)
        assert result is None

    def test_returns_none_on_exception(self, service, mock_qdrant_repo):
        mock_qdrant_repo.get_embedding_vector.side_effect = RuntimeError("fail")
        result = service.get_embedding_vector("question", 42, 1)
        assert result is None


# ═══════════════════════════════════════════════════════════════════════
# Diagnostics
# ═══════════════════════════════════════════════════════════════════════


class TestDiagnostics:
    """Tests for diagnostic properties."""

    def test_circuit_breaker_state_initially_closed(self, service):
        assert service.circuit_breaker_state == "closed"

    def test_circuit_breaker_state_after_failures(self, service):
        for _ in range(5):
            QdrantRetrievalService._circuit_breaker.record_failure()
        assert service.circuit_breaker_state == "open"

    def test_reset_circuit_breaker(self, service):
        for _ in range(5):
            QdrantRetrievalService._circuit_breaker.record_failure()
        assert service.circuit_breaker_state == "open"

        QdrantRetrievalService.reset_circuit_breaker()
        assert service.circuit_breaker_state == "closed"


# ═══════════════════════════════════════════════════════════════════════
# Circuit Breaker Integration
# ═══════════════════════════════════════════════════════════════════════


class TestCircuitBreakerIntegration:
    """Tests circuit breaker state transitions via service calls."""

    def test_success_records_success(self, service, mock_qdrant_repo):
        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        service.search_semantic(criteria)
        # Circuit breaker should be healthy
        assert service.circuit_breaker_state == "closed"

    def test_repeated_failures_open_breaker(self, service, mock_qdrant_repo, mock_cache_repo):
        mock_qdrant_repo.search_questions.side_effect = RuntimeError("fail")

        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        for _ in range(5):
            service.search_semantic(criteria)

        assert service.circuit_breaker_state == "open"

    def test_open_breaker_skips_qdrant(
        self, mock_qdrant_repo, mock_cache_repo, mock_fallback_repo
    ):
        # Fail enough times to open
        for _ in range(5):
            QdrantRetrievalService._circuit_breaker.record_failure()

        svc = QdrantRetrievalService(
            question_read_repo=mock_fallback_repo,
            qdrant_repo=mock_qdrant_repo,
            cache_repo=mock_cache_repo,
        )
        criteria = _make_criteria(org_id=1, query_vector=[0.1] * 768)
        result = svc.search_semantic(criteria)

        mock_qdrant_repo.search_questions.assert_not_called()
        assert result.fallback_activated is True
