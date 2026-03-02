# Evaluation Scoring Module — Human Testing Guide

This guide provides step-by-step instructions for manually testing the scoring module.

## Prerequisites

1. **Database**: PostgreSQL with schema applied
2. **Server**: FastAPI application running on `localhost:8000`
3. **Data**: At least one interview exchange with linked rubric

### Required Test Data

Before testing, ensure you have:

1. An interview template with rubric linked via `interview_template_rubrics`
2. An interview submission using that template
3. At least one interview exchange for that submission

## 1. AI Scoring — Score Exchange with AI

### Endpoint

```
POST /api/v1/evaluations/exchanges/{exchange_id}/score
```

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/exchanges/1/score" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "evaluator_type": "ai"
  }'
```

### Expected Response (200 OK)

```json
{
  "evaluation_id": 1,
  "interview_exchange_id": 1,
  "rubric_id": 5,
  "evaluator_type": "ai",
  "total_score": 82.50,
  "dimension_scores": [
    {
      "dimension_name": "Accuracy",
      "score": 4.5,
      "justification": "Demonstrated strong technical accuracy..."
    },
    {
      "dimension_name": "Communication",
      "score": 4.0,
      "justification": "Clear explanation with good structure..."
    },
    {
      "dimension_name": "Problem Solving",
      "score": 4.0,
      "justification": "Showed systematic problem-solving approach..."
    }
  ],
  "overall_comment": "Strong overall performance with clear understanding...",
  "model_id": "llama-3.3-70b-versatile",
  "scoring_version": "1.0.0",
  "evaluated_at": "2025-01-15T10:30:00Z"
}
```

### Error Cases

**Exchange Not Found (404)**
```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/exchanges/9999/score" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"evaluator_type": "ai"}'
```

**Evaluation Already Exists (409)**
```bash
# Second request to same exchange without force_rescore
curl -X POST "http://localhost:8000/api/v1/evaluations/exchanges/1/score" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"evaluator_type": "ai"}'
```

---

## 2. Human Scoring — Manual Evaluation

### Endpoint

```
POST /api/v1/evaluations/exchanges/{exchange_id}/score
```

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/exchanges/2/score" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "evaluator_type": "human",
    "human_scores": {
      "dimension_scores": [
        {
          "rubric_dimension_id": 1,
          "score": 4.5,
          "justification": "Excellent technical accuracy with minor issues in edge cases."
        },
        {
          "rubric_dimension_id": 2,
          "score": 4.0,
          "justification": "Clear communication with well-structured explanation."
        },
        {
          "rubric_dimension_id": 3,
          "score": 4.0,
          "justification": "Good problem-solving methodology demonstrated."
        }
      ],
      "overall_comment": "Strong candidate with solid technical foundation.",
      "evaluator_id": 42
    }
  }'
```

### Expected Response (200 OK)

```json
{
  "evaluation_id": 2,
  "interview_exchange_id": 2,
  "rubric_id": 5,
  "evaluator_type": "human",
  "total_score": 83.33,
  "dimension_scores": [...],
  "overall_comment": "Strong candidate with solid technical foundation.",
  "model_id": null,
  "scoring_version": "1.0.0",
  "evaluated_at": "2025-01-15T10:35:00Z"
}
```

### Error Cases

**Missing Dimension (400)**
```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/exchanges/2/score" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "evaluator_type": "human",
    "human_scores": {
      "dimension_scores": [
        {
          "rubric_dimension_id": 1,
          "score": 4.5,
          "justification": "Only scoring one dimension..."
        }
      ],
      "overall_comment": "Partial evaluation.",
      "evaluator_id": 42
    }
  }'
```

**Score Exceeds Maximum (400)**
```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/exchanges/2/score" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "evaluator_type": "human",
    "human_scores": {
      "dimension_scores": [
        {
          "rubric_dimension_id": 1,
          "score": 10.0,
          "justification": "Score exceeds max_score of 5.0"
        },
        {
          "rubric_dimension_id": 2,
          "score": 4.0,
          "justification": "Valid score."
        },
        {
          "rubric_dimension_id": 3,
          "score": 4.0,
          "justification": "Valid score."
        }
      ],
      "overall_comment": "Test.",
      "evaluator_id": 42
    }
  }'
```

---

## 3. Re-Scoring — Override Previous Evaluation

### Endpoint

```
POST /api/v1/evaluations/exchanges/{exchange_id}/score?force_rescore=true
```

### Request

```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/exchanges/1/score?force_rescore=true" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "evaluator_type": "human",
    "human_scores": {
      "dimension_scores": [
        {
          "rubric_dimension_id": 1,
          "score": 5.0,
          "justification": "After review, upgrading accuracy score."
        },
        {
          "rubric_dimension_id": 2,
          "score": 4.5,
          "justification": "Excellent communication demonstrated."
        },
        {
          "rubric_dimension_id": 3,
          "score": 4.5,
          "justification": "Strong problem-solving skills."
        }
      ],
      "overall_comment": "Re-evaluated with updated scoring.",
      "evaluator_id": 42
    }
  }'
```

### Expected Behavior

- Previous evaluation marked as `is_final = false`
- New evaluation created with `is_final = true`
- Both evaluations remain in database (audit trail)

---

## 4. Fetch Evaluation

### Get by Evaluation ID

```bash
curl -X GET "http://localhost:8000/api/v1/evaluations/1" \
  -H "Authorization: Bearer $TOKEN"
```

### Get by Exchange ID

```bash
curl -X GET "http://localhost:8000/api/v1/evaluations/exchanges/1" \
  -H "Authorization: Bearer $TOKEN"
```

### Expected Response

```json
{
  "evaluation_id": 1,
  "interview_exchange_id": 1,
  "rubric_id": 5,
  "evaluator_type": "ai",
  "total_score": 82.50,
  "dimension_scores": [...],
  "overall_comment": "...",
  "model_id": "llama-3.3-70b-versatile",
  "scoring_version": "1.0.0",
  "evaluated_at": "2025-01-15T10:30:00Z"
}
```

---

## 5. Database Verification

### Check Evaluation Created

```sql
SELECT * FROM evaluations 
WHERE interview_exchange_id = 1
ORDER BY evaluated_at DESC;
```

### Check Dimension Scores

```sql
SELECT 
    e.id AS evaluation_id,
    rd.dimension_name,
    eds.score,
    eds.max_score,
    eds.justification
FROM evaluation_dimension_scores eds
JOIN evaluations e ON eds.evaluation_id = e.id
JOIN rubric_dimensions rd ON eds.rubric_dimension_id = rd.id
WHERE e.interview_exchange_id = 1;
```

### Verify One Exchange = One Final Evaluation

```sql
-- Should return at most 1 row per exchange
SELECT interview_exchange_id, COUNT(*) 
FROM evaluations 
WHERE is_final = true 
GROUP BY interview_exchange_id 
HAVING COUNT(*) > 1;
```

### Check Re-evaluation History

```sql
SELECT id, is_final, evaluator_type, total_score, evaluated_at
FROM evaluations
WHERE interview_exchange_id = 1
ORDER BY evaluated_at DESC;
```

---

## 6. Unit Test Execution

### Run All Scoring Tests

```bash
# From project root
pytest tests/unit/evaluation/scoring/ -v
```

### Run Specific Test File

```bash
pytest tests/unit/evaluation/scoring/test_score_calculator.py -v
```

### Run Integration Tests

```bash
pytest tests/integration/evaluation/scoring/ -v
```

### Run with Coverage

```bash
pytest tests/unit/evaluation/scoring/ --cov=app.evaluation.scoring --cov-report=html
```

---

## 7. Common Issues & Troubleshooting

### Issue: RubricNotFoundError

**Cause**: Exchange's template doesn't have a linked rubric.

**Solution**: 
```sql
-- Check template has rubric
SELECT * FROM interview_template_rubrics 
WHERE template_id = (
    SELECT template_id FROM interview_submissions 
    WHERE id = (
        SELECT interview_submission_id FROM interview_exchanges WHERE id = 1
    )
);
```

### Issue: InvalidRubricError

**Cause**: Rubric exists but has no dimensions.

**Solution**:
```sql
-- Check rubric has dimensions
SELECT * FROM rubric_dimensions WHERE rubric_id = 5;
```

### Issue: AIEvaluationError

**Cause**: LLM provider timeout or invalid response.

**Check**:
1. LLM provider credentials configured
2. Network connectivity to LLM endpoint
3. Check application logs for detailed error

### Issue: EvaluationExistsError

**Cause**: Exchange already has final evaluation.

**Solution**: Use `force_rescore=true` query parameter.

---

## 8. Environment Variables

```bash
# Scoring Configuration
EVALUATION_MODEL=llama-3.3-70b-versatile
EVALUATION_TEMPERATURE=0.1
EVALUATION_MAX_TOKENS=2000
EVALUATION_TIMEOUT_SECONDS=30
MAX_EVALUATION_RETRIES=3

# Score Formatting
SCORE_DECIMAL_PLACES=2
NORMALIZED_SCALE=100

# Justification Validation
REQUIRE_JUSTIFICATION=true
MIN_JUSTIFICATION_LENGTH=10
MAX_JUSTIFICATION_LENGTH=5000
```

---

## Checklist

- [ ] AI scoring creates evaluation with dimension scores
- [ ] Human scoring validates all dimensions present
- [ ] Score bounds enforced (0 <= score <= max_score)
- [ ] Justification requirements enforced
- [ ] Total score calculated correctly (weighted sum)
- [ ] One exchange = one final evaluation (invariant)
- [ ] Re-scoring marks previous as non-final
- [ ] Evaluation audit trail maintained
- [ ] Error messages are informative
- [ ] Unit tests pass
- [ ] Integration tests pass
