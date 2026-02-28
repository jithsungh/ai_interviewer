# Coding Execution Module — Human Testing Guide

**Module:** `app/coding/execution` (+ `evaluation` + `persistence`)  
**Purpose:** Verify code execution lifecycle, scoring, persistence, and state machine  
**Prerequisites:** PostgreSQL with interviewer schema, Docker (for sandbox), Python venv

---

## Architecture Note

The execution module is **NOT exposed as an HTTP endpoint**.  It is a
**worker-invoked** service orchestrated by a task runner (Celery / similar).

Testing is done via:
1. **Unit tests** (pytest, no infra required)
2. **Integration tests** (pytest + live PostgreSQL)
3. **Manual Python shell** (below)

---

## Quick Start

### 1. Apply the Schema Migration

The execution module requires additional schema changes beyond the base
`docs/schema.sql`.  Apply the migration **before** running any tests
or the application.

```bash
cd /home/jithsungh/projects/ai_interviewer

# Connect to PostgreSQL (adjust credentials for your environment)
psql -h 100.95.213.103 -U postgres -d interviewer

# Apply the migration
\i app/persistence/postgres/migrations/main-coding-execution-schema.sql
```

**What the migration adds:**
| Change | Table / Type | Description |
|--------|-------------|-------------|
| `memory_exceeded` value | `code_execution_status` enum | New terminal execution state |
| `executed_at` column | `code_submissions` | Timestamp when execution finished |
| `exit_code` column | `code_execution_results` | Process exit code per test case |
| UNIQUE constraint | `code_submissions(interview_exchange_id)` | One submission per exchange |
| UNIQUE constraint | `code_execution_results(code_submission_id, test_case_id)` | One result per test+submission |
| Index | `code_submissions(execution_status)` | Speed up pending-submission queries |

### 2. Run Unit Tests (No Infra Required)

```bash
source .venv/bin/activate

# All 126 coding unit tests
python -m pytest tests/unit/coding/execution/ tests/unit/coding/evaluation/ -v

# Individual suites
python -m pytest tests/unit/coding/execution/test_enums.py -v
python -m pytest tests/unit/coding/execution/test_contracts.py -v
python -m pytest tests/unit/coding/execution/test_state_machine.py -v
python -m pytest tests/unit/coding/execution/test_service.py -v
python -m pytest tests/unit/coding/evaluation/test_comparator.py -v
python -m pytest tests/unit/coding/evaluation/test_scorer.py -v
```

**Expected:** All 126 tests pass in ~1.5s.

### 3. Run Integration Tests (Requires PostgreSQL)

```bash
# Default: connects to test cluster at 100.95.213.103
python -m pytest tests/integration/coding/execution/ -v

# Override database URL
TEST_DATABASE_URL="postgresql://user:pass@localhost/testdb" \
  python -m pytest tests/integration/coding/execution/ -v
```

**Expected:** All 18 integration tests pass.  Each test uses a
transactional session that rolls back — no permanent data changes.

---

## Manual Testing via Python Shell

For hands-on verification without pytest:

### 4. Test Output Comparison (Evaluation)

```python
source .venv/bin/activate
python3

>>> from app.coding.evaluation.comparator import normalize_output, compare_outputs

# Basic comparison
>>> compare_outputs("42\n", "42\n")
True

>>> compare_outputs("42\n", "43\n")
False

# Trailing whitespace is normalized
>>> compare_outputs("hello  \n", "hello\n")
True

# Leading whitespace is preserved (significant)
>>> compare_outputs("  hello", "hello")
False

# Multiple trailing newlines are stripped
>>> compare_outputs("42\n\n\n", "42\n")
True
```

### 5. Test Score Calculation

```python
>>> from app.coding.evaluation.scorer import calculate_score, generate_feedback
>>> from app.coding.enums import TestCaseStatus

# Equal weights, all passed
>>> calculate_score([1.0, 1.0, 1.0], [True, True, True])
100.0

# Weighted scoring: 2 of 3 pass (weighted 1, 2, 1)
>>> calculate_score([1.0, 2.0, 1.0], [True, True, False])
75.0

# All failed
>>> calculate_score([1.0, 1.0], [False, False])
0.0

# Feedback messages
>>> generate_feedback(TestCaseStatus.PASSED)
'Passed'
>>> generate_feedback(TestCaseStatus.TIMEOUT)
'Time Limit Exceeded'
>>> generate_feedback(TestCaseStatus.MEMORY_EXCEEDED)
'Memory Limit Exceeded'
```

### 6. Test State Machine

```python
>>> from app.coding.execution.state_machine import (
...     is_terminal_state, is_valid_transition, validate_transition
... )
>>> from app.coding.enums import ExecutionStatus

# Terminal states
>>> is_terminal_state(ExecutionStatus.PASSED)
True
>>> is_terminal_state(ExecutionStatus.PENDING)
False

# Valid transitions
>>> is_valid_transition(ExecutionStatus.PENDING, ExecutionStatus.RUNNING)
True
>>> is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.PASSED)
True
>>> is_valid_transition(ExecutionStatus.PENDING, ExecutionStatus.PASSED)
False

# Raises on invalid
>>> validate_transition(ExecutionStatus.PENDING, ExecutionStatus.PASSED)
Traceback (most recent call last):
  ...
ValueError: Invalid transition: pending → passed
```

### 7. Test Repository Layer (Requires PostgreSQL)

```python
import os
os.environ["TESTING"] = "1"

from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres, cleanup_postgres
from app.persistence.postgres.session import init_session_factory, get_session_factory
from app.coding.persistence.repositories import (
    SqlCodeSubmissionRepository,
    SqlCodeExecutionResultRepository,
)

# Initialize DB connection
config = DatabaseSettings(
    database_url="postgresql://postgres:interviewer%40password@100.95.213.103/interviewer",
    db_pool_size=5, db_max_overflow=2, db_pool_timeout=10,
    db_query_timeout=30, db_echo=True,  # echo=True to see SQL
)
init_postgres(config)
init_session_factory()
factory = get_session_factory()
session = factory()

# Test repository operations
sub_repo = SqlCodeSubmissionRepository(session)

# List pending submissions
pending = sub_repo.list_pending(limit=5)
print(f"Pending submissions: {len(pending)}")

# Query by exchange ID (use a known ID from your test data)
# sub = sub_repo.get_by_exchange_id(1)

# ALWAYS rollback to avoid polluting test data
session.rollback()
session.close()
cleanup_postgres()
```

### 8. Full Execution Service Test (Requires PostgreSQL + seed data)

```python
import os
os.environ["TESTING"] = "1"

from unittest.mock import MagicMock
from app.config.settings import DatabaseSettings
from app.persistence.postgres import init_postgres, cleanup_postgres
from app.persistence.postgres.session import init_session_factory, get_session_factory
from app.coding.persistence.repositories import (
    SqlCodeSubmissionRepository,
    SqlCodeExecutionResultRepository,
)
from app.coding.execution.service import ExecutionService
from app.coding.execution.contracts import (
    ExecuteSubmissionCommand,
    SubmissionData,
    TestCase,
)
from app.coding.sandbox.contracts import SandboxExecutionResult

# Initialize DB
config = DatabaseSettings(
    database_url="postgresql://postgres:interviewer%40password@100.95.213.103/interviewer",
    db_pool_size=5, db_max_overflow=2, db_pool_timeout=10,
    db_query_timeout=30, db_echo=False,
)
init_postgres(config)
init_session_factory()
factory = get_session_factory()
session = factory()

sub_repo = SqlCodeSubmissionRepository(session)
res_repo = SqlCodeExecutionResultRepository(session)

# Mock sandbox — returns correct output
sandbox = MagicMock()
sandbox.execute.return_value = SandboxExecutionResult(
    stdout="25\n", stderr="", exit_code=0,
    runtime_ms=150, memory_kb=8192,
    timed_out=False, memory_exceeded=False,
    compilation_output="",
)

service = ExecutionService(sub_repo, res_repo, sandbox)

# NOTE: You must have a submission in 'pending' status.
# Use the integration test suite instead for automated testing.
# The example below assumes submission_id=1 exists and is pending.

# cmd = ExecuteSubmissionCommand(
#     submission_id=1,
#     submission_data=SubmissionData(
#         language="python3",
#         source_code="print(int(input())**2)",
#         coding_problem_id=1,
#     ),
#     test_cases=[
#         TestCase(
#             test_case_id=1, input_data="5\n", expected_output="25\n",
#             weight=1.0, time_limit_ms=2000, memory_limit_kb=262144,
#             is_hidden=False,
#         ),
#     ],
# )
# result = service.execute(cmd)
# print(f"Status: {result.execution_status}, Score: {result.score}")

session.rollback()
session.close()
cleanup_postgres()
```

---

## Validation Checklist

| # | Scenario | How to Verify | Expected |
|---|----------|---------------|----------|
| 1 | Unit tests pass | `pytest tests/unit/coding/execution/ tests/unit/coding/evaluation/ -v` | 126 passed |
| 2 | Integration tests collect | `pytest tests/integration/coding/execution/ --collect-only` | 18 collected |
| 3 | Integration tests pass | `pytest tests/integration/coding/execution/ -v` | 18 passed |
| 4 | Output normalization | Shell test §4 | Trailing whitespace ignored |
| 5 | Score calculation | Shell test §5 | Weighted formula correct |
| 6 | State machine | Shell test §6 | Valid/invalid transitions |
| 7 | Enum values | `python3 -c "from app.coding.enums import ExecutionStatus; print(list(ExecutionStatus))"` | 7 values incl. `memory_exceeded` |
| 8 | Migration applied | `SELECT unnest(enum_range(NULL::code_execution_status));` in psql | Includes `memory_exceeded` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ImportError: cannot import name 'ExecutionService'` | Activate venv: `source .venv/bin/activate` |
| `IntegrityError: unique constraint "..."` | Migration not applied. Run §1 migration first. |
| `connection refused` on integration tests | PostgreSQL not running or wrong `TEST_DATABASE_URL` |
| `column "executed_at" does not exist` | Migration not applied. Run §1 migration. |
| `invalid input value for enum code_execution_status: "memory_exceeded"` | Migration not applied. |
| Tests pass but sandbox tests skip | Docker not available — expected for unit tests |
