"""
Unit Tests — Scoring Contracts

Tests Pydantic DTOs for validation and serialization.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.evaluation.scoring.contracts import (
    AIScoreResponseSchema,
    AIScoreResult,
    DimensionScoreResult,
    ExchangeDataDTO,
    HumanDimensionScore,
    HumanScoreInput,
    RubricDimensionDTO,
    ScoringResultDTO,
)


# ═══════════════════════════════════════════════════════════════════════════
# DimensionScoreResult Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDimensionScoreResult:
    def test_valid_dimension_score(self):
        """Valid dimension score should be created."""
        score = DimensionScoreResult(
            dimension_name="Accuracy",
            score=4.5,
            justification="Good technical accuracy with minor issues.",
        )
        
        assert score.dimension_name == "Accuracy"
        assert score.score == 4.5
        assert score.justification == "Good technical accuracy with minor issues."

    def test_score_as_int(self):
        """Integer score should work."""
        score = DimensionScoreResult(
            dimension_name="Test",
            score=5,
            justification="Perfect score.",
        )
        
        assert score.score == 5.0

    def test_zero_score(self):
        """Zero score should be valid."""
        score = DimensionScoreResult(
            dimension_name="Test",
            score=0,
            justification="No attempt made.",
        )
        
        assert score.score == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# RubricDimensionDTO Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRubricDimensionDTO:
    def test_valid_dimension(self):
        """Valid rubric dimension should be created."""
        dimension = RubricDimensionDTO(
            rubric_dimension_id=1,
            dimension_name="Accuracy",
            max_score=Decimal("5.0"),
            weight=Decimal("0.4"),
            description="Technical accuracy",
            scoring_criteria="0-1 poor, 2-3 average, 4-5 excellent",
        )
        
        assert dimension.rubric_dimension_id == 1
        assert dimension.dimension_name == "Accuracy"
        assert dimension.max_score == Decimal("5.0")
        assert dimension.weight == Decimal("0.4")

    def test_optional_weight(self):
        """Weight should be optional."""
        dimension = RubricDimensionDTO(
            rubric_dimension_id=1,
            dimension_name="Accuracy",
            max_score=Decimal("5.0"),
            weight=None,
            description="Technical accuracy",
            scoring_criteria="0-1 poor, 4-5 excellent",
        )
        
        assert dimension.weight is None

    def test_optional_description(self):
        """Description should be optional."""
        dimension = RubricDimensionDTO(
            rubric_dimension_id=1,
            dimension_name="Accuracy",
            max_score=Decimal("5.0"),
            weight=Decimal("1.0"),
            description=None,
            scoring_criteria=None,
        )
        
        assert dimension.description is None


# ═══════════════════════════════════════════════════════════════════════════
# AIScoreResult Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAIScoreResult:
    def test_valid_ai_result(self):
        """Valid AI score result should be created."""
        result = AIScoreResult(
            dimension_scores=[
                DimensionScoreResult(
                    dimension_name="Accuracy",
                    score=4.5,
                    justification="Good accuracy.",
                ),
            ],
            overall_comment="Strong performance.",
            model_id="llama-3.3-70b-versatile",
        )
        
        assert len(result.dimension_scores) == 1
        assert result.overall_comment == "Strong performance."
        assert result.model_id == "llama-3.3-70b-versatile"

    def test_model_id_optional(self):
        """Model ID should be optional (human scoring)."""
        result = AIScoreResult(
            dimension_scores=[
                DimensionScoreResult(
                    dimension_name="Accuracy",
                    score=4.0,
                    justification="Good.",
                ),
            ],
            overall_comment="Comment.",
            model_id=None,
        )
        
        assert result.model_id is None


# ═══════════════════════════════════════════════════════════════════════════
# HumanScoreInput Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHumanScoreInput:
    def test_valid_human_input(self):
        """Valid human score input should be created."""
        input_data = HumanScoreInput(
            dimension_scores=[
                HumanDimensionScore(
                    rubric_dimension_id=1,
                    score=4.5,
                    justification="Good technical accuracy demonstrated.",
                ),
            ],
            overall_comment="Solid performance.",
            evaluator_id=42,
        )
        
        assert len(input_data.dimension_scores) == 1
        assert input_data.evaluator_id == 42

    def test_justification_min_length(self):
        """Justification must meet minimum length."""
        with pytest.raises(ValidationError):
            HumanDimensionScore(
                rubric_dimension_id=1,
                score=4.0,
                justification="Too short",  # Less than 10 chars
            )

    def test_justification_max_length(self):
        """Justification must not exceed maximum length."""
        long_justification = "x" * 6000  # Exceeds 5000 chars
        with pytest.raises(ValidationError):
            HumanDimensionScore(
                rubric_dimension_id=1,
                score=4.0,
                justification=long_justification,
            )

    def test_score_ge_zero(self):
        """Score must be >= 0."""
        with pytest.raises(ValidationError):
            HumanDimensionScore(
                rubric_dimension_id=1,
                score=-1.0,
                justification="Negative score test.",
            )


# ═══════════════════════════════════════════════════════════════════════════
# ExchangeDataDTO Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeDataDTO:
    def test_valid_exchange_data(self):
        """Valid exchange data should be created."""
        data = ExchangeDataDTO(
            exchange_id=123,
            question_content="What is polymorphism?",
            question_type="technical",
            answer_content="Polymorphism is...",
            transcript="User said: Polymorphism is...",
        )
        
        assert data.exchange_id == 123
        assert data.question_type == "technical"
        assert data.question_content == "What is polymorphism?"

    def test_optional_transcript(self):
        """Transcript should be optional."""
        data = ExchangeDataDTO(
            exchange_id=123,
            question_content="Question",
            question_type="text",
            answer_content="Answer",
            transcript=None,
        )
        
        assert data.transcript is None

    def test_default_answer_content(self):
        """Answer content should default to empty string."""
        data = ExchangeDataDTO(
            exchange_id=123,
            question_content="Question",
        )
        
        assert data.answer_content == ""


# ═══════════════════════════════════════════════════════════════════════════
# ScoringResultDTO Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoringResultDTO:
    def test_valid_scoring_result(self):
        """Valid scoring result should be created."""
        result = ScoringResultDTO(
            evaluation_id=1,
            interview_exchange_id=123,
            rubric_id=5,
            evaluator_type="ai",
            total_score=Decimal("82.50"),
            dimension_scores=[
                DimensionScoreResult(
                    dimension_name="Accuracy",
                    score=4.0,
                    justification="Good accuracy.",
                ),
            ],
            overall_comment="Good performance.",
            model_id="llama-3.3-70b-versatile",
            scoring_version="1.0.0",
            evaluated_at=datetime.utcnow(),
        )
        
        assert result.evaluation_id == 1
        assert result.total_score == Decimal("82.50")
        assert result.scoring_version == "1.0.0"


# ═══════════════════════════════════════════════════════════════════════════
# AIScoreResponseSchema Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestAIScoreResponseSchema:
    def test_parse_valid_response(self):
        """Valid AI response JSON should parse correctly."""
        response_data = {
            "dimension_scores": [
                {
                    "dimension_name": "Accuracy",
                    "score": 4.5,
                    "justification": "Good technical accuracy.",
                },
                {
                    "dimension_name": "Communication",
                    "score": 4.0,
                    "justification": "Clear communication.",
                },
            ],
            "overall_comment": "Strong performance overall.",
        }
        
        parsed = AIScoreResponseSchema.model_validate(response_data)
        
        assert len(parsed.dimension_scores) == 2
        assert parsed.overall_comment == "Strong performance overall."

    def test_to_ai_score_result(self):
        """Schema should convert to AIScoreResult."""
        response_data = {
            "dimension_scores": [
                {
                    "dimension_name": "Accuracy",
                    "score": 4.5,
                    "justification": "Good accuracy.",
                },
            ],
            "overall_comment": "Good.",
        }
        
        parsed = AIScoreResponseSchema.model_validate(response_data)
        result = parsed.to_ai_score_result(model_id="test-model")
        
        assert isinstance(result, AIScoreResult)
        assert result.model_id == "test-model"
        assert len(result.dimension_scores) == 1
