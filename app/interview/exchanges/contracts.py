"""
Exchange Contracts — Pydantic DTOs

Input/output models for exchange creation and metadata.

Existing DTOs reused (NOT duplicated here):
- ``InterviewExchangeDTO`` → app.interview.session.contracts.schemas (read DTO)
- ``InterviewSessionDetailDTO`` → app.interview.session.contracts.schemas
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class ExchangeQuestionType(str, Enum):
    """
    Response modality for an exchange.

    Distinct from admin's ``QuestionType`` (behavioral/technical/situational/coding)
    which classifies question *content*. This classifies response *format*.
    """

    TEXT = "text"
    CODING = "coding"
    AUDIO = "audio"


class ContentMetadata(BaseModel):
    """
    Rich metadata stored in the ``content_metadata`` JSONB column.

    Carries extended snapshot data that complements the core exchange columns
    without requiring schema changes.
    """

    question_type: ExchangeQuestionType = Field(
        ..., description="Response modality (text, coding, audio)"
    )
    section_name: Optional[str] = Field(
        None, max_length=50, description="Interview section (resume, behavioral, coding, etc.)"
    )
    response_language: Optional[str] = Field(
        None, max_length=20, description="Programming language for coding responses"
    )
    code_submission_id: Optional[int] = Field(
        None, description="Reference to code_submissions.id for coding questions"
    )
    audio_recording_id: Optional[int] = Field(
        None, description="Reference to audio_recordings for audio questions"
    )

    # Clarification tracking
    clarification_count: int = Field(
        default=0, ge=0, description="Number of clarifications requested"
    )
    clarification_limit_exceeded: bool = Field(
        default=False, description="True if clarification limit (3) was reached"
    )
    clarification_exchange_ids: List[int] = Field(
        default_factory=list,
        description="IDs of related clarification attempt records",
    )

    # Intent classification audit trail
    intent_sequence: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Array of all intent classifications in order",
    )
    final_intent: Optional[str] = Field(
        None, description="Last classified intent (ANSWER, INVALID, etc.)"
    )
    final_intent_confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Confidence of final intent classification"
    )

    model_config = {"json_schema_extra": {"examples": [
        {
            "question_type": "text",
            "section_name": "behavioral",
            "clarification_count": 1,
            "clarification_limit_exceeded": False,
            "intent_sequence": [
                {"intent": "CLARIFICATION", "confidence": 0.95},
                {"intent": "ANSWER", "confidence": 0.88},
            ],
            "final_intent": "ANSWER",
            "final_intent_confidence": 0.88,
        }
    ]}}


class ExchangeCreationData(BaseModel):
    """
    Input DTO for immutable exchange creation.

    All data required to create a complete exchange snapshot.
    Validated BEFORE persistence — once persisted, data is immutable.
    """

    submission_id: int = Field(..., gt=0, description="Interview submission ID")
    sequence_order: int = Field(..., gt=0, description="1-based contiguous sequence")

    # Question snapshot (immutable copies)
    question_id: Optional[int] = Field(
        None, gt=0, description="Reference to questions.id"
    )
    coding_problem_id: Optional[int] = Field(
        None, gt=0, description="Reference to coding_problems.id"
    )
    question_text: str = Field(
        ..., min_length=1, description="Snapshot of question text at creation time"
    )
    expected_answer: Optional[str] = Field(
        None, description="Snapshot of expected answer"
    )
    difficulty_at_time: str = Field(
        ..., description="Difficulty level at creation time (easy/medium/hard)"
    )

    # Response snapshot (immutable copies)
    response_text: Optional[str] = Field(
        None, description="Candidate's text response"
    )
    response_code: Optional[str] = Field(
        None, description="Candidate's code response"
    )
    response_time_ms: Optional[int] = Field(
        None, ge=0, description="Response time in milliseconds"
    )

    # Metadata
    ai_followup_message: Optional[str] = Field(
        None, description="AI-generated follow-up message"
    )
    content_metadata: Optional[ContentMetadata] = Field(
        None, description="Extended snapshot metadata (question_type, section, intent data)"
    )

    @field_validator("difficulty_at_time")
    @classmethod
    def validate_difficulty(cls, v: str) -> str:
        allowed = {"easy", "medium", "hard"}
        if v not in allowed:
            raise ValueError(f"difficulty_at_time must be one of {allowed}, got {v!r}")
        return v

    @field_validator("question_id", "coding_problem_id", mode="before")
    @classmethod
    def validate_question_reference(cls, v: Any) -> Any:
        """Allow None but reject 0 or negative."""
        return v

    def model_post_init(self, __context: Any) -> None:
        """Enforce: at least one of question_id or coding_problem_id must be set."""
        if self.question_id is None and self.coding_problem_id is None:
            raise ValueError(
                "At least one of question_id or coding_problem_id must be provided"
            )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "submission_id": 1,
                    "sequence_order": 1,
                    "question_id": 101,
                    "question_text": "What is polymorphism?",
                    "difficulty_at_time": "medium",
                    "response_text": "Polymorphism is the ability of...",
                    "response_time_ms": 45000,
                    "content_metadata": {
                        "question_type": "text",
                        "section_name": "technical",
                        "clarification_count": 0,
                    },
                }
            ]
        }
    }
