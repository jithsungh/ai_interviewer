"""
Circuit Breaker for Qdrant Fault Tolerance

Implements the circuit-breaker pattern to prevent cascading failures
when Qdrant is unavailable.

States:
    CLOSED    → Normal operation; failures counted.
    OPEN      → All requests short-circuited; fallback used.
    HALF_OPEN → Probe requests allowed to test recovery.

Transitions:
    CLOSED → OPEN            when failure_count ≥ failure_threshold
    OPEN → HALF_OPEN         when timeout_duration elapsed
    HALF_OPEN → CLOSED       when success_count ≥ success_threshold
    HALF_OPEN → OPEN         on any failure

Thread-safe via threading.Lock (compatible with asyncio thread-pool workers).
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitBreakerState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Thread-safe circuit breaker.

    Args:
        name: Identifier for logging.
        failure_threshold: Consecutive failures before opening.
        timeout_duration: Seconds to wait before probing (OPEN → HALF_OPEN).
        success_threshold: Consecutive successes in HALF_OPEN before closing.
    """

    def __init__(
        self,
        name: str = "qdrant",
        failure_threshold: int = 5,
        timeout_duration: float = 60.0,
        success_threshold: int = 2,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._timeout_duration = timeout_duration
        self._success_threshold = success_threshold

        self._state = CircuitBreakerState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    # ── Public Interface ──────────────────────────────────────────────

    def is_open(self) -> bool:
        """
        Check if circuit breaker is open (short-circuiting).

        Also handles the OPEN → HALF_OPEN timeout transition.

        Returns:
            True if requests should be short-circuited.
        """
        with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self._timeout_duration:
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._success_count = 0
                    logger.info(
                        "Circuit breaker [%s] transitioned OPEN → HALF_OPEN "
                        "(timeout %.1fs elapsed)",
                        self._name,
                        elapsed,
                    )
                    return False  # Allow probe request
                return True  # Still open

            return False  # CLOSED or HALF_OPEN — allow request

    def record_success(self) -> None:
        """Record a successful operation."""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self._success_threshold:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
                    logger.info(
                        "Circuit breaker [%s] transitioned HALF_OPEN → CLOSED "
                        "(%d consecutive successes)",
                        self._name,
                        self._success_count,
                    )
            elif self._state == CircuitBreakerState.CLOSED:
                # Reset failure streak on success
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitBreakerState.HALF_OPEN:
                # Any failure in HALF_OPEN → back to OPEN
                self._state = CircuitBreakerState.OPEN
                logger.warning(
                    "Circuit breaker [%s] transitioned HALF_OPEN → OPEN "
                    "(probe request failed)",
                    self._name,
                )
            elif self._failure_count >= self._failure_threshold:
                self._state = CircuitBreakerState.OPEN
                logger.warning(
                    "Circuit breaker [%s] transitioned CLOSED → OPEN "
                    "(%d consecutive failures, threshold=%d)",
                    self._name,
                    self._failure_count,
                    self._failure_threshold,
                )

    @property
    def state(self) -> CircuitBreakerState:
        """Current state (triggers timeout-based transition check)."""
        self.is_open()
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def reset(self) -> None:
        """Force-reset the breaker to CLOSED. Use for testing only."""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = 0.0
            logger.info("Circuit breaker [%s] force-reset to CLOSED", self._name)

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self._name!r}, state={self._state.value}, "
            f"failures={self._failure_count}/{self._failure_threshold})"
        )
