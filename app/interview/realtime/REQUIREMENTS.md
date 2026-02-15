# Interview Realtime - WebSocket Protocol Handlers & Event Contracts

## 1. Purpose

The **Realtime** layer is responsible for:

- Managing WebSocket connections for live interview sessions
- Defining bidirectional event protocol (client ↔ server)
- Handling connection lifecycle (connect, active, disconnect, reconnect)
- Authenticating WebSocket connections (JWT validation)
- Broadcasting events to clients (questions, progress, errors)
- Tracking active connections in Redis

**Critical responsibility:** This is the **real-time communication boundary**. It must:

- Authenticate before accepting connection
- Track single active connection per submission (replace old connections)
- Handle reconnection gracefully (resume from current state)
- Validate all incoming events
- Send structured events (not raw text)
- Clean up on disconnect

---

## 2. WebSocket URL

```
wss://api.example.com/ws/interview/{submission_id}?token=<JWT>
```

**Path parameter:**

- `submission_id`: Interview submission ID

**Query parameter:**

- `token`: JWT authentication token (candidate token)

---

## 3. Connection Lifecycle

### 1. Connection Request

**Client initiates:**

```javascript
const ws = new WebSocket(
  `wss://api.example.com/ws/interview/123?token=${jwtToken}`,
);
```

**Server validates:**

1. Extract JWT from query parameter
2. Validate JWT signature and expiration
3. Extract candidate_id from JWT claims
4. Verify submission belongs to candidate
5. Check submission status (must be 'in_progress')
6. Accept or reject connection

---

### 2. Connection Acceptance

**On successful validation:**

1. Accept WebSocket upgrade
2. Generate connection_id (UUID)
3. Register connection in Redis: `active_websocket:{submission_id} = connection_id`
4. Check for existing connection (connection replacement)
5. Send `connection_established` event

**On validation failure:**

- Reject with code 1008 (Policy Violation)
- Send close reason: "Invalid token" or "Unauthorized"

---

### 3. Active State

**During active connection:**

- Handle incoming events (join_session, submit_answer, heartbeat)
- Send outgoing events (question_payload, timer_update, progress_update)
- Refresh Redis TTL on heartbeat (every 30 seconds)

---

### 4. Heartbeat Mechanism

**Client sends heartbeat:**

```json
{
  "event_type": "heartbeat",
  "timestamp": "2026-02-14T10:30:00Z"
}
```

**Server responds:**

```json
{
  "event_type": "heartbeat_ack",
  "server_time": "2026-02-14T10:30:01Z"
}
```

**Purpose:**

- Keep connection alive (prevent idle timeout)
- Refresh Redis TTL for active connection
- Detect disconnected clients (no heartbeat for 60s = disconnected)

---

### 5. Disconnection

**Client disconnects (normal):**

- Client sends close frame (code 1000)
- Server cleans up: remove from Redis, close connection

**Server disconnects (forced):**

- Interview expired: Send `interview_expired`, close with code 1000
- Connection replaced: Send `connection_replaced`, close with code 1000
- Token expired: Send `error_event`, close with code 1008

**Network interruption:**

- Connection drops without close frame
- Redis TTL expires after 60 seconds (no heartbeat refresh)
- Client can reconnect (see Reconnection below)

---

### 6. Reconnection

**Client reconnects after network drop:**

1. Client opens new WebSocket connection (same submission_id, fresh token)
2. Server validates token, accepts connection
3. Server fetches current session state from Redis/PostgreSQL
4. Server sends `session_joined` with current state (current_sequence, progress)
5. Client resumes from current state

---

### 7. Connection Replacement

**Scenario:** Candidate opens interview in two browser tabs.

**Flow:**

1. First connection established: `active_websocket:{submission_id} = conn_1`
2. Second connection attempts to connect
3. Server detects existing connection (conn_1)
4. Server sends `connection_replaced` event to conn_1
5. Server closes conn_1 with code 1000
6. Server registers conn_2: `active_websocket:{submission_id} = conn_2`
7. Second connection becomes active

**Event to old connection:**

```json
{
  "event_type": "connection_replaced",
  "message": "New connection established from another client. This connection will close.",
  "new_connection_id": "uuid-5678",
  "timestamp": "2026-02-14T10:35:00Z"
}
```

---

## 4. Client → Server Events

### 1. join_session

**Purpose:** Initialize session after connection.

**Payload:**

```json
{
  "event_type": "join_session",
  "submission_id": 123
}
```

**Server Response:**

- Fetch session state from Redis/PostgreSQL
- Send `session_joined` event with current state
- If session completed, send `interview_completed` and close

---

### 2. request_next_question

**Purpose:** Request next question in sequence.

**Payload:**

```json
{
  "event_type": "request_next_question",
  "submission_id": 123
}
```

**Server Response:**

- Resolve next question from template snapshot
- Fetch question content
- Send `question_payload` event
- If no more questions, send `interview_completed` (auto-submit)

---

### 3. submit_answer

**Purpose:** Submit text answer for current question.

**Payload:**

```json
{
  "event_type": "submit_answer",
  "exchange_id": 789,
  "response_text": "My answer is...",
  "response_time_ms": 45000
}
```

**Validation:**

- exchange_id matches expected sequence
- response_text is non-empty (or allow empty for skipped questions)
- response_time_ms > 0

**Server Response:**

- Create exchange
- Send `answer_accepted` event
- Resolve next question
- Send `question_payload` for next question (or `interview_completed` if final)

---

### 4. submit_code

**Purpose:** Submit code answer for coding question.

**Payload:**

```json
{
  "event_type": "submit_code",
  "exchange_id": 790,
  "response_code": "def twoSum(nums, target):\n    ...",
  "response_language": "python",
  "response_time_ms": 120000
}
```

**Validation:**

- exchange_id matches expected sequence
- response_code is non-empty
- response_language is supported (python, java, cpp)
- response_time_ms > 0

**Server Response:**

- Create code_submission (coding module)
- Trigger code execution (async)
- Send `code_submission_accepted` event (execution pending)
- Send `code_execution_completed` event later (async, when execution finishes)

---

### 5. heartbeat

**Purpose:** Keep connection alive, refresh Redis TTL.

**Payload:**

```json
{
  "event_type": "heartbeat",
  "timestamp": "2026-02-14T10:30:00Z"
}
```

**Server Response:**

- Refresh Redis TTL for connection
- Send `heartbeat_ack` event

---

## 5. Server → Client Events

### 1. connection_established

**Sent:** After successful WebSocket connection.

**Payload:**

```json
{
  "event_type": "connection_established",
  "submission_id": 123,
  "connection_id": "uuid-1234",
  "server_time": "2026-02-14T10:00:00Z"
}
```

---

### 2. session_joined

**Sent:** After client sends `join_session`.

**Payload:**

```json
{
  "event_type": "session_joined",
  "submission_id": 123,
  "submission_status": "in_progress",
  "current_sequence": 5,
  "total_questions": 10,
  "progress_percentage": 50.0,
  "time_remaining_seconds": 1800,
  "started_at": "2026-02-14T10:00:00Z",
  "expires_at": "2026-02-14T11:00:00Z"
}
```

---

### 3. question_payload

**Sent:** Deliver next question to candidate.

**Payload:**

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

**For coding questions:**

```json
{
  "event_type": "question_payload",
  "exchange_id": 790,
  "sequence_order": 2,
  "question_text": "Implement Two Sum",
  "question_type": "coding",
  "question_difficulty": "easy",
  "section_name": "coding",
  "starter_code": "def twoSum(nums: List[int], target: int) -> List[int]:\n    pass",
  "test_cases": [{ "input": "[2,7,11,15], 9", "output": "[0,1]" }],
  "time_limit_seconds": 1800,
  "is_final_question": false
}
```

---

### 4. answer_accepted

**Sent:** After text answer accepted.

**Payload:**

```json
{
  "event_type": "answer_accepted",
  "exchange_id": 789,
  "sequence_order": 1,
  "next_sequence": 2,
  "progress_percentage": 10.0,
  "message": "Answer submitted successfully!"
}
```

---

### 5. code_submission_accepted

**Sent:** After code submission accepted (execution pending).

**Payload:**

```json
{
  "event_type": "code_submission_accepted",
  "exchange_id": 790,
  "code_submission_id": 456,
  "execution_status": "pending",
  "message": "Code submitted successfully. Execution in progress...",
  "estimated_execution_time_seconds": 10
}
```

---

### 6. code_execution_completed

**Sent:** After code execution finishes (async).

**Payload:**

```json
{
  "event_type": "code_execution_completed",
  "exchange_id": 790,
  "code_submission_id": 456,
  "execution_status": "passed",
  "score": 85.5,
  "test_results_summary": "5/5 test cases passed",
  "execution_time_ms": 2458,
  "next_sequence": 3,
  "progress_percentage": 20.0
}
```

---

### 7. timer_update

**Sent:** Every 60 seconds to update remaining time.

**Payload:**

```json
{
  "event_type": "timer_update",
  "time_remaining_seconds": 1740,
  "progress_percentage": 15.0,
  "current_sequence": 2,
  "total_questions": 10
}
```

---

### 8. progress_update

**Sent:** After each exchange creation.

**Payload:**

```json
{
  "event_type": "progress_update",
  "current_sequence": 5,
  "total_questions": 10,
  "progress_percentage": 50.0,
  "section_progress": {
    "resume": { "completed": 2, "total": 2 },
    "behavioral": { "completed": 3, "total": 3 },
    "coding": { "completed": 0, "total": 3 }
  }
}
```

---

### 9. interview_completed

**Sent:** When interview completes (submitted/expired).

**Payload:**

```json
{
  "event_type": "interview_completed",
  "submission_id": 123,
  "completion_reason": "submitted",
  "submitted_at": "2026-02-14T10:45:00Z",
  "exchanges_completed": 10,
  "total_questions": 10,
  "message": "Interview completed successfully!",
  "next_steps": "Results will be available within 24 hours."
}
```

---

### 10. interview_expired

**Sent:** When interview times out.

**Payload:**

```json
{
  "event_type": "interview_expired",
  "submission_id": 123,
  "expired_at": "2026-02-14T11:00:00Z",
  "exchanges_completed": 7,
  "total_questions": 10,
  "auto_submitted": true,
  "message": "Interview time expired. Your responses have been automatically submitted."
}
```

---

### 11. error_event

**Sent:** On validation error or server error.

**Payload:**

```json
{
  "event_type": "error_event",
  "error_code": "INVALID_EXCHANGE_ID",
  "message": "Exchange 999 does not exist or does not match expected sequence",
  "details": {
    "expected_sequence": 5,
    "received_exchange_id": 999
  },
  "timestamp": "2026-02-14T10:30:00Z"
}
```

**Error codes:**

- `INVALID_EXCHANGE_ID`
- `SEQUENCE_MISMATCH`
- `EMPTY_RESPONSE`
- `INTERVIEW_EXPIRED`
- `INTERVIEW_COMPLETED`
- `VALIDATION_ERROR`
- `SERVER_ERROR`

---

### 12. connection_replaced

**Sent:** When new WebSocket connection replaces current one.

**Payload:**

```json
{
  "event_type": "connection_replaced",
  "message": "New connection established from another client. This connection will close.",
  "new_connection_id": "uuid-5678",
  "timestamp": "2026-02-14T10:35:00Z"
}
```

---

### 13. heartbeat_ack

**Sent:** Response to heartbeat.

**Payload:**

```json
{
  "event_type": "heartbeat_ack",
  "server_time": "2026-02-14T10:30:01Z",
  "time_remaining_seconds": 1800
}
```

---

## 6. Connection Management

### Redis Tracking

**Keys:**

- `active_websocket:{submission_id}` → `connection_id` (TTL 60s, refreshed by heartbeat)
- `websocket_session:{connection_id}` → session metadata (TTL 3900s)

**Session metadata:**

```json
{
  "connection_id": "uuid-1234",
  "submission_id": 123,
  "candidate_id": 456,
  "connected_at": "2026-02-14T10:00:00Z",
  "last_heartbeat_at": "2026-02-14T10:30:00Z"
}
```

---

### WebSocket Manager

```python
from fastapi import WebSocket
from typing import Dict

class WebSocketManager:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.active_connections: Dict[int, WebSocket] = {}  # {submission_id: websocket}

    async def connect(
        self,
        websocket: WebSocket,
        submission_id: int,
        connection_id: str
    ) -> None:
        """
        Accept WebSocket connection.

        Steps:
        1. Check for existing connection
        2. If exists, close old connection (send connection_replaced)
        3. Accept new connection
        4. Register in Redis
        5. Send connection_established
        """
        # Check existing
        existing_conn_id = self.redis.get(f"active_websocket:{submission_id}")
        if existing_conn_id:
            # Close old connection
            old_ws = self.active_connections.get(submission_id)
            if old_ws:
                await old_ws.send_json({
                    "event_type": "connection_replaced",
                    "message": "New connection established from another client.",
                    "new_connection_id": connection_id
                })
                await old_ws.close(code=1000)

        # Accept new connection
        await websocket.accept()

        # Register
        self.active_connections[submission_id] = websocket
        self.redis.set(
            f"active_websocket:{submission_id}",
            connection_id,
            ex=60
        )

        # Send establish event
        await websocket.send_json({
            "event_type": "connection_established",
            "submission_id": submission_id,
            "connection_id": connection_id,
            "server_time": datetime.utcnow().isoformat()
        })

    async def disconnect(self, submission_id: int) -> None:
        """Remove connection from tracking."""
        self.active_connections.pop(submission_id, None)
        self.redis.delete(f"active_websocket:{submission_id}")

    async def send_to_user(self, submission_id: int, message: dict) -> None:
        """Send message to specific user's WebSocket."""
        websocket = self.active_connections.get(submission_id)
        if websocket:
            await websocket.send_json(message)

    async def refresh_ttl(self, submission_id: int) -> None:
        """Refresh connection TTL (called on heartbeat)."""
        self.redis.expire(f"active_websocket:{submission_id}", 60)
```

---

## 7. Event Validation

### Incoming Event Schema

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class WebSocketEvent(BaseModel):
    event_type: Literal[
        "join_session",
        "request_next_question",
        "submit_answer",
        "submit_code",
        "heartbeat"
    ]

class JoinSessionEvent(WebSocketEvent):
    event_type: Literal["join_session"]
    submission_id: int

class SubmitAnswerEvent(WebSocketEvent):
    event_type: Literal["submit_answer"]
    exchange_id: int
    response_text: str
    response_time_ms: int = Field(gt=0)

class SubmitCodeEvent(WebSocketEvent):
    event_type: Literal["submit_code"]
    exchange_id: int
    response_code: str = Field(min_length=1, max_length=100000)
    response_language: Literal["python", "java", "cpp"]
    response_time_ms: int = Field(gt=0)

class HeartbeatEvent(WebSocketEvent):
    event_type: Literal["heartbeat"]
    timestamp: str
```

---

### Validation Logic

```python
async def handle_message(websocket: WebSocket, raw_message: str) -> None:
    """
    Parse and validate incoming WebSocket message.

    Raises:
        ValidationError: Invalid event schema
    """
    try:
        data = json.loads(raw_message)
        event_type = data.get("event_type")

        if event_type == "join_session":
            event = JoinSessionEvent(**data)
            await handle_join_session(websocket, event)

        elif event_type == "submit_answer":
            event = SubmitAnswerEvent(**data)
            await handle_submit_answer(websocket, event)

        elif event_type == "submit_code":
            event = SubmitCodeEvent(**data)
            await handle_submit_code(websocket, event)

        elif event_type == "heartbeat":
            event = HeartbeatEvent(**data)
            await handle_heartbeat(websocket, event)

        else:
            raise ValueError(f"Unknown event_type: {event_type}")

    except (json.JSONDecodeError, ValidationError) as e:
        await websocket.send_json({
            "event_type": "error_event",
            "error_code": "VALIDATION_ERROR",
            "message": str(e)
        })
```

---

## 8. Testing Requirements

### Unit Tests

1. **Connection acceptance:** Valid JWT → connection accepted
2. **Connection rejection:** Invalid JWT → connection rejected (1008)
3. **Connection replacement:** Second connection replaces first
4. **Heartbeat refresh:** TTL refreshed on heartbeat
5. **Event validation:** Invalid event → error_event sent

### Integration Tests

1. **Join session:** Client sends join_session → server sends session_joined
2. **Submit answer:** Client sends submit_answer → exchange created → answer_accepted sent
3. **Submit code:** Client sends submit_code → code execution triggered → code_execution_completed sent
4. **Timer updates:** Server broadcasts timer_update every 60 seconds
5. **Interview completion:** Final question answered → interview_completed sent, connection closed

### Concurrency Tests

1. **Connection replacement:** Two connections same submission, second replaces first
2. **Simultaneous events:** Multiple submit_answer rapidly, handled sequentially
3. **Disconnect during processing:** Client disconnects mid-exchange-creation, cleanup successful

---

## 9. Critical Risks

1. **No JWT validation:** Unauthorized access to WebSocket
2. **No connection tracking:** Multiple active connections cause desync
3. **No heartbeat:** Idle connections not cleaned up
4. **No event validation:** Malformed events crash server
5. **No reconnection handling:** Network drop = lost session
6. **No cleanup on disconnect:** Memory leak from unclosed connections

---

**End of Interview Realtime Requirements**
