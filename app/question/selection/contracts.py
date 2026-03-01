"""
Selection Module Contracts (DTOs)

Pydantic request/response models for the question selection layer.
Consumed by interview module (caller) and selection service (internal).

Reuses:
- DifficultyLevel from retrieval contracts (no duplication)
- QuestionScope from retrieval contracts (no duplication)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════════════════════


class SelectionStrategy(str, Enum):
    """Strategy used to select the question."""

    SEMANTIC_RETRIEVAL = "semantic_retrieval"
    STATIC_POOL = "static_pool"
    ADAPTIVE = "adaptive"
    GENERATION = "generation"
    FALLBACK_GENERIC = "fallback_generic"


class FallbackType(str, Enum):
    """Type of fallback that was activated."""

    RELAXED_DIFFICULTY = "relaxed_difficulty"
    RELAXED_TOPIC = "relaxed_topic"
    RELAXED_SIMILARITY = "relaxed_similarity"
    LLM_GENERATION = "llm_generation"
    GENERIC_FALLBACK = "generic_fallback"


# ════════════════════════════════════════════════════════════════════════════
# Configuration DTOs
# ════════════════════════════════════════════════════════════════════════════


class DifficultyAdaptationConfig(BaseModel):
    """Difficulty adaptation configuration (from template snapshot)."""

    enabled: bool = Field(True, description="Enable adaptive difficulty")
    threshold_up: float = Field(
        80.0, ge=0.0, le=100.0, description="Score to increase difficulty"
    )
    threshold_down: float = Field(
        50.0, ge=0.0, le=100.0, description="Score to decrease difficulty"
    )
    max_difficulty_jump: int = Field(
        1, ge=1, le=2, description="Max difficulty levels to jump"
    )
    difficulty_order: List[str] = Field(
        default=["easy", "medium", "hard"],
        description="Difficulty progression order",
    )

    @field_validator("difficulty_order")
    @classmethod
    def validate_difficulty_order(cls, v: List[str]) -> List[str]:
        allowed = {"easy", "medium", "hard"}
        for d in v:
            if d not in allowed:
                raise ValueError(f"Invalid difficulty '{d}', must be one of {allowed}")
        if len(v) != len(set(v)):
            raise ValueError("Duplicate values in difficulty_order")
        return v


class RepetitionConfig(BaseModel):
    """Repetition prevention configuration."""

    enable_exact_match_check: bool = Field(True)
    enable_semantic_check: bool = Field(True)
    similarity_threshold_identical: float = Field(0.95, ge=0.0, le=1.0)
    similarity_threshold_similar: float = Field(0.85, ge=0.0, le=1.0)
    relax_threshold_on_exhaustion: bool = Field(True)
    relaxed_similarity_threshold: float = Field(0.90, ge=0.0, le=1.0)


# ════════════════════════════════════════════════════════════════════════════
# Input DTOs
# ════════════════════════════════════════════════════════════════════════════


class ExchangeHistoryEntry(BaseModel):
    """Single exchange from interview history (read-only input)."""

    question_id: Optional[int] = Field(default=None)
    coding_problem_id: Optional[int] = Field(default=None)
    question_text: str = Field(...)
    difficulty: str = Field(...)
    section_name: Optional[str] = Field(default=None)
    evaluation_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    question_embedding: Optional[List[float]] = Field(default=None)
    sequence_order: int = Field(..., ge=1)


class CandidateProfile(BaseModel):
    """Optional candidate profile for personalization."""

    resume_text: Optional[str] = Field(default=None)
    job_description: Optional[str] = Field(default=None)
    resume_embedding: Optional[List[float]] = Field(default=None)
    jd_embedding: Optional[List[float]] = Field(default=None)


class SectionConfig(BaseModel):
    """Parsed section from template snapshot."""

    section_name: str = Field(...)
    question_count: int = Field(..., ge=1)
    question_type: str = Field(default="technical")
    topic_constraints: List[str] = Field(default_factory=list)
    difficulty_range: List[str] = Field(default_factory=list)
    selection_strategy: str = Field(default="static_pool")
    template_instructions: Optional[str] = Field(default=None)

    @field_validator("selection_strategy")
    @classmethod
    def validate_strategy(cls, v: str) -> str:
        allowed = {"semantic_retrieval", "static_pool", "adaptive"}
        if v not in allowed:
            raise ValueError(f"selection_strategy must be one of {allowed}, got '{v}'")
        return v


class SelectionContext(BaseModel):
    """Input context for question selection."""

    submission_id: int = Field(..., gt=0)
    organization_id: int = Field(..., gt=0)
    template_snapshot: Dict[str, Any] = Field(
        ..., description="Frozen template_structure_snapshot from submission"
    )
    current_section: str = Field(
        ..., min_length=1, description="Section name to select for"
    )
    exchange_history: List[ExchangeHistoryEntry] = Field(default_factory=list)
    candidate_profile: Optional[CandidateProfile] = Field(default=None)
    exchange_sequence_order: int = Field(
        ..., ge=1, description="Next exchange ordinal"
    )


# ════════════════════════════════════════════════════════════════════════════
# Output DTOs
# ════════════════════════════════════════════════════════════════════════════


class QuestionSnapshot(BaseModel):
    """
    Immutable question snapshot for exchange creation.

    Returned by selection service → interview module persists in exchange.
    """

    # Question identification
    question_id: Optional[int] = Field(
        default=None, description="None if generated by LLM"
    )
    question_type: str = Field(...)
    question_text: str = Field(..., min_length=1)
    expected_answer: Optional[str] = Field(default=None)

    # Difficulty & topic
    difficulty: str = Field(...)
    topic_name: Optional[str] = Field(default=None)

    # Timing
    estimated_time_seconds: int = Field(default=300, ge=0)

    # Selection metadata
    selection_strategy: str = Field(...)
    selection_metadata: Dict[str, Any] = Field(default_factory=dict)

    # Audit
    selected_at: datetime = Field(default_factory=datetime.utcnow)
    selection_rule_version: str = Field(default="1.0.0")


class AdaptationDecision(BaseModel):
    """Audit record for difficulty adaptation (FR-4.4)."""

    submission_id: int = Field(..., gt=0)
    exchange_sequence_order: int = Field(..., ge=1)

    # Previous state
    previous_difficulty: Optional[str] = Field(default=None)
    previous_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    previous_question_id: Optional[int] = Field(default=None)

    # Adaptation logic
    adaptation_rule: str = Field(...)
    threshold_up: Optional[float] = Field(default=None)
    threshold_down: Optional[float] = Field(default=None)
    max_difficulty_jump: int = Field(default=1, ge=1, le=2)

    # Output
    next_difficulty: str = Field(...)
    adaptation_reason: str = Field(...)
    difficulty_changed: bool = Field(default=False)

    # Audit
    decided_at: datetime = Field(default_factory=datetime.utcnow)
    rule_version: str = Field(default="1.0.0")


class SelectionResult(BaseModel):
    """Output of question selection."""

    question_snapshot: QuestionSnapshot
    selection_metadata: Dict[str, Any] = Field(default_factory=dict)
    adaptation_decision: Optional[AdaptationDecision] = Field(default=None)
    fallback_used: bool = Field(default=False)
    fallback_type: Optional[str] = Field(default=None)
