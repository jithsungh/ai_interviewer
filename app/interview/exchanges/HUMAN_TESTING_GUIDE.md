# Interview Exchanges — Human Testing Guide

**Module:** `app/interview/exchanges`  
**Purpose:** Immutable exchange creation, sequence validation, intent classification, state machine, and clarification policy  
**Ticket:** DEV-42  
**Branch:** `feature/DEV-42-implement-module-interview-exchanges`

---

## Module Summary

The `interview/exchanges` module is the **immutability enforcement boundary** for interview exchanges.  
Exchanges are created ONCE with complete snapshot data and NEVER updated or deleted.

### Architectural Invariants

| Invariant | Enforcement |
|-----------|-------------|
| Exchanges are **IMMUTABLE** | `update()` / `delete()` always raise `ExchangeImmutabilityViolation` |
| Exchanges are **SNAPSHOTS** | Question text, expected answer, difficulty copied at creation time |
| Exchanges are **SEQUENCED** | No gaps, no duplicates (validated + UNIQUE DB constraint) |
| One exchange = one evaluation | `question_id` OR `coding_problem_id` per exchange |

### Important: No REST API Endpoints

This module does **NOT** expose REST endpoints directly.  
It is consumed by the **orchestration layer** (`interview/orchestration`) and the **session API** (`interview/session/api/routes.py`).  
Manual smoke tests are done through the session endpoints or via programmatic Python usage.

---

## 1. Automated Tests

```bash
# All exchange tests (fast — no DB, no network)
python -m pytest tests/unit/interview/exchanges/ tests/integration/interview/exchanges/ -v

# Unit only
python -m pytest tests/unit/interview/exchanges/ -v

# Integration only (mocked DB session)
python -m pytest tests/integration/interview/exchanges/ -v

# Specific test class
python -m pytest tests/unit/interview/exchanges/test_repository.py -v
python -m pytest tests/unit/interview/exchanges/test_question_state_machine.py -v
python -m pytest tests/unit/interview/exchanges/test_intent_classifier.py -v
python -m pytest tests/unit/interview/exchanges/test_clarification_policy.py -v
python -m pytest tests/unit/interview/exchanges/test_contracts.py -v
python -m pytest tests/unit/interview/exchanges/test_validators.py -v
```

**Expected:** 135 tests pass, 0 failures.

---

## 2. Manual Programmatic Testing (Python REPL)

Since exchanges have no REST API, test them via the Python REPL.  
Prerequisite: `source .venv/bin/activate`

### 2.1 Exchange Creation Contracts

```python
from app.interview.exchanges.contracts import ExchangeCreationData, ContentMetadata

# Valid text exchange
data = ExchangeCreationData(
    submission_id=1,
    sequence_order=1,
    question_id=10,
    question_text="Explain polymorphism.",
    expected_answer="Objects of different types sharing a common interface.",
    difficulty_at_time=3,
    response_text="Polymorphism means different classes can use the same method name.",
    response_time_ms=45000,
    content_metadata=ContentMetadata(
        question_type="text",
        section_name="OOP Concepts",
    ),
)
print(data.model_dump_json(indent=2))
# ✓ Should succeed
```

### 2.2 Contract Validation — Negative Cases

```python
from pydantic import ValidationError
from app.interview.exchanges.contracts import ExchangeCreationData

# Missing required question_text
try:
    ExchangeCreationData(
        submission_id=1,
        sequence_order=1,
        question_id=10,
        expected_answer="x",
        difficulty_at_time=3,
    )
except ValidationError as e:
    print(e)
    # ✓ Should show "question_text" is required

# Invalid difficulty (out of 1-5 range)
try:
    ExchangeCreationData(
        submission_id=1,
        sequence_order=1,
        question_text="Q?",
        expected_answer="A",
        difficulty_at_time=10,
    )
except ValidationError as e:
    print(e)
    # ✓ Should show difficulty must be ≤ 5

# Zero submission_id
try:
    ExchangeCreationData(
        submission_id=0,
        sequence_order=1,
        question_text="Q?",
        expected_answer="A",
        difficulty_at_time=3,
    )
except ValidationError as e:
    print(e)
    # ✓ Should show submission_id must be positive
```

### 2.3 Sequence Validation

```python
from app.interview.exchanges.validators import validate_sequence_order
from app.interview.exchanges.errors import SequenceGapError, DuplicateSequenceError

# Valid next-in-sequence
validate_sequence_order(
    submission_id=1,
    proposed_sequence=3,
    current_exchange_count=2,
    existing_sequence_orders={1, 2},
)
print("✓ Sequence 3 accepted")

# Gap in sequence
try:
    validate_sequence_order(
        submission_id=1,
        proposed_sequence=5,
        current_exchange_count=2,
        existing_sequence_orders={1, 2},
    )
except SequenceGapError as e:
    print(f"✓ Gap detected: {e}")

# Duplicate sequence
try:
    validate_sequence_order(
        submission_id=1,
        proposed_sequence=2,
        current_exchange_count=2,
        existing_sequence_orders={1, 2},
    )
except DuplicateSequenceError as e:
    print(f"✓ Duplicate detected: {e}")
```

### 2.4 Response Completeness Validation

```python
from app.interview.exchanges.validators import validate_response_completeness
from app.interview.exchanges.errors import IncompleteResponseError

# Text question — requires response_text
validate_response_completeness({
    "content_metadata": {"question_type": "text"},
    "response_text": "My answer here",
})
print("✓ Text response valid")

# Coding question — requires response_code + code_submission_id
try:
    validate_response_completeness({
        "content_metadata": {"question_type": "coding"},
        "response_text": "See my code",
        # Missing response_code and code_submission_id
    })
except IncompleteResponseError as e:
    print(f"✓ Incomplete coding response: {e}")
```

### 2.5 Question State Machine

```python
from app.interview.exchanges.question_state_machine import (
    ExchangeState,
    QuestionStateMachine,
)
from app.interview.exchanges.errors import InvalidExchangeStateTransitionError

sm = QuestionStateMachine()
print(f"Initial state: {sm.current_state}")  # ASKED

sm.transition_to(ExchangeState.WAITING_INPUT)
print(f"After transition: {sm.current_state}")  # WAITING_INPUT

sm.submit_answer()
print(f"After answer: {sm.current_state}")  # ANSWER_SUBMITTED
print(f"Response locked: {sm.response_locked}")  # True

# Invalid transition: can't go back
try:
    sm.transition_to(ExchangeState.ASKED)
except InvalidExchangeStateTransitionError as e:
    print(f"✓ Invalid transition blocked: {e}")

# Snapshot for persistence
print(sm.to_snapshot_dict())
```

### 2.6 Intent Classification

```python
from app.interview.exchanges.intent_classifier import (
    RuleBasedIntentClassifier,
    InterviewContext,
    UtteranceIntent,
)

classifier = RuleBasedIntentClassifier()
context = InterviewContext(
    question_text="Explain polymorphism",
    exchange_state="WAITING_INPUT",
)

# Direct answer
result = classifier.classify("Polymorphism allows different classes to share methods", context)
print(f"Intent: {result.intent}")  # ANSWER
print(f"Confidence: {result.confidence}")

# Clarification request
result = classifier.classify("Can you clarify what you mean?", context)
print(f"Intent: {result.intent}")  # CLARIFICATION

# Repeat request
result = classifier.classify("Could you repeat the question?", context)
print(f"Intent: {result.intent}")  # REPEAT

# Audit trail
print(result.to_audit_dict())
```

### 2.7 Clarification Policy

```python
from app.interview.exchanges.clarification_policy import (
    ClarificationPolicy,
    ClarificationRequest,
    ClarificationResponse,
)
from app.interview.exchanges.errors import ClarificationLimitExceededError

policy = ClarificationPolicy()

# First clarification
req1 = ClarificationRequest(
    exchange_sequence=1,
    original_question="Explain polymorphism",
    candidate_utterance="What do you mean by polymorphism?",
)
print(f"Can clarify: {policy.can_clarify()}")  # True
resp1 = ClarificationResponse(
    clarification_text="Polymorphism means objects of different types...",
    is_analogy=False,
)
policy.record_clarification(req1, resp1)
print(f"Count: {policy.clarification_count}")  # 1

# Exhaust limit (default max = 3)
for i in range(2):
    policy.record_clarification(req1, resp1)

print(f"Can clarify: {policy.can_clarify()}")  # False
try:
    policy.record_clarification(req1, resp1)
except ClarificationLimitExceededError as e:
    print(f"✓ Limit exceeded: {e}")

# Audit trail
print(policy.to_audit_dict())
```

---

## 3. Smoke Tests via Session API (curl)

Exchanges are created during active interviews. Use the session endpoints:

> **Prerequisites:**  
> - FastAPI server running (`uvicorn main:app --reload --port 8000`)  
> - Valid JWT tokens (`$TOKEN_CANDIDATE`, `$TOKEN_ADMIN`)  
> - A submission in `in_progress` status (`$SID`)

### 3.1 Start Interview Session (creates submission in_progress)

```bash
curl -s -X POST http://localhost:8000/api/v1/interviews/sessions/start \
  -H "Authorization: Bearer $TOKEN_CANDIDATE" \
  -H "Content-Type: application/json" \
  -d '{"submission_id": '$SID', "consent_accepted": true}' | python -m json.tool
```

### 3.2 Get Session Status (includes exchanges array)

```bash
curl -s http://localhost:8000/api/v1/interviews/sessions/$SID/status \
  -H "Authorization: Bearer $TOKEN_CANDIDATE" | python -m json.tool
```

**Expected:** `200` with `exchanges` array (initially empty, populated during interview flow).

---

## 4. Error Cases to Verify

| Scenario | Expected Error | HTTP Code |
|----------|---------------|-----------|
| Create exchange for non-existent submission | `NotFoundError` | 404 |
| Create exchange for completed submission | `InterviewNotActiveError` | 409 |
| Create exchange with sequence gap | `SequenceGapError` | 422 |
| Create exchange with duplicate sequence | `DuplicateSequenceError` | 409 |
| Text exchange missing `response_text` | `IncompleteResponseError` | 422 |
| Coding exchange missing `response_code` | `IncompleteResponseError` | 422 |
| Call `update()` on any exchange | `ExchangeImmutabilityViolation` | 409 |
| Call `delete()` on any exchange | `ExchangeImmutabilityViolation` | 409 |
| Invalid state machine transition | `InvalidExchangeStateTransitionError` | 409 |
| Exceed clarification limit (>3) | `ClarificationLimitExceededError` | 400 |

---

## 5. Files Created

### Source Files

| File | Purpose | Lines |
|------|---------|-------|
| `app/interview/exchanges/__init__.py` | Module public API exports | 84 |
| `app/interview/exchanges/errors.py` | 6 custom error classes | ~90 |
| `app/interview/exchanges/contracts.py` | `ExchangeCreationData`, `ContentMetadata`, `ExchangeQuestionType` | ~120 |
| `app/interview/exchanges/validators.py` | `validate_sequence_order`, `validate_response_completeness` | ~100 |
| `app/interview/exchanges/repository.py` | `InterviewExchangeRepository` — immutable CRUD | ~300 |
| `app/interview/exchanges/intent_classifier.py` | `RuleBasedIntentClassifier`, `UtteranceIntent` taxonomy | ~180 |
| `app/interview/exchanges/question_state_machine.py` | `QuestionStateMachine`, `ExchangeState` lifecycle | ~200 |
| `app/interview/exchanges/clarification_policy.py` | `ClarificationPolicy` with prompt constraints | ~170 |

### Test Files

| File | Tests | Purpose |
|------|-------|---------|
| `tests/unit/interview/exchanges/test_contracts.py` | ~20 | DTO validation, edge cases |
| `tests/unit/interview/exchanges/test_validators.py` | ~15 | Sequence + response completeness |
| `tests/unit/interview/exchanges/test_repository.py` | ~25 | Mocked DB, immutability, idempotency |
| `tests/unit/interview/exchanges/test_question_state_machine.py` | ~25 | State transitions, snapshot |
| `tests/unit/interview/exchanges/test_intent_classifier.py` | ~25 | All intents, edge cases |
| `tests/unit/interview/exchanges/test_clarification_policy.py` | ~25 | Limits, audit trail, prompt constraints |
| `tests/integration/interview/exchanges/test_exchange_service.py` | ~5 | End-to-end with mocked session |

### Modified Files

**None.** This module was built entirely from new files. No existing files were modified.

### Schema Changes

**None.** Extended exchange metadata (question_type, section_name, clarification_count, intent_sequence) is stored in the existing `content_metadata` JSONB column on `interview_exchanges` table.

---

## 6. Cross-Module Dependencies

| Dependency | What Is Reused | Module |
|------------|----------------|--------|
| `InterviewExchangeModel` | ORM model (not duplicated) | `interview/session/persistence/models` |
| `InterviewSubmissionModel` | FK parent model | `interview/session/persistence/models` |
| `InterviewExchangeDTO` | Read DTO (not duplicated) | `interview/session/contracts/schemas` |
| `SubmissionStatus` | State enum for validation | `interview/session/domain/state_machine` |
| `ExchangeImmutabilityViolation` | Shared error (not duplicated) | `shared/errors` |
| `NotFoundError` | Shared error | `shared/errors` |
| `InterviewNotActiveError` | Shared error | `shared/errors` |
| `BaseError` | Error base class | `shared/errors` |
