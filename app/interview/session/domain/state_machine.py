"""
Submission State Machine

Pure domain logic — no I/O, no framework dependencies.

State diagram:
    pending → in_progress → completed → reviewed
                          → expired   → reviewed
                          → cancelled → reviewed
    pending  → cancelled  → reviewed

Terminal states: reviewed (no further transitions possible).
"""

from __future__ import annotations

import enum
from typing import FrozenSet, Dict


class SubmissionStatus(str, enum.Enum):
    """All valid submission statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    REVIEWED = "reviewed"


class StateTransitionError(Exception):
    """Raised when a state transition is not allowed by the state machine."""

    def __init__(self, current: str, target: str) -> None:
        self.current = current
        self.target = target
        super().__init__(
            f"Invalid state transition: {current!r} → {target!r}"
        )


# ════════════════════════════════════════════════════════════════════════
# Transition table
# ════════════════════════════════════════════════════════════════════════

# Maps each status to the set of statuses it may transition to.
_ALLOWED_TRANSITIONS: Dict[SubmissionStatus, FrozenSet[SubmissionStatus]] = {
    SubmissionStatus.PENDING: frozenset({
        SubmissionStatus.IN_PROGRESS,
        SubmissionStatus.CANCELLED,
    }),
    SubmissionStatus.IN_PROGRESS: frozenset({
        SubmissionStatus.COMPLETED,
        SubmissionStatus.EXPIRED,
        SubmissionStatus.CANCELLED,
    }),
    SubmissionStatus.COMPLETED: frozenset({
        SubmissionStatus.REVIEWED,
    }),
    SubmissionStatus.EXPIRED: frozenset({
        SubmissionStatus.REVIEWED,
    }),
    SubmissionStatus.CANCELLED: frozenset({
        SubmissionStatus.REVIEWED,
    }),
    SubmissionStatus.REVIEWED: frozenset(),  # terminal — no outbound edges
}


def validate_transition(current: str, target: str) -> None:
    """
    Validate that *current → target* is a legal transition.

    Args:
        current: Current status value (e.g. ``"pending"``).
        target:  Desired status value (e.g. ``"in_progress"``).

    Raises:
        StateTransitionError: If the transition is not allowed.
    """
    try:
        current_status = SubmissionStatus(current)
    except ValueError:
        raise StateTransitionError(current, target)

    try:
        target_status = SubmissionStatus(target)
    except ValueError:
        raise StateTransitionError(current, target)

    if target_status not in _ALLOWED_TRANSITIONS.get(current_status, frozenset()):
        raise StateTransitionError(current, target)
