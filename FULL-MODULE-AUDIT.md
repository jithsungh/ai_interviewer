# Comprehensive Module Audit — `app/`

> Generated from full source-code read of every module under `app/`.
> Covers architecture, public interfaces, domain services, persistence, contracts, enums, DI patterns, and cross-cutting concerns.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Module: `app/config`](#2-module-appconfig)
3. [Module: `app/bootstrap`](#3-module-appbootstrap)
4. [Module: `app/shared`](#4-module-appshared)
5. [Module: `app/persistence`](#5-module-apppersistence)
6. [Module: `app/auth`](#6-module-appauth)
7. [Module: `app/admin`](#7-module-appadmin)
8. [Module: `app/ai`](#8-module-appai)
9. [Module: `app/coding`](#9-module-appcoding)
10. [Module: `app/audio`](#10-module-appaudio)
11. [Module: `app/proctoring`](#11-module-appproctoring)
12. [Stub Modules: `question`, `interview`, `evaluation`](#12-stub-modules)
13. [Critical Findings & Observations](#13-critical-findings--observations)

---

## 1. Architecture Overview

| Concern | Technology |
|---|---|
| **Web Framework** | FastAPI (sync routes, lifespan management) |
| **ORM** | SQLAlchemy 2.x (sync `Session`, NOT async) |
| **Config** | Pydantic v2 `BaseSettings` with `.env` files |
| **Primary DB** | PostgreSQL (via `create_engine`, `QueuePool`) |
| **Cache / Sessions / Locks** | Redis (key-value, hash, distributed locks) |
| **Vector Search** | Qdrant (collection management, embedding storage) |
| **Auth** | JWT (RS256/HS256), bcrypt passwords, refresh token rotation |
| **Code Sandbox** | Docker containers (`subprocess.run`, network=none) |
| **LLM Providers** | Groq, Gemini, OpenAI, Anthropic (ABC-based `BaseLLMProvider`) |
| **Embeddings** | Self-hosted `all-mpnet-base-v2` (768-dim) |
| **Observability** | Structured JSON logging, Prometheus metrics, request-ID tracing |
| **Audio** | 16 kHz mono normalization → transcription (Whisper/Google/etc.) |

### Layering Convention

```
API Layer  →  Domain Services  →  Repository Protocols  →  Persistence (ORM/Redis/Qdrant)
    ↑                                     ↑
Pydantic contracts                 typing.Protocol (structural subtyping)
```

- **API**: FastAPI routers, Pydantic request/response models, zero business logic
- **Domain**: Pure Python, no HTTP/ORM imports, depends only on protocols
- **Persistence**: SQLAlchemy models + mappers, implements domain protocols
- **Shared**: Cross-cutting (errors, auth context, observability)

### DI Pattern

Services are **manually wired** per-request via factory functions:

```python
def build_template_service(session: Session) -> TemplateService:
    return TemplateService(
        template_repo=SqlTemplateRepository(session),
        override_repo=SqlOverrideRepository(session),
        ...
    )
```

No framework-level DI container. FastAPI `Depends()` provides `Session` and `IdentityContext`.

---

## 2. Module: `app/config`

**Files**: `__init__.py`, `settings.py`, `constants.py`, `environments.py`, `feature_flags.py`, `security.py`

### `settings.py` — Master Configuration

- `Settings` class with nested Pydantic `BaseSettings`:
  - `AppSettings` (app_name, version, environment, debug, host, port)
  - `DatabaseSettings` (url, pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=1800, echo=False, pool_pre_ping=True)
  - `RedisSettings` (url, max_connections=20, socket_timeout=5, retry_on_timeout=True)
  - `QdrantSettings` (host, port, grpc_port, collection_name, vector_size=768, api_key, prefer_grpc=True)
  - `LLMSettings` (default_provider="groq", default_model="llama-3.3-70b-versatile", embedding_provider="self_hosted", embedding_model="all-mpnet-base-v2")
  - `SandboxSettings` (sandbox_image_cpp/java/python, sandbox_default_timeout_ms=5000, sandbox_memory_limit_kb=262144, sandbox_process_limit=64, sandbox_seccomp_profile=None)
  - `SecuritySettings` (jwt_algorithm="HS256", jwt_secret_key, jwt_private_key_path, jwt_public_key_path, access_token_expire_minutes=30, refresh_token_expire_days=7)
  - `AudioSettings` (sample_rate=16000, channels=1, silence_threshold_ms=3000)
  - `RateLimitSettings` (enabled=False)
  - `FeatureFlagsSettings` (enable_ai_evaluation=True, enable_proctoring=False, ...)
- **Global singleton**: `settings = Settings.load()` (set to `None` when `TESTING=true`)

### `constants.py` — `Final` Typed Constants

```python
SUPPORTED_LANGUAGES: Final[list[str]] = ["cpp", "java", "python3"]
MAX_EXCHANGES_PER_INTERVIEW: Final[int] = 50
DIFFICULTY_LEVELS: Final[list[str]] = ["easy", "medium", "hard"]
USER_ROLES: Final[list[str]] = ["superadmin", "admin", "read_only", "candidate"]
```

Plus: `MAX_CODE_SIZE_KB`, `DEFAULT_TIME_LIMIT_MS`, `DEFAULT_MEMORY_LIMIT_KB`, `MAX_AUDIO_CHUNK_SIZE_BYTES`, `MAX_AUDIO_DURATION_SECONDS`, `VECTOR_DIMENSION`.

### `environments.py` — `EnvironmentConfig` (frozen dataclass)

Factory functions `dev_config()`, `staging_config()`, `prod_config()` with env-specific defaults (debug, log level, CORS origins, rate limiting, profiling toggles).

### `feature_flags.py` — `FeatureFlags` (frozen dataclass)

Flags: `ENABLE_AI_EVALUATION`, `ENABLE_PROCTORING`, `ENABLE_WEBCAM_PROCTORING`, `ENABLE_CODING_CHALLENGES`, `ENABLE_AUDIO_ANALYSIS`, `ENABLE_WEBSOCKET_INTERVIEWS`, `ENABLE_REAL_TIME_EVALUATION`, `ENABLE_RESUME_PARSING`.

### `security.py` — Security Configuration

- `SecurityConfig`: allowed_hosts, max_request_size_mb, request_timeout_s, enable_audit_logging
- `CORSConfig`: allowed_origins, allowed_methods, allowed_headers, allow_credentials, max_age
- `PasswordPolicy`: min_length=12, require_uppercase/lowercase/digit/special, max_length=128

---

## 3. Module: `app/bootstrap`

**Files**: `__init__.py`, `app.py`, `dependencies.py`, `lifespan.py`, `middleware.py`, `router_registry.py`, `exception_handlers.py`

### `app.py` — Application Factory

```python
def create_app() -> FastAPI:
    app = FastAPI(title=..., lifespan=lifespan)
    register_middleware(app)
    register_routers(app)
    register_exception_handlers(app)
    return app
```

Global `app = create_app()` unless `TESTING` env var is set.

### `lifespan.py` — Startup/Shutdown

- **Startup**: init PostgreSQL engine → init Redis client → init Qdrant client
- **Shutdown**: cleanup Qdrant → cleanup Redis → cleanup PostgreSQL (reverse order)
- All operations wrapped in try/except with structured logging

### `middleware.py` — 7-Layer Middleware Stack

Applied in order (outermost first):
1. `RequestContextMiddleware` — generates/extracts `request_id`
2. `LoggingMiddleware` — logs request start/end with latency
3. `ErrorFormattingMiddleware` — catches unhandled exceptions
4. `CORSMiddleware` — standard CORS headers
5. `GZipMiddleware` — response compression
6. `RateLimitMiddleware` — stub (logs only, does not enforce)
7. `IdentityInjectionMiddleware` — extracts Bearer token → validates → builds `IdentityContext` → attaches to `request.state.identity`

### `router_registry.py` — Route Registration

**Active routers**:
- `auth_router` → `/api/v1/auth`
- `admin_router` → `/api/v1/admin`
- `audio_ingestion_router` → `/api/v1/audio/ingestion`
- `audio_transcription_router` → `/api/v1/audio/transcription`

**Commented out** (not yet implemented): interview, question, evaluation, coding routers.

**Health endpoints**: `GET /health`, `GET /health/database`

### `exception_handlers.py` — Structured Error Responses

Handlers for:
- `BaseError` → maps to `status_code`, includes `error_code`, `message`, `metadata`, `request_id`
- `RequestValidationError` → 422 with field-level details
- `HTTPException` → pass-through with structured JSON
- Generic `Exception` → 500 "Internal Server Error"

### `dependencies.py` — Re-Exported FastAPI Dependencies

- `get_db_session` — SQLAlchemy session (no auto-commit)
- `get_db_session_with_commit` — SQLAlchemy session (auto-commits on success)
- `get_identity` — extracts `IdentityContext` from request (required)
- `get_optional_identity` — extracts `IdentityContext` (optional, returns None)
- `require_admin` — requires admin JWT
- `require_candidate` — requires candidate JWT
- `require_superadmin` — requires superadmin role

---

## 4. Module: `app/shared`

### 4.1 `shared/errors/`

**Files**: `__init__.py`, `exceptions.py` (664 lines), `classification.py`, `serializers.py`, `config.py`

#### Exception Hierarchy (`exceptions.py`)

```
BaseError (dataclass: status_code, error_code, message, metadata, request_id)
├── Client Errors
│   ├── AuthenticationError (401)
│   ├── AuthorizationError (403)
│   ├── TenantIsolationViolation (403)
│   ├── NotFoundError (404)
│   ├── ConflictError (409)
│   ├── ValidationError (422)
│   └── RateLimitExceeded (429)
├── Business/Domain Errors
│   ├── InterviewNotActiveError (422)
│   ├── InterviewWindowClosedError (422)
│   ├── ConsentNotCapturedError (422)
│   ├── ExchangeImmutabilityViolation (409)
│   ├── TemplateImmutabilityViolation (409)
│   ├── DomainInvariantViolation (500)
│   └── ProctoringViolation (200)
├── External/Integration Errors
│   ├── AIProviderError (502)
│   ├── AIProviderTimeoutError (504)
│   ├── SandboxExecutionError (500)
│   └── SandboxTimeoutError (408)
└── System Errors
    ├── InfrastructureError (500)
    ├── DatabaseError (500)
    ├── CacheError (500)
    ├── ConfigurationError (500)
    └── InternalServerError (500)
```

#### Classification (`classification.py`)

- `is_fatal_error()` → Auth, AuthZ, TenantIsolation, DomainInvariantViolation
- `get_log_level()` → maps error types to WARNING/ERROR/CRITICAL
- `should_send_to_client()` → hides internal details for 5xx errors

#### Serializers (`serializers.py`)

- `serialize_rest_error()` → JSON for HTTP responses
- `serialize_websocket_error()` → JSON for WebSocket close frames
- `serialize_error_for_logging()` → JSON for structured logs (includes stack trace)

### 4.2 `shared/auth_context/`

**Files**: `__init__.py`, `models.py`, `builder.py`, `dependencies.py`, `middleware.py`, `scope.py`, `websocket.py`, `registry.py`, `config.py`, `context.py`

#### `models.py` — Identity Models

```python
class UserType(str, Enum): ADMIN, CANDIDATE
class AdminRole(str, Enum): SUPERADMIN, ADMIN, READ_ONLY

@dataclass(frozen=True)
class IdentityContext:
    user_id: int
    user_type: UserType
    organization_id: Optional[int]
    admin_role: Optional[AdminRole]
    token_version: Optional[int]
    issued_at: Optional[datetime]
    expires_at: Optional[datetime]
    
    def is_superadmin(self) -> bool
    def is_admin_type(self) -> bool
    def is_candidate_type(self) -> bool
```

- `__post_init__` enforces: admin MUST have org_id and admin_role; candidate MUST have org_id
- `TaskContext` — carries identity across async task boundaries

#### `builder.py` — `IdentityBuilder.from_jwt_claims(claims) → IdentityContext`

Expected claims: `sub`, `user_type`, `organization_id`, `admin_role`, `token_version`, `iat`, `exp`

#### `scope.py` — Tenant Isolation

- `enforce_organization_scope(identity, target_org_id)` — raises `TenantIsolationViolation` for non-superadmin cross-tenant access
- `enforce_candidate_scope(identity, candidate_user_id)` — self-access only
- `require_organization_admin(identity, org_id)` — must be admin of the specific org

#### `registry.py` — `ConnectionRegistry`

Redis-backed WebSocket connection tracking. Enforces single-connection-per-submission. Keys: `ws:conn:{submission_id}` with TTL.

#### `websocket.py` — `authenticate_websocket(ws) → IdentityContext`

Extracts token from query parameter or first message, validates, builds identity.

### 4.3 `shared/observability/`

**Files**: `__init__.py`, `logging.py` (323 lines), `tracing.py` (202 lines), `metrics.py`, `redaction.py`, `config.py`, `telemetry.py`

#### `logging.py` — Structured Logging

- `StructuredFormatter` — JSON log format with `timestamp`, `level`, `logger`, `message`, `request_id`, `user_id`, `organization_id`, `event_type`, `latency_ms`, `metadata`
- `ContextLogger` — wrapper around `logging.Logger` that auto-injects context fields
- `get_context_logger(name)` — factory function

#### `tracing.py` — Request/Correlation IDs

- `TraceContext` dataclass (request_id, correlation_id, session_id, user_id, organization_id)
- ID generators: `generate_request_id()`, `generate_connection_id()`, etc. (UUID-based)
- `extract_request_id(request)` — from `X-Request-ID` header

#### `metrics.py` — Prometheus Metrics

`MetricsRegistry` class with:
- Interview: `interview_exchanges_total`, `interview_duration_seconds`, `interview_pauses_total`
- Questions: `question_generation_duration_seconds`, `question_retrieval_duration_seconds`, `question_selection_fallback_total`
- Evaluation: `evaluation_duration_seconds`, `evaluation_score_distribution`
- Sandbox: `sandbox_execution_duration_seconds`, `sandbox_timeout_total`, `sandbox_error_total`
- WebSocket: `websocket_connections_active`, `websocket_reconnects_total`, `websocket_disconnect_total`
- AI Provider: `ai_provider_calls_total`, `ai_provider_latency_seconds`, `ai_provider_tokens_total`, `ai_provider_cost_usd_total`

Global singleton: `metrics = MetricsRegistry()`

Helpers: `track_latency(histogram)` context manager, `track_operation(counter, histogram)` decorator (supports async)

#### `redaction.py` — Sensitive Data Redaction

- `SENSITIVE_FIELDS`: access_token, refresh_token, password, api_key, secret, token, authorization, bearer, credentials
- `redact_sensitive_data(data)` — recursive dict/list redaction + hidden test case output protection
- `mask_token(token, visible_chars=4)` → `"...VCJ9"`

#### `config.py` — `ObservabilityConfig(BaseSettings)`

Environment-driven config for log levels, structured logging, file logging, redaction toggles, distributed tracing, metrics port, AI telemetry logging.

#### `telemetry.py` — `AITelemetry` + `track_ai_call()` Context Manager

Legacy/convenience wrapper for AI call tracking (duplicates some functionality of `app.ai.telemetry`). Includes `calculate_openai_cost()` and `calculate_anthropic_cost()` helper functions.

---

## 5. Module: `app/persistence`

### 5.1 `persistence/postgres/`

**Files**: `__init__.py`, `base.py`, `engine.py`, `session.py`, `health.py`, `migrations/`

#### `base.py`

```python
Base = declarative_base()

def import_all_models():
    import app.admin.persistence.models
    import app.ai.prompts.models
    import app.coding.persistence.models
```

**NOTE**: Does NOT import `app.auth.persistence.models` — auth uses its own separate `Base`.

#### `engine.py`

- `create_db_engine(url, ...)` with retry logic (3 attempts, exponential backoff)
- `QueuePool` with configurable pool_size, max_overflow, pool_timeout, pool_recycle
- Pool event listeners for checkout/checkin/invalidate logging
- `init_engine()` → global singleton, `cleanup_engine()` for shutdown

#### `session.py`

- `SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)`
- `get_db_session()` — yields session, no auto-commit, always closes
- `get_db_session_with_commit()` — yields session, commits on success, rollbacks on error
- `db_session_context()` — context manager version
- `execute_with_retry(session, fn, max_retries=3)` — retries on OperationalError

#### `health.py`

- `HealthStatus` enum (HEALTHY, DEGRADED, UNHEALTHY)
- `check_postgres_health()` — runs `SELECT 1`, checks pool utilization
- Pool monitoring: checked-out vs total connections

### 5.2 `persistence/qdrant/`

- Client initialization with Qdrant SDK
- Collection management (create/check/delete collections with vector config)
- Vector CRUD: `store_vectors()`, `search_vectors()`, `delete_vectors()`
- Health checks

### 5.3 `persistence/redis/`

- Client initialization with `redis-py`
- Key-value operations: get, set, delete, get_many, set_with_ttl
- Hash operations: hget, hset, hgetall
- **Distributed locks**: `acquire_lock(key, ttl)`, `try_acquire_lock(key, ttl)`, `release_lock(key, token)` — uses Redis SET NX EX pattern with unique tokens
- Health checks

---

## 6. Module: `app/auth`

**Files**: api/ (1 router), contracts/ (4 files), domain/ (5 files), persistence/ (5 repositories + models)

### 6.1 API Layer (`auth/api/routes.py` — 391 lines)

6 endpoints on `APIRouter()`:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/register/admin` | Admin registration (admin-only) |
| POST | `/register/candidate` | Candidate registration (admin-only) |
| POST | `/login` | Login (returns access + refresh tokens) |
| POST | `/refresh` | Refresh token rotation |
| POST | `/logout` | Revoke refresh token |
| GET | `/me` | Current user profile |

Each endpoint builds its own `AuthService` via `_build_auth_service(db)`.

### 6.2 Contracts (`auth/contracts/`)

#### `schemas.py` — Pydantic Request Models

- `AdminRegistrationRequest`: email, password (with regex complexity validation), first_name, last_name, admin_role, organization_id
- `CandidateRegistrationRequest`: email, password, first_name, last_name, organization_id
- `LoginRequest`: email, password
- `RefreshTokenRequest`: refresh_token
- `LogoutRequest`: refresh_token

#### `responses.py` — Pydantic Response Models

- `RegistrationResponse`, `LoginResponse` (access_token + refresh_token + token_type + expires_in), `TokenRefreshResponse`, `CurrentUserResponse`, `UserProfileResponse`, `ErrorResponse`

#### `enums.py`

```python
class AuthErrorCode(str, Enum):
    INVALID_CREDENTIALS, USER_INACTIVE, TOKEN_EXPIRED, TOKEN_INVALID,
    USER_ALREADY_EXISTS, ORGANIZATION_NOT_FOUND, INSUFFICIENT_PERMISSIONS,
    REFRESH_TOKEN_REVOKED, REFRESH_TOKEN_EXPIRED, REGISTRATION_FAILED
```

#### `claims.py` — TypedDicts for JWT Claims

- `AdminAccessTokenClaims`: sub, user_type, organization_id, admin_role, token_version, iat, exp
- `CandidateAccessTokenClaims`: sub, user_type, organization_id, token_version, iat, exp

### 6.3 Domain Services (`auth/domain/`)

#### `auth_service.py` (1024 lines)

Main orchestrator:
- `register_admin(command, identity)` — validates org, checks email uniqueness, creates user+admin, logs audit
- `register_candidate(command, identity)` — validates org, creates user+candidate, logs audit
- `login(command)` — password verify, generates access+refresh tokens, stores hashed refresh
- `refresh(command)` — validates refresh token (by hash lookup), generates new pair, revokes old
- `logout(command)` — revokes refresh token by hash
- `validate_token(token)` — JWT decode → `TokenValidationResult`

#### `jwt_service.py`

- `generate_access_token(claims, expires_delta)` — RS256 or HS256
- `generate_refresh_token()` — random opaque string
- `hash_refresh_token(token)` — SHA-256
- `verify_access_token(token)` — decode + validate claims

#### `password_hasher.py`

- `hash_password(password)` — bcrypt with configurable cost factor
- `verify_password(plain, hashed)` — bcrypt verify
- `validate_complexity(password)` — length, upper, lower, digit, special char checks

#### `rbac_enforcer.py`

```python
class Permission(str, Enum):
    READ, WRITE, DELETE, MANAGE_USERS, MANAGE_SETTINGS, ...

PERMISSION_MATRIX = {
    AdminRole.SUPERADMIN: {all permissions},
    AdminRole.ADMIN: {READ, WRITE, DELETE, MANAGE_USERS},
    AdminRole.READ_ONLY: {READ},
}
```

### 6.4 Persistence (`auth/persistence/`)

#### `models.py` — ORM Models

**⚠️ CRITICAL**: Uses its **own** `Base = declarative_base()`, separate from `app.persistence.postgres.base.Base`.

Models:
- `User`: id, email, password_hash, first_name, last_name, is_active, user_type, created_at, updated_at
- `Organization`: id, name, slug, is_active, settings (JSONB), created_at, updated_at
- `Admin`: id, user_id (FK→users), organization_id (FK→organizations), admin_role, created_at
- `Candidate`: id, user_id (FK→users), organization_id (FK→organizations), resume_data (JSONB), created_at
- `RefreshToken`: id, user_id (FK→users), token_hash, expires_at, is_revoked, created_at
- `AuthAuditLog`: id, user_id, action, ip_address, user_agent, metadata (JSONB), created_at

#### Repositories

- `UserRepository`: get_by_email, get_by_id, create, update, exists_by_email
- `AdminRepository`: get_by_user_id, create, get_by_organization
- `CandidateRepository`: get_by_user_id, create, get_by_organization
- `RefreshTokenRepository`: create, get_by_hash, revoke_by_hash, revoke_all_for_user, cleanup_expired
- `AuditLogRepository`: INSERT-ONLY log_event

---

## 7. Module: `app/admin`

**Files**: api/ (routes, contracts, dependencies, __init__), domain/ (entities, protocols, services, authorization, __init__), persistence/ (models, mappers, repositories, __init__), validation/ (6 validator files + result.py)

### 7.1 Domain Entities (`admin/domain/entities.py` — 367 lines)

#### Enums

```python
class TemplateScope(str, Enum): PUBLIC, ORGANIZATION, PRIVATE
class InterviewScope(str, Enum): GLOBAL, LOCAL, ONLY_INVITED
class DifficultyLevel(str, Enum): EASY, MEDIUM, HARD
class QuestionType(str, Enum): BEHAVIORAL, TECHNICAL, SITUATIONAL, CODING
class CodingTopicType(str, Enum): DATA_STRUCTURE, ALGORITHM, PATTERN, SYSTEM_DESIGN, LANGUAGE_SPECIFIC, TRAVERSAL
class ContentType(str, Enum): TEMPLATE, RUBRIC, ROLE, TOPIC, QUESTION, CODING_PROBLEM
```

#### Constants

```python
SUPER_ORG_ID = 1
RUBRIC_WEIGHT_TOLERANCE = 0.001
IMMUTABLE_OVERRIDE_FIELDS = frozenset({"id", "organization_id", "scope", "created_at", "updated_at"})
```

#### Entities (all `@dataclass`)

| Entity | Table | Key Fields |
|--------|-------|------------|
| `Template` | interview_templates | name, scope, template_structure (JSONB), rules, version, is_active |
| `TemplateRole` | interview_template_roles | interview_template_id, role_id |
| `TemplateRubric` | interview_template_rubrics | interview_template_id, rubric_id, section_name |
| `Rubric` | rubrics | name, scope, schema (JSONB), is_active |
| `RubricDimension` | rubric_dimensions | rubric_id, dimension_name, max_score, weight (Decimal), criteria, sequence_order |
| `Role` | roles | name, scope, organization_id |
| `Topic` | topics | name, parent_topic_id (self-referential), scope |
| `CodingTopic` | coding_topics | name, topic_type, parent_topic_id, display_order |
| `Question` | questions | question_text, question_type, difficulty, scope, is_active |
| `CodingProblem` | coding_problems | title, body, difficulty, scope, examples, hints, code_snippets |
| `Window` | interview_submission_windows | organization_id, admin_id, name, scope, start_time, end_time, timezone |
| `WindowRoleTemplate` | window_role_templates | window_id, role_id, template_id, selection_weight |
| `OverrideRecord` | *_overrides tables | organization_id, base_content_id, content_type, override_fields (Dict) |

`Template.create_new_version()` — creates a deep copy with incremented version for immutability-safe editing.

### 7.2 Domain Protocols (`admin/domain/protocols.py` — 401 lines)

All use `typing.Protocol` with `@runtime_checkable`:

- `TemplateRepository` — CRUD + exists_with_name + get_latest_version + template-role/rubric mappings
- `RubricRepository` — CRUD + exists_with_name + dimensions CRUD
- `RoleRepository` — CRUD + exists_with_name
- `TopicRepository` — CRUD for both general topics and coding topics + ancestor traversal for cycle detection
- `QuestionRepository` — CRUD with filtering by question_type
- `CodingProblemRepository` — CRUD with filtering by difficulty
- `WindowRepository` — CRUD + find_overlapping_windows + window-role-template mappings
- `SubmissionRepository` — **Read-only** for immutability checks: `template_is_in_use()`, `rubric_is_in_use()`, `role_is_in_use()`, `window_has_submissions()`
- `OverrideRepository` — Generic CRUD for all content type overrides + `mark_overrides_stale()`
- `AuditLogRepository` — **Insert-only** event logging

### 7.3 Domain Services (`admin/domain/services.py` — 1394 lines)

7 service classes, each constructed with injected repository protocols:

#### `TemplateService`

- CRUD with RBAC enforcement
- **Immutability-safe versioning**: if template is in use by submissions, `update()` creates a new version instead of mutating
- Activation/deactivation with cascade to overrides (`mark_overrides_stale`)
- Template-role and template-rubric mapping management
- Override CRUD (create/update/delete/get effective template with merge)

#### `RubricService`

- CRUD with RBAC
- **Dimension weight validation**: sum must equal 1.0 ±0.001 tolerance
- Override management

#### `RoleService`, `TopicService`, `QuestionService`, `CodingProblemService`

- Standard CRUD with RBAC
- Topic service includes **cycle detection** (traverses ancestors)
- Override management for all

#### `WindowService`

- CRUD with time validation (end_time > start_time)
- Overlap detection for same role
- Window-role-template mapping management

### 7.4 Authorization (`admin/domain/authorization.py`)

Three authorization functions:
- `authorize_admin_operation(identity, operation, resource_org_id)` — read_only can only GET; enforces tenant isolation
- `authorize_base_content_mutation(identity)` — only superadmin can modify super-org content
- `authorize_override_operation(identity, base_content_org_id, override_org_id, operation)` — overrides only for super-org base content

### 7.5 Persistence (`admin/persistence/`)

#### Models (`models.py` — 798 lines)

Uses shared `Base` from `app.persistence.postgres.base`. 13+ ORM model classes mapping to PostgreSQL tables:
- `InterviewTemplateModel`, `InterviewTemplateRoleModel`, `InterviewTemplateRubricModel`
- `RubricModel`, `RubricDimensionModel`
- `RoleModel`
- `TopicModel`, `CodingTopicModel`
- `QuestionModel`
- `CodingProblemModel`
- `InterviewSubmissionWindowModel`, `WindowRoleTemplateModel`
- `InterviewSubmissionModel` (read-only reference)
- 6 Override models: `TemplateOverrideModel`, `RubricOverrideModel`, `RoleOverrideModel`, `TopicOverrideModel`, `QuestionOverrideModel`, `CodingProblemOverrideModel`
- `AuditLogModel`
- `OVERRIDE_MODEL_MAP` — maps `ContentType` → override model class

#### Mappers (`mappers.py` — 466 lines)

Bidirectional conversion functions for every entity: `*_model_to_entity()` and `*_entity_to_model()`. Enum string↔value conversion handled during mapping.

#### Repositories (`repositories.py` — 915 lines)

10 repository classes implementing protocol interfaces:
- `SqlTemplateRepository`, `SqlRubricRepository`, `SqlRoleRepository`, `SqlTopicRepository`, `SqlQuestionRepository`, `SqlCodingProblemRepository`, `SqlWindowRepository`
- `SqlSubmissionRepository` (read-only for immutability checks)
- `SqlOverrideRepository` (generic, uses `OVERRIDE_MODEL_MAP`)
- `SqlAuditLogRepository`

Multi-tenancy filter: `_org_filter(model, org_id)` → shows org-owned + super-org (org_id=1) content.

### 7.6 API Layer (`admin/api/`)

#### `routes.py` (1139 lines)

Complete RESTful API for all 7 resource types + overrides. All endpoints require `require_admin` dependency.

Endpoint groups:
- Templates: GET (list, detail), POST, PUT, DELETE (deactivate), PUT /activate, overrides CRUD
- Rubrics: GET (list, detail), POST, PUT, DELETE, GET /dimensions, overrides CRUD
- Roles: GET (list, detail), POST, PUT, DELETE, overrides CRUD
- Topics: GET (list, detail), POST, PUT, DELETE, overrides CRUD
- Questions: GET (list, detail), POST, PUT, DELETE, overrides CRUD
- Coding Problems: GET (list, detail), POST, PUT, DELETE, overrides CRUD
- Windows: GET (list, detail), POST, PUT, DELETE, mappings CRUD

#### `contracts.py` (545 lines)

All Pydantic request/response models for admin API. Reuses domain enums. Pagination/meta wrappers.

#### `dependencies.py`

7 factory functions: `build_template_service()`, `build_rubric_service()`, `build_role_service()`, `build_topic_service()`, `build_question_service()`, `build_coding_problem_service()`, `build_window_service()`.

---

## 8. Module: `app/ai`

### 8.1 `ai/llm/` — Multi-Provider LLM Abstraction

**Files**: `__init__.py`, `contracts.py`, `base_provider.py`, `errors.py`, `provider_factory.py`, `providers/` (groq, gemini, openai, anthropic, embedding), `utils/token_counter.py`

#### `contracts.py` (312 lines)

```python
class LLMProvider(str, Enum): GROQ, GEMINI, OPENAI, ANTHROPIC
class LLMErrorType(str, Enum): TIMEOUT, RATE_LIMIT, AUTHENTICATION, SCHEMA_VALIDATION, ...

@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    system_prompt: Optional[str]
    model_id: str
    temperature: float
    max_tokens: int
    response_schema: Optional[Dict]
    deterministic: bool

@dataclass(frozen=True)
class LLMResponse:
    text: str
    model_id: str
    provider: str
    telemetry: TelemetryData
    parsed_response: Optional[Dict]
    success: bool

@dataclass
class TelemetryData:
    model_id: str, provider: str, prompt_tokens: int, completion_tokens: int,
    total_tokens: int, latency_ms: int, success: bool,
    error_type: Optional[str], retry_count: int,
    deterministic: bool, temperature: Optional[float],
    max_tokens: Optional[int], request_id: Optional[str],
    organization_id: Optional[int], estimated_cost_usd: Optional[float]
```

Also: `EmbeddingRequest/Response`, `TranscriptionRequest/Response`, `ClarificationRequest/Response`.

#### `base_provider.py` — ABCs

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_text(self, request: LLMRequest) -> LLMResponse: ...
    @abstractmethod
    async def generate_structured(self, request: LLMRequest) -> LLMResponse: ...

class BaseEmbeddingProvider(ABC):
    @abstractmethod
    async def generate_embeddings(self, request: EmbeddingRequest) -> EmbeddingResponse: ...

class BaseTranscriptionProvider(ABC):
    @abstractmethod
    async def transcribe(self, request: TranscriptionRequest) -> TranscriptionResponse: ...

@dataclass
class ProviderCapabilities:
    supports_structured_output: bool
    supports_function_calling: bool
    supports_vision: bool
    max_context_length: int
    supports_streaming: bool
```

#### `errors.py` (360 lines)

LLM-specific error hierarchy extending `shared.errors`:

```
LLMProviderError (502)
├── LLMTimeoutError (504)
├── LLMRateLimitError (429)
├── LLMAuthenticationError (401)
├── LLMSchemaValidationError (422)
├── LLMContentFilterError (422)
├── LLMModelNotFoundError (404)
├── LLMContextLengthError (422)
└── LLMConfigurationError (500)
```

Each carries `provider`, `model_id`, `retry_after`, `raw_response` metadata.

#### `provider_factory.py`

```python
class ProviderFactory:
    @staticmethod
    def create_text_provider(provider: LLMProvider, ...) -> BaseLLMProvider
    @staticmethod
    def create_embedding_provider(provider: str, ...) -> BaseEmbeddingProvider
```

Lazy imports for non-default providers to minimize startup time.

### 8.2 `ai/prompts/` — Prompt Template System

**Files**: `__init__.py`, `entities.py`, `errors.py`, `models.py`, `protocols.py`, `parser.py`, `renderer.py`, `repository.py`, `service.py`, `mappers.py`

#### `entities.py`

```python
class PromptType(str, Enum):
    QUESTION_GENERATION, EVALUATION, RESUME_PARSING, JD_PARSING,
    REPORT_GENERATION, CLARIFICATION

@dataclass
class PromptTemplate:
    id, name, prompt_type, scope, organization_id, system_prompt, user_prompt,
    model_id, model_config (Dict), version, is_active

@dataclass
class RenderedPrompt:
    text, system_prompt, model_id, model_config, version, prompt_type,
    variables_used, truncated
```

#### `protocols.py`

```python
SUPER_ORG_ID = 1

class PromptTemplateRepository(Protocol):
    def get_active_by_type(self, prompt_type, organization_id) -> Optional[PromptTemplate]
    def get_active_by_type_strict(self, prompt_type, organization_id) -> Optional[PromptTemplate]
    def get_by_id(self, prompt_id) -> Optional[PromptTemplate]
    def list_by_type(self, prompt_type, organization_id, include_inactive=False) -> List[PromptTemplate]
    def list_active_types(self, organization_id) -> List[str]
```

Resolution: org-scoped → global (scope='public', org_id=1) → None.

#### `parser.py` — Template Variable Extraction

- `TemplateParser(template_text)` — extracts `{{variable}}` placeholders
- Validates syntax: no nesting, no empty names, no unclosed braces
- Supports escaped braces (`\{{`, `\}}`)

#### `renderer.py` — Variable Substitution

- `PromptRenderer.render(template, variables)` → `RenderedPrompt`
- Validates all required variables present
- Sanitizes values (None→"", list/dict→JSON, >50KB→truncated)
- Null byte stripping for injection prevention

#### `service.py` — `PromptService`

```python
class PromptService:
    def get_prompt(self, prompt_type, organization_id) -> PromptTemplate  # with scope fallback
    def render_prompt(self, template, variables) -> RenderedPrompt
    def get_rendered_prompt(self, prompt_type, variables, organization_id) -> RenderedPrompt  # get + render
```

#### `repository.py` — `SqlPromptTemplateRepository`

Read-only SQL implementation. Scope resolution: org → global fallback. Uses `prompt_model_to_entity` mapper.

#### `models.py` — `PromptTemplateModel`

ORM model for `prompt_templates` table. Uses shared `Base` from `app.persistence.postgres.base`.

### 8.3 `ai/telemetry/` — AI Operation Telemetry

**Files**: `__init__.py`, `contracts.py`, `tracker.py`, `cost.py`, `errors.py`, `aggregation.py`

#### `contracts.py`

```python
class OperationType(str, Enum):
    QUESTION_GENERATION, EVALUATION, RESUME_PARSING, JD_PARSING,
    REPORT_GENERATION, EMBEDDING, TRANSCRIPTION, TEXT_GENERATION, CLARIFICATION

class AIErrorType(str, Enum):
    TIMEOUT, RATE_LIMIT, AUTHENTICATION, SCHEMA_VALIDATION,
    CONTENT_FILTER, CONTEXT_LENGTH, MODEL_NOT_FOUND, PROVIDER_ERROR

@dataclass(frozen=True) CostEstimate: model_id, prompt_tokens, completion_tokens, costs, total_cost_usd
@dataclass AggregatedMetrics: time_period, total_requests, total_tokens, total_cost, latency percentiles
@dataclass OrganizationQuota: org_id, monthly limits, current usage, is_*_exceeded() methods
```

#### `tracker.py` — Non-Blocking Telemetry

```python
class TelemetrySpan:
    set_input(prompt_tokens, model_id, provider, ...)
    set_output(completion_tokens, success, ...)
    set_error(error_type)
    finalize() -> TelemetryData

class TelemetryTracker:
    @contextmanager
    def track(self, operation_type) -> TelemetrySpan:
        # Always yields span
        # Exceptions propagate normally
        # Telemetry NEVER propagates failures
```

**Design invariant**: Telemetry failure MUST NOT propagate to calling code.

#### `cost.py` — Static Model Pricing

```python
MODEL_PRICING = {
    "llama-3.3-70b-versatile": (0.00059, 0.00079),  # Groq
    "gemini-2.0-flash-exp": (0.0, 0.0),              # Free preview
    "gpt-4o": (0.0025, 0.01),                        # OpenAI
    "claude-3-5-sonnet-20241022": (0.003, 0.015),     # Anthropic
    "all-mpnet-base-v2": (0.0, 0.0),                  # Self-hosted
    ...
}

class CostEstimator:
    def estimate_cost(self, model_id, prompt_tokens, completion_tokens) -> Optional[CostEstimate]
```

#### `errors.py` — Error Classification

```python
def classify_error(error: Exception) -> str:
    # Maps LLM-specific and shared errors to AIErrorType strings
    # Lazy imports to avoid circular deps
    # Falls back to class name pattern matching
    # Never raises
```

#### `aggregation.py` — `MetricsAggregator`

Pure computation: aggregates `List[TelemetryData]` → `AggregatedMetrics` with p50/p95/p99 latency percentiles, error breakdowns, cost summation.

---

## 9. Module: `app/coding`

**Files**: `__init__.py`, `enums.py`, api/, execution/, persistence/, sandbox/, evaluation/

### 9.1 Enums (`coding/enums.py`)

```python
class ExecutionStatus(str, Enum):
    PENDING, RUNNING, PASSED, FAILED, ERROR, TIMEOUT, MEMORY_EXCEEDED

class TestCaseStatus(str, Enum):
    PASSED, FAILED, TIMEOUT, MEMORY_EXCEEDED, RUNTIME_ERROR
```

### 9.2 Execution Service (`coding/execution/service.py` — 523 lines)

Full lifecycle orchestrator:

1. **Lock** submission via Redis distributed lock
2. **State transition validation** (state_machine.py)
3. **Execute** each test case via sandbox
4. **Score** using weighted formula
5. **Persist** results

```python
class ExecutionService:
    def __init__(self, submission_repo, execution_result_repo, sandbox_executor, redis_client): ...
    def execute_submission(self, command: ExecuteSubmissionCommand) -> ExecutionResult: ...
```

#### `execution/state_machine.py`

```python
TERMINAL_STATES = {PASSED, FAILED, ERROR, TIMEOUT, MEMORY_EXCEEDED}
VALID_TRANSITIONS = {
    PENDING: {RUNNING},
    RUNNING: {PASSED, FAILED, ERROR, TIMEOUT, MEMORY_EXCEEDED},
}
```

#### `execution/contracts.py`

```python
@dataclass(frozen=True) SubmissionData: id, code, language, time_limit_ms, memory_limit_kb
@dataclass(frozen=True) TestCase: id, input_data, expected_output, weight, is_hidden
@dataclass(frozen=True) ExecuteSubmissionCommand: submission, test_cases
@dataclass TestCaseExecutionResult: test_case_id, status, actual_output, runtime_ms, memory_kb, match_details
@dataclass ExecutionResult: submission_id, status, score, test_case_results, total_runtime_ms
```

### 9.3 Sandbox (`coding/sandbox/`)

#### `executor.py` — `SandboxExecutor` (Main Entry Point)

Orchestration: validate → resolve Docker image → build script → configure container → execute → parse output → sanitize → return result.

Security invariants: network isolation, read-only FS, resource limits, non-root, stateless.

#### `docker_runner.py` — Low-Level Docker Interface

```python
@dataclass(frozen=True)
class DockerRunConfig:
    image, memory_limit_mb, time_limit_seconds,
    pids_limit=64, cpus=1.0, network="none", read_only=True,
    no_new_privileges=True, cap_drop_all=True, user="1000:1000",
    auto_remove=True, tmpfs_tmp_size_mb=100

def build_docker_command(config, env_vars) -> list[str]  # Pure function
def build_execution_script(language, time_limit, memory_limit) -> str
def run_container(config, env_vars, script, timeout) -> DockerRunResult
```

Security flags: `--rm`, `--network=none`, `--pids-limit`, `--memory` (swap disabled), `--cpus`, `--read-only`, `--tmpfs /tmp`, `--security-opt=no-new-privileges`, `--cap-drop=ALL`, `--user=1000:1000`.

Language-specific scripts handle compilation (C++/Java with 10s timeout) + execution with `/usr/bin/time -v` for metrics.

#### `output_parser.py` — `/usr/bin/time` Output Parsing

- Separates program stdout from `/usr/bin/time -v` diagnostic output
- Parses wall clock time → milliseconds, peak RSS → kilobytes, exit code
- Classifies: exit 124 → timeout, exit 137 → OOM

#### `sanitizer.py` — Output Sanitization

- Removes internal paths (`/tmp/`, `/sandbox/`), container IDs, host info
- Truncates output > 1MB with notice
- `sanitize_and_truncate()` — combined pipeline

### 9.4 Evaluation (`coding/evaluation/`)

#### `comparator.py` — Deterministic Output Comparison

```python
def normalize_output(output) -> str:
    # Split lines → strip trailing whitespace → remove trailing empty lines → join

def compare_outputs(expected, actual) -> bool:
    # Exact match after normalization
```

#### `scorer.py` — Weighted Scoring

```python
def calculate_score(weights, passed) -> float:
    # score = (Σ weight_i × passed_i) / (Σ weight_i) × 100

def generate_feedback(status: TestCaseStatus) -> str
def generate_match_details(status, is_hidden, expected, actual) -> Optional[str]
    # Hidden test cases NEVER receive match details
```

### 9.5 Persistence (`coding/persistence/`)

#### Entities (dataclasses)

```python
@dataclass CodeSubmission: id, interview_submission_id, coding_problem_id, language, source_code, status, score, ...
@dataclass CodeExecutionResult: id, code_submission_id, test_case_id, status, actual_output, runtime_ms, memory_kb, ...
```

#### Protocols

```python
class CodeSubmissionRepository(Protocol):
    def get_by_id(self, id) -> Optional[CodeSubmission]
    def get_by_id_for_update(self, id) -> Optional[CodeSubmission]  # SELECT FOR UPDATE
    def update_status(self, id, status, score)
    def create(self, submission) -> CodeSubmission

class CodeExecutionResultRepository(Protocol):
    def create(self, result) -> CodeExecutionResult
    def get_results_for_submission(self, submission_id) -> List[CodeExecutionResult]
```

#### ORM Models

`CodeSubmissionModel` and `CodeExecutionResultModel` — uses shared `Base` from `app.persistence.postgres.base`.

#### Repositories

`SqlCodeSubmissionRepository` and `SqlCodeExecutionResultRepository` — implements protocols with SQLAlchemy. `get_by_id_for_update` uses `with_for_update()`.

---

## 10. Module: `app/audio`

### 10.1 `audio/ingestion/` — Audio Pipeline

**Files**: `__init__.py`, `service.py`, `contracts.py`, `normalizer.py`, `buffer_manager.py`, `session_manager.py`, `silence_detector.py`, `exceptions.py`, `api/`

#### `service.py` — `AudioIngestionService` (Main Facade)

Pipeline: validate session → normalize audio (16kHz mono) → buffer → feed silence detector → forward to transcription

```python
class AudioIngestionService:
    def start_session(self, exchange_id, sample_rate) -> AudioSession
    def pause_session(self, exchange_id)
    def resume_session(self, exchange_id)
    def stop_session(self, exchange_id)
    def ingest_chunk(self, request: AudioStreamRequest) -> AudioChunk
    def handle_session_control(self, control: AudioSessionControl)
    def cleanup_timed_out_sessions() -> List[int]
```

Invariants:
- One active session per exchange
- Session must be active (not paused, not closed)
- All audio forwarded to transcription is 16 kHz mono
- Does NOT write to DB, advance interview state, or trigger evaluations

#### `contracts.py` — Audio Data Structures

```python
class SessionAction(str, Enum): START, PAUSE, RESUME, STOP
class SilenceReason(str, Enum): THRESHOLD_REACHED, SESSION_ENDED

@dataclass(frozen=True) AudioStreamRequest: exchange_id, audio_chunk (bytes), sample_rate, channels
@dataclass(frozen=True) AudioSessionControl: exchange_id, action, reason
@dataclass(frozen=True) AudioChunk: exchange_id, audio_data, sample_rate, channels, timestamp_ms, duration_ms
@dataclass(frozen=True) SilenceDetectedEvent: exchange_id, silence_duration_ms, should_evaluate, reason
```

### 10.2 `audio/transcription/` — Speech-to-Text

**Files**: `__init__.py`, `service.py`, `contracts.py`, `protocols.py`, `confidence.py`, `exceptions.py`, `provider_selector.py`, `providers/`, `api/`

#### `service.py` — `TranscriptionService`

```python
class TranscriptionService:
    async def transcribe(self, request) -> TranscriptionResult
    async def transcribe_streaming(self, request) -> AsyncIterator[TranscriptionResult]
    async def transcribe_with_fallback(self, request) -> TranscriptionResult
```

Features:
- Provider fallback chain (try each provider until one succeeds)
- Exponential backoff retry (configurable max_retries, base delay)
- Per-call timeout with `asyncio.wait_for`
- Telemetry logging per attempt

Invariants:
- Audio NEVER written to disk (GDPR)
- API keys NEVER logged
- Confidence scores normalized to [0.0, 1.0]

#### `contracts.py`

```python
@dataclass(frozen=True) TranscriptionRequest: audio_data (bytes), sample_rate, language, context, streaming
@dataclass(frozen=True) TranscriptionConfig: provider, api_key, model, language, detect_language, word_timestamps
@dataclass(frozen=True) TranscriptSegment: text, start_ms, end_ms, confidence
@dataclass(frozen=True) TranscriptionResult: transcript, confidence_score, language_detected, segments, partial
```

### 10.3 `audio/analysis/` — **STUB** (only REQUIREMENTS.md)

### 10.4 `audio/persistence/` — **STUB** (only REQUIREMENTS.md)

---

## 11. Module: `app/proctoring`

**STUB MODULE** — only REQUIREMENTS.md files in subdirectories:
- `ingestion/REQUIREMENTS.md`
- `persistence/REQUIREMENTS.md`
- `risk_model/REQUIREMENTS.md`
- `rules/REQUIREMENTS.md`

No implementation code.

---

## 12. Stub Modules

### `app/question/`

Subdirectories: `generation/`, `persistence/`, `prompting/`, `retrieval/`, `selection/`
Each contains only `REQUIREMENTS.md` — no implementation.

### `app/interview/`

Subdirectories: `api/`, `exchanges/`, `orchestration/`, `persistence/`, `realtime/`, `session/`
Each contains only `REQUIREMENTS.md` — no implementation.

### `app/evaluation/`

Subdirectories: `aggregation/`, `api/`, `persistence/`, `scoring/`, `snapshots/`
Each contains only `REQUIREMENTS.md` — no implementation.

---

## 13. Critical Findings & Observations

### Architecture Issues

1. **Dual `Base` declarations**: `app/auth/persistence/models.py` declares its own `Base = declarative_base()`, separate from `app/persistence/postgres/base.py`. This means `Base.metadata.create_all()` will only create tables from one Base, not both. The `import_all_models()` function in `base.py` imports admin, ai.prompts, and coding models but NOT auth models.

2. **Missing router registrations**: `router_registry.py` has interview, question, evaluation, and coding routers commented out. These modules are stubs with only REQUIREMENTS.md files.

3. **Rate limiting is a stub**: `RateLimitMiddleware` in middleware.py only logs, does not actually enforce limits.

### Pattern Consistency

4. **Consistent DI pattern**: All modules use constructor injection with Protocol-typed dependencies. Factory functions wire repositories to services per-request.

5. **Consistent mapper pattern**: All modules use bidirectional `*_model_to_entity()` / `*_entity_to_model()` functions to convert between ORM models and domain dataclasses.

6. **Consistent error handling**: All errors extend `BaseError` with structured metadata. Exception handlers produce consistent JSON responses with `request_id` correlation.

### Security

7. **Sandbox security is thorough**: Docker containers run with `--network=none`, `--read-only`, `--cap-drop=ALL`, `--security-opt=no-new-privileges`, `--user=1000:1000`, memory/PID limits, and auto-removal.

8. **GDPR compliance**: Audio is never written to disk (in-memory only). Sensitive data redaction is applied to logs.

9. **Tenant isolation**: Enforced at multiple layers — middleware identity injection, scope enforcement functions, repository multi-tenancy filters.

### Telemetry Duplication

10. **Two telemetry systems**: `app/shared/observability/telemetry.py` (AITelemetry + track_ai_call) and `app/ai/telemetry/` (TelemetryTracker + TelemetrySpan) overlap in functionality. The ai/telemetry module is more comprehensive with cost estimation and aggregation.

### Implementation Status

| Module | Status |
|--------|--------|
| config | ✅ Complete |
| bootstrap | ✅ Complete |
| shared/errors | ✅ Complete |
| shared/auth_context | ✅ Complete |
| shared/observability | ✅ Complete |
| persistence (postgres/redis/qdrant) | ✅ Complete |
| auth | ✅ Complete |
| admin | ✅ Complete |
| ai/llm | ✅ Complete (providers implemented) |
| ai/prompts | ✅ Complete |
| ai/telemetry | ✅ Complete |
| coding | ✅ Complete |
| audio/ingestion | ✅ Complete |
| audio/transcription | ✅ Complete |
| audio/analysis | ❌ Stub |
| audio/persistence | ❌ Stub |
| proctoring | ❌ Stub |
| question | ❌ Stub |
| interview | ❌ Stub |
| evaluation | ❌ Stub |
