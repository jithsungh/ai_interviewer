"""
Unit Tests — State Machine

Tests the pure domain logic: SubmissionStatus enum, validate_transition(),
and StateTransitionError.
"""

from __future__ import annotations

import pytest

from app.interview.session.domain.state_machine import (
    SubmissionStatus,
    StateTransitionError,
    validate_transition,
)


# ═══════════════════════════════════════════════════════════════════════════
# SubmissionStatus enum
# ═══════════════════════════════════════════════════════════════════════════


class TestSubmissionStatusEnum:
    def test_all_values_present(self):
        values = {s.value for s in SubmissionStatus}
        assert values == {
            "pending",
            "in_progress",
            "completed",
            "expired",
            "cancelled",
            "reviewed",
        }

    def test_string_coercion(self):
        assert SubmissionStatus("pending") is SubmissionStatus.PENDING
        assert SubmissionStatus("in_progress") is SubmissionStatus.IN_PROGRESS

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            SubmissionStatus("nonexistent")


# ═══════════════════════════════════════════════════════════════════════════
# validate_transition — allowed paths
# ═══════════════════════════════════════════════════════════════════════════


class TestAllowedTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            ("pending", "in_progress"),
            ("pending", "cancelled"),
            ("in_progress", "completed"),
            ("in_progress", "expired"),
            ("in_progress", "cancelled"),
            ("completed", "reviewed"),
            ("expired", "reviewed"),
            ("cancelled", "reviewed"),
        ],
    )
    def test_valid_transitions(self, current, target):
        """Should not raise for every legal edge in the state graph."""
        validate_transition(current, target)  # no exception = pass


# ═══════════════════════════════════════════════════════════════════════════
# validate_transition — forbidden paths
# ═══════════════════════════════════════════════════════════════════════════


class TestForbiddenTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [
            # Backward transitions
            ("in_progress", "pending"),
            ("completed", "in_progress"),
            ("reviewed", "completed"),
            # Skip-ahead
            ("pending", "completed"),
            ("pending", "reviewed"),
            # Terminal cannot move
            ("reviewed", "pending"),
            ("reviewed", "in_progress"),
            ("reviewed", "completed"),
            ("reviewed", "expired"),
            ("reviewed", "cancelled"),
            # Self-loops (not considered valid transitions)
            ("pending", "pending"),
            ("in_progress", "in_progress"),
            ("completed", "completed"),
            ("reviewed", "reviewed"),
        ],
    )
    def test_invalid_transitions(self, current, target):
        with pytest.raises(StateTransitionError) as exc_info:
            validate_transition(current, target)
        assert exc_info.value.current == current
        assert exc_info.value.target == target

    def test_invalid_current_status(self):
        with pytest.raises(StateTransitionError):
            validate_transition("bogus", "in_progress")

    def test_invalid_target_status(self):
        with pytest.raises(StateTransitionError):
            validate_transition("pending", "bogus")


# ═══════════════════════════════════════════════════════════════════════════
# StateTransitionError
# ═══════════════════════════════════════════════════════════════════════════


class TestStateTransitionError:
    def test_message_format(self):
        err = StateTransitionError("pending", "completed")
        assert "pending" in str(err)
        assert "completed" in str(err)

    def test_attributes(self):
        err = StateTransitionError("in_progress", "pending")
        assert err.current == "in_progress"
        assert err.target == "pending"
