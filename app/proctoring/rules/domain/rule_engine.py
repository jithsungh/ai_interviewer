"""
Proctoring Rule Engine — Severity & Weight Assignment

Pure domain logic: maps event types to severity/weight, detects clustering.
No database calls — receives event counts from caller.
No FastAPI imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.proctoring.rules.domain.rule_definitions import (
    ALLOWED_EVENT_TYPES,
    DEFAULT_CLUSTERING_MAP,
    DEFAULT_RULE_MAP,
    SEVERITY_ORDER,
    VALID_SEVERITIES,
    ClusteringRule,
    ProctoringRule,
)


@dataclass(frozen=True)
class EnrichedEvent:
    """
    Result of rule application to a raw proctoring event.

    Contains both the original event data and the rule-derived severity/weight.
    """

    submission_id: int
    event_type: str
    occurred_at: datetime
    evidence: dict
    base_severity: str
    base_weight: float
    applied_severity: str  # May be escalated by clustering
    applied_weight: float  # May be multiplied by clustering
    clustering_detected: bool
    clustering_reason: Optional[str]
    rule_version: str


class RuleEngine:
    """
    Deterministic, stateless rule engine.

    Applies severity and weight rules to proctoring events.
    Clustering detection requires caller to supply recent event counts.
    """

    def __init__(
        self,
        rule_map: Optional[dict[str, ProctoringRule]] = None,
        clustering_map: Optional[dict[str, list[ClusteringRule]]] = None,
    ) -> None:
        self._rule_map = rule_map or DEFAULT_RULE_MAP
        self._clustering_map = clustering_map or DEFAULT_CLUSTERING_MAP

    def is_valid_event_type(self, event_type: str) -> bool:
        """Check if an event type is recognized."""
        return event_type in ALLOWED_EVENT_TYPES

    def get_base_rule(self, event_type: str) -> Optional[ProctoringRule]:
        """Get the base rule for an event type, or None if unknown."""
        return self._rule_map.get(event_type)

    def apply_rules(
        self,
        submission_id: int,
        event_type: str,
        occurred_at: datetime,
        evidence: dict,
        recent_count_in_window: int = 0,
        consecutive_count: int = 0,
    ) -> EnrichedEvent:
        """
        Apply severity and weight rules to a raw event.

        Args:
            submission_id: The interview submission ID.
            event_type: The proctoring event type string.
            occurred_at: When the event occurred.
            evidence: JSONB evidence metadata.
            recent_count_in_window: Number of same-type events in clustering window
                                    (caller must query this from repository).
            consecutive_count: Number of consecutive same-type events
                               (caller must query this from repository).

        Returns:
            EnrichedEvent with base and applied severity/weight.

        Raises:
            ValueError: If event_type is not in ALLOWED_EVENT_TYPES.
        """
        if event_type not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"Unknown event type: {event_type!r}")

        rule = self._rule_map.get(event_type)
        if rule is None:
            # Event type is allowed but has no rule → default to low/0.0
            base_severity = "low"
            base_weight = 0.0
            rule_version = "v1.0.0"
        else:
            base_severity = rule.base_severity
            base_weight = rule.base_weight
            rule_version = rule.rule_version

        # Ensure severity is a valid DB enum value
        if base_severity not in VALID_SEVERITIES:
            base_severity = "low"

        applied_severity = base_severity
        applied_weight = base_weight
        clustering_detected = False
        clustering_reason: Optional[str] = None

        # Check clustering rules
        clustering_rules = self._clustering_map.get(event_type, [])
        for cr in clustering_rules:
            triggered = False
            if cr.condition_type == "count_in_window" and recent_count_in_window >= cr.threshold:
                triggered = True
                clustering_reason = (
                    f"{recent_count_in_window} {event_type} events in "
                    f"{cr.time_window_seconds}s window (threshold: {cr.threshold})"
                )
            elif cr.condition_type == "consecutive" and consecutive_count >= cr.threshold:
                triggered = True
                clustering_reason = (
                    f"{consecutive_count} consecutive {event_type} events "
                    f"(threshold: {cr.threshold})"
                )

            if triggered:
                clustering_detected = True
                # Escalate severity if clustering severity is higher
                if SEVERITY_ORDER.get(cr.escalated_severity, 0) > SEVERITY_ORDER.get(applied_severity, 0):
                    applied_severity = cr.escalated_severity
                # Apply weight multiplier
                applied_weight = base_weight * cr.weight_multiplier
                break  # First matching clustering rule wins

        return EnrichedEvent(
            submission_id=submission_id,
            event_type=event_type,
            occurred_at=occurred_at,
            evidence=evidence,
            base_severity=base_severity,
            base_weight=base_weight,
            applied_severity=applied_severity,
            applied_weight=applied_weight,
            clustering_detected=clustering_detected,
            clustering_reason=clustering_reason,
            rule_version=rule_version,
        )
