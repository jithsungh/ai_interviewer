# Evaluation Aggregation — Human Testing Guide

## Overview

The **aggregation** module computes interview-level final scores by:

1. Fetching all exchange evaluations for a submission
2. Grouping scores by template section with weights
3. Normalizing to 0–100
4. Mapping to recommendation (strong_hire / hire / review / no_hire)
5. Optionally adjusting for proctoring risk
6. Generating AI-powered summary (with fallback)
7. Persisting the `interview_results` row

---

## Prerequisites

- PostgreSQL running with schema applied (`docs/schema.sql`)
- At least one `interview_submission` with exchanges and final evaluations
- Template with `template_structure.scoring_configuration.section_weights`
- Python virtual environment activated (`.venv/bin/activate`)

---

## Module Entry Points

### Programmatic (Service)

```python
from sqlalchemy.orm import Session
from app.evaluation.aggregation import AggregationService

service = AggregationService(db=session, llm_provider=provider)
result = await service.aggregate_interview_result(
    submission_id=123,
    generated_by="ai",
    force_reaggregate=False,
)
```

### Programmatic (Convenience Function)

```python
from app.evaluation.aggregation import aggregate_interview_result

result = await aggregate_interview_result(
    db=session,
    submission_id=123,
    generated_by="ai",
    force_reaggregate=False,
    llm_provider=provider,
)
```

> **Note:** There is no standalone REST API endpoint yet for aggregation.
> The `evaluation/api` module is a placeholder (REQUIREMENTS.md only).
> Aggregation is invoked programmatically by the interview orchestration layer.

---

## API Endpoints

_No REST endpoints are defined by this module._ The aggregation service is consumed internally via dependency injection. When the `evaluation/api` module is implemented, the following is the expected API shape:

### POST /api/v1/evaluations/aggregate

**Purpose:** Trigger aggregation for a completed interview submission.

| Field              | Type    | Required | Description                          |
|--------------------|---------|----------|--------------------------------------|
| submission_id      | int     | Yes      | Interview submission ID              |
| generated_by       | string  | No       | "ai" (default), "human", "system"    |
| force_reaggregate  | bool    | No       | false (default). Create new version? |

**Expected Request:**

```json
{
  "submission_id": 123,
  "generated_by": "ai",
  "force_reaggregate": false
}
```

**Expected Success Response (200):**

```json
{
  "interview_submission_id": 123,
  "final_score": "8110.00",
  "normalized_score": "72.45",
  "result_status": "completed",
  "recommendation": "hire",
  "section_scores": [
    {"section_name": "resume", "score": "85.00", "weight": 10, "exchanges_evaluated": 2},
    {"section_name": "behavioral", "score": "78.00", "weight": 30, "exchanges_evaluated": 3},
    {"section_name": "coding", "score": "82.00", "weight": 60, "exchanges_evaluated": 3}
  ],
  "strengths": ["Strong problem-solving skills", "Clear communication"],
  "weaknesses": ["Limited system design knowledge"],
  "summary_notes": "The candidate demonstrated solid technical ability...",
  "scoring_version": "1.0.0",
  "generated_by": "ai"
}
```

**Error Responses:**

| Status | Error Code               | Condition                                      |
|--------|--------------------------|------------------------------------------------|
| 404    | INTERVIEW_NOT_FOUND      | Submission does not exist                      |
| 409    | AGGREGATION_EXISTS       | Current result exists (without force flag)     |
| 422    | INCOMPLETE_EVALUATION    | Not all exchanges have final evaluations       |
| 422    | NO_EXCHANGES             | Submission has zero exchanges                  |
| 422    | TEMPLATE_WEIGHTS_NOT_FOUND | Template lacks section_weights               |
| 500    | AGGREGATION_ERROR        | Unexpected persistence failure                 |

---

## Configuration

Environment variables (prefix `AGGREGATION_`):

```bash
# Recommendation Thresholds
AGGREGATION_STRONG_HIRE_THRESHOLD=85.0
AGGREGATION_HIRE_THRESHOLD=70.0
AGGREGATION_REVIEW_THRESHOLD=50.0

# Proctoring Influence
AGGREGATION_ENABLE_PROCTORING_INFLUENCE=false   # Set to true to enable
AGGREGATION_HIGH_RISK_DOWNGRADE=true

# Summary Generation
AGGREGATION_SUMMARY_MODEL=llama-3.3-70b-versatile
AGGREGATION_SUMMARY_TEMPERATURE=0.7
AGGREGATION_SUMMARY_MAX_TOKENS=1500
AGGREGATION_SUMMARY_TIMEOUT_SECONDS=30

# Score Config
AGGREGATION_MAX_EXCHANGE_SCORE=100.0
AGGREGATION_SCORE_DECIMAL_PLACES=2
AGGREGATION_SCORING_VERSION=1.0.0
```

---

## Testing

### Run Unit Tests

```bash
.venv/bin/python -m pytest tests/unit/evaluation/aggregation/ -v
```

### Run Integration Tests

```bash
.venv/bin/python -m pytest tests/integration/evaluation/aggregation/ -v
```

### Run All Aggregation Tests

```bash
.venv/bin/python -m pytest tests/unit/evaluation/aggregation/ tests/integration/evaluation/aggregation/ -v
```

### Expected Results

- **89 tests total** (74 unit + 15 integration-style)
- All should pass with 0 failures

---

## Test Scenarios

### 1. Complete Aggregation (Happy Path)

**Setup:**
- Create interview_submission with template containing section_weights
- Create 3+ exchanges with `content_metadata.section_name` set
- Create final evaluations (`is_final=true`) for each exchange

**Verify:**
- `interview_results` row created with `is_current=true`
- `final_score` = Σ(section_score × section_weight)
- `normalized_score` in [0, 100]
- `recommendation` matches threshold mapping
- `section_scores` JSONB contains per-section totals

### 2. Incomplete Evaluations

**Setup:**
- Create 3 exchanges, only 2 have final evaluations

**Verify:**
- Raises `IncompleteEvaluationError` (HTTP 422)
- Error metadata contains `pending_exchange_ids`

### 3. Versioning (Re-aggregation)

**Setup:**
- Run aggregation once (creates result with `is_current=true`)
- Run again with `force_reaggregate=true`

**Verify:**
- Old result updated to `is_current=false`
- New result created with `is_current=true`
- Both rows preserved for audit trail

### 4. Proctoring Adjustment

**Setup:**
- Set `AGGREGATION_ENABLE_PROCTORING_INFLUENCE=true`
- Insert high-severity proctoring_events for the submission
- Run aggregation

**Verify:**
- Recommendation downgraded by one level
- `supplementary_reports` row with `report_type='proctoring_risk'`

### 5. AI Summary Fallback

**Setup:**
- Run aggregation with no LLM provider configured

**Verify:**
- Result has empty `strengths`/`weaknesses` lists
- `summary_notes` contains generic fallback text

---

## Schema Dependencies

### Tables Read

| Table                      | Fields Used                                                |
|----------------------------|------------------------------------------------------------|
| interview_submissions      | id, template_id, status                                    |
| interview_exchanges        | id, interview_submission_id, sequence_order, content_metadata |
| evaluations                | id, interview_exchange_id, total_score, evaluator_type, is_final |
| interview_templates        | id, template_structure (JSONB)                             |
| interview_template_rubrics | interview_template_id, rubric_id                           |
| rubrics                    | id, name                                                   |
| rubric_dimensions          | rubric_id, dimension_name, weight, max_score, sequence_order |
| proctoring_events          | interview_submission_id, severity, event_type (optional)   |

### Tables Written

| Table                  | Operation | Fields Written                                                              |
|------------------------|-----------|-----------------------------------------------------------------------------|
| interview_results      | INSERT    | All columns per schema.sql                                                  |
| interview_results      | UPDATE    | `is_current = false` (versioning only)                                      |
| supplementary_reports  | INSERT    | interview_submission_id, report_type, content, generated_by (proctoring only)|

### No Schema Changes Required

All tables already exist in `docs/schema.sql`. No migrations needed.

---

## Debugging Tips

1. **Missing section_weights:** Check `interview_templates.template_structure` has:
   ```json
   {"scoring_configuration": {"section_weights": {"resume": 10, "behavioral": 30, "coding": 60}}}
   ```

2. **Section mismatch:** Verify `interview_exchanges.content_metadata.section_name` matches template section names.

3. **Normalized score of 0:** Check `max_exchange_score` config matches your scoring module output range (default 100.0).

4. **Proctoring not adjusting:** Verify `AGGREGATION_ENABLE_PROCTORING_INFLUENCE=true` and `proctoring_events` table has rows with `severity='high'` or `severity='critical'`.

---

## Architecture Notes

- **No cross-module imports** — reads from DB tables owned by interview/scoring/proctoring modules via raw SQL
- **ORM models** for `interview_results` and `supplementary_reports` defined locally (will migrate to `evaluation/persistence` when implemented)
- **Config singleton** follows same pattern as `evaluation/scoring/config.py`
- **Error hierarchy** extends `app.shared.errors.BaseError`
- **Logging** via `app.shared.observability.get_context_logger`
- **LLM integration** via `app.ai.llm.BaseLLMProvider` (TYPE_CHECKING import only for summary generation)
