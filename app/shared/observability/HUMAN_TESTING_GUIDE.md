# Observability Module - Human Testing Guide

## Overview

This guide provides instructions for **manually testing** the observability module in a live environment.

The observability module provides:

- Structured JSON logging
- Distributed tracing (request IDs)
- Prometheus metrics
- AI telemetry tracking
- Sensitive data redaction

---

## Prerequisites

1. **Python Environment**: Ensure dependencies are installed

   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables**: Set these in `.env` or export directly:

   ```bash
   export LOG_LEVEL=INFO
   export ENABLE_STRUCTURED_LOGGING=true
   export ENABLE_METRICS=true
   export METRICS_PORT=9090
   ```

3. **FastAPI Application**: Ensure the app is configured with observability middleware

---

## Test 1: Structured Logging

### Purpose

Verify JSON-formatted logs with context injection.

### Steps

1. **Configure logging in your application**:

   ```python
   from app.shared.observability import configure_structured_logging

   configure_structured_logging(log_level="INFO", enable_console=True)
   ```

2. **Create a context logger**:

   ```python
   from app.shared.observability import get_context_logger

   logger = get_context_logger(
       request_id="req_test_123",
       user_id=42,
       organization_id=1
   )
   ```

3. **Log a message**:

   ```python
   logger.info(
       "Test log message",
       event_type="test_event",
       latency_ms=150,
       metadata={"key": "value"}
   )
   ```

4. **Verify output** (console):
   ```json
   {
     "timestamp": "2026-02-18T10:00:00.123Z",
     "level": "INFO",
     "logger": "app",
     "message": "Test log message",
     "request_id": "req_test_123",
     "user_id": 42,
     "organization_id": 1,
     "event_type": "test_event",
     "latency_ms": 150,
     "metadata": { "key": "value" }
   }
   ```

### Expected Result

✅ Log output is valid JSON
✅ All context fields present
✅ Timestamp is ISO 8601 format

---

## Test 2: Request ID Middleware

### Purpose

Verify request ID is injected into FastAPI requests.

### Steps

1. **Add middleware to FastAPI app**:

   ```python
   from fastapi import FastAPI
   from app.shared.observability import RequestIDMiddleware

   app = FastAPI()
   app.add_middleware(RequestIDMiddleware)
   ```

2. **Create test endpoint**:

   ```python
   from fastapi import Request

   @app.get("/test")
   async def test_endpoint(request: Request):
       return {"request_id": request.state.request_id}
   ```

3. **Start application**:

   ```bash
   uvicorn main:app --reload
   ```

4. **Test with curl** (without Request-ID header):

   ```bash
   curl -v http://localhost:8000/test
   ```

5. **Verify response**:
   - Response body contains `request_id` starting with `req_`
   - Response header `X-Request-ID` present

6. **Test with custom Request-ID**:

   ```bash
   curl -H "X-Request-ID: req_custom_123" http://localhost:8000/test
   ```

7. **Verify**:
   - Response body contains `req_custom_123`
   - Response header matches

### Expected Result

✅ Request ID generated if not provided
✅ Request ID preserved if provided
✅ Response header contains request ID

---

## Test 3: Sensitive Data Redaction

### Purpose

Verify sensitive fields are redacted from logs.

### Steps

1. **Create test data**:

   ```python
   from app.shared.observability import redact_sensitive_data

   data = {
       "user_id": 42,
       "email": "test@example.com",
       "access_token": "secret_token_123",
       "password": "secret_password"
   }
   ```

2. **Redact sensitive data**:

   ```python
   redacted = redact_sensitive_data(data)
   print(redacted)
   ```

3. **Verify output**:
   ```python
   {
       "user_id": 42,
       "email": "test@example.com",
       "access_token": "[REDACTED]",
       "password": "[REDACTED]"
   }
   ```

### Expected Result

✅ `access_token` redacted
✅ `password` redacted
✅ Non-sensitive fields preserved

---

## Test 4: Prometheus Metrics

### Purpose

Verify metrics are collected and exposed.

### Steps

1. **Import metrics**:

   ```python
   from app.shared.observability.metrics import metrics
   ```

2. **Increment a counter**:

   ```python
   metrics.interview_exchanges_total.inc()
   metrics.interview_exchanges_total.inc()
   metrics.interview_exchanges_total.inc()
   ```

3. **Record histogram values**:

   ```python
   metrics.interview_duration_seconds.observe(120)  # 2 minutes
   metrics.interview_duration_seconds.observe(300)  # 5 minutes
   ```

4. **Expose metrics endpoint**:

   ```python
   from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
   from fastapi.responses import Response

   @app.get("/metrics")
   async def metrics_endpoint():
       return Response(
           content=generate_latest(),
           media_type=CONTENT_TYPE_LATEST
       )
   ```

5. **Check metrics**:

   ```bash
   curl http://localhost:8000/metrics | grep interview
   ```

6. **Verify output**:

   ```
   # HELP interview_exchanges_total Total interview exchanges created
   # TYPE interview_exchanges_total counter
   interview_exchanges_total 3.0

   # HELP interview_duration_seconds Total interview duration
   # TYPE interview_duration_seconds histogram
   interview_duration_seconds_sum 420.0
   interview_duration_seconds_count 2.0
   ```

### Expected Result

✅ Metrics endpoint returns Prometheus format
✅ Counter values correct
✅ Histogram statistics correct

---

## Test 5: AI Telemetry Tracking

### Purpose

Verify AI provider calls are tracked.

### Steps

1. **Track an AI call**:

   ```python
   from app.shared.observability import track_ai_call, get_context_logger

   logger = get_context_logger(request_id="req_123")

   with track_ai_call("openai", "gpt-4", logger) as telemetry:
       # Simulate OpenAI call
       telemetry.prompt_tokens = 150
       telemetry.completion_tokens = 50
       telemetry.cost_estimate_usd = 0.0065
   ```

2. **Check logs** (console output):

   ```json
   {
     "timestamp": "...",
     "level": "INFO",
     "message": "AI call: openai/gpt-4",
     "event_type": "ai_call",
     "latency_ms": 2.5,
     "metadata": {
       "provider": "openai",
       "model": "gpt-4",
       "prompt_tokens": 150,
       "completion_tokens": 50,
       "total_tokens": 200,
       "success": true,
       "cost_estimate_usd": 0.0065
     }
   }
   ```

3. **Check metrics**:

   ```bash
   curl http://localhost:8000/metrics | grep ai_provider
   ```

4. **Verify output**:
   ```
   ai_provider_calls_total{model="gpt-4",provider="openai"} 1.0
   ai_provider_tokens_total{provider="openai",type="prompt"} 150.0
   ai_provider_tokens_total{provider="openai",type="completion"} 50.0
   ai_provider_cost_usd_total{provider="openai"} 0.0065
   ```

### Expected Result

✅ Telemetry logged with all fields
✅ Metrics incremented correctly
✅ Latency measured

---

## Test 6: Cost Estimation

### Purpose

Verify AI cost calculation is accurate.

### Steps

1. **Calculate OpenAI cost**:

   ```python
   from app.shared.observability.telemetry import calculate_openai_cost

   cost = calculate_openai_cost(
       model="gpt-4",
       prompt_tokens=1000,
       completion_tokens=500
   )

   print(f"Estimated cost: ${cost:.4f}")
   ```

2. **Verify calculation**:
   - GPT-4: $30/1M input, $60/1M output
   - Expected: (1000 _ 30 / 1M) + (500 _ 60 / 1M) = $0.0600

3. **Calculate Anthropic cost**:

   ```python
   from app.shared.observability.telemetry import calculate_anthropic_cost

   cost = calculate_anthropic_cost(
       model="claude-3-opus",
       prompt_tokens=1000,
       completion_tokens=500
   )

   print(f"Estimated cost: ${cost:.4f}")
   ```

4. **Verify calculation**:
   - Claude 3 Opus: $15/1M input, $75/1M output
   - Expected: (1000 _ 15 / 1M) + (500 _ 75 / 1M) = $0.0525

### Expected Result

✅ OpenAI costs calculated correctly
✅ Anthropic costs calculated correctly

---

## Test 7: Trace Context Propagation

### Purpose

Verify trace context is propagated to async tasks.

### Steps

1. **Create trace context from request**:

   ```python
   from app.shared.observability.tracing import create_trace_context_from_request
   from fastapi import Request

   @app.post("/async-task")
   async def start_async_task(request: Request):
       context = create_trace_context_from_request(request)

       # Pass to async task
       task_data = {"key": "value"}
       # await celery_task.delay(task_data, trace_context=context.to_dict())

       return {"status": "queued", "request_id": context.request_id}
   ```

2. **In async task**:

   ```python
   from app.shared.observability.tracing import TraceContext
   from app.shared.observability import get_context_logger

   def celery_task(task_data, trace_context):
       context = TraceContext.from_dict(trace_context)
       logger = get_context_logger(request_id=context.request_id)

       logger.info("Task started", event_type="task_started")
       # ... process task
   ```

3. **Verify**:
   - Same `request_id` in both request handler and async task logs

### Expected Result

✅ Request ID propagated to async task
✅ Both logs share same request_id

---

## Test 8: Configuration Loading

### Purpose

Verify configuration loads from environment.

### Steps

1. **Set environment variables**:

   ```bash
   export LOG_LEVEL=DEBUG
   export ENABLE_METRICS=true
   export METRICS_PORT=9091
   export TRACE_SAMPLE_RATE=0.5
   ```

2. **Load configuration**:

   ```python
   from app.shared.observability.config import ObservabilityConfig

   config = ObservabilityConfig()

   print(f"Log level: {config.log_level}")
   print(f"Metrics enabled: {config.enable_metrics}")
   print(f"Metrics port: {config.metrics_port}")
   print(f"Sample rate: {config.trace_sample_rate}")
   ```

3. **Verify output**:
   ```
   Log level: DEBUG
   Metrics enabled: True
   Metrics port: 9091
   Sample rate: 0.5
   ```

### Expected Result

✅ All environment variables loaded correctly
✅ Validation applied (e.g., sample_rate between 0-1)

---

## Running Automated Tests

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/shared/test_observability_*.py -v

# Run specific test file
pytest tests/unit/shared/test_observability_logging.py -v

# Run with coverage
pytest tests/unit/shared/ --cov=app.shared.observability --cov-report=html
```

### Integration Tests

```bash
# Run integration tests
pytest tests/integration/shared/test_observability_integration.py -v

# Run all tests
pytest tests/ -v
```

### Expected Test Results

```
tests/unit/shared/test_observability_logging.py ........ [12 PASSED]
tests/unit/shared/test_observability_redaction.py ............... [19 PASSED]
tests/unit/shared/test_observability_tracing.py ................... [20 PASSED]
tests/unit/shared/test_observability_metrics.py ............... [15 PASSED]
tests/unit/shared/test_observability_telemetry.py ............... [17 PASSED]
tests/unit/shared/test_observability_config.py .......... [10 PASSED]
tests/integration/shared/test_observability_integration.py ......... [9 PASSED]

================================
TOTAL: 102 TESTS PASSED
================================
```

---

## Troubleshooting

### Issue: Logs not appearing

**Solution**: Check log level configuration. Set `LOG_LEVEL=DEBUG` for verbose output.

### Issue: Metrics endpoint returns 404

**Solution**: Ensure metrics endpoint is registered and `/metrics` route exists.

### Issue: Request ID not in response headers

**Solution**: Verify `RequestIDMiddleware` is added before other middleware.

### Issue: Sensitive data not redacted

**Solution**: Ensure `redact_sensitive_data()` is called before logging. Check `ENABLE_SENSITIVE_REDACTION=true`.

---

## Production Checklist

Before deploying observability to production:

- [ ] Set `LOG_LEVEL=INFO` or `WARNING`
- [ ] Set `LOG_AI_PROMPTS_IN_PROD=false`
- [ ] Set `REDACT_CANDIDATE_ANSWERS=true` (if needed)
- [ ] Set `TRACE_SAMPLE_RATE=0.1` (10% sampling to reduce overhead)
- [ ] Configure log aggregation (ELK, Loki, CloudWatch)
- [ ] Configure metrics scraping (Prometheus)
- [ ] Set up alerts for error rates and latency
- [ ] Test log rotation and retention policies

---

## Questions?

If you encounter issues not covered in this guide:

1. Check the REQUIREMENTS.md for design decisions
2. Review test cases for usage examples
3. Check logs for error messages

---

**End of Human Testing Guide**
