# REPO ALIGNMENT REPORT — evaluation/scoring

## 1. Module Purpose

The `evaluation/scoring` module is the **deterministic scoring engine** responsible for:
- Scoring individual exchanges against rubric dimensions
- Resolving correct rubric for exchanges
- AI-based scoring via LLM
- Human manual scoring
- Score validation and weighted total calculation

## 2. Repository Audit Summary

### 2.1 All Modules Under /app

| Module | Purpose | Public Interfaces | Dependencies |
|--------|---------|-------------------|--------------|
| `admin` | Admin user management, RBAC | Admin API endpoints | auth, persistence |
| `ai` | LLM providers, prompts, telemetry | PromptService, BaseLLMProvider, ProviderFactory | config, shared/observability |
| `audio` | Audio ingestion, transcription, analysis | Transcription contracts, analysis utilities | ai/llm |
| `auth` | Authentication, JWT, refresh tokens | Auth guards, identity dependencies | persistence, shared |
| `bootstrap` | App initialization, DI, middleware | get_db_session, require_admin | All modules |
| `coding` | Code execution, sandboxing | ExecutionStatus enum | persistence |
| `config` | Settings, environment config | settings singleton | None |
| `evaluation` | Exchange evaluation, aggregation, results | *This module* | interview, ai, persistence, shared |
| `interview` | Session mgmt, exchanges, orchestration | InterviewExchangeModel, ExchangeRepository | persistence, question |
| `persistence` | Postgres, Redis, Qdrant adapters | Base, get_db_session, engine | config |
| `proctoring` | Integrity signals (advisory) | Proctoring events | interview |
| `question` | Question generation, selection | Question models | ai, persistence |
| `shared` | Errors, observability, auth context | BaseError hierarchy, get_context_logger | None |

### 2.2 Dependencies for evaluation/scoring

**This module depends on:**
- `app.ai.llm` - LLM providers for AI scoring
- `app.ai.prompts` - Prompt rendering for evaluation prompts
- `app.interview.session.persistence.models` - InterviewExchangeModel
- `app.persistence.postgres` - Database session, Base
- `app.shared.errors` - Exception classes
- `app.shared.observability` - Logging
- `app.config.settings` - Configuration

**Modules that depend on this module:**
- `app.evaluation.aggregation` - Aggregates dimension scores
- `app.evaluation.api` - Exposes scoring endpoints

### 2.3 Shared Infrastructure Identified

| Infrastructure | Location | Used By scoring |
|----------------|----------|-----------------|
| BaseError hierarchy | `app/shared/errors/exceptions.py` | ✓ Extend for scoring errors |
| get_context_logger | `app/shared/observability/__init__.py` | ✓ Structured logging |
| ProviderFactory | `app/ai/llm/provider_factory.py` | ✓ LLM access |
| PromptService | `app/ai/prompts/service.py` | ✓ Evaluation prompts |
| get_db_session | `app/bootstrap/dependencies.py` | ✓ DB access |
| Base (ORM) | `app/persistence/postgres/base.py` | ✓ Model inheritance |
| LLMRequest/LLMResponse | `app/ai/llm/contracts.py` | ✓ LLM calls |

## 3. Schema Reconciliation

### 3.1 Required Tables (Already Exist in schema.sql)

| Table | Purpose | Status |
|-------|---------|--------|
| `evaluations` | Exchange-level evaluation record | ✓ EXISTS |
| `evaluation_dimension_scores` | Per-dimension scores | ✓ EXISTS |
| `rubrics` | Rubric definitions | ✓ EXISTS |
| `rubric_dimensions` | Dimension definitions | ✓ EXISTS |
| `interview_template_rubrics` | Template-rubric mapping | ✓ EXISTS |
| `interview_exchanges` | Exchange data | ✓ EXISTS |
| `audio_analytics` | Transcripts | ✓ EXISTS |

### 3.2 Existing Schema Details

#### evaluations table
```sql
CREATE TABLE public.evaluations (
    id bigint NOT NULL,
    interview_exchange_id bigint NOT NULL,
    rubric_id bigint,
    model_id bigint,
    evaluator_type public.evaluator_type NOT NULL,
    total_score numeric,
    explanation jsonb,
    is_final boolean DEFAULT false NOT NULL,
    evaluated_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
-- UNIQUE constraint on interview_exchange_id (one evaluation per exchange)
```

#### evaluation_dimension_scores table
```sql
CREATE TABLE public.evaluation_dimension_scores (
    id bigint NOT NULL,
    evaluation_id bigint NOT NULL,
    rubric_dimension_id bigint NOT NULL,
    score numeric NOT NULL,
    justification text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
```

#### rubric_dimensions table
```sql
CREATE TABLE public.rubric_dimensions (
    id bigint NOT NULL,
    rubric_id bigint NOT NULL,
    dimension_name text NOT NULL,
    description text,
    max_score numeric NOT NULL,
    weight numeric DEFAULT 1.0 NOT NULL,
    criteria jsonb,
    sequence_order integer DEFAULT 0 NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);
```

### 3.3 Foreign Keys (Verified)

- `evaluations.interview_exchange_id` → `interview_exchanges.id` (CASCADE)
- `evaluations.rubric_id` → `rubrics.id` (SET NULL)
- `evaluations.model_id` → `models.id` (SET NULL)
- `evaluation_dimension_scores.evaluation_id` → `evaluations.id` (CASCADE)
- `evaluation_dimension_scores.rubric_dimension_id` → `rubric_dimensions.id` (CASCADE)

### 3.4 Enums (Verified)

- `evaluator_type`: ('ai', 'human', 'hybrid') - EXISTS in schema

## 4. Schema Change Assessment

**NO SCHEMA CHANGES REQUIRED**

The existing schema fully supports all scoring requirements:
- ✓ evaluations table with interview_exchange_id FK
- ✓ evaluation_dimension_scores with proper FKs
- ✓ rubric_dimensions with max_score, weight, criteria
- ✓ evaluator_type enum
- ✓ UNIQUE constraint on evaluations(interview_exchange_id)

## 5. Contract Validation

### 5.1 Existing DTOs to Reuse

| DTO | Location | Purpose |
|-----|----------|---------|
| LLMRequest | `app/ai/llm/contracts.py` | LLM call input |
| LLMResponse | `app/ai/llm/contracts.py` | LLM call output |
| RenderedPrompt | `app/ai/prompts/entities.py` | Rendered prompt |

### 5.2 New DTOs Required (scoring/contracts.py)

- `RubricDimensionDTO` - Dimension info for scoring
- `DimensionScoreResult` - Per-dimension score result
- `AIScoreResult` - Complete AI scoring output
- `HumanDimensionScore` - Human input for manual scoring
- `ExchangeDataDTO` - Exchange data for scoring context

## 6. Invariant Verification

| Invariant | Enforcement Location | Status |
|-----------|---------------------|--------|
| Exchange immutability | `interview/exchanges/repository.py` | ✓ Enforced |
| One exchange = one evaluation | `evaluations` UNIQUE constraint | ✓ Enforced |
| Rubric frozen at interview creation | Template snapshot in interview_submissions | ✓ Enforced |
| Score bounds validation | Scoring domain layer | → To implement |

## 7. Implementation Decision

**PROCEED WITH IMPLEMENTATION** - No blockers identified.

---

*Generated: 2026-03-02*
