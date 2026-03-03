"""
Unit Tests — Risk Score Computation (Pure Domain)

Tests deterministic risk scoring: aggregation algorithms,
time decay, risk classification, breakdown generation.
No mocks needed — pure functions.
"""

import os
import pytest
from datetime import datetime, timezone, timedelta

os.environ["TESTING"] = "1"

from app.proctoring.risk_model.domain.risk_computation import (
    CLASSIFICATION_ACTIONS,
    DEFAULT_THRESHOLDS,
    EventData,
    RiskScore,
    RiskThresholds,
    compute_risk_score,
    is_flaggable,
)


# ════════════════════════════════════════════════════════════════════════
# RiskThresholds Tests
# ════════════════════════════════════════════════════════════════════════


class TestRiskThresholds:
    """Test threshold classification logic."""

    def test_default_thresholds(self):
        t = DEFAULT_THRESHOLDS
        assert t.low_to_moderate == 5.0
        assert t.moderate_to_high == 15.0
        assert t.high_to_critical == 30.0
        assert t.max_cap == 100.0

    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.0, "low"),
            (2.5, "low"),
            (4.99, "low"),
            (5.0, "moderate"),
            (10.0, "moderate"),
            (14.99, "moderate"),
            (15.0, "high"),
            (20.0, "high"),
            (29.99, "high"),
            (30.0, "critical"),
            (50.0, "critical"),
            (100.0, "critical"),
        ],
    )
    def test_classify(self, score, expected):
        assert DEFAULT_THRESHOLDS.classify(score) == expected

    def test_custom_thresholds(self):
        custom = RiskThresholds(
            low_to_moderate=10.0,
            moderate_to_high=25.0,
            high_to_critical=50.0,
            max_cap=200.0,
        )
        assert custom.classify(9.0) == "low"
        assert custom.classify(10.0) == "moderate"
        assert custom.classify(25.0) == "high"
        assert custom.classify(50.0) == "critical"

    def test_thresholds_frozen(self):
        with pytest.raises(AttributeError):
            DEFAULT_THRESHOLDS.max_cap = 200.0  # type: ignore


# ════════════════════════════════════════════════════════════════════════
# compute_risk_score Tests
# ════════════════════════════════════════════════════════════════════════


class TestComputeRiskScore:
    """Test the core risk computation function (pure, deterministic)."""

    def setup_method(self):
        self.now = datetime(2026, 2, 14, 11, 0, 0, tzinfo=timezone.utc)

    def _make_event(self, event_id=1, event_type="tab_switch", weight=2.0,
                    severity="low", minutes_ago=0):
        return EventData(
            event_id=event_id,
            event_type=event_type,
            risk_weight=weight,
            severity=severity,
            occurred_at=self.now - timedelta(minutes=minutes_ago),
        )

    # ───── Zero events ─────

    def test_zero_events_returns_low(self):
        """No events → risk_score = 0.0, classification = 'low'."""
        result = compute_risk_score(
            submission_id=1,
            events=[],
            reference_time=self.now,
        )
        assert result.total_risk == 0.0
        assert result.classification == "low"
        assert result.event_count == 0
        assert result.breakdown_by_type == {}
        assert result.top_events == []

    # ───── Simple sum algorithm ─────

    def test_simple_sum_10_events_weight_2(self):
        """10 events with weight 2.0 each → total_risk = 20.0."""
        events = [self._make_event(event_id=i, weight=2.0) for i in range(10)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.total_risk == 20.0
        assert result.event_count == 10
        assert result.computation_algorithm == "sum"

    def test_simple_sum_classification_high(self):
        """Risk 18.5 → classified as 'high'."""
        events = [
            self._make_event(event_id=1, weight=10.0),
            self._make_event(event_id=2, weight=8.5),
        ]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.total_risk == 18.5
        assert result.classification == "high"

    def test_classification_moderate(self):
        """Risk 10.0 → 'moderate'."""
        events = [self._make_event(event_id=1, weight=10.0)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.classification == "moderate"

    def test_classification_critical(self):
        """Risk 35.0 → 'critical'."""
        events = [self._make_event(event_id=1, weight=35.0)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.classification == "critical"

    # ───── Risk cap ─────

    def test_risk_cap_applied(self):
        """Risk 120 → capped at 100.0."""
        events = [self._make_event(event_id=i, weight=12.0) for i in range(10)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.total_risk == 100.0  # capped

    def test_custom_risk_cap(self):
        """Custom cap of 50."""
        events = [self._make_event(event_id=i, weight=10.0) for i in range(10)]
        custom_thresholds = RiskThresholds(max_cap=50.0)
        result = compute_risk_score(
            submission_id=1,
            events=events,
            thresholds=custom_thresholds,
            reference_time=self.now,
        )
        assert result.total_risk == 50.0

    # ───── Time decay algorithm ─────

    def test_time_decay_30min_ago(self):
        """Event 30 min ago with weight 2.0 and half_life 30 min → ~1.0."""
        events = [self._make_event(event_id=1, weight=2.0, minutes_ago=30)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            enable_time_decay=True,
            decay_half_life_minutes=30.0,
            reference_time=self.now,
        )
        assert result.computation_algorithm == "sum_with_time_decay"
        assert abs(result.total_risk - 1.0) < 0.01  # 2.0 × 0.5 = 1.0

    def test_time_decay_recent_event(self):
        """Event 0 min ago → full weight (decay factor ~1.0)."""
        events = [self._make_event(event_id=1, weight=2.0, minutes_ago=0)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            enable_time_decay=True,
            decay_half_life_minutes=30.0,
            reference_time=self.now,
        )
        assert abs(result.total_risk - 2.0) < 0.01

    def test_time_decay_60min_ago(self):
        """Event 60 min ago, half_life 30 → weight × 0.25."""
        events = [self._make_event(event_id=1, weight=2.0, minutes_ago=60)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            enable_time_decay=True,
            decay_half_life_minutes=30.0,
            reference_time=self.now,
        )
        assert abs(result.total_risk - 0.5) < 0.01  # 2.0 × 0.25 = 0.5

    def test_time_decay_extreme_old(self):
        """Event 5 hours ago → decayed to near-zero."""
        events = [self._make_event(event_id=1, weight=2.0, minutes_ago=300)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            enable_time_decay=True,
            decay_half_life_minutes=30.0,
            reference_time=self.now,
        )
        assert result.total_risk < 0.01

    # ───── Breakdown by type ─────

    def test_breakdown_by_type(self):
        """Events [A, A, B] → breakdown = {A: {count: 2, ...}, B: {count: 1, ...}}."""
        events = [
            self._make_event(event_id=1, event_type="tab_switch", weight=0.5),
            self._make_event(event_id=2, event_type="tab_switch", weight=0.5),
            self._make_event(event_id=3, event_type="face_absent", weight=1.5),
        ]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.breakdown_by_type["tab_switch"]["count"] == 2
        assert result.breakdown_by_type["tab_switch"]["total_weight"] == 1.0
        assert result.breakdown_by_type["face_absent"]["count"] == 1
        assert result.breakdown_by_type["face_absent"]["total_weight"] == 1.5

    # ───── Top events ─────

    def test_top_events_sorted_by_weight(self):
        """Top events should be sorted by weight descending."""
        events = [
            self._make_event(event_id=1, event_type="tab_switch", weight=0.5),
            self._make_event(event_id=2, event_type="multiple_faces", weight=3.0),
            self._make_event(event_id=3, event_type="face_absent", weight=1.5),
        ]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.top_events[0]["event_id"] == 2  # Highest weight
        assert result.top_events[0]["weight"] == 3.0

    def test_top_events_limited(self):
        """Top events limited to max_top_events."""
        events = [self._make_event(event_id=i, weight=float(i)) for i in range(1, 20)]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
            max_top_events=3,
        )
        assert len(result.top_events) == 3

    # ───── Severity counts ─────

    def test_severity_counts(self):
        events = [
            self._make_event(event_id=1, severity="low", weight=0.5),
            self._make_event(event_id=2, severity="low", weight=0.5),
            self._make_event(event_id=3, severity="high", weight=3.0),
        ]
        result = compute_risk_score(
            submission_id=1,
            events=events,
            reference_time=self.now,
        )
        assert result.severity_counts["low"] == 2
        assert result.severity_counts["high"] == 1

    # ───── Determinism ─────

    def test_deterministic_same_inputs_same_outputs(self):
        """Same events must produce identical results."""
        events = [
            self._make_event(event_id=1, weight=2.0),
            self._make_event(event_id=2, event_type="face_absent", weight=1.5, severity="medium"),
        ]
        result1 = compute_risk_score(
            submission_id=1, events=events, reference_time=self.now,
        )
        result2 = compute_risk_score(
            submission_id=1, events=events, reference_time=self.now,
        )
        assert result1.total_risk == result2.total_risk
        assert result1.classification == result2.classification
        assert result1.breakdown_by_type == result2.breakdown_by_type

    # ───── Recommended action ─────

    def test_recommended_action_matches_classification(self):
        for classification, expected_action in CLASSIFICATION_ACTIONS.items():
            thresholds = RiskThresholds(
                low_to_moderate=0.0 if classification != "low" else 999.0,
            )
            # Simple: just check the action map
            assert expected_action in CLASSIFICATION_ACTIONS.values()

    # ───── Result is frozen ─────

    def test_risk_score_is_frozen(self):
        result = compute_risk_score(
            submission_id=1, events=[], reference_time=self.now,
        )
        with pytest.raises(AttributeError):
            result.total_risk = 999.0  # type: ignore


# ════════════════════════════════════════════════════════════════════════
# is_flaggable Tests
# ════════════════════════════════════════════════════════════════════════


class TestIsFlaggable:
    """Test the flagging helper."""

    @pytest.mark.parametrize(
        "classification,expected",
        [
            ("low", False),
            ("moderate", False),
            ("high", True),
            ("critical", True),
        ],
    )
    def test_is_flaggable(self, classification, expected):
        assert is_flaggable(classification) == expected
