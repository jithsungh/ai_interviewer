# Coding Persistence Layer - Data Access for Code Submissions

## 1. Purpose

**Why this submodule exists:**

The Coding Persistence layer provides **repository pattern implementations** for code submission data access. It:

- Abstracts database operations for `code_submissions` and `code_execution_results`
- Enforces data integrity constraints (UNIQUE, foreign keys)
- Provides query methods for submission workflows
- Handles database transactions
- Isolates execution layer from SQLAlchemy ORM details

**Critical responsibility:** This is the **only layer** that directly accesses coding tables. Execution logic never writes raw SQL or imports ORM models directly.

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
    score NUMERIC(5, 2) DEFAULT 0,
    execution_time_ms INTEGER,
    memory_kb INTEGER,
    compiler_output TEXT,
    submitted_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP,
    UNIQUE(interview_exchange_id)
);

CREATE INDEX idx_code_submissions_exchange ON code_submissions(interview_exchange_id);
CREATE INDEX idx_code_submissions_status ON code_submissions(execution_status);
CREATE INDEX idx_code_submissions_problem ON code_submissions(coding_problem_id);
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
    feedback TEXT,
    executed_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(code_submission_id, test_case_id)
);

CREATE INDEX idx_code_execution_results_submission ON code_execution_results(code_submission_id);
CREATE INDEX idx_code_execution_results_test_case ON code_execution_results(test_case_id);
```

---

## 3. Input Contracts

### Repository Methods

#### CodeSubmissionRepository

```python
class CodeSubmissionRepository:
    def create(
        self,
        interview_exchange_id: int,
        coding_problem_id: int,
        language: str,
        source_code: str
    ) -> CodeSubmission:
        """Create new code submission with status=pending"""

    def get_by_id(self, submission_id: int) -> Optional[CodeSubmission]:
        """Get submission by ID"""

    def get_by_exchange_id(self, exchange_id: int) -> Optional[CodeSubmission]:
        """Get submission by interview_exchange_id (UNIQUE constraint)"""

    def get_for_update(self, submission_id: int) -> Optional[CodeSubmission]:
        """Get submission with row-level lock (SELECT ... FOR UPDATE)"""

    def update_status(
        self,
        submission_id: int,
        execution_status: str,
        score: float = None,
        execution_time_ms: int = None,
        memory_kb: int = None,
        compiler_output: str = None,
        executed_at: datetime = None
    ):
        """Update submission execution status and results"""

    def list_by_interview(self, interview_id: int) -> List[CodeSubmission]:
        """List all submissions for an interview"""

    def list_pending(self, limit: int = 100) -> List[CodeSubmission]:
        """List pending submissions (for worker queue processing)"""

    def count_submissions_by_candidate(
        self,
        candidate_id: int,
        since: datetime
    ) -> int:
        """Count submissions by candidate since timestamp (for rate limiting)"""
```

#### CodeExecutionResultRepository

```python
class CodeExecutionResultRepository:
    def create(
        self,
        code_submission_id: int,
        test_case_id: int,
        passed: bool,
        actual_output: str,
        runtime_ms: int,
        memory_kb: int,
        exit_code: int,
        stderr_output: str,
        feedback: str
    ) -> CodeExecutionResult:
        """Create test case execution result"""

    def get_by_submission(self, submission_id: int) -> List[CodeExecutionResult]:
        """Get all test case results for a submission"""

    def get_by_submission_and_test(
        self,
        submission_id: int,
        test_case_id: int
    ) -> Optional[CodeExecutionResult]:
        """Get specific test case result (for idempotency check)"""

    def exists(self, submission_id: int, test_case_id: int) -> bool:
        """Check if test case result already exists"""
```

---

## 4. Output Contracts

### ORM Models

#### CodeSubmission Model

```python
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, CheckConstraint, ForeignKey
from sqlalchemy.orm import relationship

class CodeSubmission(Base):
    __tablename__ = "code_submissions"

    id = Column(Integer, primary_key=True)
    interview_exchange_id = Column(
        Integer,
        ForeignKey("interview_exchanges.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )
    coding_problem_id = Column(
        Integer,
        ForeignKey("coding_problems.id"),
        nullable=False
    )
    language = Column(String(20), nullable=False)
    source_code = Column(Text, nullable=False)
    execution_status = Column(String(20), nullable=False, default='pending')
    score = Column(Numeric(5, 2), default=0)
    execution_time_ms = Column(Integer)
    memory_kb = Column(Integer)
    compiler_output = Column(Text)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)

    # Relationships
    interview_exchange = relationship("InterviewExchange", back_populates="code_submission")
    coding_problem = relationship("CodingProblem")
    execution_results = relationship("CodeExecutionResult", back_populates="code_submission", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "language IN ('cpp', 'java', 'python3')",
            name="language_check"
        ),
        CheckConstraint(
            "execution_status IN ('pending', 'running', 'passed', 'failed', 'error', 'timeout', 'memory_exceeded')",
            name="execution_status_check"
        ),
    )
```

#### CodeExecutionResult Model

```python
class CodeExecutionResult(Base):
    __tablename__ = "code_execution_results"

    id = Column(Integer, primary_key=True)
    code_submission_id = Column(
        Integer,
        ForeignKey("code_submissions.id", ondelete="CASCADE"),
        nullable=False
    )
    test_case_id = Column(
        Integer,
        ForeignKey("test_cases.id"),
        nullable=False
    )
    passed = Column(Boolean, nullable=False)
    actual_output = Column(Text)
    runtime_ms = Column(Integer)
    memory_kb = Column(Integer)
    exit_code = Column(Integer)
    stderr_output = Column(Text)
    feedback = Column(Text)
    executed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    code_submission = relationship("CodeSubmission", back_populates="execution_results")
    test_case = relationship("TestCase")

    __table_args__ = (
        UniqueConstraint(
            'code_submission_id',
            'test_case_id',
            name='uq_submission_test_case'
        ),
    )
```

---

## 5. Acceptance Criteria

### Functional Requirements

#### 1. CodeSubmissionRepository

**Create Submission:**

- Insert into `code_submissions` table
- Set default `execution_status='pending'`
- Set default `score=0`
- Set `submitted_at=NOW()`
- Enforce UNIQUE constraint on `interview_exchange_id`
- Return CodeSubmission model

**Get by ID:**

- Query by `id`
- Return None if not found

**Get by Exchange ID:**

- Query by `interview_exchange_id`
- Leverage UNIQUE constraint (at most one result)
- Return None if not found

**Get for Update:**

- Query with `SELECT ... FOR UPDATE` (row-level lock)
- Prevents concurrent execution of same submission
- Return locked CodeSubmission model

**Update Status:**

- Update `execution_status`
- Optionally update `score`, `execution_time_ms`, `memory_kb`, `compiler_output`, `executed_at`
- Atomic update (single UPDATE statement)

**List by Interview:**

- Query all submissions for exchanges belonging to interview
- Join: code_submissions → interview_exchanges → interviews
- Filter by `interview_id`
- Order by `submitted_at DESC`

**List Pending:**

- Query submissions where `execution_status='pending'`
- Order by `submitted_at ASC` (FIFO)
- Limit results (e.g., 100)

**Count Submissions by Candidate:**

- Query submissions for candidate since timestamp
- Join: code_submissions → interview_exchanges → interviews → candidates
- Filter by `candidate_id` and `submitted_at >= since`
- Return count

---

#### 2. CodeExecutionResultRepository

**Create Result:**

- Insert into `code_execution_results` table
- Enforce UNIQUE constraint on `(code_submission_id, test_case_id)`
- Set `executed_at=NOW()`
- Return CodeExecutionResult model

**Get by Submission:**

- Query all results for `code_submission_id`
- Order by `test_case_id ASC`
- Return list

**Get by Submission and Test:**

- Query by `code_submission_id` and `test_case_id`
- Return None if not found

**Exists:**

- Check if result exists for `(code_submission_id, test_case_id)`
- Return boolean (efficient, no full model load)

---

### Non-Functional Requirements

1. **Query Performance:**
   - Submission lookup by ID: <10ms p95 (indexed)
   - Submission lookup by exchange_id: <10ms p95 (indexed, unique)
   - Test case results by submission: <20ms p95 (indexed)

2. **Transaction Safety:**
   - Submission creation: atomic
   - Status update + result creation: atomic (single transaction)
   - Row-level locking prevents concurrent execution

3. **Constraint Enforcement:**
   - UNIQUE constraint on `interview_exchange_id`
   - UNIQUE constraint on `(code_submission_id, test_case_id)`
   - CHECK constraints on `language` and `execution_status`

---

## 6. Invariants & Constraints

### Must Hold

1. **One Submission Per Exchange:** UNIQUE constraint on `interview_exchange_id` enforced
2. **One Result Per Test Case:** UNIQUE constraint on `(code_submission_id, test_case_id)`
3. **Valid Language:** Language in ('cpp', 'java', 'python3')
4. **Valid Status:** execution_status in allowed values
5. **Cascading Deletes:** If exchange deleted, submission deleted (ON DELETE CASCADE)
6. **Non-Null Source Code:** source_code cannot be NULL or empty

### Forbidden

- MUST NOT allow duplicate submissions for same exchange
- MUST NOT allow duplicate test case results
- MUST NOT allow NULL in required fields (interview_exchange_id, coding_problem_id, language, source_code)
- MUST NOT bypass constraints via raw SQL
- MUST NOT modify immutable fields (interview_exchange_id, coding_problem_id) after creation

---

## 7. Dependent Modules

### Upstream (Callers)

1. **API Layer:** Creates submissions, fetches status
2. **Execution Layer:** Updates status, creates test results
3. **Evaluation Layer (indirect):** Reads scores

### Downstream (Dependencies)

1. **Database (PostgreSQL):** SQLAlchemy ORM
2. **SQLAlchemy Core:** Query builder, constraints

---

## 8. Edge Cases to Handle

### 1. Duplicate Submission

**Scenario:** Candidate submits code twice for same exchange.

**Handling:**

- First INSERT succeeds
- Second INSERT fails with `IntegrityError` (UNIQUE constraint violated)
- Repository catches error, raises `DuplicateSubmissionError`

---

### 2. Exchange Deleted During Execution

**Scenario:** Interview exchange deleted while code executing.

**Handling:**

- Foreign key `ON DELETE CASCADE` deletes submission
- Worker fetches submission, finds None
- Worker logs warning, exits gracefully

---

### 3. Concurrent Execution Attempt

**Scenario:** Two workers try to execute same submission simultaneously.

**Handling:**

- Use `get_for_update()` to acquire row lock
- First worker locks row, updates status to `running`
- Second worker waits for lock, sees status already `running`, exits

---

### 4. Test Case Result Already Exists

**Scenario:** Worker retries execution, some test cases already have results.

**Handling:**

- Before creating result, check `exists(submission_id, test_case_id)`
- If exists, skip test case execution (idempotent)
- If not, execute and create result

---

### 5. Large Source Code

**Scenario:** Candidate submits 100KB source code (exceeds limit).

**Handling:**

- Validation at API layer (max 50KB)
- Database stores TEXT (no size limit)
- Rejection happens before persistence

---

### 6. Large Actual Output

**Scenario:** Code prints 10MB of output.

**Handling:**

- Truncate output at 1MB before storing
- Append "... (output truncated)"
- Prevent database bloat

---

## 9. Concurrency Concerns

### 1. Concurrent Submission Creation

**Scenario:** Candidate submits code twice rapidly.

**Handling:**

- UNIQUE constraint on `interview_exchange_id`
- First INSERT succeeds, second fails with `IntegrityError`
- API returns 409 Conflict

---

### 2. Concurrent Status Updates

**Scenario:** Two workers try to update status simultaneously.

**Handling:**

- Use `get_for_update()` to acquire row lock
- First worker updates, releases lock
- Second worker sees updated status, exits

---

### 3. Concurrent Result Creation

**Scenario:** Worker retries, parallel tasks create same test result.

**Handling:**

- UNIQUE constraint on `(code_submission_id, test_case_id)`
- First INSERT succeeds, second fails
- Idempotent (no harm)

---

### 4. Transaction Isolation

**Scenario:** Worker reads submission status while another updates it.

**Handling:**

- Use READ COMMITTED isolation level (default)
- If need stronger consistency, use `get_for_update()`

---

## 10. Configuration

### Environment Variables

```bash
# Database Connection
DATABASE_URL=postgresql://user:pass@localhost/ai_interviewer

# Connection Pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Query Logging (dev only)
DB_ECHO=false
```

---

## 11. Query Optimization

### Indexes

**code_submissions:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `interview_exchange_id`
- INDEX on `execution_status` (for listing pending)
- INDEX on `coding_problem_id` (for analytics)

**code_execution_results:**

- PRIMARY KEY on `id`
- UNIQUE INDEX on `(code_submission_id, test_case_id)`
- INDEX on `code_submission_id` (for fetching results)

---

### Common Queries

**1. Get submission by exchange:**

```sql
SELECT * FROM code_submissions
WHERE interview_exchange_id = ?
LIMIT 1;
```

**Optimization:** UNIQUE index on `interview_exchange_id` → index-only scan

---

**2. List pending submissions:**

```sql
SELECT * FROM code_submissions
WHERE execution_status = 'pending'
ORDER BY submitted_at ASC
LIMIT 100;
```

**Optimization:** INDEX on `execution_status` + `submitted_at`

---

**3. Get test case results:**

```sql
SELECT * FROM code_execution_results
WHERE code_submission_id = ?
ORDER BY test_case_id ASC;
```

**Optimization:** INDEX on `code_submission_id` → index scan

---

**4. Count candidate submissions (rate limiting):**

```sql
SELECT COUNT(*) FROM code_submissions cs
JOIN interview_exchanges ie ON cs.interview_exchange_id = ie.id
JOIN interviews i ON ie.interview_id = i.id
WHERE i.candidate_id = ?
  AND cs.submitted_at >= ?;
```

**Optimization:** INDEX on `submitted_at`, INDEX on foreign keys

---

## 12. Testing Requirements

**Must test:**

### Repository Tests

1. **Create Submission:** Verify INSERT succeeds
2. **Duplicate Submission:** Verify UNIQUE constraint raises error
3. **Get by ID:** Verify query returns correct submission
4. **Get for Update:** Verify row lock acquired
5. **Update Status:** Verify UPDATE modifies fields
6. **List Pending:** Verify filtering and ordering
7. **Create Result:** Verify INSERT with test case results
8. **Duplicate Result:** Verify UNIQUE constraint raises error

### Concurrency Tests

1. **Concurrent Submission Creation:** Verify one succeeds, one fails
2. **Concurrent Status Update:** Verify lock prevents race condition
3. **Concurrent Result Creation:** Verify UNIQUE constraint prevents duplicates

### Edge Case Tests

1. **Exchange Deleted:** Verify cascading delete removes submission
2. **Large Output:** Verify truncation at persistence layer
3. **Null Fields:** Verify NOT NULL constraints

---

## 13. Future Enhancements

1. **Soft Deletes:**
   - Add `deleted_at` column
   - Filter out soft-deleted records

2. **Audit Trail:**
   - Track submission history (resubmissions in practice mode)
   - Store previous versions

3. **Query Result Caching:**
   - Cache test case results (read frequently, write once)
   - Invalidate on update

4. **Partitioning:**
   - Partition code_submissions by date (for archival)
   - Improve query performance on large datasets

5. **Read Replicas:**
   - Route read queries to replicas
   - Write queries to primary

---

**End of Coding Persistence Layer Requirements**
