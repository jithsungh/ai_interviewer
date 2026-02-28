"""
AI Telemetry Tracker

Provides span-based telemetry tracking for AI operations.
Uses monotonic clock for latency measurement and integrates with
shared/observability for logging and Prometheus metrics.

Design decisions:
- Non-blocking: telemetry failure NEVER propagates to calling code
- Uses time.perf_counter() for latency (monotonic, high-resolution)
- TelemetrySpan produces TelemetryData (from ai/llm/contracts) for compatibility
- All metrics emission wrapped in try/except
- Thread-safe: each span is independent
"""

import time
import logging
from contextlib import contextmanager
from typing import Optional

from app.ai.llm.contracts import TelemetryData
from .cost import CostEstimator
from .contracts import OperationType

# Module-level logger — uses standard logging to avoid import issues.
# Callers who need ContextLogger can pass it explicitly.
_logger = logging.getLogger("app.ai.telemetry.tracker")

# Module-level cost estimator (thread-safe, immutable pricing data)
_cost_estimator = CostEstimator()


class TelemetrySpan:
    """
    Tracks a single AI operation's telemetry.

    Created by TelemetryTracker.track(). Records timing, token usage,
    model info, success/failure, and cost estimation.

    Lifecycle:
        1. Created by tracker.track()
        2. set_input() called before AI operation
        3. set_output() called after AI operation succeeds
        4. set_error() called if AI operation fails
        5. finalize() returns TelemetryData

    Invariants:
        - total_tokens always computed (prompt + completion)
        - latency measured via monotonic clock (never negative)
        - cost estimated from pricing table (None if model unknown)
        - Thread-safe (each span is independent, no shared mutable state)
    """

    def __init__(self, operation_type: str):
        """
        Initialize telemetry span.

        Args:
            operation_type: Type of AI operation (from OperationType enum or string).
        """
        self._operation_type = operation_type
        self._start_time = time.perf_counter()
        self._end_time: Optional[float] = None

        # Input fields
        self._prompt_tokens: int = 0
        self._model_id: str = ""
        self._provider: str = ""
        self._prompt_type: Optional[str] = None

        # Output fields
        self._completion_tokens: int = 0
        self._success: bool = False
        self._error_type: Optional[str] = None
        self._retry_count: int = 0

        # Optional context
        self._deterministic: bool = False
        self._temperature: Optional[float] = None
        self._max_tokens: Optional[int] = None
        self._prompt_version: Optional[int] = None
        self._request_id: Optional[str] = None
        self._organization_id: Optional[int] = None

        self._finalized: bool = False

    @property
    def operation_type(self) -> str:
        """Operation type for this span."""
        return self._operation_type

    def set_input(
        self,
        prompt_tokens: int,
        model_id: str = "",
        provider: str = "",
        prompt_type: Optional[str] = None,
        deterministic: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt_version: Optional[int] = None,
        request_id: Optional[str] = None,
        organization_id: Optional[int] = None,
    ) -> None:
        """
        Record input parameters before AI call.

        Args:
            prompt_tokens: Number of prompt/input tokens (>= 0).
            model_id: Provider-specific model identifier.
            provider: AI provider name (groq, openai, etc.).
            prompt_type: Type of prompt used.
            deterministic: Whether deterministic mode is enabled.
            temperature: Generation temperature.
            max_tokens: Maximum completion tokens.
            prompt_version: Prompt template version.
            request_id: Request correlation ID.
            organization_id: Organization ID for cost allocation.
        """
        self._prompt_tokens = max(0, prompt_tokens)
        if model_id:
            self._model_id = model_id
        if provider:
            self._provider = provider
        self._prompt_type = prompt_type
        self._deterministic = deterministic
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._prompt_version = prompt_version
        self._request_id = request_id
        self._organization_id = organization_id

    def set_output(
        self,
        completion_tokens: int,
        success: bool = True,
        model_id: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> None:
        """
        Record output after successful AI call.

        Args:
            completion_tokens: Number of completion/output tokens (>= 0).
            success: Whether the operation succeeded.
            model_id: Override model_id if provider returned different model.
            provider: Override provider if needed.
        """
        self._completion_tokens = max(0, completion_tokens)
        self._success = success
        if model_id:
            self._model_id = model_id
        if provider:
            self._provider = provider

    def set_error(self, error_type: str) -> None:
        """
        Record error after failed AI call.

        Args:
            error_type: Classified error type (from AIErrorType or string).
        """
        self._success = False
        self._error_type = error_type

    def increment_retry(self) -> None:
        """Increment retry counter."""
        self._retry_count += 1

    def finalize(self) -> TelemetryData:
        """
        Finalize span and produce TelemetryData.

        Calculates latency and cost estimation.
        Can be called multiple times (idempotent on timing).

        Returns:
            TelemetryData with all recorded metrics.

        Invariants:
            - total_tokens = prompt_tokens + completion_tokens (enforced by TelemetryData)
            - latency_ms >= 0
            - cost = None if model has no known pricing
        """
        if not self._finalized:
            self._end_time = time.perf_counter()
            self._finalized = True

        # Calculate latency
        elapsed = (self._end_time or time.perf_counter()) - self._start_time
        latency_ms = max(0, int(elapsed * 1000))

        # Estimate cost (non-blocking)
        estimated_cost: Optional[float] = None
        try:
            cost_estimate = _cost_estimator.estimate_cost(
                model_id=self._model_id,
                prompt_tokens=self._prompt_tokens,
                completion_tokens=self._completion_tokens,
            )
            if cost_estimate is not None:
                estimated_cost = cost_estimate.total_cost_usd
        except Exception:
            # Cost estimation failure is non-fatal
            _logger.debug("Cost estimation failed", exc_info=True)

        return TelemetryData(
            model_id=self._model_id,
            provider=self._provider,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
            total_tokens=self._prompt_tokens + self._completion_tokens,
            latency_ms=latency_ms,
            success=self._success,
            error_type=self._error_type,
            retry_count=self._retry_count,
            deterministic=self._deterministic,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
            request_id=self._request_id,
            organization_id=self._organization_id,
            estimated_cost_usd=estimated_cost,
        )


class TelemetryTracker:
    """
    Factory for creating telemetry spans.

    Provides a context manager interface for tracking AI operations.
    All telemetry recording is non-blocking and failure-safe.

    Usage:
        tracker = TelemetryTracker()

        with tracker.track("question_generation") as span:
            span.set_input(prompt_tokens=100, model_id="gpt-4", provider="openai")
            result = await provider.generate_text(request)
            span.set_output(
                completion_tokens=result.telemetry.completion_tokens,
                success=result.success
            )

        telemetry = span.finalize()
    """

    def __init__(self) -> None:
        """Initialize telemetry tracker."""
        pass

    @contextmanager
    def track(self, operation_type: str):
        """
        Create a telemetry span for an AI operation.

        Args:
            operation_type: Type of AI operation (e.g., "question_generation",
                          "evaluation"). Use OperationType enum values.

        Yields:
            TelemetrySpan to record input/output.

        Guarantees:
            - Span is always yielded (even if setup fails)
            - Exceptions from the tracked operation propagate normally
            - Telemetry recording failures are logged but never propagated
            - Metrics are emitted in the finally block (non-blocking)
        """
        span = TelemetrySpan(operation_type)

        try:
            yield span
        except Exception:
            # Record that operation failed (if not already set)
            if span._success and span._error_type is None:
                span._success = False
            raise
        finally:
            # Finalize and emit metrics (non-blocking)
            try:
                telemetry = span.finalize()
                _emit_metrics(telemetry, operation_type)
                _emit_structured_log(telemetry, operation_type)
            except Exception:
                # Telemetry failure MUST NOT propagate
                _logger.debug(
                    "Failed to emit telemetry metrics",
                    exc_info=True,
                )


def _emit_metrics(telemetry: TelemetryData, operation_type: str) -> None:
    """
    Emit Prometheus metrics for a telemetry record.

    Uses shared/observability/metrics singleton.
    Non-blocking: all exceptions caught by caller.
    """
    try:
        from app.shared.observability.metrics import metrics

        # Increment call counter
        metrics.ai_provider_calls_total.labels(
            provider=telemetry.provider,
            model=telemetry.model_id,
        ).inc()

        # Record latency
        latency_seconds = telemetry.latency_ms / 1000.0
        metrics.ai_provider_latency_seconds.labels(
            provider=telemetry.provider,
        ).observe(latency_seconds)

        # Record tokens (on success)
        if telemetry.success:
            metrics.ai_provider_tokens_total.labels(
                provider=telemetry.provider,
                type="prompt",
            ).inc(telemetry.prompt_tokens)

            metrics.ai_provider_tokens_total.labels(
                provider=telemetry.provider,
                type="completion",
            ).inc(telemetry.completion_tokens)

            # Record cost
            if telemetry.estimated_cost_usd is not None:
                metrics.ai_provider_cost_usd_total.labels(
                    provider=telemetry.provider,
                ).inc(telemetry.estimated_cost_usd)

    except Exception:
        _logger.debug("Failed to emit Prometheus metrics", exc_info=True)


def _emit_structured_log(telemetry: TelemetryData, operation_type: str) -> None:
    """
    Emit structured telemetry event log.

    Uses standard logging (JSON-formatted by shared/observability).
    Non-blocking: all exceptions caught by caller.
    """
    try:
        log_data = {
            "event": "ai.telemetry.recorded",
            "operation_type": operation_type,
            "model_id": telemetry.model_id,
            "provider": telemetry.provider,
            "tokens": {
                "prompt": telemetry.prompt_tokens,
                "completion": telemetry.completion_tokens,
                "total": telemetry.total_tokens,
            },
            "latency_ms": telemetry.latency_ms,
            "success": telemetry.success,
            "deterministic": telemetry.deterministic,
        }

        if telemetry.estimated_cost_usd is not None:
            log_data["estimated_cost_usd"] = telemetry.estimated_cost_usd

        if telemetry.organization_id is not None:
            log_data["organization_id"] = telemetry.organization_id

        if telemetry.error_type is not None:
            log_data["error_type"] = telemetry.error_type

        if telemetry.retry_count > 0:
            log_data["retry_count"] = telemetry.retry_count

        _logger.info("AI telemetry: %s", operation_type, extra={"metadata": log_data})

    except Exception:
        _logger.debug("Failed to emit structured telemetry log", exc_info=True)
