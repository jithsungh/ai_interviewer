"""
Unit Tests — Aggregation Schemas (DTOs)

Tests Pydantic validation, immutability, and edge cases for aggregation contracts.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.evaluation.aggregation.schemas import (
    EvaluationSummaryDTO,
    ExchangeSummaryDTO,
    InterviewResultData,
    ProctoringRiskDTO,
    SectionScore,
    SummaryData,
    SummaryResponseSchema,
)


# ═══════════════════════════════════════════════════════════════════════════
# SectionScore Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionScore:
    def test_valid_section_score(self):
        score = SectionScore(
            section_name="coding",
            score=Decimal("85.50"),
            weight=60,
            exchanges_evaluated=3,
        )
        assert score.section_name == "coding"
        assert score.score == Decimal("85.50")
        assert score.weight == 60
        assert score.exchanges_evaluated == 3

    def test_frozen(self):
        score = SectionScore(
            section_name="resume",
            score=Decimal("10"),
            weight=10,
            exchanges_evaluated=1,
        )
        with pytest.raises(Exception):
            score.score = Decimal("20")

    def test_zero_exchanges(self):
        score = SectionScore(
            section_name="system_design",
            score=Decimal("0"),
            weight=20,
            exchanges_evaluated=0,
        )
        assert score.score == Decimal("0")
        assert score.exchanges_evaluated == 0

    def test_empty_section_name_rejected(self):
        with pytest.raises(Exception):
            SectionScore(
                section_name="",
                score=Decimal("10"),
                weight=5,
                exchanges_evaluated=1,
            )

    def test_negative_score_rejected(self):
        with pytest.raises(Exception):
            SectionScore(
                section_name="coding",
                score=Decimal("-1"),
                weight=10,
                exchanges_evaluated=1,
            )


# ═══════════════════════════════════════════════════════════════════════════
# SummaryData Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryData:
    def test_defaults(self):
        summary = SummaryData()
        assert summary.strengths == []
        assert summary.weaknesses == []
        assert summary.summary_notes == ""

    def test_with_content(self):
        summary = SummaryData(
            strengths=["Good problem solving", "Clear communication"],
            weaknesses=["Slow coding speed"],
            summary_notes="Candidate performed well overall.",
        )
        assert len(summary.strengths) == 2
        assert len(summary.weaknesses) == 1

    def test_frozen(self):
        summary = SummaryData(strengths=["A"])
        with pytest.raises(Exception):
            summary.strengths = []


# ═══════════════════════════════════════════════════════════════════════════
# SummaryResponseSchema Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSummaryResponseSchema:
    def test_to_summary_data(self):
        schema = SummaryResponseSchema(
            strengths=["Fast learner"],
            weaknesses=["Needs practice"],
            summary_notes="Good candidate.",
        )
        data = schema.to_summary_data()
        assert isinstance(data, SummaryData)
        assert data.strengths == ["Fast learner"]

    def test_get_json_schema(self):
        schema = SummaryResponseSchema.get_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema


# ═══════════════════════════════════════════════════════════════════════════
# EvaluationSummaryDTO Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestEvaluationSummaryDTO:
    def test_valid(self):
        dto = EvaluationSummaryDTO(
            evaluation_id=1,
            interview_exchange_id=10,
            total_score=Decimal("85.00"),
            evaluator_type="ai",
        )
        assert dto.evaluation_id == 1
        assert dto.total_score == Decimal("85.00")

    def test_frozen(self):
        dto = EvaluationSummaryDTO(
            evaluation_id=1,
            interview_exchange_id=10,
            total_score=Decimal("85"),
            evaluator_type="ai",
        )
        with pytest.raises(Exception):
            dto.total_score = Decimal("90")


# ═══════════════════════════════════════════════════════════════════════════
# ExchangeSummaryDTO Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestExchangeSummaryDTO:
    def test_valid(self):
        dto = ExchangeSummaryDTO(
            exchange_id=5,
            sequence_order=1,
            section_name="behavioral",
        )
        assert dto.section_name == "behavioral"

    def test_empty_section_name_rejected(self):
        with pytest.raises(Exception):
            ExchangeSummaryDTO(
                exchange_id=5,
                sequence_order=1,
                section_name="",
            )


# ═══════════════════════════════════════════════════════════════════════════
# InterviewResultData Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestInterviewResultData:
    def test_valid_result(self):
        result = InterviewResultData(
            interview_submission_id=1,
            final_score=Decimal("8110.00"),
            normalized_score=Decimal("83.72"),
            result_status="completed",
            recommendation="hire",
            section_scores=[
                SectionScore(section_name="coding", score=Decimal("263"), weight=60, exchanges_evaluated=3),
            ],
            strengths=["Good"],
            weaknesses=["Slow"],
            summary_notes="Decent candidate.",
            rubric_snapshot={"rubric_id": 1},
            template_weight_snapshot={"coding": {"weight": 60}},
            scoring_version="1.0.0",
            generated_by="ai",
        )
        assert result.recommendation == "hire"
        assert result.normalized_score == Decimal("83.72")

    def test_invalid_recommendation_rejected(self):
        with pytest.raises(Exception):
            InterviewResultData(
                interview_submission_id=1,
                final_score=Decimal("100"),
                normalized_score=Decimal("80"),
                result_status="completed",
                recommendation="super_hire",  # invalid
                section_scores=[],
                rubric_snapshot={},
                template_weight_snapshot={},
                scoring_version="1.0.0",
                generated_by="ai",
            )

    def test_valid_recommendations(self):
        for rec in ("strong_hire", "hire", "review", "no_hire"):
            result = InterviewResultData(
                interview_submission_id=1,
                final_score=Decimal("0"),
                normalized_score=Decimal("0"),
                result_status="completed",
                recommendation=rec,
                section_scores=[],
                rubric_snapshot={},
                template_weight_snapshot={},
                scoring_version="1.0.0",
                generated_by="ai",
            )
            assert result.recommendation == rec


# ═══════════════════════════════════════════════════════════════════════════
# ProctoringRiskDTO Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestProctoringRiskDTO:
    def test_valid(self):
        dto = ProctoringRiskDTO(
            overall_risk="high",
            total_events=5,
            high_severity_count=3,
            flagged_behaviors=["Tab switch", "Background noise"],
        )
        assert dto.overall_risk == "high"
        assert dto.total_events == 5
        assert len(dto.flagged_behaviors) == 2

    def test_defaults(self):
        dto = ProctoringRiskDTO(overall_risk="low")
        assert dto.total_events == 0
        assert dto.high_severity_count == 0
        assert dto.flagged_behaviors == []
