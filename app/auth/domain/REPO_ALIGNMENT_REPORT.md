# AUTH/DOMAIN MODULE - REPO ALIGNMENT REPORT

**Module:** `app/auth/domain`  
**Purpose:** Core authentication logic - registration, login, JWT issuance/validation, RBAC enforcement  
**Implementation Date:** 2026-02-26  
**Status:** Pre-Implementation Audit Complete

---

## 1. EXISTING MODULE INVENTORY

### 1.1 /app/shared (Cross-Cutting Infrastructure)
**Status:** ✅ FULLY IMPLEMENTED

#### shared/errors/
- **Purpose:** Unified error hierarchy for all protocols (REST/WebSocket/WebRTC)
- **Key Classes:**
  - `BaseError`: Foundation (error_code, message, request_id, metadata, http_status_code)
  - `AuthenticationError`: 401 errors (invalid/expired/missing token)
  - `AuthorizationError`: 403 errors (insufficient permissions)
  - `ValidationError`: 422 errors (invalid request payload)
  - `NotFoundError`: 404 errors (resource not found)
  - `ConflictError`: 409 errors (state conflicts)
  - `InfrastructureError`: 500 errors (external service failures)
- **Usage:** `raise AuthenticationError(message="...", request_id=...)`
- **Reuse:** Import and raise, do NOT define new error classes unless domain-specific

#### shared/observability/
- **Purpose:** Structured logging, metrics, tracing
- **Key Functions:**
  - `get_context_logger(name)`: Returns logger with auto context injection
  - `StructuredFormatter`: JSON log formatter
  - `ContextLogger`: Logger with request_id, user_id, organization_id injection
- **Usage:**
  ```python
  from app.shared.observability import get_context_logger
  logger = get_context_logger(__name__)
  logger.info("User registered", extra={"user_id": user.id, "event_type": "user.registered"})
  ```
- **Reuse:** Use for all domain event logging

#### shared/auth_context/
- **Purpose:** Identity context models and propagation
- **Key Models:**
  - `IdentityContext`: Immutable identity (user_id, user_type, organization_id, admin_role)
  - `UserType(Enum)`: ADMIN | CANDIDATE
  - `AdminRole(Enum)`: SUPERADMIN | ADMIN | READ_ONLY
- **Key Dependencies:**
  - `get_identity(request)`: Extract identity from request.state (FastAPI)
  - `require_admin()`, `require_candidate()`, `require_superadmin()`: Role guards
- **Usage:** Domain layer does NOT use FastAPI dependencies - API layer uses these
- **Reuse:** Use `IdentityContext` model for output contracts (e.g., `AuthContext` in JWT validation)

---

### 1.2 /app/config (Configuration Management)
**Status:** ✅ FULLY IMPLEMENTED

- **Purpose:** Centralized settings management (Pydantic Settings)
- **Key Classes:**
  - `AppSettings`: Application environment config
  - `DatabaseSettings`: PostgreSQL connection settings
  - `RedisSettings`: Redis connection settings
- **Usage:**
  ```python
  from app.config.settings import get_app_settings
  settings = get_app_settings()
  access_token_ttl = settings.jwt_access_token_ttl_minutes
  ```
- **Reuse:** Load JWT config (private key, ttl, algorithm) from settings

---

### 1.3 /app/persistence (Database Layer)
**Status:** ✅ PARTIALLY IMPLEMENTED

#### persistence/postgres/
- **Purpose:** SQLAlchemy engine, session factory, connection pooling
- **Key Functions:**
  - `get_db_session()`: FastAPI dependency for request-scoped sessions
  - `get_db_session_with_commit()`: Auto-commit on success
  - `init_session_factory()`: Initialize sessionmaker
  - `get_engine()`: Get SQLAlchemy engine
- **Session Pattern:**
  ```python
  from app.persistence.postgres import get_db_session
  from sqlalchemy.orm import Session
  
  def my_domain_function(session: Session):
      user = session.query(User).filter_by(email=email).first()
      session.add(new_user)
      session.commit()
  ```
- **Reuse:** Domain layer receives `Session` from API layer (dependency injection)

#### persistence/qdrant/ (Not Relevant to Auth)
- **Purpose:** Vector embeddings for question retrieval
- **Status:** Not used by auth module

#### persistence/redis/ (Future Use)
- **Purpose:** Caching, rate limiting, session storage
- **Status:** May be used for token blacklisting (future enhancement)

---

### 1.4 /app/bootstrap (Application Initialization)
**Status:** ✅ FULLY IMPLEMENTED

- **Purpose:** FastAPI app factory, middleware registration, router registry
- **Key Functions:**
  - `create_app()`: Returns configured FastAPI instance
  - `init_session_factory()`: Initialize DB session factory
  - `setup_logging()`: Configure structured logging
- **Exports:** `from app.bootstrap.dependencies import get_db_session, get_identity`
- **Reuse:** Do NOT modify bootstrap - auth module will be registered as router

---

### 1.5 /app/ai (AI/LLM Module)
**Status:** ✅ FULLY IMPLEMENTED

- **Purpose:** LLM provider abstraction, prompt management, telemetry
- **Relevance to Auth:** None (auth does not call LLM)
- **Pattern Identified:** Provider factory pattern, contract-based interfaces
- **Reuse:** Follow similar pattern for token generation (abstract interface + concrete implementations)

---

### 1.6 /app/admin (Admin Module)
**Status:** ❌ NOT YET IMPLEMENTED

- **Expected Purpose:** Organization management, template/rubric management, admin CRUD
- **Expected Interfaces:**
  - `admin/persistence/organization_repository.py`: CRUD for organizations table
- **Dependency:** Auth domain needs `OrganizationRepository` to validate org existence/status during admin registration
- **Decision:**
  - **CANNOT implement OrganizationRepository in auth module** (violates module boundaries)
  - **TEMPORARY SOLUTION:** Create minimal organization validation function in auth/persistence
  - **FUTURE REFACTOR:** Replace with proper admin.persistence.OrganizationRepository when admin module implemented

---

### 1.7 /app/interview, /app/evaluation, /app/question, /app/coding, /app/proctoring, /app/audio
**Status:** ❌ NOT YET IMPLEMENTED

- **Relevance to Auth:** These are **consumers** of auth module (depend on auth for identity/RBAC)
- **Decision:** No dependencies on unimplemented modules - auth is foundational

---

## 2. DEPENDENCY GRAPH

### Auth Domain Dependencies (Inbound)

```
auth/domain/
├── REUSES: shared/errors (AuthenticationError, AuthorizationError, ValidationError, ConflictError, NotFoundError)
├── REUSES: shared/observability (get_context_logger)
├── REUSES: shared/auth_context/models (IdentityContext, UserType, AdminRole) - for output contracts
├── REUSES: config/settings (JWT config, password config, token TTLs)
├── DEPENDS ON: auth/persistence (UserRepository, AdminRepository, CandidateRepository, RefreshTokenRepository, AuthAuditLogRepository)
├── DEPENDS ON: External libs (bcrypt/argon2, PyJWT/python-jose)
└── FUTURE DEPENDS ON: admin/persistence (OrganizationRepository) - **NOT YET AVAILABLE**
```

### Auth Domain Dependents (Outbound)

```
auth/api/
└── calls: auth/domain/AuthService
    └── returns: AuthenticationResult, UserProfile, TokenValidationResult

auth/middleware/ (planned)
└── calls: auth/domain/TokenValidator
    └── to inject: IdentityContext into request.state

interview/, evaluation/, admin/, etc. (future)
└── uses: IdentityContext from request.state
    └── enforces: tenant isolation, RBAC
```

---

## 3. SHARED PATTERNS IDENTIFIED

### 3.1 Error Handling Pattern
✅ **PATTERN EXISTS**: Structured exceptions with metadata

**Location:** `app/shared/errors/exceptions.py`

**Pattern:**
```python
from app.shared.errors import AuthenticationError, ConflictError

# Check user status
if user.status != 'active':
    raise AuthenticationError(
        message=f"User is {user.status}",
        request_id=request_id,
        metadata={"user_id": user.id, "status": user.status}
    )

# Check email uniqueness
if user_repo.email_exists(email):
    raise ConflictError(
        message="Email already registered",
        request_id=request_id,
        metadata={"email": email}
    )
```

**Usage in auth/domain:**
- Raise `AuthenticationError` for login failures
- Raise `ConflictError` for duplicate emails
- Raise `AuthorizationError` for insufficient permissions
- Raise `ValidationError` for password complexity failures
- Do NOT create custom error classes unless domain-specific

---

### 3.2 Repository Pattern
❌ **PATTERN PARTIALLY EXISTS**: No repository implementations in codebase yet

**Expected Pattern:**
```python
class UserRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, email: str, password_hash: str, user_type: str) -> User:
        user = User(email=email, password_hash=password_hash, user_type=user_type)
        self.session.add(user)
        self.session.flush()
        return user
    
    def find_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter(
            func.lower(User.email) == email.lower()
        ).first()
    
    def email_exists(self, email: str) -> bool:
        return self.session.query(
            exists().where(func.lower(User.email) == email.lower())
        ).scalar()
```

**Usage in auth/domain:**
- Auth domain will call repository methods
- Repositories injected via constructor
- No SQL in domain layer

---

### 3.3 Structured Logging Pattern
✅ **PATTERN EXISTS**: JSON logging with context injection

**Location:** `app/shared/observability/logging.py`

**Pattern:**
```python
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)

# Log domain events
logger.info(
    "User registered successfully",
    extra={
        "event_type": "user.registered",
        "user_id": user.id,
        "user_type": user.user_type,
        "organization_id": org_id
    }
)

# Log failures
logger.warning(
    "Login failed - invalid password",
    extra={
        "event_type": "login.failed",
        "reason": "invalid_password",
        "email": email,
        "ip_address": ip
    }
)
```

**Usage in auth/domain:**
- Log all authentication events (registration, login, logout, token refresh)
- Log failures with reason codes
- Include ip_address, user_agent in metadata
- Do NOT log passwords or tokens

---

### 3.4 Pydantic Settings Pattern
✅ **PATTERN EXISTS**: Environment-based configuration

**Location:** `app/config/settings.py`

**Pattern:**
```python
from pydantic_settings import BaseSettings
from pydantic import Field

class JWTSettings(BaseSettings):
    jwt_algorithm: str = Field(default="RS256", env="JWT_ALGORITHM")
    jwt_private_key: str = Field(..., env="JWT_PRIVATE_KEY")
    jwt_public_key: str = Field(..., env="JWT_PUBLIC_KEY")
    jwt_access_token_ttl_minutes: int = Field(default=15, env="JWT_ACCESS_TOKEN_TTL_MINUTES")
    jwt_refresh_token_ttl_days: int = Field(default=30, env="JWT_REFRESH_TOKEN_TTL_DAYS")
    
    class Config:
        env_file = ".env"
```

**Usage in auth/domain:**
- Load JWT config from settings
- Load password policy from settings
- Load token TTLs from settings
- Do NOT hardcode secrets

---

### 3.5 Dataclass Pattern
✅ **PATTERN EXISTS**: Frozen dataclasses for immutable contracts

**Location:** `app/shared/auth_context/models.py`, `app/ai/llm/contracts.py`

**Pattern:**
```python
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class AuthenticationResult:
    """Immutable authentication result"""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds
    user_profile: 'UserProfile'
```

**Usage in auth/domain:**
- Use `@dataclass` for all commands (RegisterAdminCommand, LoginCommand, etc.)
- Use `@dataclass(frozen=True)` for results (AuthenticationResult, TokenValidationResult, etc.)
- Validate invariants in `__post_init__`

---

## 4. SCHEMA RECONCILIATION

### 4.1 Existing Tables (schema.sql)

#### `users` table
```sql
CREATE TABLE public.users (
    id bigint NOT NULL PRIMARY KEY,
    name text NOT NULL,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    status public.user_status DEFAULT 'active'::public.user_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
```

**Enums:**
```sql
CREATE TYPE public.user_status AS ENUM ('active', 'inactive', 'banned');
```

**Analysis:**
- ✅ Matches auth requirements
- ⚠️ `name` field exists but requirements specify optional `full_name`
- ✅ `status` enum matches
- ❌ Missing `last_login_at` field (requirement specifies tracking last login)
- ❌ Missing `user_type` field (requirement specifies 'admin' | 'candidate')
- ❌ Missing `token_version` field (for forced logout feature)

**Required Schema Changes:**
```sql
ALTER TABLE public.users 
ADD COLUMN user_type VARCHAR(20) NOT NULL CHECK (user_type IN ('admin', 'candidate')),
ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN token_version INTEGER DEFAULT 1 NOT NULL;
```

---

#### `admins` table
```sql
CREATE TABLE public.admins (
    id bigint NOT NULL PRIMARY KEY,
    user_id bigint NOT NULL UNIQUE,
    organization_id bigint NOT NULL,
    role public.admin_role NOT NULL,
    status public.admin_status DEFAULT 'active'::public.admin_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE,
    FOREIGN KEY (organization_id) REFERENCES public.organizations(id) ON DELETE CASCADE
);
```

**Enums:**
```sql
CREATE TYPE public.admin_role AS ENUM ('superadmin', 'admin', 'read_only');
CREATE TYPE public.admin_status AS ENUM ('active', 'inactive', 'suspended');
```

**Analysis:**
- ✅ Matches auth requirements
- ✅ Correct FK constraints
- ⚠️ `admin_status` includes 'suspended' but requirements only mention 'active', 'inactive'
- ✅ Cascading delete on user delete

**No changes required** - schema is compatible

---

#### `candidates` table
```sql
CREATE TABLE public.candidates (
    id bigint NOT NULL PRIMARY KEY,
    user_id bigint NOT NULL UNIQUE,
    plan public.candidate_plan DEFAULT 'free'::public.candidate_plan NOT NULL,
    status public.user_status DEFAULT 'active'::public.user_status NOT NULL,
    profile_metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);
```

**Enums:**
```sql
CREATE TYPE public.candidate_plan AS ENUM ('free', 'pro', 'prime');
```

**Analysis:**
- ✅ Matches auth requirements
- ✅ `profile_metadata` JSONB can store full_name, phone, resume_url
- ⚠️ Requirements specify separate columns but schema uses JSONB
- ✅ Cascading delete on user delete

**Decision:** Use JSONB `profile_metadata` as-is (more flexible than separate columns)

---

### 4.2 Missing Tables (Required by Auth Module)

#### `refresh_tokens` table (MISSING)
**Requirements specify:**
```sql
CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    device_info TEXT,
    ip_address VARCHAR(45),
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    revoked_at TIMESTAMP,
    revoked_reason VARCHAR(100),
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

**Status:** ❌ DOES NOT EXIST IN SCHEMA
**Action:** MUST CREATE

**Proposed SQL:**
```sql
CREATE TABLE public.refresh_tokens (
    id bigint NOT NULL PRIMARY KEY,
    user_id bigint NOT NULL,
    token_hash text NOT NULL UNIQUE,
    device_info text,
    ip_address inet,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    revoked_reason varchar(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
);

CREATE INDEX idx_refresh_tokens_user ON public.refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires ON public.refresh_tokens(expires_at) WHERE revoked_at IS NULL;
```

---

#### `auth_audit_log` table (MISSING)
**Requirements specify:**
```sql
CREATE TABLE auth_audit_log (
    id SERIAL PRIMARY KEY,
    user_id INT,
    event_type VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);
```

**Status:** ❌ DOES NOT EXIST IN SCHEMA
**Action:** MUST CREATE

**Proposed SQL:**
```sql
CREATE TABLE public.auth_audit_log (
    id bigint NOT NULL PRIMARY KEY,
    user_id bigint,
    event_type varchar(50) NOT NULL,
    ip_address inet,
    user_agent text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_auth_audit_user ON public.auth_audit_log(user_id);
CREATE INDEX idx_auth_audit_event ON public.auth_audit_log(event_type);
CREATE INDEX idx_auth_audit_created ON public.auth_audit_log(created_at);
```

---

### 4.3 Summary of Schema Changes

#### ✅ REQUIRED SCHEMA MIGRATIONS

**Migration 001: Add missing columns to `users` table**
```sql
-- Add user_type column (admin or candidate)
ALTER TABLE public.users 
ADD COLUMN user_type VARCHAR(20) CHECK (user_type IN ('admin', 'candidate'));

-- Backfill user_type based on admins/candidates tables
UPDATE public.users u
SET user_type = 'admin'
WHERE EXISTS (SELECT 1 FROM public.admins a WHERE a.user_id = u.id);

UPDATE public.users u
SET user_type = 'candidate'
WHERE EXISTS (SELECT 1 FROM public.candidates c WHERE c.user_id = u.id);

-- Make user_type NOT NULL
ALTER TABLE public.users ALTER COLUMN user_type SET NOT NULL;

-- Add last_login_at column
ALTER TABLE public.users 
ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE;

-- Add token_version for forced logout
ALTER TABLE public.users 
ADD COLUMN token_version INTEGER DEFAULT 1 NOT NULL;
```

**Migration 002: Create `refresh_tokens` table**
```sql
CREATE SEQUENCE public.refresh_tokens_id_seq;

CREATE TABLE public.refresh_tokens (
    id bigint NOT NULL DEFAULT nextval('public.refresh_tokens_id_seq'::regclass),
    user_id bigint NOT NULL,
    token_hash text NOT NULL,
    device_info text,
    ip_address inet,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    revoked_reason varchar(100),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    
    CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id),
    CONSTRAINT refresh_tokens_token_hash_unique UNIQUE (token_hash),
    CONSTRAINT refresh_tokens_user_fkey FOREIGN KEY (user_id) 
        REFERENCES public.users(id) ON DELETE CASCADE
);

CREATE INDEX idx_refresh_tokens_user ON public.refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires ON public.refresh_tokens(expires_at) 
    WHERE revoked_at IS NULL;
```

**Migration 003: Create `auth_audit_log` table**
```sql
CREATE SEQUENCE public.auth_audit_log_id_seq;

CREATE TABLE public.auth_audit_log (
    id bigint NOT NULL DEFAULT nextval('public.auth_audit_log_id_seq'::regclass),
    user_id bigint,
    event_type varchar(50) NOT NULL,
    ip_address inet,
    user_agent text,
    metadata jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    
    CONSTRAINT auth_audit_log_pkey PRIMARY KEY (id),
    CONSTRAINT auth_audit_log_user_fkey FOREIGN KEY (user_id) 
        REFERENCES public.users(id) ON DELETE SET NULL
);

CREATE INDEX idx_auth_audit_user ON public.auth_audit_log(user_id);
CREATE INDEX idx_auth_audit_event ON public.auth_audit_log(event_type);
CREATE INDEX idx_auth_audit_created ON public.auth_audit_log(created_at);
```

---

## 5. NO DUPLICATION VERIFICATION

### ✅ Errors: REUSE EXISTING
- **Existing:** `app.shared.errors.exceptions`
- **Classes to reuse:**
  - `AuthenticationError` (401 errors)
  - `AuthorizationError` (403 errors)
  - `ValidationError` (422 errors - password complexity)
  - `ConflictError` (409 errors - duplicate email)
  - `NotFoundError` (404 errors - user not found)
- **Action:** Import and raise, do NOT redefine

---

### ✅ Logging: REUSE EXISTING
- **Existing:** `app.shared.observability.logging.get_context_logger`
- **Action:** Use for all domain event logging
- **Pattern:**
  ```python
  logger = get_context_logger(__name__)
  logger.info("Event occurred", extra={"event_type": "...", "user_id": ...})
  ```

---

### ✅ Identity Models: REUSE EXISTING
- **Existing:** `app.shared.auth_context.models`
- **Classes to reuse:**
  - `IdentityContext` (for output contracts)
  - `UserType(Enum)`
  - `AdminRole(Enum)`
- **Action:** Import and use for `AuthContext` output in JWT validation
- **DO NOT:** Redefine enums or context models

---

### ✅ Database Session: REUSE EXISTING
- **Existing:** `app.persistence.postgres.get_db_session`
- **Action:** API layer injects `Session` into domain service
- **Pattern:**
  ```python
  # API layer
  @router.post("/register")
  def register(request: RegisterRequest, db: Session = Depends(get_db_session)):
      service = AuthService(session=db)
      result = service.register_admin(command)
      db.commit()
      return result
  ```

---

### ❌ Organization Validation: TEMPORARY STUB
- **Expected:** `app.admin.persistence.OrganizationRepository`
- **Status:** Admin module not yet implemented
- **Decision:**
  - Create minimal `_validate_organization` helper in auth/domain
  - Direct SQL query: `SELECT status FROM organizations WHERE id = ?`
  - **FUTURE REFACTOR:** Replace with proper OrganizationRepository when admin module exists
- **Justification:** Cannot block auth implementation on unimplemented modules

---

### ❌ Password Hashing: NEW IMPLEMENTATION REQUIRED
- **Status:** No existing password hashing utility
- **Action:** Create `auth/domain/password_hasher.py`
- **Libraries:** Use `bcrypt` (recommended) or `argon2-cffi`
- **Interface:**
  ```python
  class PasswordHasher:
      def hash(self, password: str) -> str: ...
      def verify(self, password: str, hash: str) -> bool: ...
      def validate_complexity(self, password: str) -> None: ...
  ```

---

### ❌ JWT Services: NEW IMPLEMENTATION REQUIRED
- **Status:** No existing JWT signing/verification
- **Action:** Create `auth/domain/jwt_service.py`
- **Libraries:** Use `PyJWT` or `python-jose`
- **Interface:**
  ```python
  class JWTService:
      def generate_access_token(self, user: User, admin: Optional[Admin]) -> str: ...
      def verify_token(self, token: str) -> dict: ...
  ```

---

### ❌ Repositories: NEW IMPLEMENTATION REQUIRED
- **Status:** No repository implementations exist
- **Action:** Create all repositories in `auth/persistence/`
- **Required repositories:**
  - `UserRepository`
  - `AdminRepository`
  - `CandidateRepository`
  - `RefreshTokenRepository`
  - `AuthAuditLogRepository`

---

## 6. INVARIANT ENFORCEMENT CHECK

### SRS Invariants

#### INV-1: Email Uniqueness
- **Invariant:** One email → one user account
- **Enforcement Location:** `users.email` UNIQUE constraint + domain validation
- **Implementation:**
  - Database: `CREATE UNIQUE INDEX ON users(LOWER(email))`
  - Domain: `if user_repo.email_exists(email): raise ConflictError(...)`

#### INV-2: User Status Enforcement
- **Invariant:** Inactive/banned users cannot login
- **Enforcement Location:** `auth/domain` - login validation
- **Implementation:**
  ```python
  if user.status != 'active':
      raise AuthenticationError(f"User is {user.status}")
  ```

#### INV-3: Tenant Isolation (NFR-7.1)
- **Invariant:** Admin can only access data from own organization
- **Enforcement Location:** Repository layer + scope enforcement
- **Implementation:**
  - Auth domain: Embed `organization_id` in JWT claims
  - Other modules: Filter queries by `organization_id` from token
  - **NOT enforced in auth/domain** (auth issues tokens, consumers enforce isolation)

#### INV-4: Password Irreversibility
- **Invariant:** Passwords never reversible, never exposed
- **Enforcement Location:** `auth/domain` - hashing on registration, never returned in API
- **Implementation:**
  - Hash with bcrypt (cost 12) before storage
  - Never include in query results or API responses

#### INV-5: Token Expiration
- **Invariant:** Expired tokens always rejected
- **Enforcement Location:** `auth/domain` - JWT validation
- **Implementation:**
  - Check `exp` claim against current time
  - Return `TokenValidationResult(valid=False, error='expired')`

#### INV-6: Refresh Token Immutability After Revocation
- **Invariant:** Revoked tokens cannot be un-revoked
- **Enforcement Location:** `auth/persistence` - no UPDATE on `revoked_at` field
- **Implementation:**
  - Repository methods: `revoke()` sets `revoked_at` (one-way operation)
  - No `unrevoke()` method exists

#### INV-7: Audit Log Immutability
- **Invariant:** Auth events never deleted or modified
- **Enforcement Location:** `auth/persistence` - INSERT only repository
- **Implementation:**
  - `AuthAuditLogRepository`: Only `create()` method, no `update()` or `delete()`

#### INV-8: RBAC Permission Matrix
- **Invariant:** Permissions strictly defined per role
- **Enforcement Location:** `auth/domain/rbac_enforcer.py`
- **Implementation:**
  - Hardcoded permission matrix (superadmin > admin > read_only)
  - `require_permission(context, 'create_templates')` raises `AuthorizationError` if unauthorized

---

## 7. ARCHITECTURAL CONTRACTS

### 7.1 Public Interfaces Exposed by auth/domain

#### AuthService
```python
class AuthService:
    def register_admin(self, command: RegisterAdminCommand) -> UserProfile: ...
    def register_candidate(self, command: RegisterCandidateCommand) -> UserProfile: ...
    def login(self, command: LoginCommand) -> AuthenticationResult: ...
    def refresh_token(self, command: RefreshTokenCommand) -> AuthenticationResult: ...
    def logout(self, command: LogoutCommand) -> None: ...
    def validate_access_token(self, token: str) -> TokenValidationResult: ...
```

#### RBACEnforcer
```python
class RBACEnforcer:
    def has_permission(self, auth_context: IdentityContext, permission: str) -> bool: ...
    def require_permission(self, auth_context: IdentityContext, permission: str) -> None: ...
```

---

### 7.2 Expected Inputs from Other Modules

#### From API Layer
- **Commands:** `RegisterAdminCommand`, `LoginCommand`, etc.
- **Session:** `sqlalchemy.orm.Session` (injected via dependency)

#### From Config Module
- **Settings:** JWT config, password policy, token TTLs

#### From Shared Module
- **Errors:** Exception classes for raising domain errors
- **Logging:** Structured logger for domain events

---

### 7.3 Expected Outputs to Other Modules

#### To API Layer
- **Results:** `AuthenticationResult`, `UserProfile`, `TokenValidationResult`
- **Exceptions:** Raised on validation failures

#### To Middleware
- **JWT Validation:** `TokenValidationResult` with `IdentityContext`

#### To All Protected Endpoints
- **Identity Context:** `IdentityContext` injected into request.state by middleware

---

### 7.4 DTO Contracts (Dataclasses)

#### Commands (Input)
```python
@dataclass
class RegisterAdminCommand:
    email: str
    password: str
    organization_id: int
    admin_role: Literal["admin", "read_only"]
    full_name: Optional[str] = None
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None

@dataclass
class LoginCommand:
    email: str
    password: str
    request_ip: Optional[str] = None
    request_user_agent: Optional[str] = None
    device_info: Optional[str] = None
```

#### Results (Output)
```python
@dataclass
class AuthenticationResult:
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_profile: UserProfile

@dataclass
class UserProfile:
    user_id: int
    email: str
    user_type: Literal["admin", "candidate"]
    user_status: str
    admin_id: Optional[int] = None
    organization_id: Optional[int] = None
    admin_role: Optional[str] = None
    candidate_id: Optional[int] = None
    last_login_at: Optional[datetime] = None

@dataclass
class TokenValidationResult:
    valid: bool
    claims: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    auth_context: Optional[IdentityContext] = None
```

---

## 8. CROSS-MODULE INTEGRATION POINTS

### 8.1 Admin Module (Not Yet Implemented)
**Expected Interface:**
```python
from app.admin.persistence import OrganizationRepository

org_repo = OrganizationRepository(session)
org = org_repo.get_by_id(organization_id)
if not org or org.status != 'active':
    raise OrganizationNotFoundError()
```

**Current Workaround:**
```python
# auth/domain/auth_service.py
def _validate_organization(self, session: Session, org_id: int) -> None:
    """Temporary validation until admin module implemented"""
    result = session.execute(
        "SELECT status FROM organizations WHERE id = :id",
        {"id": org_id}
    ).first()
    
    if not result:
        raise NotFoundError(resource_type="Organization", resource_id=org_id)
    
    if result[0] != 'active':
        raise ValidationError(f"Organization is {result[0]}")
```

---

### 8.2 Interview Module (Not Yet Implemented)
**Integration Point:** Interview endpoints will use `get_identity()` dependency

**Expected Usage:**
```python
# app/interview/api/router.py
from app.bootstrap.dependencies import get_identity

@router.post("/api/interviews")
async def create_interview(
    request: CreateInterviewRequest,
    identity: IdentityContext = Depends(require_admin)
):
    # identity.organization_id used for tenant filtering
    # identity.user_id for created_by tracking
    ...
```

**Auth Module Responsibility:** Ensure `IdentityContext` contains correct claims

---

### 8.3 Shared/Auth_Context Module (Middleware)
**Integration Point:** Auth domain provides JWT validation for middleware

**Expected Flow:**
```
1. Request arrives with Authorization: Bearer <token>
2. IdentityInjectionMiddleware extracts token
3. Middleware calls: TokenValidator.validate(token) [from auth/domain]
4. TokenValidator returns: TokenValidationResult(valid=True, auth_context=...)
5. Middleware injects: request.state.identity = auth_context
6. Endpoint accesses: identity = Depends(get_identity)
```

**Auth Module Responsibility:** Implement `TokenValidator` as public interface

---

## 9. IMPLEMENTATION STRATEGY

### Phase 1: Schema Migrations (Day 1)
1. Create migration files
2. Execute on development database
3. Validate schema with `psql` inspection
4. Update schema.sql documentation

### Phase 2: Persistence Layer (Day 1-2)
1. Create ORM models (User, Admin, Candidate, RefreshToken, AuthAuditLog)
2. Create repository classes
3. Write unit tests for repositories (mock DB)
4. Write integration tests (real DB)

### Phase 3: Domain Services (Day 2-3)
1. Implement PasswordHasher
2. Implement JWTService
3. Implement AuthService (registration, login, logout, refresh, validation)
4. Implement RBACEnforcer
5. Write unit tests (mock repositories)

### Phase 4: Integration (Day 3-4)
1. Create API router (auth/api)
2. Create request/response schemas (auth/contracts)
3. Wire up dependency injection
4. Write integration tests (HTTP endpoints)

### Phase 5: Human Testing (Day 4)
1. Document API endpoints
2. Provide curl examples
3. Create Postman collection
4. Write human testing guide

---

## 10. RISK ASSESSMENT

### ❌ BLOCKER: Missing Organizations Table Validation
- **Risk:** Cannot validate organization_id during admin registration
- **Mitigation:** Temporary SQL query workaround
- **Resolution:** Refactor when admin module implemented

### ⚠️ HIGH: Schema Changes Required
- **Risk:** Database migrations may fail on existing data
- **Mitigation:**
  - Test migrations on development DB first
  - Backfill `user_type` from existing admins/candidates tables
  - Validate data integrity post-migration
- **Resolution:** Careful migration planning + rollback script

### ⚠️ MEDIUM: No Existing Repository Pattern
- **Risk:** May not align with future repository implementations
- **Mitigation:** Follow SQLAlchemy best practices, study ai/llm module patterns
- **Resolution:** Peer review before finalizing

### ✅ LOW: Shared Module Dependencies
- **Risk:** Minimal - shared modules are stable and complete
- **Mitigation:** None needed
- **Resolution:** Direct import and usage

---

## 11. DEFINITION OF DONE

### ✅ Schema Migrations Complete
- [ ] Migration 001: `users` table updated (user_type, last_login_at, token_version)
- [ ] Migration 002: `refresh_tokens` table created
- [ ] Migration 003: `auth_audit_log` table created
- [ ] All migrations tested on development database

### ✅ Persistence Layer Complete
- [ ] ORM models created (User, Admin, Candidate, RefreshToken, AuthAuditLog)
- [ ] Repository classes implemented (User, Admin, Candidate, RefreshToken, AuthAuditLog)
- [ ] Unit tests written (mock DB)
- [ ] Integration tests written (real DB)

### ✅ Domain Layer Complete
- [ ] PasswordHasher implemented (hash, verify, validate_complexity)
- [ ] JWTService implemented (generate_access_token, generate_refresh_token, verify_token)
- [ ] AuthService implemented (register, login, logout, refresh, validate)
- [ ] RBACEnforcer implemented (has_permission, require_permission)
- [ ] Unit tests written (mock repositories)
- [ ] All invariants enforced

### ✅ API Layer Complete
- [ ] Request/response schemas defined (auth/contracts)
- [ ] FastAPI router created (auth/api)
- [ ] Dependency injection wired up
- [ ] Integration tests written (HTTP endpoints)

### ✅ Documentation Complete
- [ ] HUMAN_TESTING_GUIDE.md created
- [ ] API endpoints documented
- [ ] curl examples provided
- [ ] Error responses documented

### ✅ Testing Complete
- [ ] Unit tests: 100% coverage on domain logic
- [ ] Integration tests: All endpoints tested (success + failure paths)
- [ ] Human testing: Manual verification with Postman/curl

---

## 12. DEVIATIONS FROM REQUIREMENTS

### Deviation 1: Organization Validation
- **Requirement:** Use `admin.persistence.OrganizationRepository`
- **Actual:** Direct SQL query in auth/domain
- **Justification:** Admin module not yet implemented
- **Plan:** Refactor when admin module available

### Deviation 2: Candidate Profile Storage
- **Requirement:** Separate columns (full_name, phone, resume_url)
- **Actual:** JSONB `profile_metadata` field
- **Justification:** Existing schema uses JSONB (more flexible)
- **Plan:** No change required (JSONB is acceptable)

### Deviation 3: Admin Status Enum
- **Requirement:** 'active', 'inactive'
- **Actual Schema:** 'active', 'inactive', 'suspended'
- **Justification:** Schema includes 'suspended' (more granular)
- **Plan:** Support all three values (no breaking change)

---

**END OF REPO ALIGNMENT REPORT**

**Status:** ✅ Audit Complete - Ready for Implementation  
**Next Step:** Proceed with schema migrations  
**Approval Required:** Schema migration review
