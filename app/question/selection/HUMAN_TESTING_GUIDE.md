# Question Selection Module — Human Testing Guide

**Module:** `app/question/selection`  
**Ticket:** DEV-38  
**Purpose:** Verify question selection, difficulty adaptation, repetition prevention, and fallback strategies  
**Prerequisites:** Running PostgreSQL with DEV-38 migration applied, application server running

---

## Prerequisites

### 1. Apply Migration

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate

# Apply the difficulty_adaptation_log table migration
psql "$DATABASE_URL" -f app/persistence/postgres/migrations/DEV-38_difficulty-adaptation-log.sql
```

**Verify table exists:**
```bash
psql "$DATABASE_URL" -c "\d difficulty_adaptation_log"
```

### 2. Start Application

```bash
uvicorn main:app --reload --port 8000
```

### 3. Obtain Admin JWT

```bash
# Login as admin (adjust credentials per environment)
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123"}' \
  | jq -r '.access_token')
echo $TOKEN
```

---

## Test Scenarios

### Test 1: Adaptation Log Endpoint

**Objective:** Verify admin can retrieve adaptation logs for a submission.

#### 1.1 Empty Log (No Decisions Yet)

```bash
curl -s -X GET http://localhost:8000/api/v1/questions/selection/adaptation-log/99999 \
  -H "Authorization: Bearer $TOKEN" | jq .
```

**Expected (200 OK):**
```json
[]
```

#### 1.2 Unauthorized Access

```bash
curl -s -X GET http://localhost:8000/api/v1/questions/selection/adaptation-log/1 | jq .
```

**Expected (401 or 403):**
```json
{
  "detail": "Not authenticated"
}
```

---

### Test 2: Unit Tests (Automated)

Run all 157 unit tests — no external services required.

```bash
cd /home/jithsungh/projects/ai_interviewer
source .venv/bin/activate

python -m pytest tests/unit/question/selection/ -v --tb=short
```

**Expected:** `157 passed`

#### Test Breakdown:
| File | Tests | Coverage |
|------|-------|----------|
| `test_contracts.py` | 34 | All DTOs, enums, validators |
| `test_difficulty.py` | 33 | Escalation, downgrade, maintain, edge cases |
| `test_template_parser.py` | 29 | Template validation, section lookup, config parsing |
| `test_repetition.py` | 19 | Exact match, semantic check, batch filtering |
| `test_fallback.py` | 15 | Fallback type mapping, relaxed thresholds, constants |
| `test_service.py` | 27 | Service orchestration with mocked dependencies |

---

### Test 3: Integration Tests (Requires PostgreSQL)

```bash
export DATABASE_URL="postgresql+psycopg2://postgres:password@localhost/interviewer"
python -m pytest tests/integration/question/selection/ -v --tb=short
```

**Expected:** `9 passed`

#### Integration Test Breakdown:
| File | Tests | Coverage |
|------|-------|----------|
| `test_adaptation_repository.py` | 4 | INSERT, query-by-submission, latest, empty |
| `test_selection_service.py` | 5 | Full workflow, adaptive, section isolation |

---

### Test 4: Programmatic Selection (Python Shell)

Verify the service works end-to-end (with mocked retrieval):

```python
from unittest.mock import MagicMock
from app.question.retrieval.contracts import (
    QuestionCandidate, RetrievalResult, RetrievalStrategy
)
from app.question.selection.contracts import SelectionContext
from app.question.selection.service import QuestionSelectionService

# Mock retrieval
mock_retrieval = MagicMock()
mock_retrieval.search_by_topic.return_value = RetrievalResult(
    candidates=[
        QuestionCandidate(question_id=42, similarity_score=0.9, difficulty="medium", metadata={})
    ],
    strategy_used=RetrievalStrategy.TOPIC_FILTER,
    total_found=1,
)
mock_retrieval.get_embedding_vector.return_value = None

# Create service
svc = QuestionSelectionService(retrieval_service=mock_retrieval)

# Create context
ctx = SelectionContext(
    submission_id=1,
    organization_id=1,
    template_snapshot={
        "sections": [
            {
                "section_name": "technical",
                "question_count": 5,
                "question_type": "technical",
                "selection_strategy": "static_pool",
                "difficulty_range": ["medium"],
            }
        ]
    },
    current_section="technical",
    exchange_history=[],
    exchange_sequence_order=1,
)

# Select
result = svc.select_next_question(ctx)
print(f"Selected: question_id={result.question_snapshot.question_id}")
print(f"Strategy: {result.question_snapshot.selection_strategy}")
print(f"Difficulty: {result.question_snapshot.difficulty}")
print(f"Fallback used: {result.fallback_used}")
```

**Expected Output:**
```
Selected: question_id=42
Strategy: static_pool
Difficulty: medium
Fallback used: False
```

---

### Test 5: Adaptive Difficulty Flow

Test the complete adaptive difficulty progression:

```python
from app.question.selection.contracts import (
    SelectionContext, ExchangeHistoryEntry
)

# After high-scoring first exchange → escalation
ctx = SelectionContext(
    submission_id=1,
    organization_id=1,
    template_snapshot={
        "sections": [{
            "section_name": "technical",
            "question_count": 5,
            "question_type": "technical",
            "selection_strategy": "adaptive",
            "difficulty_range": ["easy", "medium", "hard"],
        }],
        "difficulty_adaptation": {
            "enabled": True,
            "threshold_up": 80.0,
            "threshold_down": 50.0,
            "max_difficulty_jump": 1,
        },
    },
    current_section="technical",
    exchange_history=[
        ExchangeHistoryEntry(
            question_id=10,
            question_text="What is OOP?",
            difficulty="easy",
            section_name="technical",
            evaluation_score=90.0,
            sequence_order=1,
        )
    ],
    exchange_sequence_order=2,
)

result = svc.select_next_question(ctx)
print(f"Adapted to: {result.adaptation_decision.next_difficulty}")
print(f"Reason: {result.adaptation_decision.adaptation_reason}")
print(f"Changed: {result.adaptation_decision.difficulty_changed}")
```

**Expected:**
```
Adapted to: medium
Reason: score_90.0_above_threshold_80.0
Changed: True
```

---

## Rollback Procedure

If the migration needs to be reversed:

```bash
psql "$DATABASE_URL" -f app/persistence/postgres/migrations/DEV-38_difficulty-adaptation-log_rollback.sql
```

This drops the `difficulty_adaptation_log` table and its indexes.

---

## Module File Inventory

| File | Purpose |
|------|---------|
| `contracts.py` | Pydantic DTOs (SelectionContext, SelectionResult, etc.) |
| `service.py` | Main orchestrator — select_next_question() |
| `domain/difficulty.py` | Difficulty adaptation logic |
| `domain/template_parser.py` | Template snapshot parsing |
| `domain/repetition.py` | Repetition prevention |
| `domain/fallback.py` | Fallback strategy ordering |
| `persistence/models.py` | DifficultyAdaptationLogModel ORM |
| `persistence/adaptation_repository.py` | Write repo for adaptation audit |
| `api/__init__.py` | Admin endpoints (adaptation log) |
