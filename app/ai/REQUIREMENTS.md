# AI Module Requirements

## 1. Purpose

The AI module provides a **provider-agnostic abstraction layer** for all Large Language Model and AI-based operations.

**Core Responsibilities:**

- Provider abstraction (Groq, Gemini, OpenAI, Anthropic)
- Structured output enforcement with JSON schema validation
- Timeout, retry, and fallback strategies
- Token usage and latency tracking
- Deterministic mode support for evaluation
- Prompt template management with versioning

**Strict Domain Isolation:** This module is **infrastructure-only** and MUST remain completely ignorant of:

- Interview lifecycle (submissions, sessions, exchanges)
- Domain entities (templates, rubrics, evaluations)
- Business logic (scoring aggregation, template resolution)
- Runtime state (interview orchestration)

**Design Philosophy:** Pure AI driver layer that receives structured input, calls provider, returns structured output, records telemetry. Nothing more.

---

## 2. Owned Tables

### Primary Ownership

**None** - AI module is infrastructure-only and does not own business tables.

### Read-Only Access

- `prompt_templates` - Versioned prompt definitions with scope and model binding
  - Used for prompt retrieval and rendering
  - Scope resolution: organization-scoped → global fallback
  - Active flag enforcement (one active version per prompt_type per scope)

### Write Access (Metadata Only)

- JSON fields in consuming modules (write telemetry):
  - `interview_exchanges.content_metadata` - Token usage, latency for questions/responses
  - `evaluations.metadata` - Token usage, model_id for AI scoring
  - `audit_logs` - AI operation tracking

**Critical:** AI module does NOT directly write to these tables. It returns telemetry data to calling modules who persist it.

---

## 3. Input Constraints

### Provider Configuration

- Provider type (required): `openai` | `anthropic` | `local` | `embedding` | `speech`
- Model ID (optional, defaults from prompt_template or config)
- API credentials from environment/vault (never hardcoded)
- Organization ID for model override resolution

### Request Parameters

- **Prompt Type** (required): `question_generation` | `evaluation` | `resume_parsing` | `jd_parsing` | `report_generation`
- **Input Data** (required): Structured dict/object with use-case specific fields
- **Options** (optional):
  - `temperature` (float, 0.0-2.0, default varies by use case)
  - `max_tokens` (int, >0)
  - `timeout_seconds` (int, 10-300, default 60)
  - `retry_attempts` (int, 0-5, default 3)
  - `deterministic` (bool, sets temperature=0, top_p=1)
  - `schema` (JSON schema dict for structured output)

### Use Case: Question Generation

```python
{
  "role": str,
  "topics": [str],
  "difficulty": "easy|medium|hard",
  "resume_context": Optional[str],
  "jd_context": Optional[str],
  "previous_questions": Optional[List[str]]
}
```

### Use Case: Evaluation

```python
{
  "question_text": str,
  "candidate_response": str,
  "rubric_dimensions": [
    {
      "name": str,
      "criteria": str,
      "max_score": float
    }
  ],
  "evaluation_instructions": str
}
```

### Use Case: Resume Parsing

```python
{
  "resume_text": str,
  "schema": Optional[dict]  # Expected structure
}
```

### Use Case: Job Description Parsing

```python
{
  "jd_text": str,
  "schema": Optional[dict]
}
```

### Use Case: Report Generation

```python
{
  "evaluation_summary": dict,
  "strengths": [str],
  "weaknesses": [str],
  "proctoring_risk_level": str
}
```

### Validation Rules

- Prompt type MUST exist in `prompt_templates` (active version)
- Input data MUST contain all required fields for prompt_type
- Temperature MUST be in range [0.0, 2.0]
- Max tokens MUST be positive and within provider limits
- Timeout MUST be reasonable (10-300 seconds)
- Schema (if provided) MUST be valid JSON schema

---

## 4. Output Guarantees

### Success Response Structure

```python
AIResponse(
  success=True,
  data=dict,              # Structured output matching schema
  telemetry=TelemetryData(
    model_id=str,
    provider=str,
    prompt_tokens=int,
    completion_tokens=int,
    total_tokens=int,
    latency_ms=int,
    retry_count=int,
    timestamp=datetime
  ),
  metadata={
    "prompt_version": int,
    "deterministic": bool,
    "temperature": float
  }
)
```

### Failure Response Structure

```python
AIResponse(
  success=False,
  error=AIError(
    type="timeout|rate_limit|schema_validation|provider_error|unknown",
    message=str,
    retryable=bool,
    provider_error_code=Optional[str]
  ),
  telemetry=TelemetryData(...)  # Partial telemetry even on failure
)
```

### Structured Output Validation

For high-impact operations (evaluation, parsing), output MUST:

- Match provided JSON schema exactly
- Include all required fields
- Pass type validation
- Trigger retry if validation fails (up to max retries)
- Raise `SchemaValidationError` if all retries exhausted

### Performance Guarantees

- **Question Generation:** <5s p95 latency
- **Evaluation:** <10s p95 latency (deterministic mode)
- **Resume Parsing:** <8s p95 latency
- **JD Parsing:** <6s p95 latency
- **Report Generation:** <12s p95 latency

### Idempotency

- Same input + deterministic mode = same output (within model variance)
- Non-deterministic calls may vary (expected behavior)
- Retry logic preserves idempotency semantics

---

## 5. Invariants

### Provider Abstraction Invariant

```
All providers MUST implement the same interface contract
No provider-specific logic may leak into domain modules
```

**Enforcement:** Provider selection happens in AI module only; calling modules reference abstract interface.

### Schema Validation Invariant

```
IF prompt_type IN {evaluation, resume_parsing, jd_parsing}
THEN output MUST be schema-validated before returning
```

**Enforcement:** Schema validation middleware wraps provider calls.

### Telemetry Collection Invariant

```
EVERY AI operation MUST record:
- Token usage (prompt + completion)
- Latency (wall time)
- Model ID
- Retry attempts
EVEN ON FAILURE
```

**Enforcement:** Telemetry collected in try/finally block.

### Timeout Invariant

```
EVERY provider call MUST have explicit timeout
Default timeout if not specified: 60 seconds
```

**Enforcement:** Timeout wrapper around all provider SDK calls.

### Deterministic Mode Invariant

```
IF deterministic=True
THEN temperature=0, top_p=1, seed=fixed (if supported)
```

**Enforcement:** Deterministic mode overrides user-provided temperature/top_p.

---

## 6. Forbidden Behaviors

### Domain Knowledge Violations

- SHALL NOT import modules: `interview`, `evaluation`, `admin`, `coding`, `question`
- SHALL NOT reference domain entities: `InterviewSubmission`, `InterviewExchange`, `Evaluation`, `Template`, `Rubric`
- SHALL NOT perform business logic: score aggregation, template resolution, rubric weighting
- SHALL NOT access domain tables directly (only `prompt_templates` via repository)
- SHALL NOT construct interview state or orchestration logic

### Data Mutation Violations

- SHALL NOT write to business tables (submissions, evaluations, exchanges)
- SHALL NOT modify runtime state outside telemetry recording
- SHALL NOT cache AI responses in database (caching is infrastructure concern only)

### Provider Coupling Violations

- SHALL NOT hardcode provider API keys (use environment/vault)
- SHALL NOT expose provider-specific errors to calling modules (wrap in AIError)
- SHALL NOT allow provider-specific parameters to leak into public API
- SHALL NOT assume single provider (design for multi-provider from day 1)

### Security Violations

- SHALL NOT log sensitive content (PII, API keys, full prompts)
- SHALL NOT store API credentials in code or config files
- SHALL NOT bypass rate limiting or quota enforcement
- SHALL NOT allow prompt injection without sanitization

### Schema Violations

- SHALL NOT return unvalidated output for critical operations
- SHALL NOT silently fallback to unstructured output on schema failure
- SHALL NOT accept malformed JSON schemas

---

## 7. Dependent Modules

### Dependencies (Inbound)

- `ai/llm` - Provider abstraction and execution
- `ai/prompts` - Prompt template retrieval and rendering
- `ai/telemetry` - Token tracking and observability
- `shared/errors` - Custom exception types (AIError, TimeoutError, SchemaValidationError)
- `shared/observability` - Logging and tracing
- `persistence/postgres` - Repository for `prompt_templates` (read-only)

### Dependents (Outbound)

- `question/generation` - Question generation AI calls
- `evaluation/scoring` - AI-assisted evaluation scoring
- `interview/resume_parser` - Resume parsing
- `interview/jd_parser` - Job description parsing
- `evaluation/report` - Report and feedback generation

### External Systems

- **Groq API** - Fast LLM provider (primary for development)
- **Gemini API** - Google's LLM provider (primary for development)
- **OpenAI API** - Primary LLM provider (production)
- **Anthropic API** - Alternative/fallback LLM provider (production)
- **Embedding Service** - Vector embedding generation (Qdrant or provider-specific)
- **Speech-to-Text API** - Audio transcription (if audio interviews enabled)
- **Secrets Manager** - API credential storage (Vault, AWS Secrets Manager)

---

## 8. Event Contracts Emitted

### Telemetry Events (Metrics System)

```json
{
  "event": "ai.llm.request.completed",
  "prompt_type": "evaluation",
  "model_id": "gpt-4",
  "provider": "openai",
  "tokens": {
    "prompt": 1250,
    "completion": 380,
    "total": 1630
  },
  "latency_ms": 3420,
  "retry_count": 0,
  "deterministic": true,
  "timestamp": "2026-02-13T10:30:00Z"
}
```

```json
{
  "event": "ai.llm.request.failed",
  "prompt_type": "question_generation",
  "error_type": "timeout",
  "retry_count": 3,
  "latency_ms": 60000,
  "timestamp": "2026-02-13T10:35:00Z"
}
```

```json
{
  "event": "ai.schema_validation.failed",
  "prompt_type": "resume_parsing",
  "model_id": "gpt-4",
  "validation_errors": [
    "missing_field: skills",
    "invalid_type: experience_years"
  ],
  "retry_attempt": 2,
  "timestamp": "2026-02-13T10:40:00Z"
}
```

### Audit Events (Audit Logs)

```json
{
  "event": "ai.prompt.rendered",
  "prompt_type": "evaluation",
  "prompt_version": 3,
  "organization_id": 45,
  "scope": "global",
  "timestamp": "2026-02-13T10:30:00Z"
}
```

### Cost Tracking Events

```json
{
  "event": "ai.cost.accrued",
  "organization_id": 45,
  "model_id": "gpt-4",
  "tokens": 1630,
  "estimated_cost_usd": 0.0489,
  "timestamp": "2026-02-13T10:30:00Z"
}
```

---

## 9. Acceptance Criteria

### Provider Abstraction (Infrastructure Goal)

- [ ] Groq provider implements full interface contract
- [ ] Gemini provider implements full interface contract
- [ ] OpenAI provider implements full interface contract
- [ ] Anthropic provider implements full interface contract
- [ ] Switching provider requires zero changes in calling modules
- [ ] Provider selection configurable per organization
- [ ] Fallback provider triggers on primary failure

### Structured Output Enforcement (Critical Path)

- [ ] Evaluation responses validated against schema
- [ ] Resume parsing validated against schema
- [ ] JD parsing validated against schema
- [ ] Schema validation failure triggers retry
- [ ] After max retries, raises SchemaValidationError
- [ ] Question generation optionally supports structured output

### Timeout & Retry (Reliability)

- [ ] All provider calls have explicit timeout
- [ ] Timeout exceeded raises TimeoutError (retryable)
- [ ] Retry with exponential backoff (1s, 2s, 4s)
- [ ] Retryable errors: timeout, rate_limit, transient provider errors
- [ ] Non-retryable errors: schema validation after max retries, authentication failure
- [ ] Circuit breaker opens after 5 consecutive failures (30s cooldown)

### Deterministic Mode (Evaluation Integrity)

- [ ] Evaluation calls use deterministic=True by default
- [ ] Deterministic mode sets temperature=0, top_p=1
- [ ] Seed parameter used if provider supports
- [ ] Same input produces same output (within model variance)

### Prompt Versioning (Admin Feature)

- [ ] Prompt retrieved from `prompt_templates` table
- [ ] Organization-scoped prompt preferred over global
- [ ] Only active version returned
- [ ] Prompt version recorded in telemetry
- [ ] Variable interpolation works correctly

### Telemetry Recording (Observability)

- [ ] Token usage recorded for every request (success or failure)
- [ ] Latency measured end-to-end
- [ ] Model ID captured in metadata
- [ ] Retry count tracked
- [ ] Telemetry returned to calling module for persistence

### Use Case: Question Generation

- [ ] Accepts role, topics, difficulty, context
- [ ] Returns structured question with difficulty tag
- [ ] Optionally returns followup suggestions
- [ ] Respects topic constraints
- [ ] Latency <5s p95

### Use Case: Evaluation

- [ ] Accepts question, response, rubric dimensions
- [ ] Returns dimension scores with justifications
- [ ] Schema validated (required fields: dimension_name, score, justification)
- [ ] Does NOT aggregate final score (domain concern)
- [ ] Latency <10s p95

### Use Case: Resume Parsing

- [ ] Accepts raw resume text
- [ ] Returns structured skills, experience, education
- [ ] Schema validated (required fields: skills, experience_years)
- [ ] Confidence score included
- [ ] Latency <8s p95

### Use Case: JD Parsing

- [ ] Accepts raw JD text
- [ ] Returns required skills, preferred skills, experience
- [ ] Schema validated
- [ ] Latency <6s p95

### Use Case: Report Generation

- [ ] Accepts evaluation summary, strengths, weaknesses
- [ ] Returns summary, recommendation, highlights
- [ ] Narrative structure suitable for candidate feedback
- [ ] Latency <12s p95

### Domain Isolation (Architectural Constraint)

- [ ] AI module does NOT import interview, evaluation, admin modules
- [ ] AI module does NOT reference domain entities
- [ ] AI module does NOT perform DB writes to business tables
- [ ] AI module fully testable with mocked providers
- [ ] AI module can be extracted into separate service without refactoring callers

---

## 10. Testing Guide

See [TESTING.md](TESTING.md) for comprehensive testing strategies.

**Key Testing Requirements:**

- Mock provider testing (no real API calls in unit tests)
- Schema validation failure simulation
- Timeout and retry logic verification
- Deterministic mode validation
- Cost estimation testing

---

## 11. Edge Cases

### Provider Failures

- **Primary provider down:** Fallback to secondary provider after 3 failures
- **Rate limit exceeded:** Exponential backoff, queue request if persistent
- **Authentication failure:** Non-retryable, surface error immediately
- **Model deprecated:** Fallback to alternative model (configurable)

### Schema Validation Edge Cases

- **Partial schema match:** Reject, retry with explicit schema prompt
- **Extra fields returned:** Accept (permissive validation)
- **Type coercion possible:** Accept (e.g., string "5" → int 5 for experience_years)
- **Nested validation failure:** Provide detailed path to failing field

### Timeout Edge Cases

- **Provider call hangs:** Timeout enforced at HTTP client level
- **Streaming interrupted:** Capture partial response, mark as failed
- **Client disconnects:** Cancel provider request if possible

### Token Limit Edge Cases

- **Input exceeds model context:** Truncate with warning, prioritize recent context
- **Output truncated:** Retry with lower max_tokens or summary mode
- **Cost limit exceeded:** Reject request, surface error to user

### Concurrent Requests

- **Rate limiting:** Implement token bucket per organization
- **Provider quota sharing:** Track usage across requests
- **Retry storm:** Circuit breaker prevents cascading retries

### Special Characters & Encoding

- **Non-English text:** UTF-8 support required
- **Code blocks in responses:** Preserved with formatting
- **Emojis:** Handled correctly in token counting
- **SQL injection patterns in input:** Sanitize before prompt construction

---

## 12. Concurrency Concerns

### Thread Safety

- Provider clients MUST be thread-safe (use session pooling)
- Telemetry recording MUST be atomic (no race conditions)
- Circuit breaker state MUST use thread-safe counters

### Rate Limiting

- Organization-level rate limiting (requests per minute)
- Token-based rate limiting (tokens per hour)
- Provider-level global rate limiting (shared quota)

### Retry Coordination

- Avoid retry storms: exponential backoff with jitter
- Circuit breaker prevents all threads from retrying simultaneously
- Failed requests logged for later analysis (not infinite retries)

### Streaming Responses (Future)

- If streaming enabled, handle partial response buffering
- Thread-safe buffer management
- Cancel streaming on client disconnect

### Cost Tracking Race Conditions

- Token count increments must be atomic
- Cost calculations may lag (eventual consistency acceptable)
- Daily/monthly quota checks have acceptable race window (<1% error margin)

---

## 13. Future Considerations

### Migration to Separate Service

Design allows extracting AI module into microservice:

- All interactions via structured API
- No domain coupling
- Telemetry contract preserved

### Local Model Support

Support for self-hosted models:

- Same interface contract
- Different deployment strategy
- Cost tracking disabled or estimated

### A/B Testing Models

Infrastructure for model experiments:

- Route X% of traffic to model variant
- Track performance delta
- Automatic rollback on quality regression

### Embedding Management

Future: centralized embedding service:

- Generate embeddings for resume, JD, questions
- Store in Qdrant
- Semantic search support

### Caching Layer

Optional: cache AI responses for identical inputs:

- Deterministic mode responses only
- TTL-based expiration
- Organization-scoped caching
- Must preserve telemetry accuracy

---

**End of AI Module Requirements**
