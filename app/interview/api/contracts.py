"""
Interview API Contracts — Pydantic Request/Response Models

Response models for the interview API layer.
Reuses existing DTOs where possible (NOT duplicated):
- ``InterviewExchangeDTO``       → app.interview.session.contracts.schemas
- ``InterviewSessionDTO``        → app.interview.session.contracts.schemas
- ``InterviewSessionDetailDTO``  → app.interview.session.contracts.schemas
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ════════════════════════════════════════════════════════════════════════
# Exchange List Response
# ════════════════════════════════════════════════════════════════════════


class ExchangeItemDTO(BaseModel):
    """Read-only representation of a single exchange in the list."""

    exchange_id: int
    sequence_order: int
    question_text: str
    question_type: Optional[str] = Field(
        None, description="Response modality: text, coding, audio"
    )
    difficulty_at_time: str
    section_name: Optional[str] = None
    response_text: Optional[str] = None
    response_code: Optional[str] = None
    response_language: Optional[str] = None
    response_time_ms: Optional[int] = None
    ai_followup_message: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(
        cls,
        model: Any,
        include_responses: bool = True,
    ) -> "ExchangeItemDTO":
        """
        Build DTO from an InterviewExchangeModel.

        Args:
            model: ORM model instance.
            include_responses: If False, response fields are set to None.
        """
        meta = model.content_metadata or {}
        return cls(
            exchange_id=model.id,
            sequence_order=model.sequence_order,
            question_text=model.question_text,
            question_type=meta.get("question_type"),
            difficulty_at_time=model.difficulty_at_time,
            section_name=meta.get("section_name"),
            response_text=model.response_text if include_responses else None,
            response_code=model.response_code if include_responses else None,
            response_language=meta.get("response_language") if include_responses else None,
            response_time_ms=model.response_time_ms if include_responses else None,
            ai_followup_message=model.ai_followup_message if include_responses else None,
            created_at=getattr(model, "created_at", None),
        )


class ExchangeListResponse(BaseModel):
    """Response model for GET /{submission_id}/exchanges."""

    submission_id: int
    exchanges: List[ExchangeItemDTO]
    total_exchanges: int

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "submission_id": 123,
                    "exchanges": [
                        {
                            "exchange_id": 789,
                            "sequence_order": 1,
                            "question_text": "Tell me about your experience with Python.",
                            "question_type": "text",
                            "difficulty_at_time": "medium",
                            "section_name": "resume",
                            "response_text": "I have 5 years of experience...",
                            "response_time_ms": 45000,
                            "created_at": "2026-02-14T10:05:00Z",
                        }
                    ],
                    "total_exchanges": 1,
                }
            ]
        }
    }


# ════════════════════════════════════════════════════════════════════════
# Section Progress Response
# ════════════════════════════════════════════════════════════════════════


class SectionProgressDTO(BaseModel):
    """Progress for a single interview section."""

    section_name: str
    questions_total: int
    questions_answered: int
    progress_percentage: float = Field(ge=0.0, le=100.0)


class SectionProgressResponse(BaseModel):
    """Response model for GET /{submission_id}/progress."""

    submission_id: int
    overall_progress: float = Field(ge=0.0, le=100.0)
    sections: List[SectionProgressDTO]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "submission_id": 123,
                    "overall_progress": 50.0,
                    "sections": [
                        {
                            "section_name": "resume",
                            "questions_total": 2,
                            "questions_answered": 2,
                            "progress_percentage": 100.0,
                        },
                        {
                            "section_name": "coding",
                            "questions_total": 3,
                            "questions_answered": 0,
                            "progress_percentage": 0.0,
                        },
                    ],
                }
            ]
        }
    }
