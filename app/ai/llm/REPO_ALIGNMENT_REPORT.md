# REPO ALIGNMENT REPORT
## AI/LLM Module Implementation

**Date:** February 26, 2026
**Target Module:** `app/ai/llm`
**Architecture:** Modular FastAPI Monolith

---

## 1. EXISTING MODULE INVENTORY

### 1.1 /app/shared (Infrastructure Layer)

#### Purpose
Provides cross-cutting concerns for all modules.

#### Public Interfaces
- `shared/errors/exceptions.py`: Unified exception hierarchy
  - `BaseError`: Foundation class with request_id, metadata, http_status_code
  - Client errors: `AuthenticationError`, `AuthorizationError`, `ValidationError`, `NotFoundError`, `ConflictError`, `RateLimitExceeded`
  - Domain errors: `DomainInvariantViolation`, `ProctoringViolation`
  - External errors: `AIProviderError`, `AIProviderTimeoutError`, `SandboxExecutionError`
  - System errors: `InfrastructureError`, `DatabaseError`, `InternalServerError`

- `shared/observability/logging.py`: Structured logging
  - `StructuredFormatter`: JSON formatter for logs
  - `ContextLogger`: Logger with automatic context injection (request_id, user_id, organization_id)
  - `get_context_logger(name)`: Factory function

- `shared/observability/metrics.py`: Application metrics (Prometheus-compatible)
- `shared/observability/tracing.py`: Request tracing and correlation
- `shared/observability/telemetry.py`: Telemetry collection

- `shared/auth_context/models.py`: Identity models
  - `UserType(Enum)`: ADMIN | CANDIDATE
  - `AdminRole(Enum)`: SUPERADMIN | ADMIN | READ_ONLY
  - `IdentityContext`: Immutable identity for requests
  
- `shared/auth_context/dependencies.py`: FastAPI dependencies
  - `get_identity(request)`: Extract identity from request state
  - `require_admin(request)`: Require admin identity
  - `require_candidate(request)`: Require candidate identity

- `shared/auth_context/middleware.py`: Identity injection middleware
  - `IdentityInjectionMiddleware`: Extract JWT, validate, inject into request.state

#### Dependencies
- External: `fastapi`, `pydantic`, `logging`, `dataclasses`

---

### 1.2 /app/config (Configuration Layer)

#### Purpose
Centralized configuration management with environment-specific defaults.

#### Public Interfaces
- `config/settings.py`: Pydantic settings models
  - `AppSettings`: Core app config (env, debug, app_name, base_url)
  - `DatabaseSettings`: PostgreSQL config (connection pool, timeouts)
  - `RedisSettings`: Redis config (connection, pool, TTLs)
  - `QdrantSettings`: Vector DB config
  - **`LLMSettings`**: LLM provider configuration
    - `default_llm_provider`: openai | anthropic | groq
    - `openai_api_key`, `anthropic_api_key`, `groq_api_key`
    - `embedding_model_url`: Self-hosted embedding service URL
    - `default_embedding_model`: all-mpnet-base-v2
    - `embedding_timeout_seconds`: 30
    - Model routing per use case  - `llm_temperature`, `llm_max_tokens`, `llm_timeout_seconds`
  - `SandboxSettings`: Code execution sandbox config
  - `SecuritySettings`: JWT, password hashing
  - `AudioSettings`: Transcription, analysis
  - `RateLimitSettings`: Rate limiting rules
  - `FeatureFlagsSettings`: Feature toggles
  - `Settings`: Master settings combining all categories
  - `settings`: Global singleton (loaded at startup)

- `config/environments.py`: Environment-specific logic
  - `EnvironmentConfig`: Environment-aware defaults (dev/staging/prod)

- `config/constants.py`: Application constants
- `config/feature_flags.py`: Feature flag resolution
- `config/security.py`: Security utilities

#### Dependencies
- External: `pydantic`, `pydantic_settings`

---

### 1.3 /app/persistence (Data Access Layer)

#### Purpose
Database connection management and base repository patterns.

#### Public Interfaces
- `persistence/postgres/base.py`:
  - `Base`: SQLAlchemy declarative base for all ORM models
  - `import_all_models()`: Register models with metadata
  - `get_table_names()`: List registered tables

- `persistence/postgres/engine.py`:
  - Database engine initialization
  - Connection pool configuration

- `persistence/postgres/session.py`:
  - Session management
  - Transaction handling
  - `get_db()`: FastAPI dependency for DB sessions

- `persistence/postgres/health.py`:
  - Database health checks

#### Repository Pattern
From requirements docs, standard pattern is:

```python
class BaseRepository(Generic[T]):
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model
    
    def get_by_id(self, id: int) -> Optional[T]
    def get_all(self, limit: int, offset: int) -> List[T]
    def create(self, entity: T) -> T
    def delete(self, entity: T) -> None
    def commit() -> None
    def rollback() -> None
```

#### Dependencies
- External: `sqlalchemy`, `psycopg2`
- Internal: `config/settings`

---

### 1.4 /app/bootstrap (Application Bootstrap)

#### Purpose
FastAPI application initialization and lifecycle management.

#### Public Interfaces
- `bootstrap/app.py`:
  - `create_app()`: FastAPI app factory
  - CORS middleware configuration
  - Router registration (TODO: routes not yet implemented)
  - Health check endpoint: `GET /health`

#### Dependencies
- Internal: `config/settings`, `persistence/postgres/engine`
- External: `fastapi`

---

### 1.5 /app/auth (Authentication Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
User authentication, authorization, JWT token management.

#### Expected Interfaces (from REQUIREMENTS.md)
- `auth/domain`: User, Admin, Candidate domain models
- `auth/persistence`: UserRepository with email lookup, password management
- `auth/api`: Login, logout, token refresh endpoints
- `auth/contracts`: Auth request/response DTOs

#### Dependencies
- Internal: `shared/errors`, `shared/observability`, `config/settings`, `persistence/postgres`

---

### 1.6 /app/interview (Interview Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
Interview session management, exchange tracking.

#### Expected Interfaces (from REQUIREMENTS.md)
- `interview/session`: State transitions (pending → in_progress → completed)
- `interview/exchanges`: Exchange creation (immutable after creation)
- `interview/persistence`: SubmissionRepository, ExchangeRepository
- `interview/api`: Interview endpoints

#### Tables (from schema.sql)
- `interview_submissions`
- `interview_exchanges`

---

### 1.7 /app/evaluation (Evaluation Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
AI-assisted evaluation, scoring, rubrics.

#### Expected Interfaces (from REQUIREMENTS.md)
- `evaluation/scoring`: Score calculation
- `evaluation/aggregation`: Dimension score aggregation
- `evaluation/api`: Evaluation endpoints

#### Tables (from schema.sql)
- `evaluations`
- `evaluation_dimension_scores`
- `rubrics`
- `rubric_dimensions`

---

### 1.8 /app/question (Question Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
Question bank management, generation, retrieval.

---

### 1.9 /app/coding (Coding Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
Coding problem management, code execution, test case validation.

#### Tables (from schema.sql)
- `coding_problems`
- `code_submissions`
- `code_execution_results`
- `coding_test_cases`

---

### 1.10 /app/admin (Admin Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
Organization management, template management, admin user management.

---

### 1.11 /app/proctoring (Proctoring Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
Proctoring event detection, risk scoring, anomaly tracking.

---

### 1.12 /app/audio (Audio Module) - NOT IMPLEMENTED

#### Purpose (from requirements)
Audio recording, transcription, silence detection, audio analysis.

---

### 1.13 /app/ai (AI Module) - PARTIALLY DOCUMENTED

#### Current State
- **ai/llm**: REQUIREMENTS.md + TESTING.md only (NOT IMPLEMENTED)
- **ai/prompts**: REQUIREMENTS.md + TESTING.md only (NOT IMPLEMENTED)
- **ai/telemetry**: REQUIREMENTS.md + TESTING.md only (NOT IMPLEMENTED)

#### Purpose
Provider-agnostic LLM abstraction layer.

#### Responsibilities
- **ai/llm**: LLM provider implementations (Groq, Gemini, OpenAI, Anthropic, Self-hosted embeddings)
- **ai/prompts**: Prompt template retrieval, scope resolution, variable interpolation
- **ai/telemetry**: Token tracking, latency measurement, cost estimation

---

## 2. DEPENDENCY GRAPH

### 2.1 ai/llm Module Dependencies

#### Inbound Dependencies (ai/llm DEPENDS ON)
- `shared/errors/exceptions`: 
  - `BaseError`, `AIProviderError`, `AIProviderTimeoutError`, `ValidationError`, `InfrastructureError`
- `shared/observability/logging`:
  - `get_context_logger()`, `ContextLogger`
- `config/settings`:
  - `settings.llm.groq_api_key`
  - `settings.llm.openai_api_key`
  - `settings.llm.anthropic_api_key`
  - `settings.llm.embedding_model_url`
  - `settings.llm.llm_timeout_seconds`
  - `settings.llm.embedding_timeout_seconds`
- `persistence/postgres/base`: (for future ORM models if needed)
- External SDKs:
  - `groq` (Groq Python SDK)
  - `google-generativeai` (Gemini SDK)
  - `openai` (OpenAI SDK)
  - `anthropic` (Anthropic SDK)
  - `httpx` (for self-hosted embedding service)
  - `pydantic` (for DTOs)

#### Outbound Dependencies (MODULES THAT WILL DEPEND ON ai/llm)
- `ai/prompts`: Uses ai/llm providers for prompt execution (NO DIRECT DEPENDENCY - sibling module)
- Parent `ai` module: Factory pattern for provider instantiation
- Future consumers (once implemented):
  - `question/generation`: Question generation AI calls
  - `evaluation/scoring`: AI-assisted evaluation
  - `interview/resume_parser`: Resume parsing
  - `interview/jd_parser`: Job description parsing

#### Critical: NO DIRECT CROSS-DEPENDENCIES
- `ai/llm` MUST NOT import `ai/prompts` or `ai/telemetry`
- `ai/prompts` MUST NOT import `ai/llm` (sibling modules communicate via parent)
- Parent `ai` module orchestrates interactions between llm/prompts/telemetry

---

## 3. SHARED PATTERNS IDENTIFIED

### 3.1 Repository Pattern
**Location:** Documented in `app/interview/persistence/REQUIREMENTS.md`

**Pattern:**
```python
from sqlalchemy.orm import Session
from typing import TypeVar, Generic, Type, Optional, List

T = TypeVar('T')

class BaseRepository(Generic[T]):
    def __init__(self, db: Session, model: Type[T]):
        self.db = db
        self.model = model
    
    def get_by_id(self, id: int) -> Optional[T]
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]
    def create(self, entity: T) -> T
    def delete(self, entity: T) -> None
    def commit(self) -> None
    def rollback(self) -> None
```

**Usage in ai/llm:**
- ai/llm is **stateless infrastructure** - NO repositories needed
- NO ORM models (no owned tables)
- NO database writes

---

### 3.2 Error Handling Pattern
**Location:** `app/shared/errors/exceptions.py`

**Pattern:**
```python
@dataclass
class BaseError(Exception):
    error_code: str
    message: str
    request_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    http_status_code: int = 500
```

**Usage in ai/llm:**
- Define LLM-specific errors inheriting from `BaseError`
- Examples:
  - `LLMTimeoutError` (inherits from `AIProviderTimeoutError`)
  - `LLMRateLimitError` (inherits from `BaseError`, http_status_code=429)
  - `LLMSchemaValidationError` (inherits from `ValidationError`)
  - `LLMProviderError` (inherits from `AIProviderError`)

---

### 3.3 Dependency Injection Pattern
**Location:** `app/shared/auth_context/dependencies.py`, FastAPI patterns

**Pattern:**
```python
from fastapi import Depends, Request

def get_identity(request: Request) -> IdentityContext:
    if not hasattr(request.state, "identity"):
        raise AuthenticationError()
    return request.state.identity

@router.get("/protected")
async def protected_endpoint(identity: IdentityContext = Depends(get_identity)):
    ...
```

**Usage in ai/llm:**
- LLM providers injected via factory pattern
- Configuration injected via `settings` singleton
- NO FastAPI dependencies in domain/core logic (only in API layer if exposed)

---

### 3.4 Structured Logging Pattern
**Location:** `app/shared/observability/logging.py`

**Pattern:**
```python
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)

logger.info(
    "LLM request completed",
    extra={
        "model_id": "gpt-4",
        "latency_ms": 1250,
        "tokens": 450,
        "event_type": "llm.request.completed"
    }
)
```

**Usage in ai/llm:**
- Use `get_context_logger(__name__)` in every module
- Log domain events only (not implementation details)
- Include telemetry data in log metadata

---

### 3.5 Pydantic Settings Pattern
**Location:** `app/config/settings.py`

**Pattern:**
```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class ModuleSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env" if not testing else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    some_setting: str = Field(..., env="SOME_SETTING")
```

**Usage in ai/llm:**
- LLM configuration already exists in `LLMSettings` class
- Access via `settings.llm.groq_api_key`, etc.
- NO new settings classes needed (reuse existing)

---

### 3.6 FastAPI Router Pattern
**Location:** `app/bootstrap/app.py` (documented, not fully implemented)

**Pattern:**
```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/module", tags=["module"])

@router.post("/endpoint")
async def endpoint(
    payload: RequestDTO,
    identity: IdentityContext = Depends(get_identity),
    db: Session = Depends(get_db)
):
    ...
    return ResponseDTO(...)
```

**Usage in ai/llm:**
- **ai/llm SHOULD NOT expose API endpoints**
- ai/llm is infrastructure layer (consumed by other modules)
- NO `ai/api` submodule needed for llm
- If internal testing endpoints needed, mark as `include_in_schema=False`

---

### 3.7 Contract (DTO) Pattern
**Location:** Inferred from REQUIREMENTS.md files

**Pattern:**
```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RequestContract(BaseModel):
    """Request DTO with validation"""
    field: str = Field(..., description="Required field")
    optional_field: Optional[int] = Field(None, description="Optional field")
    
    class Config:
        json_schema_extra = {
            "example": {"field": "value", "optional_field": 42}
        }

class ResponseContract(BaseModel):
    """Response DTO"""
    result: str
    metadata: dict
```

**Usage in ai/llm:**
- Define contracts for all provider interfaces:
  - `LLMRequest`, `LLMResponse`
  - `EmbeddingRequest`, `EmbeddingResponse`
  - `TranscriptionRequest`, `TranscriptionResponse`
  - `TelemetryData`
  - `LLMError`

---

## 4. SCHEMA ALIGNMENT

### 4.1 Relevant Tables for ai/llm

#### prompt_templates (READ-ONLY)
```sql
CREATE TABLE prompt_templates (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    prompt_type TEXT NOT NULL,  -- 'question_generation', 'evaluation', etc.
    scope template_scope NOT NULL,  -- 'public', 'organization', 'private'
    organization_id BIGINT REFERENCES organizations(id),
    system_prompt TEXT NOT NULL,
    user_prompt TEXT NOT NULL,
    model_id BIGINT,
    model_config JSONB NOT NULL,
    version INTEGER DEFAULT 1 NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    UNIQUE(name, version, organization_id)
);
```

**Usage in ai/llm:**
- **NO DIRECT ACCESS** from ai/llm module
- `ai/prompts` module (sibling) handles prompt retrieval
- ai/llm receives rendered prompts as strings (no DB dependency)

#### Relevant Enums
```sql
CREATE TYPE template_scope AS ENUM ('public', 'organization', 'private');
```

**Usage in ai/llm:**
- ai/llm does NOT use enums directly (scope resolution is prompts layer concern)

### 4.2 Schema Changes Required

**NONE**

ai/llm module is **stateless infrastructure**:
- NO new tables needed
- NO schema modifications required
- NO ORM models to define
- Telemetry data written to JSON fields in consuming modules (handled by caller)

---

## 5. ARCHITECTURAL CONSTRAINTS

### 5.1 Module Isolation Rules

✅ **ALLOWED:**
- Import from `shared/errors`, `shared/observability`, `config`
- Import from `persistence/postgres/base` (if ORM models needed)
- Import external SDKs (`groq`, `openai`, `anthropic`, `httpx`)
- Use Pydantic for DTOs

❌ **FORBIDDEN:**
- Import from sibling modules (`ai/prompts`, `ai/telemetry`)
- Import from domain modules (`interview`, `evaluation`, `question`, `coding`, `admin`)
- Direct database writes
- Direct access to `prompt_templates` table
- Caching AI responses in database
- Exposing provider-specific types in public API
- Bypassing error wrapping (all provider errors MUST be wrapped in LLMError)

### 5.2 Dependency Injection Rules

✅ **ALLOWED:**
- Provider factory pattern (caller requests provider by name)
- Settings injection via `settings` singleton
- Logger injection via `get_context_logger(__name__)`

❌ **FORBIDDEN:**
- FastAPI `Depends()` in core logic (only in API layer)
- Database session injection (ai/llm is stateless)
- Request-scoped dependencies in provider implementations

### 5.3 Error Propagation Rules

✅ **REQUIRED:**
- Wrap ALL provider exceptions in `LLMError`
- Include request_id in all errors (for tracing)
- Record telemetry even on failure
- Use appropriate http_status_code (502 for provider errors, 504 for timeouts, 422 for validation)

❌ **FORBIDDEN:**
- Raising provider-specific exceptions to caller
- Returning `None` on failure (use explicit error in response)
- Silencing errors without logging

### 5.4 Telemetry Recording Rules

✅ **REQUIRED:**
- Measure latency for EVERY provider call
- Count tokens for EVERY completion (prompt + completion)
- Record model_id, provider, retry_count
- Return telemetry data to caller (caller persists it)
- Telemetry collection MUST NOT block API operation

❌ **FORBIDDEN:**
- Writing telemetry directly to database tables
- Skipping telemetry on failure
- Hardcoding cost estimates (use configurable pricing table)

---

## 6. IMPLEMENTATION CHECKLIST

### 6.1 File Structure

```
app/ai/llm/
├── __init__.py                    # Public API exports
├── REQUIREMENTS.md                # ✅ Exists
├── TESTING.md                     # ✅ Exists
├── REPO_ALIGNMENT_REPORT.md       # ✅ This file
├── HUMAN_TESTING_GUIDE.md         # ⬜ To create
├── contracts.py                   # ⬜ To create: DTOs (LLMRequest, LLMResponse, etc.)
├── errors.py                      # ⬜ To create: LLM-specific errors
├── base_provider.py               # ⬜ To create: Abstract provider interface
├── provider_factory.py            # ⬜ To create: Provider instantiation
├── providers/
│   ├── __init__.py
│   ├── groq_provider.py           # ⬜ To create
│   ├── gemini_provider.py         # ⬜ To create
│   ├── openai_provider.py         # ⬜ To create
│   ├── anthropic_provider.py      # ⬜ To create
│   └── embedding_provider.py      # ⬜ To create (self-hosted)
├── formatters/
│   ├── __init__.py
│   ├── groq_formatter.py          # ⬜ To create
│   ├── gemini_formatter.py        # ⬜ To create
│   ├── openai_formatter.py        # ⬜ To create
│   └── anthropic_formatter.py     # ⬜ To create
└── utils/
    ├── __init__.py
    ├── timeout.py                 # ⬜ To create: Timeout enforcement
    └── token_counter.py           # ⬜ To create: Token estimation

tests/unit/ai/llm/
├── __init__.py
├── test_groq_provider.py
├── test_gemini_provider.py
├── test_openai_provider.py
├── test_anthropic_provider.py
├── test_embedding_provider.py
├── test_provider_factory.py
└── test_errors.py

tests/integration/ai/llm/
├── __init__.py
├── test_groq_integration.py       # Requires GROQ_API_KEY
├── test_gemini_integration.py     # Requires GEMINI_API_KEY
├── test_openai_integration.py     # Requires OPENAI_API_KEY
└── test_anthropic_integration.py  # Requires ANTHROPIC_API_KEY
```

### 6.2 Implementation Order

1. ✅ **Contracts** (`contracts.py`)
   - `LLMRequest`, `LLMResponse`, `TelemetryData`, `LLMError`

2. ✅ **Errors** (`errors.py`)
   - LLM-specific error classes inheriting from shared exceptions

3. ✅ **Base Provider** (`base_provider.py`)
   - Abstract interface with `@abstractmethod`

4. ✅ **Utilities** (`utils/timeout.py`, `utils/token_counter.py`)

5. ✅ **Provider Implementations**
   - Start with Groq (primary for development)
   - Then Gemini, OpenAI, Anthropic
   - Self-hosted embedding provider

6. ✅ **Response Formatters**
   - Provider-specific response normalization

7. ✅ **Provider Factory** (`provider_factory.py`)
   - Instantiate providers by name
   - Load API keys from settings

8. ✅ **Tests** (unit → integration)

9. ✅ **Human Testing Guide**

### 6.3 Validation Checklist

- [ ] Zero imports from sibling modules (`ai/prompts`, `ai/telemetry`)
- [ ] Zero imports from domain modules
- [ ] All provider exceptions wrapped in `LLMError`
- [ ] Telemetry recorded on success AND failure
- [ ] Timeout enforced at HTTP client level (not just SDK)
- [ ] All providers implement `BaseLLMProvider` interface
- [ ] Provider-specific responses stored in `raw_response` field
- [ ] Settings accessed via `settings.llm.*`
- [ ] Logging via `get_context_logger(__name__)`
- [ ] Schema validation for structured outputs
- [ ] Thread-safe HTTP clients
- [ ] Retry logic with exponential backoff
- [ ] Cost estimation (optional, configurable)

---

## 7. RISKS & MITIGATIONS

### Risk 1: Provider SDK Breaking Changes
**Mitigation:** Wrap SDK calls in adapter layer, test against mocked responses

### Risk 2: Token Counting Discrepancies
**Mitigation:** Always use provider-reported tokens; log discrepancies for monitoring

### Risk 3: Timeout Not Enforced
**Mitigation:** Use `httpx.Timeout` or `requests.timeout` at HTTP client level (not just SDK)

### Risk 4: Circular Dependencies
**Mitigation:** ai/llm is leaf module (no imports from sibling/domain modules)

### Risk 5: Secret Leakage in Logs
**Mitigation:** Never log API keys, redact in structured logs

---

## 8. APPROVAL CHECKLIST

- [x] All existing modules enumerated
- [x] Dependency graph documented
- [x] Shared patterns identified (repository, error, DI, logging, settings, DTO)
- [x] Schema alignment confirmed (NO schema changes needed)
- [x] Architectural constraints documented
- [x] Implementation checklist defined
- [x] Risks identified with mitigations

---

**REPO ALIGNMENT STATUS:** ✅ **COMPLETE**

Implementation may proceed following strict adherence to:
1. Zero assumption rule (reuse existing patterns)
2. Module isolation (no cross-imports)
3. Error wrapping (all provider errors → LLMError)
4. Telemetry guarantee (record even on failure)
5. Stateless design (no database writes)
