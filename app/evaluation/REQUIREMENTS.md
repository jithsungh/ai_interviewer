# Evaluation Module - Exchange-Level Scoring & Final Result Computation

## 1. Purpose

**Why this module exists:**

The Evaluation module is a **deterministic scoring engine with audit guarantees**. It:

- Evaluates each interview exchange against rubric dimensions
- Produces structured dimension-level scores
- Aggregates exchange scores into final interview results
- Freezes rubric & template context at evaluation time (audit safety)
- Supports AI, human, and hybrid evaluation
- Maintains versioned results with immutable history

**Critical responsibility:** This is **one of the most critical modules** in the entire system. If this module is wrong:

- "One exchange = one evaluation" invariant breaks
- Template immutability guarantee becomes meaningless
- Audit trail collapses
- Scoring becomes non-reproducible
- Human override becomes unsafe

**Architectural philosophy:**

> **One exchange → one evaluation (UNIQUE constraint)**
> **Exchange immutability preserved**
> **Rubric-based scoring enforced**
> **Snapshot-based aggregation for reproducibility**
> **Versioned final results for audit trail**

---

## 2. Owned Tables / Entities

### evaluations

```sql
CREATE TABLE evaluations (
    id SERIAL PRIMARY KEY,
    interview_exchange_id INTEGER NOT NULL REFERENCES interview_exchanges(id) ON DELETE CASCADE,
    rubric_id INTEGER REFERENCES rubrics(id),
    evaluator_type VARCHAR(20) NOT NULL CHECK (evaluator_type IN ('ai', 'human', 'hybrid')),
    total_score NUMERIC(5, 2) NOT NULL,
    explanation TEXT,
    is_final BOOLEAN DEFAULT true,
    evaluated_at TIMESTAMP DEFAULT NOW(),
    evaluated_by INTEGER REFERENCES users(id),  -- Human evaluator if applicable
    model_id VARCHAR(100),  -- AI model used (e.g., gpt-4-turbo)
    scoring_version VARCHAR(20),  -- Scoring algorithm version
    UNIQUE(interview_exchange_id, is_final) WHERE is_final = true
);

CREATE INDEX idx_evaluations_exchange ON evaluations(interview_exchange_id);
CREATE INDEX idx_evaluations_rubric ON evaluations(rubric_id);
```

**Note:** UNIQUE constraint ensures only one final evaluation per exchange.

### evaluation_dimension_scores

```sql
CREATE TABLE evaluation_dimension_scores (
    id SERIAL PRIMARY KEY,
    evaluation_id INTEGER NOT NULL REFERENCES evaluations(id) ON DELETE CASCADE,
    rubric_dimension_id INTEGER NOT NULL REFERENCES rubric_dimensions(id),
    score NUMERIC(4, 2) NOT NULL,
    max_score NUMERIC(4, 2) NOT NULL,
    justification TEXT,
    UNIQUE(evaluation_id, rubric_dimension_id)
);

CREATE INDEX idx_dimension_scores_evaluation ON evaluation_dimension_scores(evaluation_id);
```

### interview_results

```sql
CREATE TABLE interview_results (
    id SERIAL PRIMARY KEY,
    interview_id INTEGER NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    final_score NUMERIC(6, 2) NOT NULL,
    normalized_score NUMERIC(5, 2) NOT NULL,  -- 0-100
    result_status VARCHAR(20) NOT NULL CHECK (result_status IN ('pending', 'completed', 'flagged', 'invalidated')),
    recommendation VARCHAR(20) NOT NULL CHECK (recommendation IN ('strong_hire', 'hire', 'review', 'no_hire')),

    -- Audit snapshots (JSONB)
    rubric_snapshot JSONB NOT NULL,
    template_weight_snapshot JSONB NOT NULL,
    section_scores JSONB NOT NULL,

    -- Generated content
    strengths TEXT[],
    weaknesses TEXT[],
    summary_notes TEXT,

    -- Metadata
    generated_by VARCHAR(20) NOT NULL CHECK (generated_by IN ('ai', 'human', 'hybrid')),
    model_id VARCHAR(100),
    is_current BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(interview_id, is_current) WHERE is_current = true
);

CREATE INDEX idx_interview_results_interview ON interview_results(interview_id);
CREATE INDEX idx_interview_results_current ON interview_results(interview_id, is_current);
```

### supplementary_reports

```sql
CREATE TABLE supplementary_reports (
    id SERIAL PRIMARY KEY,
    interview_result_id INTEGER NOT NULL REFERENCES interview_results(id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL CHECK (report_type IN ('technical_breakdown', 'behavioral_analysis', 'proctoring_risk', 'custom')),
    report_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_supplementary_reports_result ON supplementary_reports(interview_result_id);
```

---

## 3. Input Contracts

### EvaluateExchangeRequest

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional

class EvaluateExchangeRequest(BaseModel):
    interview_exchange_id: int = Field(gt=0)
    evaluator_type: Literal["ai", "human", "hybrid"] = "ai"
    force_reevaluate: bool = False  # Allow re-evaluation (creates new version)
    human_evaluator_id: Optional[int] = None  # Required if evaluator_type=human
```

### HumanOverrideRequest

```python
class DimensionScoreOverride(BaseModel):
    rubric_dimension_id: int
    new_score: float = Field(ge=0)
    justification: str = Field(min_length=10, max_length=5000)

class HumanOverrideRequest(BaseModel):
    evaluation_id: int
    overrides: List[DimensionScoreOverride]
    admin_id: int
    override_reason: str = Field(min_length=10, max_length=1000)
```

### FinalizeInterviewRequest

```python
class FinalizeInterviewRequest(BaseModel):
    interview_id: int = Field(gt=0)
    generated_by: Literal["ai", "human", "hybrid"] = "ai"
    admin_override: Optional[str] = None  # Optional human justification
```

---

## 4. Output Contracts

### EvaluationResponse

```python
from typing import List
from datetime import datetime

class DimensionScoreDTO(BaseModel):
    rubric_dimension_id: int
    dimension_name: str
    score: float
    max_score: float
    weight: int
    justification: str

class EvaluationResponse(BaseModel):
    evaluation_id: int
    interview_exchange_id: int
    rubric_id: int
    evaluator_type: str
    total_score: float
    dimension_scores: List[DimensionScoreDTO]
    explanation: Optional[str]
    is_final: bool
    evaluated_at: datetime
    model_id: Optional[str]
```

### InterviewResultResponse

```python
class SectionScoreDTO(BaseModel):
    section_name: str
    score: float
    weight: int
    exchanges_evaluated: int

class InterviewResultResponse(BaseModel):
    result_id: int
    interview_id: int
    final_score: float
    normalized_score: float  # 0-100
    result_status: str
    recommendation: str
    section_scores: List[SectionScoreDTO]
    strengths: List[str]
    weaknesses: List[str]
    summary_notes: str
    generated_by: str
    model_id: Optional[str]
    is_current: bool
    created_at: datetime
```

---

## 5. Acceptance Criteria

### Module-Level Requirements

#### 1. One Exchange = One Evaluation (UNIQUE Constraint)

**Must enforce:**

- Database UNIQUE constraint on `(interview_exchange_id, is_final) WHERE is_final = true`
- Application-level pre-check before evaluation
- Idempotent evaluation requests (return existing if already evaluated)

**Re-evaluation flow:**

1. Mark existing evaluation `is_final = false`
2. Create new evaluation with `is_final = true`
3. Preserve old evaluation for audit trail

---

#### 2. Exchange Immutability Preserved

**Must NOT:**

- Modify `interview_exchanges` table
- Modify `submissions` table
- Change question or answer content

**Must ONLY:**

- Read exchange data
- Read submission data
- Create evaluation records

---

#### 3. Rubric-Based Scoring Enforced

**Must:**

- Resolve rubric via `interview_template_rubrics` (linked at interview creation)
- Fetch all dimensions from `rubric_dimensions`
- Score EVERY dimension (no partial scoring)
- Validate score <= max_score for each dimension
- Calculate total_score = Σ (dimension_score × dimension_weight)

**Edge case:**

- If rubric has 0 dimensions, reject evaluation (invalid rubric)

---

#### 4. Snapshot-Based Aggregation

**Must capture at evaluation time:**

- Rubric snapshot: rubric_id, dimension definitions, weights
- Template weight snapshot: section weights from template
- Model snapshot: model_id, scoring_version, evaluator_type

**Storage:**

- `interview_results.rubric_snapshot` (JSONB)
- `interview_results.template_weight_snapshot` (JSONB)

**Why:** Ensures reproducibility even if rubric or template changes later.

---

#### 5. Versioned Final Results

**Must support:**

- Multiple `interview_results` records per interview
- Only one marked `is_current = true` at a time
- Old results marked `is_current = false` (audit trail)

**Re-finalization flow:**

1. Mark existing result `is_current = false`
2. Create new result with `is_current = true`
3. Preserve old result for audit

---

#### 6. Support AI, Human, and Hybrid Evaluation

**AI Evaluation:**

- Send question + answer to LLM
- Receive structured dimension scores
- Validate schema and score ranges
- Store with `evaluator_type = 'ai'`

**Human Evaluation:**

- Admin manually scores each dimension
- Provide justification for each score
- Store with `evaluator_type = 'human'`, `evaluated_by = admin_id`

**Hybrid Evaluation:**

- AI scores first
- Human reviews and overrides selected dimensions
- Create new evaluation version with `evaluator_type = 'hybrid'`

---

## 6. Invariants & Constraints

### Must Hold

1. **One Final Evaluation Per Exchange:** UNIQUE constraint enforced
2. **Exchange Never Modified:** Evaluation is read-only on exchanges
3. **All Dimensions Scored:** If rubric has N dimensions, evaluation must have N dimension scores
4. **Score Within Bounds:** dimension_score >= 0 AND dimension_score <= max_score
5. **One Current Result Per Interview:** UNIQUE constraint on `(interview_id, is_current) WHERE is_current = true`
6. **Snapshot Immutability:** Snapshots never modified after creation
7. **Total Score Calculation:** total_score = Σ (dimension_score × dimension_weight)

### Forbidden

- MUST NOT modify `interview_exchanges` or `submissions`
- MUST NOT overwrite old evaluations (create new version instead)
- MUST NOT aggregate before all exchanges evaluated
- MUST NOT recalculate template at evaluation time (use snapshot)
- MUST NOT score partial dimensions (all or nothing)
- MUST NOT have multiple `is_current = true` results for same interview
- MUST NOT evaluate same exchange twice with `is_final = true` (unless re-evaluation flow)

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Interview Module:** Triggers evaluation after exchange completion
2. **Admin Module:** Triggers human override, finalizes results
3. **API Layer:** Exposes evaluation endpoints

### Downstream (Dependencies)

1. **Database (PostgreSQL):** Stores evaluations, dimension scores, results
2. **LLM Providers (via config):** AI evaluation
3. **Rubric Configuration:** Resolves rubric dimensions
4. **Template Configuration:** Resolves section weights
5. **Coding Module (indirect):** Reads `code_submissions.score` for coding exchanges
6. **Audio Module (indirect):** Reads `audio_analytics` for behavioral signals

---

## 8. Event Contracts Emitted

### ExchangeEvaluated

```python
{
    "event_type": "exchange_evaluated",
    "evaluation_id": 123,
    "interview_exchange_id": 456,
    "total_score": 85.5,
    "evaluator_type": "ai",
    "timestamp": "2026-02-14T10:30:00Z"
}
```

### InterviewResultFinalized

```python
{
    "event_type": "interview_result_finalized",
    "result_id": 789,
    "interview_id": 100,
    "normalized_score": 78.5,
    "recommendation": "hire",
    "timestamp": "2026-02-14T11:00:00Z"
}
```

### EvaluationOverridden

```python
{
    "event_type": "evaluation_overridden",
    "old_evaluation_id": 123,
    "new_evaluation_id": 124,
    "override_reason": "Manual review by admin",
    "admin_id": 5,
    "timestamp": "2026-02-14T10:45:00Z"
}
```

---

## 9. Edge Cases to Handle

### 1. Duplicate Evaluation Attempt

**Scenario:** API called twice to evaluate same exchange.

**Handling:**

- Check if evaluation with `is_final = true` exists
- If yes, return existing evaluation (idempotent)
- If `force_reevaluate = true`, mark old as `is_final = false`, create new

---

### 2. Rubric Changed After Interview Started

**Scenario:** Rubric updated mid-interview, exchanges already evaluated with old rubric.

**Handling:**

- Interview uses rubric snapshot from template at interview creation
- All exchanges evaluated with same rubric version
- Snapshot stored in `interview_results.rubric_snapshot`
- New interviews use updated rubric

---

### 3. Dimension Weight Mismatch

**Scenario:** Human override changes dimension score, but weight changed in rubric.

**Handling:**

- Override uses rubric snapshot (weights frozen at evaluation time)
- Recalculate total_score with original weights
- Store justification for override

---

### 4. Score Exceeding Max Score

**Scenario:** AI returns score > max_score for dimension.

**Handling:**

- Validation rejects score
- Return error: "Score 6.0 exceeds max_score 5.0 for dimension Accuracy"
- Evaluation fails, retry with corrected score

---

### 5. Re-Evaluation During Aggregation

**Scenario:** Admin re-evaluates exchange while interview result being finalized.

**Handling:**

- Use database transaction with row-level locking
- Finalization checks all evaluations `is_final = true`
- If evaluation changed mid-transaction, rollback and retry

---

### 6. Partial Exchange Evaluation

**Scenario:** Interview has 10 exchanges, only 7 evaluated.

**Handling:**

- Finalization checks: `COUNT(evaluations WHERE is_final=true) = COUNT(exchanges)`
- If mismatch, return error: "Cannot finalize: 3 exchanges not yet evaluated"
- Admin must evaluate pending exchanges first

---

### 7. AI Timeout During Evaluation

**Scenario:** LLM request times out, evaluation incomplete.

**Handling:**

- No evaluation record created (transaction rolled back)
- Retry mechanism (max 3 retries)
- If all retries fail, mark exchange as `evaluation_status = 'error'`
- Admin notified to manually evaluate

---

### 8. Concurrent Human Override

**Scenario:** Two admins override same evaluation simultaneously.

**Handling:**

- Use row-level locking: `SELECT ... FOR UPDATE` on evaluation
- First override succeeds, creates new version
- Second override works on latest version (not stale version)

---

### 9. Aggregation with Proctoring Flag

**Scenario:** High proctoring risk detected, should affect recommendation.

**Handling:**

- Aggregate score normally
- Check `proctoring_events.risk_level`
- If `risk_level = 'high'`, adjust recommendation:
  - `strong_hire` → `review`
  - `hire` → `review`
  - `review` → `no_hire` (if configured)
- Store proctoring influence in `supplementary_reports`

---

### 10. Floating Point Precision Inconsistency

**Scenario:** Score calculated as 85.500000001 vs 85.5.

**Handling:**

- Round all scores to 2 decimal places: `ROUND(score, 2)`
- Store as NUMERIC(5, 2) in database
- Avoid floating point arithmetic (use Decimal in Python)

---

## 10. Concurrency Concerns

### 1. Simultaneous Evaluation Triggers

**Scenario:** Webhook retries evaluation request, parallel API calls.

**Handling:**

- UNIQUE constraint on `(interview_exchange_id, is_final) WHERE is_final = true`
- Second INSERT fails with IntegrityError
- Return existing evaluation (idempotent)

---

### 2. Human Override During AI Evaluation

**Scenario:** AI evaluating exchange, admin starts override on same exchange.

**Handling:**

- AI evaluation completes first, creates evaluation with `is_final = true`
- Admin override marks it `is_final = false`, creates new version
- Both preserved in audit trail

---

### 3. Finalization Race Condition

**Scenario:** Two workers try to finalize interview simultaneously.

**Handling:**

- Use row-level locking: `SELECT ... FOR UPDATE` on interview
- UNIQUE constraint on `(interview_id, is_current) WHERE is_current = true`
- Second finalization fails with IntegrityError

---

## 11. Configuration

### Environment Variables

```bash
# Evaluation
DEFAULT_EVALUATOR_TYPE=ai  # ai, human, hybrid
EVALUATION_TIMEOUT_SECONDS=30
MAX_EVALUATION_RETRIES=3

# AI Evaluation
EVALUATION_MODEL=gpt-4-turbo
EVALUATION_TEMPERATURE=0.1  # Low temperature for consistency
EVALUATION_MAX_TOKENS=2000

# Scoring Thresholds
STRONG_HIRE_THRESHOLD=85.0
HIRE_THRESHOLD=70.0
REVIEW_THRESHOLD=50.0
# Below REVIEW_THRESHOLD = no_hire

# Proctoring Influence
ENABLE_PROCTORING_INFLUENCE=true
HIGH_RISK_DOWNGRADE=true  # Downgrade recommendation if high proctoring risk
```

---

## 12. Testing Requirements

**Must test:**

### Functional Tests

1. **Duplicate Evaluation:** Verify UNIQUE constraint prevents duplicate
2. **Re-Evaluation Flow:** Verify old marked `is_final = false`, new created
3. **Human Override:** Verify new version created, old preserved
4. **Finalization:** Verify all exchanges evaluated before finalizing
5. **Snapshot Correctness:** Verify rubric/template snapshots match actual at evaluation time
6. **Score Calculation:** Verify total_score = Σ (dimension_score × weight)
7. **Recommendation Logic:** Verify normalized_score mapped to correct recommendation

### Edge Case Tests

1. **Partial Evaluation:** Cannot finalize with pending exchanges
2. **Score Exceeds Max:** Validation rejects invalid score
3. **Rubric Change:** Interview uses snapshot, not live rubric
4. **Concurrent Override:** Second override uses latest version
5. **AI Timeout:** Retry mechanism works, eventual error state

### Concurrency Tests

1. **Simultaneous Evaluation:** Second request returns existing
2. **Finalization Race:** Only one result marked `is_current = true`
3. **Override During Evaluation:** Both versions preserved

---

## 13. Critical Risk Areas

1. **Overwriting Old Evaluations:** Breaks audit trail, destroys history
2. **Recalculating Template During Aggregation:** Non-reproducible scoring
3. **Inconsistent Rubric Weights:** Different exchanges scored with different rubrics
4. **Aggregating Before All Evaluated:** Incomplete final score
5. **Failing to Mark Old Result `is_current = false`:** Multiple current results
6. **Floating Point Precision:** Inconsistent score comparisons (85.5 vs 85.500001)
7. **No Snapshot:** Cannot reproduce scoring after rubric/template changes

---

## 14. Future Enhancements

1. **Machine Learning Score Prediction:**
   - Train model on historical evaluations
   - Predict scores for new exchanges

2. **Batch Evaluation:**
   - Evaluate multiple exchanges in parallel
   - Optimize LLM API usage

3. **Comparative Analysis:**
   - Compare candidate against historical data
   - Percentile rankings

4. **Dynamic Rubrics:**
   - Adjust rubric based on question difficulty
   - Adaptive weighting

5. **Explanation Generation:**
   - AI-generated detailed justifications
   - Natural language feedback

---

**End of Evaluation Module Requirements**

---

## Architectural Intent

The evaluation module is:

- A **deterministic scoring engine with audit guarantees**
- A **transformation pipeline**: Immutable exchanges → Dimension scores → Weighted totals → Final result → Snapshot-safe audit record

It transforms:

```
Immutable exchanges
→ Dimension-level scores (rubric-based)
→ Weighted totals (section aggregation)
→ Final interview result (normalized 0-100)
→ Snapshot-safe audit record (reproducible)
```

**Everything must be reproducible. Everything must be auditable.**
