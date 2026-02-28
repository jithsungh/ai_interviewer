"""
Execution State Machine — Valid state transitions for code submissions

Enforces deterministic state progression.  Terminal states cannot
be re-entered.  The state machine prevents race-condition overwrites
by rejecting invalid transitions.

References:
- execution/REQUIREMENTS.md §5 (State Transitions)
- execution/REQUIREMENTS.md §6 (Invariants — State Determinism)
"""

from typing import Dict, FrozenSet

from app.coding.enums import ExecutionStatus


# Terminal states: once reached, no further transitions are allowed.
TERMINAL_STATES: FrozenSet[ExecutionStatus] = frozenset({
    ExecutionStatus.PASSED,
    ExecutionStatus.FAILED,
    ExecutionStatus.ERROR,
    ExecutionStatus.TIMEOUT,
    ExecutionStatus.MEMORY_EXCEEDED,
})

# Valid outgoing transitions per state.
VALID_TRANSITIONS: Dict[ExecutionStatus, FrozenSet[ExecutionStatus]] = {
    ExecutionStatus.PENDING: frozenset({ExecutionStatus.RUNNING}),
    ExecutionStatus.RUNNING: frozenset({
        ExecutionStatus.PASSED,
        ExecutionStatus.FAILED,
        ExecutionStatus.ERROR,
        ExecutionStatus.TIMEOUT,
        ExecutionStatus.MEMORY_EXCEEDED,
    }),
    # All terminal states have no outgoing transitions.
    ExecutionStatus.PASSED: frozenset(),
    ExecutionStatus.FAILED: frozenset(),
    ExecutionStatus.ERROR: frozenset(),
    ExecutionStatus.TIMEOUT: frozenset(),
    ExecutionStatus.MEMORY_EXCEEDED: frozenset(),
}


def is_terminal_state(status: ExecutionStatus) -> bool:
    """Return True if *status* is a terminal (final) state."""
    return status in TERMINAL_STATES


def is_valid_transition(
    current: ExecutionStatus,
    target: ExecutionStatus,
) -> bool:
    """
    Check whether the transition *current* → *target* is allowed.

    Args:
        current: Current execution status.
        target: Desired new status.

    Returns:
        ``True`` if the transition is valid, ``False`` otherwise.
    """
    allowed = VALID_TRANSITIONS.get(current, frozenset())
    return target in allowed


def validate_transition(
    current: ExecutionStatus,
    target: ExecutionStatus,
) -> None:
    """
    Validate a state transition, raising ``ValueError`` if invalid.

    Args:
        current: Current execution status.
        target: Desired new status.

    Raises:
        ValueError: If the transition is not permitted.
    """
    if not is_valid_transition(current, target):
        allowed = sorted(
            s.value for s in VALID_TRANSITIONS.get(current, frozenset())
        )
        raise ValueError(
            f"Invalid state transition: {current.value} → {target.value}. "
            f"Allowed transitions from {current.value}: {allowed}"
        )
