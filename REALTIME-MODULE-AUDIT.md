# Comprehensive Module Audit — For Realtime Module Implementation

## Table of Contents
1. [shared/ Module](#1-shared-module)
2. [auth/ Module](#2-auth-module)
3. [persistence/redis/](#3-persistenceredis)
4. [persistence/postgres/](#4-persistencepostgres)
5. [bootstrap/](#5-bootstrap)
6. [config/](#6-config)
7. [Cross-Module Patterns Summary](#7-cross-module-patterns-summary)

---

## 1. shared/ Module

### File Tree
```
app/shared/
├── __init__.py
├── auth_context/
│   ├── __init__.py          (119 lines - Public API, lazy Redis imports)
│   ├── builder.py           (IdentityBuilder: JWT claims → IdentityContext)
│   ├── config.py            (AuthContextConfig dataclass)
│   ├── context.py           (DEPRECATED AuthContext, UserRole enum)
│   ├── dependencies.py      (237 lines - FastAPI DI: get_identity, require_admin, etc.)
│   ├── middleware.py         (206 lines - IdentityInjectionMiddleware)
│   ├── models.py            (230 lines - IdentityContext, UserType, AdminRole, TaskContext)
│   ├── registry.py          (274 lines - ConnectionRegistry, Redis-backed WS tracking)
│   ├── scope.py             (enforce_organization_scope, enforce_candidate_scope)
│   └── websocket.py         (authenticate_websocket, generate_connection_id)
├── errors/
│   ├── __init__.py          (Public API re-exports)
│   ├── classification.py    (is_fatal_error, get_log_level, should_send_to_client)
│   ├── config.py            (ErrorConfig pydantic-settings)
│   ├── exceptions.py        (664 lines - Full exception hierarchy)
│   └── serializers.py       (serialize_rest_error, serialize_websocket_error)
└── observability/
    ├── __init__.py           (Public API re-exports)
    ├── config.py             (ObservabilityConfig pydantic-settings)
    ├── logging.py            (323 lines - StructuredFormatter, ContextLogger)
    ├── metrics.py            (253 lines - MetricsRegistry, Prometheus metrics)
    ├── redaction.py          (redact_sensitive_data, mask_token)
    ├── telemetry.py          (265 lines - AITelemetry, track_ai_call)
    └── tracing.py            (202 lines - TraceContext, RequestIDMiddleware, ID generators)
```

---

### 1.1 auth_context/models.py — Core Identity Types

#### `UserType(str, Enum)`
- `ADMIN = "admin"` / `CANDIDATE = "candidate"`
- Exclusive: user is one OR the other, never both.

#### `AdminRole(str, Enum)`
- `SUPERADMIN = "superadmin"` / `ADMIN = "admin"` / `READ_ONLY = "read_only"`
- Only applicable when `user_type == ADMIN`.

#### `IdentityContext` (frozen dataclass)
The **primary identity token** for all request/connection handling.

| Field | Type | Notes |
|---|---|---|
| `user_id` | `int` | From JWT `sub` claim |
| `user_type` | `UserType` | admin or candidate |
| `organization_id` | `Optional[int]` | MUST be set for admin, MUST be None for candidate |
| `admin_role` | `Optional[AdminRole]` | MUST be set for admin, MUST be None for candidate |
| `token_version` | `int` | For forced logout / token revocation |
| `issued_at` | `int` | Unix timestamp |
| `expires_at` | `int` | Unix timestamp |

**Key methods:**
- `is_admin()`, `is_candidate()`, `is_superadmin()`
- `is_expired()` — checks `time.time() > expires_at`
- `belongs_to_organization(org_id)` — admin-only, exact match
- `can_access_organization(org_id)` — superadmin bypasses, regular admin exact match
- `to_dict()` — safe for logging

**Invariants enforced in `__post_init__`:**
- Admin MUST have `organization_id` and `admin_role`
- Candidate MUST NOT have `organization_id` or `admin_role`
- `issued_at < expires_at`

#### `TaskContext` (dataclass, NOT frozen)
For serializing identity across async task boundaries (Celery/task queue).

| Field | Type |
|---|---|
| `request_id` | `str` |
| `user_id` | `int` |
| `user_type` | `str` (serialized enum) |
| `organization_id` | `Optional[int]` |
| `submission_id` | `Optional[int]` |

- `TaskContext.from_identity(identity, request_id, submission_id)` — factory
- `to_dict()` — for serialization

---

### 1.2 auth_context/builder.py — IdentityBuilder

**`IdentityBuilder.from_jwt_claims(claims: dict) → IdentityContext`**
- Transforms validated JWT payload into `IdentityContext`
- Does NOT do JWT crypto — auth module does that
- Expects claims: `sub`, `user_type`, `organization_id` (admin), `admin_role` (admin), `token_version`, `iat`, `exp`

**`IdentityBuilder.validate_claims_structure(claims)`**
- Validates presence and types of required fields
- Validates admin/candidate-specific constraints

---

### 1.3 auth_context/dependencies.py — FastAPI DI Functions

| Dependency | Purpose | Returns | Raises |
|---|---|---|---|
| `get_identity(request)` | Extract from `request.state.identity` | `IdentityContext` | `AuthenticationError` if missing |
| `get_optional_identity(request)` | Same but returns `None` for anonymous | `Optional[IdentityContext]` | never |
| `require_admin(identity)` | Chain from `get_identity`, check admin | `IdentityContext` | `AuthorizationError` |
| `require_candidate(identity)` | Chain from `get_identity`, check candidate | `IdentityContext` | `AuthorizationError` |
| `require_superadmin(identity)` | Chain from `require_admin`, check superadmin | `IdentityContext` | `AuthorizationError` |
| `get_token_validator()` | Returns async `token → claims` function | `Callable` | — |

**`get_token_validator()`** pattern:
- Lazy-imports `JWTService` from `app.auth.domain.jwt_service`
- Reads JWT keys from `app.config.settings.security`
- Normalizes claim keys (`type → user_type`, `role → admin_role`)
- In test mode (settings=None), returns a mock that raises `NotImplementedError`

**Usage pattern for endpoints:**
```python
@router.get("/api/resource")
async def get_resource(identity: IdentityContext = Depends(get_identity)):
    ...
```

---

### 1.4 auth_context/middleware.py — IdentityInjectionMiddleware

`BaseHTTPMiddleware` subclass. Injected via `app.add_middleware(...)`.

**Constructor args:**
- `token_validator: Callable` — async func that validates JWT → claims dict
- `require_authentication: bool = False` — if True, 401 on missing/invalid

**Flow:**
1. Extract `Authorization: Bearer <token>` header
2. Call `token_validator(token)` → claims dict
3. `IdentityBuilder.from_jwt_claims(claims)` → `IdentityContext`
4. Check `identity.is_expired()`
5. Set `request.state.identity = identity`
6. If any step fails and `require_authentication=True` → raise `AuthenticationError`
7. If `require_authentication=False` → request proceeds without identity

---

### 1.5 auth_context/websocket.py — WebSocket Auth

**`authenticate_websocket(websocket, token, token_validator) → IdentityContext`**
- Validates token via `token_validator`
- Builds `IdentityContext` via `IdentityBuilder`
- Checks expiry
- Raises `AuthenticationError` on failure
- Does NOT register connection (that's the handler's job)

**`generate_connection_id() → str`**
- Format: `"conn_{uuid4()}"`

**Usage pattern for WebSocket endpoints:**
```python
@app.websocket("/ws/interview/{submission_id}")
async def ws_handler(websocket: WebSocket, submission_id: int, token: str = Query(...)):
    try:
        identity = await authenticate_websocket(websocket, token, validate_access_token)
    except AuthenticationError:
        await websocket.close(code=1008, reason="Authentication failed")
        return
    await websocket.accept()
    connection_id = generate_connection_id()
    await connection_registry.register(connection_id, submission_id, websocket, identity)
```

---

### 1.6 auth_context/registry.py — ConnectionRegistry

Redis-backed WebSocket connection tracking. **Cluster-safe.**

**Redis key pattern:** `active_websocket:{submission_id}` → JSON metadata

| Method | Purpose |
|---|---|
| `register(connection_id, submission_id, websocket, identity, allow_replacement)` | Store connection metadata with TTL |
| `unregister(submission_id)` | Remove connection from Redis |
| `get_connection(submission_id)` | Get metadata dict or None |
| `is_active(submission_id)` | Boolean check |
| `refresh_ttl(submission_id)` | Extend TTL (heartbeat) |

**Stored metadata:**
```json
{
  "connection_id": "conn_abc123",
  "submission_id": 456,
  "user_id": 42,
  "user_type": "candidate",
  "organization_id": null,
  "connected_at": 1700000000
}
```

Default TTL: 60 seconds (refreshed by heartbeat).

**Global instance:** `connection_registry = ConnectionRegistry()`

---

### 1.7 auth_context/scope.py — Scope Enforcement

| Function | Enforces | Raises |
|---|---|---|
| `enforce_organization_scope(identity, resource_org_id)` | Admin can only access own org (superadmin bypasses) | `AuthorizationError`, `TenantIsolationViolation` |
| `enforce_candidate_scope(identity, resource_candidate_id)` | Candidate can only access own resources (`user_id == candidate_id`) | `AuthorizationError` |
| `require_organization_admin(identity, org_id, minimum_role)` | Admin with minimum role for org | `AuthorizationError`, `TenantIsolationViolation` |

**Role hierarchy:** `superadmin(3) > admin(2) > read_only(1)`

---

### 1.8 auth_context/config.py — AuthContextConfig

```python
@dataclass
class AuthContextConfig:
    require_authentication: bool = False
    allow_duplicate_connections: bool = True
    connection_ttl_seconds: int = 60
    connection_heartbeat_interval: int = 30
    enforce_token_expiry: bool = True
    token_expiry_grace_period_seconds: int = 300
    log_identity_injection: bool = True
    log_connection_registry_operations: bool = True
    strict_tenant_isolation: bool = True
    superadmin_bypass_tenant_isolation: bool = True
```

---

### 1.9 errors/exceptions.py — Full Error Hierarchy

```
BaseError (dataclass, Exception)
├── ApplicationError         (backward-compatible alias)
│
├── CLIENT ERRORS (4xx)
│   ├── AuthenticationError     (401 - AUTHENTICATION_FAILED)
│   ├── AuthorizationError      (403 - AUTHORIZATION_FAILED)
│   ├── TenantIsolationViolation (403 - TENANT_VIOLATION)
│   ├── NotFoundError           (404 - NOT_FOUND)
│   ├── ConflictError           (409 - CONFLICT)
│   ├── ValidationError         (422 - VALIDATION_ERROR)
│   └── RateLimitExceeded       (429 - RATE_LIMIT_EXCEEDED)
│
├── BUSINESS LOGIC ERRORS (4xx)
│   ├── InterviewNotActiveError  (400 - INTERVIEW_NOT_ACTIVE)
│   ├── InterviewWindowClosedError (400 - INTERVIEW_WINDOW_CLOSED)
│   └── ConsentNotCapturedError  (400 - CONSENT_REQUIRED)
│
├── DOMAIN ERRORS
│   ├── ExchangeImmutabilityViolation (400 - EXCHANGE_IMMUTABLE)
│   ├── TemplateImmutabilityViolation (400 - TEMPLATE_IMMUTABLE)
│   ├── DomainInvariantViolation (500 - DOMAIN_INVARIANT_VIOLATION, CRITICAL)
│   └── ProctoringViolation      (200 - PROCTORING_VIOLATION, advisory only)
│
├── EXTERNAL SERVICE ERRORS (5xx)
│   ├── AIProviderError          (502 - AI_PROVIDER_ERROR)
│   ├── AIProviderTimeoutError   (504 - AI_TIMEOUT)
│   ├── SandboxExecutionError    (500 - SANDBOX_EXECUTION_ERROR)
│   └── SandboxTimeoutError      (408 - EXECUTION_TIMEOUT)
│
└── SYSTEM ERRORS (5xx)
    ├── InfrastructureError      (500 - INFRASTRUCTURE_ERROR)
    ├── DatabaseError            (500 - DATABASE_ERROR)
    ├── CacheError               (500 - CACHE_ERROR)
    ├── ConfigurationError       (500 - CONFIG_ERROR)
    └── InternalServerError      (500 - INTERNAL_SERVER_ERROR)
```

**BaseError fields:** `error_code`, `message`, `request_id`, `metadata`, `http_status_code`
**Backward compat:** `status_code` property → `http_status_code`, `details` property → `metadata`

---

### 1.10 errors/classification.py — Fatal vs Recoverable

**`is_fatal_error(error) → bool`**
Fatal (requires WebSocket close): `AuthenticationError`, `AuthorizationError`, `TenantIsolationViolation`, `DomainInvariantViolation`
Recoverable (connection stays open): `ValidationError`, `NotFoundError`, `ConflictError`, `ProctoringViolation`

**`get_log_level(error) → str`**
- `DomainInvariantViolation` → `CRITICAL`
- 5xx → `ERROR`
- 4xx → `WARN`
- Others → `INFO`

**`should_send_to_client(error, is_production) → bool`**
- 4xx → always True
- 5xx in production → False (hide internals)
- 5xx in dev → True

---

### 1.11 errors/serializers.py — Error Serialization

**`serialize_rest_error(error, request_id) → dict`**
```json
{"error": {"code": "...", "message": "...", "request_id": "...", "metadata": {...}}}
```

**`serialize_websocket_error(error) → dict`**
```json
{"event": "error", "payload": {"code": "...", "message": "...", "metadata": {...}}}
```

**`serialize_error_for_logging(error, include_traceback) → dict`**

---

### 1.12 errors/config.py — ErrorConfig

Pydantic-settings based. Key fields:
- `send_error_event_on_recoverable: bool = True`
- `close_connection_on_fatal: bool = True`
- `websocket_close_code_fatal: int = 1008`
- `environment: Literal["dev", "staging", "prod"]`

---

### 1.13 observability/ — Logging, Tracing, Metrics, Telemetry

#### StructuredFormatter
JSON log formatter with fields: `timestamp`, `level`, `logger`, `message`, `request_id`, `connection_id`, `user_id`, `submission_id`, `organization_id`, `event_type`, `latency_ms`, `metadata`, `exception`.

#### ContextLogger
Wraps `logging.Logger` with automatic context injection. Constructor fields: `request_id`, `connection_id`, `user_id`, `submission_id`, `organization_id`. Methods: `debug()`, `info()`, `warning()`, `error()`, `critical()` — all accept `event_type`, `latency_ms`, `metadata`.

**Factory:** `get_context_logger(request_id=None, connection_id=None, user_id=None, ...)` — returns `ContextLogger`.

#### TraceContext (dataclass)
Fields: `request_id`, `correlation_id`, `parent_span_id`. Serializable to/from dict.

#### ID Generators
- `generate_request_id()` → `"req_{12hex}"`
- `generate_connection_id()` → `"conn_{12hex}"`
- `generate_session_id()` → `"session_{12hex}"`
- `generate_correlation_id()` → `"corr_{12hex}"`
- `extract_request_id(request)` — from `X-Request-ID` header or generate

#### RequestIDMiddleware
BaseHTTPMiddleware: extracts/generates request ID, injects into `request.state.request_id`, adds `X-Request-ID` response header.

#### MetricsRegistry
Prometheus metrics. Key WebSocket metrics:
- `websocket_connections_active` (Gauge)
- `websocket_reconnects_total` (Counter)
- `websocket_disconnect_total` (Counter, labels: `reason`)

Also: interview, question, evaluation, sandbox, AI provider metrics.

**Global instance:** `metrics = MetricsRegistry()`

#### AITelemetry / track_ai_call
Context manager for tracking AI provider calls (latency, tokens, cost).

#### redaction.py
- `redact_sensitive_data(data, redact_candidate_answers=False)` — recursive dict redaction
- `mask_token(token, visible_chars=4)` → `"...VCJ9"`
- `SENSITIVE_FIELDS` — `{"access_token", "refresh_token", "password", "api_key", ...}`

---

## 2. auth/ Module

### File Tree
```
app/auth/
├── REQUIREMENTS.md
├── api/
│   ├── __init__.py          (exports: router)
│   └── routes.py            (391 lines - FastAPI auth endpoints)
├── contracts/
│   ├── __init__.py          (exports all schemas, enums, claims)
│   ├── claims.py            (AdminAccessTokenClaims, CandidateAccessTokenClaims TypedDicts)
│   ├── enums.py             (AuthErrorCode enum)
│   ├── responses.py         (272 lines - Response Pydantic models)
│   └── schemas.py           (205 lines - Request Pydantic models)
├── domain/
│   ├── __init__.py          (exports Commands, Results, Services)
│   ├── auth_service.py      (1024 lines - Core auth business logic)
│   ├── contracts.py         (Commands and Result DTOs)
│   ├── jwt_service.py       (JWTService - RS256/HS256 token gen/validation)
│   ├── password_hasher.py   (PasswordHasher - bcrypt)
│   └── rbac_enforcer.py     (RBACEnforcer - Permission matrix)
└── persistence/
    ├── __init__.py           (exports Models + Repositories)
    ├── models.py             (User, Organization, Admin, Candidate, RefreshToken, AuthAuditLog)
    ├── user_repository.py    (UserRepository)
    ├── admin_repository.py   (AdminRepository)
    ├── candidate_repository.py (CandidateRepository)
    ├── refresh_token_repository.py (RefreshTokenRepository)
    └── audit_log_repository.py (AuthAuditLogRepository)
```

---

### 2.1 JWT Handling — JWTService

**Constructor:** `JWTService(private_key, public_key, algorithm="RS256", access_token_ttl_minutes=15, refresh_token_ttl_days=30)`

**`generate_access_token(user_id, user_type, token_version, admin_id?, org_id?, admin_role?, candidate_id?) → str`**
JWT claims:
```json
{
  "sub": 42,
  "type": "admin",       // NOTE: "type" not "user_type" in JWT
  "token_version": 3,
  "iat": 1700000000,
  "exp": 1700003600,
  "jti": "uuid",
  "admin_id": 1,          // admin only
  "organization_id": 1,   // admin only
  "role": "superadmin",   // admin only (NOTE: "role" not "admin_role")
  "candidate_id": 123     // candidate only
}
```

**CRITICAL: Claim key mapping** — JWT uses `type`/`role`, but IdentityBuilder expects `user_type`/`admin_role`. The `get_token_validator()` function in `dependencies.py` normalizes: `type → user_type`, `role → admin_role`.

**`generate_refresh_token() → str`** — 64 random bytes hex-encoded.

**`hash_refresh_token(token) → str`** — SHA-256 hex.

**`verify_access_token(token) → dict`** — Decodes + verifies signature. Raises `AuthenticationError` on expired/invalid.

---

### 2.2 JWT Claim TypedDicts

**`AdminAccessTokenClaims`:** `sub`, `type`, `admin_id`, `organization_id`, `role`, `iat`, `exp`, `jti`, `token_version`

**`CandidateAccessTokenClaims`:** `sub`, `type`, `candidate_id`, `iat`, `exp`, `jti`, `token_version`

---

### 2.3 Auth API Routes

| Endpoint | Method | Auth | Handler |
|---|---|---|---|
| `/register/admin` | POST | None | `register_admin()` |
| `/register/candidate` | POST | None | `register_candidate()` |
| `/login` | POST | None | `login()` |
| `/refresh` | POST | None | `refresh_token()` |
| `/logout` | POST | None | `logout()` |
| `/me` | GET | `Depends(get_identity)` | `get_me()` |

Registered at prefix: `/api/v1/auth`

**Route DI pattern:** Each route calls `_build_auth_service(session)` to construct `AuthService` with injected dependencies (reads JWT keys from `app.config.settings.security`).

---

### 2.4 AuthService — Core Business Logic

Constructor: `AuthService(session: Session, password_hasher: PasswordHasher, jwt_service: JWTService)`

| Method | Input | Output |
|---|---|---|
| `register_admin(RegisterAdminCommand)` | email, password, org_id, role | `UserProfile` |
| `register_candidate(RegisterCandidateCommand)` | email, password, name, phone | `UserProfile` |
| `login(LoginCommand)` | email, password, ip, ua | `AuthenticationResult` (tokens + profile) |
| `refresh_token(RefreshTokenCommand)` | refresh_token | `AuthenticationResult` |
| `logout(LogoutCommand)` | refresh_token | void |
| `get_current_user(user_id)` | user_id | `UserProfile` |

**Login flow:**
1. Find user by email (case-insensitive)
2. Verify password (bcrypt)
3. Check user status (active/inactive/banned)
4. If admin: check admin status + organization status
5. Generate access token (JWT)
6. Generate refresh token (random)
7. Store refresh token hash in DB
8. Update `last_login_at`
9. Log audit event
10. Return `AuthenticationResult`

---

### 2.5 Domain DTOs (contracts.py)

**Commands (frozen dataclasses):**
- `RegisterAdminCommand(email, password, organization_id, admin_role, full_name?, request_ip?, request_user_agent?)`
- `RegisterCandidateCommand(email, password, full_name?, phone?, request_ip?, request_user_agent?)`
- `LoginCommand(email, password, request_ip?, request_user_agent?, device_info?)`
- `RefreshTokenCommand(refresh_token, request_ip?)`
- `LogoutCommand(refresh_token, request_ip?)`
- `ValidateTokenCommand(access_token)`

**Results (frozen dataclasses):**
- `UserProfile(user_id, email, user_type, user_status, admin_id?, org_id?, admin_role?, admin_status?, candidate_id?, full_name?, candidate_status?, candidate_plan?, last_login_at?, created_at?)`
- `AuthenticationResult(access_token, refresh_token, token_type="Bearer", expires_in=900, user_profile?)`
- `TokenValidationResult(valid, claims?, error?, auth_context?)`

---

### 2.6 RBACEnforcer

**Permission enum:** `MANAGE_ADMINS`, `MANAGE_ORGANIZATION`, `CREATE_TEMPLATES`, `EDIT_TEMPLATES`, `DELETE_TEMPLATES`, `CREATE_INTERVIEWS`, `VIEW_SUBMISSIONS`, `DOWNLOAD_REPORTS`, `MANAGE_CANDIDATES`, `VIEW_ANALYTICS`

**Permission matrix:**
| Role | Permissions |
|---|---|
| superadmin | ALL |
| admin | CREATE_TEMPLATES, EDIT_TEMPLATES, CREATE_INTERVIEWS, VIEW_SUBMISSIONS, DOWNLOAD_REPORTS, MANAGE_CANDIDATES, VIEW_ANALYTICS |
| read_only | VIEW_SUBMISSIONS, DOWNLOAD_REPORTS, VIEW_ANALYTICS |

**Methods:** `has_permission(identity, permission) → bool`, `require_permission(identity, permission)` (raises `AuthorizationError`)

---

### 2.7 ORM Models (auth/persistence/models.py)

All use `declarative_base()` from `app.auth.persistence.models` (NOT from `app.persistence.postgres.base` — separate Base!).

| Model | Table | Key Columns |
|---|---|---|
| `User` | `users` | id, name, email, password_hash, user_type, status, last_login_at, token_version |
| `Organization` | `organizations` | id, name, organization_type, plan, domain, status, policy_config, metadata |
| `Admin` | `admins` | id, user_id (FK→users), organization_id (FK→organizations), role, status |
| `Candidate` | `candidates` | id, user_id (FK→users), plan, status, profile_metadata (JSONB) |
| `RefreshToken` | `refresh_tokens` | id, user_id (FK→users), token_hash, device_info, ip_address, issued_at, expires_at, revoked_at, revoked_reason |
| `AuthAuditLog` | `auth_audit_log` | id, user_id (FK→users), event_type, ip_address, user_agent, event_metadata (JSONB) — INSERT-ONLY |

---

### 2.8 Repositories

All repos take `session: Session` in constructor. **Transaction commit/rollback is caller's responsibility.**

| Repository | Methods |
|---|---|
| `UserRepository` | `create()`, `get_by_id()`, `find_by_email()`, `email_exists()`, `update_last_login()`, `update_password()`, `update_status()`, `increment_token_version()` |
| `AdminRepository` | `create()`, `get_by_id()`, `find_by_user_id()`, `list_by_organization()`, `update_role()`, `update_status()` |
| `CandidateRepository` | `create()`, `get_by_id()`, `find_by_user_id()`, `update_profile()`, `update_status()` |
| `RefreshTokenRepository` | `create()`, `find_by_hash()`, `list_active_for_user()`, `revoke()`, `revoke_all_for_user()` |
| `AuthAuditLogRepository` | `log_event()`, `get_recent_events()`, `get_failed_login_attempts()`, `get_suspicious_events()`, `get_events_by_type()` — INSERT-ONLY |

---

## 3. persistence/redis/

### File Tree
```
app/persistence/redis/
├── __init__.py          (Full public API with init_redis convenience function)
├── client.py            (RedisClientError, create_redis_client, init_redis_client, get_redis_client, cleanup_redis)
├── health.py            (HealthStatus, check_redis_health, check_redis_connectivity, get_pool_status, log_redis_stats)
├── locks.py             (LockAcquisitionError, LockReleaseError, acquire_lock, try_acquire_lock, release_lock, is_locked)
└── operations.py        (588 lines - set_value, get_value, delete_key, exists, hash ops, batch ops, counters, TTL mgmt)
```

---

### 3.1 client.py — Connection Management

**`create_redis_client(config: RedisSettings) → Redis`**
- Connection pooling via `ConnectionPool.from_url()`
- Retry with exponential backoff (max 3 attempts)
- Validates with PING
- `decode_responses=True` (returns strings not bytes)

**`init_redis_client(config) → Redis`** — initializes global `_client` singleton.

**`get_redis_client() → Redis`** — returns global client or raises `RuntimeError`.

**`cleanup_redis()`** — disconnects pool, registered via `atexit`.

**`RedisClientError(ApplicationError)`** — status 503, code `REDIS_UNAVAILABLE`.

---

### 3.2 locks.py — Distributed Locking

**`acquire_lock(lock_key, timeout_seconds=10, retry_interval=0.1) → contextmanager`**
- Uses `SET NX EX` (atomic set-if-not-exists with TTL)
- Retry loop until timeout
- Release via Lua script (only holder can release)
- Raises `LockAcquisitionError` (409) on timeout

**Lock key helpers:**
- `create_interview_lock_key(submission_id, sequence_number)`
- `create_session_lock_key(session_id)`
- `create_rate_limit_lock_key(user_id, endpoint)`

**Usage:**
```python
with acquire_lock(f"interview:lock:{submission_id}:{seq}", timeout_seconds=10):
    # Critical section
```

---

### 3.3 operations.py — Core Redis Operations

| Function | Redis Command | Notes |
|---|---|---|
| `set_value(key, value, ttl?)` | SET/SETEX | Auto JSON-encodes dicts/lists |
| `get_value(key, default?, deserialize_json?)` | GET | Graceful fallback on timeout |
| `delete_key(key)` | DEL | Returns 0 or 1 |
| `exists(key)` | EXISTS | Boolean |
| `set_ttl(key, seconds)` | EXPIRE | |
| `get_ttl(key)` | TTL | |
| `hash_set(key, field, value)` | HSET | |
| `hash_get(key, field)` | HGET | |
| `hash_get_all(key)` | HGETALL | |
| `increment_counter(key, amount)` | INCRBY | |
| `decrement_counter(key, amount)` | DECRBY | |
| `batch_set(mapping, ttl?)` | Pipeline SET | |
| `batch_get(keys)` | Pipeline GET | |
| `batch_delete(keys)` | Pipeline DEL | |
| `execute_pipeline(operations)` | Pipeline | |

All functions accept optional `client: Redis` parameter (defaults to global).

---

## 4. persistence/postgres/

### File Tree
```
app/persistence/postgres/
├── __init__.py          (init_postgres, cleanup_postgres, public API)
├── base.py              (Base = declarative_base(), import_all_models, get_table_names)
├── engine.py            (285 lines - Engine creation, pool monitoring, lifecycle)
├── session.py           (Session factory, FastAPI dependencies, retry logic)
├── health.py            (HealthStatus, check_postgres_health, etc.)
└── migrations/          (SQL migration files)
```

---

### 4.1 base.py — Declarative Base

`Base = declarative_base()` — shared base for ALL ORM models.

**NOTE:** auth module defines its own `Base = declarative_base()` in `auth/persistence/models.py`. This means auth models use a **separate** metadata registry. The `import_all_models()` in `base.py` imports models from other modules (admin, ai, coding, question, interview) to register them.

---

### 4.2 engine.py — Engine Creation

**`create_db_engine(config: DatabaseSettings) → Engine`**
- `QueuePool` with `pool_size`, `max_overflow`, `pool_timeout`, `pool_recycle`
- `pool_pre_ping=True` (detect stale connections)
- `statement_timeout` via `connect_args`
- Retry with exponential backoff (max 3 attempts)
- Pool event listeners for monitoring (connect, checkout, checkin)

**`init_engine(config) → Engine`** — global singleton, calls `import_all_models()`, registers `atexit` + signal handlers.

**`get_engine() → Engine`** — raises `RuntimeError` if not initialized.

**`cleanup_engine()`** — disposes engine.

**`get_pool_status() → dict`** — returns `pool_size`, `checked_out`, `overflow`, `total_connections`.

---

### 4.3 session.py — Session Management

**`init_session_factory()`** — creates `sessionmaker` bound to engine.

**FastAPI Dependencies:**
```python
def get_db_session() → Iterator[Session]:
    # Yields session, closes in finally (NO auto-commit)

def get_db_session_with_commit() → Iterator[Session]:
    # Yields session, commits on success, rollback on exception, closes in finally
```

**`db_session_context() → contextmanager`** — for non-FastAPI usage (auto-commit/rollback).

**`execute_with_retry(session, operation, max_retries=3)`** — retries on `OperationalError`, no retry on `IntegrityError`.

---

## 5. bootstrap/

### File Tree
```
app/bootstrap/
├── __init__.py
├── app.py                (create_app → FastAPI, global `app` instance)
├── dependencies.py       (Re-exports: get_db_session, get_identity, require_admin, etc.)
├── exception_handlers.py (Global exception handlers)
├── lifespan.py           (Startup/shutdown lifecycle)
├── middleware.py          (224 lines - 7 middleware in order)
└── router_registry.py    (register_routers - all API routes)
```

---

### 5.1 app.py — Application Factory

**`create_app() → FastAPI`**
1. Create FastAPI instance with lifespan, title, version, debug settings
2. `register_middleware(app)` — 7 middleware layers
3. `register_routers(app)` — all API routes
4. `register_exception_handlers(app)` — 4 exception handlers

Global: `app = create_app() if settings is not None else None`

---

### 5.2 dependencies.py — Convenience Re-exports

```python
from app.persistence.postgres import get_db_session, get_db_session_with_commit
from app.shared.auth_context.dependencies import (
    get_identity, get_optional_identity,
    require_admin, require_candidate, require_superadmin,
)
```

**This is the canonical import point for endpoint DI:**
```python
from app.bootstrap.dependencies import get_db_session, get_identity, require_admin
```

---

### 5.3 lifespan.py — Startup/Shutdown

**Startup order:**
1. Logging (already configured at import)
2. PostgreSQL: `init_engine(settings.database)` + `init_session_factory()`
3. Redis: `init_redis_client(settings.redis)` (failure is non-fatal, logged as warning)
4. Qdrant: `init_qdrant_client(settings.qdrant)` (failure is non-fatal)

**Shutdown order:**
1. Qdrant cleanup
2. Redis cleanup
3. PostgreSQL cleanup

---

### 5.4 middleware.py — Middleware Stack

**Registration order (CRITICAL — determines execution order):**

| # | Middleware | Purpose |
|---|---|---|
| 1 | `RequestContextMiddleware` | Injects `request_id`, `request_start_time` into `request.state` |
| 2 | `LoggingMiddleware` | Logs method, path, status, latency, user_id |
| 3 | `ErrorFormattingMiddleware` | Reformats 404s to structured JSON |
| 4 | `CORSMiddleware` | Origins: `http://localhost:8080`, credentials, all methods |
| 5 | `GZipMiddleware` | Compress responses > 1000 bytes |
| 6 | `RateLimitMiddleware` | Stub (TODO) |
| 7 | `IdentityInjectionMiddleware` | JWT validation → `request.state.identity` |

**IdentityInjectionMiddleware setup:**
```python
token_validator = get_token_validator()  # from shared.auth_context.dependencies
app.add_middleware(
    IdentityInjectionMiddleware,
    token_validator=token_validator,
    require_authentication=False
)
```

---

### 5.5 router_registry.py — Route Registration

Currently registered:
- `/api/v1/auth` — Auth router
- `/api/v1/admin` — Admin router
- `/api/v1/interviews/sessions` — Interview session router
- `/api/v1/questions/selection` — Question selection router
- `/api/v1/audio/ingestion` — Audio ingestion router
- `/api/v1/audio/transcription` — Audio transcription router
- `/health` — Basic health check
- `/health/database` — Database health with pool status

Commented out (not yet implemented): Interview (parent), Question (parent), Evaluation, Coding, Proctoring.

**To add a new router (e.g., realtime):**
```python
from app.interview.realtime.api.routes import router as realtime_router
app.include_router(
    realtime_router,
    prefix=f"{api_prefix}/interviews/realtime",
    tags=["Realtime"]
)
```

---

### 5.6 exception_handlers.py — Global Error Handling

| Handler | Exception Type | Status |
|---|---|---|
| `base_error_handler` | `BaseError` (all app errors) | error's `http_status_code` |
| `validation_error_handler` | `RequestValidationError` | 422 |
| `http_exception_handler` | `HTTPException` | error's status |
| `unhandled_exception_handler` | `Exception` | 500 |

All return structured JSON: `{"error": {"code": "...", "message": "...", "request_id": "...", "metadata": {...}}}`

---

## 6. config/

### File Tree
```
app/config/
├── __init__.py            (Global config objects: settings, feature_flags, env_config, security_config)
├── constants.py           (Immutable domain constants)
├── environments.py        (EnvironmentConfig)
├── feature_flags.py       (FeatureFlags frozen dataclass)
├── security.py            (SecurityConfig, CORSConfig, PasswordPolicy)
└── settings.py            (427 lines - Master Settings with all sub-settings)
```

---

### 6.1 settings.py — Pydantic Settings

**`Settings.load() → Settings`** — loads from `.env` file (skipped in testing via `TESTING` env var).

| Sub-settings | Class | Key Fields |
|---|---|---|
| `settings.app` | `AppSettings` | `app_env`, `debug`, `app_name`, `api_version`, `base_url` |
| `settings.database` | `DatabaseSettings` | `database_url`, `db_pool_size(20)`, `db_max_overflow(10)`, `db_pool_timeout(30)`, `db_query_timeout(30)` |
| `settings.redis` | `RedisSettings` | `redis_url`, `redis_db(0)`, `redis_max_connections(50)`, `redis_session_ttl(3600)`, `redis_lock_timeout(10)` |
| `settings.qdrant` | `QdrantSettings` | `qdrant_url`, `qdrant_collection_name`, `qdrant_embedding_dim(768)` |
| `settings.llm` | `LLMSettings` | `default_llm_provider`, API keys, model routing, temperature |
| `settings.sandbox` | `SandboxSettings` | Docker images, resource limits, security |
| `settings.security` | `SecuritySettings` | `jwt_algorithm(HS256)`, `jwt_secret_key`, `jwt_public/private_key_path`, `access_token_expire_minutes(30)`, `refresh_token_expire_days(30)`, `password_hash_rounds(12)` |
| `settings.audio` | `AudioSettings` | Silence detection, transcription provider, Whisper model |
| `settings.rate_limit` | `RateLimitSettings` | Login rate limit, API rate limit, concurrent interview limit |
| `settings.feature_flags` | `FeatureFlagsSettings` | AI evaluation, proctoring, audio, code execution, practice mode |

**Global:** `settings = None if os.getenv("TESTING") else Settings.load()`

---

### 6.2 constants.py

Key constants for realtime module:
- `MAX_EXCHANGES_PER_INTERVIEW = 50`
- `MAX_QUESTION_LENGTH = 10_000`
- `MAX_ANSWER_LENGTH = 50_000`
- `API_V1_PREFIX = "/api/v1"`
- `SUPPORTED_LANGUAGES = ["cpp", "java", "python3"]`

---

### 6.3 environments.py — EnvironmentConfig

Frozen dataclass with: `env`, `is_dev`, `is_staging`, `is_prod`, `enable_openapi`, `enable_debug_logging`, `strict_cors`, `require_ssl`, `allow_insecure_transport`.

Methods: `get_log_level()`, `get_pool_size()`, `should_use_ssl()`, `get_error_detail_level()`.

---

## 7. Cross-Module Patterns Summary

### Authentication Flow (HTTP)
```
Request → RequestContextMiddleware (request_id)
        → LoggingMiddleware
        → CORSMiddleware
        → IdentityInjectionMiddleware
            → extract Bearer token
            → get_token_validator() → JWTService.verify_access_token()
            → normalize claims (type→user_type, role→admin_role)
            → IdentityBuilder.from_jwt_claims() → IdentityContext
            → request.state.identity = identity
        → Route handler
            → Depends(get_identity) → IdentityContext
            → enforce_organization_scope() / enforce_candidate_scope()
```

### Authentication Flow (WebSocket)
```
WebSocket connect request
    → Extract token from query param
    → authenticate_websocket(ws, token, token_validator) → IdentityContext
    → websocket.accept()
    → generate_connection_id()
    → ConnectionRegistry.register(conn_id, submission_id, ws, identity)
    → Message loop
    → ConnectionRegistry.unregister(submission_id) on disconnect
```

### Dependency Injection Pattern
```python
# Canonical imports
from app.bootstrap.dependencies import get_db_session, get_identity, require_admin

@router.post("/api/v1/resource")
async def create_resource(
    body: CreateRequest,
    identity: IdentityContext = Depends(require_admin),
    db: Session = Depends(get_db_session_with_commit),
):
    enforce_organization_scope(identity, body.organization_id)
    # business logic...
```

### Error Handling Pattern
```python
# Raise structured errors
raise NotFoundError(resource_type="Submission", resource_id=123)
raise AuthorizationError(message="Admin access required")
raise ConflictError(message="Connection already exists")

# WebSocket error handling
from app.shared.errors import serialize_websocket_error, is_fatal_error

if is_fatal_error(error):
    await ws.send_json(serialize_websocket_error(error))
    await ws.close(code=1008)
else:
    await ws.send_json(serialize_websocket_error(error))
    # connection stays open
```

### Logging Pattern
```python
from app.shared.observability import get_context_logger

logger = get_context_logger(
    connection_id=connection_id,
    user_id=identity.user_id,
    submission_id=submission_id,
)
logger.info("Message received", event_type="ws.message", metadata={...})
```

### Redis Pattern
```python
from app.persistence.redis import acquire_lock, set_value, get_value

# Distributed lock
with acquire_lock(f"interview:lock:{submission_id}:{seq}", timeout_seconds=10):
    # atomic operation

# Key-value
set_value(f"session:{sid}", data_dict, ttl_seconds=3600)
state = get_value(f"session:{sid}", deserialize_json=True)
```

### Database Session Pattern
```python
# Auto-commit (for mutations)
db: Session = Depends(get_db_session_with_commit)

# Manual control (for reads)
db: Session = Depends(get_db_session)
```
