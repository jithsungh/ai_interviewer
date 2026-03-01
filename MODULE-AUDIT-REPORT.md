# Comprehensive Module Audit — `app/`

> Generated from source code analysis of all 13 top-level modules under `app/`.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Dependency Graph](#2-module-dependency-graph)
3. [Module-by-Module Audit](#3-module-by-module-audit)
   - [3.1 admin](#31-admin)
   - [3.2 ai](#32-ai)
   - [3.3 audio](#33-audio)
   - [3.4 auth](#34-auth)
   - [3.5 bootstrap](#35-bootstrap)
   - [3.6 coding](#36-coding)
   - [3.7 config](#37-config)
   - [3.8 evaluation](#38-evaluation)
   - [3.9 interview](#39-interview)
   - [3.10 persistence](#310-persistence)
   - [3.11 proctoring](#311-proctoring)
   - [3.12 question](#312-question)
   - [3.13 shared](#313-shared)
4. [Implementation Status Matrix](#4-implementation-status-matrix)
5. [Database Ownership Map](#5-database-ownership-map)
6. [Key Architectural Invariants](#6-key-architectural-invariants)

---

## 1. Architecture Overview

| Aspect            | Detail                                                      |
|-------------------|-------------------------------------------------------------|
| Framework         | FastAPI (Python 3.11+)                                      |
| ORM               | SQLAlchemy 2.x (async sessions)                             |
| Relational DB     | PostgreSQL (50+ tables, 21+ enum types)                     |
| Cache / Broker    | Redis (sessions, locks, caching, Celery broker)             |
| Vector DB         | Qdrant (768-dim embeddings, all-mpnet-base-v2)              |
| AI Providers      | OpenAI, Anthropic, Groq, Gemini (provider abstraction)      |
| Auth              | JWT (RS256/HS256), bcrypt/argon2id                          |
| Sandbox           | Docker containers (C++, Java, Python3), seccomp, no-network |
| Architecture      | Multi-tenant, modular, event-pattern signals                 |
| Total .py files   | ~160+                                                       |
| Settings          | pydantic-settings (10 sub-settings classes)                  |

---

## 2. Module Dependency Graph

```
Arrows = "imports from"

config ←── persistence ←── shared
  ↑            ↑              ↑
  │            │              │
  ├── ai ──────┤              │
  │            │              │
  ├── auth ────┤──────────────┤
  │            │              │
  ├── admin ───┤──────────────┤
  │            │              │
  ├── coding ──┤──────────────┤
  │            │              │
  ├── audio ───┤──────────────┤
  │                           │
  └── question (→ ai) ───────┘

bootstrap → config, shared, persistence, auth, admin, audio
```

### Cross-Module Import Map (from `grep "from app\." **/*.py`)

| Source Module    | Imports From                                                   |
|------------------|----------------------------------------------------------------|
| **admin**        | `shared.auth_context`, `shared.errors`, `shared.observability`, `persistence.postgres` |
| **ai**           | `shared.errors`, `shared.observability`, `persistence.postgres`, `config.settings` |
| **audio**        | `shared.errors`, `shared.observability`                        |
| **auth**         | `shared.errors`, `shared.auth_context`, `shared.observability`, `config`, `bootstrap.dependencies` |
| **bootstrap**    | `config`, `shared.observability`, `shared.auth_context`, `persistence.postgres`, `persistence.redis`, `persistence.qdrant`, `auth.api`, `admin.api`, `audio.ingestion.api`, `audio.transcription.api` |
| **coding**       | `config.settings`, `config.constants`, `shared.errors`, `shared.observability`, `persistence.postgres` |
| **config**       | (none — leaf module)                                           |
| **persistence**  | `config.settings`, `shared.errors`                             |
| **question**     | `ai.llm`, `ai.prompts`, `ai.llm.errors`, `ai.llm.utils`      |
| **shared**       | `persistence.redis` (lazy, for ConnectionRegistry), `config` (lazy, for auth dependencies) |

### Forbidden Import Rules (from REQUIREMENTS.md)

| Module     | MUST NOT Import                                           |
|------------|-----------------------------------------------------------|
| ai         | interview, evaluation, admin, coding, question            |
| persistence| Any domain module                                         |
| shared     | Any domain module                                         |
| coding     | interview, evaluation (must not modify interview_exchanges)|
| audio      | interview, evaluation (must not write to exchanges/evaluations) |

---

## 3. Module-by-Module Audit

---

### 3.1 admin

**Purpose:** Configuration/control-plane boundary — templates, rubrics, roles, topics, questions, coding problems, windows, override management.

#### Files (16 .py files)

| Submodule    | Files                                                                    |
|--------------|--------------------------------------------------------------------------|
| `api/`       | `__init__.py`, `contracts.py`, `dependencies.py`, `routes.py`           |
| `domain/`    | `__init__.py`, `authorization.py`, `entities.py`, `protocols.py`, `services.py` |
| `persistence/` | `__init__.py`, `mappers.py`, `models.py`, `repositories.py`           |
| `validation/`  | `__init__.py`, `cross_reference_validator.py`, `override_validator.py`, `pre_activation_validator.py`, `result.py`, `rubric_validator.py`, `template_validator.py` |

#### Key Classes & Interfaces

| Class / Protocol              | File                          | Role                                              |
|-------------------------------|-------------------------------|----------------------------------------------------|
| `TemplateService`             | `domain/services.py`          | Template CRUD, versioning, activation, override mgmt |
| `RubricService`               | `domain/services.py`          | Rubric CRUD, dimension weight validation            |
| `RoleService`                 | `domain/services.py`          | Role CRUD with RBAC                                |
| `TopicService`                | `domain/services.py`          | Topic CRUD, cycle detection in parent hierarchy     |
| `WindowService`               | `domain/services.py`          | Window scheduling, overlap detection                |
| `OverrideService`             | `domain/services.py`          | Tenant override CRUD, immutable field enforcement   |
| `TemplateRepository` (Protocol) | `domain/protocols.py`       | Abstract template CRUD + role/rubric mappings       |
| `RubricRepository` (Protocol)   | `domain/protocols.py`       | Abstract rubric CRUD + dimensions                   |
| `RoleRepository` (Protocol)     | `domain/protocols.py`       | Abstract role CRUD                                  |
| `TopicRepository` (Protocol)    | `domain/protocols.py`       | Abstract topic + coding topic CRUD                  |
| `QuestionRepository` (Protocol) | `domain/protocols.py`       | Abstract question CRUD                              |
| `WindowRepository` (Protocol)   | `domain/protocols.py`       | Abstract window CRUD + overlap detection            |
| `SubmissionRepository` (Protocol)| `domain/protocols.py`       | Read-only immutability checks                       |
| `OverrideRepository` (Protocol)  | `domain/protocols.py`       | Generic override CRUD for all content types         |
| `AuditLogRepository` (Protocol)  | `domain/protocols.py`       | Insert-only audit logging                           |
| `authorize_admin_operation()`    | `domain/authorization.py`   | RBAC enforcement using IdentityContext              |

#### Domain Entities (dataclasses)

`Template`, `TemplateRole`, `TemplateRubric`, `Rubric`, `RubricDimension`, `Role`, `Topic`, `CodingTopic`, `Question`, `CodingProblem`, `Window`, `WindowRoleTemplate`, `OverrideRecord`

#### Enums

`TemplateScope`, `InterviewScope`, `DifficultyLevel`, `QuestionType`, `CodingTopicType`, `ContentType`

#### API Contracts (Pydantic)

`TemplateCreateRequest`, `TemplateUpdateRequest`, `TemplateResponse`, `TemplateDetailResponse`, `TemplateListResponse`, `RubricCreateRequest`, `RubricUpdateRequest`, `RubricResponse`, `DimensionRequest`, `DimensionResponse`, `RoleCreateRequest`, `RoleResponse`, `TopicCreateRequest`, `TopicResponse`, `QuestionCreateRequest`, `QuestionResponse`, `CodingProblemCreateRequest`, `CodingProblemResponse`, `WindowCreateRequest`, `WindowResponse`, `OverrideCreateRequest`, `OverrideResponse`, `PaginationMeta`, `MetaInfo`

#### Tables Owned

`interview_templates`, `interview_template_roles`, `interview_template_rubrics`, `rubrics`, `rubric_dimensions`, `roles`, `topics`, `coding_topics`, `questions`, `coding_problems`, `interview_submission_windows`, `window_role_templates`, `template_overrides`, `rubric_overrides`, `role_overrides`, `topic_overrides`, `question_overrides`, `coding_problem_overrides`

#### Cross-Module Dependencies

- **Imports:** `shared.auth_context.models` (IdentityContext, AdminRole), `shared.errors`, `persistence.postgres.base` (Base)
- **Consumed by:** bootstrap (router), interview/orchestration, evaluation/scoring, question/selection

---

### 3.2 ai

**Purpose:** Provider-agnostic LLM abstraction layer — INFRASTRUCTURE ONLY, no domain knowledge.

#### Files (18 .py files)

| Submodule       | Files                                                                      |
|-----------------|----------------------------------------------------------------------------|
| `llm/`          | `__init__.py`, `base_provider.py`, `contracts.py`, `errors.py`, `provider_factory.py` |
| `llm/providers/`| `__init__.py`, `anthropic_provider.py`, `embedding_provider.py`, `gemini_provider.py`, `groq_provider.py`, `openai_provider.py` |
| `llm/utils/`    | `__init__.py`, `token_counter.py`                                          |
| `prompts/`      | `__init__.py`, `entities.py`, `errors.py`, `mappers.py`, `models.py`, `parser.py`, `protocols.py`, `renderer.py`, `repository.py`, `service.py` |
| `telemetry/`    | `__init__.py`, `aggregation.py`, `contracts.py`, `cost.py`, `errors.py`, `tracker.py` |

#### Key Classes & Interfaces

| Class / Function                | File                          | Role                                              |
|---------------------------------|-------------------------------|----------------------------------------------------|
| `BaseLLMProvider` (ABC)         | `llm/base_provider.py`       | Abstract provider: `generate_text()`, `generate_structured()`, `get_supported_models()` |
| `GroqProvider`                  | `llm/providers/groq_provider.py` | Groq API implementation                         |
| `OpenAIProvider`                | `llm/providers/openai_provider.py` | OpenAI API implementation                      |
| `AnthropicProvider`             | `llm/providers/anthropic_provider.py` | Anthropic API implementation                 |
| `GeminiProvider`                | `llm/providers/gemini_provider.py` | Gemini API implementation                      |
| `EmbeddingProvider`             | `llm/providers/embedding_provider.py` | Self-hosted embedding service                |
| `ProviderFactory`               | `llm/provider_factory.py`    | Factory for creating provider instances             |
| `PromptService`                 | `prompts/service.py`         | Prompt retrieval + rendering (public API for callers)|
| `PromptRenderer`                | `prompts/renderer.py`        | Jinja2-like variable substitution into templates    |
| `TemplateParser`                | `prompts/parser.py`          | Parses prompt template syntax                       |
| `SqlPromptTemplateRepository`   | `prompts/repository.py`      | SQLAlchemy implementation of PromptTemplateRepository|
| `TelemetryTracker`              | `telemetry/tracker.py`       | Span-based AI operation tracking                    |
| `TelemetrySpan`                 | `telemetry/tracker.py`       | Single AI operation span with timing/tokens/cost    |
| `CostEstimator`                 | `telemetry/cost.py`          | Per-model cost estimation                           |

#### Contracts (dataclasses)

`LLMRequest`, `LLMResponse`, `EmbeddingRequest`, `EmbeddingResponse`, `TranscriptionRequest`, `TranscriptionResponse`, `TelemetryData`

#### Entities

`PromptTemplate`, `RenderedPrompt`, `PromptType` enum (`question_generation`, `evaluation`, `resume_parsing`, `jd_parsing`, `report_generation`, `clarification`)

#### Enums

`LLMProvider` (`groq`, `gemini`, `openai`, `anthropic`, `local`), `LLMErrorType`, `OperationType`

#### Tables

- **Read-only:** `prompt_templates` (writes managed by admin module)

#### Cross-Module Dependencies

- **Imports:** `config.settings`, `shared.errors`, `shared.observability`, `persistence.postgres.base` (Base, for PromptTemplateModel)
- **FORBIDDEN:** Must NOT import interview, evaluation, admin, coding, question
- **Consumed by:** `question.generation`, `evaluation.scoring` (future), `interview` (future)

---

### 3.3 audio

**Purpose:** Structured audio analytics signal generation — ingestion, transcription, behavioral analysis.

#### Files (22 .py files)

| Submodule          | Files                                                                    |
|--------------------|--------------------------------------------------------------------------|
| `ingestion/`       | `__init__.py`, `buffer_manager.py`, `contracts.py`, `exceptions.py`, `normalizer.py`, `service.py`, `session_manager.py`, `silence_detector.py` |
| `ingestion/api/`   | `__init__.py`, `contracts.py`, `dependencies.py`, `routes.py`           |
| `transcription/`   | `__init__.py`, `confidence.py`, `contracts.py`, `exceptions.py`, `protocols.py`, `provider_selector.py`, `service.py` |
| `transcription/api/`| `__init__.py`, `contracts.py`, `dependencies.py`, `routes.py`          |
| `transcription/providers/` | `__init__.py`, `google_speech.py`, `local_whisper.py`, `whisper.py` |
| `analysis/`        | (REQUIREMENTS.md only — **no .py files**)                               |
| `persistence/`     | (REQUIREMENTS.md only — **no .py files**)                               |

#### Key Classes

| Class                        | File                          | Role                                             |
|------------------------------|-------------------------------|--------------------------------------------------|
| `AudioIngestionService`      | `ingestion/service.py`        | Pipeline facade: validate → normalize → buffer → silence detect → transcription callback |
| `AudioSessionManager`        | `ingestion/session_manager.py`| In-memory session lifecycle management            |
| `AudioBufferManager`         | `ingestion/buffer_manager.py` | Ring-buffer audio windowing                       |
| `AudioNormalizer`            | `ingestion/normalizer.py`     | Resample to 16kHz mono, volume normalization      |
| `SilenceDetector`            | `ingestion/silence_detector.py`| RMS-based silence detection with configurable threshold |
| `TranscriptionService`       | `transcription/service.py`    | Provider-selecting, retry-enabled transcription facade |
| `TranscriptionProviderSelector` | `transcription/provider_selector.py` | Primary/fallback provider chain selection   |
| `WhisperProvider`            | `transcription/providers/whisper.py` | OpenAI Whisper API                         |
| `LocalWhisperProvider`       | `transcription/providers/local_whisper.py` | Local Whisper model                    |
| `GoogleSpeechProvider`       | `transcription/providers/google_speech.py` | Google Cloud Speech-to-Text            |

#### Contracts

`AudioChunk`, `AudioStreamRequest`, `AudioSessionControl`, `SilenceDetectedEvent`, `TranscriptionRequest`, `TranscriptionResult`, `TranscriptionConfig`

#### Tables Owned

- `audio_analytics` (UNIQUE on `interview_exchange_id`) — **not yet implemented in code**

#### Cross-Module Dependencies

- **Imports:** `shared.errors`, `shared.observability`
- **FORBIDDEN:** Must NOT write to `interview_exchanges`, `evaluations`, `interview_submissions`
- **Consumed by:** `interview/orchestration` (AudioSignal), `evaluation/scoring` (behavioral rubrics), `proctoring/audio_anomaly`

---

### 3.4 auth

**Purpose:** Single source of identity truth and access control enforcement.

#### Files (15 .py files)

| Submodule       | Files                                                                     |
|-----------------|---------------------------------------------------------------------------|
| `api/`          | `__init__.py`, `routes.py`                                                |
| `contracts/`    | `__init__.py`, `claims.py`, `enums.py`, `responses.py`, `schemas.py`     |
| `domain/`       | `__init__.py`, `auth_service.py`, `contracts.py`, `jwt_service.py`, `password_hasher.py`, `rbac_enforcer.py` |
| `persistence/`  | `__init__.py`, `admin_repository.py`, `audit_log_repository.py`, `candidate_repository.py`, `models.py`, `refresh_token_repository.py`, `user_repository.py` |

#### Key Classes

| Class                     | File                               | Role                                           |
|---------------------------|------------------------------------|-------------------------------------------------|
| `AuthService`             | `domain/auth_service.py`           | Registration, login, token refresh, logout (1024 lines) |
| `JWTService`              | `domain/jwt_service.py`            | JWT create/validate/decode (RS256/HS256)        |
| `PasswordHasher`          | `domain/password_hasher.py`        | bcrypt/argon2id hashing and verification        |
| `RBACEnforcer`            | `domain/rbac_enforcer.py`          | Role-based access control checks                |
| `UserRepository`          | `persistence/user_repository.py`   | User table CRUD                                 |
| `AdminRepository`         | `persistence/admin_repository.py`  | Admin table CRUD                                |
| `CandidateRepository`     | `persistence/candidate_repository.py` | Candidate table CRUD                         |
| `RefreshTokenRepository`  | `persistence/refresh_token_repository.py` | Refresh token lifecycle                   |
| `AuditLogRepository`      | `persistence/audit_log_repository.py` | Auth audit log insertion                     |

#### Contracts

**Commands:** `RegisterAdminCommand`, `RegisterCandidateCommand`, `LoginCommand`, `RefreshTokenCommand`, `LogoutCommand`, `ValidateTokenCommand`

**Results:** `AuthenticationResult`, `UserProfile`, `TokenValidationResult`

**Schemas (Pydantic):** `LoginRequest`, `RegisterAdminRequest`, `RegisterCandidateRequest`, `RefreshTokenRequest`, `TokenResponse`

#### Tables Owned

`users`, `admins`, `candidates`, `refresh_tokens`, `auth_audit_log`

#### Cross-Module Dependencies

- **Imports:** `shared.errors`, `shared.auth_context`, `shared.observability`, `config`, `bootstrap.dependencies`
- **Consumed by:** `shared.auth_context.dependencies` (lazy import of `JWTService` for token validation), `bootstrap` (router registration)

---

### 3.5 bootstrap

**Purpose:** Application assembly layer — FastAPI app creation, middleware, routers, lifespan, dependency injection.

#### Files (7 .py files)

| File                     | Role                                                   |
|--------------------------|---------------------------------------------------------|
| `__init__.py`            | Package init, `create_app` export                      |
| `app.py`                 | `create_app()` factory: create FastAPI → middleware → routers → exception handlers |
| `dependencies.py`        | Re-exports `get_db_session`, `get_identity`, `require_admin` from submodules |
| `exception_handlers.py`  | Global exception handlers (BaseError → JSON response, 422 validator, generic 500) |
| `lifespan.py`            | `@asynccontextmanager lifespan()`: init/cleanup Postgres, Redis, Qdrant |
| `middleware.py`          | `register_middleware()`: RequestID → CORS → Identity injection → logging |
| `router_registry.py`     | `register_routers()`: registers auth, admin, audio routers + health endpoints |

#### Currently Registered Routes

| Prefix                    | Module                       | Status        |
|---------------------------|------------------------------|---------------|
| `/api/v1/auth`            | `auth.api.routes`            | **Active**    |
| `/api/v1/admin`           | `admin.api.routes`           | **Active**    |
| `/api/v1/audio/ingestion` | `audio.ingestion.api.routes` | **Active**    |
| `/api/v1/audio/transcription` | `audio.transcription.api.routes` | **Active** |
| `/api/v1/interviews`      | `interview.api.routes`       | **Commented** |
| `/api/v1/questions`       | `question.api.routes`        | **Commented** |
| `/api/v1/evaluations`     | `evaluation.api.routes`      | **Commented** |
| `/api/v1/coding`          | `coding.api.routes`          | **Commented** |
| `/api/v1/proctoring`      | `proctoring.api.routes`      | **Commented** |
| `/health`                 | inline                       | **Active**    |
| `/health/database`        | inline                       | **Active**    |

#### Tables Owned

None — pure assembly.

#### Cross-Module Dependencies

- **Imports:** `config`, `shared.observability`, `shared.auth_context`, `persistence.postgres`, `persistence.redis`, `persistence.qdrant`, `auth.api.routes`, `admin.api.routes`, `audio.ingestion.api.routes`, `audio.transcription.api.routes`

---

### 3.6 coding

**Purpose:** Deterministic, isolated execution engine for untrusted candidate code.

#### Files (16 .py files)

| Submodule      | Files                                                                    |
|----------------|--------------------------------------------------------------------------|
| root           | `__init__.py`, `enums.py`                                                |
| `evaluation/`  | `__init__.py`, `comparator.py`, `scorer.py`                             |
| `execution/`   | `__init__.py`, `contracts.py`, `service.py`, `state_machine.py`         |
| `persistence/` | `__init__.py`, `entities.py`, `mappers.py`, `models.py`, `protocols.py`, `repositories.py` |
| `sandbox/`     | `__init__.py`, `contracts.py`, `docker_runner.py`, `executor.py`, `output_parser.py`, `sanitizer.py` |

#### Key Classes

| Class                    | File                         | Role                                              |
|--------------------------|------------------------------|---------------------------------------------------|
| `ExecutionService`       | `execution/service.py`       | Full lifecycle orchestrator: lock → run → compare → score → persist (523 lines) |
| `SandboxExecutor`        | `sandbox/executor.py`        | Docker container provisioning + execution + cleanup |
| `DockerRunner`           | `sandbox/docker_runner.py`   | Low-level Docker API wrapper                       |
| `OutputParser`           | `sandbox/output_parser.py`   | Parse execution stdout/stderr                      |
| `Sanitizer`              | `sandbox/sanitizer.py`       | Truncate/sanitize code output                      |
| `compare_outputs()`      | `evaluation/comparator.py`   | Output comparison (exact, float tolerance, sorted)  |
| `calculate_score()`      | `evaluation/scorer.py`       | Weighted scoring from test results                 |
| `generate_feedback()`    | `evaluation/scorer.py`       | Human-readable feedback from scores                |
| `ExecutionStateMachine`  | `execution/state_machine.py` | `is_valid_transition()`, `validate_transition()`   |
| `CodeSubmissionRepository` | `persistence/repositories.py` | SQLAlchemy CRUD for code_submissions             |
| `CodeExecutionResultRepository` | `persistence/repositories.py` | SQLAlchemy CRUD for code_execution_results  |

#### Enums

`ExecutionStatus` (`pending`, `running`, `passed`, `failed`, `error`, `timeout`, `memory_exceeded`), `TestCaseStatus`

#### Contracts

`ExecuteSubmissionCommand`, `ExecutionResult`, `TestCase`, `TestCaseExecutionResult`, `SandboxExecutionRequest`, `SandboxExecutionResult`

#### Entities

`CodeSubmission`, `CodeExecutionResult` (domain dataclasses, persistence-decoupled)

#### Tables Owned

`code_submissions` (UNIQUE on `interview_exchange_id`), `code_execution_results`

#### Cross-Module Dependencies

- **Imports:** `config.settings` (SandboxSettings), `config.constants` (SUPPORTED_LANGUAGES), `shared.errors.exceptions` (SandboxExecutionError, SandboxTimeoutError), `shared.observability` (logging, metrics), `persistence.postgres.base` (Base)
- **FORBIDDEN:** Must NOT execute code in FastAPI process, must NOT modify `interview_exchanges`

---

### 3.7 config

**Purpose:** Centralized configuration management — settings, feature flags, constants, security policies.

#### Files (5 .py files)

| File               | Role                                                          |
|--------------------|---------------------------------------------------------------|
| `__init__.py`      | `settings` singleton export                                   |
| `constants.py`     | Immutable domain constants (139 lines): `SUPPORTED_LANGUAGES`, `MAX_CODE_SIZE_BYTES`, `MIN_PASSWORD_LENGTH`, pagination, audio, etc. |
| `environments.py`  | Environment enum and helpers                                  |
| `feature_flags.py` | Feature flag definitions                                      |
| `security.py`      | Security policy constants                                     |
| `settings.py`      | Master `Settings` class combining 10 sub-settings (427 lines) |

#### Settings Classes (pydantic-settings)

| Class                  | Key Fields                                                 |
|------------------------|------------------------------------------------------------|
| `AppSettings`          | `app_env`, `debug`, `app_name`, `api_version`, `base_url` |
| `DatabaseSettings`     | `database_url`, `db_pool_size`, `db_max_overflow`, `db_pool_timeout` |
| `RedisSettings`        | `redis_url`, `redis_db`, `redis_max_connections`, `redis_session_ttl`, `redis_lock_timeout` |
| `QdrantSettings`       | `qdrant_url`, `qdrant_api_key`, `qdrant_collection_name`, `qdrant_embedding_dim` (768) |
| `LLMSettings`          | `default_llm_provider` (groq), `openai_api_key`, `anthropic_api_key`, `groq_api_key`, `embedding_model_url`, model routing per use-case |
| `SandboxSettings`      | Docker images (cpp/java/python), `sandbox_time_limit_ms` (2000), `sandbox_memory_limit_kb` (262144), `sandbox_network_disabled` (true) |
| `SecuritySettings`     | `jwt_algorithm` (RS256/HS256), key paths, `access_token_expire_minutes` (30), `refresh_token_expire_days` (30), `password_hash_algorithm` |
| `AudioSettings`        | `silence_threshold_ms` (3000), `audio_transcription_provider`, `whisper_model`, `max_transcript_length` |
| `RateLimitSettings`    | `login_rate_limit` (5/15min), `api_rate_limit` (100/60s), `max_concurrent_interviews_per_candidate` (1) |
| `FeatureFlagsSettings` | `enable_ai_evaluation`, `enable_proctoring`, `enable_audio_analysis`, `enable_code_execution`, `enable_practice_mode`, `enable_human_override` |

#### Tables Owned

None — pure configuration.

#### Cross-Module Dependencies

- **Imports:** None (leaf module)
- **Consumed by:** Every other module via `from app.config import settings`

---

### 3.8 evaluation

**Purpose:** Exchange-level scoring & final result computation.

#### Files: **0 .py files** — NOT YET IMPLEMENTED

#### Planned Submodules

| Submodule     | Purpose                                                |
|---------------|--------------------------------------------------------|
| `scoring/`    | Rubric-based scoring (AI + human + hybrid)             |
| `aggregation/`| Snapshot-based final result aggregation                |
| `snapshots/`  | Immutable evaluation snapshots for reproducibility     |
| `persistence/`| Evaluation repository (evaluations, dimension_scores)  |
| `api/`        | REST endpoints for evaluation CRUD + review            |

#### Key Concepts (from REQUIREMENTS.md)

- One exchange = one evaluation (UNIQUE constraint on `interview_exchange_id`)
- Exchange immutability preserved (reads from exchanges, writes only to evaluations)
- Rubric-based scoring: per-dimension scores x weights
- Versioned final results with recommendation enum: `strong_hire`, `hire`, `review`, `no_hire`
- AI/human/hybrid evaluation modes
- Snapshot-based aggregation for reproducibility

#### Tables Planned

`evaluations`, `evaluation_dimension_scores`, `interview_results`, `supplementary_reports`

---

### 3.9 interview

**Purpose:** Core runtime engine — deterministic state machine orchestrator.

#### Files: **0 .py files** — NOT YET IMPLEMENTED

#### Planned Submodules

| Submodule        | Purpose                                              |
|------------------|------------------------------------------------------|
| `orchestration/` | State machine transitions, question flow coordination|
| `session/`       | Redis-backed session state management                |
| `exchanges/`     | Exchange immutability, INSERT-only                   |
| `realtime/`      | WebSocket connection management                      |
| `persistence/`   | Interview submission & exchange repositories         |
| `api/`           | REST + WebSocket endpoints                           |

#### Key Concepts (from REQUIREMENTS.md)

- Template frozen at submission creation (snapshot in JSONB column)
- Exchange immutability: NO UPDATE on `interview_exchanges` — INSERT only
- One-way state transitions: `pending` → `in_progress` → `completed`
- Redis session state for real-time coordination
- Race condition prevention via distributed locks
- WebSocket connection management via ConnectionRegistry

#### Tables Planned

`interview_submissions`, `interview_exchanges`

---

### 3.10 persistence

**Purpose:** Infrastructure-only database & cache connectors — PostgreSQL, Redis, Qdrant.

#### Files (12 .py files)

| Submodule    | Files                                                           |
|--------------|-----------------------------------------------------------------|
| `postgres/`  | `__init__.py`, `base.py`, `engine.py`, `health.py`, `session.py` |
| `qdrant/`    | `__init__.py`, `client.py`, `collections.py`, `health.py`, `operations.py` |
| `redis/`     | `__init__.py`, `client.py`, `health.py`, `locks.py`, `operations.py` |

#### Key Functions & Classes

| Function / Class                | File                       | Role                                       |
|---------------------------------|----------------------------|--------------------------------------------|
| `init_postgres(config)`         | `postgres/__init__.py`     | Init engine + session factory              |
| `get_db_session()`              | `postgres/session.py`      | FastAPI dependency yielding async session  |
| `cleanup_postgres()`            | `postgres/__init__.py`     | Dispose engine, close pool                 |
| `check_postgres_health()`       | `postgres/health.py`       | Health check with pool status              |
| `Base`                          | `postgres/base.py`         | SQLAlchemy declarative base for all models |
| `init_engine(config)`           | `postgres/engine.py`       | Create SQLAlchemy engine with pool config  |
| `init_redis(config)`            | `redis/__init__.py`        | Init Redis connection pool                 |
| `redis_client`                  | `redis/client.py`          | Module-level Redis client singleton        |
| `DistributedLock`               | `redis/locks.py`           | Redis-based distributed locking            |
| `init_qdrant(config)`           | `qdrant/__init__.py`       | Init Qdrant client                         |
| `store_embedding()`             | `qdrant/operations.py`     | Store vector in Qdrant collection          |
| `search_vectors()`              | `qdrant/operations.py`     | Semantic vector search                     |
| `check_redis_health()`          | `redis/health.py`          | Redis connectivity check                   |
| `check_qdrant_health()`         | `qdrant/health.py`         | Qdrant connectivity check                  |

#### Tables Owned

None — "dumb plumbing," connects but does not decide.

#### Cross-Module Dependencies

- **Imports:** `config.settings` (DatabaseSettings, RedisSettings, QdrantSettings), `shared.errors`
- **FORBIDDEN:** Must NEVER contain domain rules, repository logic, multi-tenant filtering, RBAC
- **Consumed by:** Every module that needs DB/cache/vector access

---

### 3.11 proctoring

**Purpose:** Advisory integrity signal collection & risk scoring.

#### Files: **0 .py files** — NOT YET IMPLEMENTED

#### Planned Submodules

| Submodule     | Purpose                                               |
|---------------|-------------------------------------------------------|
| `ingestion/`  | Event ingestion (tab_switch, face_absent, etc.)       |
| `rules/`      | Configurable rule engine for risk classification      |
| `risk_model/` | Risk scoring with thresholds (low/moderate/high/critical) |
| `persistence/`| Proctoring event storage                              |

#### Key Concepts (from REQUIREMENTS.md)

- **ADVISORY ONLY** — never blocks candidates, never auto-fails, never modifies evaluation scores
- Event types: `tab_switch`, `face_absent`, `multiple_faces`, `multiple_voices`, `camera_disabled`, `mic_disabled`
- Risk scoring with configurable thresholds
- Severity enum: `low`, `moderate`, `high`, `critical`
- **FORBIDDEN:** No autonomous rejection, no emotion recognition, no eye-tracking, no psychological inference

#### Tables Planned

`proctoring_events`

---

### 3.12 question

**Purpose:** Intelligent content decision engine — selection, retrieval, generation.

#### Files (18 .py files)

| Submodule              | Files                                                           |
|------------------------|-----------------------------------------------------------------|
| root                   | `__init__.py`                                                   |
| `generation/`          | `__init__.py`, `contracts.py`, `service.py`                    |
| `generation/domain/`   | `__init__.py`, `entities.py`, `parsing.py`, `validation.py`    |
| `generation/persistence/` | `__init__.py`, `fallback_repository.py`, `models.py`        |
| `retrieval/`           | `__init__.py`, `contracts.py`, `service.py`                    |
| `retrieval/domain/`    | `__init__.py`, `circuit_breaker.py`, `similarity.py`           |
| `retrieval/persistence/` | `__init__.py`, `cache_repository.py`, `qdrant_repository.py`, `question_read_repository.py` |
| `selection/`           | (REQUIREMENTS.md only — **no .py files**)                      |
| `prompting/`           | (REQUIREMENTS.md only — **no .py files**)                      |
| `persistence/`         | (REQUIREMENTS.md only — **no .py files**)                      |

#### Key Classes

| Class                        | File                                 | Role                                              |
|------------------------------|--------------------------------------|---------------------------------------------------|
| `QuestionGenerationService`  | `generation/service.py`              | LLM-based question generation with retry + validation + fallback (514 lines) |
| `QdrantRetrievalService`     | `retrieval/service.py`               | Semantic search with circuit breaker + cache + SQL fallback (430 lines) |
| `CircuitBreaker`             | `retrieval/domain/circuit_breaker.py`| Qdrant fault tolerance (failure_threshold=5, timeout=60s) |
| `FallbackQuestionRepository` | `generation/persistence/fallback_repository.py` | Generic fallback questions from DB      |
| `QdrantQuestionRepository`   | `retrieval/persistence/qdrant_repository.py` | Qdrant vector search wrapper              |
| `RetrievalCacheRepository`   | `retrieval/persistence/cache_repository.py` | Redis-backed retrieval cache              |
| `QuestionReadRepository`     | `retrieval/persistence/question_read_repository.py` | PostgreSQL read-only question access |

#### Contracts

**Generation:** `GenerationRequest`, `GenerationResult`, `GenerationStatus`

**Generation Entities:** `GeneratedQuestionOutput`, `GenerationMetadata`, `ValidationResult`

**Retrieval:** `SearchCriteria`, `QuestionCandidate`, `RetrievalResult`, `RetrievalStrategy`, `HybridSearchWeights`, `SimilarityCheckResult`

#### Key Algorithms (from REQUIREMENTS.md)

- Difficulty adaptation: `threshold_up=80`, `threshold_down=50`
- Repetition prevention via semantic similarity: `threshold=0.85`
- Fallback hierarchy: relax difficulty → relax topic → relax similarity → LLM generation → cached generic

#### Tables

- **Read-only:** `questions`, `generic_fallback_questions`, `embeddings`
- **Via Qdrant:** Vector search on question embeddings

#### Cross-Module Dependencies

- **Imports:** `ai.llm.base_provider` (BaseLLMProvider), `ai.llm.contracts` (LLMRequest, LLMResponse), `ai.llm.errors`, `ai.llm.utils.token_counter`, `ai.prompts.service` (PromptService), `ai.prompts.entities` (RenderedPrompt), `ai.prompts.errors`
- **Consumed by:** `interview/orchestration` (future), `question/selection` (future)

---

### 3.13 shared

**Purpose:** Cross-cutting infrastructure primitives — errors, auth context, observability.

#### Files (17 .py files)

| Submodule         | Files                                                                      |
|-------------------|----------------------------------------------------------------------------|
| root              | `__init__.py`                                                              |
| `auth_context/`   | `__init__.py`, `builder.py`, `config.py`, `context.py` (deprecated), `dependencies.py`, `middleware.py`, `models.py`, `registry.py`, `scope.py`, `websocket.py` |
| `errors/`         | `__init__.py`, `classification.py`, `config.py`, `exceptions.py`, `serializers.py` |
| `observability/`  | `__init__.py`, `config.py`, `logging.py`, `metrics.py`, `redaction.py`, `telemetry.py`, `tracing.py` |

#### Key Classes & Functions

**Auth Context:**

| Class / Function                | File                        | Role                                        |
|---------------------------------|-----------------------------|---------------------------------------------|
| `IdentityContext` (frozen)      | `models.py`                 | Immutable request identity from JWT claims  |
| `UserType` enum                 | `models.py`                 | `admin`, `candidate`                         |
| `AdminRole` enum                | `models.py`                 | `superadmin`, `admin`, `read_only`           |
| `TaskContext`                   | `models.py`                 | Serializable context for async workers       |
| `IdentityBuilder`              | `builder.py`                | JWT claims → IdentityContext transformer     |
| `get_identity()`               | `dependencies.py`           | FastAPI dependency: request → IdentityContext|
| `require_admin()`              | `dependencies.py`           | FastAPI dependency: admin-only guard         |
| `require_superadmin()`         | `dependencies.py`           | FastAPI dependency: superadmin-only guard    |
| `IdentityInjectionMiddleware`  | `middleware.py`             | Attaches identity to `request.state`         |
| `ConnectionRegistry`           | `registry.py`               | Redis-backed WebSocket connection tracking   |
| `authenticate_websocket()`     | `websocket.py`              | WebSocket authentication helper              |
| `enforce_organization_scope()` | `scope.py`                  | Tenant isolation enforcement                 |
| `enforce_candidate_scope()`    | `scope.py`                  | Resource ownership enforcement               |
| `AuthContext` (DEPRECATED)     | `context.py`                | Old model, use IdentityContext instead       |

**Error Hierarchy:**

| Error Class                    | HTTP | Error Code              |
|--------------------------------|------|--------------------------|
| `BaseError`                    | 500  | (base)                   |
| `ApplicationError`             | 500  | (backward compat alias)  |
| `AuthenticationError`          | 401  | `AUTHENTICATION_FAILED`  |
| `AuthorizationError`           | 403  | `AUTHORIZATION_FAILED`   |
| `TenantIsolationViolation`     | 403  | `TENANT_VIOLATION`       |
| `NotFoundError`                | 404  | `NOT_FOUND`              |
| `ConflictError`                | 409  | `CONFLICT`               |
| `ValidationError`              | 400  | `VALIDATION_ERROR`       |
| `RateLimitExceeded`            | 429  | `RATE_LIMIT_EXCEEDED`    |
| `InterviewNotActiveError`      | 409  | (domain)                 |
| `InterviewWindowClosedError`   | 409  | (domain)                 |
| `ConsentNotCapturedError`      | 403  | (domain)                 |
| `ExchangeImmutabilityViolation`| 409  | (domain)                 |
| `TemplateImmutabilityViolation`| 409  | (domain)                 |
| `DomainInvariantViolation`     | 409  | (domain)                 |
| `ProctoringViolation`          | 409  | (domain)                 |
| `AIProviderError`              | 502  | (external service)       |
| `AIProviderTimeoutError`       | 504  | (external service)       |
| `SandboxExecutionError`        | 500  | (sandbox)                |
| `SandboxTimeoutError`          | 504  | (sandbox)                |
| `InfrastructureError`          | 500  | (system)                 |
| `DatabaseError`                | 500  | (system)                 |
| `CacheError`                   | 500  | (system)                 |
| `ConfigurationError`           | 500  | (system)                 |
| `InternalServerError`          | 500  | (system)                 |

**Observability:**

| Export                       | File            | Role                                     |
|------------------------------|-----------------|------------------------------------------|
| `StructuredFormatter`        | `logging.py`    | JSON log formatter with ISO 8601 timestamps |
| `ContextLogger`              | `logging.py`    | Logger with auto-injected context fields |
| `get_context_logger()`       | `logging.py`    | Factory for context-aware loggers        |
| `configure_structured_logging()` | `logging.py` | Global logging setup                     |
| `TraceContext`               | `tracing.py`    | Distributed tracing context              |
| `generate_request_id()`     | `tracing.py`    | UUID-based request ID generation         |
| `RequestIDMiddleware`        | `tracing.py`    | Injects request_id into every request    |
| `redact_sensitive_data()`    | `redaction.py`  | PII/secret masking for logs              |
| `track_latency()`           | `metrics.py`    | Prometheus latency tracking decorator    |
| `MetricsRegistry`           | `metrics.py`    | Centralized Prometheus metrics           |
| `AITelemetry`               | `telemetry.py`  | AI operation telemetry hooks             |

#### Tables Owned

None — pure infrastructure.

#### Cross-Module Dependencies

- **Imports:** `persistence.redis` (lazy, for ConnectionRegistry), `config` (lazy, for auth dependencies)
- **FORBIDDEN:** Must NOT import any domain module. Must remain < 2,000 lines total.
- **Consumed by:** Every module

---

## 4. Implementation Status Matrix

| Module      | .py Files | REQUIREMENTS.md | Router Active | Tables Exist | Status              |
|-------------|-----------|-----------------|---------------|--------------|---------------------|
| admin       | 16        | 714 lines       | Active        | Yes          | **Implemented**     |
| ai          | 18        | 644 lines       | N/A           | Read-only    | **Implemented**     |
| audio       | 22        | 656 lines       | Active        | Partial      | **Partially Impl.** |
| auth        | 15        | 807 lines       | Active        | Yes          | **Implemented**     |
| bootstrap   | 7         | 1271 lines      | N/A           | N/A          | **Implemented**     |
| coding      | 16        | 775 lines       | Commented     | Yes          | **Implemented**     |
| config      | 5         | 1123 lines      | N/A           | N/A          | **Implemented**     |
| evaluation  | 0         | 699 lines       | Commented     | Schema only  | **Not Started**     |
| interview   | 0         | 796 lines       | Commented     | Schema only  | **Not Started**     |
| persistence | 12        | 746 lines       | N/A           | N/A          | **Implemented**     |
| proctoring  | 0         | 658 lines       | Commented     | Schema only  | **Not Started**     |
| question    | 18        | 896 lines       | Commented     | Read-only    | **Partially Impl.** |
| shared      | 17        | 882 lines       | N/A           | N/A          | **Implemented**     |

**Legend:** Implemented = code + tests exist; Partially Impl. = core submodules coded, others planned; Not Started = REQUIREMENTS.md only

---

## 5. Database Ownership Map

| Module     | Tables Owned (READ-WRITE)                                                   |
|------------|-----------------------------------------------------------------------------|
| admin      | `interview_templates`, `interview_template_roles`, `interview_template_rubrics`, `rubrics`, `rubric_dimensions`, `roles`, `topics`, `coding_topics`, `questions`, `coding_problems`, `interview_submission_windows`, `window_role_templates`, 6 override tables |
| auth       | `users`, `admins`, `candidates`, `refresh_tokens`, `auth_audit_log`         |
| coding     | `code_submissions`, `code_execution_results`                                |
| audio      | `audio_analytics` (planned)                                                 |
| evaluation | `evaluations`, `evaluation_dimension_scores`, `interview_results`, `supplementary_reports` (planned) |
| interview  | `interview_submissions`, `interview_exchanges` (planned)                    |
| proctoring | `proctoring_events` (planned)                                               |

**Shared/read-only tables:** `organizations`, `audit_logs`, `embeddings`, `models`, `prompt_templates`, `resumes`, `job_descriptions`, `generic_fallback_questions`, `programming_languages`, `problem_language_templates`, `coding_test_cases`, `source_topics`, `media_artifacts` + junction tables

---

## 6. Key Architectural Invariants

| # | Invariant | Enforcement |
|---|-----------|-------------|
| 1 | Template immutability after use | `SubmissionRepository.template_is_in_use()` → create new version instead of UPDATE |
| 2 | Exchange immutability | NO UPDATE on `interview_exchanges` — INSERT only, enforced by service layer |
| 3 | One exchange = one evaluation | UNIQUE constraint on `evaluations.interview_exchange_id` |
| 4 | Template frozen at submission creation | JSONB snapshot in `interview_submissions.template_snapshot` |
| 5 | Multi-tenant isolation | `organization_id` filtering in every repository + `enforce_organization_scope()` |
| 6 | Proctoring is advisory only | Never blocks, never auto-fails, never modifies scores |
| 7 | No emotion recognition / eye-tracking | Negative requirements NR-3, FR-5.5, FR-9.10 |
| 8 | AI module is infrastructure-only | No domain imports allowed per REQUIREMENTS.md |
| 9 | Persistence is "dumb plumbing" | No business logic, no RBAC, no multi-tenant filtering |
| 10 | Shared module < 2,000 lines | Zero business logic, no domain imports |
| 11 | Rubric dimension weights sum to 1.0 | +/-0.001 tolerance enforced in `rubric_validator.py` |
| 12 | No autonomous hiring decisions | NR-1: Human must approve all final results |
| 13 | Coding sandbox isolation | Docker + seccomp + no-network + non-root + resource limits |
| 14 | Consent before data collection | NFR-9: Explicit consent captured before interview initiation |
