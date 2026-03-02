"""
Score Calculator

Calculates total scores using weighted dimension scores.

Formula: total_score = Σ (dimension_score × dimension_weight)

Design:
- Receives dimension scores from AI or human scorer
- Looks up weights from rubric dimensions
- Computes weighted sum
- Normalizes to configurable scale
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional

from app.evaluation.scoring.config import get_scoring_config
from app.evaluation.scoring.contracts import (
    AIScoreResult,
    DimensionScoreResult,
    RubricDimensionDTO,
)
from app.evaluation.scoring.errors import (
    MissingDimensionError,
    ScoreValidationError,
)
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


class ScoreCalculator:
    """
    Calculates weighted total scores from dimension scores.
    
    Uses the formula: total_score = Σ (dimension_score × dimension_weight)
    """
    
    def __init__(self, config=None):
        self._config = config or get_scoring_config()
    
    def calculate_total_score(
        self,
        dimension_scores: List[DimensionScoreResult],
        dimensions: List[RubricDimensionDTO],
        normalize: bool = True,
        normalize_scale: Optional[Decimal] = None
    ) -> Decimal:
        """
        Calculate weighted total score from dimension scores.
        
        Args:
            dimension_scores: List of dimension scores from AI or human.
            dimensions: Rubric dimensions with weights and max scores.
            normalize: Whether to normalize to consistent scale.
            normalize_scale: Scale to normalize to (default: 100).
        
        Returns:
            Total weighted score (normalized if requested).
        
        Raises:
            MissingDimensionError: Not all dimensions scored.
            ScoreValidationError: Calculation error.
        """
        if not dimensions:
            raise ScoreValidationError(message="No dimensions provided for scoring")
        
        if not dimension_scores:
            raise ScoreValidationError(message="No dimension scores provided")
        
        # Build dimension lookup by name (case-insensitive)
        dimension_lookup = {d.dimension_name.lower(): d for d in dimensions}
        
        # Verify all dimensions are scored
        expected_names = set(dimension_lookup.keys())
        scored_names = {s.dimension_name.lower() for s in dimension_scores}
        
        missing = expected_names - scored_names
        if missing:
            missing_display = [
                dimension_lookup[n].dimension_name for n in missing
            ]
            raise MissingDimensionError(missing_dimensions=missing_display)
        
        # Calculate weighted sum
        weighted_sum = Decimal("0")
        total_possible = Decimal("0")
        
        for score_result in dimension_scores:
            dim_key = score_result.dimension_name.lower()
            
            if dim_key not in dimension_lookup:
                logger.warning(
                    "Ignoring unknown dimension score",
                    extra={"dimension_name": score_result.dimension_name}
                )
                continue
            
            dimension = dimension_lookup[dim_key]
            
            # Get weight (default to 1.0 if not specified)
            weight = dimension.weight if dimension.weight else Decimal("1.0")
            
            # Calculate weighted contribution
            # Formula: (score / max_score) * weight
            if dimension.max_score > 0:
                normalized_score = (
                    Decimal(str(score_result.score)) / dimension.max_score
                ) * weight
            else:
                normalized_score = Decimal("0")
            
            weighted_sum += normalized_score
            total_possible += weight
        
        if total_possible == 0:
            logger.warning("Total possible score is zero")
            return Decimal("0")
        
        # Calculate final score
        if normalize:
            scale = (
                normalize_scale 
                if normalize_scale is not None 
                else self._config.normalized_scale
            )
            final_score = (weighted_sum / total_possible) * scale
        else:
            final_score = weighted_sum
        
        # Round to configured precision
        rounding_factor = Decimal(10) ** -self._config.score_decimal_places
        final_score = final_score.quantize(rounding_factor, rounding=ROUND_HALF_UP)
        
        logger.debug(
            "Total score calculated",
            extra={
                "weighted_sum": str(weighted_sum),
                "total_possible": str(total_possible),
                "final_score": str(final_score),
                "normalized": normalize
            }
        )
        
        return final_score
    
    def calculate_percentage_score(
        self,
        dimension_scores: List[DimensionScoreResult],
        dimensions: List[RubricDimensionDTO]
    ) -> Decimal:
        """
        Calculate score as percentage (0-100).
        
        Args:
            dimension_scores: List of dimension scores.
            dimensions: Rubric dimensions with weights and max scores.
        
        Returns:
            Percentage score (0-100).
        """
        return self.calculate_total_score(
            dimension_scores=dimension_scores,
            dimensions=dimensions,
            normalize=True,
            normalize_scale=Decimal("100")
        )
    
    def validate_weights(self, dimensions: List[RubricDimensionDTO]) -> None:
        """
        Validate that dimension weights are reasonable.
        
        Args:
            dimensions: Rubric dimensions to validate.
        
        Raises:
            ScoreValidationError: Invalid weights detected.
        """
        if not dimensions:
            raise ScoreValidationError(message="No dimensions to validate")
        
        total_weight = sum(
            d.weight if d.weight else Decimal("1.0") 
            for d in dimensions
        )
        
        if total_weight <= 0:
            raise ScoreValidationError(message="Total weight must be positive")
        
        for dim in dimensions:
            if dim.weight is not None and dim.weight < 0:
                raise ScoreValidationError(
                    message=f"Dimension '{dim.dimension_name}' has negative weight"
                )
            
            if dim.max_score <= 0:
                raise ScoreValidationError(
                    message=f"Dimension '{dim.dimension_name}' has invalid max_score"
                )


def calculate_weighted_total(
    dimension_scores: List[DimensionScoreResult],
    dimensions: List[RubricDimensionDTO]
) -> Decimal:
    """
    Calculate weighted total score.
    
    Convenience function wrapping ScoreCalculator.
    
    Args:
        dimension_scores: Scores for each dimension.
        dimensions: Rubric dimensions with weights.
    
    Returns:
        Weighted total score normalized to 100-point scale.
    """
    calculator = ScoreCalculator()
    return calculator.calculate_total_score(
        dimension_scores=dimension_scores,
        dimensions=dimensions
    )


def calculate_raw_weighted_sum(
    dimension_scores: List[DimensionScoreResult],
    dimensions: List[RubricDimensionDTO]
) -> Decimal:
    """
    Calculate raw weighted sum without normalization.
    
    Args:
        dimension_scores: Scores for each dimension.
        dimensions: Rubric dimensions with weights.
    
    Returns:
        Raw weighted sum.
    """
    calculator = ScoreCalculator()
    return calculator.calculate_total_score(
        dimension_scores=dimension_scores,
        dimensions=dimensions,
        normalize=False
    )
