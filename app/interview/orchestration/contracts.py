"""
Orchestration Contracts — Pydantic DTOs

Input/output models for the orchestration layer.

Existing DTOs reused (NOT duplicated here):
- ``ExchangeCreationData``      → app.interview.exchanges.contracts
- ``ContentMetadata``           → app.interview.exchanges.contracts
- ``ExchangeQuestionType``      → app.interview.exchanges.contracts
- ``InterviewSessionDTO``       → app.interview.session.contracts.schemas
- ``InterviewSessionDetailDTO`` → app.interview.session.contracts.schemas
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ════════════════════════════════════════════════════════════════════════
# Question Sequencing
# ════════════════════════════════════════════════════════════════════════


class NextQuestionResult(BaseModel):
    """
    Result of resolving the next question from the template snapshot.

    Returned by ``resolve_next_question()`` when more questions remain.
    """

    question_id: int = Field(..., gt=0, description="Question ID from template snapshot")
    sequence_order: int = Field(..., gt=0, description="1-based contiguous sequence order")
    section_name: str = Field(..., min_length=1, description="Interview section name")
    is_final_question: bool = Field(
        ..., description="True if this is the last question in the interview"
    )


class TemplateSectionSnapshot(BaseModel):
    """
    Single section within a template snapshot.

    Validated to ensure structural integrity.
    """

    section_name: str = Field(..., min_length=1)
    question_count: int = Field(..., ge=0)
    question_ids: List[int] = Field(...)

    @field_validator("question_ids")
    @classmethod
    def validate_ids_match_count(cls, v: List[int], info) -> List[int]:
        """question_ids length must match question_count."""
        # Validation happens at snapshot level (see TemplateSnapshot)
        return v


class TemplateSnapshot(BaseModel):
    """
    Frozen template structure snapshot.

    Stored in ``interview_submissions.template_structure_snapshot`` (JSONB).
    Validated before use by the question sequencer.
    """

    template_id: int = Field(..., gt=0)
    template_name: str = Field(..., min_length=1)
    sections: List[TemplateSectionSnapshot] = Field(..., min_length=1)
    total_questions: int = Field(..., gt=0)

    @field_validator("sections")
    @classmethod
    def validate_sections_not_empty(cls, v: List[TemplateSectionSnapshot]) -> List[TemplateSectionSnapshot]:
        """At least one section required."""
        if not v:
            raise ValueError("Template snapshot must have at least one section")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate total_questions matches sum of section question_counts."""
        computed_total = sum(s.question_count for s in self.sections)
        if computed_total != self.total_questions:
            raise ValueError(
                f"total_questions ({self.total_questions}) does not match "
                f"sum of section question_counts ({computed_total})"
            )
        for section in self.sections:
            if len(section.question_ids) != section.question_count:
                raise ValueError(
                    f"Section '{section.section_name}': question_ids length "
                    f"({len(section.question_ids)}) does not match "
                    f"question_count ({section.question_count})"
                )


# ════════════════════════════════════════════════════════════════════════
# Progress Tracking
# ════════════════════════════════════════════════════════════════════════


class ProgressUpdate(BaseModel):
    """
    Progress data broadcast to clients and stored in Redis.
    """

    submission_id: int = Field(..., gt=0)
    current_sequence: int = Field(..., ge=0)
    total_questions: int = Field(..., gt=0)
    progress_percentage: float = Field(..., ge=0.0, le=100.0)
    is_complete: bool = Field(default=False)


# ════════════════════════════════════════════════════════════════════════
# Exchange Lifecycle
# ════════════════════════════════════════════════════════════════════════


class ExchangeCompletionSignal(BaseModel):
    """
    Base signal for audio/code completion events.

    Common fields for all completion signal types.
    """

    submission_id: int = Field(..., gt=0)
    sequence_order: int = Field(..., gt=0)


class AudioCompletionSignal(ExchangeCompletionSignal):
    """
    Signal emitted when audio recording + transcription is complete.

    Received from the audio module after silence detection.
    """

    recording_id: int = Field(..., gt=0)
    transcription_text: str = Field(..., min_length=1)
    duration_ms: int = Field(..., gt=0)


class CodeCompletionSignal(ExchangeCompletionSignal):
    """
    Signal emitted when code execution is complete.

    Received from the coding module after sandbox execution.
    """

    code_submission_id: Optional[int] = Field(None, gt=0)
    code: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    execution_status: str = Field(..., min_length=1)
    response_time_ms: int = Field(..., gt=0)


class TextResponseSignal(ExchangeCompletionSignal):
    """
    Signal for direct text response submission.
    """

    response_text: str = Field(..., min_length=1)
    response_time_ms: int = Field(..., gt=0)


# ════════════════════════════════════════════════════════════════════════
# Configuration
# ════════════════════════════════════════════════════════════════════════


class OrchestrationConfig(BaseModel):
    """
    Runtime configuration for the orchestration layer.

    All values have safe defaults. Override via environment or DI.
    """

    # Exchange creation
    exchange_creation_lock_timeout_seconds: int = Field(default=10, ge=1)
    exchange_max_retries: int = Field(default=3, ge=1)

    # Race condition handling
    audio_completion_grace_period_seconds: int = Field(default=2, ge=0)
    code_completion_grace_period_seconds: int = Field(default=5, ge=0)

    # Progress tracking
    progress_redis_ttl_seconds: int = Field(default=3900, ge=60)

    # Evaluation triggering
    evaluation_trigger_async: bool = Field(default=True)
