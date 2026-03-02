"""
Unit Tests — Score Calculator

Tests the weighted total score calculation with pure domain logic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.evaluation.scoring.contracts import DimensionScoreResult, RubricDimensionDTO
from app.evaluation.scoring.errors import MissingDimensionError, ScoreValidationError
from app.evaluation.scoring.score_calculator import (
    ScoreCalculator,
    calculate_raw_weighted_sum,
    calculate_weighted_total,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_dimensions():
    """Sample rubric dimensions with weights."""
    return [
        RubricDimensionDTO(
            rubric_dimension_id=1,
            dimension_name="Accuracy",
            max_score=Decimal("5.0"),
            weight=Decimal("0.4"),
            description="Technical accuracy",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
        RubricDimensionDTO(
            rubric_dimension_id=2,
            dimension_name="Communication",
            max_score=Decimal("5.0"),
            weight=Decimal("0.3"),
            description="Communication clarity",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
        RubricDimensionDTO(
            rubric_dimension_id=3,
            dimension_name="Problem Solving",
            max_score=Decimal("5.0"),
            weight=Decimal("0.3"),
            description="Problem solving ability",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
    ]


@pytest.fixture
def sample_scores():
    """Sample dimension scores."""
    return [
        DimensionScoreResult(
            dimension_name="Accuracy",
            score=4.0,
            justification="Good technical accuracy",
        ),
        DimensionScoreResult(
            dimension_name="Communication",
            score=3.5,
            justification="Clear communication",
        ),
        DimensionScoreResult(
            dimension_name="Problem Solving",
            score=4.5,
            justification="Excellent problem solving",
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════
# Basic Calculation Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreCalculator:
    def test_calculate_weighted_total(self, sample_dimensions, sample_scores):
        """
        Test weighted total calculation.
        
        Expected:
        - Accuracy: (4.0/5.0) * 0.4 = 0.32
        - Communication: (3.5/5.0) * 0.3 = 0.21
        - Problem Solving: (4.5/5.0) * 0.3 = 0.27
        - Sum: 0.32 + 0.21 + 0.27 = 0.80
        - Normalized to 100: (0.80 / 1.0) * 100 = 80.0
        """
        calculator = ScoreCalculator()
        total = calculator.calculate_total_score(
            dimension_scores=sample_scores,
            dimensions=sample_dimensions,
        )
        
        assert total == Decimal("80.00")

    def test_perfect_score(self, sample_dimensions):
        """Perfect scores should yield 100."""
        perfect_scores = [
            DimensionScoreResult(
                dimension_name="Accuracy",
                score=5.0,
                justification="Perfect",
            ),
            DimensionScoreResult(
                dimension_name="Communication",
                score=5.0,
                justification="Perfect",
            ),
            DimensionScoreResult(
                dimension_name="Problem Solving",
                score=5.0,
                justification="Perfect",
            ),
        ]
        
        calculator = ScoreCalculator()
        total = calculator.calculate_total_score(
            dimension_scores=perfect_scores,
            dimensions=sample_dimensions,
        )
        
        assert total == Decimal("100.00")

    def test_zero_scores(self, sample_dimensions):
        """Zero scores should yield 0."""
        zero_scores = [
            DimensionScoreResult(
                dimension_name="Accuracy",
                score=0.0,
                justification="No answer",
            ),
            DimensionScoreResult(
                dimension_name="Communication",
                score=0.0,
                justification="No answer",
            ),
            DimensionScoreResult(
                dimension_name="Problem Solving",
                score=0.0,
                justification="No answer",
            ),
        ]
        
        calculator = ScoreCalculator()
        total = calculator.calculate_total_score(
            dimension_scores=zero_scores,
            dimensions=sample_dimensions,
        )
        
        assert total == Decimal("0.00")

    def test_decimal_precision(self):
        """Scores should be rounded to 2 decimal places."""
        dimensions = [
            RubricDimensionDTO(
                rubric_dimension_id=1,
                dimension_name="Test",
                max_score=Decimal("10.0"),
                weight=Decimal("1.0"),
                description="Test dimension",
                scoring_criteria="Test",
            ),
        ]
        
        scores = [
            DimensionScoreResult(
                dimension_name="Test",
                score=7.777,
                justification="Test",
            ),
        ]
        
        calculator = ScoreCalculator()
        total = calculator.calculate_total_score(
            dimension_scores=scores,
            dimensions=dimensions,
        )
        
        # (7.777/10.0) * 1.0 / 1.0 * 100 = 77.77
        assert total == Decimal("77.77")


# ═══════════════════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    def test_dimension_weight_zero(self):
        """Zero weight contributes 0 to total."""
        dimensions = [
            RubricDimensionDTO(
                rubric_dimension_id=1,
                dimension_name="Main",
                max_score=Decimal("5.0"),
                weight=Decimal("1.0"),
                description="Main dimension",
                scoring_criteria="Test",
            ),
            RubricDimensionDTO(
                rubric_dimension_id=2,
                dimension_name="Bonus",
                max_score=Decimal("5.0"),
                weight=Decimal("0.0"),
                description="Bonus dimension",
                scoring_criteria="Test",
            ),
        ]
        
        scores = [
            DimensionScoreResult(
                dimension_name="Main",
                score=5.0,
                justification="Perfect",
            ),
            DimensionScoreResult(
                dimension_name="Bonus",
                score=5.0,
                justification="Perfect",
            ),
        ]
        
        calculator = ScoreCalculator()
        total = calculator.calculate_total_score(
            dimension_scores=scores,
            dimensions=dimensions,
        )
        
        # Only Main counts: (5.0/5.0) * 1.0 / 1.0 * 100 = 100
        assert total == Decimal("100.00")

    def test_missing_weight_defaults_to_one(self):
        """Missing weight should default to 1.0."""
        dimensions = [
            RubricDimensionDTO(
                rubric_dimension_id=1,
                dimension_name="Test",
                max_score=Decimal("10.0"),
                weight=None,  # Missing weight
                description="Test dimension",
                scoring_criteria="Test",
            ),
        ]
        
        scores = [
            DimensionScoreResult(
                dimension_name="Test",
                score=8.0,
                justification="Good",
            ),
        ]
        
        calculator = ScoreCalculator()
        total = calculator.calculate_total_score(
            dimension_scores=scores,
            dimensions=dimensions,
        )
        
        # (8.0/10.0) * 1.0 / 1.0 * 100 = 80
        assert total == Decimal("80.00")

    def test_case_insensitive_dimension_lookup(self, sample_dimensions):
        """Dimension names should match case-insensitively."""
        scores = [
            DimensionScoreResult(
                dimension_name="ACCURACY",  # Different case
                score=5.0,
                justification="Perfect",
            ),
            DimensionScoreResult(
                dimension_name="communication",  # Different case
                score=5.0,
                justification="Perfect",
            ),
            DimensionScoreResult(
                dimension_name="Problem SOLVING",  # Different case
                score=5.0,
                justification="Perfect",
            ),
        ]
        
        calculator = ScoreCalculator()
        total = calculator.calculate_total_score(
            dimension_scores=scores,
            dimensions=sample_dimensions,
        )
        
        assert total == Decimal("100.00")


# ═══════════════════════════════════════════════════════════════════════════
# Error Handling
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorHandling:
    def test_missing_dimension_raises_error(self, sample_dimensions):
        """Missing dimension score should raise MissingDimensionError."""
        incomplete_scores = [
            DimensionScoreResult(
                dimension_name="Accuracy",
                score=4.0,
                justification="Good",
            ),
            # Missing Communication and Problem Solving
        ]
        
        calculator = ScoreCalculator()
        with pytest.raises(MissingDimensionError):
            calculator.calculate_total_score(
                dimension_scores=incomplete_scores,
                dimensions=sample_dimensions,
            )

    def test_empty_dimensions_raises_error(self):
        """Empty dimensions list should raise ScoreValidationError."""
        scores = [
            DimensionScoreResult(
                dimension_name="Test",
                score=5.0,
                justification="Test",
            ),
        ]
        
        calculator = ScoreCalculator()
        with pytest.raises(ScoreValidationError):
            calculator.calculate_total_score(
                dimension_scores=scores,
                dimensions=[],
            )

    def test_empty_scores_raises_error(self, sample_dimensions):
        """Empty scores list should raise ScoreValidationError."""
        calculator = ScoreCalculator()
        with pytest.raises(ScoreValidationError):
            calculator.calculate_total_score(
                dimension_scores=[],
                dimensions=sample_dimensions,
            )


# ═══════════════════════════════════════════════════════════════════════════
# Convenience Functions
# ═══════════════════════════════════════════════════════════════════════════


class TestConvenienceFunctions:
    def test_calculate_weighted_total_function(
        self, sample_dimensions, sample_scores
    ):
        """Test the convenience function."""
        total = calculate_weighted_total(
            dimension_scores=sample_scores,
            dimensions=sample_dimensions,
        )
        
        assert total == Decimal("80.00")

    def test_calculate_raw_weighted_sum_function(
        self, sample_dimensions, sample_scores
    ):
        """Test raw sum without normalization."""
        raw_sum = calculate_raw_weighted_sum(
            dimension_scores=sample_scores,
            dimensions=sample_dimensions,
        )
        
        # Raw sum: (4.0/5.0)*0.4 + (3.5/5.0)*0.3 + (4.5/5.0)*0.3 = 0.80
        assert raw_sum == Decimal("0.80")


# ═══════════════════════════════════════════════════════════════════════════
# Weight Validation
# ═══════════════════════════════════════════════════════════════════════════


class TestWeightValidation:
    def test_validate_weights_valid(self, sample_dimensions):
        """Valid weights should pass validation."""
        calculator = ScoreCalculator()
        calculator.validate_weights(sample_dimensions)

    def test_validate_weights_negative_raises_error(self):
        """Negative weight should raise ValidationError at DTO level."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            RubricDimensionDTO(
                rubric_dimension_id=1,
                dimension_name="Test",
                max_score=Decimal("5.0"),
                weight=Decimal("-0.5"),  # Fails Pydantic ge=0 constraint
                description="Test",
                scoring_criteria="Test",
            )

    def test_validate_weights_invalid_max_score(self):
        """Zero or negative max_score should raise ValidationError at DTO level."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            RubricDimensionDTO(
                rubric_dimension_id=1,
                dimension_name="Test",
                max_score=Decimal("0.0"),  # Fails Pydantic gt=0 constraint
                weight=Decimal("1.0"),
                description="Test",
                scoring_criteria="Test",
            )

    def test_validate_weights_empty_raises_error(self):
        """Empty dimensions should raise ScoreValidationError."""
        calculator = ScoreCalculator()
        with pytest.raises(ScoreValidationError):
            calculator.validate_weights([])
