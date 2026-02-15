# Interview Session - Submission State Machine & Transition Enforcement

## 1. Purpose

The **Session** layer is responsible for:

- Enforcing submission state machine (pending → in_progress → completed → reviewed)
- Validating state transitions (no backward transitions)
- Preventing invalid state mutations
- Ensuring atomic state updates with precondition checks
- Handling concurrent state transition requests safely

**Critical responsibility:** This is the **state machine enforcement boundary**. It must:

- Reject backward transitions (completed → in_progress FORBIDDEN)
- Reject invalid transitions (pending → completed without in_progress)
- Ensure one-way flow through states
- Handle concurrent requests deterministically
- Maintain state consistency between Redis and PostgreSQL

---

## 2. State Diagram

```
                        ┌─────────┐
                        │ pending │
                        └────┬────┘
                             │
                      start_interview()
                             │
                             ▼
                     ┌───────────────┐
                     │  in_progress  │
                     └───────┬───────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
        complete_interview() │      cancel_interview()
                │       timeout_expired()  │
                │            │            │
                ▼            ▼            ▼
           ┌──────────┐  ┌─────────┐  ┌───────────┐
           │completed │  │ expired │  │ cancelled │
           └────┬─────┘  └─────────┘  └───────────┘
                │
         admin_review()
                │
                ▼
           ┌─────────┐
           │reviewed │
           └─────────┘
```

---

## 3. State Definitions

### pending

**Definition:** Interview scheduled but not started.

**Valid transitions:**

- → in_progress (via `start_interview`)
- → cancelled (via `cancel_interview`)

**Forbidden transitions:**

- → completed (must go through in_progress)
- → reviewed (must go through completed)
- → expired (no timeout on pending)

---

### in_progress

**Definition:** Candidate actively taking interview.

**Valid transitions:**

- → completed (via `complete_interview` - normal submission)
- → expired (via `timeout_expired` - automatic)
- → cancelled (via `cancel_interview` - admin action)

**Forbidden transitions:**

- → pending (no backward)
- → reviewed (must go through completed)

---

### completed

**Definition:** Interview submitted by candidate.

**Valid transitions:**

- → reviewed (via `admin_review`)

**Forbidden transitions:**

- → pending (no backward)
- → in_progress (no backward)
- → expired (cannot expire after completion)
- → cancelled (cannot cancel after completion)

---

### expired

**Definition:** Interview timed out before completion.

**Valid transitions:**

- → reviewed (via `admin_review`)

**Forbidden transitions:**

- → pending / in_progress / completed / cancelled (terminal state except review)

---

### cancelled

**Definition:** Interview cancelled (admin action).

**Valid transitions:**

- → reviewed (via `admin_review` - optional)

**Forbidden transitions:**

- → pending / in_progress / completed / expired (terminal state except review)

---

### reviewed

**Definition:** Admin has reviewed final result.

**Valid transitions:**

- NONE (terminal state)

**Forbidden transitions:**

- ALL (reviewed is final)

---

## 4. State Transition Methods

### start_interview

**Purpose:** Transition pending → in_progress.

**Preconditions:**

1. Submission exists
2. Current state = 'pending' OR 'in_progress' (idempotent)
3. Candidate is authenticated and authorized
4. Current time within interview window (if scheduled)
5. No other active interview for candidate (if MAX_CONCURRENT = 1)

**Execution:**

```python
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

class StateTransitionError(Exception):
    pass

def start_interview(
    db: Session,
    submission_id: int,
    candidate_id: int
) -> InterviewSubmission:
    """
    Start interview (pending → in_progress).

    Raises:
        StateTransitionError: Invalid state transition
        ConcurrencyError: Already started by concurrent request
    """
    # Atomic update with precondition
    result = db.execute(
        """
        UPDATE interview_submissions
        SET
            submission_status = 'in_progress',
            started_at = NOW(),
            expires_at = NOW() + INTERVAL '60 minutes'
        WHERE id = :submission_id
        AND candidate_id = :candidate_id
        AND submission_status = 'pending'
        RETURNING *
        """,
        {"submission_id": submission_id, "candidate_id": candidate_id}
    )

    submission = result.fetchone()

    if not submission:
        # Check current state
        current = db.query(InterviewSubmission).filter(
            InterviewSubmission.id == submission_id
        ).first()

        if not current:
            raise NotFoundError(f"Submission {submission_id} not found")

        if current.submission_status == 'in_progress':
            # Idempotent: already started
            return current

        raise StateTransitionError(
            f"Cannot start interview in '{current.submission_status}' state"
        )

    db.commit()
    return submission
```

**Post-transition:**

- Update Redis session state
- Emit InterviewStarted event
- Calculate and set expires_at

---

### complete_interview

**Purpose:** Transition in_progress → completed.

**Preconditions:**

1. Current state = 'in_progress' OR 'completed' (idempotent)
2. Candidate is authenticated and authorized (or admin)

**Execution:**

```python
def complete_interview(
    db: Session,
    submission_id: int,
    candidate_id: int,
    reason: str = "submitted"
) -> InterviewSubmission:
    """
    Complete interview (in_progress → completed).

    Raises:
        StateTransitionError: Invalid state transition
    """
    result = db.execute(
        """
        UPDATE interview_submissions
        SET
            submission_status = 'completed',
            submitted_at = NOW()
        WHERE id = :submission_id
        AND candidate_id = :candidate_id
        AND submission_status = 'in_progress'
        RETURNING *
        """,
        {"submission_id": submission_id, "candidate_id": candidate_id}
    )

    submission = result.fetchone()

    if not submission:
        current = db.query(InterviewSubmission).filter(
            InterviewSubmission.id == submission_id
        ).first()

        if not current:
            raise NotFoundError(f"Submission {submission_id} not found")

        if current.submission_status == 'completed':
            # Idempotent: already completed
            return current

        raise StateTransitionError(
            f"Cannot complete interview in '{current.submission_status}' state"
        )

    db.commit()
    return submission
```

**Post-transition:**

- Update Redis session state
- Close active WebSocket connections
- Trigger final result aggregation (evaluation module)
- Emit InterviewCompleted event

---

### timeout_expired

**Purpose:** Automatic transition in_progress → expired.

**Preconditions:**

1. Current state = 'in_progress'
2. Current time > expires_at

**Execution:**

```python
from datetime import datetime

def timeout_expired(
    db: Session,
    submission_id: int
) -> InterviewSubmission:
    """
    Mark interview as expired (in_progress → expired).

    Triggered by background job checking expires_at.
    """
    result = db.execute(
        """
        UPDATE interview_submissions
        SET
            submission_status = 'expired',
            submitted_at = NOW()
        WHERE id = :submission_id
        AND submission_status = 'in_progress'
        AND expires_at < NOW()
        RETURNING *
        """,
        {"submission_id": submission_id}
    )

    submission = result.fetchone()

    if not submission:
        # Either not found, not in_progress, or not yet expired
        raise StateTransitionError("Cannot mark as expired")

    db.commit()
    return submission
```

**Post-transition:**

- Update Redis session state
- Close active WebSocket connections
- Send email notification to candidate
- Emit InterviewExpired event

---

### cancel_interview

**Purpose:** Cancel interview (pending/in_progress → cancelled).

**Preconditions:**

1. Current state = 'pending' OR 'in_progress'
2. Admin is authenticated

**Execution:**

```python
def cancel_interview(
    db: Session,
    submission_id: int,
    admin_id: int,
    reason: str
) -> InterviewSubmission:
    """
    Cancel interview (pending/in_progress → cancelled).

    Admin action only.
    """
    result = db.execute(
        """
        UPDATE interview_submissions
        SET
            submission_status = 'cancelled',
            submitted_at = NOW()
        WHERE id = :submission_id
        AND submission_status IN ('pending', 'in_progress')
        RETURNING *
        """,
        {"submission_id": submission_id}
    )

    submission = result.fetchone()

    if not submission:
        current = db.query(InterviewSubmission).filter(
            InterviewSubmission.id == submission_id
        ).first()

        if not current:
            raise NotFoundError(f"Submission {submission_id} not found")

        raise StateTransitionError(
            f"Cannot cancel interview in '{current.submission_status}' state"
        )

    db.commit()

    # Log audit trail
    log_cancellation(submission_id, admin_id, reason)

    return submission
```

**Post-transition:**

- Update Redis session state
- Close active WebSocket connections
- Send notification to candidate
- Log admin action with reason
- Emit InterviewCancelled event

---

### admin_review

**Purpose:** Mark interview as reviewed (completed/expired/cancelled → reviewed).

**Preconditions:**

1. Current state = 'completed' OR 'expired' OR 'cancelled'
2. Admin is authenticated

**Execution:**

```python
def admin_review(
    db: Session,
    submission_id: int,
    admin_id: int,
    review_notes: str
) -> InterviewSubmission:
    """
    Mark interview as reviewed (completed/expired/cancelled → reviewed).

    Admin action only.
    """
    result = db.execute(
        """
        UPDATE interview_submissions
        SET submission_status = 'reviewed'
        WHERE id = :submission_id
        AND submission_status IN ('completed', 'expired', 'cancelled')
        RETURNING *
        """,
        {"submission_id": submission_id}
    )

    submission = result.fetchone()

    if not submission:
        raise StateTransitionError("Cannot mark as reviewed")

    db.commit()

    # Log review
    log_review(submission_id, admin_id, review_notes)

    return submission
```

---

## 5. Concurrency Handling

### Atomic State Transitions

**Pattern:**

```sql
UPDATE interview_submissions
SET submission_status = '<new_state>'
WHERE id = <submission_id>
AND submission_status = '<expected_old_state>'
RETURNING *;
```

**If 0 rows updated:**

- Current state is NOT what we expected
- Either already transitioned or invalid state
- Check current state and respond appropriately

---

### Redis Lock Pattern

**When to use:** For complex multi-step transitions.

**Example:**

```python
from redis import Redis
import uuid

def start_interview_with_lock(
    db: Session,
    redis: Redis,
    submission_id: int,
    candidate_id: int
) -> InterviewSubmission:
    """
    Start interview with Redis lock for safety.
    """
    lock_key = f"interview_lock:{submission_id}"
    lock_value = str(uuid.uuid4())

    # Step 1: Acquire lock
    acquired = redis.set(lock_key, lock_value, nx=True, ex=10)
    if not acquired:
        raise ConcurrencyError("Another operation in progress")

    try:
        # Step 2: Perform state transition
        submission = start_interview(db, submission_id, candidate_id)

        # Step 3: Update Redis session state
        redis.set(
            f"interview_session:{submission_id}",
            json.dumps({
                "submission_id": submission_id,
                "status": "in_progress",
                "started_at": submission.started_at.isoformat(),
                "expires_at": submission.expires_at.isoformat()
            }),
            ex=3900  # 65 minutes (interview + grace)
        )

        return submission

    finally:
        # Step 4: Release lock
        current_value = redis.get(lock_key)
        if current_value and current_value.decode() == lock_value:
            redis.delete(lock_key)
```

---

### Double Start Prevention

**Scenario:** Two simultaneous start requests.

**Handling:**

1. First request acquires Redis lock
2. First request transitions state: UPDATE ... WHERE status = 'pending'
3. First request succeeds, releases lock
4. Second request acquires lock (after first releases)
5. Second request attempts UPDATE ... WHERE status = 'pending'
6. 0 rows updated (state already 'in_progress')
7. Second request checks current state: 'in_progress'
8. Second request returns existing session (idempotent)

---

## 6. State Validation

### Validate Preconditions

**Before any transition:**

```python
def validate_transition(
    current_state: str,
    target_state: str
) -> None:
    """
    Validate state transition is allowed.

    Raises:
        StateTransitionError: Invalid transition
    """
    valid_transitions = {
        'pending': ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'expired', 'cancelled'],
        'completed': ['reviewed'],
        'expired': ['reviewed'],
        'cancelled': ['reviewed'],
        'reviewed': []  # Terminal state
    }

    if target_state not in valid_transitions.get(current_state, []):
        raise StateTransitionError(
            f"Invalid transition: {current_state} → {target_state}"
        )
```

---

### Enforce Authorization

**State-specific authorization:**

- `start_interview`: Candidate only (own interview)
- `complete_interview`: Candidate (own) OR Admin
- `cancel_interview`: Admin only
- `admin_review`: Admin only

---

## 7. Redis Session State Sync

### Update Pattern

**After every state transition:**

1. Commit database transaction
2. Update Redis session state
3. If Redis fails, log warning (not critical - will fallback to DB)

**Example:**

```python
def sync_redis_session(
    redis: Redis,
    submission: InterviewSubmission
) -> None:
    """Sync submission state to Redis."""
    session_key = f"interview_session:{submission.id}"
    session_data = {
        "submission_id": submission.id,
        "status": submission.submission_status,
        "started_at": submission.started_at.isoformat() if submission.started_at else None,
        "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
        "expires_at": submission.expires_at.isoformat() if submission.expires_at else None,
        "current_sequence": submission.current_exchange_sequence
    }

    try:
        redis.set(session_key, json.dumps(session_data), ex=3900)
    except Exception as e:
        logger.warning(f"Failed to sync Redis session: {e}")
```

---

## 8. Background Jobs

### Timeout Monitor

**Job:** Check for expired interviews every 60 seconds.

**Query:**

```sql
SELECT id FROM interview_submissions
WHERE submission_status = 'in_progress'
AND expires_at < NOW()
LIMIT 100;
```

**For each expired submission:**

1. Call `timeout_expired(submission_id)`
2. Handle `StateTransitionError` (already transitioned)
3. Log timeout event

---

## 9. Event Publishing

### State Transition Events

**After each transition:**

```python
# InterviewStarted
{
    "event_type": "interview_started",
    "submission_id": 123,
    "candidate_id": 456,
    "started_at": "2026-02-14T10:00:00Z",
    "expires_at": "2026-02-14T11:00:00Z"
}

# InterviewCompleted
{
    "event_type": "interview_completed",
    "submission_id": 123,
    "completion_reason": "submitted",
    "submitted_at": "2026-02-14T10:45:00Z"
}

# InterviewExpired
{
    "event_type": "interview_expired",
    "submission_id": 123,
    "expired_at": "2026-02-14T11:00:00Z",
    "auto_submitted": true
}

# InterviewCancelled
{
    "event_type": "interview_cancelled",
    "submission_id": 123,
    "cancelled_by": 789,
    "reason": "Technical issue reported by candidate"
}
```

---

## 10. Testing Requirements

### Unit Tests

1. **Valid transitions:** pending → in_progress succeeds
2. **Invalid transitions:** pending → completed raises error
3. **Backward transitions:** completed → in_progress raises error
4. **Idempotency:** Double start returns same session
5. **Authorization:** Candidate cannot cancel interview

### Integration Tests

1. **Atomic transition:** Concurrent starts, only one succeeds
2. **Redis sync:** State transition updates Redis
3. **Timeout job:** Expired interviews transitioned automatically
4. **Event publishing:** State transitions emit events

### Concurrency Tests

1. **Double start:** Second request idempotent
2. **Simultaneous complete:** Only one succeeds
3. **Lock timeout:** Lock released after timeout, retry succeeds

---

## 11. Critical Risks

1. **No precondition check:** Invalid transitions allowed (completed → in_progress)
2. **No atomicity:** Race condition in concurrent starts
3. **Redis desync:** State inconsistent between PostgreSQL and Redis
4. **No timeout job:** Expired interviews stuck in 'in_progress'
5. **No authorization:** Candidate cancels own interview
6. **No event publishing:** Downstream modules not notified

---

**End of Interview Session Requirements**
