# Shared - Cross-Cutting Infrastructure Primitives

## 1. Purpose

The **shared** module provides minimal cross-module primitives for:

- Unified error semantics (REST, WebSocket, WebRTC)
- Identity and tenant context propagation
- Structured logging, tracing, and metrics
- Connection lifecycle management (WebSocket, WebRTC)

**Critical constraint:** This module must remain EXTREMELY SMALL and contain ZERO business logic.

**Architectural role:** Cross-cutting infrastructure spine. NOT a dumping ground.

---

## 2. Module Constraints

### 2.1 What Shared MUST Be

✅ Dependency-safe (importable by all modules)
✅ Business-logic free (no domain rules)
✅ Minimal and stable (< 2,000 lines total)
✅ Cross-cutting only (errors, identity, observability)

---

### 2.2 What Shared MUST NOT Be

❌ Import interview module (circular dependency)
❌ Import evaluation module (circular dependency)
❌ Import question module (circular dependency)
❌ Import admin module (circular dependency)
❌ Import coding module (circular dependency)
❌ Contain feature logic (scoring, adaptation, selection)
❌ Contain business rules (RBAC, templates, rubrics)
❌ Grow uncontrolled (strict size budget)

**If shared imports domain modules → architectural failure.**

---

## 3. Module Structure

```
shared/
├── REQUIREMENTS.md (this file)
├── errors/
│   └── REQUIREMENTS.md
├── auth_context/
│   └── REQUIREMENTS.md
└── observability/
    └── REQUIREMENTS.md
```

**Total subdirectories:** 3
**Expected total lines:** ~1,800-2,000 (strict budget)

---

## 4. Subdirectory Responsibilities

### 4.1 errors/

**Purpose:** Unified error semantics across REST, WebSocket, WebRTC

**Provides:**

- Structured error types (AuthenticationError, ValidationError, etc.)
- Error serialization (REST JSON, WebSocket event format)
- Fatal vs recoverable error distinction
- Error logging hooks

**Must NOT:**

- Contain business validation logic (belongs in domain modules)
- Contain RBAC decisions (belongs in auth module)
- Contain template rules (belongs in interview module)

---

### 4.2 auth_context/

**Purpose:** Identity and tenant context propagation

**Provides:**

- IdentityContext object (user_id, organization_id, user_type)
- Request-scoped injection (REST middleware, WebSocket connection binding)
- Tenant resolution (organization_id enforcement)
- Context propagation to async tasks

**Must NOT:**

- Implement JWT validation (belongs in auth module)
- Implement RBAC checks (belongs in auth module)
- Contain permission logic (belongs in auth module)

---

### 4.3 observability/

**Purpose:** Structured logging, distributed tracing, metrics instrumentation

**Provides:**

- Structured logging (request_id, user_id, submission_id correlation)
- Trace correlation (request_id, connection_id propagation)
- Metrics instrumentation (counters, histograms, gauges)
- AI telemetry hooks (model, tokens, latency, cost)
- Sensitive data redaction (tokens, passwords, hidden test cases)

**Must NOT:**

- Contain business event logic (belongs in domain modules)
- Implement analytics aggregation (belongs in analytics service)
- Store metrics (only expose, storage is Prometheus/Grafana)

---

## 5. Cross-Protocol Support

### 5.1 REST API

**Shared must support:**

- Error responses (structured JSON format)
- Identity injection (request.state.identity)
- Request ID propagation (X-Request-ID header)
- Structured logging (request/response metadata)
- Metrics (request count, latency, status codes)

---

### 5.2 WebSocket

**Shared must support:**

- Connection identity binding (authenticate on connect)
- Connection registry (track active connections by submission_id)
- Error events (non-fatal continue connection, fatal close)
- Connection ID tracing (correlate events to connection)
- Disconnect handling (cleanup locks, emit event)

**Critical for interview module:**

- Prevent duplicate active sessions (one candidate, one submission, one connection)
- Persist identity across reconnects (grace period for token refresh)
- Clear Redis locks on disconnect (prevent orphaned locks)

---

### 5.3 WebRTC

**Shared must support:**

- Signaling channel identity validation
- Session binding to submission_id
- Ephemeral session tracking (short-lived, peer-to-peer)
- Identity propagation to audio/proctoring modules

**Must enforce:**

- No media stream without verified identity
- Session validated before stream establishment

---

## 6. Multi-Tenant Isolation

### 6.1 Tenant Context

**IdentityContext must include:**

- `organization_id` (required for admin users, null for candidates)
- `user_type` (admin or candidate)
- `user_id` (UUID or integer)
- `candidate_id` (if user_type=candidate)
- `admin_role` (if user_type=admin)
- `token_version` (for revocation)

---

### 6.2 Enforcement

**Shared must enforce at context level:**

- Admin requests MUST include organization_id (from JWT)
- Candidate requests scoped to own candidate_id
- No cross-tenant context resolution (no query params)

**Shared must NOT enforce:**

- Fine-grained RBAC (belongs in auth module)
- Resource ownership checks (belongs in domain modules)

---

## 7. Connection Lifecycle Management

### 7.1 WebSocket Connection Registry

**Purpose:** Track active WebSocket connections for real-time interview

**Must provide:**

```python
class ConnectionRegistry:
    def register(connection_id: str, submission_id: int, identity: Identity)
    def unregister(connection_id: str)
    def get_connection(submission_id: int) -> Optional[Connection]
    def is_active(submission_id: int) -> bool
```

**Must prevent:**

- Duplicate connections for same submission_id (reject new if active exists)
- Memory leaks (cleanup on disconnect)
- Stale entries (TTL or heartbeat)

---

### 7.2 Disconnect Handling

**On WebSocket disconnect (graceful or ungraceful):**

1. Clear connection from registry
2. Release Redis lock (if held)
3. Emit disconnect event (for audit)
4. Log disconnect reason (timeout, client close, error)

**Must NOT:**

- Auto-pause interview (belongs in interview module)
- Trigger evaluation (belongs in evaluation module)

---

## 8. Security Constraints

### 8.1 Token Handling

**Shared must NOT:**

- Parse JWT tokens (belongs in auth module)
- Validate JWT signatures (belongs in auth module)
- Store raw tokens (only validated identity)

**Shared MUST:**

- Accept pre-validated IdentityContext (from auth middleware)
- Clear identity on logout/disconnect

---

### 8.2 Sensitive Data Protection

**Shared must redact:**

- Access tokens (never log)
- Refresh tokens (never log)
- Passwords (never log)
- Hidden test case expected_output (never log)
- Candidate answers (optional redaction via config)

**Logging format:**

```json
{
  "access_token": "[REDACTED]",
  "candidate_answer": "[REDACTED_ANSWER]"
}
```

---

### 8.3 Environment Isolation

**Shared must NOT:**

- Read `os.environ` directly (use config module)
- Access Redis directly without context (use persistence module clients)
- Hardcode secrets (load from config/vault)

---

## 9. Observability Requirements

### 9.1 Structured Logging

**Every log entry must include:**

- `timestamp` (ISO 8601)
- `level` (DEBUG, INFO, WARN, ERROR)
- `request_id` (correlation)
- `user_id` (if available)
- `submission_id` (if available)
- `organization_id` (if available)
- `event_type` (descriptive name)
- `latency_ms` (for timed operations)

**Example:**

```json
{
  "timestamp": "2026-02-14T10:00:00.123Z",
  "level": "INFO",
  "request_id": "req_abc123",
  "user_id": 42,
  "submission_id": 789,
  "organization_id": 1,
  "event_type": "interview_exchange_created",
  "latency_ms": 45,
  "message": "Exchange created successfully"
}
```

---

### 9.2 Distributed Tracing

**Request ID propagation:**

- REST: Extract from `X-Request-ID` header (generate if missing)
- WebSocket: Assign `connection_id` on connect (include in all events)
- WebRTC: Assign `session_id` on signaling start
- Async tasks: Propagate `request_id` from caller

**Correlation ID:**

- Optional `correlation_id` for multi-request flows (e.g., submission → multiple exchanges)

---

### 9.3 Metrics Instrumentation

**Must expose metrics for:**

**Interview metrics:**

- `interview_duration_seconds` (histogram) - Total interview time
- `interview_exchanges_total` (counter) - Total exchanges created
- `interview_pauses_total` (counter) - Total pause events

**Question metrics:**

- `question_generation_duration_seconds` (histogram) - LLM latency
- `question_retrieval_duration_seconds` (histogram) - Qdrant search latency
- `question_selection_fallback_total` (counter) - Fallback strategies used

**Evaluation metrics:**

- `evaluation_duration_seconds` (histogram) - Scoring latency
- `evaluation_rubric_score_distribution` (histogram) - Score distribution

**Sandbox metrics:**

- `sandbox_execution_duration_seconds` (histogram) - Code execution time
- `sandbox_timeout_total` (counter) - Execution timeouts
- `sandbox_error_total` (counter with label: error_type) - Execution errors

**Proctoring metrics:**

- `proctoring_event_total` (counter with label: event_type) - Event frequency
- `proctoring_risk_score_distribution` (histogram) - Risk score distribution
- `proctoring_silence_detected_total` (counter) - Audio silence events

**Audio metrics:**

- `audio_chunk_received_total` (counter) - Audio chunks processed
- `audio_transcription_latency_seconds` (histogram) - Transcription latency

**WebSocket metrics:**

- `websocket_connections_active` (gauge) - Active connections
- `websocket_reconnects_total` (counter) - Reconnect events
- `websocket_disconnect_total` (counter with label: reason) - Disconnect reasons

**AI metrics:**

- `ai_provider_calls_total` (counter with label: provider, model) - LLM calls
- `ai_provider_latency_seconds` (histogram with label: provider) - LLM latency
- `ai_provider_tokens_total` (counter with label: provider, type) - Token usage
- `ai_provider_cost_usd_total` (counter with label: provider) - Estimated cost
- `ai_provider_errors_total` (counter with label: provider, error_type) - LLM errors

---

### 9.4 AI Telemetry Hooks

**For every LLM call, log:**

- `model_id` (e.g., "gpt-4", "claude-3-opus")
- `tokens_in` (prompt tokens)
- `tokens_out` (completion tokens)
- `latency_ms` (API call duration)
- `cost_estimate_usd` (calculated cost)
- `success` (boolean)
- `error_type` (if failed)

**Must NOT log in production:**

- Full prompt (security risk, contains resume/JD)
- Full response (may contain sensitive generated content)

**MAY log in development (with config flag):**

- Masked prompt (first 100 chars)
- Response schema (not content)

---

## 10. Error Handling Strategy

### 10.1 Error Categories

**Shared defines error taxonomy:**

1. **Client Errors (4xx):**
   - `AuthenticationError` (401) - Invalid or expired token
   - `AuthorizationError` (403) - Valid token but insufficient permissions
   - `ValidationError` (400) - Invalid request payload
   - `NotFoundError` (404) - Resource not found
   - `ConflictError` (409) - State conflict (e.g., interview already started)
   - `RateLimitExceeded` (429) - Too many requests

2. **Server Errors (5xx):**
   - `InfrastructureError` (500) - Redis/Postgres failure
   - `AIProviderError` (502) - OpenAI/Anthropic timeout or error
   - `SandboxExecutionError` (500) - Code execution failure
   - `InternalServerError` (500) - Unknown server error

3. **Domain Errors:**
   - `DomainInvariantViolation` - Business rule violated (e.g., template immutability broken)
   - `ProctoringViolation` - Advisory proctor event (NOT punitive)

---

### 10.2 Error Serialization

**REST format:**

```json
{
  "error": {
    "code": "AUTHENTICATION_FAILED",
    "message": "Access token expired",
    "request_id": "req_abc123",
    "metadata": {
      "expired_at": "2026-02-14T10:00:00Z"
    }
  }
}
```

**WebSocket format:**

```json
{
  "event": "error",
  "payload": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid answer format"
  }
}
```

**WebSocket error behavior:**

- **Recoverable errors:** Send error event, keep connection open
- **Fatal errors:** Send error event, close connection (code 1008)

---

## 11. Context Propagation to Async Tasks

### 11.1 Background Task Context

**When triggering async tasks (evaluation, sandbox execution):**

**Must propagate:**

- `request_id` (for tracing)
- `user_id` (for audit)
- `submission_id` (for association)
- `organization_id` (for multi-tenancy)

**Implementation pattern:**

```python
@celery.task
def evaluate_exchange_async(
    exchange_id: int,
    context: dict  # Serialized context
):
    # Restore context
    request_id = context.get("request_id")
    user_id = context.get("user_id")

    # Log with context
    logger.info(
        "Evaluating exchange",
        extra={
            "request_id": request_id,
            "user_id": user_id,
            "exchange_id": exchange_id
        }
    )

    # Execute task
    ...
```

---

## 12. WebSocket-Specific Requirements

### 12.1 Connection Authentication

**On WebSocket connect:**

1. Extract access token (query param or header)
2. Validate token (auth module)
3. Build IdentityContext (shared module)
4. Register connection (shared connection registry)
5. Reject if duplicate active session

**On WebSocket disconnect:**

1. Unregister connection
2. Clear Redis lock (interview module)
3. Emit disconnect event
4. Log reason (timeout, client close, error)

---

### 12.2 Token Expiry Handling

**Option 1: Grace period (recommended)**

- Allow 5-minute grace period for token refresh
- Send warning event at T-60 seconds
- Close connection at expiry + grace period

**Option 2: Immediate close**

- Close connection on token expiry
- Client must reconnect with new token

**Must log:**

- Token expiry events
- Reconnect with fresh token

---

### 12.3 Connection Heartbeat

**Purpose:** Detect stale connections

**Implementation:**

- Server sends ping every 30 seconds
- Client responds with pong
- Close connection if no pong after 60 seconds

**Must emit:**

- `websocket_heartbeat_missed` (counter)
- `websocket_heartbeat_timeout_disconnect` (counter)

---

## 13. WebRTC-Specific Requirements

### 13.1 Signaling Validation

**WebRTC is peer-to-peer, but signaling must be authenticated:**

**On signaling start:**

1. Validate identity (same as WebSocket)
2. Bind session to submission_id
3. Create ephemeral session record
4. Propagate identity to audio/proctoring modules

**Must enforce:**

- No media stream without verified identity
- Session validated before ICE negotiation

---

### 13.2 Session Lifecycle

**Session states:**

- `pending` - Signaling in progress
- `established` - Media stream active
- `closed` - Session ended

**On session close:**

- Clean up ephemeral session
- Emit session_ended event

---

## 14. Testing Requirements

### 14.1 Error Serialization Tests

**Test: REST error format consistent**

```python
def test_rest_error_format():
    error = AuthenticationError("Token expired")
    response = serialize_rest_error(error, request_id="req_123")

    assert response == {
        "error": {
            "code": "AUTHENTICATION_FAILED",
            "message": "Token expired",
            "request_id": "req_123"
        }
    }
```

**Test: WebSocket error format consistent**

```python
def test_websocket_error_format():
    error = ValidationError("Invalid payload")
    event = serialize_websocket_error(error)

    assert event == {
        "event": "error",
        "payload": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid payload"
        }
    }
```

---

### 14.2 Identity Injection Tests

**Test: REST identity injection**

```python
def test_rest_identity_injection():
    request = create_mock_request(user_id=42, organization_id=1)
    identity = extract_identity(request)

    assert identity.user_id == 42
    assert identity.organization_id == 1
```

**Test: WebSocket identity binding**

```python
def test_websocket_identity_binding():
    connection = create_mock_websocket_connection(token="valid_token")
    identity = bind_identity(connection)

    assert identity.user_id == 42
    assert connection.identity == identity
```

---

### 14.3 Connection Registry Tests

**Test: Duplicate connection rejected**

```python
def test_duplicate_connection_rejected():
    registry.register(connection_id="conn1", submission_id=123, identity=identity1)

    with pytest.raises(ConflictError, match="Active connection already exists"):
        registry.register(connection_id="conn2", submission_id=123, identity=identity2)
```

**Test: Disconnect cleanup**

```python
def test_disconnect_cleanup():
    registry.register(connection_id="conn1", submission_id=123, identity=identity)

    registry.unregister(connection_id="conn1")

    assert not registry.is_active(submission_id=123)
```

---

### 14.4 Tracing Tests

**Test: Request ID propagation**

```python
def test_request_id_propagated():
    request = create_mock_request(headers={"X-Request-ID": "req_abc"})

    request_id = extract_request_id(request)

    assert request_id == "req_abc"
```

**Test: Connection ID assigned**

```python
def test_connection_id_assigned():
    connection = create_mock_websocket_connection()

    connection_id = assign_connection_id(connection)

    assert connection_id.startswith("conn_")
```

---

### 14.5 Redaction Tests

**Test: Token redacted from logs**

```python
def test_token_redacted():
    data = {"access_token": "secret_token_123", "user_id": 42}

    redacted = redact_sensitive_data(data)

    assert redacted["access_token"] == "[REDACTED]"
    assert redacted["user_id"] == 42
```

**Test: Hidden test case redacted**

```python
def test_hidden_test_case_redacted():
    data = {
        "test_case": {
            "input": "[1,2,3]",
            "expected_output": "6",
            "is_hidden": True
        }
    }

    redacted = redact_sensitive_data(data)

    assert redacted["test_case"]["expected_output"] == "[REDACTED]"
```

---

## 15. Configuration

### 15.1 SharedConfig

```python
@dataclass
class SharedConfig:
    # Logging
    log_level: str = "INFO"
    enable_structured_logging: bool = True
    enable_sensitive_redaction: bool = True
    log_candidate_answers: bool = False  # Privacy setting

    # Tracing
    enable_distributed_tracing: bool = True
    trace_sample_rate: float = 1.0  # 100% in production, adjust for cost

    # Metrics
    enable_metrics: bool = True
    metrics_port: int = 9090

    # WebSocket
    websocket_heartbeat_interval_seconds: int = 30
    websocket_heartbeat_timeout_seconds: int = 60
    websocket_duplicate_connection_policy: str = "reject"  # or "replace"

    # Token expiry
    token_expiry_grace_period_seconds: int = 300  # 5 minutes

    # Connection registry
    connection_registry_ttl_seconds: int = 3600  # 1 hour

    # AI telemetry
    enable_ai_telemetry: bool = True
    log_ai_prompts_in_dev: bool = True
    log_ai_prompts_in_prod: bool = False
```

---

## 16. Observability

### 16.1 Metrics

**Module-level metrics:**

- `shared_errors_total` (counter with label: error_type) - Total errors
- `shared_identity_injections_total` (counter with label: protocol) - Identity injections
- `shared_connection_registry_size` (gauge) - Active connections

---

### 16.2 Logging

**Must log (INFO level):**

- Identity injected (protocol, user_id, organization_id)
- Connection registered (connection_id, submission_id)
- Connection unregistered (connection_id, reason)
- Request ID assigned (request_id)

**Must log (WARN level):**

- Token expiry approaching (user_id, expires_at)
- Duplicate connection attempt (submission_id, action)
- Heartbeat missed (connection_id, count)

**Must log (ERROR level):**

- Identity injection failed (reason)
- Connection registry error (operation, error_message)
- Sensitive data leaked to logs (CRITICAL - indicates bug)

---

## 17. Critical Risks

1. **Shared becomes dumping ground:** Business logic leaks in → architectural failure
2. **Circular imports:** Shared imports domain modules → import deadlock
3. **Token leakage:** Raw tokens logged → security breach
4. **Connection registry memory leak:** Stale connections not cleaned → OOM
5. **Cross-tenant context leak:** organization_id not enforced → data breach
6. **Hidden test case exposure:** Expected outputs logged → candidate cheating
7. **Identity mismatch:** WebSocket identity not bound correctly → authorization bypass

---

## 18. Acceptance Criteria

**Shared module is complete when:**

✅ Three subdirectories implemented (errors, auth_context, observability)
✅ Error serialization consistent (REST, WebSocket, WebRTC)
✅ Identity injection working (REST, WebSocket, WebRTC)
✅ Connection registry working (register, unregister, duplicate detection)
✅ Disconnect cleanup working (clear locks, emit events)
✅ Request ID propagation working (REST, WebSocket, async tasks)
✅ Structured logging working (all required fields)
✅ Sensitive data redaction working (tokens, passwords, test cases)
✅ Metrics instrumentation working (all protocol types)
✅ AI telemetry hooks working (model, tokens, latency, cost)
✅ Multi-tenant isolation enforced (organization_id context)
✅ No business logic present (pure infrastructure)
✅ No circular imports (importable by all modules)
✅ Size budget respected (< 2,000 lines total)
✅ All tests passing (error, identity, tracing, redaction)

---

## 19. SRS Compliance

**Shared module supports:**

- **NFR-2:** "AI-generated response within 5 seconds" ✅ (AI telemetry tracks latency)
- **NFR-4:** "REST API 99.9% uptime" ✅ (Metrics expose availability)
- **NFR-5:** "WebSocket 99.5% uptime" ✅ (Connection registry, heartbeat, metrics)
- **NFR-6:** "WebRTC 95% connection success" ✅ (Session tracking, metrics)
- **NFR-11:** "Structured logs for events" ✅ (Observability module)
- **NFR-12:** "Log correlation across modules" ✅ (Request ID propagation)
- **NFR-13:** "Multi-tenant data isolation" ✅ (Identity context enforcement)

---

**End of Shared Core Module Requirements**
