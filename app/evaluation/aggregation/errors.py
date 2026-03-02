"""
Evaluation Aggregation Errors

Extends shared error hierarchy with aggregation-specific exceptions.
All errors inherit from app.shared.errors.BaseError.

Design:
- Clear exception hierarchy for error handling
- HTTP status codes aligned with REST semantics
- Metadata included for debugging
- No business logic — error representation only
"""

from typing import Any, Dict, List, Optional

from app.shared.errors import BaseError


class AggregationError(BaseError):
    """
    Base exception for all aggregation errors.

    All aggregation-specific exceptions inherit from this class.
    """

    def __init__(
        self,
        message: str,
        error_code: str = "AGGREGATION_ERROR",
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        http_status_code: int = 500,
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=http_status_code,
        )


class IncompleteEvaluationError(AggregationError):
    """
    Not all exchanges have been evaluated.

    Raised when attempting to aggregate before all exchanges
    in the interview have final evaluations.
    """

    def __init__(
        self,
        pending_exchange_ids: List[int],
        submission_id: Optional[int] = None,
        request_id: Optional[str] = None,
    ):
        pending_count = len(pending_exchange_ids)
        super().__init__(
            error_code="INCOMPLETE_EVALUATION",
            message=(
                f"Cannot aggregate: {pending_count} exchange(s) not evaluated. "
                f"Pending exchange IDs: {pending_exchange_ids}"
            ),
            request_id=request_id,
            metadata={
                "pending_exchange_ids": pending_exchange_ids,
                "pending_count": pending_count,
                "submission_id": submission_id,
            },
            http_status_code=422,
        )
        self.pending_exchange_ids = pending_exchange_ids
        self.submission_id = submission_id


class InterviewNotFoundError(AggregationError):
    """
    Interview submission does not exist.

    Raised when the specified submission ID cannot be found.
    """

    def __init__(
        self,
        submission_id: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="INTERVIEW_NOT_FOUND",
            message=f"Interview submission {submission_id} does not exist",
            request_id=request_id,
            metadata={"submission_id": submission_id},
            http_status_code=404,
        )
        self.submission_id = submission_id


class AggregationAlreadyExistsError(AggregationError):
    """
    A current interview result already exists.

    Raised when attempting to aggregate without force flag
    and a current result already exists for the submission.
    """

    def __init__(
        self,
        submission_id: int,
        existing_result_id: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="AGGREGATION_EXISTS",
            message=(
                f"Interview submission {submission_id} already has current result "
                f"{existing_result_id}. Use force_reaggregate=true to create new version."
            ),
            request_id=request_id,
            metadata={
                "submission_id": submission_id,
                "existing_result_id": existing_result_id,
            },
            http_status_code=409,
        )
        self.submission_id = submission_id
        self.existing_result_id = existing_result_id


class TemplateWeightsNotFoundError(AggregationError):
    """
    Could not resolve template section weights.

    Raised when the interview template does not contain
    scoring_configuration.section_weights.
    """

    def __init__(
        self,
        template_id: int,
        reason: str = "No section_weights in template scoring_configuration",
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="TEMPLATE_WEIGHTS_NOT_FOUND",
            message=f"Cannot resolve section weights for template {template_id}: {reason}",
            request_id=request_id,
            metadata={"template_id": template_id, "reason": reason},
            http_status_code=422,
        )
        self.template_id = template_id


class SummaryGenerationError(AggregationError):
    """
    AI summary generation failed.

    Raised when the LLM call for summary generation fails
    after all retries. The aggregation pipeline will use
    a fallback summary instead of propagating this error.
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        final_metadata = metadata or {}
        if provider:
            final_metadata["provider"] = provider

        super().__init__(
            error_code="SUMMARY_GENERATION_FAILED",
            message=f"Summary generation failed: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=502,
        )
        self.provider = provider


class NoExchangesError(AggregationError):
    """
    Interview has no exchanges to aggregate.

    Raised when an interview submission has zero exchanges.
    """

    def __init__(
        self,
        submission_id: int,
        request_id: Optional[str] = None,
    ):
        super().__init__(
            error_code="NO_EXCHANGES",
            message=f"Interview submission {submission_id} has no exchanges to aggregate",
            request_id=request_id,
            metadata={"submission_id": submission_id},
            http_status_code=422,
        )
        self.submission_id = submission_id
