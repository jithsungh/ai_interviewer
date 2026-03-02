# Proctoring Ingestion - Event Intake & Validation

## 1. Purpose

The **ingestion** subdirectory handles:

- Receiving proctoring events from live interview sessions
- Validating event structure and content
- Attaching tenant isolation metadata (organization_id)
- Rate limiting to prevent abuse
- Batch event processing
- Event deduplication

**Critical responsibility:** Lightweight, non-blocking event intake that never disrupts the interview flow.

---

## 2. Responsibilities

### 2.1 Event Reception

**Provides:**

- WebSocket event handler for real-time events (tab switches, blur events)
- REST API endpoint for batch event submission
- Streaming ingestion support (future: Kafka, RabbitMQ)

**Must:**

- Accept events asynchronously (non-blocking)
- Return acknowledgment immediately (< 50ms)
- Queue events for background processing
- Handle network reconnection gracefully

**Must NOT:**

- Block interview flow if ingestion fails
- Require synchronous processing
- Drop events silently (log failures)

---

### 2.2 Event Validation

**Must validate:**

1. **Required fields:**
   - `submission_id` (valid UUID or integer)
   - `event_type` (must be in allowed list)
   - `timestamp` (ISO 8601 format, within reasonable time window)

2. **Optional fields:**
   - `metadata` (valid JSON, max 10KB)
   - `client_info` (browser, OS, device)
   - `confidence_score` (0.0 - 1.0 for ML-based detections)

3. **Business constraints:**
   - Submission must exist and be active (status = 'in_progress')
   - Timestamp not in future (allow 5 minute clock skew)
   - Event type supported (see allowed event types)

**Reject invalid events with:**

- HTTP 400 Bad Request (REST)
- WebSocket error frame with reason
- Detailed error message (never expose internal IDs to client)

---

### 2.3 Tenant Isolation Attachment

**Must:**

- Resolve submission_id → interview_submission → organization_id
- Attach organization_id to event before storage
- Verify requester has access to submission (JWT validation)

**Query:**

```sql
SELECT organization_id
FROM interview_submissions
WHERE id = ? AND status = 'in_progress'
```

**If submission not found or not active:**

- Reject event with 404 Not Found

---

### 2.4 Rate Limiting

**Must enforce:**

- Max events per submission per minute (default: 100)
- Max events per IP per minute (default: 500)
- Max batch size (default: 50 events)

**Rate limit exceeded:**

- Return 429 Too Many Requests
- Include retry-after header (seconds)
- Log rate limit violation (WARN level)

**Implementation:**

- Use Redis counters with sliding window: `rate_limit:proctoring:{submission_id}:{minute}` TTL 60s
- Increment on each event
- Reject if counter >= threshold

---

### 2.5 Event Deduplication

**Must detect:**

- Exact duplicate events (same submission_id, event_type, timestamp)
- Replay attacks (event_id submitted multiple times)

**Implementation:**

- Generate event fingerprint: `hash(submission_id + event_type + timestamp + metadata_hash)`
- Store in Redis set: `proctoring:dedup:{submission_id}` TTL 300s (5 minutes)
- If fingerprint exists → reject as duplicate (idempotent acknowledgment)

**Note:** Legitimate repeated events (e.g., multiple tab switches) have different timestamps → allowed.

---

## 3. Supported Event Types

**Allowed event types (validated against enum):**

### 3.1 Tab/Window Events

- `tab_switch`
- `window_blur`
- `window_focus_lost`

### 3.2 Screen Recording Events

- `screen_recording_started`
- `screen_recording_stopped`

### 3.3 Face Detection Events

- `face_absent`
- `multiple_faces`

### 3.4 Audio Anomaly Events

- `multiple_voices`
- `background_noise_spike`

### 3.5 Device Events

- `camera_disabled`
- `microphone_disabled`
- `device_change`

**Any other event type → reject with 400 Bad Request.**

---

## 4. Event Schema

### 4.1 Input Format (Client → Server)

**WebSocket frame:**

```json
{
  "type": "proctoring_event",
  "data": {
    "submission_id": "12345",
    "event_type": "tab_switch",
    "timestamp": "2026-02-14T10:30:15.234Z",
    "metadata": {
      "tab_title": "[REDACTED]",
      "previous_focus_duration": 45.3,
      "device_info": {
        "browser": "Chrome 120",
        "os": "Windows 11"
      }
    }
  }
}
```

**REST API endpoint:**

```http
POST /api/proctoring/events
Content-Type: application/json
Authorization: Bearer <JWT>

{
  "submission_id": 12345,
  "event_type": "multiple_faces",
  "timestamp": "2026-02-14T10:31:22.567Z",
  "metadata": {
    "faces_detected": 2,
    "confidence": 0.95,
    "frame_number": 1823
  }
}
```

**Batch ingestion:**

```http
POST /api/proctoring/events/batch
Content-Type: application/json
Authorization: Bearer <JWT>

{
  "submission_id": 12345,
  "events": [
    {
      "event_type": "tab_switch",
      "timestamp": "2026-02-14T10:30:15.234Z",
      "metadata": {...}
    },
    {
      "event_type": "window_blur",
      "timestamp": "2026-02-14T10:30:18.567Z",
      "metadata": {...}
    }
  ]
}
```

---

### 4.2 Internal Format (After Validation)

**Enriched event (passed to rules engine):**

```python
@dataclass
class ProctoringEventInternal:
    submission_id: int
    organization_id: int  # Attached during ingestion
    event_type: str
    timestamp: datetime
    metadata: dict
    client_info: Optional[dict]
    ingestion_timestamp: datetime  # Server time when received
    event_fingerprint: str  # For deduplication
```

---

## 5. API Endpoints

### 5.1 WebSocket Event Handler

**Endpoint:** `wss://api.example.com/ws/interview/{submission_id}?token=JWT`

**Protocol:**

- Client sends `proctoring_event` frames during interview
- Server acknowledges with `event_received` frame
- Server may send `event_rejected` frame with reason

**Error handling:**

- Invalid event → send `event_rejected` frame (don't close connection)
- Rate limit exceeded → send `rate_limit_exceeded` frame with retry-after
- Connection lost → client auto-reconnects, events queued locally

---

### 5.2 REST API - Single Event

**Endpoint:** `POST /api/proctoring/events`

**Request body:**

```json
{
  "submission_id": 12345,
  "event_type": "camera_disabled",
  "timestamp": "2026-02-14T10:32:00.000Z",
  "metadata": {
    "reason": "user_action",
    "device_id": "abc123"
  }
}
```

**Response (202 Accepted):**

```json
{
  "event_id": "evt_abc123xyz",
  "status": "queued",
  "message": "Event accepted for processing"
}
```

**Error responses:**

- `400 Bad Request`: Invalid event structure
- `404 Not Found`: Submission does not exist or not active
- `429 Too Many Requests`: Rate limit exceeded
- `401 Unauthorized`: Invalid JWT

---

### 5.3 REST API - Batch Events

**Endpoint:** `POST /api/proctoring/events/batch`

**Request body:**

```json
{
  "submission_id": 12345,
  "events": [
    {
      "event_type": "tab_switch",
      "timestamp": "2026-02-14T10:30:15.234Z",
      "metadata": {...}
    },
    {
      "event_type": "window_blur",
      "timestamp": "2026-02-14T10:30:18.567Z",
      "metadata": {...}
    }
  ]
}
```

**Response (202 Accepted):**

```json
{
  "batch_id": "batch_xyz789",
  "accepted": 2,
  "rejected": 0,
  "status": "queued"
}
```

**Partial success:** If some events invalid, return details:

```json
{
  "batch_id": "batch_xyz789",
  "accepted": 1,
  "rejected": 1,
  "errors": [
    {
      "index": 1,
      "event_type": "invalid_type",
      "reason": "Unknown event type"
    }
  ]
}
```

---

## 6. Background Processing

### 6.1 Event Queue

**Architecture:**

- Ingestion endpoint → enqueue to Redis list: `proctoring:event_queue`
- Background worker consumes events → validates → enriches → persists

**Queue structure:**

```python
# Enqueue
redis.lpush("proctoring:event_queue", json.dumps(event_data))

# Consume (worker)
while True:
    event_json = redis.brpop("proctoring:event_queue", timeout=5)
    if event_json:
        process_event(json.loads(event_json))
```

**Benefits:**

- Non-blocking ingestion (< 50ms response)
- Backpressure handling (queue depth monitoring)
- Retry on failure (re-enqueue with backoff)

---

### 6.2 Event Processing Workflow

1. **Validate:** Check required fields, business constraints
2. **Enrich:** Attach organization_id, server timestamp
3. **Deduplicate:** Check event fingerprint
4. **Apply rules:** Assign severity and risk weight (see rules/)
5. **Persist:** Insert into proctoring_events table (see persistence/)
6. **Update risk:** Recompute submission-level risk score (see risk_model/)

**On failure:**

- Log error with event data (sanitized)
- Re-enqueue with retry count (max 3 retries)
- After max retries → move to dead letter queue (DLQ)
- Alert admin if DLQ size > threshold

---

## 7. Rate Limiting Implementation

### 7.1 Per-Submission Rate Limit

**Goal:** Prevent single submission from overwhelming system.

**Implementation:**

```python
def check_rate_limit(submission_id: int, limit: int = 100) -> bool:
    """
    Check if submission has exceeded rate limit.

    Returns True if under limit, False if exceeded.
    """
    current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")
    key = f"rate_limit:proctoring:{submission_id}:{current_minute}"

    count = redis.incr(key)
    redis.expire(key, 60)  # TTL 60 seconds

    return count <= limit
```

**Sliding window (more accurate):**

```python
def check_rate_limit_sliding(submission_id: int, limit: int = 100) -> bool:
    """
    Sliding window rate limit (last 60 seconds).
    """
    now = time.perf_counter()
    window_start = now - 60

    key = f"rate_limit:proctoring:{submission_id}"

    # Remove events older than 60 seconds
    redis.zremrangebyscore(key, 0, window_start)

    # Add current event
    redis.zadd(key, {str(uuid.uuid4()): now})

    # Check count
    count = redis.zcard(key)
    redis.expire(key, 60)

    return count <= limit
```

---

### 7.2 Per-IP Rate Limit

**Goal:** Prevent abuse from single IP address.

**Implementation:**

```python
def check_ip_rate_limit(ip_address: str, limit: int = 500) -> bool:
    """
    Check if IP has exceeded rate limit.
    """
    current_minute = datetime.utcnow().strftime("%Y%m%d%H%M")
    key = f"rate_limit:ip:{ip_address}:{current_minute}"

    count = redis.incr(key)
    redis.expire(key, 60)

    return count <= limit
```

**Note:** Use X-Forwarded-For header (if behind proxy) with validation.

---

## 8. Event Deduplication

### 8.1 Fingerprint Generation

**Goal:** Detect exact duplicate events within 5-minute window.

**Implementation:**

```python
import hashlib
import json

def generate_event_fingerprint(event: dict) -> str:
    """
    Generate unique fingerprint for event.

    Uses submission_id, event_type, timestamp, metadata hash.
    """
    fingerprint_data = {
        "submission_id": event["submission_id"],
        "event_type": event["event_type"],
        "timestamp": event["timestamp"],
        "metadata_hash": hashlib.md5(
            json.dumps(event.get("metadata", {}), sort_keys=True).encode()
        ).hexdigest()
    }

    fingerprint_str = json.dumps(fingerprint_data, sort_keys=True)
    return hashlib.sha256(fingerprint_str.encode()).hexdigest()
```

---

### 8.2 Deduplication Check

**Implementation:**

```python
def is_duplicate_event(submission_id: int, fingerprint: str) -> bool:
    """
    Check if event fingerprint already seen in last 5 minutes.

    Returns True if duplicate, False if unique.
    """
    key = f"proctoring:dedup:{submission_id}"

    # Check if fingerprint exists
    if redis.sismember(key, fingerprint):
        return True

    # Add fingerprint to set
    redis.sadd(key, fingerprint)
    redis.expire(key, 300)  # TTL 5 minutes

    return False
```

**Note:** False positives (legitimate repeated events) prevented by timestamp precision (milliseconds).

---

## 9. Error Handling

### 9.1 Validation Errors

**Scenario:** Malformed event (missing required field)

**Response:**

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{
  "error": "validation_error",
  "message": "Missing required field: event_type",
  "details": {
    "field": "event_type",
    "expected": "string (from allowed list)"
  }
}
```

---

### 9.2 Submission Not Found

**Scenario:** submission_id does not exist or not active

**Response:**

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{
  "error": "submission_not_found",
  "message": "Submission not found or not active",
  "submission_id": 12345
}
```

---

### 9.3 Rate Limit Exceeded

**Scenario:** Submission exceeded max events per minute

**Response:**

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 42
Content-Type: application/json

{
  "error": "rate_limit_exceeded",
  "message": "Too many events for this submission",
  "limit": 100,
  "window": "1 minute",
  "retry_after_seconds": 42
}
```

---

### 9.4 Internal Server Error

**Scenario:** Database unavailable, Redis down

**Response:**

```http
HTTP/1.1 503 Service Unavailable
Retry-After: 60
Content-Type: application/json

{
  "error": "service_unavailable",
  "message": "Event processing temporarily unavailable",
  "retry_after_seconds": 60
}
```

**Internal action:**

- Log error with full stack trace
- Alert DevOps (PagerDuty, Slack)
- Do NOT expose internal error details to client

---

## 10. Observability

### 10.1 Metrics

**Must expose:**

- `proctoring_ingestion_events_total` (counter with label: event_type) - Total events received
- `proctoring_ingestion_events_rejected` (counter with label: reason) - Invalid events rejected
- `proctoring_ingestion_latency_seconds` (histogram) - Time from receive to acknowledge
- `proctoring_ingestion_queue_depth` (gauge) - Current queue size
- `proctoring_rate_limit_exceeded` (counter with label: submission_id) - Rate limit violations
- `proctoring_duplicate_events` (counter) - Deduplicated events

---

### 10.2 Logging

**Must log (INFO level):**

- Event received (submission_id, event_type, timestamp)
- Event queued for processing
- Rate limit exceeded (submission_id, current count)
- Duplicate event detected (fingerprint)

**Must log (ERROR level):**

- Event validation failed (reason, sanitized event data)
- Database insert failed (error message, retry count)
- Queue processing error (event data, stack trace)

**Must NOT log:**

- Full event metadata (may contain PII)
- Candidate names or personal info
- Full video frame snapshots

---

## 11. Configuration

```python
from pydantic import BaseModel, Field

class IngestionConfig(BaseModel):
    """Proctoring ingestion configuration."""

    # Rate limiting
    max_events_per_submission_per_minute: int = Field(100, gt=0)
    max_events_per_ip_per_minute: int = Field(500, gt=0)
    max_batch_size: int = Field(50, gt=0, le=100)

    # Deduplication
    deduplication_window_seconds: int = Field(300, gt=0)  # 5 minutes

    # Queue processing
    queue_worker_count: int = Field(4, gt=0)
    queue_poll_timeout_seconds: int = Field(5, gt=0)
    max_retry_attempts: int = Field(3, gt=0)
    retry_backoff_seconds: int = Field(2, gt=0)

    # Validation
    max_metadata_size_kb: int = Field(10, gt=0, le=100)
    max_clock_skew_minutes: int = Field(5, gt=0)

    # WebSocket
    websocket_ping_interval_seconds: int = Field(30, gt=0)
    websocket_pong_timeout_seconds: int = Field(10, gt=0)
```

---

## 12. Testing Requirements

### 12.1 Unit Tests

1. **Event validation:** Valid event → passes validation
2. **Event validation:** Missing event_type → rejected
3. **Event validation:** Invalid timestamp → rejected
4. **Rate limiting:** 101st event in minute → rejected
5. **Deduplication:** Exact duplicate event → rejected
6. **Fingerprint generation:** Same event → same fingerprint

---

### 12.2 Integration Tests

1. **WebSocket ingestion:** Client sends event → acknowledged, queued
2. **REST API ingestion:** POST event → 202 Accepted, queued
3. **Batch ingestion:** 10 events → all accepted
4. **Tenant isolation:** Event for submission in Org 1 → organization_id attached correctly
5. **Rate limit enforcement:** 100 events → accepted, 101st → rejected

---

### 12.3 Load Tests

1. **Burst events:** 1000 events in 1 second → handled without data loss
2. **Sustained load:** 100 events/sec for 10 minutes → stable queue depth
3. **Queue recovery:** Redis down → gracefully degrade, events queued locally, retry when up

---

## 13. Security Considerations

### 13.1 Authorization

**Must enforce:**

- JWT token required for all API requests
- Token must contain valid submission_id claim
- WebSocket connection requires JWT as query param
- Token expiration checked on each request

---

### 13.2 Input Sanitization

**Must sanitize:**

- Event metadata (strip HTML, limit size)
- Client info (validate against schema)
- Timestamps (validate format, normalize timezone)

**Must prevent:**

- SQL injection (use parameterized queries)
- NoSQL injection (sanitize Redis keys)
- XSS attacks (escape metadata before rendering in UI)

---

### 13.3 Abuse Prevention

**Must implement:**

- Rate limiting per submission (prevent flooding)
- Rate limiting per IP (prevent DDoS)
- Event deduplication (prevent replay attacks)
- Max metadata size (prevent resource exhaustion)

---

## 14. Critical Risks

1. **Event loss under load:** Queue overflow → events dropped → incomplete audit trail
2. **Clock skew issues:** Client timestamp far in past/future → risk computation incorrect
3. **Rate limit bypass:** Attacker uses multiple submissions → overwhelms system
4. **Deduplication false negatives:** Fingerprint collision → duplicate events stored
5. **WebSocket disconnection:** Network loss → events queued locally → memory exhaustion
6. **JWT token theft:** Attacker submits fake events → data integrity compromised

---

## 15. Acceptance Criteria

**Ingestion module is complete when:**

✅ WebSocket event handler working (real-time events)
✅ REST API endpoints working (single + batch)
✅ Event validation rejecting invalid events
✅ Rate limiting enforced (per submission + per IP)
✅ Event deduplication working (5-minute window)
✅ Tenant isolation enforced (organization_id attached)
✅ Background queue processing events asynchronously
✅ Retry logic with exponential backoff
✅ Dead letter queue for failed events
✅ Metrics exposed (ingestion rate, queue depth, errors)
✅ Logging complete (INFO + ERROR levels)
✅ All tests passing (unit + integration + load)

---

**End of Proctoring Ingestion Requirements**
