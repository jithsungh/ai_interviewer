"""
Evaluation Scoring Errors

Extends shared error hierarchy with scoring-specific exceptions.
All errors inherit from app.shared.errors exceptions.

Design:
- Clear exception hierarchy for error handling
- HTTP status codes aligned with REST semantics
- Metadata included for debugging
- No business logic — error representation only
"""

from typing import Any, Dict, Optional

from app.shared.errors import BaseError, ValidationError


class ScoringError(BaseError):
    """
    Base exception for all scoring errors.
    
    All scoring-specific exceptions inherit from this class.
    """
    
    def __init__(
        self,
        message: str,
        error_code: str = "SCORING_ERROR",
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        http_status_code: int = 500
    ):
        super().__init__(
            error_code=error_code,
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=http_status_code
        )


class ExchangeNotFoundError(ScoringError):
    """
    Exchange does not exist.
    
    Raised when attempting to score a non-existent exchange.
    """
    
    def __init__(
        self,
        exchange_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="EXCHANGE_NOT_FOUND",
            message=f"Interview exchange {exchange_id} does not exist",
            request_id=request_id,
            metadata={"exchange_id": exchange_id},
            http_status_code=404
        )
        self.exchange_id = exchange_id


class RubricNotFoundError(ScoringError):
    """
    No rubric linked to template.
    
    Raised when the exchange's template has no associated rubric.
    """
    
    def __init__(
        self,
        template_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="RUBRIC_NOT_FOUND",
            message=f"No rubric found for template {template_id}",
            request_id=request_id,
            metadata={"template_id": template_id},
            http_status_code=422
        )
        self.template_id = template_id


class InvalidRubricError(ScoringError):
    """
    Rubric has invalid configuration.
    
    Raised when rubric has 0 dimensions or invalid structure.
    """
    
    def __init__(
        self,
        rubric_id: int,
        reason: str,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="INVALID_RUBRIC",
            message=f"Rubric {rubric_id} is invalid: {reason}",
            request_id=request_id,
            metadata={"rubric_id": rubric_id, "reason": reason},
            http_status_code=422
        )
        self.rubric_id = rubric_id
        self.reason = reason


class AIEvaluationError(ScoringError):
    """
    AI evaluation failed.
    
    Raised when LLM call fails after all retries,
    or when response cannot be parsed.
    """
    
    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retries_attempted: int = 0,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "provider": provider,
            "retries_attempted": retries_attempted
        })
        
        super().__init__(
            error_code="AI_EVALUATION_FAILED",
            message=f"AI evaluation failed: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=502
        )
        self.provider = provider
        self.retries_attempted = retries_attempted


class InvalidScoreError(ScoringError):
    """
    Score value is invalid.
    
    Raised when score is negative or exceeds max_score.
    """
    
    def __init__(
        self,
        dimension_name: str,
        score: float,
        max_score: float,
        request_id: Optional[str] = None
    ):
        if score < 0:
            reason = f"negative score {score}"
        else:
            reason = f"score {score} exceeds max_score {max_score}"
        
        super().__init__(
            error_code="INVALID_SCORE",
            message=f"Invalid score for dimension '{dimension_name}': {reason}",
            request_id=request_id,
            metadata={
                "dimension_name": dimension_name,
                "score": score,
                "max_score": max_score
            },
            http_status_code=422
        )
        self.dimension_name = dimension_name
        self.score = score
        self.max_score = max_score


class MissingDimensionError(ScoringError):
    """
    Not all dimensions scored.
    
    Raised when scoring result is missing required dimensions.
    """
    
    def __init__(
        self,
        missing_dimensions: list[str],
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="MISSING_DIMENSIONS",
            message=f"Missing scores for dimensions: {', '.join(missing_dimensions)}",
            request_id=request_id,
            metadata={"missing_dimensions": missing_dimensions},
            http_status_code=422
        )
        self.missing_dimensions = missing_dimensions


class ScoreValidationError(ScoringError):
    """
    Score validation failed.
    
    Generic validation error for scoring issues.
    """
    
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            error_code="SCORE_VALIDATION_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=422
        )


class EvaluationExistsError(ScoringError):
    """
    Evaluation already exists for exchange.
    
    Raised when attempting to create duplicate evaluation
    without force_reevaluate flag.
    """
    
    def __init__(
        self,
        exchange_id: int,
        existing_evaluation_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="EVALUATION_EXISTS",
            message=f"Exchange {exchange_id} already has evaluation {existing_evaluation_id}. "
                    f"Use force_reevaluate=true to create new version.",
            request_id=request_id,
            metadata={
                "exchange_id": exchange_id,
                "existing_evaluation_id": existing_evaluation_id
            },
            http_status_code=409
        )
        self.exchange_id = exchange_id
        self.existing_evaluation_id = existing_evaluation_id


class ExchangeNotAnsweredError(ScoringError):
    """
    Exchange has no response to evaluate.
    
    Raised when attempting to evaluate exchange without answer.
    """
    
    def __init__(
        self,
        exchange_id: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="EXCHANGE_NOT_ANSWERED",
            message=f"Exchange {exchange_id} has no response to evaluate",
            request_id=request_id,
            metadata={"exchange_id": exchange_id},
            http_status_code=422
        )
        self.exchange_id = exchange_id
