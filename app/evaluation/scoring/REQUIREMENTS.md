# Evaluation Scoring - Rubric Dimension Scoring Logic

## 1. Purpose

The **Scoring** layer is responsible for:

- Scoring a single exchange against rubric dimensions
- Resolving correct rubric for exchange
- Invoking AI-based scoring (LLM)
- Supporting human manual scoring
- Validating dimension scores
- Calculating weighted total score
- Enforcing score bounds and consistency

**Critical responsibility:** This is the **deterministic scoring engine**. It must:

- Apply rubric dimensions consistently
- Validate scores against max_score
- Calculate total_score = Σ (dimension_score × weight)
- Never skip dimensions
- Preserve scoring reproducibility

---

## 2. Module Structure

```
scoring/
├── rubric_resolver.py    # Resolve correct rubric for exchange
├── ai_scorer.py          # AI-based dimension scoring (LLM)
├── human_scorer.py       # Human manual scoring
├── score_calculator.py   # Total score calculation & validation
└── schemas.py            # Scoring DTOs
```

---

## 3. Rubric Resolution

### Purpose

Resolve the **correct rubric** for a given exchange.

### Resolution Logic

```
interview_exchange
→ interview_id
→ interview.template_id
→ interview_template_rubrics (lookup)
→ rubric_id
→ rubric_dimensions (fetch all)
```

**Must enforce:**

- Rubric is frozen at interview creation (not re-fetched dynamically)
- All dimensions fetched from `rubric_dimensions` table
- Dimensions include: name, weight, max_score, description

### Function Signature

```python
from typing import List
from pydantic import BaseModel

class RubricDimensionDTO(BaseModel):
    rubric_dimension_id: int
    dimension_name: str
    weight: int
    max_score: float
    description: str
    scoring_criteria: Optional[str]

def resolve_rubric(interview_exchange_id: int) -> tuple[int, List[RubricDimensionDTO]]:
    """
    Resolve rubric for exchange.

    Returns:
        (rubric_id, dimensions)

    Raises:
        ExchangeNotFound: Exchange does not exist
        RubricNotFound: No rubric linked to template
        InvalidRubric: Rubric has 0 dimensions
    """
    pass
```

### Edge Cases

**1. Rubric has 0 dimensions:**

- Raise `InvalidRubric` exception
- Cannot evaluate exchange without dimensions

**2. Rubric changed after interview started:**

- Use rubric snapshot from interview creation
- Do NOT re-fetch live rubric

**3. Dimension weight = 0:**

- Include in evaluation (score still recorded)
- Does not contribute to total_score

---

## 4. AI-Based Scoring

### Purpose

Use LLM to score exchange against each rubric dimension.

### Input Context

**Must provide to LLM:**

1. **Question:** question_content from submission
2. **Candidate Answer:** answer_content from submission
3. **Transcript (if audio):** audio_analytics.transcription
4. **Rubric Dimensions:** List of dimensions with descriptions and criteria
5. **Scoring Instructions:** Prompt template

### LLM Prompt Template

```
You are an expert interviewer evaluating a candidate's response.

Question:
{question_content}

Candidate's Answer:
{answer_content}

{optional_transcript}

Rubric Dimensions:
{for dimension in dimensions:}
- {dimension_name} (max {max_score}): {description}
  Criteria: {scoring_criteria}
{endfor}

INSTRUCTIONS:
1. Evaluate the response against EACH dimension separately
2. Assign a score between 0 and {max_score} for each dimension
3. Provide concise justification for each score
4. Be consistent and objective

OUTPUT FORMAT (JSON):
{
  "dimension_scores": [
    {
      "dimension_name": "Accuracy",
      "score": 4.5,
      "justification": "..."
    }
  ],
  "overall_comment": "..."
}
```

### Response Validation

**Must validate:**

1. **Schema correctness:** All dimensions present
2. **Score bounds:** 0 <= score <= max_score
3. **No extra dimensions:** Only rubric dimensions returned
4. **Justification present:** Non-empty string

**If validation fails:**

- Retry with stricter prompt (1 retry)
- If still fails, raise `AIEvaluationError`

### Function Signature

```python
from typing import List
from pydantic import BaseModel

class DimensionScoreResult(BaseModel):
    dimension_name: str
    score: float
    justification: str

class AIScoreResult(BaseModel):
    dimension_scores: List[DimensionScoreResult]
    overall_comment: str

async def score_with_ai(
    question_content: str,
    answer_content: str,
    transcript: Optional[str],
    dimensions: List[RubricDimensionDTO],
    model_id: str = "gpt-4-turbo"
) -> AIScoreResult:
    """
    Score exchange using AI.

    Raises:
        AIEvaluationError: LLM timeout or invalid response
        InvalidScoreError: Score exceeds max_score
    """
    pass
```

### Configuration

```bash
# AI Scoring
EVALUATION_MODEL=gpt-4-turbo
EVALUATION_TEMPERATURE=0.1  # Low for consistency
EVALUATION_MAX_TOKENS=2000
EVALUATION_TIMEOUT_SECONDS=30
MAX_EVALUATION_RETRIES=3
```

### Retry Logic

**On timeout or invalid response:**

- Retry up to 3 times
- Exponential backoff: 1s, 2s, 4s
- If all retries fail, raise `AIEvaluationError`

---

## 5. Human Manual Scoring

### Purpose

Allow admin to manually score each dimension.

### Input

```python
from typing import List

class HumanDimensionScore(BaseModel):
    rubric_dimension_id: int
    score: float = Field(ge=0)
    justification: str = Field(min_length=10, max_length=5000)

class HumanScoreInput(BaseModel):
    dimension_scores: List[HumanDimensionScore]
    overall_comment: str = Field(max_length=5000)
```

### Validation

**Must validate:**

1. All dimensions scored (no missing dimensions)
2. score <= max_score for each dimension
3. Justification provided for each score

**Function Signature:**

```python
def score_with_human(
    dimension_scores: List[HumanDimensionScore],
    dimensions: List[RubricDimensionDTO]
) -> AIScoreResult:  # Same output format
    """
    Validate and format human scores.

    Raises:
        InvalidScoreError: Score exceeds max_score or negative
        MissingDimensionError: Not all dimensions scored
    """
    pass
```

---

## 6. Score Calculation

### Purpose

Calculate weighted total score from dimension scores.

### Formula

```
total_score = Σ (dimension_score × dimension_weight)
```

**NOT normalized** (e.g., if max total = 1000, score can be 850).

### Implementation

```python
from typing import List
from decimal import Decimal

def calculate_total_score(
    dimension_scores: List[DimensionScoreResult],
    dimensions: List[RubricDimensionDTO]
) -> Decimal:
    """
    Calculate weighted total score.

    Formula: Σ (dimension_score × dimension_weight)

    Returns:
        Decimal (rounded to 2 decimal places)
    """
    total = Decimal(0)
    for score_result in dimension_scores:
        dimension = find_dimension(dimensions, score_result.dimension_name)
        weighted_score = Decimal(str(score_result.score)) * Decimal(dimension.weight)
        total += weighted_score

    return total.quantize(Decimal('0.01'))
```

### Edge Cases

**1. Dimension weight = 0:**

- Include in calculation (contributes 0)
- Still recorded in `evaluation_dimension_scores`

**2. Floating point precision:**

- Use `Decimal` type (not float)
- Round to 2 decimal places

**3. Negative scores:**

- Validation rejects (score >= 0)

---

## 7. Score Validation

### Purpose

Validate dimension scores before persisting.

### Validation Rules

**Must enforce:**

1. **Score within bounds:** 0 <= score <= max_score
2. **All dimensions scored:** COUNT(scores) = COUNT(dimensions)
3. **No duplicate dimensions:** Each dimension scored once
4. **No extra dimensions:** Only rubric dimensions scored
5. **Justification present:** Non-empty string

### Function Signature

```python
from typing import List

class ScoreValidationError(Exception):
    pass

def validate_dimension_scores(
    dimension_scores: List[DimensionScoreResult],
    dimensions: List[RubricDimensionDTO]
) -> None:
    """
    Validate dimension scores.

    Raises:
        ScoreValidationError: Validation failed
    """
    # Check all dimensions scored
    if len(dimension_scores) != len(dimensions):
        raise ScoreValidationError(
            f"Expected {len(dimensions)} dimensions, got {len(dimension_scores)}"
        )

    # Check for duplicates
    dimension_names = [s.dimension_name for s in dimension_scores]
    if len(dimension_names) != len(set(dimension_names)):
        raise ScoreValidationError("Duplicate dimension scores")

    # Validate each score
    for score_result in dimension_scores:
        dimension = find_dimension(dimensions, score_result.dimension_name)
        if dimension is None:
            raise ScoreValidationError(
                f"Unknown dimension: {score_result.dimension_name}"
            )

        if score_result.score < 0:
            raise ScoreValidationError(
                f"Negative score for {score_result.dimension_name}: {score_result.score}"
            )

        if score_result.score > dimension.max_score:
            raise ScoreValidationError(
                f"Score {score_result.score} exceeds max_score {dimension.max_score} "
                f"for dimension {score_result.dimension_name}"
            )

        if not score_result.justification or score_result.justification.strip() == "":
            raise ScoreValidationError(
                f"Empty justification for {score_result.dimension_name}"
            )
```

---

## 8. Orchestration

### Scoring Pipeline

```python
from enum import Enum

class EvaluatorType(str, Enum):
    AI = "ai"
    HUMAN = "human"
    HYBRID = "hybrid"

async def score_exchange(
    interview_exchange_id: int,
    evaluator_type: EvaluatorType,
    human_scores: Optional[HumanScoreInput] = None
) -> tuple[List[DimensionScoreResult], Decimal, str]:
    """
    Complete scoring pipeline.

    Steps:
    1. Resolve rubric
    2. Fetch exchange data (question, answer, transcript)
    3. Score with AI or validate human scores
    4. Validate scores
    5. Calculate total score
    6. Return results

    Returns:
        (dimension_scores, total_score, overall_comment)

    Raises:
        ExchangeNotFound
        RubricNotFound
        InvalidRubric
        AIEvaluationError
        ScoreValidationError
    """
    # Step 1: Resolve rubric
    rubric_id, dimensions = resolve_rubric(interview_exchange_id)

    # Step 2: Fetch exchange data
    exchange = fetch_exchange_data(interview_exchange_id)

    # Step 3: Score
    if evaluator_type == EvaluatorType.AI:
        score_result = await score_with_ai(
            question_content=exchange.question_content,
            answer_content=exchange.answer_content,
            transcript=exchange.transcript,
            dimensions=dimensions
        )
    elif evaluator_type == EvaluatorType.HUMAN:
        if human_scores is None:
            raise ValueError("human_scores required for human evaluation")
        score_result = score_with_human(
            dimension_scores=human_scores.dimension_scores,
            dimensions=dimensions
        )
    else:  # HYBRID (not used in initial scoring, only overrides)
        raise ValueError("HYBRID evaluator_type not supported in initial scoring")

    # Step 4: Validate scores
    validate_dimension_scores(score_result.dimension_scores, dimensions)

    # Step 5: Calculate total
    total_score = calculate_total_score(score_result.dimension_scores, dimensions)

    return (score_result.dimension_scores, total_score, score_result.overall_comment)
```

---

## 9. Error Handling

### Exception Hierarchy

```python
class ScoringError(Exception):
    """Base exception for scoring errors."""
    pass

class ExchangeNotFound(ScoringError):
    """Exchange does not exist."""
    pass

class RubricNotFound(ScoringError):
    """No rubric linked to template."""
    pass

class InvalidRubric(ScoringError):
    """Rubric has 0 dimensions or invalid configuration."""
    pass

class AIEvaluationError(ScoringError):
    """AI evaluation failed (timeout, invalid response)."""
    pass

class InvalidScoreError(ScoringError):
    """Score exceeds max_score or is negative."""
    pass

class MissingDimensionError(ScoringError):
    """Not all dimensions scored."""
    pass

class ScoreValidationError(ScoringError):
    """Score validation failed."""
    pass
```

---

## 10. Testing Requirements

### Unit Tests

1. **Rubric resolution:**
   - Valid exchange resolves correct rubric
   - Rubric with 0 dimensions raises error
   - Non-existent exchange raises error

2. **AI scoring:**
   - Valid response parsed correctly
   - Invalid response triggers retry
   - Timeout triggers retry
   - All retries fail raises error

3. **Human scoring:**
   - Valid scores pass validation
   - Missing dimension raises error
   - Score exceeds max raises error

4. **Score calculation:**
   - Weighted sum calculated correctly
   - Rounded to 2 decimal places
   - Handles dimension weight = 0

5. **Score validation:**
   - All dimensions scored
   - No duplicates
   - Scores within bounds
   - Justification present

### Integration Tests

1. End-to-end AI scoring pipeline
2. End-to-end human scoring pipeline
3. Rubric change does not affect in-progress interview
4. Concurrent scoring of multiple exchanges

### Edge Case Tests

1. Rubric with single dimension
2. Dimension with max_score = 0 (invalid)
3. Dimension with weight = 0 (valid, contributes 0)
4. AI returns extra dimensions (rejected)
5. AI returns missing dimensions (rejected)
6. AI returns score > max_score (rejected)

---

## 11. Configuration Values

```python
# scoring/config.py

from pydantic import BaseModel

class ScoringConfig(BaseModel):
    # AI Evaluation
    evaluation_model: str = "gpt-4-turbo"
    evaluation_temperature: float = 0.1
    evaluation_max_tokens: int = 2000
    evaluation_timeout_seconds: int = 30
    max_evaluation_retries: int = 3

    # Score Precision
    score_decimal_places: int = 2

    # Validation
    require_justification: bool = True
    min_justification_length: int = 10
    max_justification_length: int = 5000
```

---

## 12. Concurrency Considerations

### AI Scoring

**Potential issue:** Multiple simultaneous AI requests for same exchange (e.g., API retry).

**Mitigation:**

- Idempotency handled at API layer (checks existing evaluation)
- Scoring layer assumes unique invocation per exchange

### Rubric Resolution

**Potential issue:** Rubric updated mid-interview.

**Mitigation:**

- Use rubric snapshot from interview creation (frozen)
- Do NOT re-fetch live rubric dynamically

---

## 13. Critical Risks

1. **Skipping dimensions:** Total score incorrect, audit trail broken
2. **No validation:** Invalid scores persisted, aggregation fails
3. **Floating point precision:** Inconsistent totals (85.5 vs 85.500001)
4. **Dynamic rubric re-fetch:** Non-reproducible scoring
5. **No retry logic:** AI timeout fails permanently
6. **Overwriting justification:** Audit trail lost

---

## 14. Future Enhancements

1. **Confidence scores:** AI returns confidence for each dimension
2. **Dimension-specific models:** Different LLMs for different dimensions
3. **Batch scoring:** Score multiple exchanges in parallel
4. **Custom judges:** Code execution judges, regex matchers
5. **Explanation generation:** Detailed breakdown for each score

---

**End of Evaluation Scoring Requirements**
