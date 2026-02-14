# Evaluation API - Evaluation Triggers & Review Overrides

## 1. Purpose

The **Evaluation API** layer exposes HTTP endpoints for:

- Triggering exchange evaluation (automatic or manual)
- Re-evaluating an exchange (creating new version)
- Applying human override to existing evaluation
- Finalizing interview results (aggregation)
- Fetching evaluation details and history

**Critical responsibility:** This is the **public interface** to the evaluation engine. It must:

- Enforce authorization (only admins can override, only owners can view)
- Validate evaluation requests before triggering scoring
- Prevent duplicate evaluations (idempotency)
- Support versioning (re-evaluation flow)
- Expose audit trail

---

## 2. Required Endpoints

### 1️⃣ POST /api/evaluation/evaluate

**Purpose:** Trigger evaluation for a specific exchange.

#### Request

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class EvaluateExchangeRequest(BaseModel):
    interview_exchange_id: int = Field(gt=0, description="Exchange to evaluate")
    evaluator_type: Literal["ai", "human", "hybrid"] = Field(default="ai")
    force_reevaluate: bool = Field(default=False, description="Allow re-evaluation (creates new version)")
    human_evaluator_id: Optional[int] = Field(None, description="Required if evaluator_type=human")

    class Config:
        json_schema_extra = {
            "example": {
                "interview_exchange_id": 123,
                "evaluator_type": "ai",
                "force_reevaluate": False
            }
        }
```

#### Response

**201 Created** (New evaluation created)

```json
{
  "evaluation_id": 456,
  "interview_exchange_id": 123,
  "rubric_id": 789,
  "evaluator_type": "ai",
  "total_score": 85.5,
  "dimension_scores": [
    {
      "rubric_dimension_id": 1,
      "dimension_name": "Accuracy",
      "score": 4.5,
      "max_score": 5.0,
      "weight": 40,
      "justification": "Answer demonstrates strong understanding..."
    }
  ],
  "explanation": "Overall, the candidate showed...",
  "is_final": true,
  "evaluated_at": "2026-02-14T10:30:00Z",
  "model_id": "gpt-4-turbo"
}
```

**200 OK** (Existing evaluation returned - idempotent)

Same structure as 201, but evaluation already existed.

#### Error Responses

**400 Bad Request**

```json
{
  "error_code": "INVALID_REQUEST",
  "message": "evaluator_type=human requires human_evaluator_id"
}
```

**403 Forbidden**

```json
{
  "error_code": "UNAUTHORIZED_EVALUATION",
  "message": "Only admins can trigger manual evaluation"
}
```

**404 Not Found**

```json
{
  "error_code": "EXCHANGE_NOT_FOUND",
  "message": "Interview exchange 123 does not exist"
}
```

**409 Conflict**

```json
{
  "error_code": "ALREADY_EVALUATED",
  "message": "Exchange 123 already has final evaluation. Use force_reevaluate=true to create new version.",
  "existing_evaluation_id": 456
}
```

**422 Unprocessable Entity**

```json
{
  "error_code": "INVALID_RUBRIC",
  "message": "Rubric for this exchange has 0 dimensions"
}
```

**500 Internal Server Error**

```json
{
  "error_code": "EVALUATION_FAILED",
  "message": "AI evaluation timeout after 3 retries"
}
```

#### Business Rules

**Must validate:**

1. Exchange exists
2. Exchange is answered (submission_id is not null)
3. If `evaluator_type = "human"`, `human_evaluator_id` must be provided
4. If exchange already evaluated and `force_reevaluate = false`, return 409
5. Requester is admin (for manual evaluation)

**Must execute:**

1. Check existing evaluation with `is_final = true`
2. If exists and `force_reevaluate = false`, return existing (idempotent)
3. If exists and `force_reevaluate = true`:
   - Mark old evaluation `is_final = false`
   - Create new evaluation with `is_final = true`
4. If not exists, create new evaluation
5. Trigger scoring pipeline
6. Persist evaluation and dimension scores
7. Emit `ExchangeEvaluated` event

---

### 2️⃣ POST /api/evaluation/override

**Purpose:** Human admin overrides selected dimension scores.

#### Request

```python
from typing import List

class DimensionScoreOverride(BaseModel):
    rubric_dimension_id: int = Field(gt=0)
    new_score: float = Field(ge=0, description="New score value")
    justification: str = Field(min_length=10, max_length=5000, description="Required justification")

class HumanOverrideRequest(BaseModel):
    evaluation_id: int = Field(gt=0, description="Evaluation to override")
    overrides: List[DimensionScoreOverride] = Field(min_length=1, description="At least one dimension override")
    admin_id: int = Field(gt=0)
    override_reason: str = Field(min_length=10, max_length=1000, description="Overall reason for override")

    class Config:
        json_schema_extra = {
            "example": {
                "evaluation_id": 456,
                "overrides": [
                    {
                        "rubric_dimension_id": 1,
                        "new_score": 5.0,
                        "justification": "Upon closer review, answer is fully correct"
                    }
                ],
                "admin_id": 5,
                "override_reason": "AI missed subtle correctness in candidate response"
            }
        }
```

#### Response

**201 Created** (New evaluation version created)

```json
{
  "evaluation_id": 457,
  "previous_evaluation_id": 456,
  "interview_exchange_id": 123,
  "rubric_id": 789,
  "evaluator_type": "hybrid",
  "total_score": 90.0,
  "dimension_scores": [
    {
      "rubric_dimension_id": 1,
      "dimension_name": "Accuracy",
      "score": 5.0,
      "max_score": 5.0,
      "weight": 40,
      "justification": "Upon closer review, answer is fully correct"
    }
  ],
  "explanation": "Admin override applied: AI missed subtle correctness in candidate response",
  "is_final": true,
  "evaluated_at": "2026-02-14T10:45:00Z",
  "evaluated_by": 5
}
```

#### Error Responses

**403 Forbidden**

```json
{
  "error_code": "ADMIN_ONLY",
  "message": "Only admins can override evaluations"
}
```

**404 Not Found**

```json
{
  "error_code": "EVALUATION_NOT_FOUND",
  "message": "Evaluation 456 does not exist"
}
```

**422 Unprocessable Entity**

```json
{
  "error_code": "INVALID_OVERRIDE",
  "message": "Score 6.0 exceeds max_score 5.0 for dimension Accuracy"
}
```

#### Business Rules

**Must validate:**

1. Evaluation exists
2. Requester is admin
3. All overridden dimensions exist in evaluation's rubric
4. new_score <= max_score for each dimension
5. Justification provided for each override

**Must execute:**

1. Fetch original evaluation
2. Mark original `is_final = false`
3. Copy all dimension scores
4. Apply overrides to specified dimensions
5. Recalculate total_score = Σ (dimension_score × weight)
6. Create new evaluation with:
   - `evaluator_type = "hybrid"`
   - `is_final = true`
   - `evaluated_by = admin_id`
   - `explanation = override_reason`
7. Emit `EvaluationOverridden` event

---

### 3️⃣ POST /api/evaluation/finalize

**Purpose:** Finalize interview result (aggregate all exchange evaluations).

#### Request

```python
class FinalizeInterviewRequest(BaseModel):
    interview_id: int = Field(gt=0)
    generated_by: Literal["ai", "human", "hybrid"] = Field(default="ai")
    admin_override: Optional[str] = Field(None, max_length=2000, description="Optional admin justification")

    class Config:
        json_schema_extra = {
            "example": {
                "interview_id": 100,
                "generated_by": "ai"
            }
        }
```

#### Response

**201 Created**

```json
{
  "result_id": 789,
  "interview_id": 100,
  "final_score": 820.5,
  "normalized_score": 82.05,
  "result_status": "completed",
  "recommendation": "hire",
  "section_scores": [
    {
      "section_name": "resume",
      "score": 85.0,
      "weight": 10,
      "exchanges_evaluated": 2
    },
    {
      "section_name": "behavioral",
      "score": 78.0,
      "weight": 30,
      "exchanges_evaluated": 3
    },
    {
      "section_name": "coding",
      "score": 85.0,
      "weight": 60,
      "exchanges_evaluated": 3
    }
  ],
  "strengths": [
    "Strong data structures knowledge",
    "Clear communication",
    "Good problem-solving approach"
  ],
  "weaknesses": [
    "Hesitant on system design",
    "Could improve time complexity analysis"
  ],
  "summary_notes": "Overall strong candidate with solid fundamentals...",
  "generated_by": "ai",
  "model_id": "gpt-4-turbo",
  "is_current": true,
  "created_at": "2026-02-14T11:00:00Z"
}
```

#### Error Responses

**403 Forbidden**

```json
{
  "error_code": "UNAUTHORIZED_FINALIZATION",
  "message": "Only admins can finalize interview results"
}
```

**404 Not Found**

```json
{
  "error_code": "INTERVIEW_NOT_FOUND",
  "message": "Interview 100 does not exist"
}
```

**422 Unprocessable Entity**

```json
{
  "error_code": "INCOMPLETE_EVALUATION",
  "message": "Cannot finalize: 3 out of 10 exchanges not yet evaluated",
  "pending_exchange_ids": [45, 46, 47]
}
```

**409 Conflict**

```json
{
  "error_code": "ALREADY_FINALIZED",
  "message": "Interview 100 already has current result. Use force=true to create new version.",
  "existing_result_id": 789
}
```

#### Business Rules

**Must validate:**

1. Interview exists
2. Interview status = "completed" or "in_progress"
3. All exchanges have evaluation with `is_final = true`
4. Requester is admin

**Must execute:**

1. Fetch all exchanges for interview
2. Verify all evaluated (COUNT matches)
3. Fetch all evaluations with `is_final = true`
4. Aggregate section scores (by template section weights)
5. Calculate normalized_score = (final_score / max_possible) × 100
6. Determine recommendation based on thresholds:
   - normalized_score >= 85 → "strong_hire"
   - normalized_score >= 70 → "hire"
   - normalized_score >= 50 → "review"
   - normalized_score < 50 → "no_hire"
7. Check proctoring risk (if enabled)
8. Generate strengths/weaknesses (AI-powered)
9. Create snapshots (rubric, template weights)
10. Mark old result `is_current = false` (if exists)
11. Create new result with `is_current = true`
12. Emit `InterviewResultFinalized` event

---

### 4️⃣ GET /api/evaluation/evaluations/{evaluation_id}

**Purpose:** Fetch single evaluation details.

#### Response

**200 OK**

```json
{
  "evaluation_id": 456,
  "interview_exchange_id": 123,
  "rubric_id": 789,
  "evaluator_type": "ai",
  "total_score": 85.5,
  "dimension_scores": [
    {
      "rubric_dimension_id": 1,
      "dimension_name": "Accuracy",
      "score": 4.5,
      "max_score": 5.0,
      "weight": 40,
      "justification": "Answer demonstrates strong understanding..."
    }
  ],
  "explanation": "Overall, the candidate showed...",
  "is_final": true,
  "evaluated_at": "2026-02-14T10:30:00Z",
  "evaluated_by": null,
  "model_id": "gpt-4-turbo",
  "scoring_version": "1.0"
}
```

#### Error Responses

**403 Forbidden**

```json
{
  "error_code": "UNAUTHORIZED_ACCESS",
  "message": "Cannot view evaluations for other candidates' interviews"
}
```

**404 Not Found**

```json
{
  "error_code": "EVALUATION_NOT_FOUND",
  "message": "Evaluation 456 does not exist"
}
```

#### Business Rules

**Must validate:**

- Requester is admin OR evaluation is for requester's interview

---

### 5️⃣ GET /api/evaluation/exchanges/{exchange_id}/evaluations

**Purpose:** Fetch all evaluations for an exchange (including historical versions).

#### Query Parameters

- `include_history` (bool, default=false): Include non-final evaluations

#### Response

**200 OK**

```json
{
  "exchange_id": 123,
  "evaluations": [
    {
      "evaluation_id": 457,
      "evaluator_type": "hybrid",
      "total_score": 90.0,
      "is_final": true,
      "evaluated_at": "2026-02-14T10:45:00Z",
      "evaluated_by": 5
    },
    {
      "evaluation_id": 456,
      "evaluator_type": "ai",
      "total_score": 85.5,
      "is_final": false,
      "evaluated_at": "2026-02-14T10:30:00Z",
      "evaluated_by": null
    }
  ],
  "current_evaluation_id": 457
}
```

---

### 6️⃣ GET /api/evaluation/results/{interview_id}

**Purpose:** Fetch interview result (final aggregated score).

#### Query Parameters

- `include_history` (bool, default=false): Include non-current results

#### Response

**200 OK**

```json
{
  "interview_id": 100,
  "results": [
    {
      "result_id": 789,
      "final_score": 820.5,
      "normalized_score": 82.05,
      "result_status": "completed",
      "recommendation": "hire",
      "section_scores": [...],
      "strengths": [...],
      "weaknesses": [...],
      "is_current": true,
      "created_at": "2026-02-14T11:00:00Z"
    }
  ],
  "current_result_id": 789
}
```

#### Error Responses

**403 Forbidden**

```json
{
  "error_code": "UNAUTHORIZED_ACCESS",
  "message": "Cannot view results for other candidates' interviews"
}
```

**404 Not Found**

```json
{
  "error_code": "RESULT_NOT_FOUND",
  "message": "No result found for interview 100"
}
```

---

### 7️⃣ GET /api/evaluation/results/{result_id}/report

**Purpose:** Fetch detailed supplementary reports (technical breakdown, behavioral analysis, proctoring risk).

#### Response

**200 OK**

```json
{
  "result_id": 789,
  "interview_id": 100,
  "reports": [
    {
      "report_id": 1001,
      "report_type": "technical_breakdown",
      "report_data": {
        "coding_score": 85.0,
        "problem_solving_score": 82.0,
        "algorithm_complexity": "Strong",
        "code_quality": "Good",
        "debugging_skills": "Excellent"
      },
      "created_at": "2026-02-14T11:05:00Z"
    },
    {
      "report_id": 1002,
      "report_type": "proctoring_risk",
      "report_data": {
        "overall_risk": "low",
        "suspicious_events": 0,
        "flagged_behaviors": []
      },
      "created_at": "2026-02-14T11:05:00Z"
    }
  ]
}
```

---

## 3. Authorization Matrix

| Endpoint                        | Candidate | Admin | Notes                                 |
| ------------------------------- | --------- | ----- | ------------------------------------- |
| POST /evaluate                  | ❌        | ✅    | Only admins trigger manual evaluation |
| POST /override                  | ❌        | ✅    | Admin-only                            |
| POST /finalize                  | ❌        | ✅    | Admin-only                            |
| GET /evaluations/{id}           | ✅ (own)  | ✅    | Candidates see own evaluations        |
| GET /exchanges/{id}/evaluations | ✅ (own)  | ✅    | Candidates see own history            |
| GET /results/{interview_id}     | ✅ (own)  | ✅    | Candidates see own results            |
| GET /results/{result_id}/report | ✅ (own)  | ✅    | Candidates see own reports            |

---

## 4. Rate Limiting

**POST /evaluate:**

- Admin: 100 requests per minute
- Automated triggers: Unlimited (internal service)

**POST /override:**

- Admin: 50 requests per minute

**POST /finalize:**

- Admin: 20 requests per minute

**GET endpoints:**

- 200 requests per minute per user

---

## 5. Idempotency

### Evaluate Endpoint

**Idempotency key:** `interview_exchange_id`

**Behavior:**

- If evaluation with `is_final = true` exists, return existing (200 OK)
- If `force_reevaluate = true`, create new version (201 Created)

### Override Endpoint

**Idempotency key:** None (always creates new version)

### Finalize Endpoint

**Idempotency key:** `interview_id`

**Behavior:**

- If result with `is_current = true` exists and same data, return existing (200 OK)
- If different data, create new version (201 Created)

---

## 6. Event Publishing

### ExchangeEvaluated

```python
{
    "event_type": "exchange_evaluated",
    "evaluation_id": 456,
    "interview_exchange_id": 123,
    "interview_id": 100,
    "total_score": 85.5,
    "evaluator_type": "ai",
    "is_final": true,
    "timestamp": "2026-02-14T10:30:00Z"
}
```

**Subscribers:**

- Interview service (update interview progress)
- Notification service (notify candidate if all evaluated)

### EvaluationOverridden

```python
{
    "event_type": "evaluation_overridden",
    "old_evaluation_id": 456,
    "new_evaluation_id": 457,
    "interview_exchange_id": 123,
    "override_reason": "AI missed subtle correctness",
    "admin_id": 5,
    "timestamp": "2026-02-14T10:45:00Z"
}
```

### InterviewResultFinalized

```python
{
    "event_type": "interview_result_finalized",
    "result_id": 789,
    "interview_id": 100,
    "normalized_score": 82.05,
    "recommendation": "hire",
    "result_status": "completed",
    "timestamp": "2026-02-14T11:00:00Z"
}
```

---

## 7. Error Handling

**Must handle:**

1. Exchange not found → 404
2. Exchange not answered → 422 "Exchange has no submission"
3. Rubric has 0 dimensions → 422 "Invalid rubric"
4. Already evaluated (no force flag) → 409
5. Incomplete evaluations during finalization → 422
6. AI timeout → 500 with retry logic
7. Invalid override (score > max) → 422
8. Unauthorized access → 403
9. Concurrent override → Handle with row locking

**Retry logic for AI evaluation:**

- Max 3 retries
- Exponential backoff: 1s, 2s, 4s
- If all fail, mark evaluation_status = "error"

---

## 8. Testing Requirements

### Unit Tests

1. Request validation (Pydantic schemas)
2. Authorization checks (admin-only endpoints)
3. Idempotency logic (duplicate evaluation)
4. Error responses (404, 409, 422)

### Integration Tests

1. End-to-end evaluation flow
2. Re-evaluation creates new version
3. Override marks old as non-final
4. Finalization aggregates correctly
5. Event publishing

### Edge Case Tests

1. Evaluate already-evaluated exchange (idempotent)
2. Override during concurrent evaluation
3. Finalize with pending exchanges (422 error)
4. AI timeout triggers retry
5. Invalid score in override (422 error)

---

## 9. Critical Risks

1. **No authorization check:** Candidate overrides evaluation
2. **No idempotency:** Duplicate evaluation created
3. **No validation:** Finalize with incomplete evaluations
4. **No versioning:** Override overwrites old evaluation
5. **No event publishing:** Downstream services not notified
6. **No rate limiting:** API abuse
7. **No retry logic:** AI timeout fails permanently

---

**End of Evaluation API Requirements**
