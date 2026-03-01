# INTERVIEW EXCHANGES MODULE — REPO ALIGNMENT REPORT

**Ticket:** DEV-42  
**Branch:** `feature/DEV-42-implement-module-interview-exchanges`  
**Date:** 2026-03-01  
**Module:** `app/interview/exchanges`

---

## 1. FOLDER TREE

```
app/interview/exchanges/
├── __init__.py                    # Module public API (84 lines)
├── errors.py                      # 6 custom error classes (BaseError subclasses)
├── contracts.py                   # ExchangeCreationData, ContentMetadata DTOs
├── validators.py                  # validate_sequence_order, validate_response_completeness
├── repository.py                  # InterviewExchangeRepository — immutable CRUD
├── intent_classifier.py           # UtteranceIntent taxonomy, RuleBasedIntentClassifier
├── question_state_machine.py      # ExchangeState enum, QuestionStateMachine
├── clarification_policy.py        # ClarificationPolicy, prompt constraints
├── REQUIREMENTS.md                # Original requirements (pre-existing)
├── HUMAN_TESTING_GUIDE.md         # Manual testing guide
└── REPO_ALIGNMENT_REPORT.md       # This file

tests/unit/interview/exchanges/
├── __init__.py
├── test_contracts.py              # DTO validation tests
├── test_validators.py             # Sequence + response completeness tests
├── test_repository.py             # Mocked DB, immutability, idempotency tests
├── test_question_state_machine.py # State transition tests
├── test_intent_classifier.py      # Intent classification tests
└── test_clarification_policy.py   # Clarification limit + audit tests

tests/integration/interview/exchanges/
├── __init__.py
└── test_exchange_service.py       # End-to-end with mocked session
```

---

## 2. REQUIREMENTS RECONCILIATION

### Requirements from REQUIREMENTS.md vs Implementation

| Requirement | Status | Notes |
|-------------|--------|-------|
| Immutable exchange records | ✅ | `update()`/`delete()` raise `ExchangeImmutabilityViolation` |
| Snapshot semantics | ✅ | Question text, expected answer, difficulty copied at creation |
| Sequence ordering with gap/dup validation | ✅ | `validate_sequence_order` + UNIQUE DB constraint |
| Response completeness by type | ✅ | `validate_response_completeness` (text/coding/audio) |
| Intent classification taxonomy | ✅ | 7 intents: ANSWER, CLARIFICATION, REPEAT, POST_ANSWER, INVALID, INCOMPLETE, UNKNOWN |
| Question state machine | ✅ | 7 states: ASKED→WAITING_INPUT→...→NEXT_QUESTION |
| Clarification policy with limits | ✅ | Max 3, analogy limit, prompt constraints, audit trail |
| Content metadata JSONB | ✅ | Extended fields in existing `content_metadata` column |
| Idempotent duplicate handling | ✅ | IntegrityError → return existing exchange |

### Requirements NOT implemented (deferred per REQUIREMENTS.md §3.4+)

| Requirement | Reason |
|-------------|--------|
| LLM-based intent classification | Requires `app/ai/llm` integration — Protocol interface defined |
| Real-time WebSocket dispatch | Requires `app/interview/realtime` — not yet implemented |
| Audio recording analysis | Requires `app/audio/analysis` — not yet implemented |

---

## 3. CROSS-MODULE CONTRACT VALIDATION

### Reused (NOT duplicated)

| Artifact | Source Module | Usage in Exchanges |
|----------|--------------|-------------------|
| `InterviewExchangeModel` | `interview/session/persistence/models` | ORM model for all DB operations |
| `InterviewSubmissionModel` | `interview/session/persistence/models` | FK parent validation |
| `InterviewExchangeDTO` | `interview/session/contracts/schemas` | Read DTO (not reimplemented) |
| `SubmissionStatus` | `interview/session/domain/state_machine` | `IN_PROGRESS` guard check |
| `ExchangeImmutabilityViolation` | `shared/errors/exceptions` | Raised by `update()`/`delete()` |
| `NotFoundError` | `shared/errors/exceptions` | Raised when submission/exchange missing |
| `InterviewNotActiveError` | `shared/errors/exceptions` | Raised when submission not in_progress |
| `BaseError` | `shared/errors/exceptions` | Base class for new errors |

### New contracts introduced

| Artifact | Purpose |
|----------|---------|
| `ExchangeCreationData` (Pydantic) | Input DTO for exchange creation — field validators for difficulty, IDs |
| `ContentMetadata` (Pydantic) | JSONB schema: question_type, section_name, clarification tracking, intent audit |
| `ExchangeQuestionType` (str enum) | Type-safe: `text`, `coding`, `audio` |
| `UtteranceIntent` (str enum) | 7-value intent taxonomy |
| `ExchangeState` (str enum) | 7-state lifecycle |
| `UtteranceIntentClassifier` (Protocol) | Classifier interface for LLM swap |

---

## 4. SCHEMA CHANGES

**None.**

All extended metadata fields are stored in the existing `content_metadata` JSONB column on the `interview_exchanges` table. No migration files created.

The `interview_exchanges` table already has:
- `content_metadata JSONB` column
- `UNIQUE(interview_submission_id, sequence_order)` constraint
- FK to `interview_submissions(id)` with `ON DELETE CASCADE`
- Indexes on `interview_submission_id` and `question_id`

---

## 5. MIGRATION FILES

**None required.** See §4.

---

## 6. MODIFIED FILES

**None.** No existing files were modified by this implementation.

The exchanges module is self-contained. It imports from but does not modify:
- `app/interview/session/persistence/models.py`
- `app/interview/session/contracts/schemas.py`
- `app/interview/session/domain/state_machine.py`
- `app/shared/errors/exceptions.py`

Router registration is NOT needed (no REST endpoints — consumed by orchestration layer).

---

## 7. TEST RESULTS

```
135 passed in 1.72s
```

### Breakdown by file

| Test File | Tests | Coverage Area |
|-----------|-------|---------------|
| `test_contracts.py` | ~20 | Valid/invalid DTO construction, edge cases |
| `test_validators.py` | ~15 | Sequence validation, response completeness |
| `test_repository.py` | ~25 | Create, immutability, idempotency, reads |
| `test_question_state_machine.py` | ~25 | All transitions, snapshot, locked state |
| `test_intent_classifier.py` | ~25 | All 7 intents, edge cases, audit dict |
| `test_clarification_policy.py` | ~25 | Limits, analogy, prompt constraints, audit |
| `test_exchange_service.py` | ~5 | Integration with mocked session |

### Regression check

Full suite: **2985 passed, 12 failed, 9 errors** — all 21 pre-existing failures are PostgreSQL connection errors (`password authentication failed for user "test"`), unrelated to exchanges.

---

## 8. ARCHITECTURAL DECISIONS

### 8.1 Immutability enforcement at repository level
UPDATE and DELETE methods exist but ALWAYS raise `ExchangeImmutabilityViolation`. This prevents accidental use and makes immutability explicit in the API contract, not just a convention.

### 8.2 content_metadata JSONB for extended fields
Rather than adding columns (which would require a migration and potentially drift from schema.sql), extended metadata (question_type, section_name, clarification_count, intent_sequence) is stored in the existing JSONB column. The `ContentMetadata` Pydantic model provides type-safe access with validation.

### 8.3 Protocol-based intent classifier
`UtteranceIntentClassifier` is defined as a Python Protocol, allowing the rule-based implementation to be swapped for an LLM-based one without changing consumers. The `RuleBasedIntentClassifier` serves as the default/fallback.

### 8.4 State machine as value object
`QuestionStateMachine` is stateful but serializable via `to_snapshot_dict()`, enabling persistence in `content_metadata`. It tracks state, clarification count, intent sequence, and response lock — all in-memory during an exchange lifecycle.

### 8.5 No REST endpoints
Exchanges are domain objects consumed by the orchestration layer. The session API endpoints (`/sessions/{id}/status`) already expose exchanges via `InterviewExchangeDTO`. Adding duplicate REST endpoints would violate the single-responsibility boundary.
