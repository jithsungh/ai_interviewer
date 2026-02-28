"""
Unit Tests — Circuit Breaker State Machine

Tests state transitions, thread safety, and reset behavior.
All tests use pure domain logic — no I/O, no mocks of external systems.
"""

import threading
import time

import pytest

from app.question.retrieval.domain.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerState,
)


# ═══════════════════════════════════════════════════════════════════════
# Initial State
# ═══════════════════════════════════════════════════════════════════════


class TestCircuitBreakerInitialState:
    """Tests for initial state and defaults."""

    def test_starts_closed(self):
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitBreakerState.CLOSED

    def test_not_open_initially(self):
        cb = CircuitBreaker(name="test")
        assert cb.is_open() is False

    def test_default_thresholds(self):
        cb = CircuitBreaker(name="test")
        assert cb._failure_threshold == 5
        assert cb._timeout_duration == 60.0
        assert cb._success_threshold == 2

    def test_custom_thresholds(self):
        cb = CircuitBreaker(
            name="custom",
            failure_threshold=3,
            timeout_duration=30.0,
            success_threshold=1,
        )
        assert cb._failure_threshold == 3
        assert cb._timeout_duration == 30.0
        assert cb._success_threshold == 1


# ═══════════════════════════════════════════════════════════════════════
# CLOSED → OPEN Transition
# ═══════════════════════════════════════════════════════════════════════


class TestClosedToOpen:
    """Tests CLOSED → OPEN transition (failure threshold exceeded)."""

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_open() is False

    def test_opens_at_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open() is True

    def test_opens_above_threshold(self):
        cb = CircuitBreaker(name="test", failure_threshold=2)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN

    def test_success_resets_failure_count(self):
        """Success in CLOSED state resets the failure counter."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        # Only 1 failure after reset, not 3
        assert cb.state == CircuitBreakerState.CLOSED


# ═══════════════════════════════════════════════════════════════════════
# OPEN → HALF_OPEN Transition
# ═══════════════════════════════════════════════════════════════════════


class TestOpenToHalfOpen:
    """Tests OPEN → HALF_OPEN transition (timeout elapsed)."""

    def test_stays_open_before_timeout(self):
        cb = CircuitBreaker(name="test", failure_threshold=1, timeout_duration=10.0)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open() is True

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=1, timeout_duration=0.05
        )
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        time.sleep(0.1)
        # is_open() triggers the OPEN → HALF_OPEN transition
        assert cb.is_open() is False
        assert cb.state == CircuitBreakerState.HALF_OPEN


# ═══════════════════════════════════════════════════════════════════════
# HALF_OPEN → CLOSED Transition
# ═══════════════════════════════════════════════════════════════════════


class TestHalfOpenToClosed:
    """Tests HALF_OPEN → CLOSED transition (success threshold met)."""

    def _make_half_open(self, **kwargs) -> CircuitBreaker:
        """Helper: create a circuit breaker in HALF_OPEN state."""
        defaults = dict(
            name="test",
            failure_threshold=1,
            timeout_duration=0.01,
            success_threshold=2,
        )
        defaults.update(kwargs)
        cb = CircuitBreaker(**defaults)
        cb.record_failure()
        time.sleep(0.02)
        cb.is_open()  # Trigger transition to HALF_OPEN
        assert cb.state == CircuitBreakerState.HALF_OPEN
        return cb

    def test_stays_half_open_below_success_threshold(self):
        cb = self._make_half_open(success_threshold=2)
        cb.record_success()
        assert cb.state == CircuitBreakerState.HALF_OPEN

    def test_closes_at_success_threshold(self):
        cb = self._make_half_open(success_threshold=2)
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_open() is False


# ═══════════════════════════════════════════════════════════════════════
# HALF_OPEN → OPEN Transition
# ═══════════════════════════════════════════════════════════════════════


class TestHalfOpenBackToOpen:
    """Tests HALF_OPEN → OPEN transition (failure during probe)."""

    def test_failure_in_half_open_reopens(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=1, timeout_duration=0.01
        )
        cb.record_failure()  # Opens
        time.sleep(0.02)
        cb.is_open()  # Transitions to HALF_OPEN
        assert cb.state == CircuitBreakerState.HALF_OPEN

        cb.record_failure()  # Should reopen
        assert cb.state == CircuitBreakerState.OPEN
        assert cb.is_open() is True


# ═══════════════════════════════════════════════════════════════════════
# Reset
# ═══════════════════════════════════════════════════════════════════════


class TestCircuitBreakerReset:
    """Tests explicit reset()."""

    def test_reset_from_open(self):
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.is_open() is False

    def test_reset_from_half_open(self):
        cb = CircuitBreaker(
            name="test", failure_threshold=1, timeout_duration=0.01
        )
        cb.record_failure()
        time.sleep(0.02)
        cb.is_open()
        assert cb.state == CircuitBreakerState.HALF_OPEN

        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED

    def test_reset_clears_failure_count(self):
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        # Need full threshold again to open
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED


# ═══════════════════════════════════════════════════════════════════════
# Thread Safety
# ═══════════════════════════════════════════════════════════════════════


class TestCircuitBreakerThreadSafety:
    """Tests thread-safe state transitions under concurrent access."""

    def test_concurrent_failures(self):
        """Concurrent failures don't corrupt state."""
        cb = CircuitBreaker(name="test", failure_threshold=100)
        errors = []

        def record_failures():
            try:
                for _ in range(50):
                    cb.record_failure()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_failures) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # 4 threads × 50 failures = 200, well above threshold
        assert cb.state == CircuitBreakerState.OPEN

    def test_concurrent_success_and_failure(self):
        """Mixed concurrent calls don't cause exceptions."""
        cb = CircuitBreaker(name="test", failure_threshold=5)
        errors = []

        def mixed_ops():
            try:
                for i in range(100):
                    if i % 2 == 0:
                        cb.record_failure()
                    else:
                        cb.record_success()
                    cb.is_open()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=mixed_ops) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        # State should be valid (one of the three states)
        assert cb.state in (
            CircuitBreakerState.CLOSED,
            CircuitBreakerState.OPEN,
            CircuitBreakerState.HALF_OPEN,
        )
