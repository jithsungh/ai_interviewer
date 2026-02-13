# AI Telemetry Layer Testing Guide

## Testing Philosophy

Telemetry testing focuses on:

1. **Non-blocking guarantee** (telemetry never crashes AI operations)
2. **Accuracy** (token counts, latency, cost calculations)
3. **Resilience** (handles backend failures gracefully)
4. **Performance** (minimal overhead <5ms)

Most telemetry tests are **unit tests** with mocked backends.

---

## Test Structure

```
tests/
├── unit/
│   └── ai/
│       └── telemetry/
│           ├── test_tracker.py
│           ├── test_cost_estimation.py
│           ├── test_error_classification.py
│           ├── test_non_blocking.py
│           └── test_aggregation.py
├── integration/
│   └── ai/
│       └── telemetry/
│           ├── test_metrics_export.py
│           └── test_metrics_backend.py
└── performance/
    └── ai/
        └── telemetry/
            └── test_overhead.py
```

---

## 1. Unit Tests (Core Logic)

### Telemetry Tracker Tests

```python
# tests/unit/ai/telemetry/test_tracker.py

import time
import pytest
from app.ai.telemetry.tracker import TelemetryTracker, TelemetrySpan

def test_basic_span_recording():
    \"\"\"Span records all required fields\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test_operation") as span:
        span.set_input(prompt_tokens=100, model_id="gpt-4", provider="openai")
        time.sleep(0.01)  # Simulate work
        span.set_output(completion_tokens=50, success=True)

    telemetry = span.finalize()

    assert telemetry.operation_type == "test_operation"
    assert telemetry.prompt_tokens == 100
    assert telemetry.completion_tokens == 50
    assert telemetry.total_tokens == 150
    assert telemetry.model_id == "gpt-4"
    assert telemetry.provider == "openai"
    assert telemetry.success is True
    assert telemetry.latency_ms >= 10  # At least 10ms

def test_span_records_failure():
    \"\"\"Span records error information on failure\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test_operation") as span:
        span.set_input(prompt_tokens=100, model_id="gpt-4", provider="openai")
        span.set_error(error_type="timeout")

    telemetry = span.finalize()

    assert telemetry.success is False
    assert telemetry.error_type == "timeout"
    assert telemetry.prompt_tokens == 100
    assert telemetry.completion_tokens == 0  # No completion on error

def test_total_tokens_computed():
    \"\"\"Total tokens always computed, never user-provided\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test") as span:
        span.set_input(prompt_tokens=100)
        span.set_output(completion_tokens=50, success=True)

    telemetry = span.finalize()
    assert telemetry.total_tokens == 150  # Computed

def test_latency_always_positive():
    \"\"\"Latency must be >= 0\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test") as span:
        span.set_input(prompt_tokens=10)
        span.set_output(completion_tokens=5, success=True)

    telemetry = span.finalize()
    assert telemetry.latency_ms >= 0

def test_retry_count_tracking():
    \"\"\"Retry count recorded correctly\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test") as span:
        span.set_input(prompt_tokens=10)
        span.increment_retry()
        span.increment_retry()
        span.set_output(completion_tokens=5, success=True)

    telemetry = span.finalize()
    assert telemetry.retry_count == 2
```

### Cost Estimation Tests

```python
# tests/unit/ai/telemetry/test_cost_estimation.py

from app.ai.telemetry.cost import CostEstimator

def test_gpt4_cost_calculation():
    \"\"\"GPT-4 cost calculated correctly\"\"\"
    estimator = CostEstimator()

    cost = estimator.estimate_cost(
        model_id="gpt-4",
        prompt_tokens=1000,
        completion_tokens=500
    )

    # GPT-4: $0.03/1K prompt, $0.06/1K completion
    expected = (1000 * 0.03 / 1000) + (500 * 0.06 / 1000)
    assert abs(cost.total_cost_usd - expected) < 0.0001
    assert cost.model_id == "gpt-4"

def test_gpt35_turbo_cost_calculation():
    \"\"\"GPT-3.5-turbo cost calculated correctly\"\"\"
    estimator = CostEstimator()

    cost = estimator.estimate_cost(
        model_id="gpt-3.5-turbo",
        prompt_tokens=2000,
        completion_tokens=1000
    )

    # GPT-3.5: $0.0005/1K prompt, $0.0015/1K completion
    expected = (2000 * 0.0005 / 1000) + (1000 * 0.0015 / 1000)
    assert abs(cost.total_cost_usd - expected) < 0.0001

def test_claude_cost_calculation():
    \"\"\"Claude 3 pricing differs by model\"\"\"
    estimator = CostEstimator()

    opus_cost = estimator.estimate_cost("claude-3-opus", 1000, 500)
    sonnet_cost = estimator.estimate_cost("claude-3-sonnet", 1000, 500)
    haiku_cost = estimator.estimate_cost("claude-3-haiku", 1000, 500)

    # Opus > Sonnet > Haiku
    assert opus_cost.total_cost_usd > sonnet_cost.total_cost_usd
    assert sonnet_cost.total_cost_usd > haiku_cost.total_cost_usd

def test_unknown_model_returns_none():
    \"\"\"Unknown models return None for cost\"\"\"
    estimator = CostEstimator()

    cost = estimator.estimate_cost("unknown-model", 1000, 500)
    assert cost is None

def test_zero_tokens_zero_cost():
    \"\"\"Zero tokens = zero cost\"\"\"
    estimator = CostEstimator()

    cost = estimator.estimate_cost("gpt-4", 0, 0)
    assert cost.total_cost_usd == 0.0

def test_embedding_cost_no_completion():
    \"\"\"Embedding models have no completion cost\"\"\"
    estimator = CostEstimator()

    cost = estimator.estimate_cost("text-embedding-ada-002", 1000, 0)
    assert cost.total_cost_usd > 0
    assert cost.completion_cost_per_1k == 0.0
```

### Error Classification Tests

```python
# tests/unit/ai/telemetry/test_error_classification.py

from app.ai.telemetry.errors import classify_error
from app.ai.llm.errors import TimeoutError, RateLimitError, AuthenticationError

def test_timeout_classified():
    \"\"\"Timeout errors classified correctly\"\"\"
    error = TimeoutError("Request timed out")
    classification = classify_error(error)
    assert classification == "timeout"

def test_rate_limit_classified():
    \"\"\"Rate limit errors classified correctly\"\"\"
    error = RateLimitError("Rate limit exceeded")
    classification = classify_error(error)
    assert classification == "rate_limit"

def test_authentication_classified():
    \"\"\"Auth errors classified correctly\"\"\"
    error = AuthenticationError("Invalid API key")
    classification = classify_error(error)
    assert classification == "authentication"

def test_unknown_error_classified():
    \"\"\"Unknown errors classified as provider_error\"\"\"
    error = Exception("Something went wrong")
    classification = classify_error(error)
    assert classification == "provider_error"
```

### Non-Blocking Tests

```python
# tests/unit/ai/telemetry/test_non_blocking.py

import pytest
from unittest.mock import patch, Mock
from app.ai.telemetry.tracker import TelemetryTracker

def test_telemetry_failure_does_not_propagate():
    \"\"\"Telemetry recording failure does not crash operation\"\"\"
    tracker = TelemetryTracker()

    with patch('app.ai.telemetry.tracker.export_metrics', side_effect=Exception("Backend down")):
        # Should not raise exception
        with tracker.track("test") as span:
            span.set_input(prompt_tokens=10)
            span.set_output(completion_tokens=5, success=True)

        telemetry = span.finalize()
        assert telemetry is not None  # Still returns telemetry data

def test_metrics_backend_unavailable():
    \"\"\"Metrics export failure logged, does not block\"\"\"
    tracker = TelemetryTracker()

    with patch('app.ai.telemetry.export.export_to_prometheus', side_effect=ConnectionError):
        with tracker.track("test") as span:
            span.set_input(prompt_tokens=10)
            span.set_output(completion_tokens=5, success=True)

        # Should complete without raising
        telemetry = span.finalize()
        assert telemetry.success is True

@pytest.mark.timeout(1)
def test_telemetry_recording_is_fast():
    \"\"\"Telemetry adds minimal overhead (<5ms)\"\"\"
    import time
    tracker = TelemetryTracker()

    start = time.perf_counter()

    with tracker.track("test") as span:
        span.set_input(prompt_tokens=10)
        span.set_output(completion_tokens=5, success=True)

    telemetry = span.finalize()

    overhead = (time.perf_counter() - start) * 1000  # Convert to ms
    assert overhead < 5  # Less than 5ms overhead
```

### Aggregation Tests

```python
# tests/unit/ai/telemetry/test_aggregation.py

from datetime import datetime, timedelta
from app.ai.telemetry.aggregation import MetricsAggregator

def test_hourly_aggregation():
    \"\"\"Hourly metrics aggregated correctly\"\"\"
    aggregator = MetricsAggregator()

    # Mock telemetry data points
    telemetry_data = [
        TelemetryData(
            operation_type="evaluation",
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=3000,
            success=True,
            timestamp=datetime.now()
        )
        for _ in range(100)
    ]

    aggregated = aggregator.aggregate_hourly(telemetry_data)

    assert aggregated.total_requests == 100
    assert aggregated.successful_requests == 100
    assert aggregated.failed_requests == 0
    assert aggregated.total_tokens == 15000  # 150 * 100

def test_latency_percentiles():
    \"\"\"Latency percentiles computed correctly\"\"\"
    aggregator = MetricsAggregator()

    latencies = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000]
    telemetry_data = [\n        TelemetryData(\n            latency_ms=lat,\n            success=True,\n            # ... other required fields\n        )\n        for lat in latencies\n    ]

    aggregated = aggregator.aggregate_hourly(telemetry_data)

    assert aggregated.p50_latency_ms == 500
    assert aggregated.p95_latency_ms == 950

def test_cost_aggregation():
    \"\"\"Total cost aggregated correctly\"\"\"
    aggregator = MetricsAggregator()

    telemetry_data = [\n        TelemetryData(\n            model_id=\"gpt-4\",\n            prompt_tokens=1000,\n            completion_tokens=500,\n            estimated_cost_usd=0.045,\n            success=True,\n            # ... other fields\n        )\n        for _ in range(100)\n    ]

    aggregated = aggregator.aggregate_hourly(telemetry_data)

    assert abs(aggregated.total_cost_usd - 4.5) < 0.01  # 0.045 * 100
```

---

## 2. Integration Tests (Real Backends)

### Metrics Export Tests

```python
# tests/integration/ai/telemetry/test_metrics_export.py

import pytest
from app.ai.telemetry.export import export_to_prometheus
from app.ai.telemetry.tracker import TelemetryData

@pytest.mark.integration
def test_export_to_prometheus():
    \"\"\"Export metrics to Prometheus pushgateway\"\"\"
    telemetry = TelemetryData(
        operation_type="evaluation",
        model_id="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_tokens=1500,
        latency_ms=3000,
        success=True,
        estimated_cost_usd=0.045
    )

    # Should not raise exception
    export_to_prometheus(telemetry)

@pytest.mark.integration
def test_metrics_queryable():
    \"\"\"Exported metrics can be queried\"\"\"
    from prometheus_api_client import PrometheusConnect

    prom = PrometheusConnect(url="http://localhost:9090")

    # Query recent AI requests
    result = prom.custom_query(
        query='ai_requests_total{model="gpt-4"}'
    )

    assert len(result) > 0
```

---

## 3. Performance Tests

```python
# tests/performance/ai/telemetry/test_overhead.py

import time
import pytest
from app.ai.telemetry.tracker import TelemetryTracker

@pytest.mark.performance
def test_telemetry_overhead_minimal():
    \"\"\"Telemetry adds <5ms overhead to operations\"\"\"
    tracker = TelemetryTracker()

    measurements = []

    for _ in range(1000):
        start = time.perf_counter()

        with tracker.track("test") as span:
            span.set_input(prompt_tokens=10)
            span.set_output(completion_tokens=5, success=True)

        span.finalize()

        overhead = (time.perf_counter() - start) * 1000
        measurements.append(overhead)

    avg_overhead = sum(measurements) / len(measurements)
    p95_overhead = sorted(measurements)[949]  # 95th percentile

    assert avg_overhead < 2, f"Average overhead {avg_overhead}ms exceeds 2ms"
    assert p95_overhead < 5, f"P95 overhead {p95_overhead}ms exceeds 5ms"

@pytest.mark.performance
def test_concurrent_telemetry_no_contention():
    \"\"\"Concurrent telemetry recording has no contention\"\"\"
    from concurrent.futures import ThreadPoolExecutor
    import time

    tracker = TelemetryTracker()

    def record_telemetry():
        with tracker.track("test") as span:
            span.set_input(prompt_tokens=10)
            span.set_output(completion_tokens=5, success=True)
        return span.finalize()

    start = time.time()

    with ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(record_telemetry) for _ in range(1000)]
        results = [f.result() for f in futures]

    duration = time.time() - start

    assert len(results) == 1000
    assert duration < 5  # Should complete in <5s even with 1000 concurrent ops
```

---

## 4. Edge Case Tests

```python
# tests/unit/ai/telemetry/test_edge_cases.py

def test_zero_tokens():
    \"\"\"Handle zero token counts gracefully\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test") as span:
        span.set_input(prompt_tokens=0)
        span.set_output(completion_tokens=0, success=True)

    telemetry = span.finalize()
    assert telemetry.total_tokens == 0
    assert telemetry.estimated_cost_usd == 0.0

def test_very_high_token_count():
    \"\"\"Handle very high token counts (100K+)\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test") as span:
        span.set_input(prompt_tokens=100000)
        span.set_output(completion_tokens=50000, success=True)

    telemetry = span.finalize()
    assert telemetry.total_tokens == 150000

def test_very_high_latency():
    \"\"\"Handle very high latencies (multi-minute)\"\"\"
    tracker = TelemetryTracker()

    with tracker.track("test") as span:
        span.set_input(prompt_tokens=10)
        time.sleep(2)  # Simulate 2 second operation
        span.set_output(completion_tokens=5, success=True)

    telemetry = span.finalize()
    assert telemetry.latency_ms >= 2000

def test_partial_telemetry_on_exception():
    \"\"\"Partial telemetry recorded even if span interrupted\"\"\"
    tracker = TelemetryTracker()

    try:
        with tracker.track("test") as span:
            span.set_input(prompt_tokens=100)
            raise Exception("Operation failed")
    except Exception:
        pass

    # Span should have partial data
    telemetry = span.finalize()
    assert telemetry.prompt_tokens == 100
    assert telemetry.completion_tokens == 0
```

---

## Test Coverage Requirements

- **Unit Tests:** >90% coverage
- **Integration Tests:** Metrics export to all backends
- **Performance Tests:** Verify <5ms overhead
- **Edge Cases:** All telemetry edge cases

---

## Running Tests

```bash
# Unit tests (fast)
pytest tests/unit/ai/telemetry/ -v

# Integration tests (requires metrics backend)
pytest tests/integration/ai/telemetry/ -v --integration

# Performance tests
pytest tests/performance/ai/telemetry/ -v --performance

# Coverage
pytest tests/ai/telemetry/ --cov=app/ai/telemetry --cov-report=html
```

---

## Monitoring Test Quality

### Required Test Scenarios

- [ ] Successful operation telemetry
- [ ] Failed operation telemetry (multiple error types)
- [ ] Zero token telemetry
- [ ] High token telemetry (100K+)
- [ ] Multiple retries telemetry
- [ ] Cost estimation for all known models
- [ ] Metrics export to Prometheus
- [ ] Metrics export failure (non-blocking)
- [ ] Concurrent telemetry recording (1000+ ops)
- [ ] Telemetry overhead <5ms

---

**End of AI Telemetry Testing Guide**
