# Coding Module - Secure Code Execution Engine

## 1. Purpose

**Why this module exists:**

The Coding module is a **deterministic, isolated execution engine** for running untrusted candidate code. It:

- Handles code submission processing
- Executes code in secure sandboxed environments
- Evaluates test cases with weighted scoring
- Captures execution metadata (runtime, memory, output)
- Persists results immutably
- Supports C++, Java, Python3

**Critical responsibility:** This is a **HIGH RISK, SECURITY-CRITICAL** module. Untrusted code MUST be executed in strict isolation with OS-level resource limits. One security breach can compromise the entire system.

**Architectural philosophy:** Code execution feeds into the core invariant:

> **One exchange = one evaluation**  
> **Exchanges are immutable**

Code execution must not break this invariant. It produces immutable results that feed into the evaluation module.

---

## 2. Owned Tables / Entities

### code_submissions

```sql
CREATE TABLE code_submissions (
    id SERIAL PRIMARY KEY,
    interview_exchange_id INTEGER NOT NULL REFERENCES interview_exchanges(id) ON DELETE CASCADE,
    coding_problem_id INTEGER NOT NULL REFERENCES coding_problems(id),
    language VARCHAR(20) NOT NULL CHECK (language IN ('cpp', 'java', 'python3')),
    source_code TEXT NOT NULL,
    execution_status VARCHAR(20) NOT NULL CHECK (execution_status IN ('pending', 'running', 'passed', 'failed', 'error', 'timeout', 'memory_exceeded')),
    score NUMERIC(5, 2) DEFAULT 0,  -- 0-100
    execution_time_ms INTEGER,
    memory_kb INTEGER,
    compiler_output TEXT,
    submitted_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP,
    UNIQUE(interview_exchange_id)  -- One submission per exchange
);

CREATE INDEX idx_code_submissions_exchange ON code_submissions(interview_exchange_id);
CREATE INDEX idx_code_submissions_status ON code_submissions(execution_status);
```

### code_execution_results

```sql
CREATE TABLE code_execution_results (
    id SERIAL PRIMARY KEY,
    code_submission_id INTEGER NOT NULL REFERENCES code_submissions(id) ON DELETE CASCADE,
    test_case_id INTEGER NOT NULL REFERENCES test_cases(id),
    passed BOOLEAN NOT NULL,
    actual_output TEXT,
    runtime_ms INTEGER,
    memory_kb INTEGER,
    exit_code INTEGER,
    stderr_output TEXT,
    feedback TEXT,  -- "Wrong Answer", "Time Limit Exceeded", etc.
    executed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(code_submission_id, test_case_id)
);

CREATE INDEX idx_code_execution_results_submission ON code_execution_results(code_submission_id);
```

---

## 3. Input Contracts

### SubmitCodeRequest

```python
from pydantic import BaseModel, Field
from typing import Literal

class SubmitCodeRequest(BaseModel):
    interview_exchange_id: int = Field(gt=0)
    coding_problem_id: int = Field(gt=0)
    language: Literal["cpp", "java", "python3"]
    source_code: str = Field(min_length=1, max_length=50000)  # 50KB limit

    class Config:
        json_schema_extra = {
            "example": {
                "interview_exchange_id": 123,
                "coding_problem_id": 45,
                "language": "python3",
                "source_code": "def solution(nums):\n    return sum(nums)"
            }
        }
```

### ExecutionRequest (Internal)

```python
class ExecutionRequest(BaseModel):
    """Internal request to sandbox"""
    language: Literal["cpp", "java", "python3"]
    source_code: str
    input_data: str
    time_limit_ms: int = 2000
    memory_limit_kb: int = 262144  # 256MB
```

---

## 4. Output Contracts

### SubmitCodeResponse

```python
class SubmitCodeResponse(BaseModel):
    submission_id: int
    execution_status: Literal["pending", "running", "passed", "failed", "error", "timeout", "memory_exceeded"]
    message: str = "Code submitted successfully"
```

### ExecutionStatusResponse

```python
from typing import List, Optional

class TestCaseResult(BaseModel):
    test_case_id: int
    test_case_name: str
    passed: bool
    visible: bool  # Hidden test cases don't show expected output
    actual_output: Optional[str] = None
    expected_output: Optional[str] = None  # Only for visible tests
    runtime_ms: int
    memory_kb: int
    feedback: str  # "Passed", "Wrong Answer", "Time Limit Exceeded", etc.

class ExecutionStatusResponse(BaseModel):
    submission_id: int
    execution_status: Literal["pending", "running", "passed", "failed", "error", "timeout", "memory_exceeded"]
    score: float  # 0-100
    execution_time_ms: Optional[int] = None
    memory_kb: Optional[int] = None
    compiler_output: Optional[str] = None
    test_results: List[TestCaseResult]
```

### ExecutionResult (Internal from Sandbox)

```python
class ExecutionResult(BaseModel):
    """Result from sandbox execution"""
    stdout: str
    stderr: str
    exit_code: int
    runtime_ms: int
    memory_kb: int
    timed_out: bool = False
    memory_exceeded: bool = False
```

---

## 5. Acceptance Criteria

### Module-Level Requirements

#### 1. Code Submission Validation

**Must validate:**

- Exchange exists and belongs to candidate
- Coding problem ID matches exchange's question
- Language is supported (cpp, java, python3)
- Source code within size limit (50KB)
- No duplicate submission if rules disallow (UNIQUE constraint on interview_exchange_id)

**Must reject:**

- Invalid interview_exchange_id
- Mismatched coding_problem_id
- Unsupported language
- Empty source code
- Duplicate submissions (if one already exists for exchange)

---

#### 2. Execution Lifecycle

**Execution states:**

- `pending`: Submission received, queued for execution
- `running`: Currently executing in sandbox
- `passed`: All required test cases passed
- `failed`: One or more test cases failed
- `error`: Compilation error or runtime error
- `timeout`: Execution exceeded time limit
- `memory_exceeded`: Execution exceeded memory limit

**State transitions:**

- `pending` → `running` → (`passed` | `failed` | `error` | `timeout` | `memory_exceeded`)
- States are final (no reversal allowed)

---

#### 3. Sandbox Execution

**Must execute code:**

- In isolated Docker container (initial implementation)
- With seccomp profile enabled
- As non-root user
- With read-only filesystem (except working directory)
- With no network access
- With CPU time limit (configurable, default 2s per test)
- With memory limit (configurable, default 256MB)

**Must NOT execute:**

- Inside FastAPI process (catastrophic risk)
- With host filesystem access
- With network access
- As root user

---

#### 4. Test Case Evaluation

**For each test case:**

1. Compile code (if C++ or Java)
2. Execute with test case input_data
3. Capture stdout, stderr, exit_code, runtime_ms, memory_kb
4. Compare actual_output vs expected_output
5. Determine pass/fail
6. Calculate weighted score contribution

**Output comparison:**

- Exact match by default
- Trim trailing whitespace
- Optional: custom comparator for floating point (future)

---

#### 5. Weighted Scoring

**Formula:**

```
score = (Σ test_case.weight × pass_boolean) / (Σ test_case.weight) × 100
```

**Requirements:**

- Each test case has weight (integer, default 1)
- Total score normalized to 0-100
- Score stored in `code_submissions.score`
- Score calculation is deterministic

---

#### 6. Hidden vs Visible Test Cases

**Visible test cases:**

- Shown to candidate before submission
- Expected output visible
- Used for practice/debugging

**Hidden test cases:**

- NOT shown to candidate
- Expected output NEVER exposed in API responses
- Used for final scoring
- Prevent hardcoded solutions

**API response rules:**

- Visible tests: return actual_output, expected_output, feedback
- Hidden tests: return passed (boolean), feedback ("Passed" or "Failed"), NO expected output

---

#### 7. Failure Classification

**Must distinguish:**

- **Compilation Error:** Code failed to compile (C++, Java)
- **Runtime Error:** Execution crashed (non-zero exit code)
- **Wrong Answer:** Output doesn't match expected
- **Time Limit Exceeded:** Execution exceeded time_limit_ms
- **Memory Exceeded:** Execution exceeded memory_limit_kb
- **System Error:** Sandbox failure, internal error

**Map to execution_status:**

- Compilation Error → `error`
- Runtime Error → `error`
- Time Limit Exceeded → `timeout`
- Memory Exceeded → `memory_exceeded`
- All tests passed → `passed`
- One or more tests failed → `failed`

---

#### 8. Concurrency Handling

**Must support:**

- Multiple concurrent submissions from different candidates
- Execution queue with worker pool
- Rate limiting per candidate (e.g., 5 submissions per minute)
- Idempotency (duplicate requests don't create duplicate submissions)

**Worker queue:**

- Use Celery with Redis broker (or similar)
- Worker processes execute submissions asynchronously
- Workers update `execution_status` atomically

---

#### 9. Resource Limits Enforcement

**Per-test-case limits (configurable per coding problem):**

- CPU time: 2000ms (default)
- Memory: 256MB (default)
- Disk I/O: Minimal (only for compilation artifacts)
- Process count: 1 (prevent fork bombs)

**Enforcement:**

- Time limit: Docker `--cpus` + timeout command
- Memory limit: Docker `--memory` + `--memory-swap`
- Process limit: Docker `--pids-limit=1`

---

#### 10. Security Requirements

**Sandbox must:**

- Run container with `--security-opt=no-new-privileges`
- Use seccomp profile (block dangerous syscalls)
- Use `--network=none` (no network access)
- Run as non-root user (UID 1000)
- Mount working directory read-only except `/tmp` for compilation
- Kill process tree on timeout (no orphaned processes)
- Prevent fork bombs (`--pids-limit`)
- Prevent infinite recursion (memory limit)

**Code must NOT:**

- Access host filesystem
- Make network requests
- Execute system commands beyond language runtime
- Write to arbitrary locations
- Spawn excessive processes

---

## 6. Invariants & Constraints

### Must Hold

1. **One Submission Per Exchange:** UNIQUE constraint on `code_submissions(interview_exchange_id)`
2. **Exchange Immutability:** Code submission never modifies `interview_exchanges` table
3. **Execution Determinism:** Same code + same input → same output (given infinite resources)
4. **Score Immutability:** Once `execution_status` is final, score never changes
5. **Hidden Test Case Protection:** Hidden test case expected_output NEVER exposed via API
6. **Sandbox Isolation:** Code execution NEVER runs in FastAPI process
7. **Resource Limit Enforcement:** All executions respect time/memory limits

### Forbidden

- MUST NOT execute code in FastAPI process
- MUST NOT modify `interview_exchanges` table
- MUST NOT modify `evaluation_results` table (evaluation module owns this)
- MUST NOT expose hidden test case expected outputs
- MUST NOT allow network access from sandbox
- MUST NOT run sandbox as root
- MUST NOT leave orphaned processes after timeout
- MUST NOT log source code with sensitive data (candidate personal info in comments)

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Interview Module (`app.interview`):**
   - Submits code on behalf of candidate
   - Triggers code execution
   - Waits for execution completion

2. **Evaluation Module (`app.evaluation`):**
   - Reads `code_submissions.score` for scoring
   - Does NOT write to code_submissions

### Downstream (Dependencies)

1. **Database (PostgreSQL):**
   - Stores code_submissions, code_execution_results

2. **Docker Engine:**
   - Executes sandboxed containers

3. **Redis:**
   - Celery task queue
   - Rate limiting

4. **Coding Problem Repository:**
   - Fetches test cases for coding_problem_id

---

## 8. Event Contracts Emitted

### CodeSubmissionReceived

```python
{
    "event_type": "code_submission_received",
    "submission_id": 123,
    "interview_exchange_id": 456,
    "language": "python3",
    "timestamp": "2026-02-14T10:30:00Z"
}
```

### CodeExecutionCompleted

```python
{
    "event_type": "code_execution_completed",
    "submission_id": 123,
    "execution_status": "passed",
    "score": 85.5,
    "execution_time_ms": 145,
    "timestamp": "2026-02-14T10:30:05Z"
}
```

### CodeExecutionFailed

```python
{
    "event_type": "code_execution_failed",
    "submission_id": 123,
    "execution_status": "timeout",
    "error_message": "Time limit exceeded on test case 3",
    "timestamp": "2026-02-14T10:30:05Z"
}
```

---

## 9. Edge Cases to Handle

### 1. Infinite Loop

**Scenario:** Candidate submits code with infinite loop.

**Handling:**

- Sandbox timeout enforced by Docker (`--stop-timeout`)
- After time_limit_ms, process killed
- execution_status = `timeout`
- Test case marked as failed

---

### 2. Memory Exhaustion Attempt

**Scenario:** Code allocates excessive memory (e.g., `arr = [0] * 10**10`).

**Handling:**

- Docker memory limit enforced (`--memory=256m`)
- Process killed by OOM killer
- execution_status = `memory_exceeded`
- Test case marked as failed

---

### 3. Fork Bomb Attempt

**Scenario:** Code spawns excessive processes (e.g., `while True: os.fork()`).

**Handling:**

- Docker process limit enforced (`--pids-limit=1`)
- Additional processes rejected
- execution_status = `error`
- Test case marked as failed

---

### 4. File System Escape Attempt

**Scenario:** Code tries to read/write host filesystem (e.g., `open('/etc/passwd')`).

**Handling:**

- Docker filesystem isolation (read-only root, no bind mounts to sensitive locations)
- Seccomp profile blocks dangerous syscalls
- Operation fails with permission denied
- Code may crash, marked as `error`

---

### 5. System Call Abuse Attempt

**Scenario:** Code attempts dangerous syscalls (e.g., `ptrace`, `mount`, `reboot`).

**Handling:**

- Seccomp profile blocks dangerous syscalls
- Syscall fails with EPERM
- Code may crash, marked as `error`

---

### 6. Hidden Test Case Leak Attempt

**Scenario:** Attacker tries to infer hidden test cases by analyzing feedback.

**Handling:**

- Hidden test case expected_output NEVER returned in API
- Feedback limited to: "Passed" or "Failed" (no detailed diff)
- Logs sanitized to exclude hidden expected_output

---

### 7. Concurrent Submissions

**Scenario:** Candidate submits code twice rapidly (double-click, network retry).

**Handling:**

- UNIQUE constraint on `interview_exchange_id` prevents duplicate rows
- Second submission returns 409 Conflict with existing submission_id
- Idempotency: if request is identical, return existing submission

---

### 8. Large Input Stress Test

**Scenario:** Test case has large input (e.g., 1MB array).

**Handling:**

- Input passed to sandbox via stdin or file
- Memory limit accounts for input size
- If input + execution exceeds memory, fail with `memory_exceeded`

---

### 9. Compilation Timeout (C++/Java)

**Scenario:** C++ code with complex templates causes long compilation.

**Handling:**

- Compilation also subject to timeout (e.g., 10 seconds)
- If compilation exceeds timeout, fail with `error` and feedback "Compilation timeout"

---

### 10. Race Condition: Execution Completion + Scoring Write

**Scenario:** Two workers process same submission simultaneously.

**Handling:**

- Use database transaction with row-level locking: `SELECT ... FOR UPDATE`
- Worker acquires lock on code_submissions row
- First worker completes execution, updates status
- Second worker finds status already updated, exits

---

## 10. Concurrency Concerns

### 1. Concurrent Submissions to Same Exchange

**Scenario:** Candidate sends multiple submissions for same exchange (should be blocked by UNIQUE constraint).

**Handling:**

- UNIQUE constraint on `interview_exchange_id` enforced at DB level
- First INSERT succeeds, subsequent INSERTs fail with IntegrityError
- API returns 409 Conflict

---

### 2. Concurrent Execution of Different Submissions

**Scenario:** Multiple candidates submit code simultaneously.

**Handling:**

- Worker pool processes submissions concurrently
- Each submission runs in isolated Docker container
- No shared state between executions

---

### 3. Execution Queue Saturation

**Scenario:** 1000 submissions queued, workers overloaded.

**Handling:**

- Rate limiting per candidate (5 submissions per minute)
- Queue max size (e.g., 10,000 tasks)
- If queue full, reject new submissions with 503 Service Unavailable

---

### 4. Worker Crash During Execution

**Scenario:** Worker process crashes mid-execution, submission stuck in `running` state.

**Handling:**

- Celery task timeout (e.g., 60 seconds per submission)
- If task doesn't complete, marked as failed
- Stale `running` submissions: periodic cleanup job resets to `pending` after 5 minutes

---

## 11. Configuration

### Environment Variables

```bash
# Sandbox
SANDBOX_TYPE=docker  # docker, firecracker, gvisor (future)
DOCKER_IMAGE_CPP=code-sandbox-cpp:latest
DOCKER_IMAGE_JAVA=code-sandbox-java:latest
DOCKER_IMAGE_PYTHON=code-sandbox-python:latest

# Resource Limits
DEFAULT_TIME_LIMIT_MS=2000
DEFAULT_MEMORY_LIMIT_KB=262144  # 256MB
DEFAULT_DISK_LIMIT_MB=100
MAX_PROCESS_COUNT=1

# Execution
MAX_SOURCE_CODE_SIZE_BYTES=51200  # 50KB
COMPILATION_TIMEOUT_MS=10000  # 10s
EXECUTION_WORKERS=4

# Rate Limiting
MAX_SUBMISSIONS_PER_CANDIDATE_PER_MINUTE=5

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
CELERY_TASK_TIMEOUT=60

# Security
ENABLE_SECCOMP=true
RUN_AS_USER_UID=1000
SANDBOX_NETWORK_DISABLED=true
```

---

## 12. Testing Requirements

**Must test:**

### 1. Security Tests

- **Infinite Loop:** Code with `while True: pass`, verify timeout
- **Memory Exhaustion:** Code allocating 1GB, verify memory_exceeded
- **Fork Bomb:** Code with `os.fork()`, verify process limit
- **System Call Abuse:** Code with `os.system('rm -rf /')`, verify blocked
- **File System Escape:** Code reading `/etc/passwd`, verify denied
- **Network Access Attempt:** Code with `requests.get()`, verify blocked

### 2. Functional Tests

- **Compilation Error (C++):** Invalid syntax, verify compilation error feedback
- **Runtime Error (Python):** Division by zero, verify runtime error feedback
- **Wrong Answer:** Code returning incorrect output, verify failed test case
- **Partial Credit:** 2 of 3 tests pass, verify score = 66.67
- **Hidden Test Case Protection:** Verify hidden expected_output not in API response

### 3. Concurrency Tests

- **Concurrent Submissions:** 10 candidates submit simultaneously, verify all succeed
- **Duplicate Submission:** Same exchange submitted twice, verify 409 Conflict
- **Worker Pool Saturation:** 100 submissions queued, verify rate limiting

### 4. Edge Case Tests

- **Large Input:** 1MB string input, verify execution completes
- **Empty Output:** Code prints nothing, verify matches empty expected_output
- **Unicode Characters:** Code with emoji in output, verify correct comparison
- **Trailing Whitespace:** Output with trailing spaces, verify trimmed comparison

---

## 13. Critical Risk Areas

1. **Running code inside FastAPI process** → Catastrophic security breach
2. **Not killing child processes on timeout** → Resource leak, orphaned processes
3. **Logging source_code with sensitive data** → Privacy violation
4. **Hidden test cases leaked to logs/API** → Cheating enabled
5. **Race condition between execution completion and scoring write** → Incorrect scores
6. **No rate limiting** → DoS via excessive submissions
7. **Weak sandbox isolation** → Host compromise

---

## 14. Future Enhancements

1. **Multi-language Extension:**
   - Add support for JavaScript, Go, Rust, etc.

2. **Custom Judges:**
   - Special judge for problems requiring approximate answers (e.g., floating point)

3. **Parallel Test Execution:**
   - Run multiple test cases in parallel (with careful resource management)

4. **Cached Compiled Binaries:**
   - Cache compilation output for identical code (with hash-based deduplication)

5. **Plagiarism Detection:**
   - Compare submissions for similarity (MOSS, JPlag)

6. **Per-Language Performance Benchmarking:**
   - Track percentile rankings (e.g., "Your solution is faster than 85% of Python submissions")

7. **Interactive Problems:**
   - Support for problems requiring multiple rounds of I/O

8. **Firecracker MicroVMs:**
   - Replace Docker with Firecracker for faster startup + stronger isolation

---

**End of Coding Module Requirements**

---

## Architectural Intent

The coding module is:

- A **deterministic, isolated execution engine**
- A **security boundary** protecting the system from untrusted code
- A **scoring engine** producing immutable results

It must feel like:

```python
result = coding.execute_submission(submission_id)
```

And produce immutable results that feed into evaluation.

**No business logic. No orchestration. Pure execution.**
