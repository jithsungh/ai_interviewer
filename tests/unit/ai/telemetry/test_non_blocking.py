"""
Unit Tests for Non-Blocking Guarantee

Tests that telemetry recording never crashes AI operations,
even when metrics backends fail, logging fails, or exceptions
occur during telemetry processing.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from app.ai.telemetry.tracker import TelemetryTracker, TelemetrySpan


class TestNonBlockingGuarantee:
    """Test that telemetry failures never propagate"""

    def test_telemetry_failure_does_not_propagate(self):
        """Telemetry recording failure does not crash operation"""
        tracker = TelemetryTracker()

        # Mock _emit_metrics to raise
        with patch(
            "app.ai.telemetry.tracker._emit_metrics",
            side_effect=Exception("Metrics backend down"),
        ):
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10)
                span.set_output(completion_tokens=5, success=True)

            # Should complete without raising
            telemetry = span.finalize()
            assert telemetry is not None
            assert telemetry.success is True

    def test_metrics_backend_unavailable(self):
        """Metrics export failure logged, does not block"""
        tracker = TelemetryTracker()

        with patch(
            "app.ai.telemetry.tracker._emit_metrics",
            side_effect=ConnectionError("Backend unavailable"),
        ):
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10)
                span.set_output(completion_tokens=5, success=True)

            telemetry = span.finalize()
            assert telemetry.success is True

    def test_structured_log_failure_does_not_propagate(self):
        """Structured log failure does not crash operation"""
        tracker = TelemetryTracker()

        with patch(
            "app.ai.telemetry.tracker._emit_structured_log",
            side_effect=Exception("Logging failed"),
        ):
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10)
                span.set_output(completion_tokens=5, success=True)

            telemetry = span.finalize()
            assert telemetry is not None

    def test_cost_estimation_failure_does_not_propagate(self):
        """Cost estimation failure returns None, doesn't crash"""
        tracker = TelemetryTracker()

        with patch(
            "app.ai.telemetry.tracker._cost_estimator.estimate_cost",
            side_effect=Exception("Pricing lookup failed"),
        ):
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10, model_id="gpt-4", provider="openai")
                span.set_output(completion_tokens=5, success=True)

            telemetry = span.finalize()
            assert telemetry is not None
            # Cost should be None since estimation failed
            assert telemetry.estimated_cost_usd is None

    def test_both_emit_functions_failing(self):
        """Both metrics and logging failing still works"""
        tracker = TelemetryTracker()

        with patch(
            "app.ai.telemetry.tracker._emit_metrics",
            side_effect=Exception("Metrics down"),
        ), patch(
            "app.ai.telemetry.tracker._emit_structured_log",
            side_effect=Exception("Logging down"),
        ):
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10)
                span.set_output(completion_tokens=5, success=True)

            telemetry = span.finalize()
            assert telemetry is not None
            assert telemetry.success is True


class TestTelemetryOverhead:
    """Test that telemetry adds minimal overhead"""

    def test_telemetry_recording_is_fast(self):
        """Telemetry adds minimal overhead (<5ms per operation)"""
        tracker = TelemetryTracker()
        measurements = []

        for _ in range(100):
            start = time.perf_counter()

            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10, model_id="gpt-4", provider="openai")
                span.set_output(completion_tokens=5, success=True)

            span.finalize()
            overhead_ms = (time.perf_counter() - start) * 1000
            measurements.append(overhead_ms)

        avg_overhead = sum(measurements) / len(measurements)
        # Average overhead should be well under 5ms
        assert avg_overhead < 5, f"Average overhead {avg_overhead:.2f}ms exceeds 5ms"

    def test_span_creation_is_fast(self):
        """Span creation alone is very fast"""
        start = time.perf_counter()

        for _ in range(1000):
            span = TelemetrySpan("test")

        duration_ms = (time.perf_counter() - start) * 1000
        per_span_us = (duration_ms / 1000) * 1000  # microseconds

        # Each span creation should be well under 1ms
        assert per_span_us < 100, f"Per-span creation {per_span_us:.2f}us too slow"


class TestConcurrency:
    """Test thread-safety of telemetry tracking"""

    def test_concurrent_telemetry_no_contention(self):
        """Concurrent telemetry recording has no contention"""
        from concurrent.futures import ThreadPoolExecutor

        tracker = TelemetryTracker()
        results = []

        def record_telemetry(idx):
            with tracker.track("test") as span:
                span.set_input(
                    prompt_tokens=idx * 10,
                    model_id="gpt-4",
                    provider="openai",
                )
                span.set_output(completion_tokens=idx * 5, success=True)
            return span.finalize()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(record_telemetry, i) for i in range(100)]
            results = [f.result() for f in futures]

        assert len(results) == 100

        # Each result should have correct tokens for its index
        # (Testing independence, not specific values since order is non-deterministic)
        token_sums = {r.total_tokens for r in results}
        assert len(token_sums) > 1  # Different values exist (not all same)

    def test_concurrent_spans_independent(self):
        """Concurrent spans don't interfere with each other"""
        from concurrent.futures import ThreadPoolExecutor

        tracker = TelemetryTracker()

        def create_success_span():
            with tracker.track("success_op") as span:
                span.set_input(prompt_tokens=100)
                span.set_output(completion_tokens=50, success=True)
            return span.finalize()

        def create_failure_span():
            with tracker.track("failure_op") as span:
                span.set_input(prompt_tokens=200)
                span.set_error("timeout")
            return span.finalize()

        with ThreadPoolExecutor(max_workers=4) as executor:
            success_futures = [executor.submit(create_success_span) for _ in range(50)]
            failure_futures = [executor.submit(create_failure_span) for _ in range(50)]

            successes = [f.result() for f in success_futures]
            failures = [f.result() for f in failure_futures]

        assert all(r.success is True for r in successes)
        assert all(r.success is False for r in failures)
        assert all(r.prompt_tokens == 100 for r in successes)
        assert all(r.prompt_tokens == 200 for r in failures)
