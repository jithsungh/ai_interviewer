"""
Human Scorer

Validates and formats human-provided scores.

Design:
- Validates human input against rubric dimensions
- Ensures all dimensions are scored
- Validates score bounds
- Validates justification requirements
- No AI interaction — validation only
"""

from __future__ import annotations

from decimal import Decimal
from typing import List

from app.evaluation.scoring.config import get_scoring_config
from app.evaluation.scoring.contracts import (
    AIScoreResult,
    DimensionScoreResult,
    HumanDimensionScore,
    HumanScoreInput,
    RubricDimensionDTO,
)
from app.evaluation.scoring.errors import (
    InvalidScoreError,
    MissingDimensionError,
    ScoreValidationError,
)
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class HumanScorer:
    """
    Validates and formats human scoring input.
    
    Ensures human-provided scores meet validation requirements.
    """
    
    def __init__(self, config=None):
        self._config = config or get_scoring_config()
    
    def validate_and_format(
        self,
        human_input: HumanScoreInput,
        dimensions: List[RubricDimensionDTO]
    ) -> AIScoreResult:
        """
        Validate human scores and convert to AIScoreResult format.
        
        Args:
            human_input: Human-provided scores.
            dimensions: Expected rubric dimensions.
        
        Returns:
            AIScoreResult with validated scores (same format as AI output).
        
        Raises:
            MissingDimensionError: Not all dimensions scored.
            InvalidScoreError: Score out of bounds.
            ScoreValidationError: Other validation failure.
        """
        # Build dimension lookup by ID
        dimension_lookup = {d.rubric_dimension_id: d for d in dimensions}
        expected_ids = set(dimension_lookup.keys())
        
        # Check all dimensions are scored
        scored_ids = {s.rubric_dimension_id for s in human_input.dimension_scores}
        missing_ids = expected_ids - scored_ids
        
        if missing_ids:
            missing_names = [
                dimension_lookup[did].dimension_name 
                for did in missing_ids
            ]
            raise MissingDimensionError(missing_dimensions=missing_names)
        
        # Check for extra dimensions
        extra_ids = scored_ids - expected_ids
        if extra_ids:
            raise ScoreValidationError(
                message=f"Unknown dimension IDs provided: {extra_ids}"
            )
        
        # Validate each score
        validated_scores: List[DimensionScoreResult] = []
        
        for human_score in human_input.dimension_scores:
            dimension = dimension_lookup[human_score.rubric_dimension_id]
            
            # Validate score bounds
            if human_score.score < 0:
                raise InvalidScoreError(
                    dimension_name=dimension.dimension_name,
                    score=float(human_score.score),
                    max_score=float(dimension.max_score)
                )
            
            if human_score.score > dimension.max_score:
                raise InvalidScoreError(
                    dimension_name=dimension.dimension_name,
                    score=float(human_score.score),
                    max_score=float(dimension.max_score)
                )
            
            # Validate justification
            if self._config.require_justification:
                justification = human_score.justification.strip()
                if len(justification) < self._config.min_justification_length:
                    raise ScoreValidationError(
                        message=f"Justification for '{dimension.dimension_name}' must be "
                                f"at least {self._config.min_justification_length} characters"
                    )
                if len(justification) > self._config.max_justification_length:
                    raise ScoreValidationError(
                        message=f"Justification for '{dimension.dimension_name}' exceeds "
                                f"maximum length of {self._config.max_justification_length} characters"
                    )
            
            validated_scores.append(DimensionScoreResult(
                dimension_name=dimension.dimension_name,
                score=human_score.score,
                justification=human_score.justification.strip()
            ))
        
        logger.info(
            "Human scoring validated",
            extra={
                "evaluator_id": human_input.evaluator_id,
                "dimension_count": len(validated_scores)
            }
        )
        
        return AIScoreResult(
            dimension_scores=validated_scores,
            overall_comment=human_input.overall_comment,
            model_id=None  # No AI model for human scoring
        )


def score_with_human(
    human_input: HumanScoreInput,
    dimensions: List[RubricDimensionDTO]
) -> AIScoreResult:
    """
    Validate and format human scores.
    
    Convenience function wrapping HumanScorer.
    
    Args:
        human_input: Human-provided scores.
        dimensions: Expected rubric dimensions.
    
    Returns:
        AIScoreResult with validated scores.
    
    Raises:
        MissingDimensionError: Not all dimensions scored.
        InvalidScoreError: Score out of bounds.
        ScoreValidationError: Other validation failure.
    """
    scorer = HumanScorer()
    return scorer.validate_and_format(human_input, dimensions)


def validate_dimension_scores_against_rubric(
    dimension_scores: List[DimensionScoreResult],
    dimensions: List[RubricDimensionDTO]
) -> None:
    """
    Validate that dimension scores match rubric requirements.
    
    Standalone validation function for use by other components.
    
    Args:
        dimension_scores: Scores to validate.
        dimensions: Expected rubric dimensions.
    
    Raises:
        MissingDimensionError: Not all dimensions scored.
        InvalidScoreError: Score out of bounds.
        ScoreValidationError: Duplicate dimensions or other issues.
    """
    config = get_scoring_config()
    
    # Build dimension lookup by name
    dimension_lookup = {d.dimension_name.lower(): d for d in dimensions}
    expected_names = set(dimension_lookup.keys())
    
    # Check for duplicates
    scored_names = [s.dimension_name.lower() for s in dimension_scores]
    if len(scored_names) != len(set(scored_names)):
        raise ScoreValidationError(message="Duplicate dimension scores detected")
    
    # Check all dimensions scored
    scored_set = set(scored_names)
    missing = expected_names - scored_set
    if missing:
        missing_display = [dimension_lookup[n].dimension_name for n in missing]
        raise MissingDimensionError(missing_dimensions=missing_display)
    
    # Check no extra dimensions
    extra = scored_set - expected_names
    if extra:
        raise ScoreValidationError(message=f"Unknown dimensions: {extra}")
    
    # Validate each score
    for score_result in dimension_scores:
        dim_key = score_result.dimension_name.lower()
        dimension = dimension_lookup[dim_key]
        
        # Check bounds
        if score_result.score < 0:
            raise InvalidScoreError(
                dimension_name=dimension.dimension_name,
                score=float(score_result.score),
                max_score=float(dimension.max_score)
            )
        
        if score_result.score > dimension.max_score:
            raise InvalidScoreError(
                dimension_name=dimension.dimension_name,
                score=float(score_result.score),
                max_score=float(dimension.max_score)
            )
        
        # Check justification
        if config.require_justification:
            justification = score_result.justification.strip() if score_result.justification else ""
            if len(justification) < config.min_justification_length:
                raise ScoreValidationError(
                    message=f"Justification for '{dimension.dimension_name}' "
                            f"must be at least {config.min_justification_length} characters"
                )
