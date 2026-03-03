"""
Unit Tests — Proctoring Rule Definitions & Rule Engine

Tests pure domain logic: event type validation, severity mapping,
weight assignment, and clustering detection.
No mocks needed — pure functions with deterministic output.
"""

import os
import pytest
from datetime import datetime, timezone

os.environ["TESTING"] = "1"

from app.proctoring.rules.domain.rule_definitions import (
    ALLOWED_EVENT_TYPES,
    DEFAULT_CLUSTERING_MAP,
    DEFAULT_CLUSTERING_RULES,
    DEFAULT_RULE_MAP,
    DEFAULT_RULES,
    SEVERITY_ORDER,
    VALID_SEVERITIES,
    ClusteringRule,
    ProctoringRule,
)
from app.proctoring.rules.domain.rule_engine import EnrichedEvent, RuleEngine


# ════════════════════════════════════════════════════════════════════════
# Rule Definitions Tests
# ════════════════════════════════════════════════════════════════════════


class TestRuleDefinitions:
    """Test the static rule definitions."""

    def test_all_allowed_event_types_have_rules(self):
        """Every allowed event type must have a corresponding base rule."""
        for event_type in ALLOWED_EVENT_TYPES:
            assert event_type in DEFAULT_RULE_MAP, (
                f"Missing rule for allowed event type: {event_type}"
            )

    def test_all_rules_use_valid_event_types(self):
        """Every rule must reference an allowed event type."""
        for rule in DEFAULT_RULES:
            assert rule.event_type in ALLOWED_EVENT_TYPES, (
                f"Rule references unknown event type: {rule.event_type}"
            )

    def test_all_rules_use_valid_severities(self):
        """Base severities must be valid DB enum values."""
        for rule in DEFAULT_RULES:
            assert rule.base_severity in VALID_SEVERITIES, (
                f"Rule {rule.event_type} uses invalid severity: {rule.base_severity}"
            )

    def test_all_rules_have_non_negative_weights(self):
        """Weights must be >= 0."""
        for rule in DEFAULT_RULES:
            assert rule.base_weight >= 0.0, (
                f"Rule {rule.event_type} has negative weight: {rule.base_weight}"
            )

    def test_clustering_rules_reference_valid_event_types(self):
        """Clustering rules must reference allowed event types."""
        for cr in DEFAULT_CLUSTERING_RULES:
            assert cr.event_type in ALLOWED_EVENT_TYPES, (
                f"Clustering rule references unknown event type: {cr.event_type}"
            )

    def test_clustering_rules_have_valid_escalated_severity(self):
        """Clustering escalated severity must be a valid DB enum value."""
        for cr in DEFAULT_CLUSTERING_RULES:
            assert cr.escalated_severity in VALID_SEVERITIES

    def test_clustering_rules_have_positive_thresholds(self):
        """Clustering thresholds must be positive."""
        for cr in DEFAULT_CLUSTERING_RULES:
            assert cr.threshold > 0
            assert cr.time_window_seconds > 0
            assert cr.weight_multiplier > 0

    def test_severity_order_covers_all_valid_severities(self):
        """Severity order map must include all valid severities."""
        for sev in VALID_SEVERITIES:
            assert sev in SEVERITY_ORDER

    def test_severity_order_is_ascending(self):
        """Severity ordering: low < medium < high < critical."""
        assert SEVERITY_ORDER["low"] < SEVERITY_ORDER["medium"]
        assert SEVERITY_ORDER["medium"] < SEVERITY_ORDER["high"]
        assert SEVERITY_ORDER["high"] < SEVERITY_ORDER["critical"]

    def test_rule_is_frozen(self):
        """ProctoringRule is frozen (immutable)."""
        rule = DEFAULT_RULES[0]
        with pytest.raises(AttributeError):
            rule.base_weight = 999.0  # type: ignore

    def test_clustering_rule_is_frozen(self):
        """ClusteringRule is frozen (immutable)."""
        cr = DEFAULT_CLUSTERING_RULES[0]
        with pytest.raises(AttributeError):
            cr.threshold = 999  # type: ignore


# ════════════════════════════════════════════════════════════════════════
# Specific Event Type Rules
# ════════════════════════════════════════════════════════════════════════


class TestSpecificEventRules:
    """Validate specific event type → severity/weight mappings from REQUIREMENTS."""

    @pytest.mark.parametrize(
        "event_type,expected_severity,expected_weight",
        [
            ("tab_switch", "low", 0.5),
            ("window_blur", "low", 0.5),
            ("window_focus_lost", "low", 0.5),
            ("microphone_disabled", "low", 1.0),
            ("device_change", "low", 1.0),
            ("face_absent", "medium", 1.5),
            ("camera_disabled", "medium", 2.0),
            ("background_noise_spike", "medium", 1.5),
            ("multiple_faces", "high", 3.0),
            ("multiple_voices", "high", 3.0),
            ("screen_recording_started", "low", 0.0),
            ("screen_recording_stopped", "low", 0.0),
        ],
    )
    def test_event_severity_and_weight(self, event_type, expected_severity, expected_weight):
        """Verify REQUIREMENTS-specified severity and weight per event type."""
        rule = DEFAULT_RULE_MAP[event_type]
        assert rule.base_severity == expected_severity
        assert rule.base_weight == expected_weight


# ════════════════════════════════════════════════════════════════════════
# Rule Engine Tests
# ════════════════════════════════════════════════════════════════════════


class TestRuleEngine:
    """Test the RuleEngine (pure domain, stateless)."""

    def setup_method(self):
        self.engine = RuleEngine()
        self.now = datetime(2026, 2, 14, 10, 30, 0, tzinfo=timezone.utc)

    def test_is_valid_event_type_true(self):
        assert self.engine.is_valid_event_type("tab_switch") is True

    def test_is_valid_event_type_false(self):
        assert self.engine.is_valid_event_type("unknown_event") is False

    def test_get_base_rule_exists(self):
        rule = self.engine.get_base_rule("tab_switch")
        assert rule is not None
        assert rule.base_severity == "low"
        assert rule.base_weight == 0.5

    def test_get_base_rule_none_for_unknown(self):
        rule = self.engine.get_base_rule("nonexistent")
        assert rule is None

    def test_apply_rules_basic_tab_switch(self):
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="tab_switch",
            occurred_at=self.now,
            evidence={},
        )
        assert isinstance(result, EnrichedEvent)
        assert result.base_severity == "low"
        assert result.base_weight == 0.5
        assert result.applied_severity == "low"
        assert result.applied_weight == 0.5
        assert result.clustering_detected is False
        assert result.clustering_reason is None
        assert result.rule_version == "v1.0.0"

    def test_apply_rules_high_severity_event(self):
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="multiple_faces",
            occurred_at=self.now,
            evidence={"faces_detected": 2},
        )
        assert result.base_severity == "high"
        assert result.base_weight == 3.0
        assert result.applied_severity == "high"
        assert result.applied_weight == 3.0

    def test_apply_rules_unknown_event_type_raises(self):
        with pytest.raises(ValueError, match="Unknown event type"):
            self.engine.apply_rules(
                submission_id=1,
                event_type="unknown_event",
                occurred_at=self.now,
                evidence={},
            )

    def test_apply_rules_zero_weight_event(self):
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="screen_recording_started",
            occurred_at=self.now,
            evidence={},
        )
        assert result.applied_weight == 0.0
        assert result.applied_severity == "low"

    # ───── Clustering tests ─────

    def test_clustering_tab_switch_triggered(self):
        """10+ tab switches in window → escalate from low to medium, 1.5x weight."""
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="tab_switch",
            occurred_at=self.now,
            evidence={},
            recent_count_in_window=10,
        )
        assert result.clustering_detected is True
        assert result.applied_severity == "medium"
        assert result.applied_weight == 0.5 * 1.5  # 0.75
        assert "tab_switch" in result.clustering_reason

    def test_clustering_tab_switch_not_triggered(self):
        """9 tab switches in window → no clustering."""
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="tab_switch",
            occurred_at=self.now,
            evidence={},
            recent_count_in_window=9,
        )
        assert result.clustering_detected is False
        assert result.applied_severity == "low"
        assert result.applied_weight == 0.5

    def test_clustering_face_absent_consecutive(self):
        """3+ consecutive face_absent → escalate from medium to high, 2x weight."""
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="face_absent",
            occurred_at=self.now,
            evidence={},
            consecutive_count=3,
        )
        assert result.clustering_detected is True
        assert result.applied_severity == "high"
        assert result.applied_weight == 1.5 * 2.0  # 3.0

    def test_clustering_multiple_faces_window(self):
        """5+ multiple_faces in 5 min → escalate from high to critical, 2.5x weight."""
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="multiple_faces",
            occurred_at=self.now,
            evidence={},
            recent_count_in_window=5,
        )
        assert result.clustering_detected is True
        assert result.applied_severity == "critical"
        assert result.applied_weight == 3.0 * 2.5  # 7.5

    def test_enriched_event_is_frozen(self):
        result = self.engine.apply_rules(
            submission_id=1,
            event_type="tab_switch",
            occurred_at=self.now,
            evidence={},
        )
        with pytest.raises(AttributeError):
            result.applied_weight = 999.0  # type: ignore

    def test_apply_rules_preserves_evidence(self):
        evidence = {"tab_title": "[REDACTED]"}
        result = self.engine.apply_rules(
            submission_id=42,
            event_type="tab_switch",
            occurred_at=self.now,
            evidence=evidence,
        )
        assert result.evidence == evidence
        assert result.submission_id == 42
