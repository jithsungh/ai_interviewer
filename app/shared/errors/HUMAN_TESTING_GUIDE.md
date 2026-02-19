# Error Handling Module - Human Testing Guide

**Module:** `app/shared/errors/`  
**Version:** 1.0.0  
**Last Updated:** February 19, 2026

---

## Overview

This guide provides **engineer-focused** instructions for manually testing the error handling module. The errors module is **pure Python** (no HTTP endpoints), so testing is done via **Python REPL**, **unit tests**, and **integration with other modules**.

---

## Prerequisites

- Python 3.11+
- Project dependencies installed (`pip install -r requirements.txt`)
- PYTHONPATH includes project root

---

## Testing Approach

Since this is a **shared infrastructure module** with no API endpoints, testing is done:

1. **Interactive Python REPL** - Test exception creation and serialization
2. **Unit Tests** - Run pytest test suite
3. **Integration Tests** - Test with FastAPI exception handlers
4. **Module Integration** - Test with existing modules (redis/locks.py, qdrant/client.py)

---

## Section 1: Interactive Python Testing

### 1.1 Import and Setup

```python
# Start Python REPL from project root
python

# Import error module
from app.shared.errors import (
    BaseError,
    AuthenticationError,
    ValidationError,
    serialize_rest_error,
    serialize_websocket_error,
    is_fatal_error,
    get_log_level,
    error_config,
)
```

### 1.2 Test Exception Creation

**Test 1: Create AuthenticationError**

```python
error = AuthenticationError(
    message="Access token expired",
    request_id="req_test_001",
    metadata={"expired_at": "2026-02-19T10:00:00Z"}
)

# Verify fields
assert error.error_code == "AUTHENTICATION_FAILED"
assert error.http_status_code == 401
assert error.request_id == "req_test_001"
assert error.metadata["expired_at"] == "2026-02-19T10:00:00Z"
print("✅ AuthenticationError creation successful")
```

**Expected Output:**

```
✅ AuthenticationError creation successful
```

---

**Test 2: Create ValidationError with Field**

```python
error = ValidationError(
    message="Invalid email format",
    field="email",
    request_id="req_test_002"
)

# Verify
assert error.error_code == "VALIDATION_ERROR"
assert error.http_status_code == 422
assert error.metadata["field"] == "email"
print("✅ ValidationError with field successful")
```

---

**Test 3: Backward Compatibility (ApplicationError)**

```python
from app.shared.errors import ApplicationError

# Old-style usage (as in redis/locks.py)
error = ApplicationError(
    message="Lock acquisition failed",
    status_code=409,
    error_code="LOCK_FAILED",
    details={"lock_key": "interview:123"}
)

# Verify backward compat
assert error.http_status_code == 409  # New property
assert error.status_code == 409        # Old property (alias)
assert error.metadata == {"lock_key": "interview:123"}  # New property
assert error.details == {"lock_key": "interview:123"}   # Old property (alias)
print("✅ Backward compatibility successful")
```

---

### 1.3 Test Error Serialization

**Test 4: REST API Serialization**

```python
error = ValidationError(
    message="Invalid input",
    field="name",
    request_id="req_rest_001"
)

serialized = serialize_rest_error(error)
print(serialized)
```

**Expected Output:**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input",
    "request_id": "req_rest_001",
    "metadata": {
      "field": "name"
    }
  }
}
```

**Validation:**

```python
assert serialized["error"]["code"] == "VALIDATION_ERROR"
assert "metadata" in serialized["error"]
print("✅ REST serialization successful")
```

---

**Test 5: WebSocket Serialization**

```python
error = AuthenticationError(
    message="Invalid token",
    request_id="req_ws_001"
)

serialized = serialize_websocket_error(error)
print(serialized)
```

**Expected Output:**

```json
{
  "event": "error",
  "payload": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Invalid token"
  }
}
```

**Note:** WebSocket serialization intentionally **omits request_id** (uses connection_id instead).

**Validation:**

```python
assert serialized["event"] == "error"
assert serialized["payload"]["code"] == "AUTHENTICATION_FAILED"
assert "request_id" not in serialized["payload"]
print("✅ WebSocket serialization successful")
```

---

### 1.4 Test Error Classification

**Test 6: Fatal vs Recoverable**

```python
from app.shared.errors import (
    AuthenticationError,
    DomainInvariantViolation,
    ValidationError,
    is_fatal_error,
)

# Fatal errors (close WebSocket connection)
fatal_errors = [
    AuthenticationError("Invalid token"),
    DomainInvariantViolation("exchange_immutable", "Exchange modified"),
]

for error in fatal_errors:
    assert is_fatal_error(error) is True

print("✅ Fatal errors classified correctly")

# Recoverable errors (keep connection open)
recoverable_errors = [
    ValidationError("Invalid field"),
]

for error in recoverable_errors:
    assert is_fatal_error(error) is False

print("✅ Recoverable errors classified correctly")
```

---

**Test 7: Log Level Determination**

```python
from app.shared.errors import get_log_level, InternalServerError

error = DomainInvariantViolation("template_immutable", "Template modified")
assert get_log_level(error) == "CRITICAL"
print("✅ Domain invariant violation → CRITICAL")

error = InternalServerError("Database failed")
assert get_log_level(error) == "ERROR"
print("✅ Server error (5xx) → ERROR")

error = ValidationError("Invalid field")
assert get_log_level(error) == "WARN"
print("✅ Client error (4xx) → WARN")
```

---

### 1.5 Test Configuration

**Test 8: Error Configuration**

```python
from app.shared.errors import error_config

# Check defaults
assert error_config.log_client_errors is True
assert error_config.log_server_errors is True
assert error_config.websocket_close_code_fatal == 1008

# Check environment detection
print(f"Environment: {error_config.environment}")
print(f"Is Production: {error_config.is_production}")
print(f"Include Stack Trace: {error_config.include_stack_trace}")

print("✅ Configuration loaded successfully")
```

---

## Section 2: Unit Test Execution

### 2.1 Run All Error Module Tests

```bash
# From project root
pytest tests/unit/shared/test_errors_*.py -v
```

**Expected Result:**

```
tests/unit/shared/test_errors_classification.py::... PASSED
tests/unit/shared/test_errors_config.py::... PASSED
tests/unit/shared/test_errors_exceptions.py::... PASSED
tests/unit/shared/test_errors_serializers.py::... PASSED

============ 176 passed in 1.2s ============
```

### 2.2 Run Specific Test Classes

**Test exception creation:**

```bash
pytest tests/unit/shared/test_errors_exceptions.py::TestClientErrors -v
```

**Test serialization:**

```bash
pytest tests/unit/shared/test_errors_serializers.py::TestRESTSerialization -v
```

**Test classification:**

```bash
pytest tests/unit/shared/test_errors_classification.py::TestFatalErrorClassification -v
```

### 2.3 Run with Coverage

```bash
pytest tests/unit/shared/test_errors_*.py --cov=app.shared.errors --cov-report=term-missing
```

**Expected Coverage:** >95%

---

## Section 3: Integration Testing

### 3.1 Test with FastAPI Exception Handler

Create test file: `test_error_handler.py`

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.shared.errors import BaseError, serialize_rest_error, get_log_level

app = FastAPI()

@app.exception_handler(BaseError)
async def base_error_handler(request: Request, exc: BaseError):
    """Global exception handler for all BaseError subclasses"""

    # Add request_id if not present
    if not exc.request_id:
        exc.request_id = request.state.get("request_id", "unknown")

    # Log error
    log_level = get_log_level(exc)
    print(f"[{log_level}] {exc.error_code}: {exc.message}")

    # Serialize response
    response_body = serialize_rest_error(exc)

    return JSONResponse(
        status_code=exc.http_status_code,
        content=response_body
    )

@app.get("/test/auth-error")
async def test_auth_error():
    from app.shared.errors import AuthenticationError
    raise AuthenticationError("Token expired")

@app.get("/test/validation-error")
async def test_validation_error():
    from app.shared.errors import ValidationError
    raise ValidationError("Invalid email", field="email")

# Test with:
# uvicorn test_error_handler:app --reload
# curl http://localhost:8000/test/auth-error
# curl http://localhost:8000/test/validation-error
```

**Expected Response (auth-error):**

```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Token expired",
    "request_id": "unknown"
  }
}
```

**HTTP Status:** 401

---

### 3.2 Test with Existing Module (Redis Locks)

```python
# Test error compatibility with existing redis/locks.py

from app.persistence.redis.locks import LockAcquisitionError
from app.shared.errors import serialize_rest_error

# Create lock error (uses ApplicationError internally)
error = LockAcquisitionError(
    lock_key="interview:lock:123",
    timeout=10
)

# Should work with new serialization
response = serialize_rest_error(error, request_id="req_integration_001")

# Verify
assert response["error"]["code"] == "LOCK_ACQUISITION_FAILED"
assert response["error"]["request_id"] == "req_integration_001"
assert error.http_status_code == 409

print("✅ Integration with redis/locks.py successful")
```

---

## Section 4: WebSocket Error Handling Simulation

### 4.1 Simulate WebSocket Connection Lifecycle

```python
from app.shared.errors import (
    AuthenticationError,
    ValidationError,
    is_fatal_error,
    serialize_websocket_error,
    error_config,
)

def handle_websocket_error(error, connection_id):
    """Simulate WebSocket error handling"""

    # Serialize error event
    event = serialize_websocket_error(error)

    print(f"[WS:{connection_id}] Sending error event: {event}")

    # Check if fatal
    if is_fatal_error(error):
        close_code = error_config.websocket_close_code_fatal
        print(f"[WS:{connection_id}] FATAL error - closing connection with code {close_code}")
        return "CLOSED"
    else:
        print(f"[WS:{connection_id}] Recoverable error - keeping connection open")
        return "OPEN"

# Test recoverable error
error = ValidationError("Invalid answer format")
status = handle_websocket_error(error, "conn_001")
assert status == "OPEN"

# Test fatal error
error = AuthenticationError("Token expired")
status = handle_websocket_error(error, "conn_002")
assert status == "CLOSED"

print("✅ WebSocket error handling simulation successful")
```

**Expected Output:**

```
[WS:conn_001] Sending error event: {'event': 'error', 'payload': {'code': 'VALIDATION_ERROR', 'message': 'Invalid answer format'}}
[WS:conn_001] Recoverable error - keeping connection open
[WS:conn_002] Sending error event: {'event': 'error', 'payload': {'code': 'AUTHENTICATION_FAILED', 'message': 'Token expired'}}
[WS:conn_002] FATAL error - closing connection with code 1008
✅ WebSocket error handling simulation successful
```

---

## Section 5: Edge Cases and Error Scenarios

### 5.1 Test Error Propagation with Context Enrichment

```python
from app.shared.errors import InfrastructureError

# Low-level error (database layer)
error = InfrastructureError(
    component="postgres",
    message="Connection timeout"
)

# Mid-level adds query context (repository layer)
error.metadata["query"] = "SELECT * FROM users WHERE id = $1"
error.metadata["params"] = [42]

# High-level adds request context (API layer)
error.request_id = "req_enriched_001"

# Serialize with full context
from app.shared.errors import serialize_rest_error
response = serialize_rest_error(error)

# Verify enrichment
assert response["error"]["request_id"] == "req_enriched_001"
assert response["error"]["metadata"]["component"] == "postgres"
assert response["error"]["metadata"]["query"] is not None

print("✅ Error context enrichment successful")
```

### 5.2 Test Domain Invariant Violation

```python
from app.shared.errors import DomainInvariantViolation, get_log_level

# Critical system bug detected
error = DomainInvariantViolation(
    invariant="exchange_immutable",
    message="Exchange was modified after creation",
    request_id="req_critical_001",
    metadata={"exchange_id": 42, "modification": "question_id changed"}
)

# Verify classification
assert get_log_level(error) == "CRITICAL"
assert is_fatal_error(error) is True
assert error.http_status_code == 500

print("✅ Domain invariant violation detected correctly")
print(f"   Invariant: {error.metadata['invariant']}")
print(f"   Log Level: {get_log_level(error)}")
```

### 5.3 Test Proctoring Violation (Advisory)

```python
from app.shared.errors import ProctoringViolation, get_log_level, is_fatal_error

# Advisory proctoring event
error = ProctoringViolation(
    event_type="face_not_visible",
    message="Face not detected in frame",
    risk_score=0.75,
    request_id="req_proctor_001"
)

# Verify it's non-blocking
assert error.http_status_code == 200  # Not an error response
assert is_fatal_error(error) is False  # Recoverable (advisory)
assert get_log_level(error) == "INFO"  # Info level

print("✅ Proctoring violation (advisory) handled correctly")
print(f"   Event: {error.metadata['event_type']}")
print(f"   Risk Score: {error.metadata['risk_score']}")
print(f"   Fatal: {is_fatal_error(error)}")
```

---

## Section 6: Performance and Stress Testing

### 6.1 Serialization Performance

```python
import time
from app.shared.errors import ValidationError, serialize_rest_error

# Create many errors
errors = [
    ValidationError(f"Error {i}", field="field_name", request_id=f"req_{i}")
    for i in range(10000)
]

# Measure serialization time
start = time.time()
for error in errors:
    serialize_rest_error(error)
end = time.time()

elapsed = end - start
print(f"Serialized 10,000 errors in {elapsed:.3f}s")
print(f"Average: {(elapsed / 10000) * 1000:.3f}ms per error")

# Should be < 1ms per error
assert elapsed < 10.0
print("✅ Serialization performance acceptable")
```

---

## Section 7: Troubleshooting

### Common Issues

**Issue 1: ImportError**

```
ImportError: cannot import name 'BaseError' from 'app.shared.errors'
```

**Fix:** Ensure PYTHONPATH includes project root:

```bash
export PYTHONPATH="${PYTHONPATH}:/path/to/project"
```

**Issue 2: Pydantic ValidationError on ErrorConfig**

```
ValidationError: 1 validation error for ErrorConfig
```

**Fix:** Check environment variables are set correctly:

```bash
env | grep ERROR_
env | grep APP_ENV
```

**Issue 3: Tests fail with "clear=True" error**
**Fix:** Updated tests to not use `clear=True` in `patch.dict(os.environ)`

---

## Section 8: Checklist

### Manual Testing Checklist

- [ ] Import all error classes successfully
- [ ] Create each exception type with required parameters
- [ ] Verify backward compatibility with ApplicationError
- [ ] Test REST API serialization format
- [ ] Test WebSocket serialization format
- [ ] Verify fatal error classification
- [ ] Verify recoverable error classification
- [ ] Verify log level determination (CRITICAL, ERROR, WARN, INFO)
- [ ] Test error configuration loading
- [ ] Test error context enrichment
- [ ] Run all unit tests successfully
- [ ] Test integration with FastAPI exception handler
- [ ] Test integration with existing modules (redis/locks.py)
- [ ] Verify WebSocket connection close behavior
- [ ] Test domain invariant violation (critical)
- [ ] Test proctoring violation (advisory)
- [ ] Verify serialization performance (<1ms per error)

---

## Section 9: Success Criteria

✅ **Module is working correctly when:**

1. All unit tests pass (176 tests)
2. All exception types can be created with correct error codes
3. REST and WebSocket serialization produce correct JSON
4. Fatal errors are classified correctly (AuthenticationError, AuthorizationError, etc.)
5. Log levels are assigned correctly (CRITICAL for domain invariants, ERROR for 5xx, WARN for 4xx)
6. Backward compatibility with ApplicationError works
7. Integration with existing modules (redis/locks.py) successful
8. Configuration loads correctly from environment variables
9. Error context enrichment works as errors propagate up the stack
10. Serialization performance is acceptable (<1ms per error)

---

## Section 10: Next Steps

After successful manual testing:

1. **Deploy to dev environment** - Test with real FastAPI application
2. **Integrate with interview module** - Test WebSocket error handling
3. **Monitor logs** - Verify structured logging works correctly
4. **Load test** - Verify performance under high error volume
5. **Update documentation** - Document any discovered edge cases

---

**End of Human Testing Guide**
