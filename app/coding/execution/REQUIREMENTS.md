# Coding Execution Layer - Execution Lifecycle & Resource Control

## 1. Purpose

**Why this submodule exists:**

The Coding Execution layer manages the **execution lifecycle and resource control** for code submissions. It:

- Orchestrates execution workflow (compile → run → evaluate)
- Manages execution state transitions
- Enforces resource limits (time, memory, processes)
- Classifies execution failures
- Coordinates with sandbox for isolated execution
- Updates execution status atomically

**Critical responsibility:** This is the **execution orchestrator**. It ensures deterministic state transitions, prevents resource exhaustion, and maintains execution invariants.

---

## 2. Owned Tables / Entities

**None directly.** Execution layer updates `code_submissions` and `code_execution_results` via persistence layer.

---

## 3. Input Contracts

### ExecuteSubmissionCommand

```python
from dataclasses import dataclass

@dataclass
class ExecuteSubmissionCommand:
    """Command to execute a code submission"""
    submission_id: int
    submission_data: SubmissionData
    test_cases: List[TestCase]

@dataclass
class SubmissionData:
    language: str  # cpp, java, python3
    source_code: str
    coding_problem_id: int

@dataclass
class TestCase:
    test_case_id: int
    test_case_name: str
    input_data: str
    expected_output: str
    weight: int
    time_limit_ms: int
    memory_limit_kb: int
    visible: bool  # Hidden vs visible
```

---

## 4. Output Contracts

### ExecutionResult

```python
from enum import Enum
from typing import List, Optional

class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"

class TestCaseStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    MEMORY_EXCEEDED = "memory_exceeded"
    RUNTIME_ERROR = "runtime_error"

@dataclass
class TestCaseExecutionResult:
    test_case_id: int
    status: TestCaseStatus
    passed: bool
    actual_output: str
    runtime_ms: int
    memory_kb: int
    exit_code: int
    stderr: str
    feedback: str  # "Passed", "Wrong Answer", "Time Limit Exceeded", etc.

@dataclass
class ExecutionResult:
    submission_id: int
    execution_status: ExecutionStatus
    score: float  # 0-100
    total_execution_time_ms: int
    peak_memory_kb: int
    compiler_output: Optional[str]
    test_results: List[TestCaseExecutionResult]
```

---

## 5. Acceptance Criteria

### Execution Workflow

**High-level flow:**

```
1. Fetch submission from database (status=pending)
2. Acquire lock on submission (prevent concurrent execution)
3. Update status to "running"
4. Compile code (if C++ or Java)
   - If compilation fails → status=error, save compiler_output, exit
5. For each test case:
   a. Execute code with test_case.input_data via sandbox
   b. Capture stdout, stderr, exit_code, runtime_ms, memory_kb
   c. Compare actual_output vs expected_output
   d. Determine passed (boolean)
   e. Classify failure (timeout, memory_exceeded, wrong_answer, runtime_error)
   f. Save to code_execution_results
6. Calculate weighted score
7. Determine final execution_status (passed if all critical tests passed)
8. Update code_submissions with final status, score, execution_time, memory
9. Release lock
10. Emit execution_completed event
```

---

### State Transitions

**Valid transitions:**

- `pending` → `running`
- `running` → `passed`
- `running` → `failed`
- `running` → `error`
- `running` → `timeout`
- `running` → `memory_exceeded`

**Invalid transitions:**

- `passed` → any state (final)
- `failed` → any state (final)
- `error` → any state (final)
- `timeout` → any state (final)
- `memory_exceeded` → any state (final)

**Enforcement:**

- Before updating status, check current status is `running`
- If not, log warning and exit (prevents race condition overwrites)

---

### Compilation Step (C++ and Java)

**For C++:**

```bash
# Compile with g++
g++ -std=c++17 -O2 -Wall -o /tmp/sandbox/solution /tmp/sandbox/solution.cpp

# Timeout: 10 seconds
# If compilation fails:
#   - Capture stderr (compilation errors)
#   - Set execution_status = "error"
#   - Set compiler_output = stderr
#   - Exit execution
```

**For Java:**

```bash
# Compile with javac
javac -d /tmp/sandbox /tmp/sandbox/Solution.java

# Timeout: 10 seconds
# If compilation fails:
#   - Capture stderr
#   - Set execution_status = "error"
#   - Set compiler_output = stderr
#   - Exit execution
```

**For Python3:**

- No compilation step
- Validate syntax by attempting `compile(source_code, '<string>', 'exec')`
- If syntax error, set execution_status = "error" and exit

---

### Test Case Execution

**For each test case:**

1. **Prepare sandbox request:**

   ```python
   sandbox_request = {
       "language": submission.language,
       "source_code": submission.source_code,
       "input_data": test_case.input_data,
       "time_limit_ms": test_case.time_limit_ms,
       "memory_limit_kb": test_case.memory_limit_kb
   }
   ```

2. **Execute via sandbox:**

   ```python
   sandbox_result = await sandbox.execute(sandbox_request)
   # Returns: {stdout, stderr, exit_code, runtime_ms, memory_kb, timed_out, memory_exceeded}
   ```

3. **Classify result:**
   - If `timed_out = True` → status = `TIMEOUT`
   - If `memory_exceeded = True` → status = `MEMORY_EXCEEDED`
   - If `exit_code != 0` → status = `RUNTIME_ERROR`
   - If `stdout != expected_output` → status = `FAILED`
   - Else → status = `PASSED`

4. **Generate feedback:**
   - `PASSED` → "Passed"
   - `FAILED` → "Wrong Answer"
   - `TIMEOUT` → "Time Limit Exceeded"
   - `MEMORY_EXCEEDED` → "Memory Limit Exceeded"
   - `RUNTIME_ERROR` → "Runtime Error"

5. **Save to code_execution_results:**
   ```python
   execution_result_repo.create(
       code_submission_id=submission_id,
       test_case_id=test_case.test_case_id,
       passed=(status == PASSED),
       actual_output=sandbox_result.stdout,
       runtime_ms=sandbox_result.runtime_ms,
       memory_kb=sandbox_result.memory_kb,
       exit_code=sandbox_result.exit_code,
       stderr_output=sandbox_result.stderr,
       feedback=feedback
   )
   ```

---

### Score Calculation

**Formula:**

```python
total_weight = sum(tc.weight for tc in test_cases)
earned_weight = sum(tc.weight for tc, result in zip(test_cases, results) if result.passed)
score = (earned_weight / total_weight) * 100
```

**Example:**

- Test 1: weight=1, passed=True → 1 point
- Test 2: weight=2, passed=True → 2 points
- Test 3: weight=1, passed=False → 0 points
- Total weight = 1 + 2 + 1 = 4
- Earned weight = 1 + 2 + 0 = 3
- Score = (3 / 4) × 100 = 75.0

---

### Final Status Determination

**Logic:**

```python
if all(result.passed for result in test_results):
    execution_status = PASSED
elif any(result.status == TIMEOUT for result in test_results):
    execution_status = TIMEOUT
elif any(result.status == MEMORY_EXCEEDED for result in test_results):
    execution_status = MEMORY_EXCEEDED
elif any(result.status == RUNTIME_ERROR for result in test_results):
    execution_status = ERROR
else:
    execution_status = FAILED
```

**Priority:**

1. If all passed → `PASSED`
2. If any timeout → `TIMEOUT`
3. If any memory exceeded → `MEMORY_EXCEEDED`
4. If any runtime error → `ERROR`
5. Else → `FAILED`

---

### Atomic Status Update

**Implementation:**

```python
async def update_final_status(submission_id: int, result: ExecutionResult):
    async with db.transaction():
        # Acquire row lock
        submission = await repo.get_for_update(submission_id)

        # Verify still in running state
        if submission.execution_status != "running":
            logger.warning(f"Submission {submission_id} already finalized by another worker")
            return

        # Update status
        await repo.update(
            submission_id=submission_id,
            execution_status=result.execution_status,
            score=result.score,
            execution_time_ms=result.total_execution_time_ms,
            memory_kb=result.peak_memory_kb,
            compiler_output=result.compiler_output,
            executed_at=datetime.utcnow()
        )
```

---

## 6. Invariants & Constraints

### Must Hold

1. **State Determinism:** Same code + same input → same output (given infinite resources)
2. **Single Execution:** Each submission executed at most once (prevent duplicate work)
3. **Atomic Transitions:** Status updates within transaction
4. **Test Case Completeness:** All test cases executed before final status set
5. **Score Immutability:** Once execution_status is final, score never changes

### Forbidden

- MUST NOT execute code in FastAPI process (catastrophic)
- MUST NOT skip test cases (all must run or fail explicitly)
- MUST NOT modify interview_exchanges table
- MUST NOT allow concurrent execution of same submission
- MUST NOT proceed if compilation fails (mark as error immediately)

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Celery Worker:** Dequeues execution tasks, calls execute_submission()

### Downstream (Dependencies)

1. **Sandbox Module:** Executes code in isolated environment
2. **Persistence Module:** Reads/writes code_submissions, code_execution_results
3. **Evaluation Module (indirect):** Reads score from code_submissions

---

## 8. Resource Limits Enforcement

### Per-Test-Case Limits

**Time Limit:**

- Default: 2000ms (2 seconds)
- Configurable per coding_problem
- Enforced by sandbox (Docker `--stop-timeout`)

**Memory Limit:**

- Default: 262144 KB (256 MB)
- Configurable per coding_problem
- Enforced by sandbox (Docker `--memory`)

**Process Limit:**

- Max processes: 1
- Enforced by sandbox (Docker `--pids-limit=1`)

**Disk I/O:**

- Minimal (only for compilation artifacts)
- Working directory size: 100 MB

---

### Compilation Limits

**Time Limit:** 10 seconds

**Memory Limit:** 512 MB

**Why higher limits?**

- C++ templates can cause long compilation times
- Java compilation requires more memory

---

## 9. Failure Classification

### Compilation Error

**Indicators:**

- C++: `g++` returns non-zero exit code
- Java: `javac` returns non-zero exit code
- Python: `compile()` raises SyntaxError

**Handling:**

- execution_status = `error`
- compiler_output = stderr
- feedback = "Compilation Error"
- Skip test case execution

---

### Runtime Error

**Indicators:**

- exit_code != 0
- stderr contains error message

**Examples:**

- Python: `ZeroDivisionError`, `IndexError`
- Java: `NullPointerException`, `ArrayIndexOutOfBoundsException`
- C++: Segmentation fault

**Handling:**

- Test case status = `RUNTIME_ERROR`
- feedback = "Runtime Error"
- actual_output = stdout (partial output before crash)

---

### Time Limit Exceeded

**Indicators:**

- Sandbox reports `timed_out = True`
- runtime_ms >= time_limit_ms

**Handling:**

- Test case status = `TIMEOUT`
- feedback = "Time Limit Exceeded"
- actual_output = stdout (partial output before timeout)

---

### Memory Exceeded

**Indicators:**

- Sandbox reports `memory_exceeded = True`
- memory_kb >= memory_limit_kb

**Handling:**

- Test case status = `MEMORY_EXCEEDED`
- feedback = "Memory Limit Exceeded"
- actual_output = stdout (partial output before OOM kill)

---

### Wrong Answer

**Indicators:**

- exit_code = 0
- stdout != expected_output

**Handling:**

- Test case status = `FAILED`
- feedback = "Wrong Answer"
- actual_output = stdout

---

### System Error

**Indicators:**

- Sandbox throws exception
- Docker container fails to start
- Internal server error

**Handling:**

- execution_status = `error`
- feedback = "System Error"
- Log error with full details
- Retry submission (max 3 times)

---

## 10. Edge Cases to Handle

### 1. Worker Crash Mid-Execution

**Scenario:** Worker process crashes while executing test cases.

**Handling:**

- Celery task timeout (60 seconds)
- If task doesn't complete, marked as failed
- Cleanup job: Reset submissions stuck in `running` for >5 minutes back to `pending`

---

### 2. Partial Test Case Execution

**Scenario:** Worker crashes after executing 2 of 3 test cases.

**Handling:**

- On retry, check which test cases already have results
- Skip already-executed test cases (idempotent execution)
- Execute remaining test cases

---

### 3. Concurrent Execution Attempt

**Scenario:** Two workers dequeue same submission simultaneously.

**Handling:**

- Use `SELECT ... FOR UPDATE` when fetching submission
- First worker acquires lock, updates status to `running`
- Second worker finds status != `pending`, exits

---

### 4. Sandbox Timeout vs Execution Timeout

**Scenario:** Sandbox times out, but test case time limit not exceeded.

**Handling:**

- Sandbox timeout = test_case.time_limit_ms + 1000ms (grace period)
- If sandbox times out, still mark as `TIMEOUT`

---

### 5. Zero-Weight Test Cases

**Scenario:** Test case has weight=0 (e.g., example test not counted in score).

**Handling:**

- Still execute test case
- Don't include in score calculation
- Mark as passed/failed for feedback

---

### 6. All Test Cases Hidden

**Scenario:** All test cases are hidden (no visible tests).

**Handling:**

- Still execute all test cases
- Candidate sees only "Passed" or "Failed" for each test
- No expected_output revealed

---

## 11. Concurrency Concerns

### 1. Concurrent Execution of Same Submission

**Prevention:**

- Use database row-level locking: `SELECT ... FOR UPDATE`
- First worker updates status to `running`
- Second worker sees status changed, exits

---

### 2. Concurrent Execution of Different Submissions

**Handling:**

- Workers process submissions concurrently
- Each submission runs in isolated Docker container
- No shared state

---

### 3. Execution Queue Overload

**Scenario:** 1000 submissions queued, limited workers.

**Handling:**

- Workers process tasks from queue
- Queue max size: 10,000 tasks
- If queue full, reject new submissions with 503

---

## 12. Configuration

### Environment Variables

```bash
# Compilation
COMPILATION_TIMEOUT_MS=10000  # 10 seconds
COMPILATION_MEMORY_LIMIT_KB=524288  # 512MB

# Execution
DEFAULT_TIME_LIMIT_MS=2000
DEFAULT_MEMORY_LIMIT_KB=262144  # 256MB
DEFAULT_PROCESS_LIMIT=1

# Workers
CELERY_WORKERS=4
CELERY_TASK_TIMEOUT=60
MAX_EXECUTION_RETRIES=3

# Cleanup
STUCK_SUBMISSION_TIMEOUT_MINUTES=5
CLEANUP_INTERVAL_MINUTES=10
```

---

## 13. Future Enhancements

1. **Parallel Test Execution:**
   - Run multiple test cases in parallel
   - Careful resource management (CPU/memory allocation)

2. **Caching Compiled Binaries:**
   - Hash source code
   - Reuse compilation output for identical code

3. **Streaming Output:**
   - Stream stdout/stderr in real-time (WebSocket)

4. **Custom Judges:**
   - Allow custom comparison logic (e.g., floating point tolerance)

5. **Execution Metrics:**
   - Track execution time percentiles
   - Compare candidate performance

---

**End of Coding Execution Layer Requirements**
