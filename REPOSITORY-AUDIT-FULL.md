# Comprehensive Repository Audit — AI Interviewer

**Generated:** Exhaustive code-level audit of `/app` directory  
**Scope:** Every module, file, public interface, domain service, persistence layer, contract/DTO, enum, and cross-module dependency

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module: config/](#2-module-config)
3. [Module: shared/](#3-module-shared)
4. [Module: persistence/](#4-module-persistence)
5. [Module: bootstrap/](#5-module-bootstrap)
6. [Module: auth/](#6-module-auth)
7. [Module: admin/](#7-module-admin)
8. [Module: ai/](#8-module-ai)
9. [Module: audio/](#9-module-audio)
10. [Module: interview/](#10-module-interview)
11. [Module: question/](#11-module-question)
12. [Module: coding/](#12-module-coding)
13. [Module: evaluation/](#13-module-evaluation)
14. [Module: proctoring/](#14-module-proctoring)
15. [Cross-Module Dependency Map](#15-cross-module-dependency-map)
16. [Implementation Status Summary](#16-implementation-status-summary)
17. [Database Schema Summary](#17-database-schema-summary)

---

## 1. Architecture Overview

### Stack
- **Framework:** FastAPI with lifespan management, middleware pipeline, central router registry
- **ORM:** SQLAlchemy 2.x (declarative base, sessionmaker, with_for_update)
- **Databases:** PostgreSQL (relational), Redis (sessions/caching/locks), Qdrant (vector search)
- **Validation:** Pydantic v2 + dataclasses (frozen for immutability)
- **Auth:** JWT (RS256/HS256), RBAC, IdentityContext frozen dataclass
- **LLM Providers:** Groq (default), Gemini, OpenAI, Anthropic — swappable via ProviderFactory
- **Sandbox:** Docker-based code execution with seccomp, network isolation, resource limits
- **Multi-tenancy:** organization-scoped data isolation enforced at auth_context + repository layers

### Design Patterns
- **Modular monolith:** 12+ domain modules with explicit boundaries
- **Repository pattern:** Protocol-based interfaces, SQLAlchemy implementations
- **State machine pattern:** Interview submissions, exchange lifecycle, code execution
- **Immutable snapshots:** Exchanges, evaluations, template structures frozen at creation
- **Distributed locking:** Redis Lua-script-based safe release
- **Circuit breaker:** Qdrant retrieval fault tolerance
- **Factory pattern:** LLM providers, feature flags, security config, environment config

### Key Invariants (from SRS + schema.sql)
- One exchange = one evaluation (UNIQUE constraint)
- Exchange immutability preserved (CREATE + READ only, no UPDATE/DELETE)
- Template immutability after first submission reference
- Rubric dimension weights sum to 1.0 (±0.001)
- Organization-scoped tenant isolation (NFR-7.1)
- Audio never written to disk (GDPR)
- Untrusted code never executes outside sandbox (NR-5)

---

## 2. Module: config/

**Purpose:** Centralized configuration management — settings from environment, feature flags, security policies, environment-specific defaults.

### Files
| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports all config objects; initializes globals (feature_flags, env_config, security_config, cors_config, password_policy) |
| `settings.py` | Pydantic Settings: AppSettings, DatabaseSettings, RedisSettings, QdrantSettings, LLMSettings, SandboxSettings, SecuritySettings, AudioSettings, RateLimitSettings, FeatureFlagsSettings, top-level Settings |
| `constants.py` | Domain constants: SUPPORTED_LANGUAGES, MAX_EXCHANGES_PER_INTERVIEW=50, difficulty levels, pagination defaults, embedding dim=768 |
| `feature_flags.py` | Frozen dataclass FeatureFlags: ENABLE_AI_EVALUATION, ENABLE_PROCTORING, ENABLE_AUDIO_ANALYSIS, ENABLE_CODE_EXECUTION, ENABLE_PRACTICE_MODE, ENABLE_HUMAN_OVERRIDE, ENABLE_RESUME_PARSING |
| `security.py` | Frozen dataclass SecurityConfig (CORS, cookies, HTTPS, password rules), CORSConfig, PasswordPolicy with validate() method |
| `environments.py` | Frozen dataclass EnvironmentConfig: dev/staging/prod toggles, log levels, pool sizes, SSL, error detail levels |

### Public Interfaces
- `settings` — global Settings singleton
- `feature_flags` — global FeatureFlags instance
- `env_config`, `security_config`, `cors_config`, `password_policy` — frozen config objects
- `constants` — module of constant values

### Dependencies
- `pydantic_settings` (env var loading)
- No domain module dependencies (config is a leaf)

---

## 3. Module: shared/

**Purpose:** Cross-cutting infrastructure — error hierarchy, auth context, observability (logging, tracing, metrics, telemetry, redaction).

### 3.1 shared/errors/

| File | Purpose |
|------|---------|
| `__init__.py` | Exports 25+ error classes, serializers, classification functions |
| `exceptions.py` | BaseError dataclass (error_code, message, request_id, metadata, http_status_code), complete hierarchy: AuthenticationError(401), AuthorizationError(403), TenantIsolationViolation(403), NotFoundError(404), ConflictError(409), ValidationError(422), RateLimitExceeded(429), InterviewNotActiveError, InterviewWindowClosedError, ConsentNotCapturedError, ExchangeImmutabilityViolation, TemplateImmutabilityViolation, DomainInvariantViolation, ProctoringViolation, AIProviderError, AIProviderTimeoutError, SandboxExecutionError, SandboxTimeoutError, InfrastructureError, DatabaseError, CacheError, ConfigurationError, InternalServerError |
| `classification.py` | `is_fatal_error()` (auth/tenant/invariant → close WebSocket), `get_log_level()` (CRITICAL/ERROR/WARN/INFO), `should_send_to_client()` (prod security filtering) |
| `config.py` | Error configuration |
| `serializers.py` | Error serialization utilities |

### 3.2 shared/auth_context/

| File | Purpose |
|------|---------|
| `__init__.py` | Re-exports IdentityContext, UserType, AdminRole, TaskContext, dependencies, ConnectionRegistry (lazy) |
| `models.py` | **IdentityContext** (frozen dataclass): user_id, user_type, organization_id, admin_role, token_version, issued_at, expires_at; `is_superadmin()`, `is_admin()`, `is_candidate()`. **UserType**(admin/candidate), **AdminRole**(superadmin/admin/read_only), **TaskContext** for async jobs |
| `dependencies.py` | FastAPI Depends: `get_identity`, `get_optional_identity`, `require_admin`, `require_candidate`, `require_superadmin`. Lazy-loads token_validator. |
| `context.py` | DEPRECATED AuthContext → migration path to IdentityContext |

### 3.3 shared/observability/

| File | Purpose |
|------|---------|
| `__init__.py` | Exports ObservabilityConfig, StructuredFormatter, ContextLogger, get_context_logger, redaction utilities, TraceContext, RequestIDMiddleware, MetricsRegistry, AITelemetry |
| `logging.py` | **StructuredFormatter** (JSON with timestamp/level/logger/message/request_id/user_id/event_type/metadata/exception), **ContextLogger** (wraps stdlib logger with auto-context injection) |
| `tracing.py` | **TraceContext** dataclass, `generate_request_id()`, `generate_connection_id()`, `generate_session_id()`, `extract_request_id()`, **RequestIDMiddleware** (injects X-Request-ID) |
| `metrics.py` | `track_latency()`, `track_operation()`, MetricsRegistry |
| `redaction.py` | `redact_sensitive_data()`, `mask_token()`, SENSITIVE_FIELDS |
| `telemetry.py` | AITelemetry, `track_ai_call()` |
| `config.py` | ObservabilityConfig |

### Dependencies
- No domain module dependencies (shared is a leaf)
- Used by: every other module

---

## 4. Module: persistence/

**Purpose:** Infrastructure-layer database clients — PostgreSQL, Redis, Qdrant initialization, connection management, and primitive operations.

### 4.1 persistence/postgres/

| File | Purpose |
|------|---------|
| `base.py` | `Base = declarative_base()`, `import_all_models()` — imports admin, ai.prompts, coding, question.generation, question.selection, interview.session models |
| `engine.py` | `create_db_engine()` (QueuePool, pool_size=20, max_overflow=10, 3 retry attempts with exponential backoff), `init_engine()` global singleton, `get_engine()`, `cleanup_engine()`, pool event listeners |
| `session.py` | `SessionLocal` sessionmaker, `get_db_session()` (no auto-commit), `get_db_session_with_commit()` (auto-commit+rollback on error), `db_session_context()` context manager, `execute_with_retry()` |

### 4.2 persistence/redis/

| File | Purpose |
|------|---------|
| `client.py` | Redis client singleton with ConnectionPool, `create_redis_client()` with retry (3 attempts), `init_redis_client()`, `get_redis_client()`, `cleanup_redis()` with connection tracking |
| `locks.py` | `acquire_lock()` context manager (SET NX + Lua script atomic release, default TTL=30s), `try_acquire_lock()` (non-blocking), `release_lock()` (manual), `create_session_lock_key()` utility. Lua script ensures safe owner-checked release. |

### 4.3 persistence/qdrant/

| File | Purpose |
|------|---------|
| `client.py` | `create_qdrant_client()` with retry (3 attempts, exponential backoff), `init_qdrant_client()` global singleton, `get_qdrant_client()`, `get_collection_name()`, `get_vector_dimension()`, `cleanup_qdrant()` |
| `collections.py` | `create_collection_if_not_exists()` (cosine distance default), `validate_collection_schema()` (dimension check, status check), `delete_collection()` (dangerous), `get_collection_info()` |
| `operations.py` | `validate_vector_dimension()`, `store_embedding()` (single point upsert with metadata payload), `store_embeddings_batch()` (batched upsert), `search_similar()` (vector search with filters: organization_id, difficulty, topic_id, scope, exclude IDs, score threshold, top_k), `delete_embedding()`, `delete_embeddings_by_source()` |
| `health.py` | Qdrant health check |

### Dependencies
- config/ (settings for connection params)
- shared/errors/ (error types)
- shared/observability/ (logging)

---

## 5. Module: bootstrap/

**Purpose:** Application assembly — FastAPI app factory, router registration, dependency re-exports, lifespan management (startup/shutdown), middleware pipeline.

### Files

| File | Purpose |
|------|---------|
| `app.py` | `create_app()` factory → FastAPI instance with lifespan, middleware, routers, exception handlers. Global `app` instance. |
| `lifespan.py` | Startup: logging → PostgreSQL (engine+session+import_all_models) → Redis → Qdrant (client+collection). Shutdown: Qdrant → Redis → PostgreSQL. |
| `dependencies.py` | Re-exports: `get_db_session`, `get_db_session_with_commit`, `get_identity`, `require_admin`, `require_candidate`, `require_superadmin` |
| `router_registry.py` | Registers routers with prefixes: auth (`/api/v1/auth`), admin (`/api/v1/admin`), interview session (`/api/v1/interviews`), question selection (`/api/v1/questions`), audio ingestion (`/api/v1/audio/ingestion`), audio transcription (`/api/v1/audio/transcription`), health (`/api/v1/health`, `/health`). **COMMENTED OUT:** interview parent, question parent, evaluation, coding, proctoring routers. |
| `middleware.py` | Middleware configuration |
| `exception_handlers.py` | Global exception handlers |

### Active Routers (registered)
1. Auth routes
2. Admin routes
3. Interview session routes
4. Question selection routes
5. Audio ingestion routes
6. Audio transcription routes
7. Health endpoints

### Dependencies
- config/, shared/, persistence/ (all three), auth, admin, interview.session, question.selection, audio

---

## 6. Module: auth/

**Purpose:** Authentication and identity management — user registration, login, JWT lifecycle, RBAC enforcement, password hashing.

### 6.1 auth/domain/

| File | Purpose |
|------|---------|
| `auth_service.py` (1024 lines) | **AuthService** — register_admin, register_candidate, login, refresh_token, logout, get_profile. Injected: Session, PasswordHasher, JWTService. Enforces: email uniqueness, org validation, password complexity, role restrictions (cannot self-assign superadmin), audit logging. |
| `jwt_service.py` (234 lines) | **JWTService** — RS256/HS256, `generate_access_token()` (claims: sub, type, token_version, iat, exp, jti + role-specific: org_id, admin_role), `generate_refresh_token()` (64-byte random), `hash_refresh_token()` (SHA-256), `verify_access_token()` with full validation |
| `password_hasher.py` | **PasswordHasher** — bcrypt with configurable cost factor (default 12), `hash()`, `verify()`, `validate_complexity()` (length, uppercase, lowercase, digit, special char) |
| `rbac_enforcer.py` | **RBACEnforcer** — Permission enum (MANAGE_ADMINS, MANAGE_ORGANIZATION, CREATE_TEMPLATES, EDIT_TEMPLATES, DELETE_TEMPLATES, etc.), permission matrix: superadmin=all, admin=CRUD+view, read_only=view only. `has_permission()`, `require_permission()`, `get_permissions()` |

### 6.2 auth/contracts/

| File | Purpose |
|------|---------|
| `enums.py` | **AuthErrorCode** — ~20 codes: INVALID_CREDENTIALS, TOKEN_EXPIRED, TOKEN_INVALID, EMAIL_ALREADY_EXISTS, ORGANIZATION_NOT_FOUND, REFRESH_TOKEN_EXPIRED, etc. |
| `schemas.py` | Request DTOs: AdminRegistrationRequest, CandidateRegistrationRequest, LoginRequest, RefreshTokenRequest, LogoutRequest. Response DTOs: RegistrationResponse, LoginResponse, TokenRefreshResponse, CurrentUserResponse, UserProfileResponse |
| `claims.py` | JWT claims models |
| `responses.py` | Additional response models |

### 6.3 auth/persistence/

| File | Purpose |
|------|---------|
| `models.py` | ORM models: **User** (users table — id, name, email, password_hash, user_type, status, token_version), **Organization** (minimal for FK resolution), **Admin** (admins — user_id, organization_id, role, status), **Candidate** (candidates — user_id, plan, profile_metadata), **RefreshToken** (refresh_tokens — token_hash, device_info, ip_address, expires_at, revoked_at), **AuthAuditLog** (auth_audit_log — event_type, ip, user_agent, metadata). Note: Uses its own `Base = declarative_base()` separate from shared Base. |
| `user_repository.py` | **UserRepository** — `create()`, `get_by_id()`, `find_by_email()` (case-insensitive), `email_exists()` (EXISTS subquery), `update_last_login()`, `update_password()`, `update_status()`, `increment_token_version()` |
| `admin_repository.py` | Admin CRUD repository |
| `candidate_repository.py` | Candidate CRUD repository |
| `refresh_token_repository.py` | Refresh token CRUD + revocation |
| `audit_log_repository.py` | Insert-only audit log repository |

### 6.4 auth/api/

| File | Purpose |
|------|---------|
| `routes.py` (391 lines) | Endpoints: `POST /register/admin` (201), `POST /register/candidate` (201), `POST /login` (200), `POST /refresh` (200), `POST /logout` (200), `GET /me` (200). Uses `_build_auth_service()` per-request factory. Reads JWT keys from config. |

### Enums
- `UserType`: admin, candidate
- `AdminRole`: superadmin, admin, read_only
- `AuthErrorCode`: ~20 error codes
- `Permission`: 10 permission types

### Dependencies
- config/ (security settings, JWT keys)
- shared/auth_context/ (IdentityContext, AdminRole)
- shared/errors/ (ConflictError, ValidationError, AuthorizationError)
- shared/observability/ (logging)
- persistence/postgres/ (session) — BUT uses own Base

---

## 7. Module: admin/

**Purpose:** Administrative CRUD for all content entities — templates, rubrics, roles, topics, questions, coding problems, windows, overrides. The "content management" brain.

### 7.1 admin/domain/

| File | Purpose |
|------|---------|
| `entities.py` (367 lines) | Domain entities (dataclasses): **Template** (with `create_new_version()` for immutability-safe editing), **TemplateRole**, **TemplateRubric**, **Rubric**, **RubricDimension**, **Role**, **Topic** (hierarchical with parent_topic_id), **CodingTopic**, **Question**, **CodingProblem**, **Window** (interview submission window with start/end time), **WindowRoleTemplate**, **OverrideRecord** (tenant-specific override for super-org base content). Enums: TemplateScope, InterviewScope, DifficultyLevel, QuestionType, CodingTopicType, ContentType. Constants: SUPER_ORG_ID=1, RUBRIC_WEIGHT_TOLERANCE=0.001, IMMUTABLE_OVERRIDE_FIELDS |
| `services.py` (1394 lines) | Service classes: **TemplateService** (CRUD, immutability-safe versioning, activate/deactivate, template-role/rubric mappings, override management), **RubricService** (CRUD, dimension weight validation to sum=1.0), **RoleService**, **TopicService** (cycle detection for hierarchical topics), **QuestionService**, **CodingProblemService**, **WindowService** (overlapping window detection). All use RBAC via authorization module. |
| `protocols.py` (401 lines) | Protocol interfaces: **TemplateRepository**, **RubricRepository**, **RoleRepository**, **TopicRepository** (with cycle detection), **QuestionRepository**, **CodingProblemRepository**, **WindowRepository** (with overlap check), **SubmissionRepository** (read-only for immutability checks), **OverrideRepository** (generic across content types), **AuditLogRepository** |
| `authorization.py` | `authorize_admin_operation()` (superadmin=all, admin=own org CRUD, read_only=GET only), `authorize_base_content_mutation()` (superadmin only for org_id=1), `authorize_override_operation()` (base content must be super-org, caller must have org access). Uses `enforce_organization_scope()` from shared. |

### 7.2 admin/persistence/

| File | Purpose |
|------|---------|
| `models.py` (783 lines) | ORM models: **InterviewTemplateModel**, **InterviewTemplateRoleModel**, **InterviewTemplateRubricModel**, **RubricModel**, **RubricDimensionModel**, **RoleModel**, **TopicModel**, **CodingTopicModel**, **QuestionModel**, **CodingProblemModel**, **InterviewSubmissionWindowModel**, **WindowRoleTemplateModel**, **AuditLogModel**, + override models (OVERRIDE_MODEL_MAP) |
| `repositories.py` (915 lines) | Concrete implementations: **SqlTemplateRepository**, **SqlRubricRepository**, **SqlRoleRepository**, **SqlTopicRepository**, **SqlQuestionRepository**, **SqlCodingProblemRepository**, **SqlWindowRepository**, **SqlSubmissionRepository**, **SqlOverrideRepository**, **SqlAuditLogRepository**. Uses `_org_filter()` for multi-tenant isolation (own org + super org). |
| `mappers.py` | Bidirectional entity↔model mapping functions for all entities |

### 7.3 admin/api/

| File | Purpose |
|------|---------|
| `contracts.py` (545 lines) | Pydantic DTOs: Create/Update/Response/List/Detail for Template, Rubric, Dimension, Role, Topic, Question, CodingProblem, Window, Override. Shared: PaginationMeta, MetaInfo. Reuses enums from domain entities. |
| `routes.py` (1139 lines) | All admin CRUD endpoints (prefix `/api/v1/admin`): Templates (CRUD + activate + overrides), Rubrics (CRUD + dimensions + overrides), Roles (CRUD + overrides), Topics (CRUD + overrides), Questions (CRUD + overrides), Coding Problems (CRUD + overrides), Windows (CRUD + mappings). All require admin JWT. |
| `dependencies.py` | Per-request service factory functions: `build_template_service()`, `build_rubric_service()`, etc. Wires repository implementations to domain services. |

### 7.4 admin/validation/

| File | Purpose |
|------|---------|
| `template_validator.py` (369 lines) | **TemplateStructureValidator** — validates template_structure JSONB: section keys, enabled sections, weight validation, topic section config, coding section config. Supports "simple" and "v2" template flavours. |
| `rubric_validator.py` | Rubric dimension validation (weight sum = 1.0) |
| `cross_reference_validator.py` | Cross-entity reference validation |
| `override_validator.py` | Override field validation |
| `pre_activation_validator.py` | Pre-activation completeness checks |
| `result.py` | ValidationResult, ValidationErrorDetail dataclasses |

### Enums
- `TemplateScope`: public, organization, private
- `InterviewScope`: global, local, only_invited
- `DifficultyLevel`: easy, medium, hard
- `QuestionType`: behavioral, technical, situational, coding
- `CodingTopicType`: data_structure, algorithm, pattern, system_design, language_specific, traversal
- `ContentType`: template, rubric, role, topic, question, coding_problem

### Dependencies
- shared/auth_context/ (IdentityContext, AdminRole)
- shared/errors/ (NotFoundError, ConflictError, ValidationError, TemplateImmutabilityViolation)
- shared/observability/ (logging)
- persistence/postgres/ (shared Base for ORM models)

---

## 8. Module: ai/

**Purpose:** LLM provider abstraction, prompt template management, and AI telemetry. The "AI brain" infrastructure.

### 8.1 ai/llm/

| File | Purpose |
|------|---------|
| `contracts.py` (312 lines) | DTOs: **LLMProvider** enum (groq/gemini/openai/anthropic/local), **LLMErrorType** enum, **LLMRequest** (prompt, model, system_prompt, temperature, max_tokens, json_mode, schema, deterministic mode), **TelemetryData** (tokens, latency, cost), **LLMError** (type, retryable, provider details), **LLMResponse** (text, finish_reason, telemetry, error), **EmbeddingRequest/Response**, **TranscriptionRequest/Response**, **ClarificationRequest** (temperature=0.0 enforced for fairness, max 120 words), **ClarificationResponse** (policy compliance tracking) |
| `base_provider.py` (246 lines) | ABCs: **BaseLLMProvider** (`generate_text()`, `generate_structured()`, `get_supported_models()`), **BaseEmbeddingProvider** (`generate_embedding()`, `get_embedding_dimension()`), **BaseTranscriptionProvider** (`transcribe_audio()`, `get_supported_formats()`), **ProviderCapabilities** flags |
| `provider_factory.py` | **ProviderFactory** — `create_text_provider()` (lazy imports per provider), `create_embedding_provider()`. Convenience: `get_groq_provider()`, `get_default_provider()`. Loads API keys from settings. |
| `errors.py` (360 lines) | **LLMProviderError**, **LLMTimeoutError** (always retryable), **LLMRateLimitError** (with retry_after_seconds), **LLMAuthenticationError**, **LLMSchemaValidationError**, **LLMConfigurationError** |

### 8.1.1 ai/llm/providers/

| File | Purpose |
|------|---------|
| `groq_provider.py` | Groq API implementation (default provider) |
| `gemini_provider.py` | Google Gemini implementation |
| `openai_provider.py` | OpenAI implementation |
| `anthropic_provider.py` | Anthropic Claude implementation |
| `embedding_provider.py` | Self-hosted embedding service |

### 8.2 ai/prompts/

| File | Purpose |
|------|---------|
| `service.py` (224 lines) | **PromptService** — `get_prompt()` (org-scoped → global fallback), `render_prompt()` (variable substitution, truncation), `get_rendered_prompt()` (combined), `list_available_types()`. Injected with PromptTemplateRepository protocol. |
| `entities.py` | **PromptTemplate**, **RenderedPrompt** dataclasses |
| `protocols.py` | **PromptTemplateRepository** protocol (get_active_by_type, get_active_by_type_strict) |
| `renderer.py` | **PromptRenderer** — variable substitution, context truncation |
| `parser.py` | Prompt template parsing |
| `errors.py` | PromptNotFoundError, VariableMissingError, TemplateSyntaxError |
| `models.py` | SQLAlchemy ORM model for prompt_templates table |
| `repository.py` | Concrete SQL repository implementation |
| `mappers.py` | Entity↔model mapping |
| `seed_prompt_templates.sql` | Seed data for prompt templates |

### 8.3 ai/telemetry/

| File | Purpose |
|------|---------|
| `tracker.py` (375 lines) | **TelemetrySpan** (set_input, set_output, set_error, finalize→TelemetryData), **TelemetryTracker** (context manager, `track()` yielding span). Non-blocking: telemetry failure never propagates. Uses monotonic clock. |
| `contracts.py` | **OperationType** enum (text_generation, structured_output, embedding, transcription, clarification) |
| `cost.py` | **CostEstimator** — pricing table per model, `estimate_cost()` from token counts |
| `aggregation.py` | Telemetry aggregation utilities |

### Enums
- `LLMProvider`: groq, gemini, openai, anthropic, local
- `LLMErrorType`: timeout, rate_limit, authentication, provider_error, schema_validation, unknown
- `OperationType`: text_generation, structured_output, embedding, transcription, clarification

### Dependencies
- config/ (LLM settings, API keys)
- shared/errors/ (AIProviderError, AIProviderTimeoutError, ValidationError)
- shared/observability/ (logging, metrics)
- persistence/postgres/ (prompt_templates ORM model)

---

## 9. Module: audio/

**Purpose:** Real-time audio pipeline — ingestion (normalize, buffer, detect silence), transcription (multi-provider with fallback), analysis (completeness, fillers, speech rate, sentiment, intent).

### 9.1 audio/ingestion/

| File | Purpose |
|------|---------|
| `service.py` (296 lines) | **AudioIngestionService** — `start_session()`, `pause_session()`, `resume_session()`, `stop_session()`, `ingest_chunk()`. Pipeline: validate session → normalize (16kHz mono) → buffer windows → detect silence → forward to transcription callback. Does NOT write to DB, does NOT advance interview state. |
| `contracts.py` | Frozen dataclasses: **AudioStreamRequest** (exchange_id, audio_chunk, sample_rate, channels), **AudioSessionControl** (action enum), **AudioChunk** (normalized output), **SilenceDetectedEvent** (exchange_id, silence_duration_ms, should_evaluate). Enums: **SessionAction** (start/pause/resume/stop), **SilenceReason** |
| `buffer_manager.py` | **AudioBufferManager** — windowed buffering with eviction |
| `normalizer.py` | **AudioNormalizer** — resampling, mono conversion, volume normalization |
| `session_manager.py` | **AudioSessionManager** — one active session per exchange, timeout auto-close |
| `silence_detector.py` | Silence detection with configurable threshold |
| `exceptions.py` | SessionNotFoundError, SessionClosedError, SessionPausedError, SessionAlreadyActiveError |
| `api/` | REST endpoints for audio ingestion |

### 9.2 audio/transcription/

| File | Purpose |
|------|---------|
| `service.py` (285 lines) | **TranscriptionService** — `transcribe()` (primary provider with retry), `transcribe_streaming()` (streaming-capable providers), `transcribe_with_fallback()` (ordered provider chain). Retry: exponential backoff. Audio NEVER written to disk (GDPR). |
| `contracts.py` | TranscriptionConfig, TranscriptionRequest, TranscriptionResult (frozen) |
| `protocols.py` | TranscriptionProvider protocol |
| `provider_selector.py` | **TranscriptionProviderSelector** — resolves provider by name |
| `confidence.py` | Confidence score normalization |
| `exceptions.py` | TranscriptionError, TranscriptionTimeoutError, AllProvidersFailedError |
| `providers/` | Concrete provider implementations (whisper, google, local) |
| `api/` | REST endpoints for transcription |

### 9.3 audio/analysis/

| File | Purpose |
|------|---------|
| `contracts.py` (295 lines) | Frozen dataclasses for analysis I/O: **CompletenessRequest/Result** (speech_state: complete/incomplete/continuing), **FillerDetectionRequest/Result** (filler words with positions), **SpeechRateRequest/Result**, **SentimentRequest/Result**, **IntentClassificationRequest/Result**. Enums: **SpeechState**, **IntentType** (ANSWER/CLARIFICATION/REPEAT/POST_ANSWER/INVALID/INCOMPLETE/UNKNOWN), **SemanticDepth** (none/surface/deep), **ConfidenceLevel** |
| `completeness_classifier.py` | Sentence completeness classification |
| `filler_detector.py` | Filler word detection (uh, um, like, etc.) |
| `speech_rate_analyzer.py` | Words-per-minute calculation |
| `sentiment_analyzer.py` | Sentiment analysis (positive/negative/neutral) |
| `intent_classifier.py` | Utterance intent classification for audio |

### 9.4 audio/persistence/

- Audio metadata persistence (media_artifacts references)

### Enums
- `SessionAction`: start, pause, resume, stop
- `SilenceReason`: threshold_reached, session_ended
- `SpeechState`: complete, incomplete, continuing
- `IntentType`: ANSWER, CLARIFICATION, REPEAT, POST_ANSWER, INVALID, INCOMPLETE, UNKNOWN
- `SemanticDepth`: none, surface, deep
- `ConfidenceLevel`: high, medium, low

### Dependencies
- shared/observability/ (logging)
- shared/errors/ (error types)
- No direct domain module dependencies (audio is infrastructure for interview/orchestration)

---

## 10. Module: interview/

**Purpose:** Core interview lifecycle — session management (start/complete/cancel/review), exchange creation (immutable snapshots), orchestration (question sequencing, audio/code handling), realtime (WebSocket protocol).

### 10.1 interview/session/

**Status: FULLY IMPLEMENTED**

| File | Purpose |
|------|---------|
| `domain/state_machine.py` | **SubmissionStatus** enum (PENDING/IN_PROGRESS/COMPLETED/EXPIRED/CANCELLED/REVIEWED), `validate_transition()`, **StateTransitionError**. Allowed transitions: PENDING→IN_PROGRESS, IN_PROGRESS→COMPLETED/EXPIRED/CANCELLED, COMPLETED→REVIEWED, EXPIRED→REVIEWED |
| `persistence/models.py` | **InterviewSubmissionModel** (maps interview_submissions: id, candidate_id, window_id, role_id, template_id, status, template_structure_snapshot JSONB, scoring_config JSONB, UNIQUE(candidate_id, window_id, role_id)), **InterviewExchangeModel** (maps interview_exchanges: submission_id, question_id OR coding_problem_id, sequence_number, question_type, question_text, response_text, response_code, is_final, metadata JSONB, CHECK constraint requiring question_id OR coding_problem_id) |
| `persistence/repository.py` | **SubmissionRepository** — atomic transitions via raw SQL `UPDATE...WHERE status=:expected RETURNING id`. Methods: `transition_to_in_progress()`, `transition_to_completed()`, `transition_to_expired()`, `transition_to_cancelled()`, `transition_to_reviewed()`. Idempotent (returns False if already in target state). Also: `create_submission()`, `get_by_id()`, `list_by_candidate()`, `count_submissions_for_window()` |
| `contracts/schemas.py` | Pydantic DTOs: **StartInterviewRequest** (window_id, role_id, template_id, consent_captured), **CompleteInterviewRequest/CancelInterviewRequest/ReviewInterviewRequest** (submission_id + admin notes), **InterviewExchangeDTO**, **InterviewSessionDTO** (with `from_model()` classmethod), **InterviewSessionDetailDTO** |
| `api/routes.py` | Endpoints: `POST /start`, `GET /{id}/status`, `POST /complete`, `POST /cancel` (admin), `POST /review` (admin). Status codes: 201/200/200/200/200. |
| `api/service.py` | **SessionService** — orchestrates state transitions + Redis session sync + distributed locking. Methods: `start_interview()` (validates window, creates submission, caches in Redis), `complete_interview()`, `expire_interview()`, `cancel_interview()`, `review_interview()`, `get_session_status()` (Redis-first, DB fallback). Redis key: `interview_session:{id}`, TTL 3600s. |

### 10.2 interview/exchanges/

**Status: FULLY IMPLEMENTED**

| File | Purpose |
|------|---------|
| `contracts.py` | **ExchangeQuestionType** (text/coding/audio), **ContentMetadata** (JSONB schema with clarification tracking: counts, states, intent sequence audit trail, timestamps), **ExchangeCreationData** (complete exchange snapshot input with field validators, all required fields for immutable creation) |
| `question_state_machine.py` | **ExchangeState** enum (ASKED→WAITING_INPUT→CLARIFICATION_REQUESTED→ANSWER_SUBMITTED→POST_ANSWER_WINDOW→EVALUATED→NEXT_QUESTION), **QuestionStateMachine** (max 3 clarifications, response_locked flag, valid transitions enforcement, `to_snapshot_dict()` for JSONB persistence) |
| `repository.py` | **InterviewExchangeRepository** — CREATE + READ only; UPDATE/DELETE raise ExchangeImmutabilityViolation. Validates: submission must be in_progress, sequence contiguous, response completeness (type-specific). Uses InterviewExchangeModel. Idempotent on IntegrityError. |
| `validators.py` | `validate_sequence_order()` (contiguous integers, no gaps, no duplicates), `validate_response_completeness()` (text→response_text required, coding→response_code+code_submission_id, audio→response_text+audio_recording_id) |
| `intent_classifier.py` | **UtteranceIntent** (ANSWER/CLARIFICATION/REPEAT/POST_ANSWER/INVALID/INCOMPLETE/UNKNOWN), **SemanticLevel** (NONE/SURFACE/DEEP), **UtteranceIntentClassification** frozen dataclass, **UtteranceIntentClassifier** Protocol, **RuleBasedIntentClassifier** (keyword-based, conservative: defaults to ANSWER) |
| `clarification_policy.py` | **ClarificationPolicy** (max 3 per question, ≤120 words, no hints, max 1 analogy), **ClarificationRequest/ClarificationResponse**, **ClarificationAuditEntry**, **CLARIFICATION_PROMPT_CONSTRAINTS** dict |
| `errors.py` | **SequenceGapError**(422), **DuplicateSequenceError**(409), **IncompleteResponseError**(422), **ClassificationError**(500), **ClarificationLimitExceededError**(400), **InvalidExchangeStateTransitionError**(409) |

### 10.3 interview/orchestration/

**Status: REQUIREMENTS ONLY — NO CODE FILES**

- `REQUIREMENTS.md` (1146 lines) — Runtime orchestration spec: question sequencer, exchange coordinator, audio handler, coding handler, progress tracker, race resolver. Critical: must use template_structure_snapshot, never dynamically resolve template.

### 10.4 interview/realtime/

**Status: REQUIREMENTS ONLY — NO CODE FILES**

- `REQUIREMENTS.md` (814 lines) — WebSocket protocol spec: `wss://api/ws/interview/{submission_id}?token=JWT`. Connection lifecycle, heartbeat, reconnection, connection replacement (single active per submission). Redis key: `active_websocket:{submission_id}`.

### 10.5 interview/persistence/

**Status: REQUIREMENTS ONLY — NO CODE FILES** (currently handled by session/persistence/)

- `REQUIREMENTS.md` (1051 lines) — Repository pattern spec, clarification fairness tracking.

### 10.6 interview/api/

**Status: REQUIREMENTS ONLY** (beyond session/api/)

- `REQUIREMENTS.md` (770 lines) — REST endpoint specs.

### Public API (from `__init__.py`)
```python
InterviewExchangeRepository, ExchangeCreationData, ContentMetadata,
validate_sequence_order, validate_response_completeness,
QuestionStateMachine, ExchangeState,
UtteranceIntentClassifier, UtteranceIntentClassification,
ClarificationPolicy, ClarificationRequest, ClarificationResponse
```

### Enums
- `SubmissionStatus`: PENDING, IN_PROGRESS, COMPLETED, EXPIRED, CANCELLED, REVIEWED
- `ExchangeState`: ASKED, WAITING_INPUT, CLARIFICATION_REQUESTED, ANSWER_SUBMITTED, POST_ANSWER_WINDOW, EVALUATED, NEXT_QUESTION
- `ExchangeQuestionType`: text, coding, audio
- `UtteranceIntent`: ANSWER, CLARIFICATION, REPEAT, POST_ANSWER, INVALID, INCOMPLETE, UNKNOWN
- `SemanticLevel`: NONE, SURFACE, DEEP

### Dependencies
- shared/errors/ (BaseError, ExchangeImmutabilityViolation, InterviewNotActiveError, InterviewWindowClosedError)
- shared/auth_context/ (IdentityContext, require_admin, require_candidate)
- shared/observability/ (logging)
- persistence/postgres/ (shared Base, session)
- persistence/redis/ (session caching, distributed locks)

---

## 11. Module: question/

**Purpose:** Intelligent content decision engine — question selection (template-based sequencing, difficulty adaptation, repetition prevention), semantic retrieval (Qdrant vector search), LLM-based question generation, fallback strategies.

### 11.1 question/selection/

**Status: IMPLEMENTED**

| File | Purpose |
|------|---------|
| `service.py` (868 lines) | **QuestionSelectionService** — orchestrates template parsing, difficulty adaptation, Qdrant retrieval, repetition prevention, fallback strategies. Stateless. Delegates to QdrantRetrievalService, QuestionGenerationService, AdaptationLogRepository. |
| `contracts.py` (228 lines) | **SelectionStrategy** (semantic_retrieval/static_pool/adaptive/generation/fallback_generic), **FallbackType**, **DifficultyAdaptationConfig**, **RepetitionConfig**, **ExchangeHistoryEntry**, **CandidateProfile**, **SectionConfig**, **SelectionContext**, **QuestionSnapshot**, **AdaptationDecision** |
| `domain/` | Difficulty adaptation, fallback logic, repetition detection, template parser |
| `persistence/` | Adaptation log repository |
| `api/` | REST endpoints for question selection |

### 11.2 question/retrieval/

**Status: IMPLEMENTED**

| File | Purpose |
|------|---------|
| `service.py` (430 lines) | **QdrantRetrievalService** — `search_semantic()` (with Redis cache + circuit breaker + PostgreSQL fallback), `search_by_topic()`, `search_hybrid()` (resume+JD weighted vectors), `check_similarity()`. Module-level CircuitBreaker (failure_threshold=5, timeout=60s). |
| `contracts.py` | **RetrievalStrategy** (semantic/topic_filter/hybrid/static_fallback), **DifficultyLevel**, **QuestionScope**, **HybridSearchWeights**, **SearchCriteria** (organization_id required for tenant isolation, query_vector, difficulty, topic_ids, top_k, score_threshold, exclude_question_ids), **QuestionCandidate**, **RetrievalResult**, **SimilarityCheckResult** |
| `domain/circuit_breaker.py` | CircuitBreaker state machine (CLOSED→OPEN→HALF_OPEN) |
| `domain/similarity.py` | Cosine similarity, hybrid vector computation, history comparison |
| `persistence/qdrant_repository.py` | Qdrant vector search operations |
| `persistence/cache_repository.py` | Redis-based retrieval caching |
| `persistence/question_read_repository.py` | PostgreSQL fallback (read-only) |

### 11.3 question/generation/

**Status: IMPLEMENTED**

| File | Purpose |
|------|---------|
| `service.py` (514 lines) | **QuestionGenerationService** — `generate()`: render prompt → LLM call → parse → validate → retry on failure → fallback to generic pool. Stateless, async. Never raises — errors captured in result. |
| `contracts.py` (201 lines) | **GenerationStatus** (success/validation_failed/llm_error/fallback_used/no_fallback), **GenerationRequest** (submission_id, org_id, difficulty, topic, resume/JD context, history for dedup, performance context, rubric context), **GenerationResult** (question text, expected answer, source tracking, audit metadata: prompt_hash, llm_model, tokens, cost, latency, attempts, validation_failures) |
| `domain/entities.py` | GeneratedQuestionOutput, GenerationMetadata, ValidationResult |
| `domain/parsing.py` | `parse_llm_response()`, ResponseParseError |
| `domain/validation.py` | `validate_generated_question()` |
| `persistence/fallback_repository.py` | FallbackQuestionRepository (generic_fallback_questions table) |

### Enums
- `SelectionStrategy`: semantic_retrieval, static_pool, adaptive, generation, fallback_generic
- `RetrievalStrategy`: semantic, topic_filter, hybrid, static_fallback
- `GenerationStatus`: success, validation_failed, llm_error, fallback_used, no_fallback

### Dependencies
- ai/llm/ (BaseLLMProvider, LLMRequest, LLMResponse)
- ai/prompts/ (PromptService)
- persistence/qdrant/ (vector search)
- persistence/redis/ (caching)
- persistence/postgres/ (read-only question access, fallback)
- shared/observability/ (logging, metrics)

---

## 12. Module: coding/

**Purpose:** Code execution pipeline — sandbox isolation (Docker), execution lifecycle (state machine), test case evaluation, scoring.

### 12.1 coding/enums.py
- **ExecutionStatus**: pending, running, passed, failed, error, timeout, memory_exceeded
- **TestCaseStatus**: passed, failed, timeout, memory_exceeded, runtime_error

### 12.2 coding/execution/

**Status: IMPLEMENTED**

| File | Purpose |
|------|---------|
| `service.py` (523 lines) | **ExecutionService** — `execute()`: acquire lock → transition pending→running → execute test cases via sandbox → compare outputs → classify results → calculate weighted score → determine final status → persist. Designed for Celery worker (synchronous, blocking). |
| `contracts.py` | Frozen dataclasses: **SubmissionData** (language, source_code, coding_problem_id), **TestCase** (input_data, expected_output, weight, time/memory limits, is_hidden), **ExecuteSubmissionCommand**, **TestCaseExecutionResult** (status, passed, actual_output, runtime_ms, memory_kb, feedback), **ExecutionResult** (final status, score, per-test outcomes) |
| `state_machine.py` | `is_terminal_state()`, `is_valid_transition()`, `validate_transition()`. Transitions: pending→running, running→passed/failed/error/timeout/memory_exceeded |

### 12.3 coding/sandbox/

**Status: IMPLEMENTED**

| File | Purpose |
|------|---------|
| `executor.py` (394 lines) | **SandboxExecutor** — `execute()`: validate → resolve Docker image → build execution script → configure container (security hardening) → run → parse output → sanitize → return result. Stateless, thread-safe. Security: network isolation, filesystem isolation, resource limits, non-root, seccomp. |
| `contracts.py` | **SandboxExecutionRequest** (language: cpp/java/python3, source_code max 50K chars, input_data max 10MB, time_limit 100ms-30s, memory_limit 4MB-1GB), **SandboxExecutionResult** (stdout/stderr sanitized, exit_code, runtime_ms, memory_kb, timed_out, memory_exceeded, compilation_output) |
| `docker_runner.py` | Docker container management: image resolution, execution script building, container execution with resource limits |
| `output_parser.py` | Parse execution output (metrics extraction, exit code interpretation) |
| `sanitizer.py` | Output sanitization (remove internal paths, system info, truncate to 1MB) |

### 12.4 coding/evaluation/

**Status: IMPLEMENTED**

| File | Purpose |
|------|---------|
| `scorer.py` | `calculate_score()` (weighted formula: Σ(weight×passed)/Σ(weight)×100), `generate_feedback()` (status→human-readable), `generate_match_details()` (hidden test cases never get details — prevents info leakage) |
| `comparator.py` | `compare_outputs()` — expected vs actual output comparison |

### 12.5 coding/persistence/

**Status: IMPLEMENTED**

| File | Purpose |
|------|---------|
| `protocols.py` | **CodeSubmissionRepository** protocol (create, get_by_id, get_by_exchange_id, get_for_update, update_status, list_pending, count_submissions_since), **CodeExecutionResultRepository** protocol (create, get_by_submission, exists) |
| `models.py` | **CodeSubmissionModel** (code_submissions: exchange_id UNIQUE, coding_problem_id, language, source_code, execution_status, score, execution_time_ms, memory_kb), **CodeExecutionResultModel** (code_execution_results: submission_id, test_case_id, passed, actual_output, runtime_ms, memory_kb, UNIQUE(submission_id, test_case_id)) |
| `entities.py` | Domain entity dataclasses |
| `mappers.py` | Entity↔model mapping |
| `repositories.py` | Concrete SQL implementations |

### 12.6 coding/api/

**Status: REQUIREMENTS ONLY — NO CODE FILES**

### Dependencies
- config/ (SandboxSettings, SUPPORTED_LANGUAGES)
- shared/errors/ (SandboxExecutionError, SandboxTimeoutError)
- shared/observability/ (logging, metrics)
- persistence/postgres/ (shared Base, session)

---

## 13. Module: evaluation/

**Purpose:** Deterministic scoring engine — exchange-level evaluation against rubric dimensions, final interview result computation with snapshot-based aggregation, versioned results, human override support.

### Status: **REQUIREMENTS ONLY — NO CODE FILES**

Subdirectories (all contain only REQUIREMENTS.md):
- `scoring/` — Exchange-level scoring against rubric dimensions
- `aggregation/` — Section/template-level score aggregation
- `persistence/` — Repository pattern for evaluations/results
- `api/` — REST endpoints for evaluation
- `snapshots/` — Rubric/template snapshot management

### Planned Entities (from REQUIREMENTS.md)
- **evaluations** — one per exchange, UNIQUE(exchange_id, is_final) WHERE is_final=true
- **evaluation_dimension_scores** — per-dimension scores, UNIQUE(evaluation_id, rubric_dimension_id)
- **interview_results** — final scores with rubric/template snapshots, UNIQUE(interview_id, is_current) WHERE is_current=true
- **supplementary_reports** — additional analysis reports

### Planned Contracts
- EvaluateExchangeRequest, HumanOverrideRequest, FinalizeInterviewRequest
- EvaluationResponse (dimension scores), InterviewResultResponse (section scores, recommendation)

### Dependencies (planned)
- ai/llm/ (for AI evaluation)
- ai/prompts/ (evaluation prompt templates)
- interview/ (exchange data)
- admin/ (rubric/template data)

---

## 14. Module: proctoring/

**Purpose:** Interview integrity monitoring — event ingestion, rule-based detection, risk scoring.

### Status: **REQUIREMENTS ONLY — NO CODE FILES**

Subdirectories (all contain only REQUIREMENTS.md):
- `ingestion/` — Proctoring event ingestion
- `rules/` — Detection rules (tab switch, copy-paste, multiple faces, etc.)
- `risk_model/` — Risk score computation
- `persistence/` — Proctoring event/score storage

### Dependencies (planned)
- interview/ (submission context)
- shared/errors/ (ProctoringViolation)

---

## 15. Cross-Module Dependency Map

```
config/  ←── (leaf — no domain dependencies)
shared/  ←── (leaf — no domain dependencies)
persistence/  ←── config/, shared/

bootstrap/  ←── config/, shared/, persistence/, auth, admin, interview, question, audio
auth/  ←── config/, shared/, persistence/postgres/
admin/  ←── shared/, persistence/postgres/
ai/  ←── config/, shared/, persistence/postgres/
audio/  ←── shared/
interview/  ←── shared/, persistence/postgres/, persistence/redis/
question/  ←── ai/, persistence/qdrant/, persistence/redis/, persistence/postgres/, shared/
coding/  ←── config/, shared/, persistence/postgres/
evaluation/  ←── (planned: ai/, interview/, admin/)
proctoring/  ←── (planned: interview/, shared/)
```

### Data Flow (runtime)
```
Candidate → auth/login → JWT
         → interview/session/start → submission created → Redis cached
         → interview/orchestration → question/selection → ai/llm → exchange created
         → audio/ingestion → audio/transcription → interview/exchanges (immutable)
         → coding/sandbox → coding/execution → interview/exchanges (immutable)
         → evaluation/scoring → evaluation/aggregation → interview_results
```

---

## 16. Implementation Status Summary

| Module | Status | Code Files | Notes |
|--------|--------|------------|-------|
| config/ | ✅ Complete | 6 | All settings, flags, security, environments |
| shared/errors/ | ✅ Complete | 5 | 25+ error types, classification, serialization |
| shared/auth_context/ | ✅ Complete | 4 | IdentityContext, dependencies, deprecated AuthContext |
| shared/observability/ | ✅ Complete | 7 | Logging, tracing, metrics, telemetry, redaction |
| persistence/postgres/ | ✅ Complete | 3 | Engine, session, base |
| persistence/redis/ | ✅ Complete | 2 | Client, locks (Lua) |
| persistence/qdrant/ | ✅ Complete | 4 | Client, collections, operations, health |
| bootstrap/ | ✅ Complete | 6 | App factory, lifespan, routers, middleware, dependencies |
| auth/ | ✅ Complete | ~15 | Full auth lifecycle (register, login, JWT, RBAC, password) |
| admin/ | ✅ Complete | ~20 | Full CRUD for all content entities + validation + overrides |
| ai/llm/ | ✅ Complete | ~10 | Provider abstraction, 4 providers, contracts, errors |
| ai/prompts/ | ✅ Complete | ~10 | Service, renderer, parser, repository, models |
| ai/telemetry/ | ✅ Complete | 4 | Tracker, cost estimator, contracts, aggregation |
| audio/ingestion/ | ✅ Complete | ~8 | Service, buffer, normalizer, session manager, silence detector |
| audio/transcription/ | ✅ Complete | ~8 | Service, providers, fallback chain, streaming |
| audio/analysis/ | ✅ Complete | ~7 | Completeness, fillers, speech rate, sentiment, intent |
| interview/session/ | ✅ Complete | 6 | Session lifecycle, state machine, repo, API, Redis sync |
| interview/exchanges/ | ✅ Complete | 7 | Immutable exchanges, state machine, validators, intent, clarification |
| interview/orchestration/ | ❌ Requirements only | 0 | 1146-line spec, no implementation |
| interview/realtime/ | ❌ Requirements only | 0 | 814-line spec, no implementation |
| interview/persistence/ | ❌ Requirements only | 0 | Handled by session/persistence/ currently |
| interview/api/ | ❌ Requirements only | 0 | Handled by session/api/ currently |
| question/selection/ | ✅ Complete | ~8 | Selection service, adaptation, template parsing |
| question/retrieval/ | ✅ Complete | ~8 | Qdrant search, circuit breaker, cache, fallback |
| question/generation/ | ✅ Complete | ~8 | LLM generation, parsing, validation, fallback |
| coding/execution/ | ✅ Complete | 3 | Execution service, state machine, contracts |
| coding/sandbox/ | ✅ Complete | 5 | Docker executor, runner, parser, sanitizer, contracts |
| coding/evaluation/ | ✅ Complete | 2 | Scorer, comparator |
| coding/persistence/ | ✅ Complete | 5 | Protocols, models, entities, mappers, repositories |
| coding/api/ | ❌ Requirements only | 0 | No routes implemented |
| evaluation/ | ❌ Requirements only | 0 | All 5 subdirs have only REQUIREMENTS.md |
| proctoring/ | ❌ Requirements only | 0 | All 4 subdirs have only REQUIREMENTS.md |

### Summary
- **Implemented modules:** 16 (fully coded and functional)
- **Requirements-only modules:** 7 (detailed specs exist, no code)
- **Total code files:** ~200+
- **Total REQUIREMENTS.md files:** ~25+

---

## 17. Database Schema Summary

(From docs/schema.sql — 4614 lines)

### PostgreSQL Enums
admin_role, admin_status, candidate_plan, code_execution_status, coding_topic_type, difficulty_level, evaluator_type, interview_mode, interview_scope, media_type, organization_plan, organization_status, organization_type, problem_pipeline_status, problem_source, proctoring_severity, question_type, report_type, submission_status, template_scope, user_status

### Core Tables (30+)
| Table | Owner Module | Key Relationships |
|-------|-------------|-------------------|
| users | auth | Base identity for admins + candidates |
| organizations | auth/admin | Tenant container |
| admins | auth | user_id FK, organization_id FK |
| candidates | auth | user_id FK |
| refresh_tokens | auth | user_id FK, token_hash UNIQUE |
| auth_audit_log | auth | INSERT-ONLY |
| audit_logs | admin | General audit trail |
| interview_templates | admin | organization_id FK, template_structure JSONB |
| interview_template_roles | admin | Composite PK (template_id, role_id) |
| interview_template_rubrics | admin | template_id, rubric_id, section_name |
| rubrics | admin | organization_id FK, scope |
| rubric_dimensions | admin | rubric_id FK, weight sum=1.0 |
| roles | admin | organization_id FK |
| topics | admin | Hierarchical (parent_topic_id self-ref) |
| coding_topics | admin | topic_type ENUM |
| questions | admin/question | organization_id, question_type, difficulty |
| coding_problems | admin/coding | difficulty, scope |
| coding_test_cases | admin/coding | coding_problem_id FK |
| interview_submission_windows | admin | organization_id, start/end time, scope |
| window_role_templates | admin | window_id, role_id, template_id |
| interview_submissions | interview | candidate_id, window_id, role_id, template_id, status, template_structure_snapshot JSONB |
| interview_exchanges | interview | submission_id, question_id OR coding_problem_id, sequence_number, metadata JSONB |
| code_submissions | coding | exchange_id UNIQUE, execution_status |
| code_execution_results | coding | submission_id, test_case_id, UNIQUE pair |
| evaluations | evaluation | exchange_id, rubric_id, UNIQUE(exchange_id, is_final) WHERE is_final |
| evaluation_dimension_scores | evaluation | evaluation_id, dimension_id, UNIQUE pair |
| interview_results | evaluation | interview_id, snapshots JSONB, UNIQUE(interview_id, is_current) WHERE is_current |
| supplementary_reports | evaluation | result_id, report_type |
| embeddings | persistence/qdrant | Reference table for vector metadata |
| prompt_templates | ai/prompts | prompt_type, organization_id, is_active |
| media_artifacts | audio | media_type, storage_path |
| proctoring_events | proctoring | submission_id, severity |
| resumes | question | candidate_id |
| job_descriptions | question | organization_id |

---

*End of comprehensive audit.*
