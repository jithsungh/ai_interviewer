"""
Proctoring Risk Model Contracts — Pydantic Response Models

Defines the API-level data structures for risk score queries
and admin review queue. Strict validation, no business logic.

NOTE: ProctoringRiskDTO already exists in app.evaluation.aggregation.schemas
and is reused where evaluation needs proctoring data. These schemas are
specific to the proctoring API responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════════════════════
# Risk score response
# ════════════════════════════════════════════════════════════════════════


class RiskScoreResponse(BaseModel):
    """Full risk score response for a submission."""

    submission_id: int = Field(..., gt=0)
    total_risk: float = Field(..., ge=0)
    classification: str = Field(..., description="low | moderate | high | critical")
    recommended_action: str = Field(...)
    event_count: int = Field(..., ge=0)
    breakdown_by_type: Dict[str, Any] = Field(default_factory=dict)
    top_events: List[Dict[str, Any]] = Field(default_factory=list)
    severity_counts: Dict[str, int] = Field(default_factory=dict)
    computation_algorithm: str = Field(default="sum")
    computed_at: datetime = Field(...)

    model_config = {"frozen": True}


class RiskScoreSummaryResponse(BaseModel):
    """Lightweight risk score summary (for list views)."""

    submission_id: int = Field(..., gt=0)
    total_risk: float = Field(..., ge=0)
    classification: str = Field(...)
    event_count: int = Field(..., ge=0)
    flagged: bool = Field(default=False)


# ════════════════════════════════════════════════════════════════════════
# Admin review queue
# ════════════════════════════════════════════════════════════════════════


class ReviewQueueItem(BaseModel):
    """Single item in the admin proctoring review queue."""

    submission_id: int = Field(..., gt=0)
    total_risk: float = Field(..., ge=0)
    classification: str = Field(...)
    event_count: int = Field(..., ge=0)
    flagged: bool = Field(default=True)
    reviewed: bool = Field(default=False)


class ReviewQueueResponse(BaseModel):
    """Paginated admin review queue response."""

    total: int = Field(..., ge=0)
    items: List[ReviewQueueItem] = Field(default_factory=list)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


# ════════════════════════════════════════════════════════════════════════
# Proctoring event response (read-only)
# ════════════════════════════════════════════════════════════════════════


class ProctoringEventResponse(BaseModel):
    """Read-only representation of a proctoring event."""

    id: int
    interview_submission_id: int
    event_type: str
    severity: str
    risk_weight: float
    evidence: Dict[str, Any]
    occurred_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, model: object) -> "ProctoringEventResponse":
        """Build from ORM model."""
        return cls(
            id=model.id,
            interview_submission_id=model.interview_submission_id,
            event_type=model.event_type,
            severity=model.severity,
            risk_weight=float(model.risk_weight),
            evidence=model.evidence or {},
            occurred_at=model.occurred_at,
            created_at=model.created_at,
        )
