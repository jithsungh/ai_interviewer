# Comprehensive Repository Audit — AI Interviewer

**Date:** 2026-02-28  
**Scope:** All modules under `/app`

---

## Table of Contents

1. [Repository Overview](#1-repository-overview)
2. [Module Audit](#2-module-audit)
   - [admin](#21-admin)
   - [ai](#22-ai)
   - [audio](#23-audio)
   - [auth](#24-auth)
   - [bootstrap](#25-bootstrap)
   - [coding](#26-coding)
   - [config](#27-config)
   - [evaluation](#28-evaluation)
   - [interview](#29-interview)
   - [persistence](#210-persistence)
   - [proctoring](#211-proctoring)
   - [question](#212-question)
   - [shared](#213-shared)
3. [Shared Infrastructure](#3-shared-infrastructure)
4. [Dependency Injection Setup](#4-dependency-injection-setup)
5. [Database Schema Summary](#5-database-schema-summary)
6. [Audio Module Deep-Dive](#6-audio-module-deep-dive)
7. [SRS Highlights](#7-srs-highlights)
8. [Requirements.txt Summary](#8-requirementstxt-summary)
9. [Implementation Status Matrix](#9-implementation-status-matrix)

---

## 1. Repository Overview

| Aspect | Detail |
|--------|--------|
| **Framework** | FastAPI 0.109 + Uvicorn |
| **ORM** | SQLAlchemy 2.0 (sync, `future=True`) |
| **Database** | PostgreSQL 17 (psycopg2-binary for sync, asyncpg available) |
| **Cache/Sessions** | Redis 5.0 (hiredis) |
| **Vector Search** | Qdrant 1.12 |
| **LLM** | Groq (default), OpenAI/Anthropic (pluggable) |
| **Auth** | JWT (HS256/RS256), bcrypt password hashing |
| **Task Queue** | Celery + Redis (declared in deps, not yet wired) |
| **Testing** | pytest + pytest-asyncio |
| **Architecture** | Domain-driven, Hexagonal (Ports & Adapters), multi-tenant |

**Module implementation status:**

| Module | Status |
|--------|--------|
| `admin` | ✅ Fully implemented (API + Domain + Persistence + Validation) |
| `ai` | ✅ Fully implemented (LLM providers + Prompts + Telemetry) |
| `audio` | ❌ Requirements-only (no Python code yet) |
| `auth` | ✅ Fully implemented (API + Domain + Persistence) |
| `bootstrap` | ✅ Fully implemented (App factory, DI, Middleware, Routing) |
| `coding` | ✅ Fully implemented (Execution + Evaluation + Sandbox + Persistence) |
| `config` | ✅ Fully implemented (Settings, Environments, Feature Flags, Security) |
| `evaluation` | ❌ Requirements-only (no Python code yet) |
| `interview` | ❌ Requirements-only (no Python code yet) |
| `persistence` | ✅ Fully implemented (Postgres, Redis, Qdrant clients) |
| `proctoring` | ❌ Requirements-only (no Python code yet) |
| `question` | ❌ Requirements-only (no Python code yet) |
| `shared` | ✅ Fully implemented (Errors, Auth Context, Observability) |

---

## 2. Module Audit

### 2.1 admin

**Purpose:** CRUD management of interview templates, rubrics, roles, topics, questions, coding problems, and interview windows. Implements multi-tenant override pattern (super-org base content + tenant-specific overrides).

#### Files

```
app/admin/
├── REQUIREMENTS.md
├── TESTING.md
├── api/
│   ├── __init__.py
│   ├── contracts.py         # Pydantic request/response schemas
│   ├── dependencies.py      # FastAPI DI factories for services
│   └── routes.py            # FastAPI router (1139 lines)
├── domain/
│   ├── __init__.py
│   ├── authorization.py     # RBAC authorization helpers
│   ├── entities.py          # Domain entities (dataclasses, 367 lines)
│   ├── protocols.py         # Repository protocols (interfaces)
│   └── services.py          # Domain services (1394 lines)
├── persistence/
│   ├── __init__.py
│   ├── mappers.py           # Entity ↔ ORM model mappers
│   ├── models.py            # SQLAlchemy ORM models
│   └── repositories.py      # Repository implementations
└── validation/
    ├── __init__.py
    ├── cross_reference_validator.py
    ├── override_validator.py
    ├── pre_activation_validator.py
    ├── result.py
    ├── rubric_validator.py
    └── template_validator.py
```

#### Public Interfaces

- **API Routes** (`/api/v1/admin`):
  - Templates: CRUD + activate + overrides
  - Rubrics: CRUD + dimensions + overrides
  - Roles: CRUD + overrides
  - Topics: CRUD + overrides
  - Questions: CRUD + overrides
  - Coding Problems: CRUD + overrides
  - Windows: CRUD + mappings

#### Domain Services

- `TemplateService` — Template CRUD, activation, immutability enforcement
- `RubricService` — Rubric CRUD, dimension weight validation
- `RoleService` — Role CRUD
- `TopicService` — Topic CRUD
- `QuestionService` — Question CRUD
- `CodingProblemService` — Coding problem CRUD
- `WindowService` — Interview window scheduling

#### Persistence Classes

- Repositories implementing protocols: `TemplateRepository`, `RubricRepository`, `RoleRepository`, `TopicRepository`, `QuestionRepository`, `CodingProblemRepository`, `WindowRepository`, `OverrideRepository`, `AuditLogRepository`, `SubmissionRepository`

#### Contracts (DTOs/Pydantic)

Extensive set in `api/contracts.py`: `TemplateCreateRequest`, `TemplateResponse`, `RubricCreateRequest`, `QuestionCreateRequest`, `CodingProblemCreateRequest`, `OverrideCreateRequest`, `WindowCreateRequest`, pagination models (`PaginationMeta`, `MetaInfo`), list/detail response models for every entity.

#### Enums

- `TemplateScope` (public, organization, private)
- `InterviewScope` (global, local, only_invited)
- `DifficultyLevel` (easy, medium, hard)
- `QuestionType` (behavioral, technical, situational, coding)
- `CodingTopicType` (data_structure, algorithm, pattern, system_design, language_specific, traversal)
- `ContentType` (template, rubric, role, topic, question, coding_problem)

#### External Dependencies

- `app.bootstrap.dependencies` — `get_db_session_with_commit`, `require_admin`
- `app.shared.auth_context.models` — `IdentityContext`, `AdminRole`
- `app.shared.errors` — `NotFoundError`, `ConflictError`, `ValidationError`, `TemplateImmutabilityViolation`
- `app.shared.observability` — `get_context_logger`

---

### 2.2 ai

**Purpose:** Abstracted LLM provider layer supporting multiple AI backends, prompt template management, and AI usage telemetry/cost tracking.

#### Files

```
app/ai/
├── REQUIREMENTS.md
├── TESTING.md
├── llm/
│   ├── __init__.py
│   ├── base_provider.py     # Abstract base class for LLM providers
│   ├── contracts.py         # LLMRequest, LLMResponse, TelemetryData DTOs
│   ├── errors.py            # LLM-specific error types
│   ├── provider_factory.py  # Factory to instantiate providers by name
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── anthropic_provider.py
│   │   ├── embedding_provider.py
│   │   ├── gemini_provider.py
│   │   ├── groq_provider.py
│   │   └── openai_provider.py
│   └── utils/
│       ├── __init__.py
│       └── token_counter.py
├── prompts/
│   ├── __init__.py
│   ├── entities.py          # Prompt template domain entities
│   ├── errors.py            # Prompt-specific errors
│   ├── mappers.py           # Entity ↔ model mappers
│   ├── models.py            # SQLAlchemy ORM models for prompt_templates
│   ├── parser.py            # Template variable parser
│   ├── protocols.py         # Repository protocols
│   ├── renderer.py          # Jinja2/string template rendering
│   ├── repository.py        # Prompt template repository
│   └── service.py           # Prompt template service
└── telemetry/
    ├── __init__.py
    ├── aggregation.py       # Usage aggregation
    ├── contracts.py         # Telemetry DTOs
    ├── cost.py              # Cost calculation per provider/model
    ├── errors.py            # Telemetry errors
    └── tracker.py           # Usage tracker service
```

#### Public Interfaces

- `BaseLLMProvider` — Abstract interface: `generate_text()`, `generate_structured()`, `get_supported_models()`
- `ProviderFactory` — Creates provider instances by name
- `PromptTemplateService` — CRUD + rendering for prompt templates

#### Domain Services

- `PromptTemplateService` — Manages prompt templates (CRUD, rendering, versioning)
- `TelemetryTracker` — Tracks AI usage (tokens, latency, cost)

#### Contracts

- `LLMRequest` — Unified request: prompt, model, temperature, max_tokens, json_mode, schema, timeout
- `LLMResponse` — Unified response: text, tokens, telemetry, raw_response
- `TelemetryData` — Provider, model, tokens in/out, latency, cost
- `EmbeddingRequest/Response` — Vector embedding operations
- `TranscriptionRequest/Response` — Audio transcription (for future audio integration)

#### Enums

- `LLMProvider` (groq, gemini, openai, anthropic, local)
- `LLMErrorType` (timeout, rate_limit, authentication, provider_error, schema_validation, unknown)

#### External Dependencies

- `app.config.settings` — API keys, model routing
- `app.shared.errors` — Base error classes
- `app.persistence.postgres` — DB session for prompt templates
- `httpx` — HTTP client for LLM API calls (timeout control)
- `groq` — Groq SDK

---

### 2.3 audio

**Purpose:** Structured audio analytics signal generation for voice-based interviews. Handles audio ingestion, transcription, behavioral analysis (fillers, speech rate, sentiment), sentence completeness detection, and audio analytics persistence.

**STATUS: REQUIREMENTS ONLY — NO PYTHON CODE IMPLEMENTED**

#### Files (all markdown)

```
app/audio/
├── REQUIREMENTS.md           # 656 lines — Master requirements
├── TESTING.md                # 711 lines — Comprehensive testing guide
├── analysis/
│   ├── REQUIREMENTS.md       # 694 lines — Analysis submodule requirements
│   └── TESTING.md
├── ingestion/
│   ├── REQUIREMENTS.md       # 344 lines — Ingestion submodule requirements
│   └── TESTING.md
├── persistence/
│   ├── REQUIREMENTS.md       # 550 lines — Persistence submodule requirements
│   └── TESTING.md
└── transcription/
    ├── REQUIREMENTS.md       # 405 lines — Transcription submodule requirements
    └── TESTING.md
```

#### Planned Architecture

- **ingestion/** — Audio stream ingestion, format normalization (to 16kHz mono), silence detection, session management
- **transcription/** — Provider-agnostic STT (Whisper, Google Cloud Speech, Azure, local Whisper); streaming + batch modes
- **analysis/** — Sentence completeness (spaCy NLP), filler word detection, speech rate, sentiment (VADER/TextBlob), intent classification
- **persistence/** — `AudioAnalyticsRepository` for `audio_analytics` table; enforces UNIQUE per exchange, transcript immutability

#### Owned Table: `audio_analytics`

```sql
audio_analytics (
    id SERIAL PRIMARY KEY,
    interview_exchange_id INT NOT NULL UNIQUE,
    transcript TEXT NOT NULL,
    confidence_score FLOAT CHECK (0.0-1.0),
    speech_rate_wpm FLOAT,
    filler_word_count INT DEFAULT 0,
    sentiment_score FLOAT,
    pause_duration_ms INT,
    speech_state VARCHAR(20) CHECK ('complete','incomplete','continuing'),
    analysis_metadata JSONB,
    created_at TIMESTAMP, updated_at TIMESTAMP
)
```

#### Key Design Principles

- Audio is a **signal generator, not a decision-maker**
- SHALL NOT write to `interview_exchanges`, `evaluations`, or `interview_submissions`
- Silence detection triggers completeness evaluation (not direct completion)
- Rule-based NLP (spaCy) for completeness, not LLMs
- One `audio_analytics` record per exchange (UNIQUE constraint)
- Finalized transcripts are immutable

See [Section 6: Audio Module Deep-Dive](#6-audio-module-deep-dive) for full detail.

---

### 2.4 auth

**Purpose:** Authentication (registration, login, JWT token management) and authorization (RBAC enforcement) for admin and candidate users.

#### Files

```
app/auth/
├── REQUIREMENTS.md
├── api/
│   ├── __init__.py
│   └── routes.py            # FastAPI router (391 lines)
├── contracts/
│   ├── __init__.py
│   ├── claims.py            # JWT claim structures
│   ├── enums.py             # Auth-specific enums
│   ├── responses.py         # Response schemas
│   └── schemas.py           # Request schemas (registration, login)
├── domain/
│   ├── __init__.py
│   ├── auth_service.py      # Core auth orchestration service
│   ├── contracts.py         # Domain commands (RegisterAdminCommand, etc.)
│   ├── jwt_service.py       # JWT creation/validation
│   ├── password_hasher.py   # bcrypt password hashing
│   └── rbac_enforcer.py     # RBAC rule enforcement
└── persistence/
    ├── __init__.py
    ├── admin_repository.py
    ├── audit_log_repository.py
    ├── candidate_repository.py
    ├── models.py            # SQLAlchemy ORM models
    ├── refresh_token_repository.py
    └── user_repository.py
```

#### Public Interfaces

- **API Routes** (`/api/v1/auth`):
  - `POST /register/admin` — Register admin user (201)
  - `POST /register/candidate` — Register candidate user (201)
  - `POST /login` — Authenticate and get tokens (200)
  - `POST /refresh` — Refresh access token (200)
  - `POST /logout` — Revoke refresh token (200)
  - `GET /me` — Current user profile (200)

#### Domain Services

- `AuthService` — Registration, login, token refresh, logout orchestration
- `JWTService` — JWT creation/validation (HS256/RS256)
- `PasswordHasher` — bcrypt hashing with configurable cost factor
- `RBACEnforcer` — Role-based access control rule enforcement

#### Persistence Classes

- `UserRepository` — Users table CRUD
- `AdminRepository` — Admins table CRUD
- `CandidateRepository` — Candidates table CRUD
- `RefreshTokenRepository` — Refresh token storage/revocation
- `AuditLogRepository` — Auth audit log (immutable INSERT-ONLY)

#### Contracts

- Request: `AdminRegistrationRequest`, `CandidateRegistrationRequest`, `LoginRequest`, `RefreshTokenRequest`, `LogoutRequest`
- Response: `RegistrationResponse`, `LoginResponse`, `TokenRefreshResponse`, `CurrentUserResponse`, `UserProfileResponse`
- Domain: `RegisterAdminCommand`, `RegisterCandidateCommand`, `LoginCommand`, `RefreshTokenCommand`, `LogoutCommand`, `UserProfile`

#### Enums

- `UserType` (admin, candidate) — in `shared/auth_context/models.py`
- `AdminRole` (superadmin, admin, read_only) — in `shared/auth_context/models.py`

#### External Dependencies

- `app.config.settings` — JWT keys, password hash config
- `app.shared.auth_context` — `IdentityContext`
- `app.shared.errors` — `AuthenticationError`, `AuthorizationError`
- `app.bootstrap.dependencies` — `get_db_session_with_commit`, `get_identity`
- `pyjwt`, `passlib[bcrypt]`

---

### 2.5 bootstrap

**Purpose:** Application assembly layer — creates FastAPI app, registers middleware/routers/exception handlers, manages DI, and controls application lifespan (startup/shutdown).

#### Files

```
app/bootstrap/
├── __init__.py
├── app.py                   # FastAPI application factory (create_app)
├── dependencies.py          # DI re-exports (get_db_session, require_admin, etc.)
├── exception_handlers.py    # Global exception handlers
├── lifespan.py              # Startup/shutdown lifecycle (Postgres, Redis, Qdrant)
├── middleware.py             # Middleware registration (RequestContext, Logging, CORS, Identity)
├── router_registry.py       # Centralized router registration
├── HUMAN_TESTING_GUIDE.md
├── IMPLEMENTATION_COMPLETE.md
├── REPO_ALIGNMENT_REPORT.md
└── REQUIREMENTS.md
```

#### Key Classes/Functions

- `create_app()` → Factory function: creates FastAPI instance, registers middleware → routers → exception handlers
- `lifespan()` → Async context manager: initializes Postgres engine + session factory, Redis client, Qdrant client on startup; cleans up on shutdown
- `register_middleware(app)` → Registers in order: RequestContext → Logging → CORS → GZip → IdentityInjection
- `register_routers(app)` → Registers auth + admin routers (others commented out pending implementation)
- `register_exception_handlers(app)` → BaseError, ValidationError, HTTPException handlers

#### DI Re-exports (dependencies.py)

- `get_db_session` — Read-only DB session
- `get_db_session_with_commit` — Auto-commit DB session
- `get_identity` — Extract IdentityContext from JWT
- `get_optional_identity` — Optional identity extraction
- `require_admin` — Require admin role
- `require_candidate` — Require candidate role
- `require_superadmin` — Require superadmin role

#### Currently Registered Routers

- ✅ `auth_router` → `/api/v1/auth`
- ✅ `admin_router` → `/api/v1/admin`
- ❌ interview, question, evaluation, coding, proctoring, audio (commented out)
- ✅ Health checks: `GET /health`, `GET /health/database`

#### External Dependencies

- `app.config` — Settings singleton
- `app.shared.observability` — Logging
- `app.shared.auth_context.middleware` — Identity injection
- `app.persistence.postgres` — Engine, session factory, health check
- `app.persistence.redis` — Client init/cleanup
- `app.persistence.qdrant` — Client init/cleanup

---

### 2.6 coding

**Purpose:** Sandboxed code execution for coding assessments. Supports C++, Java, Python3. Executes candidate code in Docker containers against test cases, compares output, and calculates weighted scores.

#### Files

```
app/coding/
├── __init__.py
├── enums.py                 # ExecutionStatus, TestCaseStatus enums
├── REQUIREMENTS.md
├── evaluation/
│   ├── __init__.py
│   ├── comparator.py        # Output comparison (actual vs expected)
│   └── scorer.py            # Weighted score calculation + feedback generation
├── execution/
│   ├── __init__.py
│   ├── contracts.py         # ExecuteSubmissionCommand, ExecutionResult DTOs
│   ├── service.py           # ExecutionService (523 lines) — lifecycle orchestrator
│   └── state_machine.py     # Status transition validation
├── persistence/
│   ├── __init__.py
│   ├── entities.py          # Domain entities
│   ├── mappers.py           # Entity ↔ ORM mappers
│   ├── models.py            # SQLAlchemy ORM models
│   ├── protocols.py         # Repository protocols
│   └── repositories.py      # Repository implementations
└── sandbox/
    ├── __init__.py
    ├── contracts.py         # SandboxExecutionRequest/Result DTOs
    ├── docker_runner.py     # Docker container execution
    ├── executor.py          # SandboxExecutor orchestration
    ├── output_parser.py     # Parse container stdout/stderr
    └── sanitizer.py         # Code sanitization
```

#### Public Interfaces

- `ExecutionService.execute(command)` → Full execution lifecycle (designed for Celery worker, not request cycle)

#### Domain Services

- `ExecutionService` — Orchestrates: acquire lock → pending→running → execute per test case → compare → score → persist
- `SandboxExecutor` — Manages Docker container lifecycle for code execution
- `compare_outputs()` — Output comparison function
- `calculate_score()` / `generate_feedback()` — Weighted scoring + feedback

#### Persistence Classes

- `CodeSubmissionRepository` — Code submissions CRUD
- `CodeExecutionResultRepository` — Per-test-case results CRUD

#### Contracts

- `ExecuteSubmissionCommand` — Submission data + test cases
- `ExecutionResult` — Final status, score, per-test-case results
- `SandboxExecutionRequest/Result` — Docker execution I/O
- `TestCase`, `TestCaseExecutionResult`

#### Enums

- `ExecutionStatus` (pending, running, passed, failed, error, timeout, memory_exceeded) — maps to `code_execution_status` PG enum
- `TestCaseStatus` (passed, failed, timeout, memory_exceeded, runtime_error)

#### External Dependencies

- `app.config.settings` — Sandbox resource limits, Docker images
- `app.shared.observability` — Logging, metrics
- `app.shared.errors` — Error types

---

### 2.7 config

**Purpose:** Centralized application configuration loaded from environment variables with Pydantic validation. Supports dev/staging/prod environments.

#### Files

```
app/config/
├── __init__.py
├── constants.py             # Domain constants (max sizes, enums, pagination)
├── environments.py          # EnvironmentConfig (dev/staging/prod behavior)
├── feature_flags.py         # FeatureFlags (immutable runtime toggles)
├── README.md
├── REQUIREMENTS.md
├── security.py              # SecurityConfig, CORSConfig, PasswordPolicy
└── settings.py              # Master Settings class (419 lines)
```

#### Settings Categories

- `AppSettings` — env, debug, name, version, base_url
- `DatabaseSettings` — connection URL, pool config, query timeout
- `RedisSettings` — URL, pool, TTL, health check interval
- `QdrantSettings` — URL, API key, collection, embedding dim
- `LLMSettings` — Provider selection, API keys, model routing by use case, temperature/tokens/timeout
- `SandboxSettings` — Docker images, time/memory/process limits
- `SecuritySettings` — JWT config, password hashing, secure headers
- `AudioSettings` — Silence threshold, transcription provider, confidence threshold
- `RateLimitSettings` — Login/API rate limits, concurrent interview limits
- `FeatureFlagsSettings` — Feature toggles
- `Settings` (master) — Combines all above via `Settings.load()`

#### Key Constants (constants.py)

- `SUPPORTED_LANGUAGES` = ["cpp", "java", "python3"]
- `AUDIO_SAMPLE_RATE` = 16000
- `MAX_EXCHANGES_PER_INTERVIEW` = 50
- `API_V1_PREFIX` = "/api/v1"
- Pagination defaults, password length rules, file size constants

#### Feature Flags

- `ENABLE_AI_EVALUATION` — AI-powered scoring
- `ENABLE_PROCTORING` — Proctoring signals
- `ENABLE_AUDIO_ANALYSIS` — Audio behavioral analysis
- `ENABLE_CODE_EXECUTION` — Sandboxed code execution
- `ENABLE_PRACTICE_MODE` — Practice interviews
- `ENABLE_HUMAN_OVERRIDE` — Reviewer score override
- `ENABLE_RESUME_PARSING` — Resume analysis

---

### 2.8 evaluation

**STATUS: REQUIREMENTS ONLY — NO PYTHON CODE**

#### Files

```
app/evaluation/
├── REQUIREMENTS.md
├── aggregation/
│   └── REQUIREMENTS.md
├── api/
│   └── REQUIREMENTS.md
├── persistence/
│   └── REQUIREMENTS.md
├── scoring/
│   └── REQUIREMENTS.md
└── snapshots/
    └── REQUIREMENTS.md
```

**Purpose:** Per-exchange rubric-based evaluation, dimension scoring, weighted aggregation, and final interview result computation with snapshot immutability. See SCORING-ARCHITECTURE.md.

**Owned Tables:** `evaluations`, `evaluation_dimension_scores`, `interview_results`, `supplementary_reports`

---

### 2.9 interview

**STATUS: REQUIREMENTS ONLY — NO PYTHON CODE**

#### Files

```
app/interview/
├── REQUIREMENTS.md
├── api/
│   └── REQUIREMENTS.md
├── exchanges/
│   └── REQUIREMENTS.md
├── orchestration/
│   └── REQUIREMENTS.md
├── persistence/
│   └── REQUIREMENTS.md
├── realtime/
│   └── REQUIREMENTS.md
└── session/
    └── REQUIREMENTS.md
```

**Purpose:** Interview session management, exchange lifecycle, question orchestration, real-time WebSocket communication, adaptive difficulty progression.

**Owned Tables:** `interview_submissions`, `interview_exchanges`, `interview_submission_windows`

---

### 2.10 persistence

**Purpose:** Infrastructure persistence layer providing client initialization, health checks, and base abstractions for PostgreSQL, Redis, and Qdrant.

#### Files

```
app/persistence/
├── REQUIREMENTS.md
├── postgres/
│   ├── __init__.py          # Re-exports (get_db_session, init_engine, etc.)
│   ├── base.py              # SQLAlchemy Base + import_all_models()
│   ├── engine.py            # Engine creation with retry/pooling (285 lines)
│   ├── health.py            # Postgres health check endpoint
│   └── session.py           # Session factory, get_db_session dependency, execute_with_retry
├── qdrant/
│   ├── __init__.py
│   ├── client.py            # Qdrant client init/cleanup (222 lines)
│   ├── collections.py       # Collection management
│   ├── health.py            # Qdrant health check
│   └── operations.py        # Vector search operations
└── redis/
    ├── __init__.py
    ├── client.py            # Redis client init/cleanup
    ├── health.py            # Redis health check
    ├── locks.py             # Distributed locks
    └── operations.py        # Redis get/set/pipeline operations
```

#### Key Patterns

**PostgreSQL:**
- `create_db_engine(config)` — Engine with QueuePool, pre-ping, query timeout, exponential backoff retry (3 attempts)
- `init_engine(config)` → Global singleton engine
- `init_session_factory()` → `SessionLocal` sessionmaker bound to engine
- `get_db_session()` → FastAPI dependency (read-only, always closes)
- `get_db_session_with_commit()` → FastAPI dependency (auto-commit, rollback on error)
- `db_session_context()` → Context manager for non-FastAPI use
- `execute_with_retry()` — Retries on `OperationalError`, not on `IntegrityError`
- `Base` — SQLAlchemy declarative base for all ORM models
- `import_all_models()` — Imports admin, ai/prompts, coding models (others TODO)

**Redis:**
- `create_redis_client(config)` — Connection pool + retry
- `init_redis_client()` → Global singleton
- Distributed locks (`locks.py`)
- Key-value operations (`operations.py`)

**Qdrant:**
- `create_qdrant_client(config)` — Client with retry
- `init_qdrant_client()` → Global singleton
- Collection management, vector search operations

---

### 2.11 proctoring

**STATUS: REQUIREMENTS ONLY — NO PYTHON CODE**

#### Files

```
app/proctoring/
├── REQUIREMENTS.md
├── ingestion/
│   └── REQUIREMENTS.md
├── persistence/
│   └── REQUIREMENTS.md
├── risk_model/
│   └── REQUIREMENTS.md
└── rules/
    └── REQUIREMENTS.md
```

**Purpose:** Integrity monitoring — tab switching detection, screen recording, presence detection, audio anomaly detection, risk scoring. All signals are **advisory only** (NR-1, NFR-14).

**Owned Tables:** `proctoring_events`, `media_artifacts`

---

### 2.12 question

**STATUS: REQUIREMENTS ONLY — NO PYTHON CODE**

#### Files

```
app/question/
├── REQUIREMENTS.md
├── generation/
│   └── REQUIREMENTS.md
├── persistence/
│   └── REQUIREMENTS.md
├── prompting/
│   └── REQUIREMENTS.md
├── retrieval/
│   └── REQUIREMENTS.md
└── selection/
    └── REQUIREMENTS.md
```

**Purpose:** Question bank management, AI-powered question generation, semantic similarity search (via Qdrant embeddings), adaptive question selection, repetition prevention.

**Owned Tables:** `questions`, `question_topics`, `question_overrides`

---

### 2.13 shared

**Purpose:** Cross-module primitives with zero business logic. Provides error types, authentication context, and observability utilities used by all other modules.

#### Files

```
app/shared/
├── __init__.py
├── REQUIREMENTS.md
├── auth_context/
│   ├── __init__.py
│   ├── builder.py           # IdentityContext builder from JWT claims
│   ├── config.py            # Auth config (public key paths, etc.)
│   ├── context.py           # DEPRECATED AuthContext (→ use models.py)
│   ├── dependencies.py      # FastAPI deps: get_identity, require_admin, etc.
│   ├── middleware.py         # IdentityInjectionMiddleware
│   ├── models.py            # IdentityContext, UserType, AdminRole (230 lines)
│   ├── registry.py          # Public key registry
│   ├── scope.py             # Organization scope validation
│   └── websocket.py         # WebSocket identity extraction
├── errors/
│   ├── __init__.py
│   ├── classification.py    # Error classification logic
│   ├── config.py            # Error response config
│   ├── exceptions.py        # Full error hierarchy (664 lines)
│   └── serializers.py       # Error → JSON serialization
└── observability/
    ├── __init__.py
    ├── config.py            # Logging/telemetry config
    ├── logging.py           # StructuredFormatter + ContextLogger (323 lines)
    ├── metrics.py           # Prometheus metrics
    ├── redaction.py         # PII redaction for logs
    ├── telemetry.py         # OpenTelemetry integration
    └── tracing.py           # Distributed tracing
```

#### Error Hierarchy (exceptions.py)

```
BaseError (error_code, message, request_id, metadata, http_status_code)
├── ApplicationError (backward-compatible alias)
├── AuthenticationError (401)
├── AuthorizationError (403)
├── TenantIsolationViolation (403)
├── ValidationError (422)
├── NotFoundError (404)
├── ConflictError (409)
├── RateLimitError (429)
├── InfrastructureError (503)
├── AIProviderError (502)
├── SandboxError (500)
├── InternalServerError (500)
├── DomainInvariantViolation (422)
├── ProctoringViolation (403)
└── TemplateImmutabilityViolation (409)
```

#### Identity Context (models.py)

- `UserType` enum: ADMIN, CANDIDATE (mutually exclusive)
- `AdminRole` enum: SUPERADMIN, ADMIN, READ_ONLY
- `IdentityContext` (frozen dataclass): user_id, user_type, organization_id, admin_role, token_version, issued_at, expires_at
  - Invariants: Admin MUST have org_id + admin_role; Candidate MUST NOT
  - Methods: `is_admin()`, `is_candidate()`, `is_superadmin()`, `can_access_organization(org_id)`
- `TaskContext` — Serializable subset for Celery/async task propagation

#### Observability

- `StructuredFormatter` — JSON log formatter with consistent schema
- `ContextLogger` — Logger wrapper with automatic context injection (request_id, user_id, org_id, event_type, latency_ms, metadata)
- `metrics` — Prometheus counter/histogram metrics
- `redaction` — PII field redaction for safe logging

---

## 3. Shared Infrastructure

### Base Patterns & Utilities

| Pattern | Location | Description |
|---------|----------|-------------|
| **Declarative Base** | `persistence/postgres/base.py` | Single `Base` for all ORM models |
| **Session Management** | `persistence/postgres/session.py` | `get_db_session`, `get_db_session_with_commit`, `db_session_context` |
| **Retry Logic** | `persistence/postgres/engine.py` | Exponential backoff (3 attempts) for engine creation |
| **Repository Protocol** | `admin/domain/protocols.py`, `coding/persistence/protocols.py` | Abstract interfaces (Python Protocols) for repositories |
| **Entity ↔ Model Mappers** | `admin/persistence/mappers.py`, `coding/persistence/mappers.py` | Bidirectional mapping between domain entities and ORM models |
| **Error Hierarchy** | `shared/errors/exceptions.py` | Unified error types with HTTP status codes |
| **Identity Context** | `shared/auth_context/models.py` | Immutable frozen dataclass from JWT claims |
| **Structured Logging** | `shared/observability/logging.py` | JSON-formatted with request correlation |
| **DI Re-exports** | `bootstrap/dependencies.py` | Convenient single-import for common dependencies |
| **Override Pattern** | `admin/domain/entities.py` | Super-org base content + per-tenant override JSONB |

### Architectural Invariants

1. **Domain services have NO database imports** — only protocol interfaces
2. **API routes have NO business logic** — delegate to domain services
3. **Persistence layer uses SQLAlchemy ORM only** — no raw SQL in repositories
4. **All errors inherit from BaseError** — consistent error response format
5. **Multi-tenant isolation enforced at every layer** — IdentityContext carries org_id
6. **Immutability enforced on finalized entities** — templates, transcripts, evaluations

---

## 4. Dependency Injection Setup

### Application Bootstrap Flow

```
main.py
  → app.bootstrap.app.create_app()
    → FastAPI(lifespan=lifespan)
    → register_middleware(app)     # RequestContext → Logging → CORS → GZip → Identity
    → register_routers(app)       # auth + admin (others pending)
    → register_exception_handlers(app)  # BaseError → ValidationError → HTTPException
```

### Lifespan (Startup/Shutdown)

```
Startup:
  1. init_engine(settings.database)      → Global Postgres engine
  2. init_session_factory()              → Global SessionLocal
  3. init_redis_client(settings.redis)   → Global Redis client
  4. init_qdrant_client(settings.qdrant) → Global Qdrant client

Shutdown:
  1. cleanup_engine()
  2. cleanup_redis()
  3. cleanup_qdrant()
```

### Per-Request DI

```python
# Database session (via FastAPI Depends)
db: Session = Depends(get_db_session)          # Read-only
db: Session = Depends(get_db_session_with_commit)  # Auto-commit

# Identity (via FastAPI Depends)
identity: IdentityContext = Depends(get_identity)
identity: IdentityContext = Depends(require_admin)
identity: IdentityContext = Depends(require_candidate)
identity: IdentityContext = Depends(require_superadmin)

# Service construction (per-route, in dependencies.py or inline)
service = build_template_service(db, identity)  # admin module
auth_service = _build_auth_service(session)     # auth module
```

---

## 5. Database Schema Summary

### All Tables (48 tables)

| Table | Module Owner | Purpose |
|-------|-------------|---------|
| `users` | auth | Base user accounts |
| `admins` | auth | Admin-specific data + role |
| `candidates` | auth | Candidate-specific data + plan |
| `organizations` | admin | Multi-tenant organizations |
| `refresh_tokens` | auth | JWT refresh token storage |
| `auth_audit_log` | auth | Immutable auth event log |
| `audit_logs` | admin | General audit trail |
| `interview_templates` | admin | Interview structure definitions |
| `interview_template_roles` | admin | Template ↔ role mapping |
| `interview_template_rubrics` | admin | Template ↔ rubric mapping |
| `template_overrides` | admin | Tenant-specific template overrides |
| `rubrics` | admin | Evaluation rubric definitions |
| `rubric_dimensions` | admin | Rubric dimension definitions + weights |
| `rubric_overrides` | admin | Tenant-specific rubric overrides |
| `roles` | admin | Job roles |
| `role_overrides` | admin | Tenant-specific role overrides |
| `role_topics` | admin | Role ↔ topic mapping |
| `role_coding_topics` | admin | Role ↔ coding topic mapping |
| `topics` | admin | Interview topics |
| `topic_overrides` | admin | Tenant-specific topic overrides |
| `questions` | question | Question bank |
| `question_topics` | question | Question ↔ topic mapping |
| `question_overrides` | question | Tenant-specific question overrides |
| `coding_problems` | admin/coding | Coding problem definitions |
| `coding_test_cases` | coding | Test cases for coding problems |
| `coding_topics` | admin | Coding topic taxonomy |
| `coding_problem_topics` | admin | Problem ↔ topic mapping |
| `coding_problem_overrides` | admin | Tenant-specific problem overrides |
| `code_submissions` | coding | Candidate code submissions |
| `code_execution_results` | coding | Per-test-case execution results |
| `interview_submissions` | interview | Interview session records |
| `interview_exchanges` | interview | Individual Q&A exchanges |
| `interview_submission_windows` | interview | Scheduling windows |
| `window_role_templates` | admin | Window ↔ role ↔ template mapping |
| `interview_results` | evaluation | Final frozen interview scores |
| `evaluations` | evaluation | Per-exchange AI evaluations |
| `evaluation_dimension_scores` | evaluation | Per-dimension scores |
| `supplementary_reports` | evaluation | Optional detailed reports |
| `audio_analytics` | audio | Per-exchange audio analysis |
| `proctoring_events` | proctoring | Integrity monitoring events |
| `media_artifacts` | proctoring | Audio/video/screen recordings |
| `embeddings` | question | Vector embedding references |
| `models` | ai | AI model registry |
| `prompt_templates` | ai | Prompt template storage |
| `resumes` | interview | Candidate resumes |
| `job_descriptions` | admin | Job descriptions |
| `programming_languages` | coding | Supported languages |
| `problem_language_templates` | coding | Code templates per language |
| `source_topics` | admin | External source topic mapping |

### PostgreSQL ENUM Types (21)

`admin_role`, `admin_status`, `candidate_plan`, `code_execution_status`, `coding_topic_type`, `difficulty_level`, `evaluator_type`, `interview_mode`, `interview_scope`, `media_type`, `organization_plan`, `organization_status`, `organization_type`, `problem_pipeline_status`, `problem_source`, `proctoring_severity`, `question_type`, `report_type`, `submission_status`, `template_scope`, `user_status`

---

## 6. Audio Module Deep-Dive

### Architecture

```
audio/
├── ingestion/    → Audio stream entry point, format normalization, silence detection
├── transcription/ → Provider-agnostic STT (Whisper, Google, Azure, local)
├── analysis/     → NLP completeness classifier, filler detection, speech rate, sentiment, intent classification
└── persistence/  → AudioAnalyticsRepository (UNIQUE per exchange, immutability)
```

### Core Data Flow

```
WebRTC Audio Stream
  → ingestion: normalize to 16kHz mono, detect silence
    → transcription: STT provider (streaming/batch)
      → analysis: completeness + fillers + speech rate + sentiment + intent
        → persistence: write audio_analytics
          → emit AudioSignal to interview/orchestration
```

### Key Contracts (Planned)

| Contract | Purpose |
|----------|---------|
| `AudioStreamRequest` | Ingestion input (exchange_id, audio_chunk, sample_rate) |
| `AudioSessionControl` | Session lifecycle (start/pause/resume/stop) |
| `SilenceDetectedEvent` | Emitted when silence threshold crossed |
| `TranscriptionRequest` | STT input (audio_data, sample_rate, language) |
| `TranscriptionResult` | STT output (transcript, confidence, segments) |
| `CompletenessResult` | NLP output (speech_state, sentence_complete, confidence) |
| `FillerDetectionResult` | Filler count + rate + positions |
| `SpeechRateResult` | WPM, pause count, speech duration |
| `SentimentResult` | Score, confidence level, hesitation/frustration flags |
| `IntentClassificationResult` | Intent (ANSWER/CLARIFICATION/REPEAT/POST_ANSWER/INVALID/INCOMPLETE/UNKNOWN) |
| `AudioSignal` | Composite signal emitted to orchestrator |
| `AudioAnalytics` | Persisted analytics record |
| `AudioAnalyticsCreate` | Repository create input |

### Critical Invariants

1. **Signal generator, not decision-maker** — Audio emits signals; orchestration decides actions
2. **One analytics record per exchange** — UNIQUE constraint on `interview_exchange_id`
3. **Transcript immutability** — No updates after `transcript_finalized=true`
4. **Silence ≠ completion** — Silence triggers completeness *evaluation*, not direct completion
5. **Rule-based NLP** — spaCy for completeness, not LLMs (deterministic, <500ms)
6. **Intent classification before business logic** — Must run before exchange creation
7. **Persist before emit** — Analytics written to DB before signal emitted to orchestrator

### Concurrency Concerns

- Silence timer vs new audio race condition (atomic flag check)
- Duplicate analytics creation (UNIQUE constraint + catch IntegrityError)
- Update during finalization (SELECT FOR UPDATE / optimistic locking)
- Session cleanup while processing (check exchange status before accepting)

### External Dependencies (Planned)

- `spaCy` (en_core_web_sm) — NLP dependency parsing
- `VADER` / `TextBlob` — Sentiment analysis
- `pydub` + `scipy` + `numpy` — Audio processing (in requirements.txt)
- OpenAI Whisper / Google Cloud Speech / Azure Speech — STT providers
- `app.shared.errors`, `app.shared.observability`, `app.persistence.postgres`
- `app.interview.orchestration` — Signal consumer (downstream)
- `app.evaluation.scoring` — Analytics consumer (downstream)

### Config (settings.py → AudioSettings)

- `silence_threshold_ms` = 3000
- `silence_confidence_threshold` = 0.8
- `audio_transcription_provider` = "whisper"
- `audio_confidence_threshold` = 0.7
- `max_transcript_length` = 10000
- `enable_audio_analysis` = True
- `audio_chunk_size_ms` = 500

---

## 7. SRS Highlights

### Key Functional Requirements

- **FR-5.2:** Voice-based interviews (SHALL)
- **FR-5.4:** Basic voice analysis signals (COULD — optional)
- **FR-5.5:** SHALL NOT perform emotion recognition or eye-tracking
- **FR-6.2:** Rubric-based scoring per response (SHALL)
- **FR-6.6:** Human review before consequential decisions (SHALL)
- **FR-9.5:** Audio anomaly detection — multiple voices (COULD)

### Audio-Relevant Non-Functional Requirements

- **NFR-1:** 300ms p95 for non-media interactions
- **NFR-2:** 5s p95 for AI responses, 4s fallback trigger
- **NFR-9:** Explicit consent before interview initiation
- **NFR-13.1:** Captions/transcripts for audio interactions
- **NFR-14:** Scoring/proctoring outputs are advisory only

### Prohibitions (NR)

- NR-1: No autonomous hiring decisions
- NR-2: No biometric identity data
- NR-3: No psychological/behavioral trait inference
- NR-4: No cross-tenant data exposure
- NR-5: No untrusted code outside sandboxes

---

## 8. Requirements.txt Summary

| Category | Packages |
|----------|----------|
| **Web Framework** | fastapi 0.109, uvicorn 0.27, python-multipart |
| **Database/ORM** | sqlalchemy 2.0.25, asyncpg 0.29, psycopg2-binary 2.9.9, alembic 1.13 |
| **Redis** | redis 5.0.1 (hiredis) |
| **Vector DB** | qdrant-client 1.12.1 |
| **Config** | pydantic 2.5.3, pydantic-settings 2.1, python-dotenv |
| **Auth/Security** | pyjwt 2.8, passlib 1.7.4, bcrypt 4.1.2, python-jose 3.3 |
| **LLM** | groq 0.4.2, httpx 0.26 |
| **Audio** | pydub 0.25.1, scipy 1.12, numpy 1.26.3 |
| **Logging** | structlog 24.1, python-json-logger 2.0.7, prometheus-client 0.19 |
| **Task Queue** | celery 5.3.6 (redis) |
| **Testing** | pytest 7.4.4, pytest-asyncio 0.23.3, pytest-cov 4.1 |
| **Code Quality** | black 24.1, flake8 7.0, mypy 1.8, isort 5.13 |
| **Utilities** | python-dateutil 2.8.2, aiofiles 23.2.1 |

**Notable gaps:** `spaCy` is NOT in requirements.txt (needed for audio analysis completeness classifier). `openai-whisper` is commented out.

---

## 9. Implementation Status Matrix

| Module | Submodule | API Routes | Domain Services | Persistence | Contracts | Tests |
|--------|-----------|------------|-----------------|-------------|-----------|-------|
| **admin** | api | ✅ | — | — | ✅ | — |
| | domain | — | ✅ | — | — | — |
| | persistence | — | — | ✅ | — | — |
| | validation | — | ✅ | — | — | — |
| **ai** | llm | — | ✅ (5 providers) | — | ✅ | — |
| | prompts | — | ✅ | ✅ | ✅ | — |
| | telemetry | — | ✅ | — | ✅ | — |
| **audio** | ingestion | ❌ | ❌ | ❌ | ❌ | ❌ |
| | transcription | ❌ | ❌ | ❌ | ❌ | ❌ |
| | analysis | ❌ | ❌ | ❌ | ❌ | ❌ |
| | persistence | ❌ | ❌ | ❌ | ❌ | ❌ |
| **auth** | api | ✅ | — | — | ✅ | — |
| | domain | — | ✅ | — | ✅ | — |
| | persistence | — | — | ✅ | — | — |
| **bootstrap** | — | ✅ | ✅ | — | — | — |
| **coding** | execution | — | ✅ | — | ✅ | — |
| | evaluation | — | ✅ | — | — | — |
| | persistence | — | — | ✅ | ✅ | — |
| | sandbox | — | ✅ | — | ✅ | — |
| **config** | — | — | ✅ | — | — | — |
| **evaluation** | all | ❌ | ❌ | ❌ | ❌ | ❌ |
| **interview** | all | ❌ | ❌ | ❌ | ❌ | ❌ |
| **persistence** | postgres | — | — | ✅ | — | — |
| | redis | — | — | ✅ | — | — |
| | qdrant | — | — | ✅ | — | — |
| **proctoring** | all | ❌ | ❌ | ❌ | ❌ | ❌ |
| **question** | all | ❌ | ❌ | ❌ | ❌ | ❌ |
| **shared** | auth_context | — | ✅ | — | ✅ | — |
| | errors | — | ✅ | — | — | — |
| | observability | — | ✅ | — | — | — |

**Legend:** ✅ = Implemented | ❌ = Requirements only (no code) | — = N/A for this submodule

---

*End of Comprehensive Repository Audit*
