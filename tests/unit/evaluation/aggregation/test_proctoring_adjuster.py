"""
Unit Tests — Proctoring Adjuster

Tests recommendation adjustment based on proctoring risk.
"""

from __future__ import annotations

import pytest

from app.evaluation.aggregation.config import AggregationConfig
from app.evaluation.aggregation.proctoring_adjuster import ProctoringAdjuster
from app.evaluation.aggregation.schemas import ProctoringRiskDTO


def _adjuster(
    enabled: bool = True,
    high_risk_downgrade: bool = True,
) -> ProctoringAdjuster:
    config = AggregationConfig(
        enable_proctoring_influence=enabled,
        high_risk_downgrade=high_risk_downgrade,
    )
    return ProctoringAdjuster(config=config)


def _risk(level: str = "high", events: int = 5) -> ProctoringRiskDTO:
    return ProctoringRiskDTO(
        overall_risk=level,
        total_events=events,
        high_severity_count=events if level in ("high", "critical") else 0,
        flagged_behaviors=["Tab switch"],
    )


# ═══════════════════════════════════════════════════════════════════════════
# Proctoring Adjuster Tests
# ═══════════════════════════════════════════════════════════════════════════


class TestProctoringAdjuster:
    def test_disabled_no_change(self):
        """When feature disabled, recommendation is never adjusted."""
        adjuster = _adjuster(enabled=False)
        assert adjuster.adjust("strong_hire", _risk("high")) == "strong_hire"

    def test_no_risk_data_no_change(self):
        """No proctoring data → no adjustment."""
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("hire", None) == "hire"

    def test_low_risk_no_change(self):
        """Low risk → no downgrade."""
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("hire", _risk("low")) == "hire"

    def test_medium_risk_no_change(self):
        """Medium risk → no downgrade (only high/critical trigger it)."""
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("hire", _risk("medium")) == "hire"

    def test_high_risk_strong_hire_to_hire(self):
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("strong_hire", _risk("high")) == "hire"

    def test_high_risk_hire_to_review(self):
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("hire", _risk("high")) == "review"

    def test_high_risk_review_to_no_hire(self):
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("review", _risk("high")) == "no_hire"

    def test_high_risk_no_hire_stays_no_hire(self):
        """Cannot downgrade below no_hire."""
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("no_hire", _risk("high")) == "no_hire"

    def test_critical_risk_downgrades(self):
        """Critical risk also triggers downgrade."""
        adjuster = _adjuster(enabled=True)
        assert adjuster.adjust("strong_hire", _risk("critical")) == "hire"

    def test_high_risk_but_downgrade_disabled(self):
        """High risk but high_risk_downgrade=false → no change."""
        adjuster = _adjuster(enabled=True, high_risk_downgrade=False)
        assert adjuster.adjust("hire", _risk("high")) == "hire"
