"""
Unit Tests for TelemetryTracker and TelemetrySpan

Tests span lifecycle, field recording, latency measurement,
non-blocking guarantees, cost estimation integration, and
metrics emission.
"""

import time
import pytest
from unittest.mock import patch, MagicMock

from app.ai.telemetry.tracker import TelemetryTracker, TelemetrySpan
from app.ai.llm.contracts import TelemetryData


class TestTelemetrySpan:
    """Test TelemetrySpan field recording and finalization"""

    def test_basic_span_recording(self):
        """Span records all required fields"""
        tracker = TelemetryTracker()

        with tracker.track("test_operation") as span:
            span.set_input(
                prompt_tokens=100,
                model_id="gpt-4",
                provider="openai",
            )
            time.sleep(0.01)  # Simulate work
            span.set_output(completion_tokens=50, success=True)

        telemetry = span.finalize()

        assert telemetry.model_id == "gpt-4"
        assert telemetry.provider == "openai"
        assert telemetry.prompt_tokens == 100
        assert telemetry.completion_tokens == 50
        assert telemetry.total_tokens == 150
        assert telemetry.success is True
        assert telemetry.latency_ms >= 10  # At least 10ms
        assert telemetry.error_type is None

    def test_span_records_failure(self):
        """Span records error information on failure"""
        tracker = TelemetryTracker()

        with tracker.track("test_operation") as span:
            span.set_input(
                prompt_tokens=100,
                model_id="gpt-4",
                provider="openai",
            )
            span.set_error(error_type="timeout")

        telemetry = span.finalize()

        assert telemetry.success is False
        assert telemetry.error_type == "timeout"
        assert telemetry.prompt_tokens == 100
        assert telemetry.completion_tokens == 0  # No completion on error

    def test_total_tokens_computed(self):
        """Total tokens always computed, never user-provided"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=100)
        span.set_output(completion_tokens=50, success=True)

        telemetry = span.finalize()
        assert telemetry.total_tokens == 150

    def test_latency_always_positive(self):
        """Latency must be >= 0"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10)
        span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert telemetry.latency_ms >= 0

    def test_retry_count_tracking(self):
        """Retry count recorded correctly"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10)
        span.increment_retry()
        span.increment_retry()
        span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert telemetry.retry_count == 2

    def test_finalize_returns_telemetry_data_type(self):
        """finalize() returns TelemetryData from ai/llm/contracts"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10, model_id="gpt-4", provider="openai")
        span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert isinstance(telemetry, TelemetryData)

    def test_finalize_idempotent(self):
        """finalize() can be called multiple times (same latency)"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10)
        span.set_output(completion_tokens=5, success=True)

        t1 = span.finalize()
        t2 = span.finalize()
        assert t1.latency_ms == t2.latency_ms

    def test_negative_tokens_clamped_to_zero(self):
        """Negative token counts are clamped to 0"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=-10)
        span.set_output(completion_tokens=-5, success=True)

        telemetry = span.finalize()
        assert telemetry.prompt_tokens == 0
        assert telemetry.completion_tokens == 0
        assert telemetry.total_tokens == 0

    def test_optional_context_fields(self):
        """Optional context fields recorded correctly"""
        span = TelemetrySpan("test")
        span.set_input(
            prompt_tokens=100,
            model_id="gpt-4",
            provider="openai",
            deterministic=True,
            temperature=0.0,
            max_tokens=500,
            request_id="req_abc123",
            organization_id=42,
        )
        span.set_output(completion_tokens=50, success=True)

        telemetry = span.finalize()
        assert telemetry.deterministic is True
        assert telemetry.temperature == 0.0
        assert telemetry.max_tokens == 500
        assert telemetry.request_id == "req_abc123"
        assert telemetry.organization_id == 42

    def test_set_output_overrides_model(self):
        """set_output can override model_id if provider returned different model"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10, model_id="gpt-4")
        span.set_output(completion_tokens=5, success=True, model_id="gpt-4-turbo")

        telemetry = span.finalize()
        assert telemetry.model_id == "gpt-4-turbo"

    def test_cost_estimation_included(self):
        """Known models get cost estimation"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=1000, model_id="gpt-4", provider="openai")
        span.set_output(completion_tokens=500, success=True)

        telemetry = span.finalize()
        assert telemetry.estimated_cost_usd is not None
        assert telemetry.estimated_cost_usd > 0

    def test_unknown_model_no_cost(self):
        """Unknown models have None for cost"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=1000, model_id="unknown-model-xyz", provider="test")
        span.set_output(completion_tokens=500, success=True)

        telemetry = span.finalize()
        assert telemetry.estimated_cost_usd is None

    def test_zero_tokens_zero_cost(self):
        """Zero tokens = zero cost for known models"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=0, model_id="gpt-4", provider="openai")
        span.set_output(completion_tokens=0, success=True)

        telemetry = span.finalize()
        assert telemetry.estimated_cost_usd == 0.0

    def test_operation_type_accessible(self):
        """operation_type is accessible on the span"""
        span = TelemetrySpan("question_generation")
        assert span.operation_type == "question_generation"


class TestTelemetryTracker:
    """Test TelemetryTracker context manager"""

    def test_context_manager_yields_span(self):
        """track() yields a TelemetrySpan"""
        tracker = TelemetryTracker()

        with tracker.track("test_op") as span:
            assert isinstance(span, TelemetrySpan)

    def test_exception_propagates(self):
        """Exceptions from tracked operation propagate normally"""
        tracker = TelemetryTracker()

        with pytest.raises(ValueError, match="test error"):
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10)
                raise ValueError("test error")

    def test_span_marked_failed_on_exception(self):
        """Span is marked as failed when exception occurs"""
        tracker = TelemetryTracker()

        try:
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=10)
                raise ValueError("test error")
        except ValueError:
            pass

        telemetry = span.finalize()
        assert telemetry.success is False

    def test_partial_telemetry_on_exception(self):
        """Partial telemetry recorded even if span interrupted"""
        tracker = TelemetryTracker()

        try:
            with tracker.track("test") as span:
                span.set_input(prompt_tokens=100, model_id="gpt-4", provider="openai")
                raise Exception("Operation failed")
        except Exception:
            pass

        telemetry = span.finalize()
        assert telemetry.prompt_tokens == 100
        assert telemetry.completion_tokens == 0
        assert telemetry.model_id == "gpt-4"

    def test_latency_measured_across_sleep(self):
        """Latency captures actual wall time"""
        tracker = TelemetryTracker()

        with tracker.track("test") as span:
            span.set_input(prompt_tokens=10)
            time.sleep(0.05)  # 50ms
            span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert telemetry.latency_ms >= 40  # Allow some tolerance

    def test_metrics_emitted_on_success(self):
        """Prometheus metrics emitted on successful operation"""
        from prometheus_client import CollectorRegistry
        from app.shared.observability.metrics import MetricsRegistry
        from app.ai.telemetry.tracker import _emit_metrics

        registry = MetricsRegistry(registry=CollectorRegistry())

        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=3000,
            success=True,
        )

        # _emit_metrics does a lazy import of metrics, so patch at source
        with patch(
            "app.shared.observability.metrics.metrics",
            registry,
        ):
            _emit_metrics(telemetry, "evaluation")

        # Verify metrics were recorded
        assert (
            registry.ai_provider_calls_total.labels(
                provider="openai", model="gpt-4"
            )._value.get()
            == 1
        )

    def test_multiple_operations_independent(self):
        """Multiple tracker operations don't interfere"""
        tracker = TelemetryTracker()

        with tracker.track("op1") as span1:
            span1.set_input(prompt_tokens=100, model_id="gpt-4", provider="openai")
            span1.set_output(completion_tokens=50, success=True)

        with tracker.track("op2") as span2:
            span2.set_input(prompt_tokens=200, model_id="gpt-3.5-turbo", provider="openai")
            span2.set_output(completion_tokens=100, success=False)
            span2.set_error("rate_limit")

        t1 = span1.finalize()
        t2 = span2.finalize()

        assert t1.prompt_tokens == 100
        assert t1.success is True
        assert t2.prompt_tokens == 200
        assert t2.success is False
        assert t2.error_type == "rate_limit"


class TestEdgeCases:
    """Test edge cases for telemetry"""

    def test_zero_tokens(self):
        """Handle zero token counts gracefully"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=0)
        span.set_output(completion_tokens=0, success=True)

        telemetry = span.finalize()
        assert telemetry.total_tokens == 0

    def test_very_high_token_count(self):
        """Handle very high token counts (100K+)"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=100_000)
        span.set_output(completion_tokens=50_000, success=True)

        telemetry = span.finalize()
        assert telemetry.total_tokens == 150_000

    def test_very_high_latency(self):
        """Handle very high latencies"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10)
        time.sleep(0.1)  # 100ms
        span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert telemetry.latency_ms >= 90

    def test_empty_model_and_provider(self):
        """Handle empty model_id and provider"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10)
        span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert telemetry.model_id == ""
        assert telemetry.provider == ""
        assert telemetry.estimated_cost_usd is None

    def test_set_error_after_set_output(self):
        """Error overrides success"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10)
        span.set_output(completion_tokens=5, success=True)
        span.set_error("timeout")

        telemetry = span.finalize()
        assert telemetry.success is False
        assert telemetry.error_type == "timeout"

    def test_multiple_retries(self):
        """Multiple retries tracked correctly"""
        span = TelemetrySpan("test")
        span.set_input(prompt_tokens=10)
        for _ in range(5):
            span.increment_retry()
        span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert telemetry.retry_count == 5
