"""
Qdrant Repository — Vector search with multi-tenant isolation.

Wraps the shared Qdrant client (app.persistence.qdrant) with
domain-specific query logic required by the retrieval module:

- OR-based tenant isolation (org_id questions OR public questions)
- Topic-based metadata filtering via MatchAny
- Difficulty filtering
- Exclude-list for already-asked questions
- Scroll API for filter-only queries (no vector)

Does NOT duplicate app.persistence.qdrant.operations — extends it
with the multi-tenant OR logic that the generic search_embeddings
cannot express (it always applies organization_id as MUST).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    SearchParams,
)

from app.persistence.qdrant.client import (
    QdrantCollectionError,
    QdrantConnectionError,
    get_collection_name,
    get_qdrant_client,
    get_vector_dimension,
)
from app.question.retrieval.contracts import QuestionCandidate

logger = logging.getLogger(__name__)


class QdrantQuestionRepository:
    """
    Read-only Qdrant vector search for question embeddings.

    All methods enforce multi-tenant isolation via
    (organization_id = X) OR (scope = 'public') filter logic.
    """

    # ── Semantic search ────────────────────────────────────────────

    def search_questions(
        self,
        query_vector: List[float],
        organization_id: int,
        top_k: int = 10,
        score_threshold: float = 0.5,
        difficulty: Optional[str] = None,
        topic_ids: Optional[List[int]] = None,
        exclude_question_ids: Optional[List[int]] = None,
        include_public: bool = True,
    ) -> List[QuestionCandidate]:
        """
        Semantic search for questions via embedding similarity.

        Builds a filter that enforces:
            (organization_id = org_id) OR (scope = 'public')
        combined with optional difficulty/topic constraints.

        Args:
            query_vector: Query embedding (dimension must match collection).
            organization_id: Tenant ID (REQUIRED — NFR-7.1).
            top_k: Maximum results.
            score_threshold: Minimum cosine similarity.
            difficulty: Optional difficulty filter.
            topic_ids: Optional list of topic IDs to match.
            exclude_question_ids: Source IDs to exclude (already asked).
            include_public: Whether to include public-scope questions.

        Returns:
            Sorted list of QuestionCandidate (highest score first).

        Raises:
            QdrantCollectionError: Search failed.
            QdrantConnectionError: Client not initialized.
        """
        client = get_qdrant_client()
        collection_name = get_collection_name()

        # Validate dimension
        expected_dim = get_vector_dimension()
        if len(query_vector) != expected_dim:
            raise ValueError(
                f"Vector dimension mismatch: expected {expected_dim}, "
                f"got {len(query_vector)}"
            )

        # Build multi-tenant filter
        qdrant_filter = self._build_question_filter(
            organization_id=organization_id,
            difficulty=difficulty,
            topic_ids=topic_ids,
            exclude_question_ids=exclude_question_ids,
            include_public=include_public,
        )

        start = time.monotonic()
        try:
            results = client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                query_filter=qdrant_filter,
                limit=top_k,
                score_threshold=score_threshold,
                search_params=SearchParams(hnsw_ef=128),
            )

            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "Qdrant search completed: %d results in %.1fms "
                "(org=%d, difficulty=%s, topics=%s)",
                len(results),
                duration_ms,
                organization_id,
                difficulty,
                topic_ids,
            )

            return self._parse_results(results)

        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "Qdrant search failed after %.1fms: %s", duration_ms, e
            )
            raise QdrantCollectionError(f"Vector search failed: {e}")

    # ── Filter-only scroll (no vector) ─────────────────────────────

    def scroll_questions_by_filter(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[List[int]] = None,
        exclude_question_ids: Optional[List[int]] = None,
        include_public: bool = True,
        limit: int = 10,
    ) -> List[QuestionCandidate]:
        """
        Retrieve questions using filter-only scroll (no vector query).

        Used for topic-based retrieval when no embedding is available.

        Returns:
            List of QuestionCandidate (score = 0.0 since no vector match).
        """
        client = get_qdrant_client()
        collection_name = get_collection_name()

        qdrant_filter = self._build_question_filter(
            organization_id=organization_id,
            difficulty=difficulty,
            topic_ids=topic_ids,
            exclude_question_ids=exclude_question_ids,
            include_public=include_public,
        )

        start = time.monotonic()
        try:
            points, _next_page = client.scroll(
                collection_name=collection_name,
                scroll_filter=qdrant_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            )

            duration_ms = (time.monotonic() - start) * 1000
            logger.info(
                "Qdrant scroll completed: %d results in %.1fms "
                "(org=%d, difficulty=%s)",
                len(points),
                duration_ms,
                organization_id,
                difficulty,
            )

            return self._parse_scroll_results(points)

        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "Qdrant scroll failed after %.1fms: %s", duration_ms, e
            )
            raise QdrantCollectionError(f"Scroll query failed: {e}")

    # ── Retrieve vector by source_id ───────────────────────────────

    def get_embedding_vector(
        self,
        source_type: str,
        source_id: int,
        organization_id: int,
    ) -> Optional[List[float]]:
        """
        Retrieve stored embedding vector for a given source entity.

        Args:
            source_type: "question", "resume", or "job_description".
            source_id: PostgreSQL entity ID.
            organization_id: Tenant ID for safety.

        Returns:
            Embedding vector or None if not found.
        """
        client = get_qdrant_client()
        collection_name = get_collection_name()

        search_filter = Filter(
            must=[
                FieldCondition(
                    key="organization_id",
                    match=MatchValue(value=organization_id),
                ),
                FieldCondition(
                    key="source_type",
                    match=MatchValue(value=source_type),
                ),
                FieldCondition(
                    key="source_id",
                    match=MatchValue(value=source_id),
                ),
            ]
        )

        try:
            points, _ = client.scroll(
                collection_name=collection_name,
                scroll_filter=search_filter,
                limit=1,
                with_payload=False,
                with_vectors=True,
            )

            if not points:
                return None

            vector = points[0].vector
            if isinstance(vector, dict):
                # Named vectors — get default
                vector = list(vector.values())[0] if vector else None
            return vector  # type: ignore[return-value]

        except Exception as e:
            logger.error(
                "Failed to retrieve embedding for %s:%d (org=%d): %s",
                source_type,
                source_id,
                organization_id,
                e,
            )
            return None

    # ── Internal helpers ───────────────────────────────────────────

    def _build_question_filter(
        self,
        organization_id: int,
        difficulty: Optional[str] = None,
        topic_ids: Optional[List[int]] = None,
        exclude_question_ids: Optional[List[int]] = None,
        include_public: bool = True,
    ) -> Filter:
        """
        Build Qdrant filter with multi-tenant OR logic.

        Logic:
            MUST: source_type = 'question'
            SHOULD (at least one):
                - organization_id = org_id
                - scope = 'public' (if include_public)
            MUST (optional):
                - difficulty = X
                - topic_id IN [...]
            MUST_NOT (optional):
                - source_id IN [excluded ids]
        """
        # Tenant isolation via SHOULD (org's questions OR public)
        should_conditions: List = []

        # Always include this org's questions
        should_conditions.append(
            Filter(
                must=[
                    FieldCondition(
                        key="organization_id",
                        match=MatchValue(value=organization_id),
                    )
                ]
            )
        )

        # Optionally include public questions from any org
        if include_public:
            should_conditions.append(
                Filter(
                    must=[
                        FieldCondition(
                            key="scope",
                            match=MatchValue(value="public"),
                        )
                    ]
                )
            )

        # Required conditions
        must_conditions: List = [
            FieldCondition(
                key="source_type",
                match=MatchValue(value="question"),
            ),
        ]

        if difficulty:
            must_conditions.append(
                FieldCondition(
                    key="difficulty",
                    match=MatchValue(value=difficulty),
                )
            )

        if topic_ids:
            must_conditions.append(
                FieldCondition(
                    key="topic_id",
                    match=MatchAny(any=topic_ids),
                )
            )

        # Exclusion conditions
        must_not_conditions: List = []
        if exclude_question_ids:
            must_not_conditions.append(
                FieldCondition(
                    key="source_id",
                    match=MatchAny(any=exclude_question_ids),
                )
            )

        # When include_public=False, only one should condition exists (org_id).
        # Qdrant treats a single-element should as optional, which would drop
        # the tenant filter entirely.  Promote it to must instead.
        if len(should_conditions) == 1:
            must_conditions.append(
                FieldCondition(
                    key="organization_id",
                    match=MatchValue(value=organization_id),
                )
            )
            effective_should = None
        else:
            effective_should = should_conditions

        return Filter(
            must=must_conditions,
            should=effective_should,
            must_not=must_not_conditions or None,
        )

    @staticmethod
    def _parse_results(results: list) -> List[QuestionCandidate]:
        """Convert Qdrant ScoredPoint results to QuestionCandidate list."""
        candidates: List[QuestionCandidate] = []
        for hit in results:
            payload = hit.payload or {}
            source_id = payload.get("source_id")
            if source_id is None:
                continue

            candidates.append(
                QuestionCandidate(
                    question_id=int(source_id),
                    similarity_score=float(hit.score),
                    point_id=str(hit.id),
                    difficulty=payload.get("difficulty"),
                    topic_id=payload.get("topic_id"),
                    scope=payload.get("scope"),
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k
                        not in {
                            "source_id",
                            "difficulty",
                            "topic_id",
                            "scope",
                        }
                    },
                )
            )
        return candidates

    @staticmethod
    def _parse_scroll_results(points: list) -> List[QuestionCandidate]:
        """Convert Qdrant scroll Record results to QuestionCandidate list."""
        candidates: List[QuestionCandidate] = []
        for point in points:
            payload = point.payload or {}
            source_id = payload.get("source_id")
            if source_id is None:
                continue

            candidates.append(
                QuestionCandidate(
                    question_id=int(source_id),
                    similarity_score=0.0,  # No vector search → no score
                    point_id=str(point.id),
                    difficulty=payload.get("difficulty"),
                    topic_id=payload.get("topic_id"),
                    scope=payload.get("scope"),
                    metadata={
                        k: v
                        for k, v in payload.items()
                        if k
                        not in {
                            "source_id",
                            "difficulty",
                            "topic_id",
                            "scope",
                        }
                    },
                )
            )
        return candidates
