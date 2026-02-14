# Interview Module - Core Runtime Engine for Live Interview Sessions

## 1. Purpose

**Why this module exists:**

The Interview module is the **deterministic state machine orchestrator** and **runtime engine** of the entire system. It:

- Manages live interview sessions (start, progress, complete)
- Enforces submission state transitions (pending → in_progress → completed → reviewed)
- Resolves next question deterministically
- Creates immutable interview_exchanges (snapshot of question + response)
- Coordinates question engine, evaluation engine, coding execution, audio analysis, proctoring signals
- Maintains session state in Redis (runtime truth)
- Persists runtime artifacts in PostgreSQL (audit trail)

**Critical responsibility:** This is the **HEART OF THE ENTIRE SYSTEM**. If this module is wrong:

- **Exchange immutability breaks** → Audit trail corrupted
- **Template immutability becomes meaningless** → Non-reproducible interviews
- **Evaluation uniqueness collapses** → Duplicate/missing evaluations
- **Audio and code race conditions explode** → Duplicate exchanges, lost submissions
- **WebSocket state becomes inconsistent** → Desync between client and server
- **Multi-tenant isolation leaks** → Security breach

**Architectural philosophy:**

> **The interview module ORCHESTRATES. It does NOT decide scoring.**
> **It enforces architectural invariants at runtime.**
> **It owns runtime truth. Everything else plugs into it.**

---

## 2. Owned Tables / Entities

### interview_submissions

```sql
CREATE TABLE interview_submissions (
    id SERIAL PRIMARY KEY,
    interview_id INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    candidate_id INTEGER NOT NULL REFERENCES users(id),
    template_id INTEGER NOT NULL,  -- FROZEN at creation, never re-resolved

    -- State machine
    submission_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (
        submission_status IN ('pending', 'in_progress', 'completed', 'cancelled', 'expired')
    ),

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    submitted_at TIMESTAMP,
    expires_at TIMESTAMP,

    -- Progress tracking
    current_exchange_sequence INTEGER DEFAULT 0,
    total_questions INTEGER NOT NULL,

    -- Template snapshot (FROZEN)
    template_structure_snapshot JSONB NOT NULL,

    -- Metadata
    time_zone VARCHAR(50),
    user_agent TEXT,

    UNIQUE(interview_id)
);

CREATE INDEX idx_submissions_candidate ON interview_submissions(candidate_id);
CREATE INDEX idx_submissions_status ON interview_submissions(submission_status);
CREATE INDEX idx_submissions_expires ON interview_submissions(expires_at) WHERE submission_status = 'in_progress';
```

### interview_exchanges

```sql
CREATE TABLE interview_exchanges (
    id SERIAL PRIMARY KEY,
    interview_submission_id INTEGER NOT NULL REFERENCES interview_submissions(id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL,

    -- Question snapshot (IMMUTABLE)
    question_id INTEGER NOT NULL REFERENCES questions(id),
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL CHECK (
        question_type IN ('text', 'coding', 'audio')
    ),
    question_difficulty VARCHAR(20),
    expected_answer TEXT,
    section_name VARCHAR(50) NOT NULL,

    -- Response snapshot (IMMUTABLE)
    response_text TEXT,
    response_code TEXT,
    response_language VARCHAR(20),
    response_time_ms INTEGER,

    -- Coding-specific
    code_submission_id INTEGER REFERENCES code_submissions(id),

    -- Audio-specific
    audio_recording_id INTEGER REFERENCES audio_recordings(id),

    -- Metadata
    ai_followup_message TEXT,
    responded_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(interview_submission_id, sequence_order),
    UNIQUE(interview_submission_id, question_id)
);

CREATE INDEX idx_exchanges_submission ON interview_exchanges(interview_submission_id);
CREATE INDEX idx_exchanges_sequence ON interview_exchanges(interview_submission_id, sequence_order);
CREATE INDEX idx_exchanges_question ON interview_exchanges(question_id);
```

---

## 3. Input Contracts

### StartInterviewRequest

```python
from pydantic import BaseModel, Field

class StartInterviewRequest(BaseModel):
    interview_id: int = Field(gt=0)
    consent_accepted: bool = Field(description="Candidate consent to recording/monitoring")
    time_zone: str = Field(default="UTC", max_length=50)
```

### SubmitAnswerRequest

```python
class SubmitAnswerRequest(BaseModel):
    exchange_id: int = Field(gt=0)
    response_text: Optional[str] = Field(None, max_length=50000)
    response_code: Optional[str] = Field(None, max_length=100000)
    response_language: Optional[str] = Field(None)
    response_time_ms: int = Field(ge=0, description="Client-measured response time")
```

### CompleteInterviewRequest

```python
class CompleteInterviewRequest(BaseModel):
    interview_id: int = Field(gt=0)
    reason: Literal["submitted", "expired", "cancelled"] = "submitted"
```

---

## 4. Output Contracts

### InterviewSessionDTO

```python
from typing import List, Optional
from datetime import datetime

class InterviewSessionDTO(BaseModel):
    submission_id: int
    interview_id: int
    candidate_id: int
    submission_status: str
    current_exchange_sequence: int
    total_questions: int
    progress_percentage: float
    started_at: Optional[datetime]
    expires_at: Optional[datetime]
    time_remaining_seconds: Optional[int]
```

### NextQuestionDTO

```python
class NextQuestionDTO(BaseModel):
    exchange_id: int
    sequence_order: int
    question_id: int
    question_text: str
    question_type: str
    question_difficulty: str
    section_name: str
    time_limit_seconds: Optional[int]
    is_final_question: bool
```

### ExchangeDTO

```python
class ExchangeDTO(BaseModel):
    exchange_id: int
    sequence_order: int
    question_text: str
    question_type: str
    response_text: Optional[str]
    response_code: Optional[str]
    response_time_ms: int
    section_name: str
    responded_at: datetime
```

---

## 5. Acceptance Criteria

### Module-Level Requirements

#### 1. Template Resolution (FROZEN at Creation)

**Must enforce:**

- Template resolved ONCE at submission creation (not at runtime)
- `template_id` stored in `interview_submissions.template_id`
- `template_structure_snapshot` copied to JSONB at creation
- NO runtime JOIN to `interview_templates` table
- NO dynamic role → template resolution

**Why:** Template changes after interview starts must NOT affect in-progress interviews.

**Example:**

```python
# CORRECT (at submission creation)
template = fetch_template(interview.role_id)
submission.template_id = template.id
submission.template_structure_snapshot = template.structure  # FROZEN

# FORBIDDEN (at runtime)
template = fetch_template(submission.interview.role_id)  # WRONG! Dynamic resolution
```

---

#### 2. Exchange Immutability

**Must enforce:**

- Exchange created ONCE after response received
- NO UPDATE statements on `interview_exchanges` table
- Repository-level protection (raise error on update attempt)
- Snapshot ALL question/response data at creation time

**Forbidden:**

```python
# FORBIDDEN
exchange.response_text = "updated answer"
db.commit()

# FORBIDDEN
UPDATE interview_exchanges SET response_text = ... WHERE id = ...
```

**Allowed:**

```python
# ALLOWED (create only)
exchange = InterviewExchange(
    interview_submission_id=submission.id,
    sequence_order=next_sequence,
    question_text=question.content,  # Snapshot
    response_text=answer.text,       # Snapshot
    ...
)
db.add(exchange)
db.commit()
```

---

#### 3. State Machine Enforcement

**Must enforce:**

- One-way transitions only: pending → in_progress → completed
- NO backward transitions (completed → in_progress FORBIDDEN)
- Atomic state updates with precondition checks
- Concurrent start requests handled safely

**State diagram:**

```
pending ──start──> in_progress ──complete──> completed ──review──> reviewed
                        │
                        └──timeout──> expired
                        └──cancel──> cancelled
```

**Concurrency handling:**

```python
# Atomic state transition with precondition
UPDATE interview_submissions
SET submission_status = 'in_progress', started_at = NOW()
WHERE id = ? AND submission_status = 'pending';

# If 0 rows updated → already started (idempotent)
```

---

#### 4. Race Condition Prevention

**Must handle:**

**Audio-Code Race:**

- Scenario: Audio detects silence, code execution completes simultaneously
- Solution: Idempotency key on exchange creation, UNIQUE constraint on (submission_id, sequence_order)

**Double Answer Submission:**

- Scenario: Network retry causes duplicate answer submission
- Solution: Check if exchange exists for sequence_order before creating

**Timeout vs Late Answer:**

- Scenario: Timeout triggers at T=60s, answer arrives at T=60.001s
- Solution: Redis lock on submission_id, check timeout before accepting answer

**Evaluation Trigger Race:**

- Scenario: Exchange created, two workers trigger evaluation
- Solution: Evaluation module enforces UNIQUE constraint on exchange_id

---

#### 5. Deterministic Question Sequencing

**Must enforce:**

- Questions delivered in template_structure_snapshot order
- Sequence increments: 1, 2, 3, ... (no gaps)
- No question skipping (unless explicitly supported by template)
- Reconnect mid-session resumes from current_exchange_sequence

**Example:**

```json
{
  "template_structure_snapshot": {
    "sections": [
      { "name": "resume", "count": 2, "questions": [101, 102] },
      { "name": "behavioral", "count": 3, "questions": [201, 202, 203] },
      { "name": "coding", "count": 3, "questions": [301, 302, 303] }
    ]
  }
}
```

Sequence: 101 → 102 → 201 → 202 → 203 → 301 → 302 → 303

---

#### 6. Redis Session State (Runtime Truth)

**Must maintain in Redis:**

- `interview_session:{submission_id}` → Session metadata (status, sequence, expires_at)
- `interview_lock:{submission_id}` → Lock for critical operations (TTL 10s)
- `active_websocket:{submission_id}` → WebSocket connection tracking

**Session data structure:**

```json
{
  "submission_id": 123,
  "status": "in_progress",
  "current_sequence": 5,
  "total_questions": 10,
  "started_at": "2026-02-14T10:00:00Z",
  "expires_at": "2026-02-14T11:00:00Z",
  "candidate_id": 456
}
```

**TTL management:**

- Session TTL = interview_duration + 5 minutes (grace period)
- Lock TTL = 10 seconds (prevents deadlock)
- WebSocket TTL = 30 seconds (heartbeat refresh)

---

## 6. Invariants & Constraints

### Must Hold

1. **Template frozen:** `template_id` in submission NEVER changes after creation
2. **Exchange immutable:** `interview_exchanges` has NO UPDATE queries
3. **One-way state transitions:** No backward state transitions
4. **Unique exchange sequence:** UNIQUE constraint on (submission_id, sequence_order)
5. **One exchange per question:** UNIQUE constraint on (submission_id, question_id)
6. **Evaluation triggered after exchange:** Exchange must exist before evaluation
7. **Progress monotonic:** `current_exchange_sequence` only increments

### Forbidden

- MUST NOT dynamically resolve template at runtime (use snapshot)
- MUST NOT update exchange after creation
- MUST NOT transition completed → in_progress
- MUST NOT skip sequence numbers (gaps)
- MUST NOT create exchange before full response received
- MUST NOT trigger evaluation before exchange persisted
- MUST NOT allow multiple active WebSocket connections per submission

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Candidate API:** Starts interview, submits answers
2. **WebSocket Clients:** Real-time question/answer flow
3. **Admin Dashboard:** Monitors interview sessions

### Downstream (Dependencies)

1. **Question Module:** Fetches question content for exchanges
2. **Evaluation Module:** Triggers evaluation after exchange creation
3. **Coding Module:** Executes code submissions, creates code_submissions
4. **Audio Module:** Records audio, creates audio_recordings, signals completion
5. **Proctoring Module:** Monitors behavior, sends alerts
6. **Redis:** Session state, locks, WebSocket tracking
7. **PostgreSQL:** Persistent storage (submissions, exchanges)

---

## 8. Event Contracts Emitted

### InterviewStarted

```python
{
    "event_type": "interview_started",
    "submission_id": 123,
    "interview_id": 100,
    "candidate_id": 456,
    "started_at": "2026-02-14T10:00:00Z",
    "expires_at": "2026-02-14T11:00:00Z",
    "total_questions": 10
}
```

### ExchangeCreated

```python
{
    "event_type": "exchange_created",
    "exchange_id": 789,
    "submission_id": 123,
    "sequence_order": 5,
    "question_type": "coding",
    "section_name": "coding",
    "timestamp": "2026-02-14T10:30:00Z"
}
```

### InterviewCompleted

```python
{
    "event_type": "interview_completed",
    "submission_id": 123,
    "interview_id": 100,
    "completion_reason": "submitted",
    "submitted_at": "2026-02-14T11:00:00Z",
    "exchanges_completed": 10
}
```

### InterviewExpired

```python
{
    "event_type": "interview_expired",
    "submission_id": 123,
    "interview_id": 100,
    "expired_at": "2026-02-14T11:00:00Z",
    "exchanges_completed": 7,
    "auto_submitted": true
}
```

---

## 9. Edge Cases to Handle

### 1. Double Start Request

**Scenario:** Candidate clicks "Start Interview" twice rapidly.

**Handling:**

- Use atomic UPDATE with precondition: `WHERE status = 'pending'`
- First request succeeds, second returns existing session (idempotent)
- Return 200 with same started_at timestamp

---

### 2. Late Answer After Timeout

**Scenario:** Interview expires at T=60:00, answer arrives at T=60:05.

**Handling:**

- Check `expires_at` before accepting answer
- If expired, return 409 Conflict: "Interview has expired"
- Do NOT create exchange for late answer

---

### 3. Simultaneous Audio and Code Completion

**Scenario:** Audio detects silence at same time code execution completes.

**Handling:**

- Both trigger exchange creation
- UNIQUE constraint on (submission_id, sequence_order) prevents duplicate
- Second INSERT fails with IntegrityError
- Both handlers report success (idempotent)

---

### 4. Reconnect Mid-Session

**Scenario:** Network drops, candidate reconnects.

**Handling:**

- Fetch current session from Redis
- Return current question based on `current_exchange_sequence`
- If exchange already created for current sequence, return next question

---

### 5. Exchange Created Before Response Fully Received

**Scenario:** Audio signals completion, exchange created, but code submission still uploading.

**Handling:**

- NEVER create exchange until ALL response data received
- Wait for: response_text OR (response_code + execution result)
- Use state flag: `response_ready = true` before exchange creation

---

### 6. Evaluation Triggered Twice

**Scenario:** WebSocket and API both trigger evaluation after exchange creation.

**Handling:**

- Evaluation module enforces UNIQUE constraint on exchange_id
- Second trigger returns existing evaluation (idempotent)
- Interview module does NOT implement deduplication logic (delegated)

---

### 7. Template Changed During Interview

**Scenario:** Admin updates template while candidate is mid-interview.

**Handling:**

- In-progress interview uses `template_structure_snapshot` (frozen)
- Template change does NOT affect current session
- New interviews use updated template

---

### 8. WebSocket Desync from Redis

**Scenario:** Redis evicts session, but WebSocket still connected.

**Handling:**

- On next WebSocket event, check Redis session
- If missing, fetch from PostgreSQL and restore to Redis
- If interview completed, send `interview_completed` event and close WebSocket

---

### 9. Two WebSocket Connections

**Scenario:** Candidate opens interview in two browser tabs.

**Handling:**

- Store single `active_websocket:{submission_id}` in Redis
- New connection replaces old connection_id
- Send `connection_replaced` event to old client, close connection

---

### 10. Zero-Duration Interview (Immediate Submit)

**Scenario:** Candidate starts interview and immediately submits without answering.

**Handling:**

- Allow state transition: pending → in_progress → completed
- Create 0 exchanges
- Evaluation module handles "no exchanges" case (low score)

---

## 10. Concurrency Concerns

### 1. Redis Locks

**When to use:**

- Starting interview (prevent double start)
- Creating exchange (prevent duplicate sequence)
- Transitioning state (prevent race)

**Implementation:**

```python
from redis import Redis
import uuid

def acquire_lock(redis: Redis, submission_id: int, timeout: int = 10) -> str:
    lock_key = f"interview_lock:{submission_id}"
    lock_value = str(uuid.uuid4())
    acquired = redis.set(lock_key, lock_value, nx=True, ex=timeout)
    if not acquired:
        raise ConcurrencyError("Lock already held")
    return lock_value

def release_lock(redis: Redis, submission_id: int, lock_value: str) -> None:
    lock_key = f"interview_lock:{submission_id}"
    current_value = redis.get(lock_key)
    if current_value and current_value.decode() == lock_value:
        redis.delete(lock_key)
```

---

### 2. Database Transactions

**Critical operations requiring transactions:**

- Start interview (update status + set started_at + update Redis)
- Create exchange (insert exchange + update current_sequence + trigger event)
- Complete interview (update status + set submitted_at + update Redis)

**Pattern:**

```python
with db.begin():
    # Step 1: Update database
    submission.submission_status = 'in_progress'
    submission.started_at = datetime.utcnow()
    db.commit()

    # Step 2: Update Redis (after commit)
    redis.set(f"interview_session:{submission.id}", session_data)
```

---

### 3. Row-Level Locking

**When needed:**

- Concurrent exchange creation (SELECT FOR UPDATE on submission)

**Example:**

```python
submission = db.query(InterviewSubmission).filter(
    InterviewSubmission.id == submission_id
).with_for_update().first()

# Critical section: check sequence, create exchange
```

---

## 11. Configuration

```bash
# Interview Session
INTERVIEW_DEFAULT_DURATION_MINUTES=60
INTERVIEW_GRACE_PERIOD_MINUTES=5
MAX_CONCURRENT_INTERVIEWS_PER_CANDIDATE=1

# Redis Session State
REDIS_SESSION_PREFIX=interview_session
REDIS_LOCK_PREFIX=interview_lock
REDIS_LOCK_TIMEOUT_SECONDS=10
REDIS_WEBSOCKET_HEARTBEAT_SECONDS=30

# Exchange Creation
EXCHANGE_RESPONSE_TIMEOUT_SECONDS=300  # 5 minutes max per question
EXCHANGE_MAX_TEXT_LENGTH=50000
EXCHANGE_MAX_CODE_LENGTH=100000

# WebSocket
WEBSOCKET_RECONNECT_GRACE_SECONDS=30
WEBSOCKET_MAX_CONNECTIONS_PER_SUBMISSION=1
```

---

## 12. Testing Requirements

**Must test:**

### Unit Tests

1. **State transitions:** Valid transitions succeed, invalid rejected
2. **Template snapshot:** Frozen at creation, not re-resolved at runtime
3. **Exchange immutability:** Update attempts raise error
4. **Sequence generation:** No gaps, no duplicates

### Integration Tests

1. **Double start request:** Second request idempotent
2. **Double answer submission:** Second ignored, exchange created once
3. **Late answer after timeout:** Rejected with 409
4. **Reconnect mid-session:** Resume from current sequence
5. **Template change during interview:** In-progress uses snapshot

### Concurrency Tests

1. **Simultaneous start:** Only one succeeds
2. **Simultaneous exchange creation:** UNIQUE constraint prevents duplicate
3. **Redis lock timeout:** Lock released after timeout, retry succeeds
4. **WebSocket connection replacement:** Old connection closed

### Edge Case Tests

1. **Zero-duration interview:** Start + immediate submit
2. **All questions skipped:** Exchanges created with null responses
3. **Redis eviction mid-session:** Restored from PostgreSQL
4. **Two WebSocket connections:** Second replaces first

---

## 13. Critical Risk Areas

1. **Template recalculated at runtime:** Non-reproducible interviews
2. **Exchange mutated after creation:** Audit trail corrupted
3. **Backward state transition:** completed → in_progress allowed
4. **Race condition in exchange creation:** Duplicate exchanges with same sequence
5. **No Redis lock:** Concurrent operations corrupt state
6. **Evaluation triggered before exchange persisted:** Foreign key violation
7. **WebSocket desync:** Client shows different state than server
8. **Timeout not enforced:** Late answers accepted indefinitely

---

## 14. Future Enhancements

1. **Adaptive questioning:** Skip sections based on performance
2. **Question branching:** Different questions based on previous answers
3. **Multi-session interviews:** Resume across multiple sessions
4. **Collaborative interviews:** Multiple interviewers join same session
5. **Interview replay:** Admin replays entire interview flow

---

**End of Interview Module Requirements**

---

## Architectural Intent

The interview module is:

- A **deterministic state machine orchestrator**
- The **runtime engine** that coordinates all other modules
- The **single source of runtime truth** (Redis + PostgreSQL)

It transforms:

```
Template snapshot (frozen)
→ Ordered runtime session (Redis state)
→ Immutable exchanges (PostgreSQL snapshot)
→ Evaluation triggers (event emission)
→ Completion (final state)
```

**It owns runtime truth. Everything else plugs into it.**
**It orchestrates. It does NOT decide scoring.**
**It enforces architectural invariants at runtime.**
