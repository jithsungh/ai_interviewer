# Coding API Layer - Code Submission Endpoints

## 1. Purpose

**Why this submodule exists:**

The Coding API layer provides **HTTP endpoints** for code submission and execution status retrieval. It:

- Accepts code submissions from candidates
- Validates submission requests
- Triggers asynchronous execution
- Returns execution status and results
- Protects hidden test case data

**Critical responsibility:** This is the **public interface** for code execution. It must validate all inputs, prevent duplicate submissions, and never expose hidden test case information.

---

## 2. Owned Tables / Entities

**None.** API layer owns no database tables. It delegates to domain/persistence layers.

---

## 3. Input Contracts

### SubmitCodeRequest

```python
from pydantic import BaseModel, Field, validator
from typing import Literal

class SubmitCodeRequest(BaseModel):
    interview_exchange_id: int = Field(gt=0, description="ID of the interview exchange")
    coding_problem_id: int = Field(gt=0, description="ID of the coding problem")
    language: Literal["cpp", "java", "python3"] = Field(description="Programming language")
    source_code: str = Field(min_length=1, max_length=50000, description="Source code (max 50KB)")

    @validator('source_code')
    def validate_source_code(cls, v):
        # Strip leading/trailing whitespace
        v = v.strip()
        if not v:
            raise ValueError('Source code cannot be empty')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "interview_exchange_id": 123,
                "coding_problem_id": 45,
                "language": "python3",
                "source_code": "def two_sum(nums, target):\n    seen = {}\n    for i, num in enumerate(nums):\n        complement = target - num\n        if complement in seen:\n            return [seen[complement], i]\n        seen[num] = i\n    return []"
            }
        }
```

---

## 4. Output Contracts

### SubmitCodeResponse

```python
class SubmitCodeResponse(BaseModel):
    submission_id: int
    execution_status: Literal["pending", "running"]
    message: str = "Code submitted successfully. Execution in progress."

    class Config:
        json_schema_extra = {
            "example": {
                "submission_id": 789,
                "execution_status": "pending",
                "message": "Code submitted successfully. Execution in progress."
            }
        }
```

### ExecutionStatusResponse

```python
from typing import List, Optional
from datetime import datetime

class TestCaseResultDTO(BaseModel):
    test_case_id: int
    test_case_name: str
    passed: bool
    visible: bool  # If false, hide expected_output
    actual_output: Optional[str] = None  # Only if visible
    expected_output: Optional[str] = None  # Only if visible
    runtime_ms: int
    memory_kb: int
    feedback: str  # "Passed", "Wrong Answer", "Time Limit Exceeded", etc.

class ExecutionStatusResponse(BaseModel):
    submission_id: int
    interview_exchange_id: int
    coding_problem_id: int
    language: str
    execution_status: Literal["pending", "running", "passed", "failed", "error", "timeout", "memory_exceeded"]
    score: float  # 0-100
    execution_time_ms: Optional[int] = None  # Total execution time across all tests
    memory_kb: Optional[int] = None  # Peak memory usage
    compiler_output: Optional[str] = None  # Only if compilation failed
    test_results: List[TestCaseResultDTO]
    submitted_at: datetime
    executed_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "submission_id": 789,
                "interview_exchange_id": 123,
                "coding_problem_id": 45,
                "language": "python3",
                "execution_status": "passed",
                "score": 100.0,
                "execution_time_ms": 145,
                "memory_kb": 12000,
                "compiler_output": None,
                "test_results": [
                    {
                        "test_case_id": 1,
                        "test_case_name": "Example 1",
                        "passed": True,
                        "visible": True,
                        "actual_output": "[0, 1]",
                        "expected_output": "[0, 1]",
                        "runtime_ms": 45,
                        "memory_kb": 12000,
                        "feedback": "Passed"
                    },
                    {
                        "test_case_id": 2,
                        "test_case_name": "Hidden Test 1",
                        "passed": True,
                        "visible": False,
                        "actual_output": None,
                        "expected_output": None,
                        "runtime_ms": 50,
                        "memory_kb": 11500,
                        "feedback": "Passed"
                    }
                ],
                "submitted_at": "2026-02-14T10:30:00Z",
                "executed_at": "2026-02-14T10:30:05Z"
            }
        }
```

### ErrorResponse

```python
class CodeSubmissionError(BaseModel):
    error: str  # Error code
    message: str  # Human-readable message
    details: Optional[dict] = None
    request_id: Optional[str] = None
```

---

## 5. Acceptance Criteria

### Endpoint 1: Submit Code

**Route:** `POST /api/coding/submit`

**Authentication:** Required (candidate or admin)

**Request Body:** `SubmitCodeRequest`

**Response:** `SubmitCodeResponse` (201 Created)

**Validation:**

1. Extract `auth_context` from request (injected by auth middleware)
2. Verify candidate owns the interview_exchange (query interview_exchanges table)
3. Verify coding_problem_id matches exchange's question_id
4. Verify no existing submission for this exchange (UNIQUE constraint)
5. Validate language is supported
6. Validate source_code size <= 50KB

**Business Logic:**

1. Create `code_submission` record with status=`pending`
2. Enqueue execution task asynchronously (Celery)
3. Return submission_id and status=`pending`

**Error Cases:**

- **401 Unauthorized:** Missing or invalid auth token
- **403 Forbidden:** Candidate doesn't own interview_exchange
- **404 Not Found:** interview_exchange_id or coding_problem_id not found
- **409 Conflict:** Submission already exists for this exchange
- **422 Unprocessable Entity:** Invalid request data (validation errors)
- **429 Too Many Requests:** Rate limit exceeded (5 submissions per minute)

**Example:**

```bash
curl -X POST https://api.example.com/api/coding/submit \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "interview_exchange_id": 123,
    "coding_problem_id": 45,
    "language": "python3",
    "source_code": "def solution(nums):\n    return sum(nums)"
  }'

# Response 201 Created
{
  "submission_id": 789,
  "execution_status": "pending",
  "message": "Code submitted successfully. Execution in progress."
}
```

---

### Endpoint 2: Get Execution Status

**Route:** `GET /api/coding/submissions/{submission_id}`

**Authentication:** Required (candidate or admin)

**Path Parameter:** `submission_id` (integer)

**Response:** `ExecutionStatusResponse` (200 OK)

**Validation:**

1. Extract `auth_context` from request
2. Fetch `code_submission` by submission_id
3. Verify candidate owns the submission (via interview_exchange)
4. Fetch `code_execution_results` for this submission

**Data Filtering (Hidden Test Cases):**

- For each test case result:
  - If `test_case.visible = False`:
    - Set `actual_output = None`
    - Set `expected_output = None`
    - Set `feedback = "Passed"` or `"Failed"` (no detailed diff)
  - If `test_case.visible = True`:
    - Include full details (actual_output, expected_output, feedback)

**Error Cases:**

- **401 Unauthorized:** Missing or invalid auth token
- **403 Forbidden:** Candidate doesn't own submission
- **404 Not Found:** submission_id not found

**Example:**

```bash
curl -X GET https://api.example.com/api/coding/submissions/789 \
  -H "Authorization: Bearer <token>"

# Response 200 OK
{
  "submission_id": 789,
  "interview_exchange_id": 123,
  "coding_problem_id": 45,
  "language": "python3",
  "execution_status": "passed",
  "score": 100.0,
  "execution_time_ms": 145,
  "memory_kb": 12000,
  "compiler_output": null,
  "test_results": [
    {
      "test_case_id": 1,
      "test_case_name": "Example 1",
      "passed": true,
      "visible": true,
      "actual_output": "[0, 1]",
      "expected_output": "[0, 1]",
      "runtime_ms": 45,
      "memory_kb": 12000,
      "feedback": "Passed"
    },
    {
      "test_case_id": 2,
      "test_case_name": "Hidden Test 1",
      "passed": true,
      "visible": false,
      "actual_output": null,
      "expected_output": null,
      "runtime_ms": 50,
      "memory_kb": 11500,
      "feedback": "Passed"
    }
  ],
  "submitted_at": "2026-02-14T10:30:00Z",
  "executed_at": "2026-02-14T10:30:05Z"
}
```

---

### Endpoint 3: List Submissions for Interview

**Route:** `GET /api/coding/interviews/{interview_id}/submissions`

**Authentication:** Required (candidate or admin)

**Path Parameter:** `interview_id` (integer)

**Response:** `List[SubmissionSummary]` (200 OK)

**Purpose:** Allow candidate (or admin) to see all code submissions for an interview.

**Validation:**

1. Verify candidate owns interview (or admin has permission)
2. Fetch all code_submissions for interview_exchanges belonging to this interview
3. Return summary (no full source code or detailed results)

**Response Schema:**

```python
class SubmissionSummary(BaseModel):
    submission_id: int
    interview_exchange_id: int
    coding_problem_id: int
    language: str
    execution_status: str
    score: float
    submitted_at: datetime
```

---

## 6. Invariants & Constraints

### Must Hold

1. **One Submission Per Exchange:** UNIQUE constraint enforced, API returns 409 on duplicate
2. **Hidden Test Case Protection:** Hidden test expected_output NEVER in API response
3. **Candidate Ownership:** Candidate can only submit/view their own code
4. **Admin Visibility:** Admins can view all submissions in their organization
5. **Rate Limiting:** Max 5 submissions per minute per candidate

### Forbidden

- MUST NOT expose hidden test case expected_output in API responses
- MUST NOT allow candidate to submit code for another candidate's interview
- MUST NOT allow duplicate submissions for same exchange
- MUST NOT return full source code in list endpoints (privacy, size)
- MUST NOT execute code synchronously in API request (timeout risk)

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Frontend UI:** Interview portal, coding editor

2. **Interview Orchestrator:** Submits code on candidate's behalf

### Downstream (Dependencies)

1. **Coding Execution Module:** Enqueues execution tasks

2. **Coding Persistence Module:** Reads/writes code_submissions

3. **Interview Module:** Validates interview_exchange ownership

4. **Auth Module:** Validates candidate identity

---

## 8. Security Requirements

### Rate Limiting

- **Per Candidate:** 5 submissions per minute
- **Storage:** Redis with sliding window
- **Response:** 429 Too Many Requests with `Retry-After` header

### Input Validation

- **Source Code Size:** Max 50KB (prevent abuse)
- **Language Whitelist:** Only cpp, java, python3
- **Exchange Ownership:** Verify candidate owns exchange before submission

### Output Sanitization

- **Hidden Test Cases:** Never expose expected_output
- **Error Messages:** Don't leak internal paths or stack traces
- **Compiler Output:** Sanitize paths (e.g., `/tmp/sandbox/code.cpp` → `code.cpp`)

---

## 9. Edge Cases to Handle

### 1. Duplicate Submission (429 Conflict)

**Scenario:** Candidate submits code twice for same exchange (double-click, network retry).

**Handling:**

- First submission creates row, returns 201
- Second submission hits UNIQUE constraint, returns 409 Conflict
- Response includes existing submission_id

**Response:**

```json
{
  "error": "DUPLICATE_SUBMISSION",
  "message": "Code already submitted for this exchange",
  "details": {
    "existing_submission_id": 789
  }
}
```

---

### 2. Mismatched Coding Problem

**Scenario:** Candidate submits code with coding_problem_id that doesn't match exchange's question.

**Handling:**

- Query interview_exchanges to get question_id
- If question_id != coding_problem_id, return 400 Bad Request
- Response: "Coding problem does not match exchange question"

---

### 3. Hidden Test Case Leak via Error Messages

**Scenario:** Compiler error message reveals hidden test case input (e.g., "Variable 'x' undefined when x=42").

**Handling:**

- Sanitize compiler_output to remove test case input data
- Only show generic compilation errors
- If impossible to sanitize, omit compiler_output for hidden tests

---

### 4. Execution Still Running

**Scenario:** Candidate polls `/api/coding/submissions/{id}` while execution in progress.

**Handling:**

- Return status=`running`
- test_results list is empty
- score = 0
- Client should poll periodically (e.g., every 2 seconds)

---

### 5. Long-Running Execution

**Scenario:** Execution takes >30 seconds (e.g., many test cases, slow code).

**Handling:**

- API returns immediately with status=`pending`
- Execution happens asynchronously in background worker
- Candidate polls for status updates
- If execution exceeds worker timeout (60s), marked as `error`

---

### 6. Candidate Unauthorized to View Submission

**Scenario:** Candidate A tries to view Candidate B's submission.

**Handling:**

- Fetch submission, check interview_exchange ownership
- If exchange belongs to different candidate, return 403 Forbidden
- Response: "You do not have permission to view this submission"

---

## 10. Example API Usage

### Submit Code (Python)

```python
import requests

response = requests.post(
    "https://api.example.com/api/coding/submit",
    headers={"Authorization": "Bearer <token>"},
    json={
        "interview_exchange_id": 123,
        "coding_problem_id": 45,
        "language": "python3",
        "source_code": "def solution(nums):\n    return sum(nums)"
    }
)

if response.status_code == 201:
    submission = response.json()
    submission_id = submission["submission_id"]
    print(f"Submitted! Submission ID: {submission_id}")
elif response.status_code == 409:
    error = response.json()
    print(f"Duplicate submission: {error['details']['existing_submission_id']}")
```

### Poll for Execution Status

```python
import time

submission_id = 789
while True:
    response = requests.get(
        f"https://api.example.com/api/coding/submissions/{submission_id}",
        headers={"Authorization": "Bearer <token>"}
    )

    if response.status_code == 200:
        result = response.json()
        status = result["execution_status"]

        if status in ["passed", "failed", "error", "timeout", "memory_exceeded"]:
            print(f"Execution complete! Status: {status}, Score: {result['score']}")
            break
        else:
            print(f"Status: {status}. Waiting...")
            time.sleep(2)
```

---

## 11. Configuration

### Environment Variables

```bash
# API
MAX_SOURCE_CODE_SIZE_BYTES=51200  # 50KB

# Rate Limiting
MAX_SUBMISSIONS_PER_MINUTE=5
RATE_LIMIT_STORAGE=redis://localhost:6379/3
```

---

## 12. Future Enhancements

1. **WebSocket Status Updates:**
   - Real-time execution status via WebSocket
   - No need for polling

2. **Submission History:**
   - Allow multiple submissions per exchange (practice mode)
   - Track submission history

3. **Code Diff:**
   - Compare submissions
   - Show what changed

4. **Submission Templates:**
   - Pre-populate editor with function signature

5. **Syntax Highlighting:**
   - Return syntax-highlighted code in response

---

**End of Coding API Layer Requirements**
