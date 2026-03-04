# COMPREHENSIVE REPOSITORY AUDIT — AI Interviewer

**Generated**: Step 1 of Module Implementation Protocol  
**Scope**: Every module under `app/`, all persistence infrastructure, shared primitives, bootstrap, config  
**Goal**: Full inventory of purpose, public interfaces, domain services, persistence, contracts, enums, external dependencies, and implementation status for each module

---

## TABLE OF CONTENTS

1. [Architecture Overview](#1-architecture-overview)
2. [Module: question](#2-module-question)
3. [Module: shared](#3-module-shared)
4. [Module: persistence (infrastructure)](#4-module-persistence-infrastructure)
5. [Module: bootstrap](#5-module-bootstrap)
6. [Module: config](#6-module-config)
7. [Module: interview](#7-module-interview)
8. [Module: evaluation](#8-module-evaluation)
9. [Module: coding](#9-module-coding)
10. [Module: ai](#10-module-ai)
11. [Module: auth](#11-module-auth)
12. [Module: admin](#12-module-admin)
13. [Module: audio](#13-module-audio)
14. [Module: proctoring](#14-module-proctoring)
15. [Cross-Module Dependency Map](#15-cross-module-dependency-map)
16. [Implementation Gap Summary](#16-implementation-gap-summary)

---

## 1. Architecture Overview

| Aspect | Detail |
|---|---|
| **Framework** | FastAPI with app-factory pattern (`bootstrap/app.py`) |
| **ORM** | SQLAlchemy 2.x with PostgreSQL (connection pooling, retry logic) |
| **Cache / Locks** | Redis (caching, distributed locks, WebSocket registry) |
| **Vector DB** | Qdrant (semantic question search, multi-tenant collections) |
| **LLM** | Groq (default), OpenAI, Anthropic, Gemini — abstracted via `BaseLLMProvider` |
| **Auth** | JWT-based with RBAC (admin/candidate/superadmin), middleware injection |
| **Multi-Tenancy** | `organization_id` enforced at every data-access layer |
| **DTOs** | Pydantic `BaseModel` throughout; `pydantic-settings` for env config |
| **Patterns** | DDD (domain, persistence, contracts, api per submodule), repository pattern, circuit breaker, state machine |

### Router Registry (registered endpoints)

Registered in `bootstrap/router_registry.py`:

| Prefix | Module | Status |
|---|---|---|
| `/api/v1/auth` | auth | ✅ Active |
| `/api/v1/admin` | admin | ✅ Active |
| `/api/v1/interviews` | interview.api | ✅ Active |
| `/api/v1/interviews/sessions` | interview.session | ✅ Active |
| `/api/v1/questions/selection` | question.selection | ✅ Active |
| `/api/v1/evaluations` | evaluation | ✅ Active |
| `/api/v1/proctoring/ingestion` | proctoring.ingestion | ✅ Active |
| `/api/v1/proctoring/risk` | proctoring.risk_model | ✅ Active |
| `/api/v1/audio/ingestion` | audio.ingestion | ✅ Active |
| `/api/v1/audio/transcription` | audio.transcription | ✅ Active |
| `/ws/interview` | interview.realtime | ✅ Active (WebSocket) |
| `/api/v1/questions` | question (parent) | ❌ COMMENTED OUT |
| `/api/v1/coding` | coding | ❌ COMMENTED OUT |
| `/health`, `/health/database` | bootstrap | ✅ Health checks |

---

## 2. Module: question

**Location**: `app/question/`  
**Purpose**: "Intelligent Content Decision Engine" — transforms `Template + Candidate Context + History → Next Question Snapshot`. The question module **SELECTS**. It does NOT ORCHESTRATE.  
**Owned DB Tables**: `questions`, `topics` (READ-ONLY access to admin-owned tables), `difficulty_adaptation_log`, `generic_fallback_questions`

### 2.1 Submodule: selection/ — ✅ FULLY IMPLEMENTED

**Purpose**: Orchestrates the question selection pipeline: template parsing → difficulty adaptation → Qdrant retrieval → repetition filtering → fallback strategies.

#### Files

| File | Purpose | Status |
|---|---|---|
| `__init__.py` | Public exports: `QuestionSelectionService`, `SelectionContext`, `SelectionResult`, `QuestionSnapshot`, `AdaptationDecision` | ✅ |
| `contracts.py` (228 lines) | Enums + DTOs for the selection pipeline | ✅ |
| `service.py` (868 lines) | `QuestionSelectionService` — main orchestrator | ✅ |
| `domain/difficulty.py` | Pure functions: `adapt_difficulty()`, `increase_difficulty()`, `decrease_difficulty()`, `build_adaptation_decision()`. RULE_VERSION = "1.0.0" | ✅ |
| `domain/template_parser.py` | `validate_template_snapshot()`, `find_section()`, `parse_adaptation_config()`, `count_section_exchanges()`, `get_last_exchange_in_section()`. Exceptions: `TemplateSnapshotError`, `SectionCompleteError` | ✅ |
| `domain/repetition.py` | `is_exact_match()`, `check_repetition()`, `filter_candidates_by_repetition()`. Delegates cosine similarity to retrieval module | ✅ |
| `domain/fallback.py` | `FallbackLevel` IntEnum (0–4), `get_fallback_type()`, `get_relaxed_difficulties()`, `should_relax_similarity()`. MAX_FALLBACK_ATTEMPTS = 5 | ✅ |
| `persistence/models.py` | `DifficultyAdaptationLogModel` ORM → `difficulty_adaptation_log` table (INSERT-ONLY audit) | ✅ |
| `persistence/adaptation_repository.py` | `AdaptationLogRepository`: `log_decision()`, `get_by_submission()`, `get_latest_for_submission()` | ✅ |
| `api/__init__.py` | FastAPI router: `GET /adaptation-log/{submission_id}` (admin-only), `POST /preview` | ✅ |

#### Contracts (contracts.py)

**Enums:**
- `SelectionStrategy` — `ADAPTIVE`, `FIXED`, `RANDOM`
- `FallbackType` — `NONE`, `RELAXED_DIFFICULTY`, `RELAXED_SIMILARITY`, `FALLBACK_BANK`, `LLM_GENERATED`

**DTOs (all Pydantic BaseModel):**
- `DifficultyAdaptationConfig` — `enabled`, `initial_difficulty`, `increase_threshold`, `decrease_threshold`
- `RepetitionConfig` — `exact_match_block`, `similarity_threshold`, `min_candidates`
- `ExchangeHistoryEntry` — `question_text`, `difficulty`, `topic`, `score`, `exchange_id`
- `CandidateProfile` — `resume_text`, `job_description`, `performance_summary`
- `SectionConfig` — `name`, `max_exchanges`, `topic`, `difficulty_override`, `adaptation`
- `SelectionContext` — `submission_id`, `organization_id`, `template_snapshot`, `section_name`, `exchange_history`, `candidate_profile`, `repetition_config`
- `SelectionResult` — `snapshot`, `adaptation_decision`, `source`, `fallback_used`, `metadata`
- `QuestionSnapshot` — `question_text`, `difficulty`, `topic`, `source_type`, `source_id`, `estimated_time_minutes`, `metadata`, `embedding_vector`
- `AdaptationDecision` — `previous_difficulty`, `new_difficulty`, `reason`, `rule_version`, `raw_score`, `threshold_used`

#### Dependencies
- `app.question.retrieval` — `QdrantRetrievalService`
- `app.question.generation` — `QuestionGenerationService`
- `app.shared.errors` — error types
- `app.shared.observability` — logging

---

### 2.2 Submodule: retrieval/ — ✅ FULLY IMPLEMENTED

**Purpose**: Semantic + topic-based question search via Qdrant vector DB, with Redis caching and circuit breaker fault tolerance.

#### Files

| File | Purpose | Status |
|---|---|---|
| `__init__.py` | Exports: `QdrantRetrievalService`, `SearchCriteria`, `QuestionCandidate`, `RetrievalResult`, similarity functions, `CircuitBreaker` | ✅ |
| `contracts.py` | Enums + DTOs for retrieval | ✅ |
| `service.py` (430 lines) | `QdrantRetrievalService`: `search_semantic()`, `search_by_topic()`, `check_similarity()`. Module-level `CircuitBreaker(failure_threshold=5, timeout_duration=60)` | ✅ |
| `domain/similarity.py` | `cosine_similarity()`, `normalize_vector()`, `compute_hybrid_vector()`, `compute_similarity_to_history()`, `is_acceptable_candidate()`. Thresholds: IDENTICAL=0.95, SIMILAR=0.85 | ✅ |
| `domain/circuit_breaker.py` | `CircuitBreaker` with CLOSED/OPEN/HALF_OPEN states, thread-safe (`threading.Lock`) | ✅ |
| `persistence/qdrant_repository.py` (437 lines) | `QdrantQuestionRepository`: `search_questions()`, `scroll_questions_by_filter()`. Builds OR-based multi-tenant filter (`org_id OR scope='public'`) | ✅ |
| `persistence/cache_repository.py` | `RetrievalCacheRepository`: Redis cache, TTL=3600s, key pattern `question_search:{org}:{diff}:{topics}:{vector_hash}` | ✅ |
| `persistence/question_read_repository.py` (207 lines) | `QuestionReadRepository`: PostgreSQL fallback when Qdrant is unavailable. Imports `QuestionModel` from `app.admin.persistence.models` (read-only) | ✅ |

#### Contracts (contracts.py)

**Enums:**
- `RetrievalStrategy` — `SEMANTIC`, `TOPIC_FILTER`, `HYBRID`
- `DifficultyLevel` — `EASY`, `MEDIUM`, `HARD`, `EXPERT`
- `QuestionScope` — `PUBLIC`, `ORGANIZATION`, `PRIVATE`

**DTOs:**
- `HybridSearchWeights` — `semantic_weight`, `topic_weight`
- `SearchCriteria` — `organization_id`, `difficulty`, `topics`, `scope`, `strategy`, `embedding_vector`, `limit`, `similarity_threshold`, `exclude_ids`, `hybrid_weights`
- `QuestionCandidate` — `question_id`, `question_text`, `difficulty`, `topic`, `score`, `source`, `metadata`, `embedding_vector`
- `RetrievalResult` — `candidates`, `total_found`, `strategy_used`, `cache_hit`, `search_time_ms`
- `SimilarityCheckResult` — `is_similar`, `score`, `threshold`

---

### 2.3 Submodule: generation/ — ✅ FULLY IMPLEMENTED

**Purpose**: LLM-powered on-demand question generation with validation, retry, and fallback to a static bank.

#### Files

| File | Purpose | Status |
|---|---|---|
| `__init__.py` | Exports: `QuestionGenerationService`, `GenerationRequest`, `GenerationResult`, `GenerationStatus`, domain entities | ✅ |
| `contracts.py` (201 lines) | Enums + DTOs for generation | ✅ |
| `service.py` (514 lines) | `QuestionGenerationService`: `generate()` with retry+validation+fallback workflow. Depends on `BaseLLMProvider`, `PromptService`, `FallbackQuestionRepository`, optional `embedding_provider` | ✅ |
| `domain/entities.py` | `GeneratedQuestionOutput` (frozen dataclass), `ValidationResult` (frozen dataclass), `GenerationMetadata` (frozen dataclass with `to_dict()`) | ✅ |
| `domain/parsing.py` | `parse_llm_response()` — JSON parsing with markdown fence stripping, difficulty/field validation. `ResponseParseError` exception | ✅ |
| `domain/validation.py` | `validate_generated_question()` — checks difficulty_match, topic_allowed, not_empty, semantic_similarity. Uses retrieval's `cosine_similarity` | ✅ |
| `persistence/models.py` | `GenericFallbackQuestion` ORM → `generic_fallback_questions` table | ✅ |
| `persistence/fallback_repository.py` | `FallbackQuestionRepository`: `get_by_difficulty_and_topic()`, `get_by_difficulty()`, `get_any_active()`, `increment_usage()` | ✅ |

#### Contracts (contracts.py)

**Enums:**
- `GenerationStatus` — `SUCCESS`, `VALIDATION_FAILED`, `LLM_ERROR`, `FALLBACK_USED`, `NO_FALLBACK`

**DTOs:**
- `GenerationRequest` — `submission_id`, `organization_id`, `difficulty`, `topic`, `resume_context`, `jd_context`, `exchange_history`, `performance_context`, `rubric_context`, control params (`max_retries`, `temperature`, `model_override`)
- `GenerationResult` — `question_text`, `difficulty`, `topic`, `status`, `source`, `fallback_used`, `attempts`, `total_tokens`, `estimated_cost`, `latency_ms`, `validation_errors`, `metadata`

---

### 2.4 Submodule: persistence/ — ❌ STUB (No Python files)

**What exists**: Only `REQUIREMENTS.md` (817 lines of detailed specifications).

**What it specifies**:
- `QuestionRepository` — read-only access to `questions` table with multi-tenant filtering
- `TopicRepository` — topic tree traversal, parent/child queries
- `CodingProblemRepository` — read-only access to `coding_problems` table
- All repos are READ-ONLY (question module does not write to `questions`/`topics`/`coding_problems` — those are admin-owned)
- Multi-tenant filter: `organization_id = :org OR scope = 'public'`
- Pagination, sorting, search interfaces

**Python files needed**: `__init__.py`, `repositories.py` (or split into `question_repository.py`, `topic_repository.py`, `coding_problem_repository.py`), potentially `mappers.py`

---

### 2.5 Submodule: prompting/ — ❌ STUB (No Python files)

**What exists**: Only `REQUIREMENTS.md` (800 lines of detailed specifications).

**What it specifies**:
- Prompt composition and context injection for question generation/selection
- Token budget management (ceiling enforcement per model)
- Prompt injection prevention (input sanitization)
- Template versioning and A/B testing
- `prompt_templates` table schema with scope/org isolation
- `PromptComposer` service, `PromptTemplate` entities, `ContextInjector`, `TokenBudgetManager`
- Rendering functions with Jinja2-style variable substitution

**Python files needed**: `__init__.py`, `service.py` (PromptComposer), `contracts.py`, `domain/` (composer, sanitizer, token_budget), `persistence/` (prompt_template_repository)

**Note**: `app/ai/prompts/` already implements a generic `PromptService` with `PromptTemplate` entities. The question/prompting module would be a question-specific layer on top of that.

---

## 3. Module: shared

**Location**: `app/shared/`  
**Purpose**: "Cross-module primitives without business logic"

### 3.1 Submodule: auth_context/ — ✅ FULLY IMPLEMENTED

**Purpose**: Identity injection, RBAC guards, WebSocket authentication, connection registry.

#### Files

| File | Purpose | Key Exports |
|---|---|---|
| `models.py` (230 lines) | Identity primitives | `UserType` (ADMIN/CANDIDATE), `AdminRole` (SUPERADMIN/ADMIN/READ_ONLY), `IdentityContext` (frozen dataclass with invariant validation), `TaskContext` (serializable for async) |
| `builder.py` | JWT → Identity conversion | `IdentityBuilder.from_jwt_claims()`, `validate_claims_structure()` |
| `dependencies.py` (237 lines) | FastAPI `Depends` guards | `get_identity()`, `get_optional_identity()`, `require_admin()`, `require_candidate()`, `require_superadmin()`, `get_token_validator()` |
| `middleware.py` (206 lines) | Request middleware | `IdentityInjectionMiddleware` — extracts JWT from `Authorization` header, validates, builds `IdentityContext`, attaches to `request.state.identity` |
| `scope.py` | Tenant enforcement | `enforce_organization_scope()`, `enforce_candidate_scope()`, `require_organization_admin()` with role hierarchy |
| `config.py` | Settings | `AuthContextConfig` dataclass (middleware/websocket/token/scope settings) |
| `registry.py` (274 lines) | WebSocket state | `ConnectionRegistry` — Redis-backed connection tracking, single connection per submission, heartbeat TTL |
| `websocket.py` | WS auth | `authenticate_websocket()`, `generate_connection_id()` |
| `context.py` | DEPRECATED | `AuthContext`, `UserRole` (backward compatibility aliases) |

#### Key Pattern: IdentityContext

```python
@dataclass(frozen=True)
class IdentityContext:
    user_id: int
    user_type: UserType           # ADMIN or CANDIDATE
    organization_id: Optional[int]
    admin_role: Optional[AdminRole]  # Only set for ADMIN
    # Invariants validated at __post_init__:
    #   - ADMIN must have organization_id and admin_role
    #   - CANDIDATE must have organization_id, must NOT have admin_role
```

---

### 3.2 Submodule: errors/ — ✅ FULLY IMPLEMENTED

**Purpose**: Unified error hierarchy, classification, and serialization for REST + WebSocket.

#### Files

| File | Purpose |
|---|---|
| `exceptions.py` (664 lines) | Full error hierarchy (see below) |
| `classification.py` | `is_fatal_error()`, `get_log_level()`, `should_send_to_client()` |
| `serializers.py` | `serialize_rest_error()`, `serialize_websocket_error()`, `serialize_error_for_logging()` |
| `config.py` | `ErrorConfig` (pydantic-settings) — logging/serialization/environment controls |

#### Error Hierarchy

```
BaseError (dataclass: error_code, message, request_id, metadata, http_status_code)
├── Client Errors
│   ├── AuthenticationError (401)
│   ├── AuthorizationError (403)
│   ├── TenantIsolationViolation (403)
│   ├── NotFoundError (404)
│   ├── ConflictError (409)
│   ├── ValidationError (422)
│   └── RateLimitExceeded (429)
├── Business Errors
│   ├── InterviewNotActiveError
│   ├── InterviewWindowClosedError
│   └── ConsentNotCapturedError
├── Domain Errors
│   ├── ExchangeImmutabilityViolation
│   ├── TemplateImmutabilityViolation
│   ├── DomainInvariantViolation
│   └── ProctoringViolation
├── External Errors
│   ├── AIProviderError → AIProviderTimeoutError
│   └── SandboxExecutionError
└── System Errors
    ├── InfrastructureError
    ├── DatabaseError
    ├── CacheError
    ├── ConfigurationError
    └── InternalServerError
```

---

### 3.3 Submodule: observability/ — ✅ FULLY IMPLEMENTED

**Purpose**: Structured logging, request tracing, metrics primitives.

#### Files

| File | Key Exports |
|---|---|
| `__init__.py` | Full public API barrel export |
| `logging.py` (323 lines) | `StructuredFormatter` (JSON output), `ContextLogger` (auto-injects `request_id`, `user_id`, `org_id`), `configure_structured_logging()`, `redact_sensitive_data()`, `mask_token()` |
| `tracing.py` (202 lines) | `TraceContext` dataclass, ID generators (`req_`, `conn_`, `session_`, `corr_` prefixed), `RequestIDMiddleware`, `extract_request_id()` |
| `metrics.py` | `MetricsRegistry`, `AITelemetry`, `track_ai_call`, `track_latency`, `track_operation` |

---

## 4. Module: persistence (infrastructure)

**Location**: `app/persistence/`  
**Purpose**: Database client creation, connection management, and low-level operations for all three data stores.

### 4.1 postgres/ — ✅ FULLY IMPLEMENTED

| File | Purpose |
|---|---|
| `base.py` | `Base = declarative_base()`, `import_all_models()` — imports ORM models from admin, ai.prompts, coding, question.generation, question.selection, interview.session, proctoring, evaluation |
| `engine.py` (285 lines) | `create_db_engine()` with retry logic, `QueuePool` (configurable `pool_size`, `max_overflow`), pool event listeners, global `_engine` singleton. `init_engine()`, `get_engine()`, `cleanup_engine()` |
| `session.py` | `SessionLocal` sessionmaker, `get_db_session()` (FastAPI DI generator), `get_db_session_with_commit()`, `db_session_context()` (async context manager), `execute_with_retry()` |
| `health.py` | `check_postgres_health()`, `check_postgres_connectivity()`, `log_pool_stats()` |
| `__init__.py` | Convenience: `init_postgres(config)`, `cleanup_postgres()` |

### 4.2 redis/ — ✅ FULLY IMPLEMENTED

| File | Purpose |
|---|---|
| `client.py` | `create_redis_client()` with `ConnectionPool.from_url`, retry logic, global `_client` singleton |
| `operations.py` (588 lines) | `set_value()`, `get_value()`, `delete_key()`, `exists()`, TTL management, hash operations, counters, batch operations, pipeline execution |
| `locks.py` | `acquire_lock()`, `try_acquire_lock()`, `release_lock()`, `is_locked()`, lock key helpers |
| `__init__.py` | Full public API export including distributed locks |

### 4.3 qdrant/ — ✅ FULLY IMPLEMENTED

| File | Purpose |
|---|---|
| `client.py` (222 lines) | `create_qdrant_client()` with retry, global `_client`/`_collection_name`/`_vector_dimension` singletons |
| `operations.py` (501 lines) | `store_embedding()`, `store_embeddings_batch()`, `search_embeddings()`, `update_embedding_metadata()`, `delete_embedding()`, `delete_embeddings_by_source()` |
| `collections.py` | `create_collection_if_not_exists()`, `validate_collection_schema()` |
| `health.py` | `check_qdrant_health()` |

---

## 5. Module: bootstrap

**Location**: `app/bootstrap/`  
**Purpose**: Application factory, middleware registration, router wiring, dependency injection, exception handlers.

### Files

| File | Purpose |
|---|---|
| `app.py` | `create_app()` factory — creates `FastAPI`, registers middleware, routers, exception handlers. Uses `lifespan` for startup/shutdown |
| `dependencies.py` | Re-exports: `get_db_session`, `get_db_session_with_commit`, `get_identity`, `require_admin`, `require_candidate`, `require_superadmin` |
| `router_registry.py` (211 lines) | `register_routers()` — wires all module API routers to the app (see Router Registry table above) |
| `middleware.py` | Middleware stack registration (CORS, identity injection, request ID) |
| `exception_handlers.py` | Maps `BaseError` hierarchy to HTTP responses via shared serializers |
| `lifespan.py` | Async startup/shutdown: init DB engine, Redis client, Qdrant client |

---

## 6. Module: config

**Location**: `app/config/`  
**Purpose**: Centralized configuration loaded from environment variables.

### Files

| File | Key Exports |
|---|---|
| `settings.py` (427 lines) | `AppSettings`, `DatabaseSettings` (pool_size, max_overflow, echo), `RedisSettings`, `QdrantSettings`, `LLMSettings` (model routing by use case: `question_generation_model`, `evaluation_model`, `embedding_model`), `SandboxSettings`, `SecuritySettings`, `AudioSettings`, `RateLimitSettings`, `FeatureFlagsSettings` |
| `feature_flags.py` | `FeatureFlags` frozen dataclass: `ENABLE_AI_EVALUATION`, `ENABLE_PROCTORING`, `ENABLE_AUDIO_ANALYSIS`, `ENABLE_CODE_EXECUTION`, `ENABLE_PRACTICE_MODE`, `ENABLE_HUMAN_OVERRIDE`, `ENABLE_RESUME_PARSING` |
| `security.py` | Security settings (CORS origins, JWT secrets, password policies) |
| `environments.py` | Environment detection and profile loading |
| `constants.py` | Static constants |
| `__init__.py` | Global initialization: `settings`, `feature_flags`, `env_config`, `security_config`, `cors_config`, `password_policy` (all `None` in testing mode when `TESTING=1`) |

---

## 7. Module: interview

**Location**: `app/interview/`  
**Purpose**: Interview lifecycle management — session state machine, exchange orchestration, realtime WebSocket, and read-only query API.

### 7.1 Submodule: session/ — ✅ FULLY IMPLEMENTED

**Purpose**: Submission state machine enforcement and ORM models.

| File | Purpose |
|---|---|
| `domain/state_machine.py` | `SubmissionStatus` enum (`PENDING→IN_PROGRESS→COMPLETED→REVIEWED`, etc.), `StateTransitionError`, `validate_transition()`. Terminal state: `REVIEWED` |
| `persistence/models.py` (111 lines) | `InterviewSubmissionModel` ORM (interview_submissions), `InterviewExchangeModel` ORM (interview_exchanges). Columns include `current_exchange_sequence`, `template_structure_snapshot` (JSONB) |
| `persistence/repository.py` | Submission CRUD with state transition validation |
| `contracts/schemas.py` (144 lines) | `StartInterviewRequest`, `CompleteInterviewRequest`, `CancelInterviewRequest`, `ReviewInterviewRequest`, `InterviewExchangeDTO`, `InterviewSessionDTO` |
| `api/` | Session API routes (start, complete, cancel, review) |

### 7.2 Submodule: exchanges/ — ✅ FULLY IMPLEMENTED

**Purpose**: Exchange creation, immutability enforcement, content classification.

| File | Purpose |
|---|---|
| `__init__.py` | Exports: `InterviewExchangeRepository`, `ExchangeCreationData`, `ContentMetadata`, `QuestionStateMachine`, `UtteranceIntentClassifier`, `ClarificationPolicy` |
| `contracts.py` | `ExchangeCreationData`, `ContentMetadata`, `ExchangeCompletionData` DTOs |
| Domain | `QuestionStateMachine` (exchange lifecycle), `UtteranceIntentClassifier`, `ClarificationPolicy` |
| Persistence | `InterviewExchangeRepository` — exchange CRUD, immutability enforcement |

### 7.3 Submodule: orchestration/ — ✅ FULLY IMPLEMENTED

**Purpose**: Cross-concern coordination — question sequencing, completion handling, progress tracking, race condition resolution.

| File | Purpose |
|---|---|
| `__init__.py` | Exports: `ExchangeCoordinator`, `question_sequencer`, `AudioCompletionHandler`, `CodingCompletionHandler`, `ProgressTracker`, `RaceResolver` |
| `contracts.py` | `NextQuestionResult`, `TemplateSnapshot`, `ProgressUpdate`, completion signal types |

### 7.4 Submodule: realtime/ — ✅ FULLY IMPLEMENTED

**Purpose**: WebSocket protocol for live interview sessions.

| File | Purpose |
|---|---|
| `api/routes.py` | WebSocket endpoint `/ws/interview/{submission_id}` |
| `domain/connection_manager.py` | `ConnectionManager` — in-process + Redis connection tracking |
| `domain/event_handler.py` | `RealtimeEventHandler` — event processing business logic |
| `contracts/` | Client↔Server event Pydantic models |

### 7.5 Submodule: persistence/ — ✅ FULLY IMPLEMENTED

| File | Purpose |
|---|---|
| `repository.py` (296 lines) | `InterviewQueryRepository` — READ-ONLY queries: submission listing with pagination, exchange listing with section filtering, progress calculation. Reuses ORM from `session/persistence/models.py` |

### 7.6 Submodule: api/ — ✅ FULLY IMPLEMENTED

| File | Purpose |
|---|---|
| `routes.py` | REST endpoints for interview data queries |
| `service.py` | Interview API service layer |
| `contracts.py` | API-level DTOs |

---

## 8. Module: evaluation

**Location**: `app/evaluation/`  
**Purpose**: Multi-dimensional evaluation pipeline — AI scoring, human override, rubric resolution, section aggregation, normalization, proctoring adjustment, and final recommendation.

### Submodules (all ✅ FULLY IMPLEMENTED)

| Submodule | Key Classes/Functions |
|---|---|
| `scoring/` | `AIScorer` (LLM-based), `HumanScorer` (admin override), `RubricResolver`, `ScoreCalculator`, `ScoringService` |
| `aggregation/` | `SectionAggregator`, `Normalizer`, `ProctoringAdjuster`, `RecommendationEngine`, `SummaryGenerator`, `AggregationService` |
| `persistence/` | `EvaluationModel` ORM (evaluations table), `evaluation_dimension_scores` association table |
| `snapshots/` | Evaluation state snapshots |
| `api/` | Evaluation REST endpoints |

### Key ORM: EvaluationModel

```
evaluations table:
  id, interview_submission_id, evaluator_type, dimension_scores (JSONB),
  overall_score, section_name, rubric_id, ai_model_used, confidence_score,
  evaluated_at, created_at
```

---

## 9. Module: coding

**Location**: `app/coding/`  
**Purpose**: Code execution sandbox, submission evaluation, and coding problem management.

### Enums (enums.py)

- `ExecutionStatus` — `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `ERROR`, `TIMEOUT`, `MEMORY_EXCEEDED`
- `TestCaseStatus` — test case result states

### Submodules

| Submodule | Purpose | Status |
|---|---|---|
| `persistence/` | `CodeSubmissionModel`, `CodeExecutionResultModel` ORMs, repositories, mappers, entities, protocols | ✅ |
| `execution/` | Code execution orchestration | ✅ |
| `evaluation/` | Code submission evaluation | ✅ |
| `sandbox/` | Sandboxed execution environment | ✅ |
| `api/` | API routes | ✅ (but router COMMENTED OUT in registry) |

### Key ORM Models

```
code_submissions table:
  id, interview_exchange_id, language, source_code, submitted_at

code_execution_results table:
  id, code_submission_id, status, stdout, stderr, exit_code,
  execution_time_ms, memory_used_bytes, test_cases_passed,
  test_cases_total, created_at
```

---

## 10. Module: ai

**Location**: `app/ai/`  
**Purpose**: LLM provider abstraction, prompt management, and AI telemetry.

### 10.1 Submodule: llm/ — ✅ FULLY IMPLEMENTED

| File | Purpose |
|---|---|
| `base_provider.py` | `BaseLLMProvider` ABC: `generate_text()`, `generate_structured()`, `get_supported_models()` |
| `contracts.py` | `LLMRequest` (model, messages, temperature, max_tokens, response_format), `LLMResponse` (content, model, tokens, latency), `TelemetryData`, `EmbeddingRequest`, `EmbeddingResponse` |
| `errors.py` (360 lines) | `LLMProviderError`, `LLMTimeoutError`, `LLMRateLimitError`, `LLMAuthenticationError`, `LLMModelNotFoundError`, `LLMContentFilterError`, `LLMResponseParseError`, `LLMQuotaExceededError` — all extend shared error hierarchy |
| `provider_factory.py` | Provider instantiation by name |
| `providers/groq_provider.py` | Groq implementation |
| `providers/openai_provider.py` | OpenAI implementation |
| `providers/anthropic_provider.py` | Anthropic implementation |
| `providers/gemini_provider.py` | Gemini implementation |
| `providers/embedding_provider.py` | Embedding generation |
| `utils/` | LLM utilities |

### 10.2 Submodule: prompts/ — ✅ FULLY IMPLEMENTED

| File | Purpose |
|---|---|
| `service.py` | `PromptService`: `get_prompt()`, `get_rendered_prompt()` with scope resolution and `fallback_to_global` |
| `entities.py` | `PromptTemplate` (frozen dataclass), `RenderedPrompt` (frozen dataclass), `PromptType` enum |
| `protocols.py` | `PromptTemplateRepository` protocol |
| `renderer.py` | `PromptRenderer` — Jinja2-style variable substitution |
| `repository.py` | DB-backed prompt template repository |
| `models.py` | `PromptTemplateModel` ORM |
| `mappers.py` | ORM ↔ entity mappers |
| `parser.py` | Prompt parsing utilities |
| `errors.py` | Prompt-specific errors |
| `seed_prompts.sql` | SQL seed data for prompt templates |

### 10.3 Submodule: telemetry/ — ✅ FULLY IMPLEMENTED

AI call tracking and cost estimation.

---

## 11. Module: auth

**Location**: `app/auth/`  
**Purpose**: Authentication (JWT), authorization (RBAC), user management.

### Submodules (all ✅ FULLY IMPLEMENTED)

| Submodule | Files | Purpose |
|---|---|---|
| `api/` | `routes.py` | Login, register, refresh, logout endpoints |
| `domain/` | `auth_service.py`, `jwt_service.py`, `password_hasher.py`, `rbac_enforcer.py`, `contracts.py` | Core auth business logic |
| `persistence/` | `admin_repository.py`, `candidate_repository.py`, `refresh_token_repository.py`, `user_repository.py`, `audit_log_repository.py`, `models.py` | User/token storage |
| `contracts/` | `claims.py`, `enums.py`, `responses.py`, `schemas.py` | Auth DTOs |

### Key Enum: AuthErrorCode (contracts/enums.py)

- Authentication (401): `INVALID_CREDENTIALS`, `USER_INACTIVE`, `USER_BANNED`, `ADMIN_INACTIVE`, `ORG_SUSPENDED`, `ORG_INACTIVE`
- Token (401): `TOKEN_EXPIRED`, `TOKEN_INVALID`, `TOKEN_REVOKED`, `REFRESH_TOKEN_INVALID`, `REFRESH_TOKEN_EXPIRED`
- Registration (409/422): `EMAIL_ALREADY_EXISTS`, `PASSWORD_TOO_WEAK`, `ORG_NOT_FOUND`
- Authorization (403): `INSUFFICIENT_PERMISSIONS`, `MISSING_TOKEN`
- Security (429): `SUSPICIOUS_ACTIVITY`, `RATE_LIMIT_EXCEEDED`

---

## 12. Module: admin

**Location**: `app/admin/`  
**Purpose**: Admin CRUD for all content entities (templates, rubrics, roles, topics, questions, coding problems, windows, overrides).

### Submodules

| Submodule | Purpose | Status |
|---|---|---|
| `api/` | Admin REST endpoints | ✅ |
| `domain/` | Admin business rules | ✅ |
| `persistence/` | ORM models, repositories, mappers | ✅ |
| `validation/` | Input validation | ✅ |

### Key ORM Models (persistence/models.py — 783 lines)

| Model | Table | Key Fields |
|---|---|---|
| `InterviewTemplateModel` | `interview_templates` | name, scope, organization_id, template_structure (JSONB), rules (JSONB), version |
| `InterviewTemplateRoleModel` | `interview_template_roles` | template_id, role_id (composite PK) |
| `InterviewTemplateRubricModel` | `interview_template_rubrics` | template_id, rubric_id, section_name |
| `RubricModel` | `rubrics` | name, scope, organization_id, schema (JSONB) |
| `RubricDimensionModel` | `rubric_dimensions` | rubric_id, dimension_name, max_score, weight, criteria (JSONB), sequence_order |
| `RoleModel` | `roles` | name, scope, organization_id |
| `TopicModel` | `topics` | name, parent_topic_id (self-referential), scope, organization_id |
| `CodingTopicModel` | `coding_topics` | name, topic_type, parent_topic_id, scope, organization_id |
| `QuestionModel` | `questions` | question_text, answer_text, question_type, difficulty, scope, organization_id |
| `CodingProblemModel` | `coding_problems` | body, difficulty, scope, organization_id, source_name, source_id, code_snippets (JSONB) |
| `InterviewSubmissionWindowModel` | `interview_submission_windows` | organization_id, admin_id, start_time, end_time, max_allowed_submissions |
| `WindowRoleTemplateModel` | `window_role_templates` | window_id, role_id, template_id, selection_weight |
| `AuditLogModel` | `audit_logs` | organization_id, actor_user_id, action, entity_type, entity_id, old_value/new_value (JSONB) |
| **6 Override Models** | `*_overrides` tables | organization_id, base_content_id, override_fields (JSONB) — for template, rubric, role, topic, question, coding_problem |

**Cross-module import**: `InterviewSubmissionModel` is re-exported from `app.interview.session.persistence.models` in admin models for convenience.

**Override pattern**: `OVERRIDE_MODEL_MAP` dict maps entity type strings to override model classes for a generic `OverrideRepository`.

---

## 13. Module: audio

**Location**: `app/audio/`  
**Purpose**: Audio stream ingestion, transcription, analysis, and persistence for voice-based interviews.

### Submodules

| Submodule | Purpose | Status |
|---|---|---|
| `ingestion/` | Audio stream intake | ✅ |
| `transcription/` | Speech-to-text | ✅ |
| `analysis/` | Audio quality analysis | ✅ |
| `persistence/` | Audio data storage | ✅ |

---

## 14. Module: proctoring

**Location**: `app/proctoring/`  
**Purpose**: "This module OBSERVES. It does NOT DECIDE." Advisory integrity signal collection, rule-based severity assignment, deterministic risk scoring, and admin review queue.

### Submodules

| Submodule | Purpose | Status |
|---|---|---|
| `ingestion/` | Event intake, validation, deduplication | ✅ |
| `rules/` | Severity & weight assignment, clustering detection | ✅ |
| `risk_model/` | Aggregated risk score computation, classification | ✅ |
| `persistence/` | Immutable event storage & retrieval | ✅ |

---

## 15. Cross-Module Dependency Map

```
question/selection  ──→  question/retrieval (QdrantRetrievalService)
                    ──→  question/generation (QuestionGenerationService)
                    ──→  shared/errors
                    ──→  shared/observability

question/retrieval  ──→  persistence/qdrant (QdrantQuestionRepository)
                    ──→  persistence/redis (RetrievalCacheRepository)
                    ──→  persistence/postgres (QuestionReadRepository)
                    ──→  admin/persistence/models (QuestionModel — read-only)

question/generation ──→  ai/llm (BaseLLMProvider)
                    ──→  ai/prompts (PromptService)
                    ──→  question/retrieval/domain (cosine_similarity — for validation)

interview/session   ──→  shared/auth_context (identity guards)
                    ──→  shared/errors (state transition errors)

interview/orchestration ──→  question/selection (QuestionSelectionService)
                        ──→  interview/exchanges (ExchangeRepository)
                        ──→  interview/session (SubmissionRepository)

interview/realtime  ──→  interview/orchestration (ExchangeCoordinator)
                    ──→  shared/auth_context (WebSocket auth, ConnectionRegistry)
                    ──→  persistence/redis (connection state)

evaluation/scoring  ──→  ai/llm (BaseLLMProvider — for AI scoring)
                    ──→  admin/persistence (RubricModel — rubric lookup)

coding/execution    ──→  coding/sandbox (sandboxed runner)

bootstrap           ──→  ALL modules (router registration, middleware, DI)
config              ──→  ALL modules (settings injection)
```

---

## 16. Implementation Gap Summary

### ❌ STUBS — No Python Implementation

| Module | Submodule | REQUIREMENTS.md | Lines | Priority |
|---|---|---|---|---|
| `question` | `persistence/` | ✅ Detailed spec | 817 | **HIGH** — needed for `QuestionRepository`, `TopicRepository`, `CodingProblemRepository` |
| `question` | `prompting/` | ✅ Detailed spec | 800 | **HIGH** — needed for question-specific prompt composition and token budget management |

### ❌ COMMENTED OUT — Router Not Registered

| Module | Router | Reason |
|---|---|---|
| `question` | Parent `/api/v1/questions` | Likely depends on `question/persistence/` being implemented |
| `coding` | `/api/v1/coding` | Unknown — code exists but router disabled |

### ✅ Fully Implemented Modules

All other modules are **fully implemented** with Python code:
- `question/selection`, `question/retrieval`, `question/generation`
- `shared` (auth_context, errors, observability)
- `persistence` (postgres, redis, qdrant)
- `bootstrap`, `config`
- `interview` (session, exchanges, orchestration, realtime, persistence, api)
- `evaluation` (scoring, aggregation, persistence, snapshots, api)
- `coding` (persistence, execution, evaluation, sandbox, api)
- `ai` (llm, prompts, telemetry)
- `auth` (api, domain, persistence, contracts)
- `admin` (api, domain, persistence, validation)
- `audio` (ingestion, transcription, analysis, persistence)
- `proctoring` (ingestion, rules, risk_model, persistence)

### Key Cross-Module Notes

1. **`QuestionModel` lives in `admin/persistence/models.py`**, not in `question/`. The question module has READ-ONLY access. This is by design — admin owns the content, question module selects from it.

2. **`InterviewSubmissionModel` lives in `interview/session/persistence/models.py`** but is re-exported from `admin/persistence/models.py` for convenience.

3. **`import_all_models()` in `persistence/postgres/base.py`** imports from: admin, ai.prompts, coding, question.generation, question.selection, interview.session, proctoring, evaluation. When `question/persistence/` is implemented, its models will need to be added here (if any new tables are created).

4. **`ai/prompts/`** provides a generic prompt service. `question/prompting/` (when implemented) should layer question-specific composition on top, not duplicate it.

5. **Tests**: `tests/conftest.py` sets `TESTING=1` which causes `config/__init__.py` to skip all initialization (settings, feature_flags, etc. remain `None`). Test fixtures provide `minimal_env`, `dev_env`, `staging_env`, `prod_env` environment configs.

---

*End of STEP 1 Audit. Ready for STEP 2: Module Implementation.*
