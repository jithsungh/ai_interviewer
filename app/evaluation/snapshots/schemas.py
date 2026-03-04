"""
Evaluation Snapshots — Pydantic Schemas

Defines the structured schemas for rubric and template weight snapshots
stored as JSONB in the ``interview_results`` table.

These schemas ensure consistent structure, enable validation, and provide
typed access to frozen audit-trail data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class DimensionSnapshot(BaseModel):
    """
    Frozen state of a single rubric dimension at evaluation time.
    """

    dimension_id: int = Field(..., gt=0, description="rubric_dimensions.id")
    dimension_name: str = Field(..., min_length=1, max_length=200)
    weight: float = Field(..., ge=0, description="Scoring weight")
    max_score: float = Field(..., gt=0, description="Maximum score for this dimension")
    description: Optional[str] = Field(None, max_length=2000)
    scoring_criteria: Optional[str] = Field(None, max_length=5000)

    model_config = {"frozen": True}


class RubricSnapshot(BaseModel):
    """
    Frozen state of a rubric (with all dimensions) at evaluation time.

    Stored in ``interview_results.rubric_snapshot`` JSONB column.
    """

    rubric_id: int = Field(..., gt=0, description="rubrics.id")
    rubric_name: str = Field(..., min_length=1, max_length=300)
    rubric_description: Optional[str] = Field(None, max_length=2000)
    dimensions: List[DimensionSnapshot] = Field(
        ..., min_length=1, description="At least one dimension required"
    )
    snapshot_timestamp: datetime = Field(
        ..., description="When the snapshot was taken"
    )

    model_config = {"frozen": True}

    @field_validator("dimensions")
    @classmethod
    def _validate_unique_dimensions(
        cls, v: List[DimensionSnapshot],
    ) -> List[DimensionSnapshot]:
        ids = [d.dimension_id for d in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate dimension_id in snapshot")
        return v


class TemplateWeightSnapshot(BaseModel):
    """
    Frozen state of template section weights at evaluation time.

    Stored in ``interview_results.template_weight_snapshot`` JSONB column.
    """

    template_id: int = Field(..., gt=0, description="interview_templates.id")
    template_name: str = Field(..., min_length=1, max_length=300)
    section_weights: Dict[str, int] = Field(
        ..., min_length=1, description="Section name → weight mapping"
    )
    snapshot_timestamp: datetime = Field(
        ..., description="When the snapshot was taken"
    )

    model_config = {"frozen": True}

    @field_validator("section_weights")
    @classmethod
    def _validate_positive_weights(
        cls, v: Dict[str, int],
    ) -> Dict[str, int]:
        for section, weight in v.items():
            if weight < 0:
                raise ValueError(
                    f"Weight for section '{section}' must be >= 0, got {weight}"
                )
        return v


class MultiRubricSnapshot(BaseModel):
    """
    Container for multiple rubric snapshots (when template references
    more than one rubric).
    """

    rubrics: List[RubricSnapshot] = Field(
        ..., min_length=1, description="List of rubric snapshots"
    )
    snapshot_timestamp: datetime = Field(
        ..., description="When the snapshot was taken"
    )

    model_config = {"frozen": True}
