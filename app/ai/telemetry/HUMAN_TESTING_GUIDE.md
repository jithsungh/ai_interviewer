# AI Telemetry Layer — Human Testing Guide

## Module Overview

The `ai/telemetry` module provides observability and cost tracking for all AI operations.
It is a **pure programmatic module** — no REST endpoints, no owned database tables.

Telemetry data is consumed by calling modules (e.g., `ai/llm` providers) and persisted
in their own tables as JSON metadata fields.

---

## Components

| Component | File | Purpose |
|---|---|---|
| `TelemetryTracker` | `app/ai/telemetry/tracker.py` | Span-based telemetry tracking |
| `TelemetrySpan` | `app/ai/telemetry/tracker.py` | Records one AI operation's metrics |
| `CostEstimator` | `app/ai/telemetry/cost.py` | Model pricing lookup + cost calculation |
| `classify_error` | `app/ai/telemetry/errors.py` | Exception → error type classification |
| `MetricsAggregator` | `app/ai/telemetry/aggregation.py` | Aggregate telemetry for reporting |
| `OperationType` | `app/ai/telemetry/contracts.py` | Enum of AI operation types |
| `AIErrorType` | `app/ai/telemetry/contracts.py` | Enum of classified error types |
| `CostEstimate` | `app/ai/telemetry/contracts.py` | Cost estimation result (frozen) |
| `AggregatedMetrics` | `app/ai/telemetry/contracts.py` | Aggregated metrics summary |
| `OrganizationQuota` | `app/ai/telemetry/contracts.py` | Org-level quota tracking |

---

## No REST Endpoints

This module exposes **no HTTP endpoints**. It is used programmatically:

```python
from app.ai.telemetry import TelemetryTracker, CostEstimator, classify_error
```

---

## Testing via Python REPL

### 1. Basic Telemetry Tracking

```bash
cd /home/jithsungh/projects/ai_interviewer
TESTING=1 .venv/bin/python
```

```python
from app.ai.telemetry import TelemetryTracker

tracker = TelemetryTracker()

with tracker.track("question_generation") as span:
    span.set_input(
        prompt_tokens=500,
        model_id="llama-3.3-70b-versatile",
        provider="groq",
        organization_id=1,
    )
    # simulate AI operation...
    span.set_output(completion_tokens=200, success=True)

telemetry = span.finalize()
print(f"Model: {telemetry.model_id}")
print(f"Tokens: {telemetry.total_tokens}")
print(f"Latency: {telemetry.latency_ms}ms")
print(f"Cost: ${telemetry.estimated_cost_usd}")
print(f"Success: {telemetry.success}")
```

Expected output:
```
Model: llama-3.3-70b-versatile
Tokens: 700
Latency: 0ms  (near-zero since no real AI call)
Cost: $0.000453
Success: True
```

### 2. Error Telemetry

```python
from app.ai.telemetry import TelemetryTracker

tracker = TelemetryTracker()

try:
    with tracker.track("evaluation") as span:
        span.set_input(prompt_tokens=100, model_id="gpt-4", provider="openai")
        raise TimeoutError("Provider timeout")
except TimeoutError:
    pass

telemetry = span.finalize()
print(f"Success: {telemetry.success}")  # False
print(f"Latency: {telemetry.latency_ms}ms")
print(f"Tokens recorded: {telemetry.prompt_tokens}")
```

### 3. Cost Estimation

```python
from app.ai.telemetry import CostEstimator

estimator = CostEstimator()

# Known model
cost = estimator.estimate_cost("gpt-4", prompt_tokens=1000, completion_tokens=500)
print(f"GPT-4 cost: ${cost.total_cost_usd:.4f}")
# Expected: $0.0600

# Unknown model
cost = estimator.estimate_cost("unknown-model", 1000, 500)
print(f"Unknown: {cost}")
# Expected: None

# List known models
print(estimator.get_known_models())
```

### 4. Error Classification

```python
from app.ai.telemetry import classify_error
from app.ai.llm.errors import LLMTimeoutError, LLMRateLimitError

print(classify_error(LLMTimeoutError("openai", 30)))       # "timeout"
print(classify_error(LLMRateLimitError("openai")))          # "rate_limit"
print(classify_error(TimeoutError("stdlib timeout")))       # "timeout"
print(classify_error(Exception("unknown")))                 # "provider_error"
```

### 5. Metrics Aggregation

```python
from app.ai.telemetry import MetricsAggregator
from app.ai.llm.contracts import TelemetryData

records = [
    TelemetryData(
        model_id="gpt-4", provider="openai",
        prompt_tokens=100, completion_tokens=50, total_tokens=150,
        latency_ms=lat, success=(lat < 5000),
        error_type=("timeout" if lat >= 5000 else None),
        estimated_cost_usd=0.01,
    )
    for lat in [500, 1000, 2000, 3000, 5000, 10000]
]

agg = MetricsAggregator()
result = agg.aggregate_hourly(records)

print(f"Total requests: {result.total_requests}")
print(f"Successful: {result.successful_requests}")
print(f"Failed: {result.failed_requests}")
print(f"P50 latency: {result.p50_latency_ms}ms")
print(f"P95 latency: {result.p95_latency_ms}ms")
print(f"Total cost: ${result.total_cost_usd}")
print(f"Errors: {result.errors_by_type}")
```

---

## Running Tests

### Unit Tests (fast, no external dependencies)

```bash
cd /home/jithsungh/projects/ai_interviewer
TESTING=1 .venv/bin/pytest tests/unit/ai/telemetry/ -v
```

Expected: **102 tests pass**

### Integration Tests (Prometheus metrics)

```bash
TESTING=1 .venv/bin/pytest tests/integration/ai/telemetry/ -v
```

Expected: **7 tests pass**

### All Tests Together

```bash
TESTING=1 .venv/bin/pytest tests/unit/ai/telemetry/ tests/integration/ai/telemetry/ -v
```

Expected: **109 tests pass, 0 failures**

### With Coverage

```bash
TESTING=1 .venv/bin/pytest tests/unit/ai/telemetry/ tests/integration/ai/telemetry/ \
    --cov=app.ai.telemetry --cov-report=term-missing -v
```

---

## Test Categories

| Test File | Count | What It Tests |
|---|---|---|
| `test_tracker.py` | 28 | Span lifecycle, field recording, latency, cost, edge cases |
| `test_cost_estimation.py` | 18 | All pricing models, edge cases, custom pricing |
| `test_error_classification.py` | 16 | LLM errors, shared errors, stdlib errors, fallbacks |
| `test_non_blocking.py` | 10 | Failure isolation, overhead <5ms, concurrency |
| `test_aggregation.py` | 16 | Counts, costs, percentiles, filtering, validation |
| `test_metrics_export.py` | 7 | Prometheus counter/histogram integration |

---

## Failure Cases to Verify

| Scenario | Expected Behavior |
|---|---|
| Metrics backend down | Telemetry still recorded, error logged silently |
| Unknown model pricing | `estimated_cost_usd = None` |
| AI operation raises exception | Partial telemetry recorded (prompt_tokens, latency) |
| Negative token count | Clamped to 0 |
| Cost estimator throws | `estimated_cost_usd = None`, operation continues |
| Concurrent spans | All independent, no contention |
| `classify_error` with weird exception | Returns "provider_error", never raises |

---

## Schema Changes

**None.** This module owns no database tables. Telemetry data is returned to callers
as `TelemetryData` objects (from `app.ai.llm.contracts`), which callers persist in
their own tables' JSON metadata fields.

---

## Migration Instructions

**No migrations required.**

---

## Architecture Notes

### Dependencies (what this module uses)
- `app.ai.llm.contracts.TelemetryData` — reused as the per-call telemetry DTO
- `app.shared.observability.metrics.metrics` — Prometheus metrics singleton
- `app.ai.llm.errors.*` — LLM error hierarchy (for `classify_error`)
- `app.shared.errors.*` — shared error hierarchy (for `classify_error`)

### Dependents (what uses this module)
- `app.ai.llm.providers.*` — providers can use `TelemetryTracker` for span-based tracking
- Reporting/admin modules — can use `MetricsAggregator` for cost/usage reporting
- Any module making AI calls — uses `CostEstimator` for cost estimation

### Non-Blocking Guarantee
All telemetry recording is wrapped in try/except. Failures are logged at DEBUG level
and never propagate to calling code. This is enforced in:
- `TelemetryTracker.track()` — catches all exceptions in the `finally` block
- `_emit_metrics()` — catches all Prometheus errors internally
- `_emit_structured_log()` — catches all logging errors internally
- `TelemetrySpan.finalize()` — catches cost estimation errors
