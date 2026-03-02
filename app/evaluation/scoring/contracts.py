"""
Evaluation Scoring Contracts — Pydantic DTOs

Defines input/output models for the scoring pipeline.

Design:
- Immutable data structures where possible (frozen=True for dataclasses)
- Strict validation with Pydantic Field constraints
- Clear separation between input/output contracts
- No business logic — validation only
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class EvaluatorType(str, Enum):
    """
    Type of evaluator performing the scoring.
    
    Maps to the `evaluator_type` PostgreSQL enum.
    """
    
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"


# ============================================================================
# RUBRIC CONTRACTS
# ============================================================================


class RubricDimensionDTO(BaseModel):
    """
    Rubric dimension data for scoring.
    
    Contains all information needed to score against a single dimension.
    """
    
    rubric_dimension_id: int = Field(..., gt=0, description="Dimension ID")
    dimension_name: str = Field(..., min_length=1, max_length=200, description="Dimension name")
    weight: Optional[Decimal] = Field(None, ge=0, description="Weight for total score calculation")
    max_score: Decimal = Field(..., gt=0, description="Maximum score for this dimension")
    description: Optional[str] = Field(None, max_length=2000, description="Dimension description")
    scoring_criteria: Optional[str] = Field(None, max_length=5000, description="Detailed scoring criteria")
    sequence_order: int = Field(default=0, ge=0, description="Display order")

    model_config = {"frozen": True}


class RubricDTO(BaseModel):
    """
    Complete rubric with all dimensions.
    """
    
    rubric_id: int = Field(..., gt=0)
    rubric_name: str = Field(..., min_length=1, max_length=200)
    dimensions: List[RubricDimensionDTO] = Field(..., min_length=1)

    model_config = {"frozen": True}


# ============================================================================
# EXCHANGE DATA CONTRACTS
# ============================================================================


class ExchangeDataDTO(BaseModel):
    """
    Exchange data required for scoring context.
    
    Contains question, answer, and optional transcript for AI scoring.
    """
    
    exchange_id: int = Field(..., gt=0)
    question_content: str = Field(..., min_length=1, description="Question presented to candidate")
    question_type: Optional[str] = Field(None, description="Type of question (behavioral, technical, etc.)")
    answer_content: str = Field("", description="Candidate's response content")
    transcript: Optional[str] = Field(None, description="Audio transcript if available")

    model_config = {"frozen": True}


# ============================================================================
# SCORING RESULT CONTRACTS
# ============================================================================


class DimensionScoreResult(BaseModel):
    """
    Score result for a single dimension.
    
    Output from AI or human scoring.
    """
    
    dimension_name: str = Field(..., min_length=1)
    score: Decimal = Field(..., ge=0, description="Score value (0 to max_score)")
    justification: str = Field(..., min_length=1, max_length=5000, description="Reasoning for score")

    model_config = {"frozen": True}

    @field_validator("score", mode="before")
    @classmethod
    def convert_score_to_decimal(cls, v: Any) -> Decimal:
        """Convert numeric types to Decimal."""
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v


class AIScoreResult(BaseModel):
    """
    Complete AI scoring result.
    
    Contains per-dimension scores and overall comment.
    """
    
    dimension_scores: List[DimensionScoreResult] = Field(..., min_length=1)
    overall_comment: str = Field(..., min_length=1, max_length=5000, description="Overall evaluation comment")
    model_id: Optional[str] = Field(None, description="AI model used for scoring")
    
    model_config = {"frozen": True, "protected_namespaces": ()}


# ============================================================================
# HUMAN INPUT CONTRACTS
# ============================================================================


class HumanDimensionScore(BaseModel):
    """
    Human-provided score for a single dimension.
    
    Input from admin for manual scoring.
    """
    
    rubric_dimension_id: int = Field(..., gt=0)
    score: Decimal = Field(..., ge=0)
    justification: str = Field(..., min_length=10, max_length=5000, description="Justification required")

    @field_validator("score", mode="before")
    @classmethod
    def convert_score_to_decimal(cls, v: Any) -> Decimal:
        """Convert numeric types to Decimal."""
        if isinstance(v, (int, float, str)):
            return Decimal(str(v))
        return v


class HumanScoreInput(BaseModel):
    """
    Complete human scoring input.
    
    Contains all dimension scores from human evaluator.
    """
    
    dimension_scores: List[HumanDimensionScore] = Field(..., min_length=1)
    overall_comment: str = Field(..., min_length=1, max_length=5000)
    evaluator_id: int = Field(..., gt=0, description="User ID of human evaluator")


# ============================================================================
# SERVICE OUTPUT CONTRACTS
# ============================================================================


class DimensionScoreDTO(BaseModel):
    """
    Dimension score with full context for API responses.
    """
    
    rubric_dimension_id: int = Field(..., gt=0)
    dimension_name: str
    score: Decimal
    max_score: Decimal
    weight: Decimal
    justification: str


class ScoringResultDTO(BaseModel):
    """
    Complete scoring result for an exchange.
    
    Final output of the scoring pipeline.
    """
    
    model_config = {"protected_namespaces": ()}
    
    evaluation_id: int = Field(..., gt=0)
    interview_exchange_id: int = Field(..., gt=0)
    rubric_id: int = Field(..., gt=0)
    evaluator_type: str
    total_score: Decimal = Field(..., ge=0)
    dimension_scores: List[DimensionScoreResult]
    overall_comment: Optional[str] = None
    model_id: Optional[str] = None
    scoring_version: Optional[str] = None
    evaluated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


# ============================================================================
# AI RESPONSE SCHEMA (for structured output)
# ============================================================================


class AIDimensionScoreSchema(BaseModel):
    """
    Schema for AI-generated dimension score.
    
    Used for structured output validation.
    """
    
    dimension_name: str
    score: float = Field(..., ge=0)
    justification: str


class AIScoreResponseSchema(BaseModel):
    """
    Schema for AI scoring response.
    
    Used for JSON mode structured output from LLM.
    """
    
    dimension_scores: List[AIDimensionScoreSchema]
    overall_comment: str
    
    def to_ai_score_result(self, model_id: Optional[str] = None) -> AIScoreResult:
        """Convert to AIScoreResult."""
        return AIScoreResult(
            dimension_scores=[
                DimensionScoreResult(
                    dimension_name=ds.dimension_name,
                    score=ds.score,
                    justification=ds.justification
                )
                for ds in self.dimension_scores
            ],
            overall_comment=self.overall_comment,
            model_id=model_id
        )

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Get JSON schema for LLM structured output."""
        return cls.model_json_schema()
