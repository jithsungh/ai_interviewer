"""
Unit Tests — Evaluation API Contracts

Tests Pydantic request/response models for validation and serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.evaluation.api.contracts import (
    DimensionScoreOverride,
    DimensionScoreResponse,
    EvaluateExchangeRequest,
    EvaluationOverrideResponse,
    EvaluationResponse,
    ExchangeEvaluationsResponse,
    FinalizeInterviewRequest,
    HumanOverrideRequest,
    InterviewResultResponse,
    SubmissionReportsResponse,
    SubmissionResultsResponse,
    SupplementaryReportResponse,
)


NOW = datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════
# EvaluateExchangeRequest Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluateExchangeRequest:
    def test_valid_minimal(self):
        """Minimal request should be valid."""
        req = EvaluateExchangeRequest(interview_exchange_id=1)
        assert req.interview_exchange_id == 1
        assert req.evaluator_type == "ai"
        assert req.force_reevaluate is False
        assert req.human_evaluator_id is None

    def test_valid_human(self):
        """Human evaluator request should include evaluator ID."""
        req = EvaluateExchangeRequest(
            interview_exchange_id=1,
            evaluator_type="human",
            human_evaluator_id=42,
        )
        assert req.evaluator_type == "human"
        assert req.human_evaluator_id == 42

    def test_exchange_id_gt_zero(self):
        """Exchange ID must be > 0."""
        with pytest.raises(ValidationError):
            EvaluateExchangeRequest(interview_exchange_id=0)

    def test_invalid_evaluator_type(self):
        """Invalid evaluator type should be rejected."""
        with pytest.raises(ValidationError):
            EvaluateExchangeRequest(
                interview_exchange_id=1, evaluator_type="robot"
            )

    def test_force_reevaluate_flag(self):
        """force_reevaluate=True should be accepted."""
        req = EvaluateExchangeRequest(
            interview_exchange_id=1, force_reevaluate=True
        )
        assert req.force_reevaluate is True


# ═══════════════════════════════════════════════════════════════════════════
# DimensionScoreOverride Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestDimensionScoreOverride:
    def test_valid_override(self):
        """Valid override should be created."""
        ovr = DimensionScoreOverride(
            rubric_dimension_id=1,
            new_score=4.5,
            justification="Upon review, the answer fully addresses the question",
        )
        assert ovr.rubric_dimension_id == 1
        assert ovr.new_score == 4.5

    def test_score_ge_zero(self):
        """Score must be >= 0."""
        with pytest.raises(ValidationError):
            DimensionScoreOverride(
                rubric_dimension_id=1,
                new_score=-1.0,
                justification="This should fail for negative score value",
            )

    def test_justification_min_length(self):
        """Justification must be at least 10 chars."""
        with pytest.raises(ValidationError):
            DimensionScoreOverride(
                rubric_dimension_id=1,
                new_score=4.0,
                justification="Short",
            )

    def test_justification_max_length(self):
        """Justification must not exceed 5000 chars."""
        with pytest.raises(ValidationError):
            DimensionScoreOverride(
                rubric_dimension_id=1,
                new_score=4.0,
                justification="x" * 5001,
            )


# ═══════════════════════════════════════════════════════════════════════════
# HumanOverrideRequest Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestHumanOverrideRequest:
    def _make_override(self) -> DimensionScoreOverride:
        return DimensionScoreOverride(
            rubric_dimension_id=1,
            new_score=5.0,
            justification="Fully correct answer upon careful review",
        )

    def test_valid_request(self):
        """Valid override request should be created."""
        req = HumanOverrideRequest(
            evaluation_id=10,
            overrides=[self._make_override()],
            override_reason="AI underscored the candidate's technical response",
        )
        assert req.evaluation_id == 10
        assert len(req.overrides) == 1

    def test_empty_overrides_rejected(self):
        """At least one override is required."""
        with pytest.raises(ValidationError):
            HumanOverrideRequest(
                evaluation_id=10,
                overrides=[],
                override_reason="Need at least one override here",
            )

    def test_override_reason_min_length(self):
        """Override reason must be at least 10 chars."""
        with pytest.raises(ValidationError):
            HumanOverrideRequest(
                evaluation_id=10,
                overrides=[self._make_override()],
                override_reason="Short",
            )


# ═══════════════════════════════════════════════════════════════════════════
# FinalizeInterviewRequest Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestFinalizeInterviewRequest:
    def test_valid_minimal(self):
        """Minimal finalize request should be valid."""
        req = FinalizeInterviewRequest(interview_submission_id=100)
        assert req.interview_submission_id == 100
        assert req.generated_by == "ai"
        assert req.force_reaggregate is False

    def test_submission_id_gt_zero(self):
        """Submission ID must be > 0."""
        with pytest.raises(ValidationError):
            FinalizeInterviewRequest(interview_submission_id=0)

    def test_invalid_generated_by(self):
        """Invalid generated_by should be rejected."""
        with pytest.raises(ValidationError):
            FinalizeInterviewRequest(
                interview_submission_id=1, generated_by="bot"
            )


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationResponse Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationResponse:
    def test_from_model(self):
        """from_model should transform ORM model to response."""
        mock_model = Mock()
        mock_model.id = 1
        mock_model.interview_exchange_id = 10
        mock_model.rubric_id = 2
        mock_model.evaluator_type = "ai"
        mock_model.total_score = Decimal("85.50")
        mock_model.explanation = {"overall": "Good"}
        mock_model.is_final = True
        mock_model.evaluated_at = NOW
        mock_model.evaluated_by = None
        mock_model.model_id = 5
        mock_model.scoring_version = "v1.0"
        mock_model.created_at = NOW

        response = EvaluationResponse.from_model(mock_model)

        assert response.evaluation_id == 1
        assert response.interview_exchange_id == 10
        assert response.total_score == 85.50
        assert response.evaluator_type == "ai"
        assert response.is_final is True

    def test_from_model_with_dimension_scores(self):
        """from_model should include dimension scores when provided."""
        mock_model = Mock()
        mock_model.id = 1
        mock_model.interview_exchange_id = 10
        mock_model.rubric_id = 2
        mock_model.evaluator_type = "ai"
        mock_model.total_score = Decimal("85")
        mock_model.explanation = None
        mock_model.is_final = True
        mock_model.evaluated_at = NOW
        mock_model.evaluated_by = None
        mock_model.model_id = None
        mock_model.scoring_version = None
        mock_model.created_at = NOW

        dim_scores = [
            DimensionScoreResponse(
                rubric_dimension_id=1,
                dimension_name="Accuracy",
                score=4.5,
                max_score=5.0,
                weight=0.5,
                justification="Good",
            ),
        ]

        response = EvaluationResponse.from_model(mock_model, dim_scores)
        assert len(response.dimension_scores) == 1
        assert response.dimension_scores[0].dimension_name == "Accuracy"

    def test_from_model_none_total_score(self):
        """None total_score should map to None (not 0)."""
        mock_model = Mock()
        mock_model.id = 1
        mock_model.interview_exchange_id = 10
        mock_model.rubric_id = None
        mock_model.evaluator_type = "ai"
        mock_model.total_score = None
        mock_model.explanation = None
        mock_model.is_final = False
        mock_model.evaluated_at = None
        mock_model.evaluated_by = None
        mock_model.model_id = None
        mock_model.scoring_version = None
        mock_model.created_at = NOW

        response = EvaluationResponse.from_model(mock_model)
        assert response.total_score is None


# ═══════════════════════════════════════════════════════════════════════════
# InterviewResultResponse Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewResultResponse:
    def test_from_model(self):
        """from_model should transform ORM model to response."""
        mock_model = Mock()
        mock_model.id = 5
        mock_model.interview_submission_id = 100
        mock_model.final_score = Decimal("87.50")
        mock_model.normalized_score = Decimal("0.875")
        mock_model.result_status = "pass"
        mock_model.recommendation = "hire"
        mock_model.section_scores = {"tech": 85, "soft": 90}
        mock_model.strengths = "Good analytical skills"
        mock_model.weaknesses = "Could improve time management"
        mock_model.summary_notes = "Solid candidate"
        mock_model.generated_by = "ai"
        mock_model.model_id = 3
        mock_model.scoring_version = "v1.0"
        mock_model.is_current = True
        mock_model.computed_at = NOW
        mock_model.created_at = NOW

        response = InterviewResultResponse.from_model(mock_model)

        assert response.result_id == 5
        assert response.interview_submission_id == 100
        assert response.final_score == 87.50
        assert response.recommendation == "hire"
        assert response.is_current is True


# ═══════════════════════════════════════════════════════════════════════════
# SupplementaryReportResponse Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSupplementaryReportResponse:
    def test_from_model(self):
        """from_model should transform ORM model to response."""
        mock_model = Mock()
        mock_model.id = 7
        mock_model.report_type = "technical_breakdown"
        mock_model.content = {"sections": []}
        mock_model.generated_by = "ai"
        mock_model.model_id = 3
        mock_model.created_at = NOW

        response = SupplementaryReportResponse.from_model(mock_model)

        assert response.report_id == 7
        assert response.report_type == "technical_breakdown"
        assert response.content == {"sections": []}


# ═══════════════════════════════════════════════════════════════════════════
# Composite Response Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCompositeResponses:
    def test_exchange_evaluations_response(self):
        """ExchangeEvaluationsResponse should accept a list."""
        resp = ExchangeEvaluationsResponse(
            exchange_id=10,
            evaluations=[],
            current_evaluation_id=None,
        )
        assert resp.exchange_id == 10
        assert resp.evaluations == []

    def test_submission_results_response(self):
        """SubmissionResultsResponse should accept a list."""
        resp = SubmissionResultsResponse(
            interview_submission_id=100,
            results=[],
            current_result_id=None,
        )
        assert resp.interview_submission_id == 100

    def test_submission_reports_response(self):
        """SubmissionReportsResponse should accept a list."""
        resp = SubmissionReportsResponse(
            interview_submission_id=100,
            reports=[],
        )
        assert resp.interview_submission_id == 100
        assert resp.reports == []
