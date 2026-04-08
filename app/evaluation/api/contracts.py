"""
Evaluation API — Request/Response Contracts

Pydantic models for all evaluation REST endpoints.
Follows the repo pattern: ``from_attributes = True``, ``from_model`` classmethods,
and explicit ``json_schema_extra`` examples.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


# Pydantic v2 treats "model_" as a protected namespace.  Our domain
# genuinely uses ``model_id`` (FK to the models table). Silence the warning
# globally for this module by declaring a base with the namespace cleared.
class _EvalBase(BaseModel):
    model_config = {"protected_namespaces": (), "from_attributes": True}


# ============================================================================
# REQUESTS
# ============================================================================


class EvaluateExchangeRequest(BaseModel):
    """POST /evaluate — trigger evaluation for an exchange."""

    interview_exchange_id: int = Field(
        ..., gt=0, description="Exchange to evaluate"
    )
    evaluator_type: Literal["ai", "human", "hybrid"] = Field(
        default="ai", description="Evaluation method"
    )
    force_reevaluate: bool = Field(
        default=False,
        description="Allow re-evaluation (creates new version)",
    )
    human_evaluator_id: Optional[int] = Field(
        None, gt=0, description="Required if evaluator_type=human or hybrid"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "interview_exchange_id": 123,
                    "evaluator_type": "ai",
                    "force_reevaluate": False,
                }
            ]
        }
    }


class DimensionScoreOverride(BaseModel):
    """Single dimension override in a human-override request."""

    rubric_dimension_id: int = Field(..., gt=0)
    new_score: float = Field(..., ge=0, description="New score value")
    justification: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Required justification for override",
    )


class HumanOverrideRequest(BaseModel):
    """POST /override — human admin overrides dimension scores."""

    evaluation_id: int = Field(..., gt=0, description="Evaluation to override")
    overrides: List[DimensionScoreOverride] = Field(
        ..., min_length=1, description="At least one dimension override"
    )
    override_reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Overall reason for override",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "evaluation_id": 456,
                    "overrides": [
                        {
                            "rubric_dimension_id": 1,
                            "new_score": 5.0,
                            "justification": "Upon closer review, the answer is fully correct and demonstrates deep understanding",
                        }
                    ],
                    "override_reason": "AI missed subtle correctness in candidate response",
                }
            ]
        }
    }


class FinalizeInterviewRequest(BaseModel):
    """POST /finalize — aggregate all evaluations into final result."""

    interview_submission_id: int = Field(
        ..., gt=0, description="Submission to finalize"
    )
    generated_by: Literal["ai", "human", "system"] = Field(
        default="ai", description="Who triggered finalization"
    )
    force_reaggregate: bool = Field(
        default=False,
        description="Create new version if result exists",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "interview_submission_id": 100,
                    "generated_by": "ai",
                    "force_reaggregate": False,
                }
            ]
        }
    }


class GenerateReportRequest(BaseModel):
    """POST /generate-report — trigger full evaluation + aggregation pipeline."""

    interview_submission_id: int = Field(
        ..., gt=0, description="Submission to generate report for"
    )
    force_regenerate: bool = Field(
        default=False,
        description="Force re-evaluation and re-aggregation",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "interview_submission_id": 100,
                    "force_regenerate": False,
                }
            ]
        }
    }


# ============================================================================
# RESPONSES
# ============================================================================


class DimensionScoreResponse(BaseModel):
    """A single dimension score in evaluation response."""

    rubric_dimension_id: int
    dimension_name: str
    score: float
    max_score: Optional[float] = None
    weight: Optional[float] = None
    justification: Optional[str] = None


class EvaluationResponse(_EvalBase):
    """Full evaluation detail response."""

    evaluation_id: int
    interview_exchange_id: int
    rubric_id: Optional[int] = None
    evaluator_type: str
    total_score: Optional[float] = None
    dimension_scores: List[DimensionScoreResponse] = Field(default_factory=list)
    explanation: Any = None
    is_final: bool
    evaluated_at: Optional[datetime] = None
    evaluated_by: Optional[int] = None
    model_id: Optional[int] = None
    scoring_version: Optional[str] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_model(
        cls,
        model: Any,
        dimension_scores: Optional[List[DimensionScoreResponse]] = None,
    ) -> "EvaluationResponse":
        """Build from EvaluationModel ORM instance."""
        return cls(
            evaluation_id=model.id,
            interview_exchange_id=model.interview_exchange_id,
            rubric_id=model.rubric_id,
            evaluator_type=model.evaluator_type,
            total_score=float(model.total_score) if model.total_score else None,
            dimension_scores=dimension_scores or [],
            explanation=model.explanation,
            is_final=model.is_final,
            evaluated_at=model.evaluated_at,
            evaluated_by=model.evaluated_by,
            model_id=model.model_id,
            scoring_version=model.scoring_version,
            created_at=model.created_at,
        )


class EvaluationOverrideResponse(_EvalBase):
    """Response for human override — includes previous eval reference."""

    evaluation_id: int
    previous_evaluation_id: int
    interview_exchange_id: int
    rubric_id: Optional[int] = None
    evaluator_type: str
    total_score: Optional[float] = None
    dimension_scores: List[DimensionScoreResponse] = Field(default_factory=list)
    explanation: Any = None
    is_final: bool
    evaluated_at: Optional[datetime] = None
    evaluated_by: Optional[int] = None


class SectionScoreResponse(BaseModel):
    """Section-level aggregated score."""

    section_name: str
    score: float
    weight: int
    exchanges_evaluated: int


class InterviewResultResponse(_EvalBase):
    """Full interview result response."""

    result_id: int
    interview_submission_id: int
    final_score: Optional[float] = None
    normalized_score: Optional[float] = None
    result_status: Optional[str] = None
    recommendation: Optional[str] = None
    section_scores: Any = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    summary_notes: Optional[str] = None
    generated_by: str
    model_id: Optional[int] = None
    scoring_version: Optional[str] = None
    is_current: bool
    computed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_model(cls, model: Any) -> "InterviewResultResponse":
        """Build from InterviewResultModel ORM instance."""
        return cls(
            result_id=model.id,
            interview_submission_id=model.interview_submission_id,
            final_score=(
                float(model.final_score) if model.final_score is not None else None
            ),
            normalized_score=(
                float(model.normalized_score)
                if model.normalized_score is not None
                else None
            ),
            result_status=model.result_status,
            recommendation=model.recommendation,
            section_scores=model.section_scores,
            strengths=model.strengths,
            weaknesses=model.weaknesses,
            summary_notes=model.summary_notes,
            generated_by=model.generated_by,
            model_id=model.model_id,
            scoring_version=model.scoring_version,
            is_current=model.is_current,
            computed_at=model.computed_at,
            created_at=model.created_at,
        )


class ExchangeEvaluationsResponse(BaseModel):
    """Response for listing evaluations of an exchange."""

    exchange_id: int
    evaluations: List[EvaluationResponse]
    current_evaluation_id: Optional[int] = None


class SubmissionResultsResponse(BaseModel):
    """Response for listing results of a submission."""

    interview_submission_id: int
    results: List[InterviewResultResponse]
    current_result_id: Optional[int] = None


class SupplementaryReportResponse(_EvalBase):
    """A single supplementary report."""

    report_id: int
    report_type: str
    content: Any
    generated_by: str
    model_id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_model(cls, model: Any) -> "SupplementaryReportResponse":
        """Build from SupplementaryReportModel ORM instance."""
        return cls(
            report_id=model.id,
            report_type=model.report_type,
            content=model.content,
            generated_by=model.generated_by,
            model_id=model.model_id,
            created_at=model.created_at,
        )


class SubmissionReportsResponse(BaseModel):
    """Response for supplementary reports of a result."""

    interview_submission_id: int
    reports: List[SupplementaryReportResponse]
