# Comprehensive Repository Audit — AI Interviewer

> **Generated**: Research-only audit of every module under `/app`.  
> **Scope**: Enumerate all modules, document structure, public interfaces, domain services, persistence classes, contracts/DTOs, enums, and external dependencies.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module Inventory](#2-module-inventory)
3. [Module: bootstrap](#3-module-bootstrap)
4. [Module: config](#4-module-config)
5. [Module: shared](#5-module-shared)
6. [Module: auth](#6-module-auth)
7. [Module: admin](#7-module-admin)
8. [Module: persistence](#8-module-persistence)
9. [Module: ai](#9-module-ai)
10. [Modules: Specification-Only (No Python Code)](#10-modules-specification-only)
11. [External Dependencies](#11-external-dependencies)
12. [Test Coverage Structure](#12-test-coverage-structure)
13. [Cross-Cutting Patterns](#13-cross-cutting-patterns)
14. [Key Observations & Gaps](#14-key-observations--gaps)

---

## 1. Architecture Overview

**Type**: FastAPI monolith with 13 top-level modules under `app/`.

**Entry Point**: `main.py` → `uvicorn main:app` → imports `app` from `app.bootstrap` → calls `create_app()` factory.

**Infrastructure Stack**:
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Framework | FastAPI 0.109 | HTTP API |
| ORM / DB | SQLAlchemy 2.0 + PostgreSQL | Primary persistence (asyncpg driver) |
| Cache / Sessions | Redis 5.0 (hiredis) | Session state, rate limiting, distributed locks |
| Vector DB | Qdrant 1.12 | Embedding storage & similarity search |
| LLM | Groq (primary), OpenAI/Anthropic/Gemini (stubs) | Text generation, structured output |
| Embeddings | Self-hosted all-mpnet-base-v2 (768-dim) | Question/resume embeddings |
| Auth | PyJWT (RS256/HS256) + bcrypt | JWT access tokens, password hashing |
| Observability | prometheus_client, structlog | Metrics, structured logging, tracing |
| Task Queue | Celery + Redis broker | Background tasks (configured, not wired) |

**Multi-Tenancy Model**: Organization-scoped. Super-org (`org_id=1`) owns base content. Tenants override via `*_overrides` tables (template_overrides, rubric_overrides, role_overrides, topic_overrides, question_overrides, coding_problem_overrides).

**API Prefix**: `/api/v1/` — only `/api/v1/auth` is currently registered. Health endpoints at `/health` and `/health/database`.

---

## 2. Module Inventory

| Module | Implementation Status | Python Files | Lines of Code (approx) |
|--------|----------------------|-------------|----------------------|
| `bootstrap` | ✅ Complete | 7 | ~500 |
| `config` | ✅ Complete | 6 | ~700 |
| `shared` | ✅ Complete | 23 | ~2,500 |
| `auth` | ✅ Complete | ~20 | ~3,000 |
| `admin` | ✅ Domain + Persistence + Validation | ~16 | ~5,500 |
| `persistence` | ✅ Infrastructure | ~15 | ~2,500 |
| `ai` | ⚠️ Partial (Groq done, 3 stubs) | ~13 | ~2,500 |
| `audio` | ❌ Specs only | 0 | — |
| `coding` | ❌ Specs only | 0 | — |
| `evaluation` | ❌ Specs only | 0 | — |
| `interview` | ❌ Specs only | 0 | — |
| `proctoring` | ❌ Specs only | 0 | — |
| `question` | ❌ Specs only | 0 | — |

---

## 3. Module: bootstrap

**Purpose**: Application assembly — wires all middleware, routers, exception handlers, and lifespan events into the FastAPI app instance.

### Files

| File | Purpose |
|------|---------|
| `app.py` | `create_app() → FastAPI` factory; global `app = create_app()` singleton |
| `dependencies.py` | Re-exports convenience imports (`get_db_session`, `get_identity`, `require_admin`, etc.) |
| `middleware.py` | Registers 6 middleware in order: RequestContext → Logging → ErrorFormatting → CORS → GZip → RateLimit(stub) |
| `router_registry.py` | `register_routers(app)` — only auth router active at `/api/v1/auth`; all others commented out. Health endpoints at `/health`, `/health/database` |
| `exception_handlers.py` | 4 handlers: `BaseError` → structured JSON, `RequestValidationError` → 422, `HTTPException` → wrapped, `Exception` → 500 catch-all |
| `lifespan.py` | Async lifespan: PostgreSQL → Redis → Qdrant init on startup; reverse shutdown |
| `__init__.py` | Exports `app` |

### Public Interfaces

- `create_app() → FastAPI`
- `register_routers(app: FastAPI) → None`
- `register_middleware(app: FastAPI) → None`
- `register_exception_handlers(app: FastAPI) → None`
- `lifespan(app: FastAPI)` — async context manager

---

## 4. Module: config

**Purpose**: Centralized configuration via pydantic-settings, environment-specific behavior, feature flags, and security policies.

### Files

| File | Purpose |
|------|---------|
| `settings.py` | Master `Settings` class composing 10 sub-settings. Global `settings = Settings.load()` singleton. |
| `constants.py` | ~30 `Final` constants (API_V1_PREFIX, SUPPORTED_LANGUAGES, MAX_CODE_SIZE_BYTES, DEFAULT_EMBEDDING_DIM=768, etc.) |
| `environments.py` | `EnvironmentConfig` frozen dataclass via `create_env_config(app_env)` — controls debug, CORS, SSL, error detail |
| `feature_flags.py` | `FeatureFlags` frozen dataclass: ENABLE_AI_EVALUATION, ENABLE_PROCTORING, ENABLE_AUDIO_ANALYSIS, ENABLE_CODE_EXECUTION, ENABLE_PRACTICE_MODE, ENABLE_HUMAN_OVERRIDE, ENABLE_RESUME_PARSING |
| `security.py` | `SecurityConfig`, `CORSConfig`, `PasswordPolicy` frozen dataclasses. `PasswordPolicy.validate(password)` checks min length, uppercase, lowercase, digit, special char |
| `__init__.py` | Exports global singletons: `settings`, `feature_flags`, `env_config`, `security_config`, `cors_config`, `password_policy` |

### Sub-Settings Classes (in `settings.py`)

| Class | Key Fields |
|-------|-----------|
| `AppSettings` | app_env, debug, base_url, app_name, api_version |
| `DatabaseSettings` | database_url, db_pool_size(5), db_max_overflow(10), db_query_timeout(30), db_pool_pre_ping |
| `RedisSettings` | redis_url, redis_max_connections(20), redis_connection_timeout(5), redis_socket_timeout(5) |
| `QdrantSettings` | qdrant_url, qdrant_api_key, qdrant_collection_prefix, qdrant_embedding_dim(768), qdrant_prefer_grpc |
| `LLMSettings` | default_llm_provider("groq"), default_model("gpt-oss-120b"), groq_api_key, gemini_api_key, openai_api_key, anthropic_api_key, embedding_model_url, llm_timeout(60), llm_max_retries(2) |
| `SandboxSettings` | sandbox_type("docker"), sandbox_timeout(30), sandbox_memory_limit_mb(256), sandbox_cpu_limit(1.0) |
| `SecuritySettings` | jwt_secret_key, jwt_algorithm("RS256"), access_token_ttl(1800), refresh_token_ttl(604800), password_min_length(8) |
| `AudioSettings` | max_audio_size_mb(50), supported_formats, sample_rate(16000), whisper_model("base") |
| `RateLimitSettings` | enabled(true), requests_per_minute(60), burst_size(10) |
| `FeatureFlagsSettings` | Mirrors `FeatureFlags` with defaults from env |

---

## 5. Module: shared

**Purpose**: Cross-cutting infrastructure used by all domain modules — error taxonomy, identity/auth context, observability.

### Sub-module: `shared/errors`

| File | Contents |
|------|----------|
| `exceptions.py` | `BaseError` (frozen dataclass: error_code, message, request_id, metadata, http_status_code). 23 subclasses organized by category: Auth (401/403), Domain (409/422/business-specific), AI Provider, Infrastructure, Internal. Backward-compat alias `ApplicationError`. |
| `serializers.py` | `serialize_rest_error(err, request_id)`, `serialize_websocket_error(err)`, `serialize_error_for_logging(err)` |
| `classification.py` | `is_fatal_error(err)`, `get_log_level(err)`, `should_send_to_client(err)` |
| `config.py` | `ErrorConfig` pydantic settings (include_stack_traces, max_metadata_size, default_error_code) |

**Error Hierarchy** (key classes):
```
BaseError
├── AuthenticationError (401)
├── AuthorizationError (403)
├── TenantIsolationViolation (403)
├── NotFoundError (404)
├── ConflictError (409)
├── ValidationError (422)
├── RateLimitExceeded (429)
├── InterviewNotActiveError (409)
├── TemplateImmutabilityViolation (409)
├── DomainInvariantViolation (422)
├── AIProviderError (502)
│   └── AIProviderTimeoutError (504)
├── SandboxExecutionError (500)
├── InfrastructureError (500)
│   ├── DatabaseError
│   └── CacheError
├── ConfigurationError (500)
└── InternalServerError (500)
```

### Sub-module: `shared/auth_context`

| File | Contents |
|------|----------|
| `models.py` | `IdentityContext` frozen dataclass (user_id, user_type:UserType, organization_id, admin_role:AdminRole, token_version, issued_at, expires_at). Enums: `UserType` (ADMIN, CANDIDATE), `AdminRole` (SUPERADMIN, ADMIN, READ_ONLY). `TaskContext` for async task propagation. |
| `builder.py` | `IdentityBuilder.from_jwt_claims(claims)` — transforms JWT claims dict → `IdentityContext` |
| `dependencies.py` | FastAPI deps: `get_identity`, `get_optional_identity`, `require_admin`, `require_candidate`, `require_superadmin`, `get_token_validator` |
| `middleware.py` | `IdentityInjectionMiddleware` — extracts Bearer token → validates → attaches `IdentityContext` to `request.state.identity` |
| `scope.py` | `enforce_organization_scope(identity, target_org_id)`, `enforce_candidate_scope(identity, candidate_user_id)`, `require_organization_admin(identity, org_id)` |
| `registry.py` | `ConnectionRegistry` — Redis-backed WebSocket connection tracker (single connection per submission_id) |
| `websocket.py` | `authenticate_websocket(websocket)` helper |
| `config.py` | `AuthContextConfig` dataclass |

### Sub-module: `shared/observability`

| File | Contents |
|------|---------|
| `logging.py` | `StructuredFormatter` (JSON log format), `ContextLogger` wrapper with auto-injected fields |
| `tracing.py` | `TraceContext` dataclass, generators: `generate_request_id`, `generate_connection_id`, `generate_session_id`. `RequestIDMiddleware`. |
| `metrics.py` | `MetricsRegistry` with Prometheus metrics: interview_exchanges_total, interview_duration_seconds, question_generation/retrieval durations, evaluation metrics, sandbox metrics, websocket metrics, ai_provider metrics. `track_latency` ctx-mgr, `track_operation` decorator. |
| `telemetry.py` | `AITelemetry` dataclass (provider, model, tokens, latency, cost). `log()`, `emit_metrics()`. `track_ai_call` ctx-mgr. |
| `redaction.py` | `redact_sensitive_data(data, patterns)` recursive redactor, `mask_token(token)` |
| `config.py` | `ObservabilityConfig` pydantic settings |

---

## 6. Module: auth

**Purpose**: User registration, login, JWT token lifecycle, RBAC enforcement. The only module with an active API router.

### API Endpoints (`/api/v1/auth`)

| Method | Path | Purpose | Status |
|--------|------|---------|--------|
| POST | `/register/admin` | Admin registration (201) | Active |
| POST | `/register/candidate` | Candidate registration (201) | Active |
| POST | `/login` | Email/password login → access+refresh tokens (200) | Active |
| POST | `/refresh` | Refresh access token (200) | Active |
| POST | `/logout` | Revoke refresh token (200) | Active |
| GET | `/me` | Get current user profile (200) | Active |

### Contracts / DTOs (`auth/contracts/`)

**Request Schemas** (Pydantic BaseModel):
- `AdminRegistrationRequest` (name, email, password, organization_id, role)
- `CandidateRegistrationRequest` (name, email, password)
- `LoginRequest` (email, password)
- `RefreshTokenRequest` (refresh_token)
- `LogoutRequest` (refresh_token)

**Response Schemas**:
- `RegistrationResponse` (user_id, email, user_type, message)
- `LoginResponse` (access_token, refresh_token, token_type, expires_in, user)
- `TokenRefreshResponse` (access_token, token_type, expires_in)
- `CurrentUserResponse` (user, profile)
- `UserProfileResponse` (id, name, email, user_type, status, timestamps)

**Enums**:
- `AuthErrorCode` (INVALID_CREDENTIALS, USER_INACTIVE, TOKEN_EXPIRED, EMAIL_ALREADY_EXISTS, INVALID_TOKEN, REFRESH_TOKEN_REVOKED, ACCOUNT_LOCKED, INSUFFICIENT_PERMISSIONS)

**Claims** (TypedDicts):
- `AdminAccessTokenClaims` (sub, user_type, organization_id, admin_role, token_version, iat, exp)
- `CandidateAccessTokenClaims` (sub, user_type, token_version, iat, exp)

### Domain Services (`auth/domain/`)

| Class / Function | Responsibility |
|-----------------|---------------|
| `AuthService` | Orchestrator: `register_admin`, `register_candidate`, `login`, `refresh`, `logout`, `validate`. 1024 lines. |
| `JWTService` | `generate_access_token`, `generate_refresh_token`, `hash_refresh_token`, `verify_access_token`. RS256/HS256 via PyJWT. |
| `PasswordHasher` | `hash(password)`, `verify(password, hash)`, `validate_complexity(password)`. bcrypt with configurable rounds. |
| `RBACEnforcer` | `Permission` enum (VIEW_USERS, MANAGE_USERS, etc.). `PERMISSION_MATRIX` maps AdminRole → set of permissions. `has_permission(identity, permission)`, `enforce(identity, permission)`. |

**Domain Command DTOs** (`contracts.py`):
- `RegisterAdminCommand`, `RegisterCandidateCommand`, `LoginCommand`, `RefreshTokenCommand`, `LogoutCommand`, `ValidateTokenCommand`

**Domain Result DTOs**:
- `UserProfile`, `AuthenticationResult`, `TokenValidationResult`

### Persistence (`auth/persistence/`)

**ORM Models** (SQLAlchemy declarative_base):

| Model | Table | Key Columns |
|-------|-------|------------|
| `User` | `users` | id, name, email, password_hash, user_type, status, token_version, last_login_at |
| `Admin` | `admins` | user_id (FK→users), organization_id (FK→organizations), role, status |
| `Candidate` | `candidates` | user_id (FK→users), plan, status, profile_metadata (JSONB) |
| `RefreshToken` | `refresh_tokens` | user_id, token_hash, device_info, ip_address, expires_at, revoked_at |
| `AuthAuditLog` | `auth_audit_logs` | user_id, event_type, ip_address, user_agent, event_metadata (JSONB) |

**Repositories** (session-injected, flush-not-commit):

| Repository | Key Methods |
|-----------|------------|
| `UserRepository` | create, get_by_id, find_by_email, email_exists, update_last_login, update_password, update_status, increment_token_version |
| `AdminRepository` | create, get_by_id, find_by_user_id, list_by_organization, update_role, update_status |
| `CandidateRepository` | create, get_by_id, find_by_user_id, update_profile, update_status |
| `RefreshTokenRepository` | create, find_by_hash, list_active_for_user, revoke, revoke_all_for_user |
| `AuthAuditLogRepository` | log_event, get_recent_events, get_failed_login_attempts, get_suspicious_events |

---

## 7. Module: admin

**Purpose**: Content management for interview templates, rubrics, roles, topics, questions, coding problems, submission windows, and tenant overrides. Largest domain module.

**Note**: `admin/api/` has no `routes.py` — admin API endpoints are NOT yet implemented (commented out in `router_registry.py`).

### Domain Entities (`admin/domain/entities.py`) — 367 lines

All are `@dataclass` classes mapping 1:1 to PostgreSQL tables:

| Entity | Table | Key Fields |
|--------|-------|-----------|
| `Template` | interview_templates | id, name, description, scope, organization_id, template_structure(JSONB), rules(JSONB), version, is_active |
| `TemplateRole` | interview_template_roles | interview_template_id, role_id |
| `TemplateRubric` | interview_template_rubrics | id, interview_template_id, rubric_id, section_name |
| `Rubric` | rubrics | id, organization_id, name, description, scope, schema(JSONB), is_active |
| `RubricDimension` | rubric_dimensions | id, rubric_id, dimension_name, max_score(Decimal), weight(Decimal), criteria(JSONB), sequence_order |
| `Role` | roles | id, name, description, scope, organization_id |
| `Topic` | topics | id, name, description, parent_topic_id (self-ref), scope, organization_id, estimated_time_minutes |
| `CodingTopic` | coding_topics | id, name, description, topic_type, parent_topic_id (self-ref), display_order |
| `Question` | questions | id, question_text, answer_text, question_type, difficulty, scope, is_active |
| `CodingProblem` | coding_problems | id, title, body, difficulty, scope, constraints, examples(JSONB), hints(JSONB), code_snippets(JSONB), stats(JSONB) |
| `Window` | interview_submission_windows | id, organization_id, admin_id, name, scope, start_time, end_time, timezone, allow_resubmission |
| `WindowRoleTemplate` | window_role_templates | id, window_id, role_id, template_id, selection_weight |
| `OverrideRecord` | *_overrides tables | id, organization_id, base_content_id, content_type, override_fields(JSONB), is_active |

### Enums (in `entities.py`)

| Enum | Values |
|------|--------|
| `TemplateScope` | PUBLIC, ORGANIZATION, PRIVATE |
| `InterviewScope` | GLOBAL, LOCAL, ONLY_INVITED |
| `DifficultyLevel` | EASY, MEDIUM, HARD |
| `QuestionType` | BEHAVIORAL, TECHNICAL, SITUATIONAL, CODING |
| `CodingTopicType` | DATA_STRUCTURE, ALGORITHM, PATTERN, SYSTEM_DESIGN, LANGUAGE_SPECIFIC, TRAVERSAL |
| `ContentType` | TEMPLATE, RUBRIC, ROLE, TOPIC, QUESTION, CODING_PROBLEM |

### Constants

- `SUPER_ORG_ID = 1` — superadmin organization
- `RUBRIC_WEIGHT_TOLERANCE = 0.001` — weight sum tolerance
- `IMMUTABLE_OVERRIDE_FIELDS` — frozenset: id, organization_id, scope, created_at, updated_at

### Domain Services (`admin/domain/services.py`) — 1394 lines

| Service | Injected Repos | Key Methods |
|---------|---------------|------------|
| `TemplateService` | template, submission, override, rubric, role, audit | get_template, get_effective_template (with override merge), list_templates, create_template, update_template (immutability-safe versioning), activate/deactivate, set_template_roles, set_template_rubrics, create/update/delete_template_override |
| `RubricService` | rubric, submission, override, audit | get_rubric, list_rubrics, get_dimensions, create_rubric, update_rubric, deactivate_rubric. Enforces: weight sum == 1.0 ± 0.001, unique sequence_order |
| `RoleService` | role, submission, override, audit | get_role, list_roles, create_role, update_role. Name uniqueness per org. |
| `TopicService` | topic, override, audit | get/list/create/update for both general topics and coding topics. Cycle detection in parent hierarchy. |
| `QuestionService` | question, override, audit | get_question, list_questions, create_question, update_question, create_question_override |
| `CodingProblemService` | problem, override, audit | get/list/create/update_problem |
| `WindowService` | window, role, template, submission, audit | get/list/create/update_window. Validates: end_time > start_time, non-overlapping windows for same role (if !allow_resubmission), mapping references exist. |

**Key Invariants Enforced**:
1. **Immutability after use** — templates referenced by submissions get versioned (INSERT new row) instead of mutated
2. **RBAC** — superadmin can do everything; admin can CRUD own org; read_only can only GET
3. **Tenant isolation** — non-superadmin only sees own org + super-org content
4. **Override restrictions** — only super-org base content can be overridden; immutable fields blocked
5. **Rubric weight sum** — dimension weights must sum to 1.0 ± 0.001
6. **No topic cycles** — parent chain walked up to 50 levels to detect cycles

### Authorization (`admin/domain/authorization.py`)

| Function | Purpose |
|----------|---------|
| `authorize_admin_operation(identity, operation, resource_org_id)` | RBAC gate: read_only → GET only; delegates tenant isolation to `enforce_organization_scope` |
| `authorize_base_content_mutation(identity)` | Only superadmin can modify org_id=1 content |
| `authorize_override_operation(identity, base_content_org_id, override_org_id, operation)` | Base content must be super-org; standard operation + tenant check |

### Repository Protocols (`admin/domain/protocols.py`) — 401 lines

10 `Protocol` interfaces (all `@runtime_checkable`):

| Protocol | Methods |
|----------|---------|
| `TemplateRepository` | get_by_id, list_for_organization, count_for_organization, create, update, exists_with_name, get_latest_version, set/get_template_roles, set/get_template_rubrics |
| `RubricRepository` | get_by_id, list/count_for_organization, create, update, exists_with_name, get/set_dimensions |
| `RoleRepository` | get_by_id, list/count_for_organization, create, update, exists_with_name |
| `TopicRepository` | get/list/count/create/update for both topics and coding_topics; get_topic_ancestors, get_coding_topic_ancestors |
| `QuestionRepository` | get_by_id, list/count_for_organization, create, update |
| `CodingProblemRepository` | get_by_id, list/count_for_organization, create, update |
| `WindowRepository` | get_by_id, list/count_for_organization, create, update, find_overlapping_windows, get/set_mappings |
| `SubmissionRepository` | template_is_in_use, rubric_is_in_use, role_is_in_use, window_has_submissions (read-only) |
| `OverrideRepository` | get_override, create_override, update_override, delete_override, list_overrides_for_organization, mark_overrides_stale |
| `AuditLogRepository` | log(organization_id, actor_user_id, action, entity_type, entity_id, old_value, new_value, ip_address, user_agent) |

### Persistence (`admin/persistence/`)

**ORM Models** (`models.py` — 798 lines, 19 model classes):

Core entities: `InterviewTemplateModel`, `InterviewTemplateRoleModel`, `InterviewTemplateRubricModel`, `RubricModel`, `RubricDimensionModel`, `RoleModel`, `TopicModel`, `CodingTopicModel`, `QuestionModel`, `CodingProblemModel`, `InterviewSubmissionWindowModel`, `WindowRoleTemplateModel`, `InterviewSubmissionModel` (read-only), `AuditLogModel`.

Override tables (6, identical structure): `TemplateOverrideModel`, `RubricOverrideModel`, `RoleOverrideModel`, `TopicOverrideModel`, `QuestionOverrideModel`, `CodingProblemOverrideModel`.

`OVERRIDE_MODEL_MAP` — dict mapping ContentType string → model class.

**Repository Implementations** (`repositories.py` — 915 lines, 9 classes):

| Class | Protocol |
|-------|----------|
| `SqlTemplateRepository` | TemplateRepository |
| `SqlRubricRepository` | RubricRepository |
| `SqlRoleRepository` | RoleRepository |
| `SqlTopicRepository` | TopicRepository (general + coding) |
| `SqlQuestionRepository` | QuestionRepository |
| `SqlCodingProblemRepository` | CodingProblemRepository |
| `SqlWindowRepository` | WindowRepository |
| `SqlSubmissionRepository` | SubmissionRepository (read-only) |
| `SqlOverrideRepository` | OverrideRepository (generic across all 6 content types) |
| `SqlAuditLogRepository` | AuditLogRepository (insert-only) |

Helper functions: `_paginate(query, page, per_page)`, `_org_filter(model_cls, org_id)` — multi-tenancy filter showing own org + super-org content.

**Mappers** (`mappers.py` — 466 lines): Bidirectional `*_model_to_entity()` / `*_entity_to_model()` for all 12 entity types + override. All mappers accept optional `model=` param for in-place update.

### Validation (`admin/validation/`)

| Class | File | Purpose |
|-------|------|---------|
| `ValidationResult` | `result.py` | Frozen dataclass: `is_valid`, `errors: tuple[ValidationErrorDetail]`. Factory: `success()`, `failure()`, `from_single()`. Combinator: `merge()`, `merge_all()`. |
| `ValidationErrorDetail` | `result.py` | Frozen dataclass: field, message, code |
| `TemplateStructureValidator` | `template_validator.py` | Validates `template_structure` JSONB: has sections, valid section keys, per-section config (weight, enabled), coding section config, scoring config. Supports "simple" and "v2" template flavours. |
| `RubricValidator` | `rubric_validator.py` | Validates dimensions: weight sum == 1.0 ± tolerance, unique sequence_order, positive max_score/weight, non-empty dimension_name. Also `validate_dimension_weights_from_dicts()` for raw API payloads. |
| `OverrideValidator` | `override_validator.py` | Validates override fields: non-empty, no immutable fields, known mutable fields per content type, base content owned by super org. |
| `CrossReferenceValidator` | `cross_reference_validator.py` | Validates entity cross-references: template→role/rubric IDs exist, window mapping roles/templates exist and are active, topic parent exists with no cycles. Requires repository DI. |
| `PreActivationValidator` | `pre_activation_validator.py` | Composite validator for template activation: name, structure, ≥1 role, rubric cross-refs, dimension consistency for every linked rubric. |

---

## 8. Module: persistence

**Purpose**: Infrastructure primitives for PostgreSQL, Redis, and Qdrant. No business logic.

### Sub-module: `persistence/postgres`

| File | Contents |
|------|----------|
| `base.py` | `Base = declarative_base()` — shared by all ORM models. `import_all_models()` ensuring metadata registration. `get_table_names()`. |
| `engine.py` | `create_db_engine(config)` with QueuePool, pool_pre_ping, query timeout, exponential backoff retry (3 attempts). `init_engine(config)` global singleton. `get_engine()`, `cleanup_engine()`. Pool event listeners (connect, checkout, checkin). |
| `session.py` | `init_session_factory()` → `SessionLocal` (sessionmaker). `get_db_session()` — FastAPI dependency (close-only). `get_db_session_with_commit()` — auto-commit dependency. `db_session_context()` — context manager with commit/rollback. `execute_with_retry(session, operation, max_retries=3)`. |
| `health.py` | `check_postgres_health()` → dict with status (healthy/degraded/unhealthy), latency_ms, pool metrics. `HealthStatus` enum. |

### Sub-module: `persistence/redis`

| File | Contents |
|------|----------|
| `client.py` | `create_redis_client(config)` with ConnectionPool, retry (3 attempts), PING test. `init_redis_client(config)` global singleton. `get_redis_client()`, `cleanup_redis()`. `RedisClientError(ApplicationError)`. |
| `locks.py` | `acquire_lock(lock_key, timeout, retry_interval)` — context manager with SET NX + EX, Lua script safe release. `try_acquire_lock()` non-blocking. `release_lock()` manual. `LockAcquisitionError`, `LockReleaseError`. |
| `operations.py` | Pure ops: `set_value`, `get_value`, `delete_key`, `exists`, `set_ttl`, `get_ttl`. Hash ops: `hash_set`, `hash_get`, `hash_get_all`, `hash_delete`. Counter: `increment`, `decrement`. Batch: `batch_get`, `batch_delete`. Pattern: `scan_keys`, `delete_by_pattern`. ~588 lines. |
| `health.py` | `check_redis_health()` → dict with status, latency_ms, Redis server info (memory, clients, version, ops/sec). `HealthStatus` enum. |

### Sub-module: `persistence/qdrant`

| File | Contents |
|------|----------|
| `client.py` | `create_qdrant_client(config)` with retry (3 attempts), gRPC preference. `init_qdrant_client(config)` global singleton. `get_qdrant_client()`, `get_collection_name()`, `get_vector_dimension()`, `cleanup_qdrant()`. `QdrantConnectionError`, `QdrantCollectionError`. |
| `collections.py` | `create_collection_if_not_exists(distance=COSINE)`, `validate_collection_schema()`, `delete_collection()`, `get_collection_info()`. |
| `operations.py` | `store_embedding(vector, org_id, source_type, source_id, model, version, ...)` → point_id(UUID). `store_embeddings_batch(embeddings, batch_size=100)`. `search_similar(query_vector, org_id, limit, filters)`. `get_embedding(point_id)`. `delete_embedding(point_id)`. `delete_embeddings_by_source(source_type, source_id)`. Multi-tenant filtering via `organization_id` in payload. ~501 lines. |
| `health.py` | `check_qdrant_health()` → dict with status, latency_ms, collection count, collection info. |

---

## 9. Module: ai

**Purpose**: LLM provider abstraction layer with pluggable providers, unified request/response contracts, error handling, token counting, and telemetry.

### Provider Architecture

```
BaseLLMProvider (ABC)
├── GroqProvider        ✅ Fully implemented (482 lines)
├── OpenAIProvider      ⚠️ Stub (NotImplementedError)
├── AnthropicProvider   ⚠️ Stub (NotImplementedError)
└── GeminiProvider      ⚠️ Stub (NotImplementedError)

BaseEmbeddingProvider (ABC)
└── EmbeddingProvider   ✅ Fully implemented (self-hosted all-mpnet-base-v2)

BaseTranscriptionProvider (ABC)
└── (no implementations)
```

### Contracts (`ai/llm/contracts.py`) — 312 lines

| DTO | Type | Key Fields |
|-----|------|-----------|
| `LLMRequest` | dataclass | prompt, model, system_prompt, temperature(0.7), max_tokens, top_p(1.0), json_mode, schema, timeout_seconds(60), deterministic, request_id, organization_id |
| `LLMResponse` | dataclass | success, text, finish_reason, telemetry, metadata, error, raw_response |
| `TelemetryData` | dataclass | model_id, provider, prompt_tokens, completion_tokens, total_tokens, latency_ms, success, error_type, retry_count, estimated_cost_usd |
| `LLMError` | dataclass | type, message, retryable, provider_error_code, provider_error_details |
| `EmbeddingRequest` | dataclass | text, model("all-mpnet-base-v2"), timeout_seconds(30) |
| `EmbeddingResponse` | dataclass | success, embedding(List[float]), dimensions, telemetry, error |
| `TranscriptionRequest` | dataclass | audio_data, model, language |
| `TranscriptionResponse` | dataclass | success, text, confidence, telemetry, error |

### Enums

| Enum | Values |
|------|--------|
| `LLMProvider` | GROQ, GEMINI, OPENAI, ANTHROPIC, LOCAL |
| `LLMErrorType` | TIMEOUT, RATE_LIMIT, AUTHENTICATION, PROVIDER_ERROR, SCHEMA_VALIDATION, UNKNOWN |

### Error Classes (`ai/llm/errors.py`) — 360 lines

| Error | Parent | HTTP | Retryable |
|-------|--------|------|-----------|
| `LLMProviderError` | AIProviderError | 502 | configurable |
| `LLMTimeoutError` | AIProviderTimeoutError | 504 | always |
| `LLMRateLimitError` | BaseError | 429 | always |
| `LLMAuthenticationError` | BaseError | 401 | never |
| `LLMSchemaValidationError` | ValidationError | 422 | yes |
| `LLMContentFilterError` | BaseError | 451 | never |
| `LLMModelNotFoundError` | BaseError | 404 | never |
| `LLMContextLengthError` | BaseError | 422 | never |
| `LLMEmbeddingServiceError` | BaseError | 502 | configurable |
| `LLMConfigurationError` | BaseError | 500 | never |

### Factory (`ai/llm/provider_factory.py`)

`ProviderFactory`:
- `create_text_provider(provider_name?, api_key?)` → `BaseLLMProvider`
- `create_embedding_provider(api_key?, service_url?)` → `BaseEmbeddingProvider`
- `_get_api_key(provider_name)` — loads from `settings.llm.*_api_key`

Convenience: `get_groq_provider()`, `get_default_provider()`

### Token Counter (`ai/llm/utils/token_counter.py`)

- `estimate_tokens(text, model)` — heuristic: ~4 chars/token (English), ~3 (code), ~2 (non-English)
- `estimate_cost(prompt_tokens, completion_tokens, model_id)` — pricing table (Feb 2026 approx)
- `truncate_text(text, max_tokens, model)` — approximate truncation with sentence boundary

### Groq Provider (`ai/llm/providers/groq_provider.py`) — 482 lines

Fully implemented. Uses `httpx` async client against `https://api.groq.com/openai/v1`.

Supported models: llama-3.3-70b-versatile, llama-3.1-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768, gemma2-9b-it.

Methods: `generate_text(request)`, `generate_structured(request)` (JSON mode + schema validation + retry), `get_supported_models()`. Error handling maps HTTP status codes to typed errors (429→RateLimitError, 401→AuthenticationError, etc.).

### Un-implemented Sub-modules

- `ai/prompts/` — REQUIREMENTS.md only (prompt templates for interview stages)
- `ai/telemetry/` — REQUIREMENTS.md only (AI telemetry persistence)

---

## 10. Modules: Specification-Only

These 6 modules have `REQUIREMENTS.md` files specifying future implementation but **no Python code**.

### audio
- **Sub-modules**: analysis/, ingestion/, persistence/, transcription/
- **Planned**: Audio recording, WebSocket-based ingestion, Whisper transcription, analysis (filler word detection, pacing, silence detection)

### coding
- **Sub-modules**: api/, evaluation/, execution/, persistence/, sandbox/
- **Planned**: Code execution sandbox (Docker/Firecracker), test case evaluation, language support (Python, JS, Java, C++, Go, Rust), complexity analysis

### evaluation
- **Sub-modules**: aggregation/, api/, persistence/, scoring/, snapshots/
- **Planned**: AI-driven scoring per exchange, rubric dimension scoring, weighted aggregation, human override, immutable score snapshots

### interview
- **Sub-modules**: api/, exchanges/, orchestration/, persistence/, realtime/, session/
- **Planned**: WebSocket real-time interview flow, exchange management (Q&A + follow-ups), session state machine, orchestration of question selection → AI evaluation → next question

### proctoring
- **Sub-modules**: ingestion/, persistence/, risk_model/, rules/
- **Planned**: Webcam/tab-switch monitoring, rule-based anomaly detection, risk scoring model, event recording

### question
- **Sub-modules**: generation/, persistence/, prompting/, retrieval/, selection/
- **Planned**: AI question generation, vector similarity retrieval, adaptive selection based on difficulty/topic, prompt engineering

---

## 11. External Dependencies

From `requirements.txt`:

| Category | Package | Version | Usage |
|----------|---------|---------|-------|
| **Web** | fastapi | 0.109.0 | HTTP framework |
| | uvicorn[standard] | 0.27.0 | ASGI server |
| | python-multipart | 0.0.6 | Form data parsing |
| **Database** | sqlalchemy[asyncio] | 2.0.25 | ORM |
| | asyncpg | 0.29.0 | Async PostgreSQL driver |
| | psycopg2-binary | 2.9.9 | Sync PostgreSQL for tests |
| | alembic | 1.13.1 | Migrations |
| **Cache** | redis[hiredis] | 5.0.1 | Redis client |
| **Vector DB** | qdrant-client | 1.12.1 | Qdrant client |
| **Config** | pydantic[email] | 2.5.3 | Validation |
| | pydantic-settings | 2.1.0 | Env config |
| | python-dotenv | 1.0.0 | .env loading |
| **Auth** | pyjwt[crypto] | 2.8.0 | JWT encode/decode |
| | passlib[bcrypt] | 1.7.4 | Password hashing |
| | python-jose[cryptography] | 3.3.0 | JOSE/JWK |
| | bcrypt | 4.1.2 | bcrypt backend |
| **LLM** | groq | 0.4.2 | Groq SDK |
| | httpx | 0.26.0 | Async HTTP for LLM APIs |
| **Audio** | pydub | 0.25.1 | Audio processing |
| | scipy | 1.12.0 | Signal processing |
| | numpy | 1.26.3 | Numerical |
| **Observability** | structlog | 24.1.0 | Structured logging |
| | python-json-logger | 2.0.7 | JSON log formatting |
| | prometheus-client | 0.19.0 | Metrics |
| **Task Queue** | celery[redis] | 5.3.6 | Background tasks |
| **Testing** | pytest | 7.4.4 | Test runner |
| | pytest-asyncio | 0.23.3 | Async test support |
| | pytest-cov | 4.1.0 | Coverage |

---

## 12. Test Coverage Structure

Tests mirror the module structure under `tests/unit/` and `tests/integration/`:

```
tests/
├── conftest.py              — Session fixtures (env vars, mock configs)
├── unit/
│   ├── admin/
│   │   ├── validation/      — test_result, test_template_validator, test_rubric_validator,
│   │   │                      test_override_validator, test_pre_activation_validator
│   │   └── persistence/     — test_mappers, ...
│   ├── ai/
│   │   └── llm/             — (test files present)
│   ├── auth/
│   │   ├── api/             — test_routes
│   │   ├── contracts/       — test_schemas, test_enums_and_claims, test_responses
│   │   ├── domain/          — test_auth_service, test_jwt_service, test_password_hasher, test_rbac_enforcer
│   │   └── persistence/     — test_models, test_user_repository, test_admin_repository,
│   │                          test_candidate_repository, test_refresh_token_repository, test_audit_log_repository
│   ├── bootstrap/           — test_bootstrap
│   ├── config/              — (test files present)
│   ├── persistence/         — (test files present)
│   └── shared/
│       ├── auth_context/    — test_models, test_builder, test_scope, test_dependencies, test_websocket
│       └──                  — test_errors_exceptions, test_errors_serializers, test_errors_classification,
│                              test_errors_config, test_observability_logging, test_observability_tracing,
│                              test_observability_metrics, test_observability_telemetry,
│                              test_observability_redaction, test_observability_config
└── integration/
    ├── admin/
    ├── ai/
    ├── auth/
    ├── bootstrap/
    ├── config/
    ├── persistence/
    └── shared/
```

Total: **118 test files** discovered across unit and integration directories.

---

## 13. Cross-Cutting Patterns

### Repository Pattern
- All repositories accept `Session` via constructor
- Use `flush()` not `commit()` — caller manages transaction
- Return domain entities (dataclasses), never ORM models
- Multi-tenancy filter: `OR(org == caller_org, org == SUPER_ORG)`

### Domain Service Pattern
- Accept repository protocols (dependency injection)
- Enforce RBAC via `authorize_*` functions before any operation
- Log audit events after mutations
- Map between command/result DTOs and domain entities
- Zero database imports

### Override Pattern (Multi-Tenancy)
- Base content owned by super-org (org_id=1)
- Tenants create overrides with sparse `override_fields` JSONB
- At read time: base fields merged with override (override wins)
- 6 override tables with identical structure, routed via `OVERRIDE_MODEL_MAP`

### Error Pattern
- All domain errors extend `BaseError` (frozen dataclass)
- HTTP status code embedded in error class
- Exception handlers convert to structured JSON responses
- Errors classified as fatal/non-fatal with appropriate log levels

### Validation Pattern (Admin Module)
- `ValidationResult` accumulates errors (never fail-fast)
- Validators are stateless classes with static methods
- `merge_all()` combinator for composite validation
- `PreActivationValidator` orchestrates all checks before template activation

---

## 14. Key Observations & Gaps

### Implemented and Functional
1. **Auth flow** is complete end-to-end: registration → login → JWT → refresh → logout
2. **Admin domain layer** is comprehensive: entities, services, repository protocols, persistence, mappers, validation — all implemented
3. **Infrastructure layer** (PostgreSQL, Redis, Qdrant) is production-ready with retry logic, health checks, and connection pooling
4. **AI provider abstraction** has a working Groq implementation with full error handling
5. **Shared infrastructure** (errors, auth_context, observability) is thorough and well-structured

### Not Yet Implemented
1. **Admin API routes** — `admin/api/routes.py` does not exist; admin services have no HTTP exposure
2. **6 domain modules** — audio, coding, evaluation, interview, proctoring, question are pure specifications
3. **3 LLM providers** — OpenAI, Anthropic, Gemini are stubs (`NotImplementedError`)
4. **AI prompts** — no prompt templates implemented
5. **AI telemetry persistence** — telemetry data classes exist but no storage layer
6. **Celery integration** — dependency installed but no task definitions or broker wiring
7. **Alembic migrations** — dependency present but no migration scripts detected

### Architecture Notes
- The `import_all_models()` in `base.py` only imports `app.admin.persistence.models` — auth models are NOT registered with the shared `Base`. Auth uses its own `declarative_base()` instance, which means auth and admin tables cannot share a single `metadata.create_all()`.
- `settings.load()` returns `None` during testing (guarded by `TESTING` env var), so test fixtures must provide their own config.
- The rate-limit middleware in `bootstrap/middleware.py` is a stub (passes through).
- The `IdentityInjectionMiddleware` is imported but not registered in the standard middleware chain — it's presumably registered conditionally or per-route.
