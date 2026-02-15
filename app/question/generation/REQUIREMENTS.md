# Question Generation - AI-Powered Question Creation

## 1. Purpose

The **generation** subdirectory handles:

- LLM-based question creation when retrieval fails or template requires dynamic generation
- Structured output enforcement (valid JSON with required fields)
- Post-generation validation (similarity, difficulty, topic checks)
- Source tracking for audit trail
- Fallback to cached generic questions on failure

**Critical responsibility:** Generate valid, non-repetitive questions via LLM with safety checks.

---

## 2. Responsibilities

### 2.1 Structured Output Enforcement

**Challenge:** LLMs can return unstructured text, missing fields, or invalid JSON

**Solution:**

- Request JSON format explicitly
- Use `response_format` (OpenAI) or structured prompts (Claude)
- Parse and validate response
- Retry with stricter instructions if validation fails

**Required output schema:**

```json
{
  "question_text": "string, clear and specific question",
  "expected_answer": "string, key points to cover (not full answer)",
  "difficulty": "string, exactly 'easy', 'medium', or 'hard'",
  "topic": "string, specific topic like 'binary trees'",
  "estimated_time_seconds": "integer, realistic time (60-900)"
}
```

---

### 2.2 Post-Generation Validation

**Must validate:**

1. **Semantic similarity:** Not too similar to previous questions
2. **Difficulty match:** LLM returned requested difficulty
3. **Topic allowed:** Topic is in template's allowed set
4. **Not empty:** Question and answer have substance
5. **Grammar:** (Optional) No obvious errors

**Reject if any check fails.**

---

### 2.3 Source Tracking

**For audit trail:**

- Mark `source_type = 'generated'` in question metadata
- Store generation metadata:
  - `prompt_hash`: SHA256 of prompt (deduplication)
  - `llm_model`: Model identifier
  - `llm_temperature`: Creativity setting
  - `generated_at`: Timestamp
  - `validation_passed`: Boolean
  - `validation_failures`: List of failed checks
  - `candidate_profile_used`: Boolean (personalization flag)

---

### 2.4 Fallback Strategy

**If generation fails after max retries:**

1. Load cached generic fallback question
2. Match by difficulty + topic
3. Return fallback with `source_type = 'fallback_generic'`
4. Log failure reason for debugging

---

## 3. Generation Workflow

### 3.1 High-Level Process

```
generate_question(submission_id, difficulty, topic, context)
├── 1. Validate inputs (submission exists, difficulty valid, topic allowed)
├── 2. Assemble prompt (call prompting module)
├── 3. Call LLM provider (OpenAI or Anthropic)
│   ├── Request structured JSON
│   ├── Timeout: 5 seconds (NFR-2)
│   ├── Retry with exponential backoff (rate limits, server errors)
│   └── Max 3 retries
├── 4. Parse & validate response
│   ├── JSON parse (raises JSONDecodeError if invalid)
│   └── Validate required fields (raises ValidationError if missing)
├── 5. Post-generation checks
│   ├── Semantic similarity (reject if too similar to history)
│   ├── Difficulty match (reject if doesn't match request)
│   ├── Topic check (reject if not in allowed set)
│   └── Not empty check (reject if vague)
├── 6. Store metadata (even if failed for analysis)
├── 7. Return QuestionSnapshot (if passed)
└── 8. Fallback to generic (if all retries exhausted)
```

---

### 3.2 Implementation

```python
def generate_question(
    submission_id: int,
    difficulty: str,
    topic: str,
    resume_text: Optional[str],
    job_description: Optional[str],
    previous_exchanges: list[dict],
    template_instructions: str,
    max_retries: int = 3
) -> QuestionSnapshot:
    """
    Generate interview question using LLM.

    Returns: QuestionSnapshot with generated question
    Raises: GenerationError if all retries fail and no fallback available
    """
    # Step 1: Validate inputs
    validate_generation_inputs(submission_id, difficulty, topic)

    # Step 2: Assemble prompt
    prompt_result = assemble_generation_prompt(
        submission_id=submission_id,
        difficulty=difficulty,
        topic=topic,
        resume_text=resume_text,
        job_description=job_description,
        previous_exchanges=previous_exchanges,
        template_instructions=template_instructions
    )

    # Step 3: Call LLM with retries
    for attempt in range(max_retries):
        try:
            # Call LLM
            llm_response = call_llm_provider(
                system_prompt=prompt_result.system_prompt,
                user_prompt=prompt_result.user_prompt,
                model=config.llm_model,
                temperature=config.llm_temperature,
                max_tokens=config.llm_max_tokens_output,
                timeout=config.generation_timeout_seconds
            )

            # Step 4: Parse & validate
            question_output = parse_and_validate_response(llm_response)

            # Step 5: Post-generation checks
            validation_result = validate_generated_question(
                question_output=question_output,
                requested_difficulty=difficulty,
                allowed_topics=[topic],
                previous_exchanges=previous_exchanges
            )

            if validation_result.passed:
                # Step 6: Store metadata
                metadata = build_generation_metadata(
                    prompt_result=prompt_result,
                    llm_response=llm_response,
                    validation_result=validation_result
                )

                # Step 7: Build snapshot
                snapshot = build_question_snapshot(
                    question_output=question_output,
                    metadata=metadata,
                    source_type="generated"
                )

                logger.info(f"Generated question for submission {submission_id}")
                return snapshot
            else:
                # Validation failed, retry with stricter prompt
                logger.warning(f"Validation failed: {validation_result.failures}")
                if attempt < max_retries - 1:
                    prompt_result = make_prompt_stricter(prompt_result, validation_result.failures)
                    continue

        except (TimeoutError, RateLimitError, LLMError) as e:
            logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                sleep_time = exponential_backoff(attempt)
                time.sleep(sleep_time)
                continue
            else:
                # Max retries exhausted
                logger.error(f"Generation failed after {max_retries} attempts")

    # Step 8: Fallback to generic
    if config.enable_fallback_to_generic:
        fallback = load_generic_fallback_question(difficulty, topic)
        if fallback:
            logger.info(f"Using fallback generic question for {difficulty} {topic}")
            return fallback

    # No fallback available
    raise GenerationError(f"Failed to generate question after {max_retries} attempts")
```

---

## 4. LLM Provider Integration

### 4.1 OpenAI Integration

**Structured output via `response_format`:**

```python
def call_openai_provider(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 500,
    timeout: int = 5
) -> str:
    """
    Call OpenAI API with structured JSON output.

    Returns: JSON string from LLM
    """
    import openai

    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},  # Forces JSON
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        )

        return response.choices[0].message.content

    except openai.Timeout:
        raise TimeoutError(f"OpenAI request timed out after {timeout}s")
    except openai.RateLimitError:
        raise RateLimitError("OpenAI rate limit exceeded")
    except openai.APIError as e:
        raise LLMError(f"OpenAI API error: {e}")
```

---

### 4.2 Anthropic (Claude) Integration

**Structured output via prompt design:**

```python
def call_anthropic_provider(
    system_prompt: str,
    user_prompt: str,
    model: str = "claude-3-opus-20240229",
    temperature: float = 0.7,
    max_tokens: int = 500,
    timeout: int = 5
) -> str:
    """
    Call Anthropic API with JSON output guidance.

    Claude doesn't have response_format, so we guide via prompt.
    """
    import anthropic

    # Force JSON start by beginning the Assistant's response
    full_prompt = f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant: {{"

    try:
        client = anthropic.Client(api_key=config.anthropic_api_key)

        response = client.completions.create(
            model=model,
            prompt=full_prompt,
            stop_sequences=["}"],  # Stop after closing brace
            max_tokens_to_sample=max_tokens,
            temperature=temperature,
            timeout=timeout
        )

        # Reconstruct JSON
        json_str = "{" + response.completion + "}"
        return json_str

    except anthropic.APITimeoutError:
        raise TimeoutError(f"Anthropic request timed out after {timeout}s")
    except anthropic.RateLimitError:
        raise RateLimitError("Anthropic rate limit exceeded")
    except anthropic.APIError as e:
        raise LLMError(f"Anthropic API error: {e}")
```

---

## 5. Response Parsing & Validation

### 5.1 JSON Parsing

```python
def parse_and_validate_response(llm_response: str) -> QuestionOutput:
    """
    Parse LLM response as JSON and validate required fields.

    Raises: ValidationError if invalid
    """
    # Parse JSON
    try:
        data = json.loads(llm_response)
    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON: {e}")

    # Validate required fields
    required_fields = [
        "question_text",
        "expected_answer",
        "difficulty",
        "topic",
        "estimated_time_seconds"
    ]

    missing = [f for f in required_fields if f not in data]
    if missing:
        raise ValidationError(f"Missing fields: {missing}")

    # Validate field types
    if not isinstance(data["question_text"], str):
        raise ValidationError("question_text must be string")

    if not isinstance(data["expected_answer"], str):
        raise ValidationError("expected_answer must be string")

    if data["difficulty"] not in ["easy", "medium", "hard"]:
        raise ValidationError(f"difficulty must be easy/medium/hard, got {data['difficulty']}")

    if not isinstance(data["topic"], str):
        raise ValidationError("topic must be string")

    if not isinstance(data["estimated_time_seconds"], int):
        raise ValidationError("estimated_time_seconds must be integer")

    # Build QuestionOutput
    return QuestionOutput(
        question_text=data["question_text"],
        expected_answer=data["expected_answer"],
        difficulty=data["difficulty"],
        topic=data["topic"],
        estimated_time_seconds=data["estimated_time_seconds"]
    )
```

---

## 6. Post-Generation Validation

### 6.1 Semantic Similarity Check

**Purpose:** Ensure generated question is different from previous questions

**Algorithm:**

1. Generate embedding for generated question
2. Compute cosine similarity with all previous question embeddings
3. Reject if any similarity > threshold (0.85)

**Implementation:**

```python
def check_semantic_similarity(
    question_text: str,
    previous_exchanges: list[dict],
    threshold: float = 0.85
) -> tuple[bool, float]:
    """
    Check if generated question is too similar to previous questions.

    Returns: (is_acceptable, max_similarity)
    """
    # Generate embedding for new question
    new_embedding = generate_embedding(question_text)

    if not previous_exchanges:
        return (True, 0.0)

    # Compare with previous embeddings
    similarities = []
    for exchange in previous_exchanges:
        if "question_embedding" not in exchange:
            continue

        prev_embedding = exchange["question_embedding"]
        similarity = cosine_similarity(new_embedding, prev_embedding)
        similarities.append(similarity)

    max_similarity = max(similarities) if similarities else 0.0

    return (max_similarity < threshold, max_similarity)
```

---

### 6.2 Difficulty Match Check

**Purpose:** Ensure LLM returned requested difficulty

```python
def check_difficulty_match(
    generated_difficulty: str,
    requested_difficulty: str
) -> bool:
    """
    Check if generated difficulty matches requested.
    """
    return generated_difficulty.lower() == requested_difficulty.lower()
```

---

### 6.3 Topic Validation

**Purpose:** Ensure topic is in allowed set

```python
def check_topic_allowed(
    generated_topic: str,
    allowed_topics: list[str]
) -> bool:
    """
    Check if generated topic is in allowed set.

    Uses case-insensitive comparison.
    """
    return generated_topic.lower() in [t.lower() for t in allowed_topics]
```

---

### 6.4 Not Empty Check

**Purpose:** Reject vague or too-short questions

```python
def check_not_empty(
    question_text: str,
    expected_answer: str
) -> tuple[bool, str]:
    """
    Check if question and answer have substance.

    Returns: (is_valid, reason)
    """
    if len(question_text) < 20:
        return (False, "question_text too short (<20 chars)")

    if len(expected_answer) < 10:
        return (False, "expected_answer too short (<10 chars)")

    # Check for vague patterns
    vague_patterns = ["something", "anything", "whatever"]
    if any(p in question_text.lower() for p in vague_patterns):
        return (False, "question_text contains vague terms")

    return (True, "")
```

---

### 6.5 Combined Validation

```python
@dataclass
class ValidationResult:
    passed: bool
    failures: list[str]
    similarity_score: float
    difficulty_match: bool
    topic_allowed: bool
    not_empty: bool


def validate_generated_question(
    question_output: QuestionOutput,
    requested_difficulty: str,
    allowed_topics: list[str],
    previous_exchanges: list[dict]
) -> ValidationResult:
    """
    Run all post-generation validation checks.
    """
    failures = []

    # Similarity check
    is_acceptable, similarity_score = check_semantic_similarity(
        question_output.question_text,
        previous_exchanges
    )
    if not is_acceptable:
        failures.append(f"too_similar (similarity={similarity_score:.2f})")

    # Difficulty check
    difficulty_match = check_difficulty_match(
        question_output.difficulty,
        requested_difficulty
    )
    if not difficulty_match:
        failures.append(f"difficulty_mismatch (got {question_output.difficulty}, expected {requested_difficulty})")

    # Topic check
    topic_allowed = check_topic_allowed(
        question_output.topic,
        allowed_topics
    )
    if not topic_allowed:
        failures.append(f"topic_not_allowed (got {question_output.topic})")

    # Not empty check
    not_empty, reason = check_not_empty(
        question_output.question_text,
        question_output.expected_answer
    )
    if not not_empty:
        failures.append(f"empty_or_vague ({reason})")

    return ValidationResult(
        passed=(len(failures) == 0),
        failures=failures,
        similarity_score=similarity_score,
        difficulty_match=difficulty_match,
        topic_allowed=topic_allowed,
        not_empty=not_empty
    )
```

---

## 7. Source Tracking & Metadata

### 7.1 Generation Metadata

**Stored in `question_snapshot` JSONB or separate table:**

```python
@dataclass
class GenerationMetadata:
    source_type: str = "generated"
    prompt_hash: str  # SHA256(system_prompt + user_prompt)
    llm_model: str
    llm_temperature: float
    llm_max_tokens: int
    generated_at: datetime
    validation_passed: bool
    validation_failures: list[str]
    similarity_scores: dict  # {previous_question_id: score}
    candidate_profile_hash: Optional[str]  # SHA256(resume + JD)
    prompt_version: str
    estimated_cost_usd: float
```

**Implementation:**

```python
import hashlib

def build_generation_metadata(
    prompt_result: PromptAssemblyResult,
    llm_response: str,
    validation_result: ValidationResult
) -> GenerationMetadata:
    """
    Build metadata for generated question.
    """
    # Hash prompt for deduplication
    prompt_text = prompt_result.system_prompt + prompt_result.user_prompt
    prompt_hash = hashlib.sha256(prompt_text.encode()).hexdigest()

    # Estimate cost
    prompt_tokens = prompt_result.metadata["total_tokens"]
    completion_tokens = estimate_token_count(llm_response)
    estimated_cost = calculate_cost(
        model=config.llm_model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens
    )

    return GenerationMetadata(
        source_type="generated",
        prompt_hash=prompt_hash,
        llm_model=config.llm_model,
        llm_temperature=config.llm_temperature,
        llm_max_tokens=config.llm_max_tokens_output,
        generated_at=datetime.utcnow(),
        validation_passed=validation_result.passed,
        validation_failures=validation_result.failures,
        similarity_scores={},  # Populated by validation
        candidate_profile_hash=None,  # Optional
        prompt_version=prompt_result.metadata["prompt_template_version"],
        estimated_cost_usd=estimated_cost
    )
```

---

## 8. Fallback to Generic Questions

### 8.1 Generic Fallback Questions Table

**Table: generic_fallback_questions**

```sql
CREATE TABLE generic_fallback_questions (
    id SERIAL PRIMARY KEY,
    question_type VARCHAR(50) NOT NULL,  -- 'behavioral', 'technical', etc.
    difficulty VARCHAR(20) NOT NULL,     -- 'easy', 'medium', 'hard'
    topic VARCHAR(100) NOT NULL,         -- 'communication', 'algorithms', etc.
    question_text TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    estimated_time_seconds INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    usage_count INTEGER DEFAULT 0,       -- Track how often used
    metadata JSONB
);

CREATE INDEX idx_generic_fallback_difficulty_topic ON generic_fallback_questions(difficulty, topic, is_active);
```

---

### 8.2 Loading Fallback

```python
def load_generic_fallback_question(
    difficulty: str,
    topic: str
) -> Optional[QuestionSnapshot]:
    """
    Load cached generic fallback question.

    Returns: QuestionSnapshot or None if no fallback available
    """
    # Query for matching fallback
    fallback = db.query(GenericFallbackQuestion).filter(
        GenericFallbackQuestion.difficulty == difficulty,
        GenericFallbackQuestion.topic == topic,
        GenericFallbackQuestion.is_active == True
    ).order_by(
        GenericFallbackQuestion.usage_count.asc()  # Use least-used
    ).first()

    if not fallback:
        # Try broader match (any topic)
        fallback = db.query(GenericFallbackQuestion).filter(
            GenericFallbackQuestion.difficulty == difficulty,
            GenericFallbackQuestion.is_active == True
        ).order_by(
            GenericFallbackQuestion.usage_count.asc()
        ).first()

    if not fallback:
        return None

    # Increment usage count
    fallback.usage_count += 1
    db.commit()

    # Build snapshot
    return QuestionSnapshot(
        question_id=fallback.id,
        question_text=fallback.question_text,
        expected_answer=fallback.expected_answer,
        difficulty=fallback.difficulty,
        topic=fallback.topic,
        estimated_time_seconds=fallback.estimated_time_seconds,
        source_type="fallback_generic",
        metadata={"fallback_id": fallback.id}
    )
```

---

## 9. Cost Tracking

### 9.1 Cost Calculation

**OpenAI pricing (as of 2024):**

- GPT-4: $0.03 per 1K prompt tokens, $0.06 per 1K completion tokens
- GPT-4-32k: $0.06 per 1K prompt, $0.12 per 1K completion
- GPT-3.5-turbo: $0.0015 per 1K prompt, $0.002 per 1K completion

**Implementation:**

```python
PRICING = {
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-32k": {"prompt": 0.06, "completion": 0.12},
    "gpt-3.5-turbo": {"prompt": 0.0015, "completion": 0.002}
}

def calculate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int
) -> float:
    """
    Calculate estimated cost for LLM generation.

    Returns: Cost in USD
    """
    pricing = PRICING.get(model, PRICING["gpt-4"])

    prompt_cost = (prompt_tokens / 1000) * pricing["prompt"]
    completion_cost = (completion_tokens / 1000) * pricing["completion"]

    return prompt_cost + completion_cost
```

---

### 9.2 Cost Logging

**Table: generation_cost_log**

```sql
CREATE TABLE generation_cost_log (
    id SERIAL PRIMARY KEY,
    submission_id INTEGER REFERENCES interview_submissions(id),
    organization_id INTEGER NOT NULL,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    llm_model VARCHAR(50) NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    estimated_cost_usd NUMERIC(10, 6) NOT NULL
);

CREATE INDEX idx_generation_cost_org_date ON generation_cost_log(organization_id, generated_at);
```

**Implementation:**

```python
def log_generation_cost(
    submission_id: int,
    organization_id: int,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost: float
):
    """
    Log generation cost for billing and analytics.
    """
    cost_log = GenerationCostLog(
        submission_id=submission_id,
        organization_id=organization_id,
        generated_at=datetime.utcnow(),
        llm_model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated_cost
    )

    db.add(cost_log)
    db.commit()
```

---

## 10. Configuration

### 10.1 GenerationConfig

```python
@dataclass
class GenerationConfig:
    llm_provider: str = "openai"  # or 'anthropic'
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.7
    llm_max_tokens_output: int = 500
    generation_timeout_seconds: int = 5  # NFR-2
    max_retries: int = 3
    enable_post_generation_validation: bool = True
    similarity_threshold: float = 0.85
    enable_fallback_to_generic: bool = True
    generic_question_pool_size: int = 50
    enable_cost_tracking: bool = True
    cost_alert_threshold_usd: float = 1000  # Monthly per org
```

---

## 11. Observability

### 11.1 Metrics

**Must expose:**

- `question_generation_total` (counter with labels: model, success) - Total generations
- `question_generation_duration_seconds` (histogram with label: model) - Latency
- `question_generation_validation_failures_total` (counter with label: reason) - Failed validations
- `question_generation_cost_usd_total` (counter with label: organization_id) - Cumulative cost
- `question_generation_fallback_total` (counter) - Fallback uses

---

### 11.2 Logging

**Must log (INFO level):**

- Generation initiated (submission_id, difficulty, topic, model)
- Generation succeeded (submission_id, validation_passed, cost_usd)
- Fallback used (submission_id, reason, fallback_id)

**Must log (WARN level):**

- Validation failed (submission_id, failures, similarity_score)
- Retry triggered (submission_id, attempt, reason)
- LLM timeout (submission_id, timeout_seconds)

**Must log (ERROR level):**

- Generation failed after max retries (submission_id, last_error)
- No fallback available (submission_id, difficulty, topic)
- Cost threshold exceeded (organization_id, monthly_cost_usd, threshold)

---

## 12. Testing Requirements

### 12.1 Generation Tests

**Test: Valid generation succeeds**

```python
def test_valid_generation():
    with mock_llm_response(valid_json_response):
        snapshot = generate_question(
            submission_id=1,
            difficulty="medium",
            topic="algorithms",
            resume_text="Python developer...",
            job_description="Backend role...",
            previous_exchanges=[],
            template_instructions="Generate technical question"
        )

        assert snapshot.source_type == "generated"
        assert snapshot.difficulty == "medium"
        assert "algorithms" in snapshot.topic.lower()
```

**Test: Missing field rejected**

```python
def test_missing_field_rejected():
    invalid_json = '{"question_text": "What is sorting?", "difficulty": "medium"}'

    with mock_llm_response(invalid_json):
        with pytest.raises(ValidationError):
            generate_question(...)
```

**Test: Wrong difficulty rejected and retried**

```python
def test_wrong_difficulty_retry():
    # First attempt: returns "hard" when "medium" requested
    # Second attempt: returns "medium" correctly

    with mock_llm_responses([
        '{"difficulty": "hard", ...}',
        '{"difficulty": "medium", ...}'
    ]):
        snapshot = generate_question(difficulty="medium", ...)

        assert snapshot.difficulty == "medium"
```

---

### 12.2 Similarity Tests

**Test: Similar question rejected**

```python
def test_similar_question_rejected():
    previous_exchanges = [{
        "question_text": "Explain quicksort algorithm",
        "question_embedding": [0.1, 0.2, 0.3, ...]
    }]

    # LLM generates very similar question
    generated = "Describe the quicksort algorithm"

    with mock_embedding_similarity(0.92):  # > threshold 0.85
        with pytest.raises(ValidationError):
            generate_question(previous_exchanges=previous_exchanges, ...)
```

---

### 12.3 Fallback Tests

**Test: Fallback used after max retries**

```python
def test_fallback_on_failure():
    # Mock LLM failures
    with mock_llm_errors(count=3):
        snapshot = generate_question(
            difficulty="medium",
            topic="communication",
            ...
        )

        assert snapshot.source_type == "fallback_generic"
        assert snapshot.difficulty == "medium"
```

**Test: Error raised if no fallback available**

```python
def test_no_fallback_error():
    # No generic questions in DB
    with empty_fallback_pool():
        with mock_llm_errors(count=3):
            with pytest.raises(GenerationError):
                generate_question(...)
```

---

## 13. Critical Risks

1. **Hallucination:** LLM generates factually incorrect expected_answer → candidate confused
2. **Bias:** LLM generates biased question → discrimination lawsuit
3. **Difficulty mismatch:** LLM ignores difficulty consistently → adaptation breaks
4. **Infinite retry loop:** Validation always fails → infinite regeneration → stack overflow
5. **Cost explosion:** Generation used excessively → high OpenAI bills
6. **Prompt leakage:** LLM response includes prompt text → exposes instructions

---

## 14. Acceptance Criteria

**Generation module is complete when:**

✅ OpenAI integration working (structured JSON via response_format)
✅ Anthropic integration working (structured JSON via prompt design)
✅ Response parsing working (JSON parsed, required fields validated)
✅ Post-generation validation working (similarity, difficulty, topic, not empty)
✅ Source tracking working (generation metadata stored)
✅ Fallback to generic working (cached questions loaded on failure)
✅ Cost tracking working (token usage logged, cost calculated)
✅ Retry logic working (exponential backoff, max retries)
✅ Metrics exposed (generation rate, validation failures, cost)
✅ All tests passing (valid generation, validation, fallback, cost)

---

**End of Question Generation Requirements**
