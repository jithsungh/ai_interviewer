"""
Unit Tests — Score Normalizer

Tests normalization to 0–100 scale and final score calculation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.evaluation.aggregation.config import AggregationConfig
from app.evaluation.aggregation.normalizer import ScoreNormalizer, calculate_final_score
from app.evaluation.aggregation.schemas import SectionScore


@pytest.fixture
def config():
    return AggregationConfig(
        max_exchange_score=100.0,
        score_decimal_places=2,
    )


@pytest.fixture
def normalizer(config):
    return ScoreNormalizer(config=config)


# ── Helpers ────────────────────────────────────────────────────────────


def _section(name: str, score: str, weight: int, count: int) -> SectionScore:
    return SectionScore(
        section_name=name,
        score=Decimal(score),
        weight=weight,
        exchanges_evaluated=count,
    )


# ═══════════════════════════════════════════════════════════════════════════
# calculate_final_score Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestCalculateFinalScore:
    def test_basic_weighted_sum(self):
        sections = [
            _section("resume", "85", 10, 1),
            _section("behavioral", "145", 30, 2),
            _section("coding", "263", 60, 3),
        ]
        result = calculate_final_score(sections)

        # 85*10 + 145*30 + 263*60 = 850 + 4350 + 15780 = 20980
        assert result == Decimal("20980.00")

    def test_single_section(self):
        sections = [_section("coding", "90", 1, 1)]
        result = calculate_final_score(sections)
        assert result == Decimal("90.00")

    def test_zero_weight(self):
        sections = [_section("experimental", "100", 0, 1)]
        result = calculate_final_score(sections)
        assert result == Decimal("0.00")

    def test_empty_sections(self):
        result = calculate_final_score([])
        assert result == Decimal("0.00")

    def test_custom_decimal_places(self):
        sections = [_section("coding", "33.333", 1, 1)]
        result = calculate_final_score(sections, decimal_places=4)
        assert result == Decimal("33.3330")


# ═══════════════════════════════════════════════════════════════════════════
# ScoreNormalizer Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestScoreNormalizer:
    def test_perfect_score(self, normalizer):
        """All sections at max → normalized = 100."""
        sections = [
            _section("resume", "100", 10, 1),
            _section("coding", "300", 60, 3),
        ]
        # final = 100*10 + 300*60 = 1000 + 18000 = 19000
        # max   = (100*1)*10 + (100*3)*60 = 1000 + 18000 = 19000
        final = Decimal("19000")
        result = normalizer.normalize(final, sections)
        assert result == Decimal("100.00")

    def test_half_score(self, normalizer):
        """Half of max → normalized = 50."""
        sections = [_section("coding", "150", 1, 3)]
        # final = 150
        # max = 100*3*1 = 300
        # norm = 150/300 * 100 = 50
        result = normalizer.normalize(Decimal("150"), sections)
        assert result == Decimal("50.00")

    def test_realistic_scenario(self, normalizer):
        """Realistic multi-section scenario."""
        sections = [
            _section("resume", "85", 10, 1),
            _section("behavioral", "145", 30, 2),
            _section("coding", "263", 60, 3),
        ]
        final = Decimal("20980.00")
        # max = (100*1)*10 + (100*2)*30 + (100*3)*60
        #     = 1000 + 6000 + 18000 = 25000
        # norm = 20980/25000 * 100 = 83.92
        result = normalizer.normalize(final, sections)
        assert result == Decimal("83.92")

    def test_zero_max_possible(self, normalizer):
        """max_possible = 0 → normalized = 0."""
        sections = [_section("empty", "0", 0, 0)]
        result = normalizer.normalize(Decimal("0"), sections)
        assert result == Decimal("0.00")

    def test_exceeds_max_clamped(self, normalizer):
        """Score exceeding max → clamped to 100."""
        sections = [_section("coding", "200", 1, 1)]
        # max = 100*1*1 = 100
        # final > max → clamp
        result = normalizer.normalize(Decimal("200"), sections)
        assert result == Decimal("100.00")

    def test_negative_final_clamped(self, normalizer):
        """Negative final → clamped to 0."""
        sections = [_section("coding", "50", 1, 1)]
        result = normalizer.normalize(Decimal("-10"), sections)
        assert result == Decimal("0.00")

    def test_precision(self, normalizer):
        """Result should have exactly configured decimal places."""
        sections = [_section("coding", "33", 1, 1)]
        # max = 100, norm = 33/100*100 = 33
        result = normalizer.normalize(Decimal("33"), sections)
        assert str(result) == "33.00"

    def test_border_case_floating_point(self, normalizer):
        """Using Decimal prevents floating-point errors at thresholds."""
        sections = [_section("coding", "70", 1, 1)]
        # max = 100, norm = 70/100*100 = 70.00
        result = normalizer.normalize(Decimal("70"), sections)
        assert result == Decimal("70.00")
        # Ensure exact equality, not 69.999... or 70.0001...
        assert float(result) == 70.0
