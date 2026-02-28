"""
Qdrant Retrieval Service — Main Orchestrator

Coordinates:
1. Qdrant semantic search (primary path)
2. Circuit breaker fault tolerance
3. Redis caching
4. PostgreSQL static-pool fallback (degraded path)
5. Similarity/repetition checks

This service is STATELESS — safe for concurrent calls.
It does NOT modify any data.  It does NOT orchestrate interviews.

Consumed by: question/selection module.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from app.question.retrieval.contracts import (
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
from app.question.retrieval.domain.similarity import (
    compute_hybrid_vector,
    compute_similarity_to_history,
    cosine_similarity,
    is_acceptable_candidate,
    normalize_vector,
)
from app.question.retrieval.persistence.cache_repository import (
    RetrievalCacheRepository,
)
from app.question.retrieval.persistence.qdrant_repository import (
    QdrantQuestionRepository,
)
from app.question.retrieval.persistence.question_read_repository import (
    QuestionReadRepository,
)

logger = logging.getLogger(__name__)


class QdrantRetrievalService:
    """
    Main retrieval orchestrator.

    Lifecycle:
        Instantiated once per request (or injected as dependency).
        Qdrant repo and cache repo are stateless singletons.
        CircuitBreaker is shared across requests (module-level).
        QuestionReadRepository requires per-request DB session.

    Args:
        db_session_factory: Callable that yields a SQLAlchemy Session
            (used only when fallback is needed).
    """

    # Module-level circuit breaker (shared across all requests)
    _circuit_breaker = CircuitBreaker(
        name="qdrant_retrieval",
        failure_threshold=5,
        timeout_duration=60.0,
        success_threshold=2,
    )

    def __init__(
        self,
        question_read_repo: Optional[QuestionReadRepository] = None,
        qdrant_repo: Optional[QdrantQuestionRepository] = None,
        cache_repo: Optional[RetrievalCacheRepository] = None,
    ) -> None:
        self._qdrant_repo = qdrant_repo or QdrantQuestionRepository()
        self._cache_repo = cache_repo or RetrievalCacheRepository()
        self._fallback_repo = question_read_repo  # May be None if no DB session

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ══════════════════════════════════════════════════════════════════

    def search_semantic(
        self, criteria: SearchCriteria
    ) -> RetrievalResult:
        """
        Semantic search using embedding vector.

        Primary path: Qdrant vector search.
        Fallback: PostgreSQL random selection.

        Args:
            criteria: Must include query_vector.

        Returns:
            RetrievalResult with candidates sorted by similarity.
        """
        if criteria.query_vector is None:
            raise ValueError("query_vector is required for semantic search")

        # Check cache
        vector_hash = self._cache_repo.compute_vector_hash(criteria.query_vector)
        cached = self._cache_repo.get_cached(
            organization_id=criteria.organization_id,
            difficulty=criteria.difficulty.value if criteria.difficulty else None,
            topic_ids=criteria.topic_ids,
            vector_hash=vector_hash,
        )
        if cached is not None:
            return cached

        # Check circuit breaker
        if self._circuit_breaker.is_open():
            logger.warning(
                "Circuit breaker OPEN — falling back to static pool "
                "(org=%d)",
                criteria.organization_id,
            )
            return self._static_fallback(
                criteria, reason="circuit_breaker_open"
            )

        # Qdrant search
        start = time.monotonic()
        try:
            candidates = self._qdrant_repo.search_questions(
                query_vector=criteria.query_vector,
                organization_id=criteria.organization_id,
                top_k=criteria.top_k,
                score_threshold=criteria.score_threshold,
                difficulty=(
                    criteria.difficulty.value if criteria.difficulty else None
                ),
                topic_ids=criteria.topic_ids,
                exclude_question_ids=criteria.exclude_question_ids or None,
                include_public=criteria.include_public,
            )
            self._circuit_breaker.record_success()

            duration_ms = (time.monotonic() - start) * 1000

            result = RetrievalResult(
                candidates=candidates,
                strategy_used=RetrievalStrategy.SEMANTIC,
                total_found=len(candidates),
                search_duration_ms=duration_ms,
            )

            # Cache successful result
            self._cache_repo.store(
                organization_id=criteria.organization_id,
                difficulty=(
                    criteria.difficulty.value if criteria.difficulty else None
                ),
                topic_ids=criteria.topic_ids,
                vector_hash=vector_hash,
                result=result,
            )

            return result

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(
                "Qdrant search failed (org=%d): %s — activating fallback",
                criteria.organization_id,
                e,
            )
            return self._static_fallback(
                criteria, reason=f"qdrant_error: {type(e).__name__}"
            )

    def search_by_topic(
        self, criteria: SearchCriteria
    ) -> RetrievalResult:
        """
        Topic-based retrieval (filter-only, no vector).

        Uses Qdrant scroll API for metadata filtering.
        Falls back to PostgreSQL if Qdrant unavailable.
        """
        if self._circuit_breaker.is_open():
            return self._static_fallback(
                criteria, reason="circuit_breaker_open"
            )

        start = time.monotonic()
        try:
            candidates = self._qdrant_repo.scroll_questions_by_filter(
                organization_id=criteria.organization_id,
                difficulty=(
                    criteria.difficulty.value if criteria.difficulty else None
                ),
                topic_ids=criteria.topic_ids,
                exclude_question_ids=criteria.exclude_question_ids or None,
                include_public=criteria.include_public,
                limit=criteria.top_k,
            )
            self._circuit_breaker.record_success()
            duration_ms = (time.monotonic() - start) * 1000

            return RetrievalResult(
                candidates=candidates,
                strategy_used=RetrievalStrategy.TOPIC_FILTER,
                total_found=len(candidates),
                search_duration_ms=duration_ms,
            )

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(
                "Qdrant scroll failed (org=%d): %s — activating fallback",
                criteria.organization_id,
                e,
            )
            return self._static_fallback(
                criteria, reason=f"qdrant_error: {type(e).__name__}"
            )

    def search_hybrid(
        self,
        resume_vector: List[float],
        jd_vector: List[float],
        criteria: SearchCriteria,
        weights: Optional[HybridSearchWeights] = None,
    ) -> RetrievalResult:
        """
        Hybrid search combining resume and JD embeddings.

        Computes weighted average vector, normalizes, then runs
        semantic search.

        Args:
            resume_vector: Resume embedding.
            jd_vector: Job description embedding.
            criteria: Search criteria (query_vector is overwritten).
            weights: Optional weights (default 0.5/0.5).

        Returns:
            RetrievalResult with hybrid strategy.
        """
        if weights is None:
            weights = HybridSearchWeights()

        hybrid_vec = compute_hybrid_vector(
            vec_a=resume_vector,
            vec_b=jd_vector,
            weight_a=weights.resume_weight,
            weight_b=weights.jd_weight,
        )

        # Override criteria vector with hybrid
        criteria_copy = criteria.model_copy(
            update={"query_vector": hybrid_vec}
        )

        result = self.search_semantic(criteria_copy)
        result.strategy_used = RetrievalStrategy.HYBRID
        return result

    def check_repetition(
        self,
        candidate_embedding: List[float],
        exchange_history: List[Dict],
        threshold: float = 0.85,
    ) -> SimilarityCheckResult:
        """
        Check if a candidate question embedding is too similar to
        previously asked questions.

        Pure domain computation — no I/O.

        Args:
            candidate_embedding: Embedding of candidate question.
            exchange_history: List of dicts with question_id and
                              question_embedding keys.
            threshold: Maximum acceptable similarity (default 0.85).

        Returns:
            SimilarityCheckResult.
        """
        return is_acceptable_candidate(
            candidate_embedding=candidate_embedding,
            exchange_history=exchange_history,
            threshold=threshold,
        )

    def get_embedding_vector(
        self,
        source_type: str,
        source_id: int,
        organization_id: int,
    ) -> Optional[List[float]]:
        """
        Retrieve stored embedding vector for a source entity.

        Delegates to Qdrant repository. Returns None if not found
        or Qdrant unavailable.
        """
        if self._circuit_breaker.is_open():
            logger.warning(
                "Circuit breaker OPEN — cannot retrieve embedding "
                "for %s:%d",
                source_type,
                source_id,
            )
            return None

        try:
            vector = self._qdrant_repo.get_embedding_vector(
                source_type=source_type,
                source_id=source_id,
                organization_id=organization_id,
            )
            if vector is not None:
                self._circuit_breaker.record_success()
            return vector

        except Exception as e:
            self._circuit_breaker.record_failure()
            logger.error(
                "Failed to retrieve embedding for %s:%d: %s",
                source_type,
                source_id,
                e,
            )
            return None

    # ══════════════════════════════════════════════════════════════════
    # Diagnostics
    # ══════════════════════════════════════════════════════════════════

    @property
    def circuit_breaker_state(self) -> str:
        """Current circuit breaker state."""
        return self._circuit_breaker.state.value

    @classmethod
    def reset_circuit_breaker(cls) -> None:
        """Reset circuit breaker (admin/testing use only)."""
        cls._circuit_breaker.reset()

    # ══════════════════════════════════════════════════════════════════
    # PRIVATE — Fallback
    # ══════════════════════════════════════════════════════════════════

    def _static_fallback(
        self,
        criteria: SearchCriteria,
        reason: str,
    ) -> RetrievalResult:
        """
        Fallback to PostgreSQL static pool.

        Returns random questions matching criteria (no semantic ranking).
        """
        logger.warning(
            "Activating static fallback (org=%d, reason=%s)",
            criteria.organization_id,
            reason,
        )

        if self._fallback_repo is None:
            logger.error(
                "Static fallback unavailable — no DB session provided"
            )
            return RetrievalResult(
                candidates=[],
                strategy_used=RetrievalStrategy.STATIC_FALLBACK,
                total_found=0,
                search_duration_ms=0.0,
                fallback_activated=True,
                fallback_reason=f"{reason} (no DB session)",
            )

        start = time.monotonic()
        try:
            candidates = self._fallback_repo.get_random(
                organization_id=criteria.organization_id,
                difficulty=(
                    criteria.difficulty.value if criteria.difficulty else None
                ),
                exclude_ids=criteria.exclude_question_ids or None,
                limit=criteria.top_k,
            )

            # If no results with difficulty filter, relax it
            if not candidates and criteria.difficulty:
                logger.info(
                    "No results with difficulty=%s — relaxing filter",
                    criteria.difficulty.value,
                )
                candidates = self._fallback_repo.get_random(
                    organization_id=criteria.organization_id,
                    difficulty=None,
                    exclude_ids=criteria.exclude_question_ids or None,
                    limit=criteria.top_k,
                )

            duration_ms = (time.monotonic() - start) * 1000

            return RetrievalResult(
                candidates=candidates,
                strategy_used=RetrievalStrategy.STATIC_FALLBACK,
                total_found=len(candidates),
                search_duration_ms=duration_ms,
                fallback_activated=True,
                fallback_reason=reason,
            )

        except Exception as e:
            logger.error("Static fallback failed: %s", e)
            return RetrievalResult(
                candidates=[],
                strategy_used=RetrievalStrategy.STATIC_FALLBACK,
                total_found=0,
                search_duration_ms=0.0,
                fallback_activated=True,
                fallback_reason=f"{reason} (DB error: {type(e).__name__})",
            )
