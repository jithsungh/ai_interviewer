"""
Question Retrieval Module — Qdrant Semantic Search & Similarity Detection

Provides:
- Semantic similarity search using Qdrant vector database
- Resume/JD-based question personalization
- Hybrid search (weighted resume + JD vectors)
- Topic-based metadata filtering
- Multi-tenant collection isolation (organization_id + scope)
- Similarity scoring for repetition prevention
- Circuit breaker pattern for Qdrant fault tolerance
- Redis caching for repeated queries
- PostgreSQL static-pool fallback when Qdrant is unavailable

Public API:
- QdrantRetrievalService: Main orchestrator
- SearchCriteria, QuestionCandidate, RetrievalResult: DTOs
- cosine_similarity, is_acceptable_candidate: Similarity functions
- CircuitBreaker: Fault tolerance
"""

from .contracts import (
    SearchCriteria,
    QuestionCandidate,
    RetrievalResult,
    SimilarityCheckResult,
    HybridSearchWeights,
)
from .domain.similarity import (
    cosine_similarity,
    normalize_vector,
    compute_hybrid_vector,
    compute_similarity_to_history,
    is_acceptable_candidate,
)
from .domain.circuit_breaker import CircuitBreaker, CircuitBreakerState
from .service import QdrantRetrievalService

__all__ = [
    # Service
    "QdrantRetrievalService",
    # Contracts
    "SearchCriteria",
    "QuestionCandidate",
    "RetrievalResult",
    "SimilarityCheckResult",
    "HybridSearchWeights",
    # Domain
    "cosine_similarity",
    "normalize_vector",
    "compute_hybrid_vector",
    "compute_similarity_to_history",
    "is_acceptable_candidate",
    "CircuitBreaker",
    "CircuitBreakerState",
]
