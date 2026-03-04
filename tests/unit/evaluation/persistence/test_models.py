"""
Unit Tests — Evaluation Persistence Models

Tests ORM model instantiation and column defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.evaluation.persistence.models import (
    EvaluationDimensionScoreModel,
    EvaluationModel,
    InterviewResultModel,
    SupplementaryReportModel,
)


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationModel Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationModel:
    def test_tablename(self):
        """Model should map to 'evaluations' table."""
        assert EvaluationModel.__tablename__ == "evaluations"

    def test_basic_instantiation(self):
        """Model should accept valid evaluation data."""
        model = EvaluationModel(
            interview_exchange_id=1,
            evaluator_type="ai",
            total_score=Decimal("85.00"),
            is_final=True,
        )
        assert model.interview_exchange_id == 1
        assert model.evaluator_type == "ai"
        assert model.total_score == Decimal("85.00")
        assert model.is_final is True

    def test_nullable_fields(self):
        """Optional fields should accept None."""
        model = EvaluationModel(
            interview_exchange_id=1,
            evaluator_type="human",
            total_score=None,
            explanation=None,
            rubric_id=None,
            model_id=None,
            evaluated_by=None,
            scoring_version=None,
        )
        assert model.rubric_id is None
        assert model.model_id is None
        assert model.explanation is None
        assert model.evaluated_by is None
        assert model.scoring_version is None

    def test_jsonb_explanation(self):
        """Explanation should accept dict (JSONB)."""
        model = EvaluationModel(
            interview_exchange_id=1,
            evaluator_type="ai",
            total_score=Decimal("90"),
            explanation={"overall": "Strong performance", "notes": ["a", "b"]},
        )
        assert model.explanation["overall"] == "Strong performance"

    def test_dev49_fields(self):
        """DEV-49 migration columns should be present."""
        model = EvaluationModel(
            interview_exchange_id=1,
            evaluator_type="hybrid",
            total_score=Decimal("80"),
            evaluated_by=42,
            scoring_version="v2.1",
        )
        assert model.evaluated_by == 42
        assert model.scoring_version == "v2.1"

    def test_extend_existing(self):
        """Table args should include extend_existing=True."""
        assert EvaluationModel.__table_args__[0].get("extend_existing") is True

    def test_repr(self):
        """Repr should contain key identifiers."""
        model = EvaluationModel(
            id=10,
            interview_exchange_id=5,
            evaluator_type="ai",
            is_final=True,
        )
        r = repr(model)
        assert "10" in r
        assert "5" in r
        assert "ai" in r


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationDimensionScoreModel Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationDimensionScoreModel:
    def test_tablename(self):
        """Model should map to 'evaluation_dimension_scores' table."""
        assert (
            EvaluationDimensionScoreModel.__tablename__
            == "evaluation_dimension_scores"
        )

    def test_basic_instantiation(self):
        """Model should accept valid dimension score data."""
        model = EvaluationDimensionScoreModel(
            evaluation_id=1,
            rubric_dimension_id=2,
            score=Decimal("4.5"),
            justification="Good answer.",
        )
        assert model.evaluation_id == 1
        assert model.rubric_dimension_id == 2
        assert model.score == Decimal("4.5")
        assert model.justification == "Good answer."

    def test_max_score_dev49(self):
        """DEV-49 max_score column should be present."""
        model = EvaluationDimensionScoreModel(
            evaluation_id=1,
            rubric_dimension_id=2,
            score=Decimal("4.0"),
            max_score=Decimal("5.0"),
        )
        assert model.max_score == Decimal("5.0")

    def test_nullable_justification(self):
        """Justification should accept None."""
        model = EvaluationDimensionScoreModel(
            evaluation_id=1,
            rubric_dimension_id=2,
            score=Decimal("3"),
            justification=None,
        )
        assert model.justification is None

    def test_extend_existing(self):
        """Table args should include extend_existing=True."""
        assert (
            EvaluationDimensionScoreModel.__table_args__[0].get("extend_existing")
            is True
        )

    def test_repr(self):
        """Repr should contain key identifiers."""
        model = EvaluationDimensionScoreModel(
            id=7, evaluation_id=3, rubric_dimension_id=5, score=Decimal("4.0")
        )
        r = repr(model)
        assert "7" in r
        assert "3" in r


# ═══════════════════════════════════════════════════════════════════════════
# InterviewResultModel Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewResultModel:
    def test_tablename(self):
        """Model should map to 'interview_results' table."""
        assert InterviewResultModel.__tablename__ == "interview_results"

    def test_basic_instantiation(self):
        """Model should accept required fields."""
        now = datetime.now(timezone.utc)
        model = InterviewResultModel(
            interview_submission_id=10,
            scoring_version="v1.0",
            generated_by="ai",
            result_status="pass",
            recommendation="hire",
            is_current=True,
            computed_at=now,
        )
        assert model.interview_submission_id == 10
        assert model.scoring_version == "v1.0"
        assert model.generated_by == "ai"
        assert model.is_current is True

    def test_jsonb_fields(self):
        """JSONB fields should accept dicts."""
        model = InterviewResultModel(
            interview_submission_id=10,
            scoring_version="v1.0",
            generated_by="ai",
            computed_at=datetime.now(timezone.utc),
            rubric_snapshot={"rubric_id": 1, "dimensions": []},
            template_weight_snapshot={"template_id": 5, "section_weights": {}},
            section_scores={"technical": 85.0, "behavioral": 90.0},
        )
        assert model.rubric_snapshot["rubric_id"] == 1
        assert model.section_scores["technical"] == 85.0

    def test_nullable_fields(self):
        """Optional fields should accept None."""
        model = InterviewResultModel(
            interview_submission_id=10,
            scoring_version="v1.0",
            generated_by="ai",
            computed_at=datetime.now(timezone.utc),
            final_score=None,
            normalized_score=None,
            strengths=None,
            weaknesses=None,
            summary_notes=None,
            model_id=None,
        )
        assert model.final_score is None
        assert model.strengths is None

    def test_extend_existing(self):
        """Table args should include extend_existing=True."""
        assert InterviewResultModel.__table_args__[0].get("extend_existing") is True

    def test_repr(self):
        """Repr should contain key identifiers."""
        model = InterviewResultModel(
            id=15, interview_submission_id=10, is_current=True
        )
        r = repr(model)
        assert "15" in r
        assert "10" in r


# ═══════════════════════════════════════════════════════════════════════════
# SupplementaryReportModel Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSupplementaryReportModel:
    def test_tablename(self):
        """Model should map to 'supplementary_reports' table."""
        assert SupplementaryReportModel.__tablename__ == "supplementary_reports"

    def test_basic_instantiation(self):
        """Model should accept valid report data."""
        model = SupplementaryReportModel(
            interview_submission_id=20,
            report_type="technical_breakdown",
            content={"sections": [{"name": "technical", "score": 85}]},
            generated_by="ai",
        )
        assert model.interview_submission_id == 20
        assert model.report_type == "technical_breakdown"
        assert model.content["sections"][0]["score"] == 85

    def test_nullable_model_id(self):
        """model_id should accept None."""
        model = SupplementaryReportModel(
            interview_submission_id=20,
            report_type="candidate_summary",
            content={"summary": "Good candidate"},
            generated_by="system",
            model_id=None,
        )
        assert model.model_id is None

    def test_extend_existing(self):
        """Table args should include extend_existing=True."""
        assert SupplementaryReportModel.__table_args__[0].get("extend_existing") is True

    def test_repr(self):
        """Repr should contain key identifiers."""
        model = SupplementaryReportModel(
            id=3,
            interview_submission_id=20,
            report_type="proctoring_risk",
        )
        r = repr(model)
        assert "3" in r
        assert "20" in r
