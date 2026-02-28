"""
Unit tests for coding.execution.state_machine — State transition validation
"""

import pytest
from app.coding.enums import ExecutionStatus
from app.coding.execution.state_machine import (
    TERMINAL_STATES,
    VALID_TRANSITIONS,
    is_terminal_state,
    is_valid_transition,
    validate_transition,
)


class TestTerminalStates:
    """Verify terminal state classification."""

    @pytest.mark.parametrize(
        "status",
        [
            ExecutionStatus.PASSED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ERROR,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.MEMORY_EXCEEDED,
        ],
    )
    def test_terminal_states(self, status: ExecutionStatus):
        assert is_terminal_state(status) is True

    @pytest.mark.parametrize(
        "status",
        [
            ExecutionStatus.PENDING,
            ExecutionStatus.RUNNING,
        ],
    )
    def test_non_terminal_states(self, status: ExecutionStatus):
        assert is_terminal_state(status) is False

    def test_terminal_count(self):
        assert len(TERMINAL_STATES) == 5


class TestValidTransitions:
    """Verify allowed and forbidden state transitions."""

    # --- Valid transitions ---

    def test_pending_to_running(self):
        assert is_valid_transition(ExecutionStatus.PENDING, ExecutionStatus.RUNNING) is True

    @pytest.mark.parametrize(
        "target",
        [
            ExecutionStatus.PASSED,
            ExecutionStatus.FAILED,
            ExecutionStatus.ERROR,
            ExecutionStatus.TIMEOUT,
            ExecutionStatus.MEMORY_EXCEEDED,
        ],
    )
    def test_running_to_terminal(self, target: ExecutionStatus):
        assert is_valid_transition(ExecutionStatus.RUNNING, target) is True

    # --- Invalid transitions ---

    def test_pending_to_passed_invalid(self):
        assert is_valid_transition(ExecutionStatus.PENDING, ExecutionStatus.PASSED) is False

    def test_pending_to_failed_invalid(self):
        assert is_valid_transition(ExecutionStatus.PENDING, ExecutionStatus.FAILED) is False

    @pytest.mark.parametrize("terminal", list(TERMINAL_STATES))
    def test_terminal_to_any_invalid(self, terminal: ExecutionStatus):
        for target in ExecutionStatus:
            assert is_valid_transition(terminal, target) is False

    def test_running_to_pending_invalid(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.PENDING) is False

    def test_running_to_running_invalid(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.RUNNING) is False

    def test_pending_to_pending_invalid(self):
        assert is_valid_transition(ExecutionStatus.PENDING, ExecutionStatus.PENDING) is False


class TestValidateTransition:
    """Verify validate_transition raises on invalid transitions."""

    def test_valid_transition_does_not_raise(self):
        validate_transition(ExecutionStatus.PENDING, ExecutionStatus.RUNNING)
        validate_transition(ExecutionStatus.RUNNING, ExecutionStatus.PASSED)

    def test_invalid_transition_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid state transition"):
            validate_transition(ExecutionStatus.PENDING, ExecutionStatus.PASSED)

    def test_error_message_contains_states(self):
        with pytest.raises(ValueError, match="pending.*passed"):
            validate_transition(ExecutionStatus.PENDING, ExecutionStatus.PASSED)

    def test_terminal_state_raises(self):
        with pytest.raises(ValueError, match="Invalid state transition"):
            validate_transition(ExecutionStatus.PASSED, ExecutionStatus.RUNNING)


class TestTransitionCompleteness:
    """Verify VALID_TRANSITIONS covers all states."""

    def test_all_states_have_entry(self):
        for status in ExecutionStatus:
            assert status in VALID_TRANSITIONS, f"{status} missing from VALID_TRANSITIONS"
