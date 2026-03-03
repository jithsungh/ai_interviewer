"""
Proctoring Rule Definitions — Default Rules v1.0.0

Pure data: event-to-severity mapping, base weights, and clustering rules.
No I/O, no database calls, no FastAPI imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Optional


# ════════════════════════════════════════════════════════════════════════
# Data classes
# ════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ProctoringRule:
    """Base rule for a single event type."""

    event_type: str
    base_severity: str  # low, medium, high, critical, info
    base_weight: float  # >= 0.0
    description: str
    rule_version: str = "v1.0.0"


@dataclass(frozen=True)
class ClusteringRule:
    """Rule for escalating severity based on event clustering."""

    event_type: str
    condition_type: str  # "count_in_window" or "consecutive"
    threshold: int
    time_window_seconds: int
    escalated_severity: str
    weight_multiplier: float
    rule_version: str = "v1.0.0"


# ════════════════════════════════════════════════════════════════════════
# Supported event types
# ════════════════════════════════════════════════════════════════════════

ALLOWED_EVENT_TYPES: Final[frozenset[str]] = frozenset(
    {
        # Tab/window events (FR-9.1)
        "tab_switch",
        "window_blur",
        "window_focus_lost",
        # Screen recording events (FR-9.2)
        "screen_recording_started",
        "screen_recording_stopped",
        # Face detection events (FR-9.3, FR-9.4)
        "face_absent",
        "multiple_faces",
        # Audio anomaly events (FR-9.5)
        "multiple_voices",
        "background_noise_spike",
        # Device events
        "camera_disabled",
        "microphone_disabled",
        "device_change",
    }
)


# ════════════════════════════════════════════════════════════════════════
# Default base rules (v1.0.0)
# ════════════════════════════════════════════════════════════════════════

DEFAULT_RULES: Final[tuple[ProctoringRule, ...]] = (
    # Low severity (0.5 - 1.0)
    ProctoringRule("tab_switch", "low", 0.5, "Candidate switched browser tab"),
    ProctoringRule("window_blur", "low", 0.5, "Window lost focus"),
    ProctoringRule("window_focus_lost", "low", 0.5, "Browser window minimized/hidden"),
    ProctoringRule("microphone_disabled", "low", 1.0, "Microphone muted mid-interview"),
    ProctoringRule("device_change", "low", 1.0, "Camera/mic device switched"),
    # Medium severity (1.5 - 2.0)
    ProctoringRule("face_absent", "medium", 1.5, "Face not detected in frame"),
    ProctoringRule("camera_disabled", "medium", 2.0, "Camera turned off mid-interview"),
    ProctoringRule("background_noise_spike", "medium", 1.5, "Sudden background noise increase"),
    # High severity (3.0)
    ProctoringRule("multiple_faces", "high", 3.0, "Multiple faces detected"),
    ProctoringRule("multiple_voices", "high", 3.0, "Multiple voices detected"),
    # Info (0.0 weight, no risk impact)
    ProctoringRule("screen_recording_started", "low", 0.0, "Screen recording initiated"),
    ProctoringRule("screen_recording_stopped", "low", 0.0, "Screen recording ended"),
)

# Index by event_type for O(1) lookup
DEFAULT_RULE_MAP: Final[dict[str, ProctoringRule]] = {
    rule.event_type: rule for rule in DEFAULT_RULES
}


# ════════════════════════════════════════════════════════════════════════
# Default clustering rules (v1.0.0)
# ════════════════════════════════════════════════════════════════════════

DEFAULT_CLUSTERING_RULES: Final[tuple[ClusteringRule, ...]] = (
    ClusteringRule(
        event_type="tab_switch",
        condition_type="count_in_window",
        threshold=10,
        time_window_seconds=60,
        escalated_severity="medium",
        weight_multiplier=1.5,
    ),
    ClusteringRule(
        event_type="face_absent",
        condition_type="consecutive",
        threshold=3,
        time_window_seconds=30,
        escalated_severity="high",
        weight_multiplier=2.0,
    ),
    ClusteringRule(
        event_type="multiple_faces",
        condition_type="count_in_window",
        threshold=5,
        time_window_seconds=300,
        escalated_severity="critical",
        weight_multiplier=2.5,
    ),
)

# Index clustering rules by event_type for lookup
DEFAULT_CLUSTERING_MAP: Final[dict[str, list[ClusteringRule]]] = {}
for _cr in DEFAULT_CLUSTERING_RULES:
    DEFAULT_CLUSTERING_MAP.setdefault(_cr.event_type, []).append(_cr)


# ════════════════════════════════════════════════════════════════════════
# Severity ordering (for comparisons)
# ════════════════════════════════════════════════════════════════════════

SEVERITY_ORDER: Final[dict[str, int]] = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 3,
}

# Only these severities are stored in the proctoring_severity enum
VALID_SEVERITIES: Final[frozenset[str]] = frozenset({"low", "medium", "high", "critical"})
