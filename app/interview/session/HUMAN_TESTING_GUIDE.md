# Interview Session — Human Testing Guide

## Module Summary

The `interview/session` module is the **state machine enforcement boundary** for
interview submissions.  It enforces one-way state transitions, prevents invalid
mutations, and ensures atomic state updates with distributed locking.

### State flow

```
pending → in_progress → completed/expired/cancelled → reviewed (terminal)
```

---

## 1. Automated Tests

```bash
# Unit tests (state machine + repository)
python -m pytest tests/unit/interview/session/ -v

# Integration tests (service layer with mocked DB & Redis)
python -m pytest tests/integration/interview/session/ -v

# All session tests
python -m pytest tests/unit/interview/session/ tests/integration/interview/session/ -v
```

---

## 2. Manual API Smoke Tests (curl)

> **Prerequisite:** The FastAPI server must be running and a valid JWT is required.
> Replace `$TOKEN_CANDIDATE` / `$TOKEN_ADMIN` with valid tokens.
> Replace `$SID` with an existing `interview_submissions.id` in pending status.

### 2.1 Start Interview (candidate)

```bash
curl -s -X POST http://localhost:8000/api/v1/interviews/sessions/start \
  -H "Authorization: Bearer $TOKEN_CANDIDATE" \
  -H "Content-Type: application/json" \
  -d '{"submission_id": '$SID', "consent_accepted": true}' | python -m json.tool
```

**Expected:** `200` with `status = "in_progress"`.

### 2.2 Get Status

```bash
curl -s http://localhost:8000/api/v1/interviews/sessions/$SID/status \
  -H "Authorization: Bearer $TOKEN_CANDIDATE" | python -m json.tool
```

**Expected:** `200` with session + exchanges array.

### 2.3 Complete Interview (candidate)

```bash
curl -s -X POST http://localhost:8000/api/v1/interviews/sessions/complete \
  -H "Authorization: Bearer $TOKEN_CANDIDATE" \
  -H "Content-Type: application/json" \
  -d '{"submission_id": '$SID'}' | python -m json.tool
```

**Expected:** `200` with `status = "completed"`.

### 2.4 Cancel Interview (admin)

```bash
curl -s -X POST http://localhost:8000/api/v1/interviews/sessions/cancel \
  -H "Authorization: Bearer $TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"submission_id": '$SID', "reason": "Technical issue"}' | python -m json.tool
```

**Expected:** `200` with `status = "cancelled"`.

### 2.5 Review Interview (admin)

```bash
curl -s -X POST http://localhost:8000/api/v1/interviews/sessions/review \
  -H "Authorization: Bearer $TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"submission_id": '$SID', "review_notes": "Looks good"}' | python -m json.tool
```

**Expected:** `200` with `status = "reviewed"`.

---

## 3. Error Cases to Verify

| Scenario                            | Expected                              |
| ----------------------------------- | ------------------------------------- |
| Start without consent               | `422` — consent required              |
| Start already-completed submission  | `409` — invalid state transition      |
| Complete a pending submission       | `409` — must be in_progress first     |
| Candidate tries to cancel           | `403` — admin only                    |
| Double start (idempotent)           | `200` — returns existing session      |
| Non-existent submission ID          | `404` — not found                     |

---

## 4. Files Created / Modified

### New files
| File | Purpose |
|------|---------|
| `app/interview/session/__init__.py` | Module root |
| `app/interview/session/domain/__init__.py` | Domain package |
| `app/interview/session/domain/state_machine.py` | Pure state machine logic |
| `app/interview/session/persistence/__init__.py` | Persistence package |
| `app/interview/session/persistence/models.py` | ORM models |
| `app/interview/session/persistence/repository.py` | Repository with atomic transitions |
| `app/interview/session/contracts/__init__.py` | Contracts package |
| `app/interview/session/contracts/schemas.py` | Pydantic DTOs |
| `app/interview/session/api/__init__.py` | API package |
| `app/interview/session/api/service.py` | Service (orchestration + Redis sync) |
| `app/interview/session/api/routes.py` | FastAPI router |
| `app/interview/session/HUMAN_TESTING_GUIDE.md` | This file |
| `app/persistence/postgres/migrations/DEV-36_add-submission-status-expired-cancelled.sql` | Migration |
| `app/persistence/postgres/migrations/DEV-36_add-submission-status-expired-cancelled_rollback.sql` | Rollback |
| `tests/unit/interview/session/domain/test_state_machine.py` | State machine tests |
| `tests/unit/interview/session/persistence/test_repository.py` | Repository tests |
| `tests/integration/interview/session/test_session_service.py` | Service integration tests |

### Modified files
| File | Change |
|------|--------|
| `app/persistence/postgres/base.py` | Added `import app.interview.session.persistence.models` |
| `app/bootstrap/router_registry.py` | Registered session router at `/api/v1/interviews/sessions` |
