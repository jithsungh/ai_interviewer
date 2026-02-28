"""
Integration Tests for AI Telemetry Metrics Export

Tests that telemetry integrates correctly with the shared
Prometheus metrics infrastructure. Uses isolated registries
to avoid polluting global state.
"""

import pytest
from prometheus_client import CollectorRegistry
from unittest.mock import patch

from app.ai.llm.contracts import TelemetryData
from app.ai.telemetry.tracker import TelemetryTracker, _emit_metrics
from app.shared.observability.metrics import MetricsRegistry


@pytest.mark.integration
class TestMetricsExport:
    """Test Prometheus metrics integration"""

    def _create_isolated_registry(self) -> MetricsRegistry:
        """Create isolated MetricsRegistry to avoid global pollution"""
        return MetricsRegistry(registry=CollectorRegistry())

    def test_successful_operation_metrics(self):
        """Successful AI operation records all expected metrics"""
        registry = self._create_isolated_registry()

        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500,
            latency_ms=3000,
            success=True,
            estimated_cost_usd=0.06,
        )

        with patch("app.shared.observability.metrics.metrics", registry):
            _emit_metrics(telemetry, "evaluation")

        # Verify call counter
        assert (
            registry.ai_provider_calls_total.labels(
                provider="openai", model="gpt-4"
            )._value.get()
            == 1
        )

        # Verify token counters
        assert (
            registry.ai_provider_tokens_total.labels(
                provider="openai", type="prompt"
            )._value.get()
            == 1000
        )
        assert (
            registry.ai_provider_tokens_total.labels(
                provider="openai", type="completion"
            )._value.get()
            == 500
        )

    def test_failed_operation_metrics(self):
        """Failed AI operation records call counter but not tokens"""
        registry = self._create_isolated_registry()

        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=1000,
            completion_tokens=0,
            total_tokens=1000,
            latency_ms=30000,
            success=False,
            error_type="timeout",
        )

        with patch("app.shared.observability.metrics.metrics", registry):
            _emit_metrics(telemetry, "evaluation")

        # Call counter still incremented
        assert (
            registry.ai_provider_calls_total.labels(
                provider="openai", model="gpt-4"
            )._value.get()
            == 1
        )

        # Tokens NOT incremented (operation failed)
        assert (
            registry.ai_provider_tokens_total.labels(
                provider="openai", type="prompt"
            )._value.get()
            == 0
        )

    def test_multiple_operations_accumulated(self):
        """Multiple operations accumulate in counters"""
        registry = self._create_isolated_registry()

        for i in range(5):
            telemetry = TelemetryData(
                model_id="gpt-4",
                provider="openai",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=1000 + i * 100,
                success=True,
                estimated_cost_usd=0.01,
            )

            with patch("app.shared.observability.metrics.metrics", registry):
                _emit_metrics(telemetry, "evaluation")

        # 5 calls counted
        assert (
            registry.ai_provider_calls_total.labels(
                provider="openai", model="gpt-4"
            )._value.get()
            == 5
        )

        # 500 prompt tokens total
        assert (
            registry.ai_provider_tokens_total.labels(
                provider="openai", type="prompt"
            )._value.get()
            == 500
        )

    def test_different_providers_isolated(self):
        """Different providers have independent counters"""
        registry = self._create_isolated_registry()

        for provider, model in [("openai", "gpt-4"), ("groq", "llama-3.3-70b-versatile")]:
            telemetry = TelemetryData(
                model_id=model,
                provider=provider,
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=1000,
                success=True,
            )
            with patch("app.shared.observability.metrics.metrics", registry):
                _emit_metrics(telemetry, "evaluation")

        # Each provider gets its own counter
        assert (
            registry.ai_provider_calls_total.labels(
                provider="openai", model="gpt-4"
            )._value.get()
            == 1
        )
        assert (
            registry.ai_provider_calls_total.labels(
                provider="groq", model="llama-3.3-70b-versatile"
            )._value.get()
            == 1
        )

    def test_cost_accumulated(self):
        """Cost accumulates across operations"""
        registry = self._create_isolated_registry()

        for _ in range(10):
            telemetry = TelemetryData(
                model_id="gpt-4",
                provider="openai",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                latency_ms=1000,
                success=True,
                estimated_cost_usd=0.01,
            )
            with patch("app.shared.observability.metrics.metrics", registry):
                _emit_metrics(telemetry, "evaluation")

        cost = registry.ai_provider_cost_usd_total.labels(
            provider="openai"
        )._value.get()

        assert abs(cost - 0.10) < 0.001


@pytest.mark.integration
class TestEndToEndTrackerMetrics:
    """Test full tracker → metrics pipeline"""

    def test_tracker_emits_to_registry(self):
        """Full tracker pipeline: track → finalize → metrics emitted"""
        registry = MetricsRegistry(registry=CollectorRegistry())

        tracker = TelemetryTracker()

        with patch("app.shared.observability.metrics.metrics", registry):
            with tracker.track("question_generation") as span:
                span.set_input(
                    prompt_tokens=200,
                    model_id="llama-3.3-70b-versatile",
                    provider="groq",
                )
                span.set_output(completion_tokens=100, success=True)

        # Metrics should have been emitted in the finally block
        assert (
            registry.ai_provider_calls_total.labels(
                provider="groq", model="llama-3.3-70b-versatile"
            )._value.get()
            == 1
        )

    def test_tracker_error_still_emits_metrics(self):
        """Tracker emits metrics even when tracked operation fails"""
        registry = MetricsRegistry(registry=CollectorRegistry())

        tracker = TelemetryTracker()

        try:
            with patch("app.shared.observability.metrics.metrics", registry):
                with tracker.track("evaluation") as span:
                    span.set_input(
                        prompt_tokens=100,
                        model_id="gpt-4",
                        provider="openai",
                    )
                    raise RuntimeError("Provider error")
        except RuntimeError:
            pass

        # Metrics still emitted despite exception
        assert (
            registry.ai_provider_calls_total.labels(
                provider="openai", model="gpt-4"
            )._value.get()
            == 1
        )
