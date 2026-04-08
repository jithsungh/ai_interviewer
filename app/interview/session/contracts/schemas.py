"""
Pydantic Schemas — Interview Session DTOs

Request / response models exchanged between the API layer and callers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════════════════
# Request schemas
# ════════════════════════════════════════════════════════════════════════


class StartInterviewRequest(BaseModel):
    """Body for POST /sessions/start."""

    submission_id: int = Field(..., gt=0, description="Interview submission ID")
    consent_accepted: bool = Field(..., description="Candidate consent flag")

    model_config = {
        "json_schema_extra": {
            "examples": [{"submission_id": 42, "consent_accepted": True}]
        }
    }


class CompleteInterviewRequest(BaseModel):
    """Body for POST /sessions/complete."""

    submission_id: int = Field(..., gt=0)

    model_config = {
        "json_schema_extra": {
            "examples": [{"submission_id": 42}]
        }
    }


class CancelInterviewRequest(BaseModel):
    """Body for POST /sessions/cancel (admin only)."""

    submission_id: int = Field(..., gt=0)
    reason: Optional[str] = Field(None, max_length=500, description="Cancellation reason")

    model_config = {
        "json_schema_extra": {
            "examples": [{"submission_id": 42, "reason": "Technical issue"}]
        }
    }


class ReviewInterviewRequest(BaseModel):
    """Body for POST /sessions/review (admin only)."""

    submission_id: int = Field(..., gt=0)
    review_notes: Optional[str] = Field(None, max_length=2000)

    model_config = {
        "json_schema_extra": {
            "examples": [{"submission_id": 42, "review_notes": "Looks good"}]
        }
    }


class ExpireOverdueRequest(BaseModel):
    """Body for POST /sessions/expire-overdue (admin only)."""

    limit: int = Field(500, ge=1, le=5000, description="Max submissions to expire in this run")


class ExpireOverdueResponse(BaseModel):
    """Result for expiry processing run."""

    expired_count: int
    limit: int


# ════════════════════════════════════════════════════════════════════════
# Response / DTO schemas
# ════════════════════════════════════════════════════════════════════════


class InterviewExchangeDTO(BaseModel):
    """Read-only representation of an interview exchange."""

    id: int
    sequence_order: int
    question_text: str
    difficulty_at_time: str
    response_text: Optional[str] = None
    response_time_ms: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InterviewSessionDTO(BaseModel):
    """Lightweight view of a submission (returned after transitions)."""

    submission_id: int
    candidate_id: int
    status: str
    mode: str
    consent_captured: bool
    started_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    version: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, model: object) -> "InterviewSessionDTO":
        """Build DTO from an ORM model or SimpleNamespace."""
        return cls(
            submission_id=model.id,
            candidate_id=model.candidate_id,
            status=model.status,
            mode=model.mode,
            consent_captured=model.consent_captured,
            started_at=getattr(model, "started_at", None),
            submitted_at=getattr(model, "submitted_at", None),
            version=getattr(model, "version", None),
            created_at=getattr(model, "created_at", None),
            updated_at=getattr(model, "updated_at", None),
        )


class InterviewSessionDetailDTO(BaseModel):
    """Full view: submission + exchanges (for GET status)."""

    session: InterviewSessionDTO
    exchanges: List[InterviewExchangeDTO] = Field(default_factory=list)

    @classmethod
    def from_model(cls, model: object) -> "InterviewSessionDetailDTO":
        """Build detail DTO from an ORM model with ``exchanges`` relationship."""
        session_dto = InterviewSessionDTO.from_model(model)
        exchange_dtos = [
            InterviewExchangeDTO(
                id=ex.id,
                sequence_order=ex.sequence_order,
                question_text=ex.question_text,
                difficulty_at_time=ex.difficulty_at_time,
                response_text=getattr(ex, "response_text", None),
                response_time_ms=getattr(ex, "response_time_ms", None),
                created_at=getattr(ex, "created_at", None),
            )
            for ex in getattr(model, "exchanges", [])
        ]
        return cls(session=session_dto, exchanges=exchange_dtos)
