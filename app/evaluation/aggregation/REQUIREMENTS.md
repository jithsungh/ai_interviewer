# Evaluation Aggregation - Interview-Level Final Scoring

## 1. Purpose

The **Aggregation** layer is responsible for:

- Aggregating all exchange evaluations into final interview score
- Computing section-level scores (resume, behavioral, coding)
- Normalizing final score to 0-100 scale
- Determining recommendation (strong_hire, hire, review, no_hire)
- Adjusting for proctoring risk (if enabled)
- Generating strengths, weaknesses, summary notes
- Creating versioned interview results

**Critical responsibility:** This is the **final scoring computation engine**. It must:

- Wait for all exchanges to be evaluated
- Apply template section weights consistently
- Calculate reproducible normalized score
- Map score to recommendation based on thresholds
- Preserve all context in snapshots

---

## 2. Module Structure

```
aggregation/
├── section_aggregator.py    # Aggregate by template section
├── normalizer.py            # Normalize score to 0-100
├── recommendation.py        # Map score to recommendation
├── proctoring_adjuster.py   # Adjust for proctoring risk
├── summary_generator.py     # Generate strengths/weaknesses/notes
└── schemas.py               # Aggregation DTOs
```

---

## 3. Section Aggregation

### Purpose

Aggregate exchange scores by template section (resume, behavioral, coding, etc.).

### Input

**Fetched from database:**

1. **All evaluations** for interview (WHERE `is_final = true`)
2. **Template section weights** from interview template
3. **Exchange metadata** (which section each exchange belongs to)

### Template Section Weight Example

```json
{
  "resume": 10,
  "behavioral": 30,
  "coding": 60
}
```

### Aggregation Logic

**For each section:**

1. Filter evaluations by section
2. Calculate section_score = Σ(evaluation.total_score) for section
3. Calculate section_weight from template
4. Store: `{section_name, section_score, section_weight, exchanges_evaluated}`

### Function Signature

```python
from typing import Dict, List
from pydantic import BaseModel

class SectionScore(BaseModel):
    section_name: str
    score: float  # Sum of all exchange total_scores in section
    weight: int  # From template
    exchanges_evaluated: int

def aggregate_by_section(
    interview_id: int,
    template_weights: Dict[str, int]
) -> List[SectionScore]:
    """
    Aggregate evaluations by template section.

    Args:
        interview_id: Interview to aggregate
        template_weights: Section weights from template {'resume': 10, ...}

    Returns:
        List of section scores

    Raises:
        IncompleteEvaluationError: Not all exchanges evaluated
    """
    # Fetch all exchanges
    exchanges = fetch_exchanges(interview_id)

    # Fetch all evaluations with is_final=true
    evaluations = fetch_final_evaluations(interview_id)

    # Verify all exchanges evaluated
    if len(evaluations) != len(exchanges):
        pending = [e.id for e in exchanges if e.id not in evaluation_exchange_ids]
        raise IncompleteEvaluationError(
            f"Cannot aggregate: {len(pending)} exchanges not evaluated",
            pending_exchange_ids=pending
        )

    # Group evaluations by section
    section_scores = {}
    for exchange in exchanges:
        section = exchange.section_name
        evaluation = find_evaluation(evaluations, exchange.id)

        if section not in section_scores:
            section_scores[section] = {
                'score': 0.0,
                'exchanges': 0
            }

        section_scores[section]['score'] += evaluation.total_score
        section_scores[section]['exchanges'] += 1

    # Build result
    results = []
    for section_name, weight in template_weights.items():
        section_data = section_scores.get(section_name, {'score': 0.0, 'exchanges': 0})
        results.append(SectionScore(
            section_name=section_name,
            score=section_data['score'],
            weight=weight,
            exchanges_evaluated=section_data['exchanges']
        ))

    return results
```

### Edge Cases

**1. Section with 0 exchanges:**

- Include in section_scores with score = 0
- exchanges_evaluated = 0

**2. Section not in template_weights:**

- Log warning: "Section 'system_design' not in template weights"
- Exclude from aggregation (weight = 0 implicitly)

**3. Incomplete evaluations:**

- Raise `IncompleteEvaluationError` with pending exchange IDs
- Cannot finalize until all evaluated

---

## 4. Final Score Calculation

### Purpose

Calculate weighted final score from section scores.

### Formula

```
final_score = Σ (section_score × section_weight)
```

**Example:**

```
resume: 85.0 × 10 = 850.0
behavioral: 78.0 × 30 = 2340.0
coding: 82.0 × 60 = 4920.0
---------------------------
final_score = 8110.0
```

### Function Signature

```python
from decimal import Decimal

def calculate_final_score(section_scores: List[SectionScore]) -> Decimal:
    """
    Calculate weighted final score.

    Formula: Σ (section_score × section_weight)

    Returns:
        Decimal (rounded to 2 decimal places)
    """
    total = Decimal(0)
    for section in section_scores:
        weighted = Decimal(str(section.score)) * Decimal(section.weight)
        total += weighted

    return total.quantize(Decimal('0.01'))
```

---

## 5. Score Normalization

### Purpose

Normalize final score to 0-100 scale for consistent recommendation mapping.

### Formula

```
normalized_score = (final_score / max_possible_score) × 100
```

**Where:**

```
max_possible_score = Σ (max_section_score × section_weight)
```

**Example:**

- Assume each dimension max_score = 5.0, weight = 20
- Resume section: 2 exchanges × 5 dimensions × 5.0 × 20 = 1000
- Behavioral section: 3 exchanges × 5 dimensions × 5.0 × 20 = 1500
- Coding section: 3 exchanges × 5 dimensions × 5.0 × 20 = 1500
- max_possible = (1000 × 10) + (1500 × 30) + (1500 × 60) = 145,000

```
normalized_score = (8110.0 / 145000) × 100 = 5.59
```

**Note:** This example uses hypothetical dimensions. Actual max depends on rubric configuration.

### Function Signature

```python
def normalize_score(
    final_score: Decimal,
    section_scores: List[SectionScore],
    dimensions: List[RubricDimensionDTO]
) -> Decimal:
    """
    Normalize final score to 0-100 scale.

    Args:
        final_score: Weighted sum of section scores
        section_scores: Section breakdown
        dimensions: Rubric dimensions with max_score

    Returns:
        Decimal clamped to [0, 100] with 2 decimal places
    """
    # Calculate max possible score per exchange
    max_per_exchange = sum(d.max_score * d.weight for d in dimensions)

    # Calculate max possible by section
    max_possible = Decimal(0)
    for section in section_scores:
        section_max = max_per_exchange * section.exchanges_evaluated
        weighted_section_max = section_max * Decimal(section.weight)
        max_possible += weighted_section_max

    if max_possible == 0:
        return Decimal(0)

    # Normalize
    normalized = (final_score / max_possible) * Decimal(100)

    # Clamp to [0, 100]
    normalized = max(Decimal(0), min(Decimal(100), normalized))

    return normalized.quantize(Decimal('0.01'))
```

### Edge Cases

**1. max_possible_score = 0:**

- Return normalized_score = 0
- Log warning

**2. final_score > max_possible_score:**

- Clamp to 100
- Log warning: "Final score exceeds max possible"

**3. final_score < 0:**

- Clamp to 0 (should never happen due to validation)

---

## 6. Recommendation Determination

### Purpose

Map normalized_score to recommendation category.

### Thresholds (Configurable)

```python
# From config module
STRONG_HIRE_THRESHOLD = 85.0
HIRE_THRESHOLD = 70.0
REVIEW_THRESHOLD = 50.0
# Below REVIEW_THRESHOLD = no_hire
```

### Mapping Logic

```python
def determine_recommendation(normalized_score: Decimal) -> str:
    """
    Map normalized score to recommendation.

    Returns: 'strong_hire' | 'hire' | 'review' | 'no_hire'
    """
    score = float(normalized_score)

    if score >= config.STRONG_HIRE_THRESHOLD:
        return "strong_hire"
    elif score >= config.HIRE_THRESHOLD:
        return "hire"
    elif score >= config.REVIEW_THRESHOLD:
        return "review"
    else:
        return "no_hire"
```

### Edge Cases

**1. Border case (score = 70.00):**

- Use inclusive threshold: score >= 70 → "hire"

**2. Proctoring risk:**

- Apply adjustment AFTER initial recommendation
- See Proctoring Adjustment section below

---

## 7. Proctoring Risk Adjustment

### Purpose

Adjust recommendation if high proctoring risk detected.

### Configuration

```bash
# Feature flag
ENABLE_PROCTORING_INFLUENCE=true

# Adjustment rules
HIGH_RISK_DOWNGRADE=true  # Downgrade recommendation by one level
```

### Adjustment Logic

```python
def adjust_for_proctoring(
    recommendation: str,
    interview_id: int
) -> str:
    """
    Adjust recommendation based on proctoring risk.

    Args:
        recommendation: Initial recommendation
        interview_id: Interview to check proctoring events

    Returns:
        Adjusted recommendation
    """
    if not config.ENABLE_PROCTORING_INFLUENCE:
        return recommendation

    # Fetch proctoring risk
    risk_level = fetch_proctoring_risk(interview_id)

    if risk_level == "high" and config.HIGH_RISK_DOWNGRADE:
        # Downgrade by one level
        if recommendation == "strong_hire":
            return "hire"
        elif recommendation == "hire":
            return "review"
        elif recommendation == "review":
            return "no_hire"
        # no_hire stays no_hire

    return recommendation
```

### Supplementary Report

**Must create `proctoring_risk` report:**

```json
{
  "report_type": "proctoring_risk",
  "report_data": {
    "overall_risk": "high",
    "suspicious_events": 5,
    "flagged_behaviors": [
      "Multiple window switches",
      "Long silence periods",
      "Background noise detected"
    ],
    "recommendation_adjustment": "Downgraded from 'hire' to 'review'"
  }
}
```

---

## 8. Summary Generation

### Purpose

Generate human-readable strengths, weaknesses, and summary notes.

### Input Context

**Must aggregate:**

1. All dimension scores across exchanges
2. Coding scores (if applicable)
3. Audio analytics (pause frequency, confidence)
4. Proctoring signals

### AI-Powered Generation

**Prompt template:**

```
You are generating a summary for an interview.

Candidate Performance:
{for section in section_scores:}
- {section_name}: {section.score} ({section.exchanges_evaluated} exchanges)
{endfor}

Dimension Breakdown:
{for dimension in all_dimension_scores:}
- {dimension_name}: avg {avg_score} / {max_score}
{endfor}

Coding Performance:
- Problems Solved: {passed} / {total}
- Average Score: {avg_coding_score}

INSTRUCTIONS:
1. Identify top 3-5 strengths
2. Identify top 3-5 weaknesses/areas for improvement
3. Write 2-3 paragraph summary

OUTPUT FORMAT (JSON):
{
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "summary_notes": "..."
}
```

### Function Signature

```python
from typing import List

class SummaryData(BaseModel):
    strengths: List[str]
    weaknesses: List[str]
    summary_notes: str

async def generate_summary(
    section_scores: List[SectionScore],
    all_evaluations: List[EvaluationDTO],
    coding_stats: Optional[CodingStatsDTO]
) -> SummaryData:
    """
    Generate AI-powered summary.

    Returns:
        Summary with strengths, weaknesses, notes
    """
    pass
```

### Fallback (AI Unavailable)

**If timeout or error:**

- Return empty lists and generic summary:
  ```python
  SummaryData(
      strengths=[],
      weaknesses=[],
      summary_notes=f"Interview completed with normalized score {normalized_score}. "
                    f"Detailed summary unavailable."
  )
  ```

---

## 9. Aggregation Orchestration

### Complete Pipeline

```python
from decimal import Decimal

class InterviewResultData(BaseModel):
    final_score: Decimal
    normalized_score: Decimal
    result_status: str
    recommendation: str
    section_scores: List[SectionScore]
    strengths: List[str]
    weaknesses: List[str]
    summary_notes: str
    rubric_snapshot: dict
    template_weight_snapshot: dict
    generated_by: str
    model_id: Optional[str]

async def aggregate_interview_result(
    interview_id: int,
    generated_by: str = "ai"
) -> InterviewResultData:
    """
    Complete aggregation pipeline.

    Steps:
    1. Verify all exchanges evaluated
    2. Fetch template weights
    3. Aggregate by section
    4. Calculate final score
    5. Normalize score
    6. Determine recommendation
    7. Adjust for proctoring (if enabled)
    8. Generate summary
    9. Create snapshots
    10. Return result data

    Raises:
        IncompleteEvaluationError: Not all exchanges evaluated
        InterviewNotFound: Interview does not exist
    """
    # Step 1: Check completeness
    exchanges = fetch_exchanges(interview_id)
    evaluations = fetch_final_evaluations(interview_id)
    if len(evaluations) != len(exchanges):
        raise IncompleteEvaluationError

    # Step 2: Fetch template
    template_weights = fetch_template_weights(interview_id)
    rubric_id, dimensions = fetch_rubric(interview_id)

    # Step 3: Aggregate sections
    section_scores = aggregate_by_section(interview_id, template_weights)

    # Step 4: Calculate final
    final_score = calculate_final_score(section_scores)

    # Step 5: Normalize
    normalized_score = normalize_score(final_score, section_scores, dimensions)

    # Step 6: Determine recommendation
    recommendation = determine_recommendation(normalized_score)

    # Step 7: Adjust for proctoring
    recommendation = adjust_for_proctoring(recommendation, interview_id)

    # Step 8: Generate summary
    summary = await generate_summary(section_scores, evaluations, fetch_coding_stats(interview_id))

    # Step 9: Create snapshots
    rubric_snapshot = create_rubric_snapshot(rubric_id, dimensions)
    template_weight_snapshot = template_weights

    # Step 10: Return
    return InterviewResultData(
        final_score=final_score,
        normalized_score=normalized_score,
        result_status="completed",
        recommendation=recommendation,
        section_scores=section_scores,
        strengths=summary.strengths,
        weaknesses=summary.weaknesses,
        summary_notes=summary.summary_notes,
        rubric_snapshot=rubric_snapshot,
        template_weight_snapshot=template_weight_snapshot,
        generated_by=generated_by,
        model_id=config.EVALUATION_MODEL if generated_by == "ai" else None
    )
```

---

## 10. Versioning

### Purpose

Support re-finalization (human override triggers new aggregate).

### Flow

1. Mark old result `is_current = false`
2. Create new result with `is_current = true`
3. Preserve old result for audit

**Database constraint:**

```sql
UNIQUE(interview_id, is_current) WHERE is_current = true
```

---

## 11. Edge Cases

### 1. Incomplete Evaluations

**Scenario:** Finalize called before all exchanges evaluated.

**Handling:**

- Raise `IncompleteEvaluationError` with pending exchange IDs
- Return 422 to API caller

---

### 2. Section with 0 Exchanges

**Scenario:** Template defines section "system_design" but interview has no such exchanges.

**Handling:**

- Include in section_scores with score = 0, exchanges = 0
- Weight still applied (contributes 0 to final_score)

---

### 3. Template Weight Changed

**Scenario:** Template updated mid-interview with different weights.

**Handling:**

- Use template_weight_snapshot from interview creation
- Do NOT re-fetch live template

---

### 4. Proctoring Risk High but Feature Disabled

**Scenario:** Proctoring events exist but `ENABLE_PROCTORING_INFLUENCE = false`.

**Handling:**

- Ignore proctoring risk
- Recommendation based only on score

---

### 5. AI Summary Timeout

**Scenario:** Summary generation times out.

**Handling:**

- Log warning
- Return empty strengths/weaknesses
- Generic summary_notes

---

### 6. Floating Point Precision

**Scenario:** normalized_score = 69.999999 vs 70.0.

**Handling:**

- Round to 2 decimal places before comparison
- Use Decimal type, not float

---

## 12. Configuration

```bash
# Recommendation Thresholds
STRONG_HIRE_THRESHOLD=85.0
HIRE_THRESHOLD=70.0
REVIEW_THRESHOLD=50.0

# Proctoring Influence
ENABLE_PROCTORING_INFLUENCE=true
HIGH_RISK_DOWNGRADE=true

# Summary Generation
SUMMARY_MODEL=gpt-4-turbo
SUMMARY_TEMPERATURE=0.7
SUMMARY_MAX_TOKENS=1500
SUMMARY_TIMEOUT_SECONDS=30
```

---

## 13. Testing Requirements

### Unit Tests

1. Section aggregation with multiple sections
2. Final score calculation with weights
3. Normalization to 0-100 scale
4. Recommendation mapping at thresholds
5. Proctoring adjustment (downgrade logic)
6. Summary generation (mock AI)

### Integration Tests

1. End-to-end aggregation pipeline
2. Incomplete evaluations raise error
3. Template weight snapshot used (not live template)
4. Versioning (old result marked non-current)

### Edge Case Tests

1. Section with 0 exchanges
2. normalized_score = threshold (border case)
3. Proctoring disabled (no adjustment)
4. AI summary timeout (fallback)
5. max_possible_score = 0 (degenerate case)

---

## 14. Critical Risks

1. **Aggregating incomplete:** Final score incorrect, missing exchanges
2. **Dynamic template fetch:** Non-reproducible scoring
3. **Floating point comparison:** Border cases misclassified
4. **No version control:** Overwriting old result destroys audit trail
5. **Proctoring influence without flag check:** Unexpected downgrades
6. **No max_possible validation:** Division by zero

---

**End of Evaluation Aggregation Requirements**
