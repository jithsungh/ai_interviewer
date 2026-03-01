"""
Generation Module Contracts (DTOs)

Pydantic request/response models for the generation layer.
Consumed by selection module and generation service.

Reuses:
- DifficultyLevel from retrieval contracts (no duplication)
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════════════════════


class GenerationStatus(str, Enum):
    """Outcome status for a generation attempt."""

    SUCCESS = "success"
    VALIDATION_FAILED = "validation_failed"
    LLM_ERROR = "llm_error"
    FALLBACK_USED = "fallback_used"
    NO_FALLBACK = "no_fallback"


# ════════════════════════════════════════════════════════════════════════════
# Input DTOs
# ════════════════════════════════════════════════════════════════════════════


class GenerationRequest(BaseModel):
    """
    Input contract for question generation.

    Provided by the selection module when retrieval fails or
    the template mandates dynamic generation.
    """

    submission_id: int = Field(
        ..., gt=0, description="Interview submission ID"
    )
    organization_id: int = Field(
        ..., gt=0, description="Tenant ID (mandatory for isolation)"
    )
    difficulty: str = Field(
        ..., description="Requested difficulty (easy, medium, hard)"
    )
    topic: str = Field(
        ..., min_length=1, description="Primary topic for the question"
    )

    # Optional context for personalisation
    subtopic: Optional[str] = Field(
        default=None, description="Subtopic refinement"
    )
    question_type: str = Field(
        default="technical",
        description="Question type (behavioral, technical, situational, coding)",
    )
    resume_text: Optional[str] = Field(
        default=None, description="Candidate resume (parsed text)"
    )
    job_description: Optional[str] = Field(
        default=None, description="Job description text"
    )
    template_instructions: Optional[str] = Field(
        default=None, description="Section-level template instructions"
    )

    # History for deduplication
    previous_questions: List[str] = Field(
        default_factory=list,
        description="Previously asked question texts in this session",
    )
    previous_question_embeddings: List[List[float]] = Field(
        default_factory=list,
        description="Embeddings of previously asked questions",
    )

    # Performance context for cognitive progression
    last_score_percent: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Last exchange score %"
    )
    performance_trend: Optional[str] = Field(
        default=None, description="improving / declining / stable"
    )
    exchange_number: Optional[int] = Field(
        default=None, ge=1, description="Current exchange ordinal"
    )
    total_exchanges: Optional[int] = Field(
        default=None, ge=1, description="Total expected exchanges"
    )
    remaining_time_minutes: Optional[int] = Field(
        default=None, ge=0, description="Remaining interview time in minutes"
    )

    # Rubric context
    rubric_dimensions: Optional[str] = Field(
        default=None, description="Serialised rubric dimensions for scoring"
    )

    # Control
    max_retries: int = Field(
        default=3, ge=1, le=5, description="Maximum LLM retry attempts"
    )
    similarity_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Cosine similarity rejection threshold",
    )

    @field_validator("difficulty")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        allowed = {"easy", "medium", "hard"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(
                f"difficulty must be one of {allowed}, got '{v}'"
            )
        return v_lower

    @field_validator("question_type")
    @classmethod
    def validate_question_type(cls, v: str) -> str:
        allowed = {"behavioral", "technical", "situational", "coding"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(
                f"question_type must be one of {allowed}, got '{v}'"
            )
        return v_lower


# ════════════════════════════════════════════════════════════════════════════
# Output DTOs
# ════════════════════════════════════════════════════════════════════════════


class GenerationResult(BaseModel):
    """
    Output contract for a generation operation.

    Returned by QuestionGenerationService.generate().
    Contains the generated question snapshot (if successful)
    plus full audit metadata.
    """

    status: GenerationStatus
    question_text: Optional[str] = Field(default=None)
    expected_answer: Optional[str] = Field(default=None)
    difficulty: Optional[str] = Field(default=None)
    topic: Optional[str] = Field(default=None)
    subtopic: Optional[str] = Field(default=None)
    question_type: Optional[str] = Field(default=None)
    estimated_time_seconds: Optional[int] = Field(default=None)
    skill_tags: List[str] = Field(default_factory=list)

    # Source tracking
    source_type: str = Field(
        default="generated",
        description="'generated' | 'fallback_generic'",
    )

    # Audit metadata
    prompt_hash: Optional[str] = Field(default=None)
    llm_model: Optional[str] = Field(default=None)
    llm_provider: Optional[str] = Field(default=None)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    estimated_cost_usd: float = Field(default=0.0)
    generation_latency_ms: float = Field(default=0.0)
    attempts: int = Field(default=0)
    validation_failures: List[str] = Field(default_factory=list)
    similarity_score: float = Field(default=0.0)
    prompt_version: Optional[int] = Field(default=None)

    # Fallback info
    fallback_question_id: Optional[int] = Field(default=None)
    fallback_reason: Optional[str] = Field(default=None)

    generated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_success(self) -> bool:
        return self.status == GenerationStatus.SUCCESS

    @property
    def is_fallback(self) -> bool:
        return self.status == GenerationStatus.FALLBACK_USED
