# Shared Errors - Unified Error Semantics

## 1. Purpose

The **errors** subdirectory provides:

- Structured error type hierarchy
- Error serialization for REST, WebSocket, WebRTC
- Fatal vs recoverable error distinction
- Error logging hooks
- Consistent error responses across all protocols

**Critical responsibility:** Unified error handling WITHOUT business logic.

---

## 2. Responsibilities

### 2.1 Error Type Hierarchy

**Must define structured error types:**

**Client Errors (4xx):**

- `AuthenticationError` (401) - Invalid or expired token
- `AuthorizationError` (403) - Insufficient permissions
- `ValidationError` (400) - Invalid request payload
- `NotFoundError` (404) - Resource not found
- `ConflictError` (409) - State conflict
- `RateLimitExceeded` (429) - Too many requests

**Server Errors (5xx):**

- `InfrastructureError` (500) - Redis/Postgres failure
- `AIProviderError` (502) - OpenAI/Anthropic error
- `SandboxExecutionError` (500) - Code execution failure
- `InternalServerError` (500) - Unknown error

**Domain Errors:**

- `DomainInvariantViolation` - Business rule violated (logged as 500)
- `ProctoringViolation` - Advisory proctor event (NOT punitive)

---

### 2.2 Error Structure

**All errors must include:**

```python
@dataclass
class BaseError(Exception):
    error_code: str           # Machine-readable code
    message: str              # Human-readable message
    request_id: Optional[str] # Trace correlation
    metadata: Optional[dict]  # Additional context
    http_status_code: int     # HTTP status (for REST)
```

**Example:**

```python
raise AuthenticationError(
    error_code="TOKEN_EXPIRED",
    message="Access token expired at 2026-02-14T10:00:00Z",
    request_id="req_abc123",
    metadata={"expired_at": "2026-02-14T10:00:00Z"},
    http_status_code=401
)
```

---

## 3. Error Type Definitions

### 3.1 Client Errors

**AuthenticationError (401)**

```python
class AuthenticationError(BaseError):
    """
    Raised when authentication fails.

    Examples:
    - Invalid token
    - Expired token
    - Missing token
    - Token signature invalid
    """
    def __init__(
        self,
        message: str = "Authentication failed",
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="AUTHENTICATION_FAILED",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=401
        )
```

---

**AuthorizationError (403)**

```python
class AuthorizationError(BaseError):
    """
    Raised when user lacks permission for resource.

    Examples:
    - Admin accessing another org's data
    - Candidate accessing admin endpoints
    - Insufficient role privilege
    """
    def __init__(
        self,
        message: str = "Insufficient permissions",
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="AUTHORIZATION_FAILED",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=403
        )
```

---

**ValidationError (400)**

```python
class ValidationError(BaseError):
    """
    Raised when request payload is invalid.

    Examples:
    - Missing required field
    - Invalid field type
    - Field value out of range
    - Malformed JSON
    """
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="VALIDATION_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=400
        )
```

---

**NotFoundError (404)**

```python
class NotFoundError(BaseError):
    """
    Raised when resource does not exist.

    Examples:
    - Submission not found
    - Question not found
    - Exchange not found
    """
    def __init__(
        self,
        resource_type: str,
        resource_id: Any,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="NOT_FOUND",
            message=f"{resource_type} with ID {resource_id} not found",
            request_id=request_id,
            metadata={"resource_type": resource_type, "resource_id": resource_id},
            http_status_code=404
        )
```

---

**ConflictError (409)**

```python
class ConflictError(BaseError):
    """
    Raised when operation conflicts with current state.

    Examples:
    - Interview already started
    - Submission already submitted
    - Duplicate active WebSocket connection
    """
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="CONFLICT",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=409
        )
```

---

**RateLimitExceeded (429)**

```python
class RateLimitExceeded(BaseError):
    """
    Raised when rate limit exceeded.

    Examples:
    - Too many API requests
    - Too many question generations
    - Too many sandbox executions
    """
    def __init__(
        self,
        limit: int,
        window_seconds: int,
        retry_after_seconds: int,
        request_id: Optional[str] = None
    ):
        super().__init__(
            error_code="RATE_LIMIT_EXCEEDED",
            message=f"Rate limit of {limit} requests per {window_seconds}s exceeded",
            request_id=request_id,
            metadata={
                "limit": limit,
                "window_seconds": window_seconds,
                "retry_after_seconds": retry_after_seconds
            },
            http_status_code=429
        )
```

---

### 3.2 Server Errors

**InfrastructureError (500)**

```python
class InfrastructureError(BaseError):
    """
    Raised when infrastructure component fails.

    Examples:
    - Redis connection timeout
    - Postgres connection failed
    - Qdrant unavailable
    """
    def __init__(
        self,
        component: str,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="INFRASTRUCTURE_ERROR",
            message=f"{component} error: {message}",
            request_id=request_id,
            metadata={"component": component, **(metadata or {})},
            http_status_code=500
        )
```

---

**AIProviderError (502)**

```python
class AIProviderError(BaseError):
    """
    Raised when AI provider (OpenAI, Anthropic) fails.

    Examples:
    - OpenAI timeout
    - OpenAI rate limit (429)
    - Claude unavailable
    """
    def __init__(
        self,
        provider: str,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="AI_PROVIDER_ERROR",
            message=f"{provider} error: {message}",
            request_id=request_id,
            metadata={"provider": provider, **(metadata or {})},
            http_status_code=502
        )
```

---

**SandboxExecutionError (500)**

```python
class SandboxExecutionError(BaseError):
    """
    Raised when code sandbox execution fails.

    Examples:
    - Execution timeout
    - Runtime error in candidate code
    - Memory limit exceeded
    """
    def __init__(
        self,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="SANDBOX_EXECUTION_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=500
        )
```

---

**InternalServerError (500)**

```python
class InternalServerError(BaseError):
    """
    Raised for unknown server errors.

    Catch-all for unexpected exceptions.
    """
    def __init__(
        self,
        message: str = "Internal server error",
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="INTERNAL_SERVER_ERROR",
            message=message,
            request_id=request_id,
            metadata=metadata,
            http_status_code=500
        )
```

---

### 3.3 Domain Errors

**DomainInvariantViolation**

```python
class DomainInvariantViolation(BaseError):
    """
    Raised when business invariant is violated.

    Examples:
    - Template recalculated at runtime (must be immutable)
    - Exchange mutated after creation (must be immutable)
    - Submission state transition invalid

    NOTE: This is a 500 error (indicates system bug, not user error).
    """
    def __init__(
        self,
        invariant: str,
        message: str,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="DOMAIN_INVARIANT_VIOLATION",
            message=f"Invariant '{invariant}' violated: {message}",
            request_id=request_id,
            metadata={"invariant": invariant, **(metadata or {})},
            http_status_code=500
        )
```

---

**ProctoringViolation**

```python
class ProctoringViolation(BaseError):
    """
    Raised (or logged) when proctoring event detected.

    Examples:
    - Face not visible
    - Multiple faces detected
    - Audio silence detected

    NOTE: This is ADVISORY only, NOT punitive.
    System must NOT auto-fail interview on this error.

    Typically logged, not raised (non-blocking).
    """
    def __init__(
        self,
        event_type: str,
        message: str,
        risk_score: float,
        request_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ):
        super().__init__(
            error_code="PROCTORING_VIOLATION",
            message=message,
            request_id=request_id,
            metadata={
                "event_type": event_type,
                "risk_score": risk_score,
                **(metadata or {})
            },
            http_status_code=200  # Not an error response, just an event
        )
```

---

## 4. Error Serialization

### 4.1 REST Error Serialization

**Format:**

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable message",
    "request_id": "req_abc123",
    "metadata": {
      "key": "value"
    }
  }
}
```

**Implementation:**

```python
def serialize_rest_error(
    error: BaseError,
    request_id: Optional[str] = None
) -> dict:
    """
    Serialize error for REST API response.
    """
    return {
        "error": {
            "code": error.error_code,
            "message": error.message,
            "request_id": request_id or error.request_id,
            **({"metadata": error.metadata} if error.metadata else {})
        }
    }
```

**FastAPI exception handler:**

```python
@app.exception_handler(BaseError)
async def base_error_handler(request: Request, exc: BaseError):
    """
    Global exception handler for all BaseError subclasses.
    """
    request_id = request.state.request_id

    # Log error
    logger.error(
        f"Request failed: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "message": exc.message,
            "metadata": exc.metadata
        }
    )

    # Serialize response
    response_body = serialize_rest_error(exc, request_id)

    return JSONResponse(
        status_code=exc.http_status_code,
        content=response_body
    )
```

---

### 4.2 WebSocket Error Serialization

**Format:**

```json
{
  "event": "error",
  "payload": {
    "code": "ERROR_CODE",
    "message": "Human-readable message"
  }
}
```

**Implementation:**

```python
def serialize_websocket_error(error: BaseError) -> dict:
    """
    Serialize error for WebSocket event.

    Omits request_id (use connection_id for tracing).
    """
    return {
        "event": "error",
        "payload": {
            "code": error.error_code,
            "message": error.message,
            **({"metadata": error.metadata} if error.metadata else {})
        }
    }
```

---

### 4.3 Fatal vs Recoverable Errors

**Fatal errors (close WebSocket connection):**

- `AuthenticationError` (invalid token → cannot continue)
- `AuthorizationError` (insufficient permissions → cannot continue)
- `DomainInvariantViolation` (system bug → unsafe to continue)

**Recoverable errors (send event, keep connection):**

- `ValidationError` (invalid answer format → user can retry)
- `NotFoundError` (question not found → can retry)
- `ConflictError` (already paused → can resume)
- `ProctoringViolation` (advisory only → non-blocking)

**WebSocket error handler:**

```python
async def handle_websocket_error(
    websocket: WebSocket,
    error: BaseError,
    connection_id: str
):
    """
    Handle WebSocket error (fatal or recoverable).
    """
    # Send error event
    await websocket.send_json(serialize_websocket_error(error))

    # Log
    logger.warning(
        f"WebSocket error: {error.error_code}",
        extra={
            "connection_id": connection_id,
            "error_code": error.error_code,
            "is_fatal": is_fatal_error(error)
        }
    )

    # Close if fatal
    if is_fatal_error(error):
        await websocket.close(code=1008, reason=error.error_code)


def is_fatal_error(error: BaseError) -> bool:
    """
    Determine if error is fatal (requires connection close).
    """
    fatal_types = (
        AuthenticationError,
        AuthorizationError,
        DomainInvariantViolation
    )

    return isinstance(error, fatal_types)
```

---

## 5. Error Logging

### 5.1 Logging Strategy

**Client errors (4xx):** Log at WARN level (user error, not system error)

```python
logger.warning(
    "Client error",
    extra={
        "error_code": error.error_code,
        "http_status": error.http_status_code,
        "request_id": request_id
    }
)
```

**Server errors (5xx):** Log at ERROR level (system error, requires investigation)

```python
logger.error(
    "Server error",
    extra={
        "error_code": error.error_code,
        "http_status": error.http_status_code,
        "request_id": request_id
    }
)
```

**Domain invariant violations:** Log at CRITICAL level (system bug, immediate fix required)

```python
logger.critical(
    "Domain invariant violated",
    extra={
        "invariant": error.metadata["invariant"],
        "message": error.message,
        "request_id": request_id
    }
)
```

---

### 5.2 Error Context

**Every error log must include:**

- `timestamp` (ISO 8601)
- `level` (WARN, ERROR, CRITICAL)
- `error_code` (machine-readable)
- `message` (human-readable)
- `request_id` (trace correlation)
- `user_id` (if available)
- `submission_id` (if available)
- `http_status_code` (if REST)
- `metadata` (additional context)

**Example:**

```json
{
  "timestamp": "2026-02-14T10:00:00.123Z",
  "level": "ERROR",
  "error_code": "AI_PROVIDER_ERROR",
  "message": "OpenAI timeout after 5 seconds",
  "request_id": "req_abc123",
  "user_id": 42,
  "submission_id": 789,
  "http_status_code": 502,
  "metadata": {
    "provider": "openai",
    "model": "gpt-4",
    "timeout_seconds": 5
  }
}
```

---

## 6. Error Propagation

### 6.1 Error Context Enrichment

**Errors should be enriched as they propagate up the stack:**

```python
# Low-level (database)
try:
    db.query(...)
except DBException as e:
    raise InfrastructureError(
        component="postgres",
        message=str(e),
        metadata={"query": "SELECT ..."}
    )

# Mid-level (repository)
try:
    question = question_repo.get_by_id(question_id)
except InfrastructureError as e:
    # Re-raise with additional context
    e.metadata["question_id"] = question_id
    raise

# High-level (API)
try:
    question = question_service.get(question_id)
except InfrastructureError as e:
    # Add request context
    e.request_id = request.state.request_id
    raise
```

---

## 7. Business Logic Constraints

### 7.1 What Errors Module MUST NOT Do

❌ **Implement validation logic:**

```python
# WRONG: Business logic in error module
class ValidationError:
    def validate_answer(self, answer: str):
        if len(answer) < 10:
            raise ValidationError("Answer too short")
```

✅ **Only define error types:**

```python
# CORRECT: Error module only defines error
class ValidationError(BaseError):
    pass

# Validation logic belongs in domain module
def validate_answer(answer: str):
    if len(answer) < 10:
        raise ValidationError("Answer too short")
```

---

❌ **Implement RBAC checks:**

```python
# WRONG: Authorization logic in error module
class AuthorizationError:
    def check_permission(self, user, resource):
        if user.role != 'admin':
            raise AuthorizationError("Not admin")
```

✅ **Only define error type:**

```python
# CORRECT: Error module only defines error
class AuthorizationError(BaseError):
    pass

# RBAC logic belongs in auth module
def check_permission(user, resource):
    if not has_permission(user, resource):
        raise AuthorizationError("Insufficient permissions")
```

---

## 8. Testing Requirements

### 8.1 Error Creation Tests

**Test: Error includes all required fields**

```python
def test_error_structure():
    error = AuthenticationError(
        message="Token expired",
        request_id="req_123",
        metadata={"expired_at": "2026-02-14T10:00:00Z"}
    )

    assert error.error_code == "AUTHENTICATION_FAILED"
    assert error.message == "Token expired"
    assert error.request_id == "req_123"
    assert error.http_status_code == 401
    assert error.metadata["expired_at"] == "2026-02-14T10:00:00Z"
```

---

### 8.2 Serialization Tests

**Test: REST error format**

```python
def test_rest_error_serialization():
    error = ValidationError(
        message="Invalid field",
        request_id="req_123"
    )

    serialized = serialize_rest_error(error)

    assert serialized == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid field",
            "request_id": "req_123"
        }
    }
```

**Test: WebSocket error format**

```python
def test_websocket_error_serialization():
    error = ConflictError(
        message="Interview already started"
    )

    serialized = serialize_websocket_error(error)

    assert serialized == {
        "event": "error",
        "payload": {
            "code": "CONFLICT",
            "message": "Interview already started"
        }
    }
```

---

### 8.3 Fatal Error Tests

**Test: Authentication error is fatal**

```python
def test_authentication_error_is_fatal():
    error = AuthenticationError("Invalid token")

    assert is_fatal_error(error) == True
```

**Test: Validation error is recoverable**

```python
def test_validation_error_is_recoverable():
    error = ValidationError("Invalid field")

    assert is_fatal_error(error) == False
```

---

## 9. Configuration

### 9.1 ErrorConfig

```python
@dataclass
class ErrorConfig:
    # Logging
    log_client_errors: bool = True  # Log 4xx errors
    log_server_errors: bool = True  # Log 5xx errors

    # Serialization
    include_error_metadata_in_response: bool = True
    include_stack_trace_in_dev: bool = True
    include_stack_trace_in_prod: bool = False

    # WebSocket
    send_error_event_on_recoverable: bool = True
    close_connection_on_fatal: bool = True
    websocket_close_code_fatal: int = 1008  # Policy Violation
```

---

## 10. Observability

### 10.1 Metrics

**Must expose:**

- `errors_total` (counter with labels: error_code, http_status) - Total errors
- `fatal_errors_total` (counter with label: error_code) - Fatal WebSocket errors
- `recoverable_errors_total` (counter with label: error_code) - Recoverable errors

---

### 10.2 Logging

**Must log (WARN level):**

- Client error occurred (error_code, http_status, request_id)

**Must log (ERROR level):**

- Server error occurred (error_code, http_status, request_id)
- Infrastructure error (component, message, request_id)
- AI provider error (provider, message, request_id)

**Must log (CRITICAL level):**

- Domain invariant violation (invariant, message, request_id)

---

## 11. Critical Risks

1. **Business logic leak:** Validation/RBAC in error module → architectural violation
2. **Sensitive data in error message:** Token/password in message → security breach
3. **Missing request_id:** Errors without request_id → untraceable failures
4. **Inconsistent serialization:** REST vs WebSocket format mismatch → client confusion
5. **Fatal error misclassification:** Validation as fatal → unnecessary disconnects
6. **Error suppression:** Catching BaseError without re-raise → silent failures

---

## 12. Acceptance Criteria

**Errors module is complete when:**

✅ All error types defined (client, server, domain)
✅ Error structure consistent (error_code, message, request_id, metadata)
✅ REST serialization working (JSON format)
✅ WebSocket serialization working (event format)
✅ Fatal vs recoverable distinction working
✅ Error logging working (WARN/ERROR/CRITICAL levels)
✅ Error context enrichment working (propagation up stack)
✅ No business logic present (pure error definitions)
✅ All tests passing (creation, serialization, fatal classification)

---

**End of Shared Errors Requirements**
