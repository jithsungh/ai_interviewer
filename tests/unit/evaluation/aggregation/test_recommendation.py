"""
Unit Tests — Recommendation Engine

Tests normalized score → recommendation mapping and threshold boundary behavior.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.evaluation.aggregation.config import AggregationConfig
from app.evaluation.aggregation.recommendation import RecommendationEngine


@pytest.fixture
def default_engine():
    config = AggregationConfig(
        strong_hire_threshold=85.0,
        hire_threshold=70.0,
        review_threshold=50.0,
    )
    return RecommendationEngine(config=config)


# ═══════════════════════════════════════════════════════════════════════════
# Recommendation Mapping Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestRecommendationEngine:
    def test_strong_hire(self, default_engine):
        assert default_engine.determine(Decimal("90.00")) == "strong_hire"
        assert default_engine.determine(Decimal("100.00")) == "strong_hire"

    def test_strong_hire_threshold_inclusive(self, default_engine):
        """Exact threshold → strong_hire."""
        assert default_engine.determine(Decimal("85.00")) == "strong_hire"

    def test_hire(self, default_engine):
        assert default_engine.determine(Decimal("75.00")) == "hire"
        assert default_engine.determine(Decimal("84.99")) == "hire"

    def test_hire_threshold_inclusive(self, default_engine):
        """Exact threshold → hire."""
        assert default_engine.determine(Decimal("70.00")) == "hire"

    def test_review(self, default_engine):
        assert default_engine.determine(Decimal("55.00")) == "review"
        assert default_engine.determine(Decimal("69.99")) == "review"

    def test_review_threshold_inclusive(self, default_engine):
        """Exact threshold → review."""
        assert default_engine.determine(Decimal("50.00")) == "review"

    def test_no_hire(self, default_engine):
        assert default_engine.determine(Decimal("49.99")) == "no_hire"
        assert default_engine.determine(Decimal("0.00")) == "no_hire"
        assert default_engine.determine(Decimal("25.00")) == "no_hire"

    def test_custom_thresholds(self):
        config = AggregationConfig(
            strong_hire_threshold=90.0,
            hire_threshold=75.0,
            review_threshold=60.0,
        )
        engine = RecommendationEngine(config=config)

        assert engine.determine(Decimal("90.00")) == "strong_hire"
        assert engine.determine(Decimal("89.99")) == "hire"
        assert engine.determine(Decimal("75.00")) == "hire"
        assert engine.determine(Decimal("74.99")) == "review"
        assert engine.determine(Decimal("60.00")) == "review"
        assert engine.determine(Decimal("59.99")) == "no_hire"

    def test_zero_score(self, default_engine):
        assert default_engine.determine(Decimal("0")) == "no_hire"
