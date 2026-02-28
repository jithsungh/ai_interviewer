"""
Redis Cache Repository for Retrieval Results

Caches Qdrant search results to avoid redundant vector searches.

Key pattern:
    question_search:{org_id}:{difficulty}:{topic_ids_sorted}:{vector_hash}

TTL: 1 hour (questions change infrequently).

Uses shared Redis operations from app.persistence.redis.operations.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import List, Optional

from app.persistence.redis.operations import (
    delete_key,
    get_value,
    set_value,
)
from app.question.retrieval.contracts import QuestionCandidate, RetrievalResult

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_PREFIX = "question_search"
DEFAULT_TTL_SECONDS = 3600  # 1 hour


class RetrievalCacheRepository:
    """
    Redis cache for retrieval search results.

    Cache key is a deterministic hash of the search parameters.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds

    # ── Public Interface ──────────────────────────────────────────

    def get_cached(
        self,
        organization_id: int,
        difficulty: Optional[str],
        topic_ids: Optional[List[int]],
        vector_hash: Optional[str],
    ) -> Optional[RetrievalResult]:
        """
        Look up cached retrieval result.

        Args:
            organization_id: Tenant ID.
            difficulty: Difficulty filter (or None).
            topic_ids: Topic ID list (or None).
            vector_hash: SHA256 of the query vector (or None for filter-only).

        Returns:
            Cached RetrievalResult, or None if miss.
        """
        key = self._build_key(organization_id, difficulty, topic_ids, vector_hash)

        try:
            raw = get_value(key, deserialize_json=True)
            if raw is None:
                logger.debug("Cache MISS: %s", key)
                return None

            logger.debug("Cache HIT: %s", key)
            result = self._deserialize(raw)
            result.cache_hit = True
            return result

        except Exception as e:
            # Cache errors are non-fatal — log and continue
            logger.warning("Cache GET failed for %s: %s", key, e)
            return None

    def store(
        self,
        organization_id: int,
        difficulty: Optional[str],
        topic_ids: Optional[List[int]],
        vector_hash: Optional[str],
        result: RetrievalResult,
    ) -> None:
        """
        Store retrieval result in cache.

        Does NOT cache fallback results (stale data risk).
        """
        if result.fallback_activated:
            return  # Don't cache degraded results

        key = self._build_key(organization_id, difficulty, topic_ids, vector_hash)

        try:
            serialized = self._serialize(result)
            set_value(key, serialized, ttl_seconds=self._ttl)
            logger.debug("Cache SET: %s (TTL=%ds)", key, self._ttl)

        except Exception as e:
            # Cache errors are non-fatal
            logger.warning("Cache SET failed for %s: %s", key, e)

    def invalidate(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[List[int]] = None,
        vector_hash: Optional[str] = None,
    ) -> None:
        """Invalidate specific cache entry."""
        key = self._build_key(organization_id, difficulty, topic_ids, vector_hash)
        try:
            delete_key(key)
            logger.debug("Cache INVALIDATED: %s", key)
        except Exception as e:
            logger.warning("Cache invalidation failed for %s: %s", key, e)

    # ── Utility ───────────────────────────────────────────────────

    @staticmethod
    def compute_vector_hash(vector: List[float]) -> str:
        """
        SHA256 hash of embedding vector for cache key stability.

        Truncates floats to 6 decimal places for determinism.
        """
        # Truncate to 6 decimal places to avoid floating-point noise
        rounded = [round(v, 6) for v in vector]
        raw = json.dumps(rounded, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── Internals ─────────────────────────────────────────────────

    @staticmethod
    def _build_key(
        organization_id: int,
        difficulty: Optional[str],
        topic_ids: Optional[List[int]],
        vector_hash: Optional[str],
    ) -> str:
        """Build deterministic Redis key."""
        diff_part = difficulty or "any"
        topic_part = (
            ":".join(str(t) for t in sorted(topic_ids)) if topic_ids else "any"
        )
        vec_part = vector_hash or "none"
        return f"{CACHE_PREFIX}:{organization_id}:{diff_part}:{topic_part}:{vec_part}"

    @staticmethod
    def _serialize(result: RetrievalResult) -> dict:
        """Serialize RetrievalResult for Redis storage."""
        return result.model_dump(mode="json")

    @staticmethod
    def _deserialize(raw: dict) -> RetrievalResult:
        """Deserialize RetrievalResult from Redis."""
        return RetrievalResult.model_validate(raw)
