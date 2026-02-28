"""
Retrieval Module Contracts (DTOs)

Pydantic request/response models for the retrieval layer.
Consumed by selection module and internal retrieval services.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════════════════════


class RetrievalStrategy(str, Enum):
    """Retrieval strategy used to obtain results."""

    SEMANTIC = "semantic"
    TOPIC_FILTER = "topic_filter"
    HYBRID = "hybrid"
    STATIC_FALLBACK = "static_fallback"


class DifficultyLevel(str, Enum):
    """Question difficulty levels (mirrors DB enum)."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionScope(str, Enum):
    """Question visibility scope (mirrors DB enum)."""

    PUBLIC = "public"
    ORGANIZATION = "organization"
    PRIVATE = "private"


# ════════════════════════════════════════════════════════════════════════════
# Input DTOs
# ════════════════════════════════════════════════════════════════════════════


class HybridSearchWeights(BaseModel):
    """Weights for hybrid search combining resume and JD vectors."""

    resume_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Weight for resume vector"
    )
    jd_weight: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Weight for JD vector"
    )

    @field_validator("jd_weight")
    @classmethod
    def weights_must_sum_to_one(cls, v: float, info) -> float:
        resume_w = info.data.get("resume_weight", 0.5)
        if abs(resume_w + v - 1.0) > 1e-6:
            raise ValueError(
                f"resume_weight ({resume_w}) + jd_weight ({v}) must sum to 1.0"
            )
        return v


class SearchCriteria(BaseModel):
    """
    Input criteria for retrieval search.

    organization_id is REQUIRED — enforces multi-tenant isolation (NFR-7.1).
    """

    organization_id: int = Field(
        ..., gt=0, description="Tenant ID (mandatory for isolation)"
    )
    query_vector: Optional[List[float]] = Field(
        default=None, description="Query embedding for semantic search"
    )
    difficulty: Optional[DifficultyLevel] = Field(
        default=None, description="Difficulty filter"
    )
    topic_ids: Optional[List[int]] = Field(
        default=None, description="Topic IDs for metadata filter"
    )
    question_type: Optional[str] = Field(
        default=None, description="Question type filter (behavioral, technical, coding)"
    )
    top_k: int = Field(
        default=10, ge=1, le=100, description="Maximum results to return"
    )
    score_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum similarity score"
    )
    exclude_question_ids: List[int] = Field(
        default_factory=list,
        description="Question IDs to exclude (already asked in session)",
    )
    include_public: bool = Field(
        default=True, description="Include public-scope questions"
    )


# ════════════════════════════════════════════════════════════════════════════
# Output DTOs
# ════════════════════════════════════════════════════════════════════════════


class QuestionCandidate(BaseModel):
    """Single question candidate from retrieval search."""

    question_id: int = Field(..., description="PostgreSQL question.id")
    similarity_score: float = Field(
        ..., ge=-1.0, le=1.0, description="Cosine similarity score"
    )
    point_id: Optional[str] = Field(
        default=None, description="Qdrant point UUID (for debugging)"
    )
    difficulty: Optional[str] = Field(default=None)
    topic_id: Optional[int] = Field(default=None)
    scope: Optional[str] = Field(default=None)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Aggregate output of a retrieval operation."""

    candidates: List[QuestionCandidate] = Field(default_factory=list)
    strategy_used: RetrievalStrategy
    total_found: int = Field(default=0, ge=0)
    search_duration_ms: float = Field(default=0.0, ge=0.0)
    cache_hit: bool = Field(default=False)
    fallback_activated: bool = Field(default=False)
    fallback_reason: Optional[str] = Field(default=None)

    @property
    def is_empty(self) -> bool:
        return len(self.candidates) == 0


class SimilarityCheckResult(BaseModel):
    """Result of repetition/similarity detection."""

    is_acceptable: bool = Field(
        ..., description="True if candidate is sufficiently distinct"
    )
    max_similarity: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description="Highest similarity score against history",
    )
    most_similar_question_id: Optional[int] = Field(
        default=None,
        description="ID of the most similar previously asked question",
    )
    similarities: Dict[int, float] = Field(
        default_factory=dict,
        description="Map of question_id → similarity score",
    )
