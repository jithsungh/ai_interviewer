"""
Orchestration-Specific Errors

Domain errors for the interview orchestration module.
Extends the shared error hierarchy (``BaseError``).

Existing shared errors reused directly (NOT duplicated here):
- ``NotFoundError``            → app.shared.errors
- ``InterviewNotActiveError``  → app.shared.errors
- ``ConflictError``            → app.shared.errors
- ``DomainInvariantViolation`` → app.shared.errors

Existing exchange errors reused directly (NOT duplicated here):
- ``SequenceGapError``         → app.interview.exchanges.errors
- ``DuplicateSequenceError``   → app.interview.exchanges.errors
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.shared.errors import BaseError


class TemplateSnapshotMissingError(BaseError):
    """
    Raised when submission has no template_structure_snapshot.

    The template snapshot must be populated at interview creation/start.
    Orchestration cannot sequence questions without it.
    """

    def __init__(
        self,
        submission_id: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="TEMPLATE_SNAPSHOT_MISSING",
            message=(
                f"Submission {submission_id} has no template_structure_snapshot. "
                f"Snapshot must be set before orchestration can begin."
            ),
            request_id=request_id,
            metadata={"submission_id": submission_id},
            http_status_code=500,
        )


class TemplateSnapshotInvalidError(BaseError):
    """
    Raised when template_structure_snapshot has invalid structure.

    Expected shape: {template_id, template_name, sections: [...], total_questions}
    """

    def __init__(
        self,
        submission_id: int,
        reason: str,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="TEMPLATE_SNAPSHOT_INVALID",
            message=(
                f"Invalid template snapshot for submission {submission_id}: {reason}"
            ),
            request_id=request_id,
            metadata={"submission_id": submission_id, "reason": reason},
            http_status_code=500,
        )


class InterviewCompleteError(BaseError):
    """
    Raised when all questions in the template have been answered.

    The interview should transition to completed state instead of
    requesting the next question.
    """

    def __init__(
        self,
        submission_id: int,
        total_questions: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="INTERVIEW_COMPLETE",
            message=(
                f"All {total_questions} questions completed for submission "
                f"{submission_id}. Interview should be marked complete."
            ),
            request_id=request_id,
            metadata={
                "submission_id": submission_id,
                "total_questions": total_questions,
            },
            http_status_code=400,
        )


class SequenceMismatchError(BaseError):
    """
    Raised when audio/code completion signal has unexpected sequence_order.

    Indicates either a race condition (exchange already created by another
    handler) or a bug in signal routing.
    """

    def __init__(
        self,
        submission_id: int,
        expected_sequence: int,
        received_sequence: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="SEQUENCE_MISMATCH",
            message=(
                f"Sequence mismatch for submission {submission_id}: "
                f"expected {expected_sequence}, received {received_sequence}"
            ),
            request_id=request_id,
            metadata={
                "submission_id": submission_id,
                "expected_sequence": expected_sequence,
                "received_sequence": received_sequence,
            },
            http_status_code=409,
        )


class AudioNotReadyError(BaseError):
    """
    Raised when audio recording or transcription is not yet complete.

    Orchestration requires completed transcription before creating an exchange.
    """

    def __init__(
        self,
        recording_id: int,
        reason: str = "Transcription not complete",
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="AUDIO_NOT_READY",
            message=f"Audio recording {recording_id} not ready: {reason}",
            request_id=request_id,
            metadata={"recording_id": recording_id, "reason": reason},
            http_status_code=409,
        )


class CodeNotReadyError(BaseError):
    """
    Raised when code submission execution is not yet complete.

    Orchestration requires completed execution before creating an exchange.
    """

    def __init__(
        self,
        code_submission_id: int,
        reason: str = "Execution not complete",
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="CODE_NOT_READY",
            message=f"Code submission {code_submission_id} not ready: {reason}",
            request_id=request_id,
            metadata={"code_submission_id": code_submission_id, "reason": reason},
            http_status_code=409,
        )
