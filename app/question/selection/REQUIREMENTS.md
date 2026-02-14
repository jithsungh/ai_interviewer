# Question Selection - Rule-Based Filtering & Adaptive Difficulty

## 1. Purpose

The **selection** subdirectory handles:

- Deterministic next question selection based on template structure
- Adaptive difficulty progression based on candidate performance
- Repetition prevention via embedding similarity
- Topic and constraint filtering
- Fallback strategies when no match found

**Critical responsibility:** Deterministic, auditable question selection that respects template structure and adapts to candidate performance.

---

## 2. Responsibilities

### 2.1 Template-Based Selection

**Provides:**

- Parse template_structure_snapshot from submission
- Extract current section configuration
- Determine question count remaining in section
- Apply topic constraints
- Apply difficulty constraints
- Respect selection_strategy (retrieval, static_pool, adaptive)

**Must:**

- Never JOIN to interview_templates table
- Read only from frozen snapshot
- Validate snapshot schema before use

---

### 2.2 Difficulty Adaptation (FR-3.2, FR-4.3, FR-4.4)

**Algorithm:**

```python
def adapt_difficulty(
    previous_difficulty: str,
    previous_score: Optional[float],
    config: DifficultyConfig
) -> tuple[str, str]:
    """
    Adapt difficulty based on previous performance.

    Returns: (next_difficulty, adaptation_reason)
    """
    # No previous score → use template default
    if previous_score is None:
        return (template_default_difficulty, "first_question")

    # Score above threshold → escalate
    if previous_score >= config.threshold_up:
        next_diff = increase_difficulty(previous_difficulty, config.max_jump)
        reason = f"score_{previous_score:.1f}_above_threshold_{config.threshold_up}"
        return (next_diff, reason)

    # Score below threshold → downgrade
    elif previous_score < config.threshold_down:
        next_diff = decrease_difficulty(previous_difficulty, config.max_jump)
        reason = f"score_{previous_score:.1f}_below_threshold_{config.threshold_down}"
        return (next_diff, reason)

    # Score in range → maintain
    else:
        reason = f"score_{previous_score:.1f}_in_range"
        return (previous_difficulty, reason)
```

**Difficulty ordering:**

```
easy → medium → hard
```

**Max jump constraint:**

- `max_jump=1`: Can only move one level (easy → medium, not easy → hard)
- Prevents jarring difficulty spikes

---

### 2.3 Repetition Prevention (FR-4.5)

**Strategy:**

1. Check exact match: `question_id in previous_exchange_ids` → reject
2. Check semantic similarity: `similarity(candidate_embedding, previous_embeddings) > threshold` → reject
3. If all candidates rejected → relax threshold or trigger generation

**Similarity threshold:**

- `identical_threshold = 0.95`: Essentially same question
- `similar_threshold = 0.85`: Too similar for reuse

**Implementation:**

```python
def is_repetition(
    candidate_question_id: int,
    candidate_embedding: list[float],
    exchange_history: list[Exchange],
    threshold: float = 0.85
) -> tuple[bool, Optional[float]]:
    """
    Check if candidate question is repetition.

    Returns: (is_repetition, max_similarity_score)
    """
    # Check exact match
    if candidate_question_id in [e.question_id for e in exchange_history]:
        return (True, 1.0)

    # Check semantic similarity
    max_similarity = 0.0
    for exchange in exchange_history:
        if exchange.question_embedding:
            similarity = cosine_similarity(
                candidate_embedding,
                exchange.question_embedding
            )
            max_similarity = max(max_similarity, similarity)

            if similarity >= threshold:
                return (True, similarity)

    return (False, max_similarity)
```

---

### 2.4 Multi-Tenant Filtering

**Must enforce:**

- Questions with `scope = 'public'` → visible to all
- Questions with `scope = 'organization'` → visible to organization_id only
- Questions with `scope = 'private'` → visible to creator only (admin use)

**Query filter:**

```sql
SELECT * FROM questions
WHERE is_active = TRUE
  AND (
    scope = 'public'
    OR (scope = 'organization' AND organization_id = :org_id)
  )
  AND difficulty = :difficulty
  AND topic_id IN (:topic_ids)
```

---

## 3. Selection Workflow

### 3.1 Main Selection Function

**Interface:**

```python
@dataclass
class SelectionContext:
    """Input context for selection."""
    submission_id: int
    organization_id: int
    template_snapshot: dict
    current_section: str
    exchange_history: list[dict]
    candidate_profile: Optional[dict]

@dataclass
class SelectionResult:
    """Output of selection."""
    question_snapshot: QuestionSnapshot
    selection_metadata: dict
    adaptation_decision: Optional[AdaptationDecision]

def select_next_question(context: SelectionContext) -> SelectionResult:
    """
    Select next question based on template and context.

    Workflow:
    1. Parse template snapshot
    2. Determine current section
    3. Adapt difficulty (if enabled)
    4. Filter by topic and difficulty
    5. Check repetition
    6. Fallback if needed
    7. Return snapshot
    """
    pass
```

---

### 3.2 Workflow Steps

**Step 1: Parse template snapshot**

```python
template = context.template_snapshot
section_config = find_section(template, context.current_section)

if not section_config:
    raise TemplateError(f"Section {context.current_section} not found in template")
```

**Step 2: Count remaining questions**

```python
section_exchanges = [
    e for e in context.exchange_history
    if e['section_name'] == context.current_section
]
remaining = section_config['question_count'] - len(section_exchanges)

if remaining <= 0:
    raise SectionCompleteError(f"Section {context.current_section} already complete")
```

**Step 3: Adapt difficulty**

```python
if section_config.get('selection_strategy') == 'adaptive':
    last_exchange = get_last_exchange_in_section(
        context.exchange_history,
        context.current_section
    )

    if last_exchange and last_exchange['evaluation_score']:
        target_difficulty, reason = adapt_difficulty(
            previous_difficulty=last_exchange['difficulty'],
            previous_score=last_exchange['evaluation_score'],
            config=difficulty_config
        )

        # Log adaptation decision
        log_adaptation(submission_id, target_difficulty, reason)
    else:
        target_difficulty = section_config['difficulty_range'][0]  # Default to first
        reason = "first_question_in_section"
else:
    target_difficulty = section_config['difficulty_range'][0]
    reason = "static_difficulty"
```

**Step 4: Retrieve candidates**

```python
if section_config.get('selection_strategy') == 'semantic_retrieval':
    candidates = retrieval_service.search(
        organization_id=context.organization_id,
        difficulty=target_difficulty,
        topics=section_config['topic_constraints'],
        resume_embedding=context.candidate_profile.get('resume_embedding'),
        top_k=10
    )
elif section_config.get('selection_strategy') == 'static_pool':
    candidates = question_repository.filter(
        organization_id=context.organization_id,
        difficulty=target_difficulty,
        topics=section_config['topic_constraints']
    )
else:
    raise ValueError(f"Unknown strategy: {section_config['selection_strategy']}")
```

**Step 5: Filter repetitions**

```python
candidates_deduplicated = []
for candidate in candidates:
    is_repeat, similarity = is_repetition(
        candidate.id,
        candidate.embedding,
        context.exchange_history,
        threshold=config.similarity_threshold_similar
    )

    if not is_repeat:
        candidates_deduplicated.append(candidate)
    else:
        logger.info(f"Rejected question {candidate.id} (similarity: {similarity:.3f})")

if not candidates_deduplicated:
    logger.warning("All candidates rejected due to repetition")
    # Trigger fallback
    return fallback_selection(context, reason="no_unique_candidates")
```

**Step 6: Select final question**

```python
# Take first candidate (highest relevance from retrieval or random from pool)
selected_question = candidates_deduplicated[0]

# Build snapshot
snapshot = QuestionSnapshot(
    question_id=selected_question.id,
    question_type=selected_question.question_type,
    question_text=selected_question.question_text,
    expected_answer=selected_question.expected_answer,
    difficulty=selected_question.difficulty,
    topic_id=selected_question.topic_id,
    estimated_time_seconds=selected_question.estimated_time_seconds,
    selection_strategy="retrieval" if using_retrieval else "static_pool",
    selection_metadata={
        "candidates_count": len(candidates),
        "after_deduplication": len(candidates_deduplicated),
        "adaptation_reason": reason
    },
    selected_at=datetime.utcnow(),
    rule_version=config.selection_rule_version
)

return SelectionResult(
    question_snapshot=snapshot,
    selection_metadata=metadata,
    adaptation_decision=adaptation_log if adapted else None
)
```

---

## 4. Fallback Strategies

### 4.1 Fallback Hierarchy

**When no candidates match:**

1. Relax difficulty constraint (medium → [easy, medium, hard])
2. Relax topic constraint (remove topic filter)
3. Relax similarity threshold (0.85 → 0.90)
4. Trigger LLM generation
5. Use cached generic question (last resort)

**Implementation:**

```python
def fallback_selection(
    context: SelectionContext,
    reason: str,
    attempt: int = 0
) -> SelectionResult:
    """
    Fallback selection when primary strategy fails.

    Tries progressively relaxed constraints.
    """
    if attempt >= 5:
        # Max fallback attempts reached
        raise NoQuestionAvailableError("Exhausted all fallback strategies")

    logger.warning(f"Fallback attempt {attempt} (reason: {reason})")

    if attempt == 0:
        # Relax difficulty
        return select_with_relaxed_difficulty(context)
    elif attempt == 1:
        # Relax topic
        return select_with_relaxed_topic(context)
    elif attempt == 2:
        # Relax similarity
        return select_with_relaxed_similarity(context)
    elif attempt == 3:
        # Generate via LLM
        return generate_question(context)
    else:
        # Use generic fallback
        return get_generic_fallback_question(context)
```

---

## 5. Adaptation Decision Logging

### 5.1 Audit Record

**Must log every adaptation:**

```python
@dataclass
class AdaptationDecision:
    """Audit record for difficulty adaptation (FR-4.4)."""

    id: Optional[int]
    submission_id: int
    exchange_sequence_order: int

    # Input state
    previous_difficulty: Optional[str]
    previous_score: Optional[float]
    previous_question_id: Optional[int]

    # Adaptation logic
    adaptation_rule: str  # "score_based", "template_default", "section_first"
    threshold_up: Optional[float]
    threshold_down: Optional[float]
    max_difficulty_jump: int

    # Output
    next_difficulty: str
    adaptation_reason: str
    difficulty_changed: bool

    # Audit
    decided_at: datetime
    rule_version: str
```

**Storage:**

```sql
CREATE TABLE difficulty_adaptation_log (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER NOT NULL REFERENCES interview_submissions(id),
    exchange_sequence_order INTEGER NOT NULL,
    previous_difficulty VARCHAR(20),
    previous_score NUMERIC(5, 2),
    adaptation_rule VARCHAR(50) NOT NULL,
    threshold_up NUMERIC(5, 2),
    threshold_down NUMERIC(5, 2),
    next_difficulty VARCHAR(20) NOT NULL,
    adaptation_reason TEXT NOT NULL,
    decided_at TIMESTAMP NOT NULL,
    rule_version VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_adaptation_log_submission ON difficulty_adaptation_log(submission_id);
```

---

## 6. Configuration

```python
from pydantic import BaseModel, Field

class DifficultyAdaptationConfig(BaseModel):
    """Difficulty adaptation configuration."""

    enabled: bool = Field(True, description="Enable adaptive difficulty")
    threshold_up: float = Field(80.0, ge=0.0, le=100.0, description="Score to increase difficulty")
    threshold_down: float = Field(50.0, ge=0.0, le=100.0, description="Score to decrease difficulty")
    max_difficulty_jump: int = Field(1, ge=1, le=2, description="Max difficulty levels to jump")

    # Difficulty ordering
    difficulty_order: list[str] = Field(
        ["easy", "medium", "hard"],
        description="Difficulty progression order"
    )

class RepetitionConfig(BaseModel):
    """Repetition prevention configuration."""

    enable_exact_match_check: bool = Field(True)
    enable_semantic_check: bool = Field(True)

    similarity_threshold_identical: float = Field(0.95, ge=0.0, le=1.0)
    similarity_threshold_similar: float = Field(0.85, ge=0.0, le=1.0)

    # Fallback behavior
    relax_threshold_on_exhaustion: bool = Field(True)
    relaxed_similarity_threshold: float = Field(0.90, ge=0.0, le=1.0)
```

---

## 7. Testing Requirements

### 7.1 Difficulty Adaptation Tests

**Test: Score above threshold → escalate**

```python
def test_difficulty_escalation():
    previous_score = 85.0
    previous_difficulty = "easy"
    config = DifficultyAdaptationConfig(threshold_up=80.0, max_jump=1)

    next_difficulty, reason = adapt_difficulty(previous_difficulty, previous_score, config)

    assert next_difficulty == "medium"
    assert "above_threshold" in reason
```

**Test: Score below threshold → downgrade**

```python
def test_difficulty_downgrade():
    previous_score = 45.0
    previous_difficulty = "hard"
    config = DifficultyAdaptationConfig(threshold_down=50.0, max_jump=1)

    next_difficulty, reason = adapt_difficulty(previous_difficulty, previous_score, config)

    assert next_difficulty == "medium"
    assert "below_threshold" in reason
```

**Test: Already at max → maintain**

```python
def test_difficulty_at_max():
    previous_score = 95.0
    previous_difficulty = "hard"
    config = DifficultyAdaptationConfig(threshold_up=80.0)

    next_difficulty, reason = adapt_difficulty(previous_difficulty, previous_score, config)

    assert next_difficulty == "hard"  # Cannot escalate beyond hard
```

---

### 7.2 Repetition Prevention Tests

**Test: Exact match rejected**

```python
def test_repetition_exact_match():
    candidate_id = 42
    exchange_history = [
        {"question_id": 42, "question_text": "..."},
        {"question_id": 43, "question_text": "..."}
    ]

    is_repeat, similarity = is_repetition(candidate_id, [], exchange_history)

    assert is_repeat == True
    assert similarity == 1.0
```

**Test: Semantically similar rejected**

```python
def test_repetition_semantic_similar():
    candidate_embedding = [0.1, 0.2, 0.3, ...]
    exchange_history = [
        {
            "question_id": 50,
            "question_embedding": [0.11, 0.19, 0.31, ...]  # Very similar
        }
    ]

    is_repeat, similarity = is_repetition(
        candidate_id=999,
        candidate_embedding=candidate_embedding,
        exchange_history=exchange_history,
        threshold=0.85
    )

    assert is_repeat == True
    assert similarity > 0.85
```

**Test: Different enough accepted**

```python
def test_repetition_different_enough():
    candidate_embedding = [0.1, 0.2, 0.3, ...]
    exchange_history = [
        {
            "question_id": 50,
            "question_embedding": [0.8, 0.9, 0.1, ...]  # Very different
        }
    ]

    is_repeat, similarity = is_repetition(
        candidate_id=999,
        candidate_embedding=candidate_embedding,
        exchange_history=exchange_history,
        threshold=0.85
    )

    assert is_repeat == False
    assert similarity < 0.85
```

---

### 7.3 Fallback Strategy Tests

**Test: No matches → relax difficulty**

```python
def test_fallback_relax_difficulty():
    context = SelectionContext(
        current_section="behavioral",
        template_snapshot={"sections": [{"difficulty_range": ["medium"]}]},
        ...
    )

    # Mock: No medium questions available
    with mock_empty_question_pool("medium"):
        result = fallback_selection(context, reason="no_match", attempt=0)

    # Should have relaxed to [easy, medium, hard]
    assert result.selection_metadata["fallback_type"] == "relaxed_difficulty"
```

---

## 8. Critical Risks

1. **Template recalculation:** Selection JOINs to interview_templates at runtime → configuration drift
2. **Adaptation loop:** Bad threshold configuration → difficulty oscillates wildly
3. **Similarity drift:** Embedding model updated → old embeddings incompatible → all questions marked as repeat
4. **Exhausted pool:** Not enough unique questions → infinite fallback loop
5. **Race condition:** Two workers adapt simultaneously → inconsistent difficulty
6. **Tenant leak:** organization_id filter missing → cross-tenant question returned

---

## 9. Acceptance Criteria

**Selection module is complete when:**

✅ Template snapshot drives selection (no runtime config joins)
✅ Difficulty adaptation working (escalate, downgrade, maintain)
✅ Max difficulty jump enforced
✅ Repetition prevention working (exact + semantic)
✅ Multi-tenant filtering enforced
✅ Fallback strategies implemented (relax difficulty, topic, similarity)
✅ Adaptation decisions logged with FR-4.4 compliance
✅ Configuration externalized (thresholds, similarity)
✅ All tests passing (adaptation, repetition, fallback)

---

**End of Question Selection Requirements**
