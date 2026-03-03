"""
Proctoring Ingestion Contracts — Pydantic Request/Response Models

Defines the API-level data structures for event ingestion.
Strict validation, no business logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.proctoring.rules.domain.rule_definitions import ALLOWED_EVENT_TYPES


# ════════════════════════════════════════════════════════════════════════
# Request schemas
# ════════════════════════════════════════════════════════════════════════


class ProctoringEventInput(BaseModel):
    """Input model for a single proctoring event."""

    submission_id: int = Field(..., gt=0, description="Interview submission ID")
    event_type: str = Field(..., min_length=1, max_length=50, description="Proctoring event type")
    timestamp: datetime = Field(..., description="When event occurred (ISO 8601)")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Evidence metadata (device info, confidence, etc.)",
    )

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in ALLOWED_EVENT_TYPES:
            raise ValueError(
                f"Unknown event type '{v}'. Allowed: {sorted(ALLOWED_EVENT_TYPES)}"
            )
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "submission_id": 42,
                    "event_type": "tab_switch",
                    "timestamp": "2026-02-14T10:30:15.234Z",
                    "metadata": {"tab_title": "[REDACTED]"},
                }
            ]
        }
    }


class BatchEventRequest(BaseModel):
    """Request model for batch event ingestion."""

    submission_id: int = Field(..., gt=0, description="Interview submission ID")
    events: List[ProctoringEventInput] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of proctoring events (max 50 per batch)",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "submission_id": 42,
                    "events": [
                        {
                            "submission_id": 42,
                            "event_type": "tab_switch",
                            "timestamp": "2026-02-14T10:30:15.234Z",
                            "metadata": {},
                        }
                    ],
                }
            ]
        }
    }


# ════════════════════════════════════════════════════════════════════════
# Response schemas
# ════════════════════════════════════════════════════════════════════════


class EventIngestionResult(BaseModel):
    """Response for single event ingestion."""

    event_id: Optional[int] = Field(None, description="Persisted event ID")
    status: str = Field(..., description="accepted | duplicate | rejected")
    message: str = Field(..., description="Human-readable status message")


class BatchIngestionResult(BaseModel):
    """Response for batch event ingestion."""

    accepted: int = Field(..., ge=0)
    rejected: int = Field(..., ge=0)
    event_ids: List[int] = Field(default_factory=list)
    errors: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Details of rejected events",
    )
