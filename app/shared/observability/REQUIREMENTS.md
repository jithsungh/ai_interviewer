# Shared Observability - Logging, Tracing & Metrics

## 1. Purpose

The **observability** subdirectory provides:

- Structured logging (JSON format with correlation)
- Distributed tracing (request ID propagation)
- Metrics instrumentation (Prometheus-compatible)
- AI telemetry hooks (LLM calls tracking)
- Sensitive data redaction (tokens, passwords, PII)

**Critical responsibility:** Comprehensive observability WITHOUT business logic.

---

## 2. Responsibilities

### 2.1 Structured Logging

**Must provide:**

- JSON-formatted logs
- Request ID correlation
- User/submission/organization context
- Event type classification
- Latency tracking
- Sensitive data redaction

**Must NOT:**

- Implement business event logic (belongs in domain modules)
- Store logs (only emit, storage is ELK/Loki)

---

### 2.2 Distributed Tracing

**Must provide:**

- Request ID generation and extraction
- Connection ID assignment (WebSocket, WebRTC)
- Correlation ID propagation (multi-request flows)
- Trace context propagation to async tasks

**Must NOT:**

- Implement distributed tracing backend (use Jaeger/Zipkin)

---

### 2.3 Metrics Instrumentation

**Must provide:**

- Counter metrics (total operations)
- Histogram metrics (latency distribution)
- Gauge metrics (current state)
- Protocol-agnostic metric helpers

**Must NOT:**

- Store metrics (only expose, storage is Prometheus/Grafana)
- Aggregate metrics (scraping handles this)

---

### 2.4 AI Telemetry

**Must provide:**

- LLM call tracking (model, tokens, latency, cost)
- Prompt/response logging (masked in production)
- Token usage aggregation
- Cost estimation

**Must NOT:**

- Log full prompts in production (security risk)
- Implement cost billing (belongs in billing service)

---

## 3. Structured Logging

### 3.1 Log Format

**Standard log entry structure:**

```json
{
  "timestamp": "2026-02-14T10:00:00.123Z",
  "level": "INFO",
  "logger": "app.interview.api",
  "message": "Exchange created successfully",
  "request_id": "req_abc123",
  "user_id": 42,
  "submission_id": 789,
  "organization_id": 1,
  "event_type": "exchange_created",
  "latency_ms": 45,
  "metadata": {
    "exchange_id": 123,
    "question_id": 456
  }
}
```

---

### 3.2 Logger Configuration

```python
import logging
import json
from datetime import datetime
from typing import Any, Optional

class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.
        """
        # Base fields
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage()
        }

        # Add correlation fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        if hasattr(record, "connection_id"):
            log_entry["connection_id"] = record.connection_id

        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id

        if hasattr(record, "submission_id"):
            log_entry["submission_id"] = record.submission_id

        if hasattr(record, "organization_id"):
            log_entry["organization_id"] = record.organization_id

        if hasattr(record, "event_type"):
            log_entry["event_type"] = record.event_type

        if hasattr(record, "latency_ms"):
            log_entry["latency_ms"] = record.latency_ms

        # Add metadata if present
        if hasattr(record, "metadata"):
            log_entry["metadata"] = record.metadata

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


def configure_structured_logging(
    log_level: str = "INFO",
    enable_console: bool = True
):
    """
    Configure structured JSON logging.
    """
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers
    logger.handlers = []

    if enable_console:
        # Console handler with JSON formatter
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(StructuredFormatter())
        logger.addHandler(console_handler)

    return logger
```

---

### 3.3 Context-Aware Logging

**Purpose:** Inject context into log entries

```python
class ContextLogger:
    """
    Logger with automatic context injection.
    """

    def __init__(
        self,
        logger: logging.Logger,
        request_id: Optional[str] = None,
        user_id: Optional[int] = None,
        submission_id: Optional[int] = None,
        organization_id: Optional[int] = None
    ):
        self.logger = logger
        self.request_id = request_id
        self.user_id = user_id
        self.submission_id = submission_id
        self.organization_id = organization_id

    def _log(
        self,
        level: int,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[dict] = None
    ):
        """
        Log with automatic context injection.
        """
        extra = {}

        if self.request_id:
            extra["request_id"] = self.request_id
        if self.user_id:
            extra["user_id"] = self.user_id
        if self.submission_id:
            extra["submission_id"] = self.submission_id
        if self.organization_id:
            extra["organization_id"] = self.organization_id
        if event_type:
            extra["event_type"] = event_type
        if latency_ms is not None:
            extra["latency_ms"] = latency_ms
        if metadata:
            extra["metadata"] = metadata

        self.logger.log(level, message, extra=extra)

    def info(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[dict] = None
    ):
        self._log(logging.INFO, message, event_type, latency_ms, metadata)

    def warning(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[dict] = None
    ):
        self._log(logging.WARNING, message, event_type, latency_ms, metadata)

    def error(
        self,
        message: str,
        event_type: Optional[str] = None,
        latency_ms: Optional[float] = None,
        metadata: Optional[dict] = None
    ):
        self._log(logging.ERROR, message, event_type, latency_ms, metadata)


def get_context_logger(
    request_id: Optional[str] = None,
    user_id: Optional[int] = None,
    submission_id: Optional[int] = None,
    organization_id: Optional[int] = None
) -> ContextLogger:
    """
    Create context-aware logger.
    """
    logger = logging.getLogger("app")

    return ContextLogger(
        logger=logger,
        request_id=request_id,
        user_id=user_id,
        submission_id=submission_id,
        organization_id=organization_id
    )
```

**Usage:**

```python
# In API endpoint
@app.post("/api/v1/exchanges")
async def create_exchange(
    request: Request,
    identity: IdentityContext = Depends(get_identity)
):
    # Create context logger
    logger = get_context_logger(
        request_id=request.state.request_id,
        user_id=identity.user_id,
        submission_id=request_data["submission_id"],
        organization_id=identity.organization_id
    )

    start_time = time.perf_counter()

    # Create exchange
    exchange = exchange_service.create(...)

    latency_ms = (time.perf_counter() - start_time) * 1000

    # Log with context (automatically includes request_id, user_id, etc.)
    logger.info(
        "Exchange created successfully",
        event_type="exchange_created",
        latency_ms=latency_ms,
        metadata={"exchange_id": exchange.id}
    )

    return exchange
```

---

## 4. Sensitive Data Redaction

### 4.1 Redaction Rules

**Must redact:**

- Access tokens
- Refresh tokens
- Passwords
- API keys
- Hidden test case expected outputs
- Candidate answers (optional, configurable)

**Example:**

```json
{
  "access_token": "[REDACTED]",
  "refresh_token": "[REDACTED]",
  "password": "[REDACTED]",
  "test_case": {
    "input": "[1,2,3]",
    "expected_output": "[REDACTED]",
    "is_hidden": true
  }
}
```

---

### 4.2 Redaction Implementation

```python
import re
from typing import Any

SENSITIVE_FIELDS = {
    "access_token",
    "refresh_token",
    "password",
    "api_key",
    "secret",
    "token"
}

def redact_sensitive_data(
    data: Any,
    redact_candidate_answers: bool = False
) -> Any:
    """
    Recursively redact sensitive fields from data structure.

    Args:
        data: Data to redact (dict, list, or primitive)
        redact_candidate_answers: If True, redact candidate_answer fields

    Returns:
        Redacted copy of data
    """
    if isinstance(data, dict):
        redacted = {}

        for key, value in data.items():
            # Check if field is sensitive
            key_lower = key.lower()

            if any(sensitive in key_lower for sensitive in SENSITIVE_FIELDS):
                redacted[key] = "[REDACTED]"

            # Redact hidden test case expected outputs
            elif key == "expected_output" and data.get("is_hidden"):
                redacted[key] = "[REDACTED]"

            # Optionally redact candidate answers
            elif redact_candidate_answers and key == "candidate_answer":
                redacted[key] = "[REDACTED_ANSWER]"

            # Recursively redact nested structures
            else:
                redacted[key] = redact_sensitive_data(value, redact_candidate_answers)

        return redacted

    elif isinstance(data, list):
        return [redact_sensitive_data(item, redact_candidate_answers) for item in data]

    else:
        # Primitive type, return as-is
        return data


def mask_token(token: str, visible_chars: int = 4) -> str:
    """
    Mask token, showing only last N characters.

    Example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." -> "...cJ9"
    """
    if len(token) <= visible_chars:
        return "[REDACTED]"

    return f"...{token[-visible_chars:]}"
```

---

## 5. Distributed Tracing

### 5.1 Request ID Management

**Purpose:** Generate and propagate request IDs

```python
import uuid

def generate_request_id() -> str:
    """
    Generate unique request ID.
    """
    return f"req_{uuid.uuid4().hex[:12]}"


def extract_request_id(request: Request) -> str:
    """
    Extract request ID from header or generate new one.
    """
    request_id = request.headers.get("X-Request-ID")

    if not request_id:
        request_id = generate_request_id()

    return request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject request ID into request state.
    """

    async def dispatch(self, request: Request, call_next):
        # Extract or generate request ID
        request_id = extract_request_id(request)

        # Inject into request state
        request.state.request_id = request_id

        # Call next middleware
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
```

---

### 5.2 Connection ID Management

**Purpose:** Assign unique ID to WebSocket/WebRTC connections

```python
def generate_connection_id() -> str:
    """
    Generate unique connection ID for WebSocket/WebRTC.
    """
    return f"conn_{uuid.uuid4().hex[:12]}"


def generate_session_id() -> str:
    """
    Generate unique session ID for WebRTC.
    """
    return f"session_{uuid.uuid4().hex[:12]}"
```

---

### 5.3 Trace Context Propagation

**Purpose:** Propagate trace context to async tasks

```python
@dataclass
class TraceContext:
    """
    Trace context for propagation.
    """
    request_id: str
    correlation_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@celery.task
def async_task_with_tracing(
    task_data: dict,
    trace_context: dict
):
    """
    Async task with trace context propagation.
    """
    context = TraceContext(**trace_context)

    logger = get_context_logger(request_id=context.request_id)

    logger.info(
        "Task started",
        event_type="task_started",
        metadata={"task_name": "async_task"}
    )

    # Execute task...
```

---

## 6. Metrics Instrumentation

### 6.1 Metric Types

**Counter:** Monotonically increasing count

```python
from prometheus_client import Counter

interview_exchanges_total = Counter(
    name="interview_exchanges_total",
    documentation="Total interview exchanges created"
)

# Usage
interview_exchanges_total.inc()
```

**Histogram:** Distribution of values (latency, size)

```python
from prometheus_client import Histogram

interview_latency_seconds = Histogram(
    name="interview_latency_seconds",
    documentation="Interview exchange creation latency",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
)

# Usage
with interview_latency_seconds.time():
    exchange = create_exchange(...)
```

**Gauge:** Current value (can go up or down)

```python
from prometheus_client import Gauge

websocket_connections_active = Gauge(
    name="websocket_connections_active",
    documentation="Active WebSocket connections"
)

# Usage
websocket_connections_active.inc()  # On connect
websocket_connections_active.dec()  # On disconnect
```

---

### 6.2 Metric Helpers

```python
from contextlib import contextmanager
from time import time

@contextmanager
def track_latency(histogram: Histogram):
    """
    Context manager to track operation latency.
    """
    start = time()
    try:
        yield
    finally:
        duration = time() - start
        histogram.observe(duration)


def track_operation(
    counter: Counter,
    histogram: Histogram,
    operation_name: str
):
    """
    Decorator to track operation count and latency.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            counter.inc()

            start = time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time() - start
                histogram.observe(duration)

        return wrapper
    return decorator


# Usage
@track_operation(
    counter=question_generation_total,
    histogram=question_generation_latency_seconds,
    operation_name="generate_question"
)
async def generate_question(...):
    ...
```

---

### 6.3 Standard Metrics

**Interview metrics:**

```python
interview_duration_seconds = Histogram(
    "interview_duration_seconds",
    "Total interview duration"
)

interview_exchanges_total = Counter(
    "interview_exchanges_total",
    "Total exchanges created"
)

interview_pauses_total = Counter(
    "interview_pauses_total",
    "Total interview pauses"
)
```

**Question metrics:**

```python
question_generation_duration_seconds = Histogram(
    "question_generation_duration_seconds",
    "Question generation latency"
)

question_retrieval_duration_seconds = Histogram(
    "question_retrieval_duration_seconds",
    "Qdrant retrieval latency"
)

question_selection_fallback_total = Counter(
    "question_selection_fallback_total",
    "Fallback strategies used",
    labelnames=["reason"]
)
```

**Evaluation metrics:**

```python
evaluation_duration_seconds = Histogram(
    "evaluation_duration_seconds",
    "Evaluation latency"
)

evaluation_score_distribution = Histogram(
    "evaluation_score_distribution",
    "Score distribution",
    buckets=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
)
```

**Sandbox metrics:**

```python
sandbox_execution_duration_seconds = Histogram(
    "sandbox_execution_duration_seconds",
    "Sandbox execution time"
)

sandbox_timeout_total = Counter(
    "sandbox_timeout_total",
    "Sandbox timeouts"
)

sandbox_error_total = Counter(
    "sandbox_error_total",
    "Sandbox errors",
    labelnames=["error_type"]
)
```

**WebSocket metrics:**

```python
websocket_connections_active = Gauge(
    "websocket_connections_active",
    "Active WebSocket connections"
)

websocket_reconnects_total = Counter(
    "websocket_reconnects_total",
    "WebSocket reconnects"
)

websocket_disconnect_total = Counter(
    "websocket_disconnect_total",
    "WebSocket disconnects",
    labelnames=["reason"]
)
```

**AI metrics:**

```python
ai_provider_calls_total = Counter(
    "ai_provider_calls_total",
    "AI provider calls",
    labelnames=["provider", "model"]
)

ai_provider_latency_seconds = Histogram(
    "ai_provider_latency_seconds",
    "AI provider latency",
    labelnames=["provider"]
)

ai_provider_tokens_total = Counter(
    "ai_provider_tokens_total",
    "Token usage",
    labelnames=["provider", "type"]  # type: prompt, completion
)

ai_provider_cost_usd_total = Counter(
    "ai_provider_cost_usd_total",
    "Estimated cost",
    labelnames=["provider"]
)
```

---

## 7. AI Telemetry Hooks

### 7.1 LLM Call Tracking

```python
@dataclass
class AITelemetry:
    """
    Telemetry data for AI provider call.
    """
    provider: str           # 'openai', 'anthropic'
    model: str              # 'gpt-4', 'claude-3-opus'
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float
    success: bool
    error_type: Optional[str]
    cost_estimate_usd: float

    def log(self, logger: ContextLogger):
        """
        Log AI telemetry.
        """
        logger.info(
            f"AI call: {self.provider}/{self.model}",
            event_type="ai_call",
            latency_ms=self.latency_seconds * 1000,
            metadata={
                "provider": self.provider,
                "model": self.model,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "success": self.success,
                "error_type": self.error_type,
                "cost_estimate_usd": self.cost_estimate_usd
            }
        )

    def emit_metrics(self):
        """
        Emit Prometheus metrics.
        """
        ai_provider_calls_total.labels(
            provider=self.provider,
            model=self.model
        ).inc()

        ai_provider_latency_seconds.labels(
            provider=self.provider
        ).observe(self.latency_seconds)

        if self.success:
            ai_provider_tokens_total.labels(
                provider=self.provider,
                type="prompt"
            ).inc(self.prompt_tokens)

            ai_provider_tokens_total.labels(
                provider=self.provider,
                type="completion"
            ).inc(self.completion_tokens)

            ai_provider_cost_usd_total.labels(
                provider=self.provider
            ).inc(self.cost_estimate_usd)


@contextmanager
def track_ai_call(
    provider: str,
    model: str,
    logger: ContextLogger
):
    """
    Context manager to track AI provider call.
    """
    start = time()
    telemetry = AITelemetry(
        provider=provider,
        model=model,
        prompt_tokens=0,
        completion_tokens=0,
        latency_seconds=0,
        success=False,
        error_type=None,
        cost_estimate_usd=0
    )

    try:
        yield telemetry
        telemetry.success = True
    except Exception as e:
        telemetry.error_type = type(e).__name__
        raise
    finally:
        telemetry.latency_seconds = time() - start
        telemetry.log(logger)
        telemetry.emit_metrics()


# Usage
async def call_openai(prompt: str, logger: ContextLogger):
    with track_ai_call("openai", "gpt-4", logger) as telemetry:
        response = await openai.ChatCompletion.create(...)

        # Populate telemetry
        telemetry.prompt_tokens = response.usage.prompt_tokens
        telemetry.completion_tokens = response.usage.completion_tokens
        telemetry.cost_estimate_usd = calculate_cost(
            model="gpt-4",
            prompt_tokens=telemetry.prompt_tokens,
            completion_tokens=telemetry.completion_tokens
        )

        return response
```

---

## 8. Configuration

### 8.1 ObservabilityConfig

```python
@dataclass
class ObservabilityConfig:
    # Logging
    log_level: str = "INFO"
    enable_structured_logging: bool = True
    enable_console_logging: bool = True
    enable_file_logging: bool = False
    log_file_path: str = "/var/log/app/app.log"

    # Redaction
    enable_sensitive_redaction: bool = True
    redact_candidate_answers: bool = False
    redact_test_case_outputs: bool = True

    # Tracing
    enable_distributed_tracing: bool = True
    trace_sample_rate: float = 1.0

    # Metrics
    enable_metrics: bool = True
    metrics_port: int = 9090

    # AI telemetry
    enable_ai_telemetry: bool = True
    log_ai_prompts_in_dev: bool = True
    log_ai_prompts_in_prod: bool = False
```

---

## 9. Testing Requirements

### 9.1 Logging Tests

**Test: Structured log format**

```python
def test_structured_log_format():
    logger = configure_structured_logging()

    with LogCapture() as captured:
        logger.info("Test message", extra={"request_id": "req_123"})

        log_entry = json.loads(captured.records[0])

        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Test message"
        assert log_entry["request_id"] == "req_123"
```

**Test: Context injection**

```python
def test_context_logger():
    logger = get_context_logger(request_id="req_123", user_id=42)

    with LogCapture() as captured:
        logger.info("Test", event_type="test_event")

        log_entry = json.loads(captured.records[0])

        assert log_entry["request_id"] == "req_123"
        assert log_entry["user_id"] == 42
        assert log_entry["event_type"] == "test_event"
```

---

### 9.2 Redaction Tests

**Test: Sensitive fields redacted**

```python
def test_sensitive_field_redaction():
    data = {
        "user_id": 42,
        "access_token": "secret_token_123",
        "password": "secret_pass"
    }

    redacted = redact_sensitive_data(data)

    assert redacted["user_id"] == 42
    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["password"] == "[REDACTED]"
```

**Test: Hidden test case redacted**

```python
def test_hidden_test_case_redaction():
    data = {
        "test_case": {
            "input": "[1,2,3]",
            "expected_output": "6",
            "is_hidden": True
        }
    }

    redacted = redact_sensitive_data(data)

    assert redacted["test_case"]["input"] == "[1,2,3]"
    assert redacted["test_case"]["expected_output"] == "[REDACTED]"
```

---

### 9.3 Metrics Tests

**Test: Counter increments**

```python
def test_counter_metric():
    counter = Counter("test_counter", "Test counter")

    initial = counter._value.get()
    counter.inc()

    assert counter._value.get() == initial + 1
```

**Test: Histogram records value**

```python
def test_histogram_metric():
    histogram = Histogram("test_histogram", "Test histogram")

    histogram.observe(0.5)

    assert histogram._sum.get() == 0.5
    assert histogram._count.get() == 1
```

---

## 10. Critical Risks

1. **Sensitive data logged:** Tokens/passwords in logs → security breach
2. **Hidden test case exposed:** Expected outputs logged → candidate cheating
3. **Missing request ID:** Logs without correlation → untraceable issues
4. **Metric cardinality explosion:** Too many label values → Prometheus overload
5. **Full prompt logged in prod:** Resume/JD in logs → PII exposure
6. **Log volume explosion:** Debug logs in prod → storage costs skyrocket

---

## 11. Acceptance Criteria

**Observability module is complete when:**

✅ Structured logging configured (JSON format)
✅ Context logger working (automatic context injection)
✅ Sensitive data redaction working (tokens, passwords, test cases)
✅ Request ID propagation working (REST, WebSocket, async tasks)
✅ Connection ID assignment working (WebSocket, WebRTC)
✅ Metrics instrumentation working (counter, histogram, gauge)
✅ AI telemetry hooks working (LLM call tracking)
✅ Metrics exposed (Prometheus endpoint)
✅ All tests passing (logging, redaction, metrics)

---

**End of Shared Observability Requirements**
