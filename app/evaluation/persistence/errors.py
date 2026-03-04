"""
Evaluation Persistence — Error Classes

Persistence-specific errors for database operations on evaluation tables.
All errors inherit from ``BaseError`` (app.shared.errors) for consistent
structured error handling through the global exception handler.
"""

from __future__ import annotations

from app.shared.errors import BaseError


class PersistenceError(BaseError):
    """Base error for evaluation persistence operations."""

    def __init__(
        self,
        message: str = "Evaluation persistence error",
        error_code: str = "EVAL_PERSISTENCE_ERROR",
        **kwargs,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            http_status_code=500,
            metadata=kwargs,
        )


class EvaluationNotFoundError(BaseError):
    """Evaluation record not found."""

    def __init__(self, evaluation_id: int) -> None:
        self.evaluation_id = evaluation_id
        super().__init__(
            error_code="EVALUATION_NOT_FOUND",
            message=f"Evaluation {evaluation_id} not found",
            http_status_code=404,
            metadata={"evaluation_id": evaluation_id},
        )


class InterviewResultNotFoundError(BaseError):
    """Interview result record not found."""

    def __init__(
        self,
        *,
        result_id: int | None = None,
        submission_id: int | None = None,
    ) -> None:
        self.result_id = result_id
        self.submission_id = submission_id
        identifier = (
            f"result_id={result_id}"
            if result_id
            else f"submission_id={submission_id}"
        )
        super().__init__(
            error_code="RESULT_NOT_FOUND",
            message=f"Interview result not found ({identifier})",
            http_status_code=404,
            metadata={
                "result_id": result_id,
                "submission_id": submission_id,
            },
        )


class DuplicateEvaluationError(BaseError):
    """Attempted to create a duplicate final evaluation for an exchange."""

    def __init__(
        self,
        interview_exchange_id: int,
        existing_evaluation_id: int | None = None,
    ) -> None:
        self.interview_exchange_id = interview_exchange_id
        self.existing_evaluation_id = existing_evaluation_id
        super().__init__(
            error_code="DUPLICATE_EVALUATION",
            message=(
                f"Exchange {interview_exchange_id} already has a final evaluation"
            ),
            http_status_code=409,
            metadata={
                "interview_exchange_id": interview_exchange_id,
                "existing_evaluation_id": existing_evaluation_id,
            },
        )


class DuplicateResultError(BaseError):
    """Attempted to create a duplicate current result for a submission."""

    def __init__(
        self,
        submission_id: int,
        existing_result_id: int | None = None,
    ) -> None:
        self.submission_id = submission_id
        self.existing_result_id = existing_result_id
        super().__init__(
            error_code="DUPLICATE_RESULT",
            message=(
                f"Submission {submission_id} already has a current result"
            ),
            http_status_code=409,
            metadata={
                "submission_id": submission_id,
                "existing_result_id": existing_result_id,
            },
        )
