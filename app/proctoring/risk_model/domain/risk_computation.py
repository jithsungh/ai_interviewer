"""
Risk Score Computation — Pure Domain Logic

Deterministic, reproducible risk scoring with transparent computation.
No database calls, no FastAPI imports, no I/O.

Algorithms:
- Simple sum (default): total_risk = Σ(event.applied_weight)
- Sum with time decay: total_risk = Σ(event.applied_weight × decay_factor)
- Risk cap: capped_risk = min(total_risk, max_cap)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ════════════════════════════════════════════════════════════════════════
# Configuration
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RiskThresholds:
    """Risk classification thresholds (configurable)."""

    low_to_moderate: float = 5.0
    moderate_to_high: float = 15.0
    high_to_critical: float = 30.0
    max_cap: float = 100.0

    def classify(self, risk_score: float) -> str:
        """Classify a risk score into a category."""
        if risk_score < self.low_to_moderate:
            return "low"
        elif risk_score < self.moderate_to_high:
            return "moderate"
        elif risk_score < self.high_to_critical:
            return "high"
        else:
            return "critical"


# Default thresholds (from REQUIREMENTS.md)
DEFAULT_THRESHOLDS = RiskThresholds()

# Action recommendations per classification
CLASSIFICATION_ACTIONS: dict[str, str] = {
    "low": "No action required",
    "moderate": "Informational flag - no review required",
    "high": "Admin review required before decision",
    "critical": "Urgent admin review required",
}


# ════════════════════════════════════════════════════════════════════════
# Event data container (input to risk computation)
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class EventData:
    """Minimal event data needed for risk computation."""

    event_id: int
    event_type: str
    risk_weight: float
    severity: str
    occurred_at: datetime


# ════════════════════════════════════════════════════════════════════════
# Risk score result
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class RiskScore:
    """Complete result of risk score computation."""

    submission_id: int
    total_risk: float
    classification: str  # low, moderate, high, critical
    recommended_action: str
    event_count: int
    breakdown_by_type: dict  # {event_type: {count, total_weight}}
    top_events: list[dict]  # [{event_id, event_type, weight, timestamp}]
    severity_counts: dict  # {severity: count}
    computation_algorithm: str
    computed_at: datetime


# ════════════════════════════════════════════════════════════════════════
# Risk computation functions (pure, deterministic)
# ════════════════════════════════════════════════════════════════════════


def compute_risk_score(
    submission_id: int,
    events: list[EventData],
    thresholds: Optional[RiskThresholds] = None,
    enable_time_decay: bool = False,
    decay_half_life_minutes: float = 30.0,
    reference_time: Optional[datetime] = None,
    max_top_events: int = 5,
) -> RiskScore:
    """
    Compute the aggregated risk score for a submission.

    This is a pure function: same inputs always produce same outputs.

    Args:
        submission_id: Interview submission ID.
        events: List of EventData from repository.
        thresholds: Risk classification thresholds. Defaults to standard thresholds.
        enable_time_decay: Whether to apply exponential time decay.
        decay_half_life_minutes: Half-life for time decay (minutes).
        reference_time: Reference time for decay calculation. Defaults to now (UTC).
        max_top_events: Number of top contributing events to include.

    Returns:
        RiskScore with total risk, classification, breakdown, and top events.
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    now = reference_time or datetime.now(timezone.utc)

    if not events:
        return RiskScore(
            submission_id=submission_id,
            total_risk=0.0,
            classification="low",
            recommended_action=CLASSIFICATION_ACTIONS["low"],
            event_count=0,
            breakdown_by_type={},
            top_events=[],
            severity_counts={},
            computation_algorithm="sum",
            computed_at=now,
        )

    # Compute per-event effective weights
    effective_weights: list[tuple[EventData, float]] = []

    if enable_time_decay:
        algorithm = "sum_with_time_decay"
        for evt in events:
            age_minutes = _event_age_minutes(evt.occurred_at, now)
            decay_factor = 0.5 ** (age_minutes / decay_half_life_minutes) if decay_half_life_minutes > 0 else 1.0
            effective_weight = evt.risk_weight * decay_factor
            effective_weights.append((evt, effective_weight))
    else:
        algorithm = "sum"
        for evt in events:
            effective_weights.append((evt, evt.risk_weight))

    # Sum and cap
    total_risk = sum(w for _, w in effective_weights)
    total_risk = min(total_risk, thresholds.max_cap)

    # Classify
    classification = thresholds.classify(total_risk)
    recommended_action = CLASSIFICATION_ACTIONS.get(classification, "Unknown")

    # Breakdown by type
    breakdown: dict[str, dict] = {}
    for evt, ew in effective_weights:
        if evt.event_type not in breakdown:
            breakdown[evt.event_type] = {"count": 0, "total_weight": 0.0}
        breakdown[evt.event_type]["count"] += 1
        breakdown[evt.event_type]["total_weight"] += ew
    # Round total_weight for readability
    for key in breakdown:
        breakdown[key]["total_weight"] = round(breakdown[key]["total_weight"], 4)

    # Top events (highest effective weight)
    sorted_events = sorted(effective_weights, key=lambda x: x[1], reverse=True)
    top_events = [
        {
            "event_id": evt.event_id,
            "event_type": evt.event_type,
            "weight": round(ew, 4),
            "timestamp": evt.occurred_at.isoformat(),
        }
        for evt, ew in sorted_events[:max_top_events]
    ]

    # Severity counts
    severity_counts: dict[str, int] = {}
    for evt, _ in effective_weights:
        severity_counts[evt.severity] = severity_counts.get(evt.severity, 0) + 1

    return RiskScore(
        submission_id=submission_id,
        total_risk=round(total_risk, 4),
        classification=classification,
        recommended_action=recommended_action,
        event_count=len(events),
        breakdown_by_type=breakdown,
        top_events=top_events,
        severity_counts=severity_counts,
        computation_algorithm=algorithm,
        computed_at=now,
    )


def _event_age_minutes(occurred_at: datetime, reference: datetime) -> float:
    """Calculate event age in minutes. Handles timezone-naive datetimes."""
    # Make both timezone-aware if one is naive
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    delta = (reference - occurred_at).total_seconds() / 60.0
    return max(delta, 0.0)  # Clamp negative (future events) to 0


def is_flaggable(classification: str) -> bool:
    """Check if a risk classification should trigger admin review flagging."""
    return classification in ("high", "critical")
