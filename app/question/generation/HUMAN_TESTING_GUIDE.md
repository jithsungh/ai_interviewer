# Question Generation Module — Human Testing Guide

**Module:** `app/question/generation`  
**Purpose:** LLM-powered question generation with retry, validation, and fallback  
**Status:** ✅ Implemented  
**Ticket:** DEV-37

---

## Overview

The question generation module produces interview questions via LLM with:
- **Prompt rendering** → variable substitution on versioned templates
- **LLM structured output** → JSON-mode call to Groq (or other provider)
- **Post-generation validation** → difficulty match, topic check, substance check, similarity dedup
- **Retry loop** → up to 3 attempts with exponential backoff
- **Fallback** → generic pre-seeded questions from `generic_fallback_questions` table

**Note:** This module is consumed **internally** by `question/selection` and does NOT expose REST API endpoints. Testing is done via Python scripts.

---

## Prerequisites

### 1. Environment Setup

```bash
# From project root
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
export GROQ_API_KEY="gsk_..."                     # Required — only functional provider
export DATABASE_URL="postgresql://postgres:password@localhost/interviewer"
export REDIS_URL="redis://localhost:6379/0"
export QDRANT_URL="http://localhost:6333"
export JWT_SECRET_KEY="test-secret-key-long-enough"
export APP_ENV="dev"
```

### 3. Run Migration

Apply the fallback-questions table migration:

```bash
psql "$DATABASE_URL" -f app/persistence/postgres/migrations/DEV-37_generic-fallback-questions.sql
```

Verify table exists:

```bash
psql "$DATABASE_URL" -c "SELECT count(*) FROM generic_fallback_questions;"
# Expected: 9 (seeded rows)
```

### 4. Ensure Prompt Templates are Seeded

The generation service requires an active `question_generation` prompt template:

```bash
psql "$DATABASE_URL" -c "
  SELECT id, name, version, is_active 
  FROM prompt_templates 
  WHERE prompt_type = 'question_generation' AND is_active = true;
"
```

If no rows are returned, run the seed script:

```bash
psql "$DATABASE_URL" -f app/ai/prompts/seed_prompt_templates.sql
```

---

## Test Scenarios

### Scenario 1: Successful Generation (Happy Path)

**Purpose:** Verify end-to-end LLM question generation.

**Steps:**

1. Create and run `test_manual_generation.py`:

```python
import asyncio
from app.ai.llm import ProviderFactory
from app.ai.prompts.service import PromptService
from app.ai.prompts.repository import SqlPromptTemplateRepository
from app.persistence.postgres import get_db_session, init_postgres
from app.config.settings import settings
from app.question.generation.service import QuestionGenerationService
from app.question.generation.contracts import GenerationRequest, GenerationStatus

async def test_successful_generation():
    # Initialize DB
    init_postgres(settings.database)

    # Build dependencies
    provider = ProviderFactory.create_text_provider("groq")
    session = next(get_db_session())
    prompt_repo = SqlPromptTemplateRepository(session)
    prompt_service = PromptService(prompt_repo)

    svc = QuestionGenerationService(
        llm_provider=provider,
        prompt_service=prompt_service,
        fallback_repo=None,    # No fallback for this test
    )

    request = GenerationRequest(
        submission_id=999,
        organization_id=1,
        difficulty="medium",
        topic="algorithms",
        question_type="technical",
        max_retries=2,
    )

    result = await svc.generate(request)

    print(f"Status:       {result.status}")
    print(f"Question:     {result.question_text}")
    print(f"Answer:       {result.expected_answer[:80]}...")
    print(f"Difficulty:   {result.difficulty}")
    print(f"Topic:        {result.topic}")
    print(f"Source:       {result.source_type}")
    print(f"Attempts:     {result.attempts}")
    print(f"Latency (ms): {result.generation_latency_ms:.1f}")
    print(f"Tokens:       {result.prompt_tokens}p + {result.completion_tokens}c")
    print(f"Cost (USD):   ${result.estimated_cost_usd:.6f}")
    print(f"Prompt hash:  {result.prompt_hash[:16]}...")
    print(f"Model:        {result.llm_model}")

    assert result.status == GenerationStatus.SUCCESS
    assert result.question_text is not None
    assert len(result.question_text) > 20
    print("\n✅ PASSED: Successful generation")

asyncio.run(test_successful_generation())
```

**Expected output:**
- Status: `success`
- Question text: a non-trivial question about algorithms
- Attempts: 1 (usually)
- Source: `generated`

---

### Scenario 2: Fallback Activation

**Purpose:** Verify the fallback path when the LLM is unreachable.

**Steps:**

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.ai.llm.errors import LLMProviderError
from app.ai.prompts.service import PromptService
from app.ai.prompts.repository import SqlPromptTemplateRepository
from app.persistence.postgres import get_db_session, init_postgres
from app.config.settings import settings
from app.question.generation.service import QuestionGenerationService
from app.question.generation.contracts import GenerationRequest, GenerationStatus
from app.question.generation.persistence.fallback_repository import FallbackQuestionRepository

async def test_fallback():
    init_postgres(settings.database)
    session = next(get_db_session())

    # Broken LLM — always throws
    broken_llm = AsyncMock()
    broken_llm.generate_structured = AsyncMock(
        side_effect=LLMProviderError(provider="groq", message="simulated failure")
    )
    broken_llm.get_provider_name = MagicMock(return_value="groq")

    prompt_repo = SqlPromptTemplateRepository(session)
    prompt_service = PromptService(prompt_repo)

    fallback_repo = FallbackQuestionRepository(session)

    svc = QuestionGenerationService(
        llm_provider=broken_llm,
        prompt_service=prompt_service,
        fallback_repo=fallback_repo,
    )

    request = GenerationRequest(
        submission_id=999,
        organization_id=1,
        difficulty="medium",
        topic="algorithms",
        max_retries=1,
    )

    result = await svc.generate(request)

    print(f"Status:      {result.status}")
    print(f"Question:    {result.question_text}")
    print(f"Source:      {result.source_type}")
    print(f"Fallback ID: {result.fallback_question_id}")
    print(f"Reason:      {result.fallback_reason}")
    print(f"Failures:    {result.validation_failures}")

    assert result.status == GenerationStatus.FALLBACK_USED
    assert result.source_type == "fallback_generic"
    assert result.fallback_question_id is not None
    print("\n✅ PASSED: Fallback activated")

asyncio.run(test_fallback())
```

**Expected output:**
- Status: `fallback_used`
- Source: `fallback_generic`
- Fallback ID: a valid integer from the seed data

---

### Scenario 3: Validation Rejection & Retry

**Purpose:** Demonstrate that validation catches difficulty mismatches.

```python
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
from app.ai.llm.contracts import LLMResponse, TelemetryData
from app.ai.prompts.entities import RenderedPrompt
from app.question.generation.service import QuestionGenerationService
from app.question.generation.contracts import GenerationRequest, GenerationStatus

async def test_validation_retry():
    # First call: wrong difficulty → will be rejected
    bad_response = LLMResponse(
        success=True,
        text=json.dumps({
            "question_text": "Explain distributed consensus.",
            "expected_answer": "Raft, Paxos, etc.",
            "difficulty": "hard",       # ← mismatch with requested "easy"
            "topic": "systems",
        }),
        telemetry=TelemetryData(
            model_id="test", provider="groq",
            prompt_tokens=100, completion_tokens=50,
            total_tokens=150, latency_ms=200, success=True,
        ),
    )

    # Second call: correct difficulty → will pass
    good_response = LLMResponse(
        success=True,
        text=json.dumps({
            "question_text": "What is a variable?",
            "expected_answer": "A named storage location.",
            "difficulty": "easy",
            "topic": "basics",
        }),
        telemetry=TelemetryData(
            model_id="test", provider="groq",
            prompt_tokens=100, completion_tokens=50,
            total_tokens=150, latency_ms=200, success=True,
        ),
    )

    llm = AsyncMock()
    llm.generate_structured = AsyncMock(side_effect=[bad_response, good_response])
    llm.get_provider_name = MagicMock(return_value="groq")

    prompt_svc = MagicMock()
    prompt_svc.get_rendered_prompt = MagicMock(return_value=RenderedPrompt(
        text="Generate a question.",
        system_prompt="Interviewer.",
        model_config={"model": "test"},
        version=1,
        prompt_type="question_generation",
    ))

    svc = QuestionGenerationService(llm_provider=llm, prompt_service=prompt_svc)

    request = GenerationRequest(
        submission_id=1,
        organization_id=1,
        difficulty="easy",
        topic="basics",
        max_retries=3,
    )

    result = await svc.generate(request)

    print(f"Status:     {result.status}")
    print(f"Attempts:   {result.attempts}")
    print(f"Failures:   {result.validation_failures}")
    print(f"Question:   {result.question_text}")

    assert result.status == GenerationStatus.SUCCESS
    assert result.attempts == 2
    assert any("difficulty" in f.lower() for f in result.validation_failures)
    print("\n✅ PASSED: Validation retry worked")

asyncio.run(test_validation_retry())
```

---

### Scenario 4: Domain Parsing (Offline, No LLM Needed)

**Purpose:** Test JSON parsing independently.

```python
from app.question.generation.domain.parsing import parse_llm_response, ResponseParseError

# Valid response
output = parse_llm_response('{"question_text": "What is TCP?", "expected_answer": "Protocol.", "difficulty": "easy", "topic": "networking"}')
print(f"Parsed: {output.question_text} (difficulty={output.difficulty})")
assert output.question_text == "What is TCP?"

# Markdown fence stripping
output2 = parse_llm_response('```json\n{"question_text": "X?", "expected_answer": "Y.", "difficulty": "medium", "topic": "z"}\n```')
print(f"Stripped fences: {output2.question_text}")
assert output2.question_text == "X?"

# Invalid input
try:
    parse_llm_response("not json at all")
    assert False, "Should have raised"
except ResponseParseError as e:
    print(f"Correctly rejected: {e}")

print("\n✅ PASSED: Parsing tests")
```

---

### Scenario 5: Domain Validation (Offline, No LLM Needed)

**Purpose:** Test post-generation validation independently.

```python
from app.question.generation.domain.entities import GeneratedQuestionOutput
from app.question.generation.domain.validation import validate_generated_question

output = GeneratedQuestionOutput(
    question_text="Explain the difference between TCP and UDP.",
    expected_answer="TCP is connection-oriented, UDP is connectionless.",
    difficulty="medium",
    topic="networking",
)

# Should pass
result = validate_generated_question(
    output=output,
    requested_difficulty="medium",
    allowed_topics=["networking"],
)
print(f"Passed: {result.passed}, Failures: {result.failures}")
assert result.passed is True

# Difficulty mismatch
result2 = validate_generated_question(
    output=output,
    requested_difficulty="hard",
    allowed_topics=["networking"],
)
print(f"Passed: {result2.passed}, Failures: {result2.failures}")
assert result2.passed is False

print("\n✅ PASSED: Validation tests")
```

---

## Rollback Guide

To undo the migration:

```bash
psql "$DATABASE_URL" -f app/persistence/postgres/migrations/DEV-37_generic-fallback-questions_rollback.sql
```

Verify:

```bash
psql "$DATABASE_URL" -c "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'generic_fallback_questions');"
# Expected: f (false)
```

---

## Running Automated Tests

### Unit Tests (no infrastructure required)

```bash
.venv/bin/python -m pytest tests/unit/question/generation/ -v
```

Expected: **68 tests pass** covering parsing, validation, contracts, and service.

### Integration Tests (requires PostgreSQL)

```bash
.venv/bin/python -m pytest tests/integration/question/generation/ -v -m integration
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `PromptNotFoundError` | No active `question_generation` prompt | Run `seed_prompt_templates.sql` |
| `LLMProviderError` | Bad/missing `GROQ_API_KEY` | Verify API key in environment |
| `relation "generic_fallback_questions" does not exist` | Migration not applied | Run the DEV-37 migration SQL |
| All attempts fail → `NO_FALLBACK` | Fallback repo not injected | Pass `FallbackQuestionRepository(session)` to service |
| `ResponseParseError` | LLM returned non-JSON | Check model supports JSON mode; verify prompt asks for JSON |

---

## Architecture Notes

- **Service is stateless** — safe for concurrent `asyncio.gather()` calls
- **Fallback repo uses sync SQLAlchemy** — standard pattern across the codebase
- **Embedding provider is optional** — similarity dedup gracefully degrades when unavailable
- **No API routes** — this module is consumed by `question/selection`, not exposed as HTTP endpoints
- **Prompt type** — `question_generation` (matches seed in `seed_prompt_templates.sql`)
