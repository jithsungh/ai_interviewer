"""
Exchange-Specific Errors

Domain errors for the interview exchanges module. These extend the shared
error hierarchy (``BaseError``) and are NOT duplicating existing classes.

Existing shared errors reused directly:
- ``ExchangeImmutabilityViolation`` → app.shared.errors
- ``NotFoundError``                → app.shared.errors
- ``ConflictError``                → app.shared.errors
- ``ValidationError``              → app.shared.errors
- ``DomainInvariantViolation``     → app.shared.errors
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.shared.errors import BaseError


class SequenceGapError(BaseError):
    """
    Raised when proposed sequence_order creates a gap in exchange ordering.

    Exchange sequence must be contiguous: 1, 2, 3, ... with no gaps.
    """

    def __init__(
        self,
        expected_sequence: int,
        proposed_sequence: int,
        submission_id: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="SEQUENCE_GAP",
            message=(
                f"Sequence gap detected for submission {submission_id}: "
                f"expected {expected_sequence}, got {proposed_sequence}"
            ),
            request_id=request_id,
            metadata={
                "submission_id": submission_id,
                "expected_sequence": expected_sequence,
                "proposed_sequence": proposed_sequence,
            },
            http_status_code=422,
        )


class DuplicateSequenceError(BaseError):
    """
    Raised when an exchange already exists for the given sequence_order.

    Redundant with the DB UNIQUE constraint but provides an explicit
    application-level check.
    """

    def __init__(
        self,
        sequence_order: int,
        submission_id: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="DUPLICATE_SEQUENCE",
            message=(
                f"Exchange already exists for submission {submission_id} "
                f"at sequence {sequence_order}"
            ),
            request_id=request_id,
            metadata={
                "submission_id": submission_id,
                "sequence_order": sequence_order,
            },
            http_status_code=409,
        )


class IncompleteResponseError(BaseError):
    """
    Raised when exchange data is incomplete for the given question type.

    Response completeness rules:
    - text:   response_text required, response_time_ms > 0
    - coding: response_code required, code_submission_id required
    - audio:  response_text (transcription) required, audio_recording_id required
    """

    def __init__(
        self,
        message: str,
        question_type: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        metadata: Dict[str, Any] = {}
        if question_type:
            metadata["question_type"] = question_type

        super().__init__(
            error_code="INCOMPLETE_RESPONSE",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=422,
        )


class ClassificationError(BaseError):
    """
    Raised when utterance intent classification fails.

    Classification must complete within 500ms and produce deterministic output.
    """

    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            error_code="CLASSIFICATION_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata or {},
            http_status_code=500,
        )


class ClarificationLimitExceededError(BaseError):
    """
    Raised when candidate exceeds the maximum clarification count (3).

    After this limit, the exchange auto-transitions to ANSWER_SUBMITTED.
    """

    def __init__(
        self,
        exchange_id: int,
        clarification_count: int,
        max_clarifications: int = 3,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="CLARIFICATION_LIMIT_EXCEEDED",
            message=(
                f"Clarification limit ({max_clarifications}) exceeded "
                f"for exchange {exchange_id} (count: {clarification_count})"
            ),
            request_id=request_id,
            metadata={
                "exchange_id": exchange_id,
                "clarification_count": clarification_count,
                "max_clarifications": max_clarifications,
            },
            http_status_code=400,
        )


class InvalidExchangeStateTransitionError(BaseError):
    """
    Raised when a question state machine transition is invalid.

    The question state machine governs exchange lifecycle:
    ASKED → WAITING_INPUT → ANSWER_SUBMITTED → EVALUATED → NEXT_QUESTION
    """

    def __init__(
        self,
        current_state: str,
        target_state: str,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="INVALID_EXCHANGE_STATE_TRANSITION",
            message=f"Invalid exchange state transition: {current_state!r} → {target_state!r}",
            request_id=request_id,
            metadata={
                "current_state": current_state,
                "target_state": target_state,
            },
            http_status_code=409,
        )
