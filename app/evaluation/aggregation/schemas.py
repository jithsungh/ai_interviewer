"""
Evaluation Aggregation Contracts — Pydantic DTOs

Defines input/output models for the aggregation pipeline.

Design:
- Immutable data structures (frozen=True)
- Strict validation with Pydantic Field constraints
- Clear separation between computation DTOs and persistence data
- No business logic — validation only
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# SECTION AGGREGATION
# ============================================================================


class SectionScore(BaseModel):
    """
    Score breakdown for a single template section.

    Represents the aggregated score of all evaluated exchanges
    belonging to a specific interview section (e.g., resume, behavioral, coding).
    """

    section_name: str = Field(..., min_length=1, description="Template section name")
    score: Decimal = Field(..., ge=0, description="Sum of exchange total_scores in section")
    weight: int = Field(..., ge=0, description="Section weight from template")
    exchanges_evaluated: int = Field(..., ge=0, description="Number of exchanges in section")

    model_config = {"frozen": True}


# ============================================================================
# SUMMARY DATA
# ============================================================================


class SummaryData(BaseModel):
    """
    AI-generated interview summary.

    Contains strengths, weaknesses, and narrative summary.
    """

    strengths: List[str] = Field(default_factory=list, description="Top strengths identified")
    weaknesses: List[str] = Field(default_factory=list, description="Areas for improvement")
    summary_notes: str = Field(default="", description="Narrative summary")

    model_config = {"frozen": True}


class SummaryResponseSchema(BaseModel):
    """
    Schema for AI summary generation structured output.

    Used for JSON mode structured output from LLM.
    """

    strengths: List[str] = Field(..., description="3-5 key strengths")
    weaknesses: List[str] = Field(..., description="3-5 areas for improvement")
    summary_notes: str = Field(..., description="2-3 paragraph narrative summary")

    def to_summary_data(self) -> SummaryData:
        """Convert to SummaryData DTO."""
        return SummaryData(
            strengths=self.strengths,
            weaknesses=self.weaknesses,
            summary_notes=self.summary_notes,
        )

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Get JSON schema for LLM structured output."""
        return cls.model_json_schema()


# ============================================================================
# EVALUATION DATA (for aggregation input)
# ============================================================================


class EvaluationSummaryDTO(BaseModel):
    """
    Minimal evaluation data needed for aggregation.

    Fetched from evaluations table for final evaluations.
    """

    evaluation_id: int = Field(..., gt=0)
    interview_exchange_id: int = Field(..., gt=0)
    total_score: Decimal = Field(..., ge=0)
    evaluator_type: str = Field(...)

    model_config = {"frozen": True}


class ExchangeSummaryDTO(BaseModel):
    """
    Minimal exchange data needed for aggregation.

    Contains the section assignment for grouping.
    """

    exchange_id: int = Field(..., gt=0)
    sequence_order: int = Field(..., gt=0)
    section_name: str = Field(..., min_length=1)

    model_config = {"frozen": True}


# ============================================================================
# INTERVIEW RESULT (final output)
# ============================================================================


class InterviewResultData(BaseModel):
    """
    Complete aggregation result for an interview.

    Represents all computed data needed to persist an interview_results row.
    """

    model_config = {"protected_namespaces": ()}

    interview_submission_id: int = Field(..., gt=0)
    final_score: Decimal = Field(..., ge=0)
    normalized_score: Decimal = Field(..., ge=0, le=100)
    result_status: str = Field(..., description="completed | partial")
    recommendation: str = Field(
        ..., description="strong_hire | hire | review | no_hire"
    )
    section_scores: List[SectionScore] = Field(...)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    summary_notes: str = Field(default="")
    rubric_snapshot: Dict[str, Any] = Field(default_factory=dict)
    template_weight_snapshot: Dict[str, Any] = Field(default_factory=dict)
    scoring_version: str = Field(default="1.0.0")
    generated_by: str = Field(default="ai")
    model_id: Optional[int] = None

    @field_validator("recommendation")
    @classmethod
    def validate_recommendation(cls, v: str) -> str:
        """Recommendation must be one of the valid values."""
        valid = {"strong_hire", "hire", "review", "no_hire"}
        if v not in valid:
            raise ValueError(
                f"Invalid recommendation '{v}'. Must be one of: {', '.join(sorted(valid))}"
            )
        return v


# ============================================================================
# PROCTORING DATA
# ============================================================================


class ProctoringRiskDTO(BaseModel):
    """
    Proctoring risk assessment for an interview.

    Aggregated from proctoring_events table.
    """

    overall_risk: str = Field(
        ..., description="low | medium | high | critical"
    )
    total_events: int = Field(default=0, ge=0)
    high_severity_count: int = Field(default=0, ge=0)
    flagged_behaviors: List[str] = Field(default_factory=list)

    model_config = {"frozen": True}
