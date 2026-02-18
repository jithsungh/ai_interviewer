# AI Telemetry Layer Requirements

## 1. Purpose

The telemetry layer provides **observability and cost tracking** for all AI operations.

**Core Responsibilities:**

- Track token usage (prompt + completion tokens)
- Measure latency (end-to-end and provider-specific)
- Record model ID and provider for each call
- Count retry attempts
- Classify and track errors
- Estimate costs based on model pricing
- Aggregate metrics for reporting

**Design Principle:** Telemetry must be non-blocking and MUST be recorded even on failure.

---

## 2. Owned Tables

**None** - Telemetry layer writes to JSON fields in consuming modules' tables, not separate tables.

### Write Targets (JSON Fields)

- `interview_exchanges.content_metadata` - AI telemetry for questions/responses
- `evaluations.metadata` - AI telemetry for scoring
- Audit logs - AI operation tracking
- Application metrics system (Prometheus, CloudWatch, etc.)

**Critical:** Telemetry layer returns data structures; calling modules persist them.

---

## 3. Input Constraints

### Telemetry Span Context

Every AI operation wrapped in telemetry span:

```python
with telemetry_tracker.track(operation_type: str) as span:
    # Record before call
    span.set_input(prompt_tokens: int, prompt_type: str)

    # Perform AI operation
    result = provider.generate_text(...)

    # Record after call
    span.set_output(
        completion_tokens: int,
        model_id: str,
        success: bool
    )
```

### Required Fields

- `operation_type` (required): `question_generation` | `evaluation` | `resume_parsing` | `jd_parsing` | `report_generation` | `embedding` | `transcription`
- `prompt_tokens` (required): Integer >= 0
- `completion_tokens` (required): Integer >= 0
- `model_id` (required): String, provider-specific model identifier
- `provider` (required): `groq` | `gemini` | `openai` | `anthropic` | `local`
- `success` (required): Boolean

### Optional Fields

- `temperature`: Float, 0.0-2.0
- `max_tokens`: Integer
- `deterministic`: Boolean
- `retry_count`: Integer, 0-N
- `error_type`: String (if success=False)
- `prompt_version`: Integer (from prompt_templates)
- `organization_id`: Integer (for cost allocation)

---

## 4. Output Guarantees

### TelemetryData Structure

```python
@dataclass
class TelemetryData:
    # Core metrics
    operation_type: str
    model_id: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int           # Computed: prompt + completion
    latency_ms: int             # Wall time from span start to end

    # Success/failure
    success: bool
    error_type: Optional[str]   # timeout | rate_limit | schema_validation | provider_error
    retry_count: int

    # Context
    timestamp: datetime
    deterministic: bool
    temperature: Optional[float]
    max_tokens: Optional[int]
    prompt_version: Optional[int]
    organization_id: Optional[int]

    # Cost estimation
    estimated_cost_usd: Optional[float]
```

### CostEstimate Structure

```python
@dataclass
class CostEstimate:
    model_id: str
    prompt_tokens: int
    completion_tokens: int
    prompt_cost_per_1k: float
    completion_cost_per_1k: float
    total_cost_usd: float
    currency: str = "USD"
```

### AggregatedMetrics Structure (for reporting)

```python
@dataclass
class AggregatedMetrics:
    time_period: str            # "hour" | "day" | "month"
    organization_id: Optional[int]
    model_id: Optional[str]     # None = all models

    # Aggregated values
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens: int
    total_cost_usd: float

    # Latency percentiles
    p50_latency_ms: int
    p95_latency_ms: int
    p99_latency_ms: int

    # Error breakdown
    errors_by_type: Dict[str, int]  # {timeout: 5, rate_limit: 2, ...}
```

### Performance Guarantees

- Telemetry collection overhead: <5ms per operation
- Telemetry recording MUST NOT block AI operation
- Failed telemetry MUST NOT fail AI operation (log error, continue)
- Metrics aggregation: eventual consistency acceptable (up to 5 minutes delay)

---

## 5. Invariants

### Non-Blocking Invariant

```
Telemetry failure MUST NOT propagate to calling code
AI operation failure MUST still record partial telemetry
```

**Enforcement:** Try/except around all telemetry recording, log errors separately.

### Total Tokens Invariant

```
total_tokens = prompt_tokens + completion_tokens
Always computed, never user-provided
```

**Enforcement:** Computed property on TelemetryData.

### Latency Measurement Invariant

```
Latency measured from span start to span end (wall time)
Measured in milliseconds, rounded to integer
Negative latency impossible (sanity check)
```

**Enforcement:** Use high-resolution timer (`time.perf_counter()`), validate >= 0.

### Cost Estimation Invariant

```
IF model_id has known pricing:
    estimated_cost_usd = (prompt_tokens * prompt_rate) + (completion_tokens * completion_rate)
ELSE:
    estimated_cost_usd = None
```

**Enforcement:** Pricing table lookup, fallback to None if unknown.

---

## 6. Forbidden Behaviors

### Blocking Operations

- SHALL NOT block AI operation waiting for telemetry write
- SHALL NOT retry telemetry writes synchronously
- SHALL NOT raise exceptions from telemetry layer to calling code

### Data Integrity

- SHALL NOT modify token counts (must be provider-reported values)
- SHALL NOT average latencies within a span (record actual wall time)
- SHALL NOT truncate or round cost estimates incorrectly

### Privacy Violations

- SHALL NOT log full prompts or responses (PII risk)
- SHALL NOT store API keys in telemetry
- SHALL NOT expose cross-tenant metrics (isolation required)

### Performance Degradation

- SHALL NOT perform database queries in span recording (async write)
- SHALL NOT aggregate metrics in critical path
- SHALL NOT hold locks during telemetry recording

---

## 7. Dependent Modules

### Dependencies (Inbound)

- `shared/observability` - Logging and tracing infrastructure
- `shared/metrics` - Prometheus/CloudWatch client
- Pricing configuration (database or config file)

### Dependents (Outbound)

- `ai/llm` - Records telemetry for every provider call
- Parent `ai` module - Returns telemetry to calling modules

### External Systems

- **Metrics Backend** (Prometheus, CloudWatch, Datadog)
- **Logging Backend** (Elasticsearch, CloudWatch Logs)
- **Cost Tracking Database** (for organization-level quotas)

---

## 8. Event Contracts Emitted

### Real-Time Metrics (Prometheus Format)

```
# Counter: Total AI requests
ai_requests_total{operation_type="evaluation", model="gpt-4", provider="openai", org_id="45", status="success"} 1250

# Counter: Total tokens consumed
ai_tokens_total{model="gpt-4", token_type="prompt", org_id="45"} 50000
ai_tokens_total{model="gpt-4", token_type="completion", org_id="45"} 15000

# Histogram: Request latency
ai_request_duration_milliseconds{operation_type="evaluation"} 3420

# Counter: Total cost
ai_cost_usd_total{org_id="45", model="gpt-4"} 12.45

# Counter: Errors
ai_errors_total{error_type="timeout", model="gpt-4"} 5
```

### Telemetry Events (Structured Logs)

```json
{
  "event": "ai.telemetry.recorded",
  "operation_type": "evaluation",
  "model_id": "gpt-4",
  "provider": "openai",
  "organization_id": 45,
  "tokens": {
    "prompt": 1250,
    "completion": 380,
    "total": 1630
  },
  "latency_ms": 3420,
  "success": true,
  "deterministic": true,
  "estimated_cost_usd": 0.0489,
  "timestamp": "2026-02-13T10:30:00Z"
}
```

```json
{
  "event": "ai.telemetry.error",
  "error": "Failed to record telemetry",
  "operation_type": "question_generation",
  "reason": "Metrics backend unavailable",
  "timestamp": "2026-02-13T10:35:00Z"
}
```

---

## 9. Acceptance Criteria

### Telemetry Collection

- [ ] Token usage recorded for every AI call (success or failure)
- [ ] Latency measured with <1ms precision
- [ ] Model ID captured from provider response
- [ ] Retry count tracked across retries
- [ ] Error type classified correctly (timeout, rate_limit, etc.)
- [ ] Telemetry recorded even when AI call fails

### Cost Estimation

- [ ] Known models have accurate pricing (OpenAI GPT-4, GPT-3.5, etc.)
- [ ] Cost calculated correctly: (prompt*tokens * rate) + (completion*tokens * rate)
- [ ] Unknown models return None for cost (no estimation fallback)
- [ ] Cost rounded to 4 decimal places (USD cents precision)

### Metrics Export

- [ ] Metrics exported to Prometheus/CloudWatch
- [ ] Metrics tagged with: model, provider, org_id, operation_type, status
- [ ] Latency histogram buckets appropriate for AI calls (0.1s, 1s, 5s, 10s, 30s, 60s)
- [ ] Metrics scrape interval: 15 seconds (configurable)

### Aggregation

- [ ] Hourly aggregates computed for cost tracking
- [ ] Daily aggregates computed for reporting
- [ ] Organization-level quotas checked against aggregates
- [ ] Aggregation runs async (not in request path)

### Non-Blocking Guarantee

- [ ] Telemetry failure logged, does not crash AI operation
- [ ] Telemetry recording <5ms overhead
- [ ] Async write to metrics backend
- [ ] No locks held during telemetry recording

### Privacy & Security

- [ ] Prompt/response text NOT logged in telemetry
- [ ] API keys NOT stored in telemetry
- [ ] Cross-tenant metrics isolated
- [ ] PII-free telemetry structure

---

## 10. Testing Guide

See [TESTING.md](TESTING.md) for comprehensive testing strategies.

**Key Testing Requirements:**

- Telemetry collection with mocked AI calls
- Cost estimation accuracy
- Non-blocking behavior verification
- Metrics export validation

---

## 11. Edge Cases

### Token Counting Edge Cases

- **Provider reports 0 tokens:** Accept (possible for cached responses)
- **Prompt tokens > 100K:** Accept, flag as unusual
- **Completion tokens = 0:** Accept (timeout mid-response, empty response)
- **Token count mismatch:** Prefer provider-reported over local estimate

### Latency Edge Cases

- **Latency > 5 minutes:** Flag as anomaly, record actual value
- **Latency < 1ms:** Sanity check failed, log warning
- **Clock skew:** Use monotonic clock (`time.perf_counter`), not wall clock

### Cost Estimation Edge Cases

- **Model pricing changes:** Use pricing effective at request time (version pricing table)
- **Promotional credits:** Not tracked in telemetry (billing concern)
- **Negative cost:** Impossible, sanity check

### Error Classification Edge Cases

- **Multiple error types:** Record first/root error type
- **Unknown error:** Classify as `provider_error` with details
- **Partial success (streaming):** Count as success with truncation flag

### Metrics Backend Failures

- **Backend unavailable:** Buffer metrics in-memory (max 1000 entries), flush when available
- **Buffer overflow:** Drop oldest metrics, log warning
- **Persistent failure:** Degrade gracefully, log to file

---

## 12. Concurrency Concerns

### Thread-Safe Counters

- Token counters MUST be thread-safe (atomic increments)
- Use `threading.Lock` or atomic types (`multiprocessing.Value`)

### Metrics Buffering

- In-memory buffer for async writes
- Buffer MUST be thread-safe (queue or locked list)
- Periodic flush (every 5 seconds or 100 events)

### Aggregation Queries

- Aggregation runs in background thread
- No blocking of AI requests
- Eventual consistency acceptable (lag up to 5 minutes)

### Clock Synchronization

- Use monotonic clock for latency (not affected by NTP adjustments)
- Timestamp uses wall clock (UTC) for correlation

---

## 13. Cost Tracking Configuration

### Model Pricing Table

```python
# Pricing per 1K tokens (USD)
MODEL_PRICING = {
    # Groq Models (Development - very cost effective)
    "llama-3.3-70b-versatile": {
        "prompt": 0.00059,
        "completion": 0.00079
    },
    "llama-3.1-70b-versatile": {
        "prompt": 0.00059,
        "completion": 0.00079
    },
    "llama-3.1-8b-instant": {
        "prompt": 0.00005,
        "completion": 0.00008
    },
    "mixtral-8x7b-32768": {
        "prompt": 0.00024,
        "completion": 0.00024
    },
    "gemma2-9b-it": {
        "prompt": 0.00020,
        "completion": 0.00020
    },

    # Gemini Models (Development - cost effective)
    "gemini-2.0-flash-exp": {
        "prompt": 0.0,  # Free during preview
        "completion": 0.0
    },
    "gemini-1.5-pro": {
        "prompt": 0.00125,
        "completion": 0.005
    },
    "gemini-1.5-flash": {
        "prompt": 0.000075,
        "completion": 0.0003
    },
    "gemini-1.5-flash-8b": {
        "prompt": 0.0000375,
        "completion": 0.00015
    },
    "text-embedding-004": {
        "prompt": 0.00001,
        "completion": 0.0
    },

    # Self-Hosted Embedding (Development & Production)
    "all-mpnet-base-v2": {
        "prompt": 0.0,  # Self-hosted, no API cost
        "completion": 0.0
    },

    # OpenAI Models (Production)
    "gpt-4o": {
        "prompt": 0.0025,
        "completion": 0.01
    },
    "gpt-4": {
        "prompt": 0.03,
        "completion": 0.06
    },
    "gpt-4-turbo": {
        "prompt": 0.01,
        "completion": 0.03
    },
    "gpt-3.5-turbo": {
        "prompt": 0.0005,
        "completion": 0.0015
    },
    "text-embedding-3-large": {
        "prompt": 0.00013,
        "completion": 0.0
    },
    "text-embedding-3-small": {
        "prompt": 0.00002,
        "completion": 0.0
    },
    "text-embedding-ada-002": {
        "prompt": 0.0001,
        "completion": 0.0
    },

    # Anthropic Models (Production Fallback)
    "claude-3-5-sonnet-20241022": {
        "prompt": 0.003,
        "completion": 0.015
    },
    "claude-3-5-haiku-20241022": {
        "prompt": 0.001,
        "completion": 0.005
    },
    "claude-3-opus-20240229": {
        "prompt": 0.015,
        "completion": 0.075
    },
    "claude-3-sonnet-20240229": {
        "prompt": 0.003,
        "completion": 0.015
    },
    "claude-3-haiku-20240307": {
        "prompt": 0.00025,
        "completion": 0.00125
    }
}
```

### Organization Quotas

```python
@dataclass
class OrganizationQuota:
    organization_id: int
    monthly_cost_limit_usd: float
    monthly_token_limit: int
    daily_request_limit: int

    # Current usage (updated hourly)
    current_month_cost_usd: float
    current_month_tokens: int
    current_day_requests: int
```

---

## 14. Telemetry Usage Examples

### Basic Usage in LLM Provider

```python
# app/ai/llm/openai_provider.py

from app.ai.telemetry import TelemetryTracker

class OpenAIProvider(BaseLLMProvider):
    def generate_text(self, prompt: str, model: str, **kwargs):
        tracker = TelemetryTracker()

        with tracker.track("text_generation") as span:
            try:
                # Estimate prompt tokens
                prompt_tokens = estimate_tokens(prompt, model)
                span.set_input(prompt_tokens, model_id=model, provider="openai")

                # Call OpenAI
                response = openai.ChatCompletion.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    **kwargs
                )

                # Record output
                span.set_output(
                    completion_tokens=response.usage.completion_tokens,
                    success=True
                )

                telemetry = span.finalize()
                return LLMResponse(success=True, data=..., telemetry=telemetry)

            except Exception as e:
                span.set_error(error_type=classify_error(e))
                telemetry = span.finalize()
                return LLMResponse(success=False, error=..., telemetry=telemetry)
```

### Cost Reporting Query

```python
# Get organization's monthly AI cost
from app.ai.telemetry import get_aggregated_metrics

metrics = get_aggregated_metrics(
    organization_id=45,
    time_period="month",
    start_date=datetime(2026, 2, 1),
    end_date=datetime(2026, 2, 28)
)

print(f"Total cost: ${metrics.total_cost_usd:.2f}")
print(f"Total tokens: {metrics.total_tokens:,}")
print(f"Success rate: {metrics.successful_requests / metrics.total_requests * 100:.1f}%")
```

---

**End of AI Telemetry Layer Requirements**
