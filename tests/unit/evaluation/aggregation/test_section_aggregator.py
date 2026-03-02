"""
Unit Tests — Section Aggregator

Tests grouping evaluations by template section and computing section scores.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.evaluation.aggregation.schemas import (
    EvaluationSummaryDTO,
    ExchangeSummaryDTO,
    SectionScore,
)
from app.evaluation.aggregation.section_aggregator import SectionAggregator


@pytest.fixture
def aggregator():
    return SectionAggregator()


# ── Helpers ────────────────────────────────────────────────────────────


def _exchange(eid: int, seq: int, section: str) -> ExchangeSummaryDTO:
    return ExchangeSummaryDTO(exchange_id=eid, sequence_order=seq, section_name=section)


def _evaluation(eid: int, exchange_id: int, score: str) -> EvaluationSummaryDTO:
    return EvaluationSummaryDTO(
        evaluation_id=eid,
        interview_exchange_id=exchange_id,
        total_score=Decimal(score),
        evaluator_type="ai",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Basic Aggregation Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSectionAggregator:
    def test_single_section(self, aggregator):
        exchanges = [_exchange(1, 1, "coding"), _exchange(2, 2, "coding")]
        evaluations = [_evaluation(10, 1, "80"), _evaluation(11, 2, "90")]
        weights = {"coding": 60}

        result = aggregator.aggregate(exchanges, evaluations, weights)

        assert len(result) == 1
        assert result[0].section_name == "coding"
        assert result[0].score == Decimal("170")
        assert result[0].weight == 60
        assert result[0].exchanges_evaluated == 2

    def test_multiple_sections(self, aggregator):
        exchanges = [
            _exchange(1, 1, "resume"),
            _exchange(2, 2, "behavioral"),
            _exchange(3, 3, "behavioral"),
            _exchange(4, 4, "coding"),
            _exchange(5, 5, "coding"),
            _exchange(6, 6, "coding"),
        ]
        evaluations = [
            _evaluation(10, 1, "85"),
            _evaluation(11, 2, "70"),
            _evaluation(12, 3, "75"),
            _evaluation(13, 4, "90"),
            _evaluation(14, 5, "85"),
            _evaluation(15, 6, "88"),
        ]
        weights = {"resume": 10, "behavioral": 30, "coding": 60}

        result = aggregator.aggregate(exchanges, evaluations, weights)

        by_name = {s.section_name: s for s in result}
        assert by_name["resume"].score == Decimal("85")
        assert by_name["resume"].exchanges_evaluated == 1
        assert by_name["behavioral"].score == Decimal("145")  # 70 + 75
        assert by_name["behavioral"].exchanges_evaluated == 2
        assert by_name["coding"].score == Decimal("263")  # 90 + 85 + 88
        assert by_name["coding"].exchanges_evaluated == 3

    def test_section_with_zero_exchanges(self, aggregator):
        """Section in template but no exchanges → score=0, count=0."""
        exchanges = [_exchange(1, 1, "coding")]
        evaluations = [_evaluation(10, 1, "90")]
        weights = {"coding": 60, "system_design": 20}

        result = aggregator.aggregate(exchanges, evaluations, weights)
        by_name = {s.section_name: s for s in result}

        assert by_name["system_design"].score == Decimal("0")
        assert by_name["system_design"].exchanges_evaluated == 0
        assert by_name["system_design"].weight == 20

    def test_exchange_section_not_in_weights_excluded(self, aggregator):
        """Exchange in unmapped section is excluded from results."""
        exchanges = [
            _exchange(1, 1, "coding"),
            _exchange(2, 2, "bonus_round"),  # not in weights
        ]
        evaluations = [
            _evaluation(10, 1, "90"),
            _evaluation(11, 2, "100"),
        ]
        weights = {"coding": 60}

        result = aggregator.aggregate(exchanges, evaluations, weights)

        assert len(result) == 1
        assert result[0].section_name == "coding"
        assert result[0].score == Decimal("90")

    def test_empty_exchanges(self, aggregator):
        """No exchanges → all sections get 0."""
        weights = {"coding": 60, "behavioral": 40}

        result = aggregator.aggregate([], [], weights)

        assert len(result) == 2
        for s in result:
            assert s.score == Decimal("0")
            assert s.exchanges_evaluated == 0

    def test_preserves_template_weight_order(self, aggregator):
        """Result should include one entry per template weight section."""
        exchanges = [_exchange(1, 1, "coding")]
        evaluations = [_evaluation(10, 1, "50")]
        weights = {"resume": 10, "behavioral": 30, "coding": 60}

        result = aggregator.aggregate(exchanges, evaluations, weights)

        section_names = [s.section_name for s in result]
        assert "resume" in section_names
        assert "behavioral" in section_names
        assert "coding" in section_names
