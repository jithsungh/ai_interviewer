# Interview API - REST & WebSocket Entry Points

## 1. Purpose

The **Interview API** layer exposes HTTP and WebSocket endpoints for the interview lifecycle:

- Starting interviews (transition pending → in_progress)
- Submitting answers (create exchanges)
- Completing interviews (transition in_progress → completed)
- Real-time question/answer flow (WebSocket events)
- Fetching session status and progress

**Critical responsibility:** This is the **public interface** to the interview engine. It must:

- Enforce authorization (only candidate can access own interview)
- Validate preconditions before state transitions
- Coordinate with orchestration layer for business logic
- Handle WebSocket connections safely
- Prevent unauthorized state mutations

---

## 2. Required REST Endpoints

### 1️⃣ POST /api/interviews/start

**Purpose:** Start an interview (transition pending → in_progress).

#### Request

```python
from pydantic import BaseModel, Field

class StartInterviewRequest(BaseModel):
    interview_id: int = Field(gt=0)
    consent_accepted: bool = Field(description="Candidate consent to recording/monitoring")
    time_zone: str = Field(default="UTC", max_length=50)

    class Config:
        json_schema_extra = {
            "example": {
                "interview_id": 100,
                "consent_accepted": true,
                "time_zone": "America/New_York"
            }
        }
```

#### Response

**201 Created** (Interview started)

```json
{
  "submission_id": 123,
  "interview_id": 100,
  "submission_status": "in_progress",
  "started_at": "2026-02-14T10:00:00Z",
  "expires_at": "2026-02-14T11:00:00Z",
  "total_questions": 10,
  "current_exchange_sequence": 0,
  "progress_percentage": 0.0,
  "time_remaining_seconds": 3600,
  "websocket_url": "wss://api.example.com/ws/interview/123"
}
```

**200 OK** (Already started - idempotent)

Same structure as 201, returns existing session.

#### Error Responses

**400 Bad Request**

```json
{
  "error_code": "CONSENT_REQUIRED",
  "message": "Candidate must accept consent before starting interview"
}
```

**403 Forbidden**

```json
{
  "error_code": "UNAUTHORIZED_ACCESS",
  "message": "Cannot start interview for other candidates"
}
```

**404 Not Found**

```json
{
  "error_code": "INTERVIEW_NOT_FOUND",
  "message": "Interview 100 does not exist"
}
```

**409 Conflict**

```json
{
  "error_code": "ALREADY_COMPLETED",
  "message": "Interview already completed at 2026-02-14T09:00:00Z"
}
```

**422 Unprocessable Entity**

```json
{
  "error_code": "OUTSIDE_INTERVIEW_WINDOW",
  "message": "Interview can only be started between 2026-02-14 09:00 and 2026-02-14 18:00"
}
```

#### Business Rules

**Must validate:**

1. Interview exists and belongs to authenticated candidate
2. consent_accepted = true
3. Current time within interview window (if scheduled)
4. Submission status = 'pending' (or idempotent if 'in_progress')
5. No other active interview for candidate (if MAX_CONCURRENT = 1)

**Must execute:**

1. Acquire Redis lock on submission_id
2. Atomic state transition: UPDATE submission SET status = 'in_progress', started_at = NOW() WHERE status = 'pending'
3. Calculate expires_at = started_at + INTERVIEW_DURATION
4. Create Redis session state
5. Emit InterviewStarted event
6. Release lock
7. Return session data with WebSocket URL

---

### 2️⃣ POST /api/interviews/{submission_id}/complete

**Purpose:** Complete interview (transition in_progress → completed).

#### Request

```python
class CompleteInterviewRequest(BaseModel):
    reason: Literal["submitted", "expired", "cancelled"] = "submitted"
    final_notes: Optional[str] = Field(None, max_length=5000)
```

#### Response

**200 OK**

```json
{
  "submission_id": 123,
  "submission_status": "completed",
  "submitted_at": "2026-02-14T10:45:00Z",
  "exchanges_completed": 10,
  "total_questions": 10,
  "completion_reason": "submitted"
}
```

#### Error Responses

**403 Forbidden**

```json
{
  "error_code": "UNAUTHORIZED_ACCESS",
  "message": "Cannot complete interview for other candidates"
}
```

**409 Conflict**

```json
{
  "error_code": "INVALID_STATE_TRANSITION",
  "message": "Cannot complete interview in 'pending' state"
}
```

#### Business Rules

**Must validate:**

1. Submission belongs to authenticated candidate (or admin)
2. Submission status = 'in_progress' (or idempotent if 'completed')

**Must execute:**

1. Atomic state transition: UPDATE submission SET status = 'completed', submitted_at = NOW()
2. Update Redis session state
3. Close active WebSocket connections
4. Trigger final result aggregation (evaluation module)
5. Emit InterviewCompleted event

---

### 3️⃣ GET /api/interviews/{submission_id}/status

**Purpose:** Fetch current interview session status.

#### Response

**200 OK**

```json
{
  "submission_id": 123,
  "interview_id": 100,
  "candidate_id": 456,
  "submission_status": "in_progress",
  "current_exchange_sequence": 5,
  "total_questions": 10,
  "progress_percentage": 50.0,
  "started_at": "2026-02-14T10:00:00Z",
  "expires_at": "2026-02-14T11:00:00Z",
  "time_remaining_seconds": 1800,
  "created_at": "2026-02-14T09:00:00Z"
}
```

#### Error Responses

**403 Forbidden**

```json
{
  "error_code": "UNAUTHORIZED_ACCESS",
  "message": "Cannot view interview for other candidates"
}
```

**404 Not Found**

```json
{
  "error_code": "SUBMISSION_NOT_FOUND",
  "message": "Submission 123 does not exist"
}
```

#### Business Rules

- Return Redis session state if available (fast path)
- Fallback to PostgreSQL if Redis evicted
- Calculate time_remaining_seconds dynamically

---

### 4️⃣ GET /api/interviews/{submission_id}/exchanges

**Purpose:** Fetch all exchanges for interview (audit trail).

#### Query Parameters

- `include_responses` (bool, default=true): Include response data
- `section` (str, optional): Filter by section name

#### Response

**200 OK**

```json
{
  "submission_id": 123,
  "exchanges": [
    {
      "exchange_id": 789,
      "sequence_order": 1,
      "question_text": "Tell me about your experience with Python.",
      "question_type": "text",
      "section_name": "resume",
      "response_text": "I have 5 years of experience...",
      "response_time_ms": 45000,
      "responded_at": "2026-02-14T10:05:00Z"
    },
    {
      "exchange_id": 790,
      "sequence_order": 2,
      "question_text": "Implement Two Sum",
      "question_type": "coding",
      "section_name": "coding",
      "response_code": "def twoSum(nums, target): ...",
      "response_language": "python",
      "code_submission_id": 456,
      "response_time_ms": 120000,
      "responded_at": "2026-02-14T10:20:00Z"
    }
  ],
  "total_exchanges": 2
}
```

#### Authorization

- Candidate can view own exchanges (responses included)
- Admin can view all exchanges (responses included)
- Unauthorized users cannot view exchanges

---

### 5️⃣ GET /api/interviews/{submission_id}/progress

**Purpose:** Fetch detailed progress breakdown by section.

#### Response

**200 OK**

```json
{
  "submission_id": 123,
  "overall_progress": 50.0,
  "sections": [
    {
      "section_name": "resume",
      "questions_total": 2,
      "questions_answered": 2,
      "progress_percentage": 100.0
    },
    {
      "section_name": "behavioral",
      "questions_total": 3,
      "questions_answered": 3,
      "progress_percentage": 100.0
    },
    {
      "section_name": "coding",
      "questions_total": 3,
      "questions_answered": 0,
      "progress_percentage": 0.0
    }
  ]
}
```

---

## 3. WebSocket Protocol

### Connection

**URL:** `wss://api.example.com/ws/interview/{submission_id}`

**Query Parameters:**

- `token`: JWT authentication token

**Connection Flow:**

1. Client sends WebSocket upgrade request with JWT in query param
2. Server validates JWT, extracts candidate_id
3. Server verifies submission belongs to candidate
4. Server accepts WebSocket connection
5. Server registers connection in Redis: `active_websocket:{submission_id}`
6. Server sends `connection_established` event

---

### Client → Server Events

#### 1. join_session

**Purpose:** Initialize session after connection.

```json
{
  "event_type": "join_session",
  "submission_id": 123
}
```

**Response:** `session_joined` event with current state.

---

#### 2. request_next_question

**Purpose:** Request next question in sequence.

```json
{
  "event_type": "request_next_question",
  "submission_id": 123
}
```

**Response:** `question_payload` event.

---

#### 3. submit_answer

**Purpose:** Submit text answer for current question.

```json
{
  "event_type": "submit_answer",
  "exchange_id": 789,
  "response_text": "My answer is...",
  "response_time_ms": 45000
}
```

**Response:** `answer_accepted` event.

---

#### 4. submit_code

**Purpose:** Submit code answer for coding question.

```json
{
  "event_type": "submit_code",
  "exchange_id": 790,
  "response_code": "def twoSum(nums, target): ...",
  "response_language": "python",
  "response_time_ms": 120000
}
```

**Response:** `code_submission_accepted` event (execution happens async).

---

#### 5. heartbeat

**Purpose:** Keep connection alive, refresh Redis TTL.

```json
{
  "event_type": "heartbeat",
  "timestamp": "2026-02-14T10:30:00Z"
}
```

**Response:** `heartbeat_ack` event.

---

### Server → Client Events

#### 1. connection_established

**Sent:** After successful WebSocket connection.

```json
{
  "event_type": "connection_established",
  "submission_id": 123,
  "connection_id": "uuid-1234",
  "server_time": "2026-02-14T10:00:00Z"
}
```

---

#### 2. session_joined

**Sent:** After client sends `join_session`.

```json
{
  "event_type": "session_joined",
  "submission_id": 123,
  "submission_status": "in_progress",
  "current_sequence": 5,
  "total_questions": 10,
  "time_remaining_seconds": 1800
}
```

---

#### 3. question_payload

**Sent:** Deliver next question to candidate.

```json
{
  "event_type": "question_payload",
  "exchange_id": 789,
  "sequence_order": 1,
  "question_text": "Tell me about your experience with Python.",
  "question_type": "text",
  "question_difficulty": "medium",
  "section_name": "resume",
  "time_limit_seconds": 300,
  "is_final_question": false
}
```

---

#### 4. answer_accepted

**Sent:** After text answer accepted.

```json
{
  "event_type": "answer_accepted",
  "exchange_id": 789,
  "sequence_order": 1,
  "next_sequence": 2,
  "progress_percentage": 10.0
}
```

---

#### 5. code_submission_accepted

**Sent:** After code submission accepted (execution pending).

```json
{
  "event_type": "code_submission_accepted",
  "exchange_id": 790,
  "code_submission_id": 456,
  "execution_status": "pending",
  "message": "Code submitted successfully. Execution in progress..."
}
```

---

#### 6. code_execution_completed

**Sent:** After code execution finishes.

```json
{
  "event_type": "code_execution_completed",
  "exchange_id": 790,
  "code_submission_id": 456,
  "execution_status": "passed",
  "score": 85.5,
  "test_results_summary": "5/5 test cases passed"
}
```

---

#### 7. timer_update

**Sent:** Every 60 seconds to update remaining time.

```json
{
  "event_type": "timer_update",
  "time_remaining_seconds": 1740,
  "progress_percentage": 15.0
}
```

---

#### 8. interview_completed

**Sent:** When interview completes (submitted/expired).

```json
{
  "event_type": "interview_completed",
  "submission_id": 123,
  "completion_reason": "submitted",
  "submitted_at": "2026-02-14T10:45:00Z",
  "exchanges_completed": 10,
  "message": "Interview completed successfully!"
}
```

---

#### 9. error_event

**Sent:** On validation error or server error.

```json
{
  "event_type": "error_event",
  "error_code": "INVALID_EXCHANGE_ID",
  "message": "Exchange 999 does not exist",
  "timestamp": "2026-02-14T10:30:00Z"
}
```

---

#### 10. connection_replaced

**Sent:** When new WebSocket connection replaces current one.

```json
{
  "event_type": "connection_replaced",
  "message": "New connection established from another client. This connection will close.",
  "timestamp": "2026-02-14T10:35:00Z"
}
```

---

## 4. Authorization Matrix

| Endpoint                     | Candidate | Admin | Notes                                       |
| ---------------------------- | --------- | ----- | ------------------------------------------- |
| POST /start                  | ✅ (own)  | ✅    | Candidate can only start own interview      |
| POST /complete               | ✅ (own)  | ✅    | Admin can complete any interview            |
| GET /status                  | ✅ (own)  | ✅    | Candidate sees own status                   |
| GET /exchanges               | ✅ (own)  | ✅    | Candidate sees own exchanges                |
| GET /progress                | ✅ (own)  | ✅    | Candidate sees own progress                 |
| WebSocket /ws/interview/{id} | ✅ (own)  | ❌    | Admin cannot connect to candidate WebSocket |

---

## 5. Rate Limiting

**REST endpoints:**

- POST /start: 10 requests per minute per candidate (prevent spam)
- POST /complete: 20 requests per minute per candidate
- GET /status: 100 requests per minute per candidate
- GET /exchanges: 50 requests per minute per candidate

**WebSocket events:**

- submit_answer: No rate limit (interview controls sequencing)
- submit_code: No rate limit
- heartbeat: Max 1 per second (disconnect if exceeded)

---

## 6. Error Handling

**Must handle:**

### REST Errors

1. Interview not found → 404
2. Unauthorized access → 403
3. Invalid state transition → 409
4. Outside interview window → 422
5. Consent not accepted → 400
6. Already completed → 409
7. Redis unavailable → 503 (Service Unavailable)

### WebSocket Errors

1. Invalid JWT → Close with code 1008 (Policy Violation)
2. Token expired → Send `error_event`, close with code 1008
3. Invalid exchange_id → Send `error_event`, keep connection open
4. Interview expired → Send `interview_completed`, close with code 1000
5. Connection replaced → Send `connection_replaced`, close with code 1000
6. Malformed event → Send `error_event`, keep connection open

---

## 7. Idempotency

### Start Interview

**Idempotency key:** `interview_id` + `candidate_id`

**Behavior:**

- If already started, return existing session (200 OK)
- If completed, return 409 Conflict

### Complete Interview

**Idempotency key:** `submission_id`

**Behavior:**

- If already completed, return existing completion data (200 OK)

### Submit Answer (WebSocket)

**Idempotency key:** `exchange_id`

**Behavior:**

- If exchange already created for sequence, return error (duplicate submission)

---

## 8. WebSocket Connection Management

### Connection Lifecycle

1. **Connect:** Validate JWT, register in Redis
2. **Active:** Handle events, send timer updates
3. **Heartbeat:** Refresh Redis TTL every 30 seconds
4. **Disconnect:** Remove from Redis, log disconnect reason

### Reconnect Handling

**Scenario:** Network drops, candidate reconnects.

**Flow:**

1. Client establishes new WebSocket connection
2. Server validates JWT, fetches session from Redis/PostgreSQL
3. Server sends `session_joined` with current state
4. Client resumes from current_exchange_sequence

### Multiple Connection Handling

**Scenario:** Candidate opens interview in two tabs.

**Flow:**

1. First connection registered: `active_websocket:{submission_id} = connection_id_1`
2. Second connection attempts: `active_websocket:{submission_id} = connection_id_2`
3. Server sends `connection_replaced` to connection_id_1, closes it
4. Second connection becomes active

---

## 9. Testing Requirements

### Unit Tests

1. Request validation (Pydantic schemas)
2. Authorization checks (candidate/admin roles)
3. State transition validation (pending → in_progress only)

### Integration Tests

1. Start interview → session created
2. Submit answer (REST) → exchange created
3. Complete interview → status updated
4. WebSocket connect → connection established
5. WebSocket submit answer → exchange created
6. WebSocket heartbeat → TTL refreshed

### Edge Case Tests

1. Double start request (idempotent)
2. Start already completed interview (409)
3. Complete pending interview (409)
4. Late answer after timeout (rejected)
5. Reconnect mid-session (resume from current)
6. Two WebSocket connections (second replaces first)

---

## 10. Critical Risks

1. **No JWT validation:** Unauthorized access to interviews
2. **No state validation:** Invalid transitions allowed
3. **No Redis lock:** Concurrent operations corrupt state
4. **WebSocket desync:** Client/server state mismatch
5. **No idempotency:** Duplicate start/complete operations
6. **No timeout enforcement:** Late answers accepted
7. **No connection replacement:** Multiple active WebSockets

---

**End of Interview API Requirements**
