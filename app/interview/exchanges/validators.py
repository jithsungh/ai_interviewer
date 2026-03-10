"""
Exchange Validators

Pure validation functions — no I/O, no framework dependencies.

Validates:
- Sequence order integrity (contiguous, no gaps, no duplicates)
- Response completeness (type-specific field requirements)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.interview.exchanges.contracts import ExchangeQuestionType
from app.interview.exchanges.errors import (
    DuplicateSequenceError,
    IncompleteResponseError,
    SequenceGapError,
)


def validate_sequence_order(
    submission_id: int,
    proposed_sequence: int,
    current_exchange_count: int,
    existing_sequence_orders: Optional[set] = None,
) -> None:
    """
    Validate that proposed sequence_order maintains contiguous ordering.

    Rules:
    1. proposed_sequence == current_exchange_count + 1 (no gaps)
    2. No duplicate sequence numbers

    Args:
        submission_id: The interview submission ID.
        proposed_sequence: The sequence order to validate.
        current_exchange_count: Number of existing exchanges for this submission.
        existing_sequence_orders: Set of existing sequence orders (optional,
            for explicit duplicate check).

    Raises:
        SequenceGapError: If a gap is detected.
        DuplicateSequenceError: If sequence already exists.
    """
    expected_sequence = current_exchange_count + 1

    # Check for duplicate (if explicit set provided)
    if existing_sequence_orders is not None and proposed_sequence in existing_sequence_orders:
        raise DuplicateSequenceError(
            sequence_order=proposed_sequence,
            submission_id=submission_id,
        )

    # Check for gap
    if proposed_sequence != expected_sequence:
        raise SequenceGapError(
            expected_sequence=expected_sequence,
            proposed_sequence=proposed_sequence,
            submission_id=submission_id,
        )


def validate_response_completeness(
    exchange_data: Dict[str, Any],
) -> None:
    """
    Validate response completeness before exchange creation.

    Rules vary by question_type (from content_metadata):
    - text:   response_text required, response_time_ms > 0
    - coding: response_code required, code_submission_id required
    - audio:  response_text (transcription) required, audio_recording_id required

    All types: response_time_ms must be > 0

    Args:
        exchange_data: Dictionary with exchange fields. Must contain
            ``content_metadata`` with ``question_type`` for type-specific checks.

    Raises:
        IncompleteResponseError: If required fields are missing or invalid.
    """
    # Extract question_type from content_metadata
    content_metadata = exchange_data.get("content_metadata") or {}
    if isinstance(content_metadata, dict):
        raw_question_type = content_metadata.get("question_type")
    else:
        # Pydantic model
        raw_question_type = getattr(content_metadata, "question_type", None)
        if raw_question_type is not None:
            raw_question_type = raw_question_type.value if hasattr(raw_question_type, "value") else raw_question_type

    if raw_question_type is None:
        # No question_type in metadata — skip type-specific validation
        # but still validate response_time_ms
        _validate_response_time(exchange_data)
        return

    question_type = raw_question_type

    if question_type == ExchangeQuestionType.TEXT.value or question_type == "text":
        if not exchange_data.get("response_text"):
            raise IncompleteResponseError(
                message="response_text required for text question",
                question_type=question_type,
            )

    elif question_type == ExchangeQuestionType.AUDIO.value or question_type == "audio":
        if not exchange_data.get("response_text"):
            raise IncompleteResponseError(
                message="response_text (transcription) required for audio question",
                question_type=question_type,
            )
        metadata_audio_id = None
        if isinstance(content_metadata, dict):
            metadata_audio_id = content_metadata.get("audio_recording_id")
        else:
            metadata_audio_id = getattr(content_metadata, "audio_recording_id", None)
        if not metadata_audio_id:
            raise IncompleteResponseError(
                message="audio_recording_id required for audio question",
                question_type=question_type,
            )

    elif question_type == ExchangeQuestionType.CODING.value or question_type == "coding":
        if not exchange_data.get("response_code"):
            raise IncompleteResponseError(
                message="response_code required for coding question",
                question_type=question_type,
            )
        # TODO: Re-enable code_submission_id validation when coding evaluation is ready
        # metadata_code_id = None
        # if isinstance(content_metadata, dict):
        #     metadata_code_id = content_metadata.get("code_submission_id")
        # else:
        #     metadata_code_id = getattr(content_metadata, "code_submission_id", None)
        # if not metadata_code_id:
        #     raise IncompleteResponseError(
        #         message="code_submission_id required for coding question",
        #         question_type=question_type,
        #     )

    else:
        raise IncompleteResponseError(
            message=f"Unknown question_type: {question_type}",
            question_type=question_type,
        )

    _validate_response_time(exchange_data)


def _validate_response_time(exchange_data: Dict[str, Any]) -> None:
    """Validate response_time_ms is positive."""
    response_time = exchange_data.get("response_time_ms")
    if response_time is not None and response_time <= 0:
        raise IncompleteResponseError(
            message="response_time_ms must be > 0",
        )
