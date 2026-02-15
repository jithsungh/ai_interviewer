# Bootstrap Module - Application Assembly Layer

## 1. Purpose

**Why this module exists:**

The Bootstrap module is the **application assembly layer**. It:

- Creates and configures the FastAPI application
- Registers middleware in correct order
- Registers all routers centrally
- Manages application lifespan (startup/shutdown)
- Wires dependency injection
- Defines global exception handlers
- Initializes infrastructure connections (DB, Redis, Qdrant, AI providers)

**Critical responsibility:** This is the **dependency graph root** and **global control boundary**. It wires the system together but owns NO business rules.

**Architectural philosophy:** If this layer is sloppy, you get:

- Hidden dependencies
- Circular imports
- Middleware chaos
- Inconsistent error handling
- Broken lifespan cleanup
- Undebuggable WebSocket behavior

This module must be **boring, deterministic, and thin**. If it grows large, your architecture is drifting.

---

## 2. Owned Tables / Entities

**None.** Bootstrap owns no database tables or domain entities. It is pure infrastructure assembly.

---

## 3. Module Structure

```
bootstrap/
├── app_factory.py          # FastAPI app creation
├── middleware.py           # Middleware registration
├── lifespan.py            # Startup/shutdown lifecycle
├── router_registry.py     # Router registration
├── exception_handlers.py  # Global exception handling
└── dependencies.py        # DI wiring (get_db, get_current_user, etc.)
```

---

## 4. Input / Output Contracts

### Application Factory

#### Input: Configuration

```python
from dataclasses import dataclass
from typing import List

@dataclass
class AppConfig:
    # Application
    app_name: str
    app_version: str
    debug_mode: bool
    enable_openapi: bool  # Disable in production

    # Database
    database_url: str
    db_pool_size: int
    db_max_overflow: int

    # Redis
    redis_url: str

    # Qdrant
    qdrant_url: str
    qdrant_api_key: str

    # JWT
    jwt_public_key_path: str
    jwt_private_key_path: str

    # CORS
    cors_origins: List[str]
    cors_allow_credentials: bool

    # Security
    enforce_https: bool
    secure_headers: bool

    # Rate Limiting
    enable_rate_limiting: bool
    rate_limit_requests: int
    rate_limit_window: int
```

#### Output: FastAPI Application

```python
from fastapi import FastAPI

def create_app(config: AppConfig) -> FastAPI:
    """
    Create fully configured FastAPI application.

    Returns:
        FastAPI: Configured application ready to serve
    """
```

---

## 5. Acceptance Criteria

### 1️⃣ Application Factory

**Must:**

- Create FastAPI instance with title, version, debug settings
- Disable OpenAPI docs if `enable_openapi=False`
- Register middleware in correct order (see Middleware section)
- Register all routers with correct prefixes
- Attach global exception handlers
- Configure lifespan context manager
- Return configured FastAPI app

**Must NOT:**

- Import deep internal modules unnecessarily
- Create DB sessions manually
- Instantiate providers directly
- Contain business logic
- Perform DB queries (except health checks)

**Example structure:**

```python
def create_app(config: AppConfig) -> FastAPI:
    # 1. Create FastAPI instance
    app = FastAPI(
        title=config.app_name,
        version=config.app_version,
        debug=config.debug_mode,
        docs_url="/docs" if config.enable_openapi else None,
        redoc_url="/redoc" if config.enable_openapi else None,
        lifespan=lifespan_handler
    )

    # 2. Register middleware (order matters!)
    register_middleware(app, config)

    # 3. Register routers
    register_routers(app)

    # 4. Register exception handlers
    register_exception_handlers(app)

    return app
```

---

### 2️⃣ Middleware Registration

**Middleware must be registered in this order:**

1. **Request Context Middleware** (first)
2. **Logging Middleware**
3. **CORS Middleware**
4. **Rate Limiting Middleware**
5. **Authentication Middleware** (last before routes)

**Why order matters:**

- Request context needed by all subsequent middleware
- Logging must capture all requests (even CORS preflight)
- CORS must run before auth (OPTIONS requests don't have tokens)
- Auth runs last so it has full request context

---

#### Middleware 1: Request Context Middleware

**Purpose:** Inject request metadata into `request.state` and contextvars.

**Must inject:**

- `request_id`: Unique UUID for request tracing
- `request_start_time`: Timestamp for latency calculation
- `user_id`: Set by auth middleware (or None)
- `organization_id`: Set by auth middleware for admins (or None)

**Example:**

```python
import uuid
from contextvars import ContextVar
from time import time

# Context vars for async task access
request_id_ctx: ContextVar[str] = ContextVar('request_id', default='')
user_id_ctx: ContextVar[Optional[int]] = ContextVar('user_id', default=None)
organization_id_ctx: ContextVar[Optional[int]] = ContextVar('organization_id', default=None)

async def request_context_middleware(request: Request, call_next):
    # Generate request ID
    req_id = str(uuid.uuid4())

    # Set in request.state
    request.state.request_id = req_id
    request.state.request_start_time = time()
    request.state.user_id = None
    request.state.organization_id = None

    # Set in contextvars
    request_id_ctx.set(req_id)

    response = await call_next(request)

    # Add request ID to response headers
    response.headers["X-Request-ID"] = req_id

    return response
```

---

#### Middleware 2: Logging Middleware

**Purpose:** Log all requests with method, path, status, latency, request_id.

**Must log:**

- `method`: HTTP method
- `path`: Request path (strip query params with sensitive data)
- `status_code`: Response status code
- `latency_ms`: Request duration in milliseconds
- `request_id`: From request.state
- `user_id`: From request.state (if authenticated)

**Must NOT log:**

- Access tokens
- Password fields
- Authorization headers (log presence, not value)
- Sensitive query params

**Example log format:**

```json
{
  "timestamp": "2026-02-14T10:30:00Z",
  "level": "INFO",
  "request_id": "abc-123",
  "method": "POST",
  "path": "/api/auth/login",
  "status_code": 200,
  "latency_ms": 45,
  "user_id": null
}
```

---

#### Middleware 3: CORS Middleware

**Purpose:** Control cross-origin requests.

**Must configure:**

- `allow_origins`: Whitelist from config (e.g., `["https://app.example.com"]`)
- `allow_credentials`: True (for cookies)
- `allow_methods`: `["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]`
- `allow_headers`: Include `Authorization`, `Content-Type`, `X-Request-ID`
- `expose_headers`: `["X-Request-ID"]`

**Must allow:** WebSocket upgrade requests

**Example:**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=config.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"]
)
```

---

#### Middleware 4: Rate Limiting Middleware

**Purpose:** Prevent abuse on expensive endpoints.

**Must protect:**

- `/api/auth/login` - 5 requests per 15 minutes per IP
- `/api/auth/register/*` - 3 requests per hour per IP
- `/api/evaluation/evaluate` - 10 requests per minute per user
- `/api/coding/execute` - 20 requests per minute per user

**Must NOT apply to:**

- Health check endpoints
- WebSocket connections (rate limit at connection level instead)

**Storage:** Use Redis for distributed rate limiting

**Response on limit exceeded:**

- Status: 429 Too Many Requests
- Headers: `Retry-After: <seconds>`
- Body: `{"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"}}`

---

#### Middleware 5: Authentication Middleware

**Purpose:** Parse JWT, validate, inject identity into request context.

**Must:**

- Extract JWT from `Authorization: Bearer <token>` header
- Extract JWT from query param for WebSocket (`?token=<token>`)
- Validate JWT signature using public key
- Validate JWT not expired
- Validate user active, admin active, org active (if applicable)
- Inject `AuthContext` into `request.state.auth`
- Set `request.state.user_id` and `request.state.organization_id`
- Skip for public routes (login, register, health check)

**Must NOT:**

- Perform RBAC checks (done in auth domain layer)
- Query database on every request (validate from JWT claims only, except critical checks)
- Block all requests if token invalid (allow public routes)

**Public routes (no auth required):**

- `/api/auth/login`
- `/api/auth/register/*`
- `/health`
- `/docs` (if enabled)

**Example:**

```python
PUBLIC_ROUTES = {
    "/api/auth/login",
    "/api/auth/register/admin",
    "/api/auth/register/candidate",
    "/health"
}

async def auth_middleware(request: Request, call_next):
    # Skip public routes
    if request.url.path in PUBLIC_ROUTES:
        return await call_next(request)

    # Extract token
    token = extract_token_from_header(request) or extract_token_from_query(request)

    if not token:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "MISSING_TOKEN", "message": "Authentication required"}}
        )

    # Validate token (delegates to auth.domain)
    try:
        auth_context = await validate_access_token(token)
        request.state.auth = auth_context
        request.state.user_id = auth_context.user_id
        request.state.organization_id = auth_context.organization_id

        # Update contextvars
        user_id_ctx.set(auth_context.user_id)
        organization_id_ctx.set(auth_context.organization_id)

    except TokenExpiredError:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "TOKEN_EXPIRED", "message": "Token has expired"}}
        )
    except TokenInvalidError:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "TOKEN_INVALID", "message": "Invalid token"}}
        )

    return await call_next(request)
```

---

### 3️⃣ Lifespan Management

**Purpose:** Manage application startup and shutdown safely.

**Lifespan context manager:**

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan_handler(app: FastAPI):
    # Startup
    await startup_handler(app)

    yield  # Application runs

    # Shutdown
    await shutdown_handler(app)
```

---

#### Startup Handler

**Must initialize:**

1. **PostgreSQL connection pool**
   - Create SQLAlchemy engine
   - Verify DB connectivity (simple query: `SELECT 1`)
   - Store engine in `app.state.db_engine`

2. **Redis connection pool**
   - Create Redis client
   - Verify connectivity (ping)
   - Store in `app.state.redis_client`

3. **Qdrant client**
   - Create Qdrant client
   - Verify connectivity (get collections)
   - Store in `app.state.qdrant_client`

4. **AI provider clients**
   - OpenAI client (for evaluation)
   - Whisper client (for transcription)
   - Store in `app.state.ai_clients`

5. **WebSocket manager**
   - Create WebSocket connection manager
   - Store in `app.state.ws_manager`

**Must verify connectivity for critical services:**

- If PostgreSQL fails: **fail fast and exit** (cannot run without DB)
- If Redis fails: **fail fast and exit** (needed for sessions, rate limiting)
- If Qdrant fails: **fail fast and exit** (needed for vector search)
- If AI provider fails: **log warning, continue** (can fail gracefully at runtime)

**Example:**

```python
async def startup_handler(app: FastAPI):
    logger.info("Starting application...")

    # 1. Database
    try:
        db_engine = create_db_engine(config.database_url)
        # Verify connectivity
        async with db_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        app.state.db_engine = db_engine
        logger.info("Database connected")
    except Exception as e:
        logger.critical(f"Database connection failed: {e}")
        raise SystemExit(1)

    # 2. Redis
    try:
        redis_client = create_redis_client(config.redis_url)
        await redis_client.ping()
        app.state.redis_client = redis_client
        logger.info("Redis connected")
    except Exception as e:
        logger.critical(f"Redis connection failed: {e}")
        raise SystemExit(1)

    # 3. Qdrant
    try:
        qdrant_client = create_qdrant_client(config.qdrant_url, config.qdrant_api_key)
        await qdrant_client.get_collections()
        app.state.qdrant_client = qdrant_client
        logger.info("Qdrant connected")
    except Exception as e:
        logger.critical(f"Qdrant connection failed: {e}")
        raise SystemExit(1)

    # 4. AI providers (non-critical)
    try:
        ai_clients = create_ai_clients(config)
        app.state.ai_clients = ai_clients
        logger.info("AI providers initialized")
    except Exception as e:
        logger.warning(f"AI provider initialization failed: {e}")
        app.state.ai_clients = None

    # 5. WebSocket manager
    app.state.ws_manager = WebSocketManager()
    logger.info("WebSocket manager initialized")

    logger.info("Application startup complete")
```

---

#### Shutdown Handler

**Must close:**

1. **PostgreSQL connection pool**
   - Dispose engine: `await db_engine.dispose()`

2. **Redis connection pool**
   - Close Redis client: `await redis_client.close()`

3. **Qdrant client**
   - Close Qdrant client: `await qdrant_client.close()`

4. **WebSocket connections**
   - Disconnect all active WebSocket connections gracefully
   - Send close message to clients
   - Wait for acknowledgment (with timeout)

5. **Telemetry buffers**
   - Flush logs
   - Flush metrics

**Must NOT:**

- Leave hanging tasks
- Leave open connections
- Block shutdown indefinitely (use timeouts)

**Example:**

```python
async def shutdown_handler(app: FastAPI):
    logger.info("Shutting down application...")

    # 1. Close WebSocket connections
    if hasattr(app.state, 'ws_manager'):
        await app.state.ws_manager.disconnect_all(reason="Server shutting down")

    # 2. Close database
    if hasattr(app.state, 'db_engine'):
        await app.state.db_engine.dispose()
        logger.info("Database connections closed")

    # 3. Close Redis
    if hasattr(app.state, 'redis_client'):
        await app.state.redis_client.close()
        logger.info("Redis connection closed")

    # 4. Close Qdrant
    if hasattr(app.state, 'qdrant_client'):
        await app.state.qdrant_client.close()
        logger.info("Qdrant connection closed")

    logger.info("Application shutdown complete")
```

---

### 4️⃣ Router Registration

**Must register all routers centrally.**

**Routers to register:**

1. Auth router: `/api/auth`
2. Admin router: `/api/admin`
3. Interview router: `/api/interviews`
4. Evaluation router: `/api/evaluation`
5. Question router: `/api/questions`
6. Coding router: `/api/coding`
7. Proctoring router: `/api/proctoring`
8. Audio router: `/api/audio`
9. Health check router: `/health`
10. WebSocket router: `/ws`

**Example:**

```python
def register_routers(app: FastAPI):
    # Public routes
    app.include_router(health_router, tags=["health"])
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

    # Protected routes
    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    app.include_router(interview_router, prefix="/api/interviews", tags=["interviews"])
    app.include_router(evaluation_router, prefix="/api/evaluation", tags=["evaluation"])
    app.include_router(question_router, prefix="/api/questions", tags=["questions"])
    app.include_router(coding_router, prefix="/api/coding", tags=["coding"])
    app.include_router(proctoring_router, prefix="/api/proctoring", tags=["proctoring"])
    app.include_router(audio_router, prefix="/api/audio", tags=["audio"])

    # WebSocket routes
    app.include_router(websocket_router, prefix="/ws", tags=["websocket"])
```

**No router should self-register.** All registration happens in bootstrap.

---

### 5️⃣ Global Exception Handling

**Must define centralized handlers for:**

#### 1. AuthenticationError

```python
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "request_id": request.state.request_id
            }
        }
    )
```

#### 2. AuthorizationError (Insufficient Permissions)

```python
@app.exception_handler(AuthorizationError)
async def authorization_error_handler(request: Request, exc: AuthorizationError):
    return JSONResponse(
        status_code=403,
        content={
            "error": {
                "code": "INSUFFICIENT_PERMISSIONS",
                "message": exc.message,
                "request_id": request.state.request_id
            }
        }
    )
```

#### 3. ValidationError (Pydantic)

```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request data",
                "details": exc.errors(),
                "request_id": request.state.request_id
            }
        }
    )
```

#### 4. DomainInvariantViolation

```python
@app.exception_handler(DomainInvariantViolation)
async def invariant_violation_handler(request: Request, exc: DomainInvariantViolation):
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "INVARIANT_VIOLATION",
                "message": exc.message,
                "request_id": request.state.request_id
            }
        }
    )
```

#### 5. DatabaseError

```python
from sqlalchemy.exc import SQLAlchemyError

@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"Database error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "DATABASE_ERROR",
                "message": "An internal database error occurred",
                "request_id": request.state.request_id
            }
        }
    )
```

#### 6. AIProviderError

```python
@app.exception_handler(AIProviderError)
async def ai_provider_error_handler(request: Request, exc: AIProviderError):
    logger.error(f"AI provider error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "AI_SERVICE_UNAVAILABLE",
                "message": "AI service is temporarily unavailable",
                "request_id": request.state.request_id
            }
        }
    )
```

#### 7. RateLimitExceeded

```python
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests",
                "retry_after": exc.retry_after,
                "request_id": request.state.request_id
            }
        },
        headers={"Retry-After": str(exc.retry_after)}
    )
```

#### 8. Catch-All Handler

```python
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.critical(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "request_id": request.state.request_id
            }
        }
    )
```

**All responses must:**

- Follow consistent JSON structure
- Never leak stack traces (log them, don't expose)
- Include `request_id` for tracing

---

### 6️⃣ Dependency Injection Wiring

**Must define reusable dependencies:**

#### 1. Get Database Session

```python
from sqlalchemy.ext.asyncio import AsyncSession

async def get_db_session(request: Request) -> AsyncSession:
    """Provide database session for request"""
    engine = request.app.state.db_engine
    async with AsyncSession(engine) as session:
        yield session
```

#### 2. Get Redis Client

```python
async def get_redis_client(request: Request) -> Redis:
    """Provide Redis client for request"""
    return request.app.state.redis_client
```

#### 3. Get Qdrant Client

```python
async def get_qdrant_client(request: Request) -> QdrantClient:
    """Provide Qdrant client for request"""
    return request.app.state.qdrant_client
```

#### 4. Get Current User (Auth Context)

```python
async def get_current_user(request: Request) -> AuthContext:
    """Get authenticated user from request context"""
    if not hasattr(request.state, 'auth'):
        raise AuthenticationError("Authentication required")
    return request.state.auth
```

#### 5. Get Current Admin

```python
async def get_current_admin(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    """Require user to be admin"""
    if not auth.is_admin():
        raise AuthorizationError("Admin access required")
    return auth
```

#### 6. Get Current Candidate

```python
async def get_current_candidate(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
    """Require user to be candidate"""
    if not auth.is_candidate():
        raise AuthorizationError("Candidate access required")
    return auth
```

**Dependencies must:**

- Be stateless
- Be reusable across endpoints
- Avoid circular imports

---

### 7️⃣ WebSocket Bootstrap

**Must:**

- Authenticate on connection (before upgrade)
- Extract token from query param or header
- Validate token
- Attach identity context to WebSocket connection
- Reject invalid tokens before upgrade
- Track active connections in WebSocket manager

**Must integrate with:**

- Redis session store (for tracking active connections across instances)
- Interview orchestrator (for routing interview messages)

**Must handle:**

- Disconnect cleanup (remove from active connections)
- Token expiration mid-session (send close message, disconnect)

**Example WebSocket endpoint:**

```python
@router.websocket("/ws/interview/{interview_id}")
async def interview_websocket(
    websocket: WebSocket,
    interview_id: int,
    token: str = Query(...)  # Token from query param
):
    # 1. Authenticate before accepting connection
    try:
        auth_context = await validate_access_token(token)
    except Exception as e:
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # 2. Accept connection
    await websocket.accept()

    # 3. Register connection
    ws_manager = websocket.app.state.ws_manager
    await ws_manager.connect(websocket, auth_context, interview_id)

    try:
        # 4. Handle messages
        while True:
            data = await websocket.receive_json()
            await handle_interview_message(websocket, auth_context, interview_id, data)
    except WebSocketDisconnect:
        # 5. Cleanup on disconnect
        await ws_manager.disconnect(websocket, auth_context, interview_id)
```

---

## 6. Invariants & Constraints

### Must Hold

1. **Middleware Order:** Request context → Logging → CORS → Rate Limiting → Auth
2. **Lifespan Safety:** Shutdown must close all connections
3. **Auth Injection:** All protected routes must have `AuthContext` in request.state
4. **Consistent Errors:** All errors follow same JSON structure
5. **No Business Logic:** Bootstrap contains only wiring, no domain logic
6. **Fail Fast:** Critical service failures (DB, Redis, Qdrant) must exit immediately on startup

### Forbidden

- MUST NOT contain business logic
- MUST NOT access domain modules directly (only via router imports)
- MUST NOT perform DB queries (except health checks)
- MUST NOT expose stack traces in production
- MUST NOT log sensitive data (tokens, passwords)
- MUST NOT allow router self-registration (all registration in bootstrap)

---

## 7. Dependent Modules

### Upstream (Callers)

1. **Main entrypoint (`main.py` or `uvicorn`):**
   - Calls `create_app()`
   - Runs app with ASGI server

### Downstream (Dependencies)

1. **All routers:** Auth, Admin, Interview, Evaluation, Coding, Proctoring, Audio
2. **Auth domain:** Token validation
3. **Database:** SQLAlchemy engine
4. **Redis:** Client for rate limiting, sessions
5. **Qdrant:** Client for vector search
6. **AI providers:** OpenAI, Whisper clients

---

## 8. Security Requirements

**Bootstrap must ensure:**

1. **HTTPS Enforcement:** Redirect HTTP to HTTPS (if behind proxy, trust proxy headers)
2. **Secure Headers:**
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `X-XSS-Protection: 1; mode=block`
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains`

3. **Debug Mode:** Disabled in production
4. **OpenAPI Docs:** Disabled in production (optional, or require auth)
5. **CORS Restrictions:** Whitelist specific origins, no wildcard in production

**Example secure headers middleware:**

```python
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if not config.debug_mode:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
```

---

## 9. Edge Cases to Handle

### 1. Silent Startup Failure

**Scenario:** Database connection succeeds on startup, but connection is dropped immediately after.

**Handling:**

- Verify connectivity with actual query: `SELECT 1`
- If verification fails, exit immediately
- Log critical error

---

### 2. Missing Tenant Injection

**Scenario:** Admin user authenticated, but `organization_id` not injected into request.state.

**Handling:**

- Auth middleware MUST extract `organization_id` from JWT claims
- Set `request.state.organization_id = auth_context.organization_id`
- If missing, log error and reject request

---

### 3. WebSocket Bypassing Auth Middleware

**Scenario:** WebSocket upgrade happens before auth validation.

**Handling:**

- Authenticate BEFORE calling `websocket.accept()`
- Extract token from query param
- Validate token
- If invalid, call `websocket.close(code=1008, reason="Authentication failed")` and return

---

### 4. Double Registration of Routers

**Scenario:** Router registered twice, causing duplicate routes.

**Handling:**

- FastAPI raises error on duplicate route registration
- Ensure each router registered exactly once in `register_routers()`

---

### 5. Blocking Operations in Middleware

**Scenario:** Middleware performs blocking I/O (e.g., synchronous Redis call), blocking event loop.

**Handling:**

- All middleware must use async operations
- Use `await` for I/O operations
- Never use synchronous blocking calls (no `time.sleep`, use `asyncio.sleep`)

---

### 6. Memory Leaks in Connection Pools

**Scenario:** Database connections not properly closed, pool exhausted.

**Handling:**

- Use context managers for sessions: `async with AsyncSession(engine) as session:`
- Ensure `get_db_session` dependency uses `yield` (FastAPI closes automatically)
- Monitor connection pool metrics (active connections, idle connections)

---

### 7. Token Expiration Mid-Session

**Scenario:** WebSocket connected with valid token, token expires 30 minutes later.

**Handling:**

- WebSocket manager periodically checks token expiration (every 5 minutes)
- If token expired, send close message: `{"type": "close", "reason": "token_expired"}`
- Close WebSocket connection: `await websocket.close(code=1008, reason="Token expired")`

---

## 10. Concurrency Concerns

### 1. Concurrent Startup

**Scenario:** Multiple instances of app starting simultaneously (e.g., Kubernetes rollout).

**Handling:**

- Connection pools handle concurrency
- Database migrations should be applied separately (not in startup)
- Redis and Qdrant clients are safe for concurrent initialization

---

### 2. Middleware State Mutation

**Scenario:** Middleware modifies shared state, causing race conditions.

**Handling:**

- Use `request.state` for request-scoped data (thread-safe per request)
- Use `contextvars` for async task isolation
- Never mutate global state in middleware

---

### 3. Shutdown During Request Handling

**Scenario:** App shutting down while requests are in-flight.

**Handling:**

- FastAPI graceful shutdown waits for in-flight requests (with timeout)
- Set reasonable shutdown timeout (e.g., 30 seconds)
- Log warning if requests still pending after timeout

---

## 11. Configuration

### Environment Variables

```bash
# Application
APP_NAME=AI Interviewer API
APP_VERSION=1.0.0
DEBUG_MODE=false
ENABLE_OPENAPI=false

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ai_interviewer
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Redis
REDIS_URL=redis://localhost:6379/0

# Qdrant
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key

# JWT
JWT_PUBLIC_KEY_PATH=/path/to/public.pem
JWT_PRIVATE_KEY_PATH=/path/to/private.pem

# CORS
CORS_ORIGINS=["https://app.example.com"]
CORS_ALLOW_CREDENTIALS=true

# Security
ENFORCE_HTTPS=true
SECURE_HEADERS=true

# Rate Limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_REQUESTS=5
RATE_LIMIT_WINDOW=900  # 15 minutes
```

---

## 12. Testing Requirements

**Must test:**

### 1. App Startup with Missing DB

```python
def test_startup_failure_missing_db():
    """App should exit if database unavailable"""
    with pytest.raises(SystemExit):
        create_app(config_with_invalid_db_url)
```

### 2. Middleware Injection Correctness

```python
async def test_request_context_injection():
    """Request context should have request_id and timestamps"""
    response = await client.get("/health")
    assert "X-Request-ID" in response.headers
```

### 3. Invalid JWT Rejection

```python
async def test_invalid_jwt_rejected():
    """Invalid JWT should return 401"""
    response = await client.get(
        "/api/admin/users",
        headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "TOKEN_INVALID"
```

### 4. WebSocket Connection with Expired Token

```python
async def test_websocket_expired_token():
    """WebSocket should reject expired token"""
    with pytest.raises(WebSocketDisconnect):
        async with client.websocket_connect(f"/ws/interview/1?token=expired-token") as ws:
            pass
```

### 5. Exception Handler Format

```python
async def test_exception_handler_format():
    """All exceptions should follow consistent JSON structure"""
    response = await client.post("/api/auth/login", json={"invalid": "data"})
    assert "error" in response.json()
    assert "code" in response.json()["error"]
    assert "message" in response.json()["error"]
    assert "request_id" in response.json()["error"]
```

### 6. Lifespan Shutdown Cleanup

```python
async def test_lifespan_shutdown():
    """Shutdown should close all connections"""
    app = create_app(config)
    async with LifespanManager(app):
        # App running
        assert hasattr(app.state, 'db_engine')
        assert hasattr(app.state, 'redis_client')

    # After shutdown
    # Verify connections closed (check pool metrics)
```

---

## 13. Critical Risk Areas

1. **Silent startup failure:** DB not actually connected, app starts anyway
2. **Missing tenant injection:** Admin actions not filtered by organization_id
3. **WebSocket bypassing auth middleware:** Unauthenticated WebSocket connections
4. **Double registration of routers:** Duplicate routes causing unpredictable behavior
5. **Blocking operations in middleware:** Synchronous I/O blocking event loop
6. **Memory leaks in connection pools:** Connections not properly closed

---

## 14. Future Enhancements

1. **OpenTelemetry Integration:**
   - Distributed tracing
   - Metrics collection
   - Log aggregation

2. **Health Check Enhancements:**
   - Deep health checks (DB query, Redis ping, Qdrant connectivity)
   - Readiness vs liveness probes
   - Graceful degradation status

3. **Admin API for Bootstrap:**
   - Runtime configuration updates
   - Connection pool resizing
   - Circuit breaker status

4. **Advanced Rate Limiting:**
   - Per-user rate limits
   - Per-organization rate limits
   - Dynamic rate limit adjustment

5. **Request Replay for Debugging:**
   - Record failed requests
   - Replay in test environment

---

**End of Bootstrap Module Requirements**

---

## Architectural Intent

`bootstrap` is:

- The **assembly layer**
- The **dependency graph root**
- The **global control boundary**

It wires the system together but owns no business rules.

**If it grows large, your architecture is drifting.**

Keep it thin, predictable, and boring.
