"""
Unit Tests — Human Scorer

Tests human score validation with pure domain logic.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.evaluation.scoring.contracts import (
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
from app.evaluation.scoring.human_scorer import (
    HumanScorer,
    score_with_human,
    validate_dimension_scores_against_rubric,
)


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_dimensions():
    """Sample rubric dimensions."""
    return [
        RubricDimensionDTO(
            rubric_dimension_id=1,
            dimension_name="Accuracy",
            max_score=Decimal("5.0"),
            weight=Decimal("0.5"),
            description="Technical accuracy",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
        RubricDimensionDTO(
            rubric_dimension_id=2,
            dimension_name="Communication",
            max_score=Decimal("5.0"),
            weight=Decimal("0.5"),
            description="Communication clarity",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        ),
    ]


@pytest.fixture
def valid_human_input():
    """Valid human scoring input."""
    return HumanScoreInput(
        dimension_scores=[
            HumanDimensionScore(
                rubric_dimension_id=1,
                score=4.5,
                justification="Excellent technical accuracy with minor issues.",
            ),
            HumanDimensionScore(
                rubric_dimension_id=2,
                score=4.0,
                justification="Clear communication with good structure.",
            ),
        ],
        overall_comment="Strong performance overall.",
        evaluator_id=42,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Valid Scoring Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHumanScorerValid:
    def test_valid_scores_pass(self, sample_dimensions, valid_human_input):
        """Valid human scores should be accepted."""
        scorer = HumanScorer()
        result = scorer.validate_and_format(
            human_input=valid_human_input,
            dimensions=sample_dimensions,
        )
        
        assert len(result.dimension_scores) == 2
        assert result.overall_comment == "Strong performance overall."
        assert result.model_id is None  # No AI model for human scoring

    def test_dimension_names_populated(self, sample_dimensions, valid_human_input):
        """Result should have dimension names (not IDs)."""
        scorer = HumanScorer()
        result = scorer.validate_and_format(
            human_input=valid_human_input,
            dimensions=sample_dimensions,
        )
        
        dimension_names = {s.dimension_name for s in result.dimension_scores}
        assert "Accuracy" in dimension_names
        assert "Communication" in dimension_names

    def test_scores_preserved(self, sample_dimensions, valid_human_input):
        """Original scores should be preserved."""
        scorer = HumanScorer()
        result = scorer.validate_and_format(
            human_input=valid_human_input,
            dimensions=sample_dimensions,
        )
        
        accuracy_score = next(
            s for s in result.dimension_scores 
            if s.dimension_name == "Accuracy"
        )
        assert accuracy_score.score == 4.5


# ═══════════════════════════════════════════════════════════════════════════
# Missing Dimension Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestMissingDimensions:
    def test_missing_dimension_raises_error(self, sample_dimensions):
        """Missing dimension should raise MissingDimensionError."""
        partial_input = HumanScoreInput(
            dimension_scores=[
                HumanDimensionScore(
                    rubric_dimension_id=1,
                    score=4.0,
                    justification="Good technical accuracy.",
                ),
                # Missing dimension 2
            ],
            overall_comment="Partial evaluation.",
            evaluator_id=42,
        )
        
        scorer = HumanScorer()
        with pytest.raises(MissingDimensionError) as exc_info:
            scorer.validate_and_format(
                human_input=partial_input,
                dimensions=sample_dimensions,
            )
        
        assert "Communication" in exc_info.value.missing_dimensions

    def test_extra_dimension_raises_error(self, sample_dimensions):
        """Extra/unknown dimension should raise ScoreValidationError."""
        extra_input = HumanScoreInput(
            dimension_scores=[
                HumanDimensionScore(
                    rubric_dimension_id=1,
                    score=4.0,
                    justification="Good technical accuracy.",
                ),
                HumanDimensionScore(
                    rubric_dimension_id=2,
                    score=4.0,
                    justification="Good communication.",
                ),
                HumanDimensionScore(
                    rubric_dimension_id=999,  # Unknown dimension
                    score=4.0,
                    justification="Unknown dimension.",
                ),
            ],
            overall_comment="Evaluation.",
            evaluator_id=42,
        )
        
        scorer = HumanScorer()
        with pytest.raises(ScoreValidationError):
            scorer.validate_and_format(
                human_input=extra_input,
                dimensions=sample_dimensions,
            )


# ═══════════════════════════════════════════════════════════════════════════
# Score Bounds Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreBounds:
    def test_score_exceeds_max_raises_error(self, sample_dimensions):
        """Score > max_score should raise InvalidScoreError."""
        over_max = HumanScoreInput(
            dimension_scores=[
                HumanDimensionScore(
                    rubric_dimension_id=1,
                    score=6.0,  # max is 5.0
                    justification="Over maximum score.",
                ),
                HumanDimensionScore(
                    rubric_dimension_id=2,
                    score=4.0,
                    justification="Valid score.",
                ),
            ],
            overall_comment="Evaluation.",
            evaluator_id=42,
        )
        
        scorer = HumanScorer()
        with pytest.raises(InvalidScoreError) as exc_info:
            scorer.validate_and_format(
                human_input=over_max,
                dimensions=sample_dimensions,
            )
        
        assert exc_info.value.dimension_name == "Accuracy"
        assert exc_info.value.score == 6.0
        assert exc_info.value.max_score == 5.0

    def test_negative_score_raises_error(self, sample_dimensions):
        """Negative score should raise ValidationError at DTO level."""
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            HumanScoreInput(
                dimension_scores=[
                    HumanDimensionScore(
                        rubric_dimension_id=1,
                        score=-1.0,  # Negative - fails Pydantic ge=0 constraint
                        justification="Negative score.",
                    ),
                    HumanDimensionScore(
                        rubric_dimension_id=2,
                        score=4.0,
                        justification="Valid score.",
                    ),
                ],
                overall_comment="Evaluation.",
                evaluator_id=42,
            )

    def test_boundary_scores_valid(self, sample_dimensions):
        """Boundary scores (0 and max) should be valid."""
        boundary = HumanScoreInput(
            dimension_scores=[
                HumanDimensionScore(
                    rubric_dimension_id=1,
                    score=0.0,  # Minimum
                    justification="Zero score - no attempt.",
                ),
                HumanDimensionScore(
                    rubric_dimension_id=2,
                    score=5.0,  # Maximum
                    justification="Perfect score achieved.",
                ),
            ],
            overall_comment="Boundary test.",
            evaluator_id=42,
        )
        
        scorer = HumanScorer()
        result = scorer.validate_and_format(
            human_input=boundary,
            dimensions=sample_dimensions,
        )
        
        assert len(result.dimension_scores) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Justification Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestJustification:
    def test_justification_trimmed(self, sample_dimensions):
        """Justifications should be trimmed."""
        whitespace_input = HumanScoreInput(
            dimension_scores=[
                HumanDimensionScore(
                    rubric_dimension_id=1,
                    score=4.0,
                    justification="  Trimmed justification.  ",
                ),
                HumanDimensionScore(
                    rubric_dimension_id=2,
                    score=4.0,
                    justification="\n\tAnother justification.\n",
                ),
            ],
            overall_comment="Evaluation.",
            evaluator_id=42,
        )
        
        scorer = HumanScorer()
        result = scorer.validate_and_format(
            human_input=whitespace_input,
            dimensions=sample_dimensions,
        )
        
        for score in result.dimension_scores:
            assert not score.justification.startswith(" ")
            assert not score.justification.endswith(" ")


# ═══════════════════════════════════════════════════════════════════════════
# Convenience Function Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestConvenienceFunctions:
    def test_score_with_human_function(
        self, sample_dimensions, valid_human_input
    ):
        """Test the convenience function."""
        result = score_with_human(
            human_input=valid_human_input,
            dimensions=sample_dimensions,
        )
        
        assert len(result.dimension_scores) == 2
        assert result.model_id is None


# ═══════════════════════════════════════════════════════════════════════════
# Validation Function Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestValidateDimensionScores:
    def test_valid_scores_pass(self, sample_dimensions):
        """Valid dimension scores should pass validation."""
        scores = [
            DimensionScoreResult(
                dimension_name="Accuracy",
                score=4.0,
                justification="Good accuracy demonstrated.",
            ),
            DimensionScoreResult(
                dimension_name="Communication",
                score=4.0,
                justification="Clear communication shown.",
            ),
        ]
        
        # Should not raise
        validate_dimension_scores_against_rubric(scores, sample_dimensions)

    def test_duplicate_dimension_raises_error(self, sample_dimensions):
        """Duplicate dimensions should raise ScoreValidationError."""
        scores = [
            DimensionScoreResult(
                dimension_name="Accuracy",
                score=4.0,
                justification="First accuracy score.",
            ),
            DimensionScoreResult(
                dimension_name="Accuracy",  # Duplicate
                score=3.5,
                justification="Second accuracy score.",
            ),
            DimensionScoreResult(
                dimension_name="Communication",
                score=4.0,
                justification="Communication score.",
            ),
        ]
        
        with pytest.raises(ScoreValidationError) as exc_info:
            validate_dimension_scores_against_rubric(scores, sample_dimensions)
        
        assert "Duplicate" in str(exc_info.value)

    def test_case_insensitive_matching(self, sample_dimensions):
        """Dimension names should match case-insensitively."""
        scores = [
            DimensionScoreResult(
                dimension_name="ACCURACY",  # Different case
                score=4.0,
                justification="Accuracy score with uppercase.",
            ),
            DimensionScoreResult(
                dimension_name="communication",  # Different case
                score=4.0,
                justification="Communication score with lowercase.",
            ),
        ]
        
        # Should not raise
        validate_dimension_scores_against_rubric(scores, sample_dimensions)
