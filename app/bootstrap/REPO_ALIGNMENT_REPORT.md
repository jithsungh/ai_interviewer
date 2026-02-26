# BOOTSTRAP MODULE - REPO ALIGNMENT REPORT

## 1. EXISTING MODULE INVENTORY

### 1.1 /app/config (Configuration Layer)
**Purpose:** Centralized configuration management  
**Status:** ✅ FULLY IMPLEMENTED  
**Public Interfaces:**
- `settings.py`: Pydantic-based settings with nested structure
  - `Settings.load()`: Master settings loader
  - `settings`: Global singleton (auto-loaded, None in testing)
  - Sub-settings: AppSettings, DatabaseSettings, RedisSettings, QdrantSettings, LLMSettings, SecuritySettings, AudioSettings, RateLimitSettings, FeatureFlagsSettings
- `constants.py`: Application constants
- `environments.py`: Environment-specific configs
- `security.py`: Security configuration
- `feature_flags.py`: Feature toggle management

**Contracts Exported:**
- Settings hierarchy with validation
- Environment-aware configuration loading
- Automatic .env file parsing (disabled in TESTING mode)

---

### 1.2 /app/persistence (Data Access Layer)
**Purpose:** Database, Redis, Qdrant connection management  
**Status:** ✅ POSTGRES FULLY IMPLEMENTED, REDIS/QDRANT PARTIAL

#### postgres/
**Public Interfaces:**
- `engine.py`:
  - `init_engine(config: DatabaseSettings)`: Initialize SQLAlchemy engine
  - `get_engine()`: Get initialized engine
  - `cleanup_engine()`: Graceful shutdown
  - `create_tables()`, `drop_tables()`: Schema management
  - `get_pool_status()`: Pool monitoring
  
- `session.py`:
  - `init_session_factory()`: Initialize sessionmaker
  - `get_db_session()`: **FastAPI dependency** for DB sessions
  - `get_db_session_with_commit()`: Auto-commit variant
  - `db_session_context()`: Context manager for manual usage
  - `execute_with_retry()`: Retry wrapper for transient failures
  
- `base.py`:
  - `Base`: SQLAlchemy declarative base
  - `get_table_names()`: List registered tables
  
- `health.py`:
  - `check_postgres_health()`: Health check with retry
  - `check_postgres_connectivity()`: Basic connectivity test
  - `get_health_check_endpoint_response()`: FastAPI-ready response
  - `HealthStatus`: Enum (healthy, degraded, unhealthy)

**Initialization Pattern:**
```python
from app.persistence.postgres import init_engine, init_session_factory, cleanup_engine

# Startup
init_engine(settings.database)
init_session_factory()

# Shutdown
cleanup_engine()
```

**Dependencies Used:** SQLAlchemy, app.config.settings

#### redis/
**Status:** ⚠️ PARTIALLY IMPLEMENTED (client exists, needs health check)
**Public Interfaces:**
- `redis_client.connect()`: Async initialization
- `redis_client.disconnect()`: Cleanup

#### qdrant/
**Status:** ⚠️ PARTIALLY IMPLEMENTED (client exists, needs health check)
**Public Interfaces:**
- `qdrant_client.connect()`: Initialization  
- `qdrant_client.disconnect()`: Cleanup

---

### 1.3 /app/shared (Cross-Cutting Concerns)
**Purpose:** Reusable utilities, logging, errors, auth context  
**Status:** ✅ FULLY IMPLEMENTED

#### shared/errors/
**Public Interfaces:**
- `exceptions.py`:
  - `BaseError`: Foundation class (error_code, message, request_id,metadata, http_status_code)
  - `ApplicationError`: Backward-compatible alias
  - Client Errors (4xx): `AuthenticationError`, `AuthorizationError`, `ValidationError`, `NotFoundError`, `ConflictError`, `RateLimitError`
  - Server Errors (5xx): `InfrastructureError`, `InternalServerError`
  - Domain Errors: `DomainInvariantViolation`
  
- `classification.py`: Error type classification  
- `serializers.py`: Error serialization for REST/WebSocket/WebRTC

**Usage Example:**
```python
raise AuthenticationError(
    message="Invalid credentials",
    request_id=request_id
)
```

#### shared/observability/
**Public Interfaces:**
- `logging.py`:
  - `StructuredFormatter`: JSON formatter for logs
  - `ContextLogger`: Logger with auto context injection
  - `setup_logging(config: LoggingConfig)`: Initialize logging
  - `get_context_logger(name: str)`: Get logger instance
  
- `metrics.py`: Prometheus metrics (if implemented)
- `tracing.py`: Distributed tracing (if implemented)
- `telemetry.py`: Observability aggregation

**Usage Example:**
```python
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)
logger.info(
    "Request processed",
    event_type="request.completed",
    latency_ms=45,
    metadata={"user_id": 123}
)
```

#### shared/auth_context/
**Public Interfaces:**
- `models.py`:
  - `IdentityContext`: Immutable identity from validated JWT
  - `UserType`: Enum (admin, candidate)
  - `AdminRole`: Enum (superadmin, admin, read_only)
  - `TaskContext`: Serializable context for async tasks
  
- `dependencies.py`: **FastAPI dependencies**
  - `get_identity(request: Request)`: Require authenticated user
  - `get_optional_identity(request: Request)`: Optional auth
  - `require_admin()`: Admin-only
  - `require_candidate()`: Candidate-only 
  - `require_superadmin()`: Superadmin-only
  
- `middleware.py`:
  - `IdentityInjectionMiddleware`: Inject identity into request.state
  
- `scope.py`: Tenant isolation and scope enforcement

**Usage Example:**
```python
from fastapi import Depends
from app.shared.auth_context import get_identity, IdentityContext

@app.get("/api/profile")
async def get_profile(identity: IdentityContext = Depends(get_identity)):
    return {"user_id": identity.user_id}
```

---

### 1.4 /app/ai (AI/LLM Layer)
**Purpose:** LLM provider abstraction  
**Status:** ✅ LLM MODULE IMPLEMENTED

#### ai/llm/
**Public Interfaces:**
- `provider_factory.py`:
  - `ProviderFactory.create_text_provider()`: Get LLM provider
  - `ProviderFactory.create_embedding_provider()`: Get embedding provider
  
- `contracts.py`: Request/response DTOs for LLM operations
- `providers/`: Groq, OpenAI, Anthropic implementations
- `base_provider.py`: Abstract provider interface

**Dependencies:** httpx, app.config.settings.llm

---

### 1.5 /app/auth, /app/admin, /app/interview, etc. (Domain Modules)
**Status:** ⚠️ REQUIREMENTS DEFINED, IMPLEMENTATION INCOMPLETE  
**Public Interfaces:** Not yet exposed (routers not implemented)

---

## 2. DEPENDENCY GRAPH

### Bootstrap Module Dependencies (Inbound)

```
bootstrap/
├── depends on: config/settings (configuration)
├── depends on: persistence/postgres (DB initialization)
├── depends on: persistence/redis (caching/sessions)
├── depends on: persistence/qdrant (vector search)
├── depends on: shared/errors (exception handlers)
├── depends on: shared/observability (logging setup)
└── depends on: shared/auth_context (middleware)
```

### Bootstrap Module Dependents (Outbound)

```
main.py
└── imports: bootstrap.create_app()
    └── returns: FastAPI application instance
```

### Cross-Module Shared Dependencies

**All domain modules will use:**
- `get_db_session()` from `persistence/postgres`
- `get_identity()`, `require_admin()`, etc. from `shared/auth_context`
- Exception classes from `shared/errors`
- `get_context_logger()` from `shared/observability`

---

## 3. SHARED PATTERNS IDENTIFIED

### 3.1 Configuration Pattern
✅ **PATTERN EXISTS**: Pydantic Settings with nested structure
- Global `settings` singleton (None in testing)
- Environment-aware (.env file support)
- Validation at load time
- Settings categories: app, database, redis, qdrant, llm, security, audio, rate_limit, feature_flags

### 3.2 Database Session Management
✅ **PATTERN EXISTS**: FastAPI dependency injection
```python
from sqlalchemy.orm import Session
from app.persistence.postgres import get_db_session

@router.get("/resource")
def get_resource(db: Session = Depends(get_db_session)):
    return db.query(Model).all()
```

### 3.3 Error Handling
✅ **PATTERN EXISTS**: Structured exceptions with BaseError
- All errors extend `BaseError`
- Include: error_code, message, request_id, metadata, http_status_code
- HTTP status codes standardized

### 3.4 Logging
✅ **PATTERN EXISTS**: Structured JSON logging with context
- `ContextLogger` injects request_id, user_id, organization_id
- Event-based logging (event_type, latency_ms, metadata)
- Redaction for sensitive data

### 3.5 Authentication Context
✅ **PATTERN EXISTS**: FastAPI dependencies with IdentityContext
- Middleware injects identity into `request.state.identity`
- Dependencies extract and validate identity
- Role-based guards: `require_admin()`, `require_candidate()`, `require_superadmin()`

---

## 4. INITIALIZATION SEQUENCE (REQUIRED)

Bootstrap must initialize components in this order:

1. **Logging** (first, so all subsequent steps can log)
2. **Database Engine & Session Factory**
3. **Redis Connection**
4. **Qdrant Connection**
5. **Middleware Registration** (order: Context → Logging → CORS → Rate Limit → Auth)
6. **Router Registration** (when routers exist)
7. **Exception Handlers**

---

## 5. NO DUPLICATION VERIFICATION

### ✅ Database Session: REUSE EXISTING
- **Existing:** `app.persistence.postgres.get_db_session()`
- **Action:** Import and use, do NOT redefine

### ✅ Auth Dependencies: REUSE EXISTING
- **Existing:** `app.shared.auth_context.dependencies`
- **Action:** Import and use, do NOT redefine

### ✅ Error Classes: REUSE EXISTING
- **Existing:** `app.shared.errors.exceptions`
- **Action:** Import for exception handlers, do NOT redefine

### ✅ Logging Setup: REUSE EXISTING
- **Existing:** `app.shared.observability.logging.setup_logging()`
- **Action:** Call during startup, do NOT reimplement

### ✅ Settings: REUSE EXISTING
- **Existing:** `app.config.settings`
- **Action:** Import global singleton, do NOT reload

---

## 6. GAPS & CLARIFICATIONS

### ⚠️ Gap 1: No API Routers Implemented Yet
**Decision:** Bootstrap will prepare router registration system but leave router array empty until domain APIs are implemented.

### ⚠️ Gap 2: Middleware Order Needs Validation
**Decision:** Follow requirements order: RequestContext → Logging → CORS → RateLimit → Identity → (routers)

### ⚠️ Gap 3: Redis/Qdrant Health Checks Incomplete
**Decision:** Add basic connectivity checks in lifespan, log warnings if unhealthy but don't block startup.

### ⚠️ Gap 4: Auth Middleware vs Identity Middleware
**Clarification Needed:** Do we have JWT validation middleware? Or only identity injection?
**Assumption:** Identity injection assumes upstream JWT validation (not in scope for bootstrap).

---

## 7. IMPLEMENTATION STRATEGY

### Phase 1: Lifespan Management (IMMEDIATE)
✅ Initialize logging first  
✅ Initialize database (engine + session factory)  
✅ Initialize Redis (with health check)  
✅ Initialize Qdrant (with health check)  
✅ Graceful shutdown for all connections  

### Phase 2: Middleware Stack (IMMEDIATE)
✅ Request context middleware (request_id, timestamps)  
✅ Logging middleware (log all requests)  
✅ CORS middleware  
✅ Rate limiting middleware (stub, requires Redis)  
✅ Identity injection middleware (from shared/auth_context)  

### Phase 3: Exception Handlers (IMMEDIATE)
✅ Global exception handler for BaseError  
✅ Validation error handler (Pydantic)  
✅ HTTP exception handler (FastAPI defaults)  
✅ Catch-all handler (500 errors)  

### Phase 4: Router Registry (INCREMENTAL)
✅ Create registration system  
⏳ Leave router list empty (populated as domain APIs are implemented)  

### Phase 5: Dependencies Module (OPTIONAL)
✅ Re-export commonly used dependencies for convenience:
  - `get_db_session` (from persistence)
  - `get_identity`, `require_admin`, etc. (from auth_context)

---

## 8. SCHEMA IMPACT

**No schema changes required.** Bootstrap is pure infrastructure assembly.

---

## 9. TESTING STRATEGY

### Unit Tests:
- Middleware order validation
- Exception handler coverage
- Lifespan event sequencing
- Settings validation

### Integration Tests:
- Full app startup/shutdown cycle
- Health check endpoints
- Middleware stack integration  
- Database connectivity through app

---

## CONCLUSION

✅ **No duplication detected**  
✅ **All shared patterns identified and will be reused**  
✅ **Initialization sequence validated**  
✅ **No schema changes needed**  
✅ **Incremental design allows future router registration**  

**READY TO IMPLEMENT** 🚀
