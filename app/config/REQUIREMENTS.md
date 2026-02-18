# Config Module - Centralized Configuration Management

## 1. Purpose

**Why this module exists:**

The Config module is the **deterministic runtime brain** of the system. It:

- Loads and validates environment configuration
- Manages feature flags
- Defines global system constants
- Centralizes security policies
- Enforces environment-specific behavior
- Provides runtime thresholds and limits

**Critical responsibility:** This is the **single source of runtime configuration truth**. Every threshold, limit, model name, and feature toggle MUST originate here. No magic numbers scattered across codebase.

**Architectural philosophy:**

> **All configuration flows through this module.**
> **No direct `os.environ` access outside config.**
> **Fail fast on misconfiguration.**
> **Immutable after startup.**

---

## 2. Owned Tables / Entities

**None.** Config module owns no database tables. It is pure configuration loading and validation.

---

## 3. Module Structure

```
config/
├── settings.py          # Core application settings (Pydantic BaseSettings)
├── feature_flags.py     # Runtime feature toggles
├── constants.py         # Domain-safe immutable constants
├── security.py          # Security policies and rules
└── environments.py      # Environment-specific behavior (dev/staging/prod)
```

---

## 4. Configuration Categories

### Application Core Settings

**Required Environment Variables:**

```bash
# Application
APP_ENV=prod  # dev, staging, prod
DEBUG=false
APP_NAME="AI Interviewer API"
API_VERSION=1.0.0
BASE_URL=https://api.example.com
```

**Validation:**

- `APP_ENV` MUST be defined (no default)
- If `APP_ENV=prod`, `DEBUG` MUST be `false`
- `BASE_URL` MUST use HTTPS in prod

**Pydantic Schema:**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class AppSettings(BaseSettings):
    app_env: Literal["dev", "staging", "prod"]
    debug: bool = False
    app_name: str = "AI Interviewer API"
    api_version: str = "1.0.0"
    base_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    @model_validator(mode='after')
    def validate_production_settings(self):
        if self.app_env == "prod":
            if self.debug:
                raise ValueError("DEBUG must be False in production")
            if not self.base_url.startswith("https://"):
                raise ValueError("BASE_URL must use HTTPS in production")
        return self
```

---

### Database Configuration (Hosted Postgres)

**Required Environment Variables:**

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname?ssl=require
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600
DB_ECHO=false  # SQL logging (dev only)
```

**Validation:**

- `DATABASE_URL` MUST be valid PostgreSQL connection string
- In prod: URL MUST include `ssl=require` or `sslmode=require`
- `DB_POOL_SIZE` MUST be > 0
- `DB_POOL_TIMEOUT` MUST be > 0

**Schema:**

```python
class DatabaseSettings(BaseSettings):
    database_url: PostgresDsn
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600
    db_echo: bool = False

    @model_validator(mode='after')
    def validate_ssl_in_prod(self):
        if self.app_env == "prod":
            if "ssl" not in str(self.database_url) and "sslmode" not in str(self.database_url):
                raise ValueError("Database must use SSL in production")
        return self
```

---

### Redis Configuration

**Required Environment Variables:**

```bash
REDIS_URL=redis://localhost:6379
REDIS_DB=0
REDIS_SESSION_TTL=3600  # 1 hour
REDIS_PASSWORD=
```

**Used By:**

- Interview session state (WebSocket connections)
- Rate limiting
- Celery task queue
- Cache layer

**Schema:**

```python
class RedisSettings(BaseSettings):
    redis_url: RedisDsn
    redis_db: int = 0
    redis_session_ttl: int = 3600
    redis_password: Optional[str] = None
```

---

### Qdrant Configuration (Vector Database)

**Required Environment Variables:**

```bash
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=interview_questions
QDRANT_EMBEDDING_DIM=768  # Self-hosted all-mpnet-base-v2 (default)
```

**Note:** Embedding dimension must match the model specified in `DEFAULT_EMBEDDING_MODEL`.
Supported dimensions: 768 (all-mpnet-base-v2), 1536 (OpenAI ada-002), 3072 (OpenAI large).

**Environment Separation:**

- Dev: `interview_questions_dev`
- Staging: `interview_questions_staging`
- Prod: `interview_questions_prod`

**Schema:**

```python
class QdrantSettings(BaseSettings):
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection_name: str = "interview_questions"
    qdrant_embedding_dim: int = 1536

    @property
    def collection_name_with_env(self) -> str:
        """Return collection name with environment suffix"""
        if self.app_env == "dev":
            return f"{self.qdrant_collection_name}_dev"
        elif self.app_env == "staging":
            return f"{self.qdrant_collection_name}_staging"
        return self.qdrant_collection_name
```

---

### LLM Provider Configuration

**Required Environment Variables:**

```bash
# Default Provider
DEFAULT_LLM_PROVIDER=openai  # openai, anthropic

# API Keys
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Model Routing by Use Case
LLM_MODEL_QUESTION_GENERATION=gpt-4
LLM_MODEL_EVALUATION=gpt-4-turbo
LLM_MODEL_RESUME_PARSING=gpt-3.5-turbo
LLM_MODEL_REPORT_GENERATION=gpt-4

# Model Parameters
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
LLM_TIMEOUT_SECONDS=30
```

**Validation:**

- If `DEFAULT_LLM_PROVIDER=openai`, `OPENAI_API_KEY` MUST be set
- If `DEFAULT_LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY` MUST be set

**Schema:**

```python
class LLMSettings(BaseSettings):
    default_llm_provider: Literal["openai", "anthropic"] = "openai"

    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Model routing
    llm_model_question_generation: str = "gpt-4"
    llm_model_evaluation: str = "gpt-4-turbo"
    llm_model_resume_parsing: str = "gpt-3.5-turbo"
    llm_model_report_generation: str = "gpt-4"

    # Parameters
    llm_temperature: float = 0.7
    llm_max_tokens: int = 2000
    llm_timeout_seconds: int = 30

    @model_validator(mode='after')
    def validate_api_keys(self):
        if self.default_llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY required when DEFAULT_LLM_PROVIDER=openai")
        if self.default_llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY required when DEFAULT_LLM_PROVIDER=anthropic")
        return self
```

---

### Sandbox Execution Configuration

**Required Environment Variables:**

```bash
# Docker Images
SANDBOX_IMAGE_CPP=code-sandbox-cpp:latest
SANDBOX_IMAGE_JAVA=code-sandbox-java:latest
SANDBOX_IMAGE_PYTHON=code-sandbox-python:latest

# Resource Limits
SANDBOX_TIME_LIMIT_MS=2000
SANDBOX_MEMORY_LIMIT_KB=262144  # 256MB
SANDBOX_PROCESS_LIMIT=1
SANDBOX_MAX_OUTPUT_SIZE=1048576  # 1MB

# Security
SANDBOX_NETWORK_DISABLED=true
SANDBOX_SECCOMP_PROFILE=/etc/docker/seccomp-sandbox.json
```

**Critical:** These limits MUST match what's enforced in sandbox module.

**Schema:**

```python
class SandboxSettings(BaseSettings):
    sandbox_image_cpp: str = "code-sandbox-cpp:latest"
    sandbox_image_java: str = "code-sandbox-java:latest"
    sandbox_image_python: str = "code-sandbox-python:latest"

    sandbox_time_limit_ms: int = 2000
    sandbox_memory_limit_kb: int = 262144
    sandbox_process_limit: int = 1
    sandbox_max_output_size: int = 1048576

    sandbox_network_disabled: bool = True
    sandbox_seccomp_profile: Optional[str] = None

    @model_validator(mode='after')
    def validate_resource_limits(self):
        if self.sandbox_time_limit_ms < 100:
            raise ValueError("SANDBOX_TIME_LIMIT_MS must be >= 100ms")
        if self.sandbox_memory_limit_kb < 4096:
            raise ValueError("SANDBOX_MEMORY_LIMIT_KB must be >= 4MB")
        return self
```

---

### JWT & Security Configuration

**Required Environment Variables:**

```bash
# JWT
JWT_ALGORITHM=RS256
JWT_PUBLIC_KEY_PATH=/path/to/public.pem
JWT_PRIVATE_KEY_PATH=/path/to/private.pem
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30

# Password Hashing
PASSWORD_HASH_ALGORITHM=bcrypt
PASSWORD_HASH_ROUNDS=12

# Security Headers
ENABLE_SECURE_HEADERS=true
ALLOWED_HOSTS=["api.example.com"]
```

**Validation:**

- If `JWT_ALGORITHM=RS256`, both key paths MUST be provided
- In prod: `ACCESS_TOKEN_EXPIRE_MINUTES` <= 30
- `PASSWORD_HASH_ROUNDS` >= 10

**Schema:**

```python
class SecuritySettings(BaseSettings):
    jwt_algorithm: Literal["RS256", "HS256"] = "RS256"
    jwt_public_key_path: Optional[str] = None
    jwt_private_key_path: Optional[str] = None
    jwt_secret_key: Optional[str] = None  # For HS256 only

    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    password_hash_algorithm: Literal["bcrypt", "argon2id"] = "bcrypt"
    password_hash_rounds: int = 12

    enable_secure_headers: bool = True
    allowed_hosts: List[str] = []

    @model_validator(mode='after')
    def validate_jwt_config(self):
        if self.jwt_algorithm == "RS256":
            if not self.jwt_public_key_path or not self.jwt_private_key_path:
                raise ValueError("JWT key paths required for RS256")
        if self.jwt_algorithm == "HS256":
            if not self.jwt_secret_key:
                raise ValueError("JWT_SECRET_KEY required for HS256")
            if self.app_env == "prod" and len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 chars in prod")
        return self
```

---

### Audio Processing Configuration

**Required Environment Variables:**

```bash
# Silence Detection
SILENCE_THRESHOLD_MS=3000  # 3 seconds
SILENCE_CONFIDENCE_THRESHOLD=0.8

# Transcription
AUDIO_TRANSCRIPTION_PROVIDER=whisper  # whisper, google, azure
AUDIO_CONFIDENCE_THRESHOLD=0.7
MAX_TRANSCRIPT_LENGTH=10000

# Analysis
ENABLE_AUDIO_ANALYSIS=true
AUDIO_CHUNK_SIZE_MS=500
```

**Critical:** `SILENCE_THRESHOLD_MS` is the "3-second pause" detection threshold mentioned in audio module.

**Schema:**

```python
class AudioSettings(BaseSettings):
    silence_threshold_ms: int = 3000
    silence_confidence_threshold: float = 0.8

    audio_transcription_provider: Literal["whisper", "google", "azure"] = "whisper"
    audio_confidence_threshold: float = 0.7
    max_transcript_length: int = 10000

    enable_audio_analysis: bool = True
    audio_chunk_size_ms: int = 500
```

---

### Rate Limiting Configuration

**Required Environment Variables:**

```bash
# Login Rate Limiting
LOGIN_RATE_LIMIT=5  # Attempts per window
LOGIN_RATE_WINDOW_SECONDS=900  # 15 minutes

# API Rate Limiting
API_RATE_LIMIT=100  # Requests per window
API_RATE_WINDOW_SECONDS=60  # 1 minute

# Resource Limits
MAX_CONCURRENT_INTERVIEWS_PER_CANDIDATE=1
MAX_CODE_SUBMISSIONS_PER_MINUTE=5
```

**Schema:**

```python
class RateLimitSettings(BaseSettings):
    login_rate_limit: int = 5
    login_rate_window_seconds: int = 900

    api_rate_limit: int = 100
    api_rate_window_seconds: int = 60

    max_concurrent_interviews_per_candidate: int = 1
    max_code_submissions_per_minute: int = 5
```

---

### Feature Flags Configuration

**Required Environment Variables:**

```bash
# Core Features
ENABLE_AI_EVALUATION=true
ENABLE_PROCTORING=true
ENABLE_AUDIO_ANALYSIS=true
ENABLE_CODE_EXECUTION=true

# Optional Features
ENABLE_PRACTICE_MODE=false
ENABLE_HUMAN_OVERRIDE=true
ENABLE_RESUME_PARSING=true
```

**Schema:**

```python
class FeatureFlagsSettings(BaseSettings):
    # Core features
    enable_ai_evaluation: bool = True
    enable_proctoring: bool = True
    enable_audio_analysis: bool = True
    enable_code_execution: bool = True

    # Optional features
    enable_practice_mode: bool = False
    enable_human_override: bool = True
    enable_resume_parsing: bool = True
```

---

## 5. Acceptance Criteria

### Configuration Loading

**Must:**

1. Load all environment variables at startup
2. Validate all required variables present
3. Validate all value constraints (types, ranges, formats)
4. Fail fast with clear error message if validation fails
5. Make configuration immutable after loading

**Example:**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Master settings object"""
    app: AppSettings
    database: DatabaseSettings
    redis: RedisSettings
    qdrant: QdrantSettings
    llm: LLMSettings
    sandbox: SandboxSettings
    security: SecuritySettings
    audio: AudioSettings
    rate_limit: RateLimitSettings
    feature_flags: FeatureFlagsSettings

    @classmethod
    def load(cls) -> "Settings":
        """Load and validate all settings at startup"""
        try:
            settings = cls(
                app=AppSettings(),
                database=DatabaseSettings(),
                redis=RedisSettings(),
                qdrant=QdrantSettings(),
                llm=LLMSettings(),
                sandbox=SandboxSettings(),
                security=SecuritySettings(),
                audio=AudioSettings(),
                rate_limit=RateLimitSettings(),
                feature_flags=FeatureFlagsSettings()
            )
            return settings
        except ValidationError as e:
            logger.critical(f"Configuration validation failed: {e}")
            raise SystemExit(1)

# Global singleton
settings = Settings.load()
```

---

### Feature Flags

**Must provide:**

- Boolean flags for runtime feature toggling
- Environment-specific flag overrides
- Centralized access (no scattered string checks)

**Example:**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class FeatureFlags:
    """Immutable feature flags"""
    ENABLE_AI_EVALUATION: bool
    ENABLE_PROCTORING: bool
    ENABLE_AUDIO_ANALYSIS: bool
    ENABLE_CODE_EXECUTION: bool
    ENABLE_PRACTICE_MODE: bool
    ENABLE_HUMAN_OVERRIDE: bool
    ENABLE_RESUME_PARSING: bool

    @classmethod
    def from_settings(cls, settings: FeatureFlagsSettings) -> "FeatureFlags":
        return cls(
            ENABLE_AI_EVALUATION=settings.enable_ai_evaluation,
            ENABLE_PROCTORING=settings.enable_proctoring,
            ENABLE_AUDIO_ANALYSIS=settings.enable_audio_analysis,
            ENABLE_CODE_EXECUTION=settings.enable_code_execution,
            ENABLE_PRACTICE_MODE=settings.enable_practice_mode,
            ENABLE_HUMAN_OVERRIDE=settings.enable_human_override,
            ENABLE_RESUME_PARSING=settings.enable_resume_parsing
        )

# Global singleton
feature_flags = FeatureFlags.from_settings(settings.feature_flags)
```

**Usage in code:**

```python
from app.config import feature_flags

if feature_flags.ENABLE_AI_EVALUATION:
    await evaluate_with_ai(submission)
else:
    await evaluate_with_rubric(submission)
```

---

### Constants

**Must provide:**

- Immutable domain constants
- No magic numbers in business logic
- Type-safe constant access

**Example:**

```python
from typing import Final

# Code Execution
SUPPORTED_LANGUAGES: Final[list[str]] = ["cpp", "java", "python3"]
MAX_CODE_SIZE_BYTES: Final[int] = 100_000
MAX_TEST_CASE_INPUT_SIZE_BYTES: Final[int] = 10_485_760  # 10MB

# Interview
MAX_QUESTION_LENGTH: Final[int] = 10_000
MAX_ANSWER_LENGTH: Final[int] = 50_000
MAX_EXCHANGES_PER_INTERVIEW: Final[int] = 50

# Evaluation
MIN_EVALUATION_SCORE: Final[float] = 0.0
MAX_EVALUATION_SCORE: Final[float] = 100.0
DEFAULT_RUBRIC_WEIGHT: Final[int] = 1

# Audio
AUDIO_SAMPLE_RATE: Final[int] = 16000
AUDIO_CHANNELS: Final[int] = 1
MAX_AUDIO_CHUNK_SIZE_BYTES: Final[int] = 1_048_576  # 1MB

# Status Values
INTERVIEW_STATUS_VALUES: Final[list[str]] = [
    "scheduled", "in_progress", "completed", "cancelled"
]
SUBMISSION_STATUS_VALUES: Final[list[str]] = [
    "pending", "running", "passed", "failed", "error", "timeout", "memory_exceeded"
]
```

---

### Security Configuration

**Must provide:**

- CORS policy
- Secure cookie settings
- HTTPS enforcement
- Password complexity rules

**Example:**

```python
from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class SecurityConfig:
    """Security policies"""

    # CORS
    cors_origins: List[str]
    cors_allow_credentials: bool
    cors_max_age: int

    # Cookies
    cookie_secure: bool  # True in prod
    cookie_httponly: bool
    cookie_samesite: str  # "lax" or "strict"

    # HTTPS
    enforce_https: bool

    # Headers
    enable_security_headers: bool

    # Password
    min_password_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_special_char: bool

    @classmethod
    def from_settings(cls, settings: SecuritySettings, app_env: str) -> "SecurityConfig":
        return cls(
            cors_origins=settings.allowed_hosts,
            cors_allow_credentials=True,
            cors_max_age=3600,
            cookie_secure=(app_env == "prod"),
            cookie_httponly=True,
            cookie_samesite="lax",
            enforce_https=(app_env == "prod"),
            enable_security_headers=settings.enable_secure_headers,
            min_password_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special_char=True
        )

security_config = SecurityConfig.from_settings(settings.security, settings.app.app_env)
```

---

### Environment-Specific Behavior

**Must provide:**

- Clear separation between dev/staging/prod
- Environment-aware defaults
- Validation of environment-specific requirements

**Example:**

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class EnvironmentConfig:
    """Environment-specific configuration"""
    env: str  # dev, staging, prod
    is_dev: bool
    is_staging: bool
    is_prod: bool

    # Environment-specific settings
    enable_openapi: bool  # Disable in prod
    enable_debug_logging: bool
    strict_cors: bool
    require_ssl: bool
    allow_insecure_transport: bool

    @classmethod
    def from_app_env(cls, app_env: str) -> "EnvironmentConfig":
        is_dev = app_env == "dev"
        is_staging = app_env == "staging"
        is_prod = app_env == "prod"

        return cls(
            env=app_env,
            is_dev=is_dev,
            is_staging=is_staging,
            is_prod=is_prod,
            enable_openapi=(not is_prod),
            enable_debug_logging=is_dev,
            strict_cors=is_prod,
            require_ssl=is_prod,
            allow_insecure_transport=is_dev
        )

env_config = EnvironmentConfig.from_app_env(settings.app.app_env)
```

---

## 6. Invariants & Constraints

### Must Hold

1. **Configuration Immutability:** Settings NEVER change after startup
2. **Fail Fast:** Invalid configuration crashes app at startup (not at runtime)
3. **Single Source of Truth:** No `os.environ` access outside config module
4. **Type Safety:** All config values have explicit types
5. **Environment Validation:** Prod config validated more strictly than dev
6. **No Magic Numbers:** All thresholds/limits defined in config or constants

### Forbidden

- MUST NOT read `os.environ` directly outside config module
- MUST NOT use hardcoded magic numbers in business logic
- MUST NOT have different config behavior based on runtime conditions (only startup)
- MUST NOT log sensitive values (API keys, passwords, tokens)
- MUST NOT allow weak defaults in production (e.g., default secret key)
- MUST NOT scatter feature flag checks (centralize in feature_flags object)

---

## 7. Dependent Modules

### Upstream (Callers)

**All modules** depend on config:

- bootstrap (app initialization)
- auth (JWT settings)
- coding (sandbox limits)
- audio (silence thresholds)
- evaluation (LLM model routing)
- interview (concurrency limits)

### Downstream (Dependencies)

- **Pydantic:** Settings validation
- **dotenv:** .env file loading
- **Python typing:** Type safety

---

## 8. Sensitive Configuration Handling

### Secrets Management

**Must:**

- Never log secrets
- Mask secrets in error messages
- Support environment variable injection
- Support secret manager integration (future)

**Example:**

```python
class Settings(BaseSettings):
    openai_api_key: str

    def __repr__(self):
        """Mask secrets in repr"""
        return f"Settings(openai_api_key='****')"

    def model_dump(self, **kwargs):
        """Mask secrets in dict representation"""
        data = super().model_dump(**kwargs)
        if "openai_api_key" in data:
            data["openai_api_key"] = "****"
        return data
```

**Logging:**

```python
# GOOD
logger.info(f"Using LLM provider: {settings.llm.default_llm_provider}")

# BAD - leaks API key
logger.info(f"API key: {settings.llm.openai_api_key}")
```

---

## 9. Edge Cases to Handle

### 1. Missing Required Environment Variable

**Scenario:** `DATABASE_URL` not set.

**Handling:**

- Pydantic raises `ValidationError`
- Application crashes with clear error message
- Error includes variable name and requirement

---

### 2. Invalid Database URL Format

**Scenario:** `DATABASE_URL=invalid-url`

**Handling:**

- Pydantic `PostgresDsn` validator fails
- Application crashes with format error
- Example valid URL shown in error

---

### 3. Prod Config with Debug Enabled

**Scenario:** `APP_ENV=prod`, `DEBUG=true`

**Handling:**

- `@model_validator` catches contradiction
- Application crashes: "DEBUG must be False in production"

---

### 4. JWT Algorithm Mismatch

**Scenario:** `JWT_ALGORITHM=RS256` but no key paths provided.

**Handling:**

- Validator raises error: "JWT key paths required for RS256"
- Application crashes before any tokens generated

---

### 5. Sandbox Resource Limit Too Low

**Scenario:** `SANDBOX_MEMORY_LIMIT_KB=100`

**Handling:**

- Validator raises error: "Memory limit must be >= 4MB"
- Prevents impossible execution

---

### 6. Conflicting Feature Flags

**Scenario:** `ENABLE_AI_EVALUATION=false` but `LLM_MODEL_EVALUATION` set.

**Handling:**

- Validator warns (not fatal)
- AI evaluation disabled, model setting ignored

---

### 7. Environment Suffix on Collection Name

**Scenario:** Dev environment using prod Qdrant collection.

**Handling:**

- Config automatically appends `_dev` suffix
- `interview_questions_dev` used instead of `interview_questions`
- Prevents dev data pollution in prod

---

## 10. Configuration Validation Examples

### Startup Validation Flow

```python
# main.py or app initialization
from app.config import settings, feature_flags, env_config

def initialize_app():
    # Settings already validated at import time
    logger.info(f"Starting app in {settings.app.app_env} environment")
    logger.info(f"Debug mode: {settings.app.debug}")
    logger.info(f"AI Evaluation: {feature_flags.ENABLE_AI_EVALUATION}")

    # Validate connectivity to external services
    await validate_db_connection(settings.database.database_url)
    await validate_redis_connection(settings.redis.redis_url)
    await validate_qdrant_connection(settings.qdrant.qdrant_url)

    logger.info("Configuration validated successfully")
```

---

## 11. Testing Requirements

**Must test:**

### Configuration Validation Tests

1. **Missing Required Variable:**

   ```python
   def test_missing_database_url():
       with pytest.raises(ValidationError, match="DATABASE_URL"):
           Settings()
   ```

2. **Invalid URL Format:**

   ```python
   def test_invalid_database_url():
       os.environ["DATABASE_URL"] = "not-a-url"
       with pytest.raises(ValidationError, match="invalid URL"):
           DatabaseSettings()
   ```

3. **Prod Config Validation:**

   ```python
   def test_prod_requires_https():
       os.environ["APP_ENV"] = "prod"
       os.environ["BASE_URL"] = "http://insecure.com"
       with pytest.raises(ValidationError, match="HTTPS"):
           AppSettings()
   ```

4. **JWT Config Validation:**

   ```python
   def test_rs256_requires_keys():
       os.environ["JWT_ALGORITHM"] = "RS256"
       with pytest.raises(ValidationError, match="key paths required"):
           SecuritySettings()
   ```

5. **Sandbox Resource Limits:**
   ```python
   def test_sandbox_memory_minimum():
       os.environ["SANDBOX_MEMORY_LIMIT_KB"] = "100"
       with pytest.raises(ValidationError, match="must be >= 4MB"):
           SandboxSettings()
   ```

### Feature Flag Tests

1. **Flag Access:**

   ```python
   def test_feature_flag_access():
       assert isinstance(feature_flags.ENABLE_AI_EVALUATION, bool)
   ```

2. **Flag Immutability:**
   ```python
   def test_feature_flags_immutable():
       with pytest.raises(FrozenInstanceError):
           feature_flags.ENABLE_AI_EVALUATION = False
   ```

### Constants Tests

1. **Constant Immutability:**
   ```python
   def test_constants_immutable():
       with pytest.raises(TypeError):
           SUPPORTED_LANGUAGES.append("rust")
   ```

---

## 12. Configuration

### Environment Variable Files

**Dev (.env.dev):**

```bash
APP_ENV=dev
DEBUG=true
BASE_URL=http://localhost:8000

DATABASE_URL=postgresql+asyncpg://user:pass@localhost/ai_interviewer_dev

ENABLE_OPENAPI=true
SANDBOX_TIME_LIMIT_MS=5000  # Higher limit for debugging
```

**Staging (.env.staging):**

```bash
APP_ENV=staging
DEBUG=false
BASE_URL=https://staging-api.example.com

DATABASE_URL=postgresql+asyncpg://user:pass@staging-db/ai_interviewer?ssl=require

ENABLE_OPENAPI=true
```

**Prod (.env.prod):**

```bash
APP_ENV=prod
DEBUG=false
BASE_URL=https://api.example.com

DATABASE_URL=postgresql+asyncpg://user:pass@prod-db/ai_interviewer?ssl=require

ENABLE_OPENAPI=false
SANDBOX_TIME_LIMIT_MS=2000
```

---

## 13. Critical Risk Areas

1. **Different Behavior Dev vs Prod:** Unnoticed config differences cause prod failures
2. **Hardcoded Model Names:** Module directly calls `gpt-4` instead of using config
3. **Sandbox Limit Mismatch:** Config says 2s timeout, sandbox enforces 5s
4. **Silent Default Secret:** Production uses default `SECRET_KEY=changeme`
5. **Feature Flag Drift:** Code checks `if config.enable_ai` in one place, `if AI_ENABLED` in another
6. **Magic Numbers:** "3000ms" timeout hardcoded in audio module instead of using config

---

## 14. Future Enhancements

1. **Cloud Secret Manager Integration:**
   - AWS Secrets Manager
   - Azure Key Vault
   - GCP Secret Manager

2. **Organization-Level Overrides:**
   - Allow specific orgs to override feature flags
   - Store in DB, cache in Redis

3. **Dynamic Configuration Reload:**
   - Hot-reload feature flags without restart
   - Graceful configuration updates

4. **Configuration Versioning:**
   - Track config changes over time
   - Audit trail for config modifications

5. **Multi-Region Configuration:**
   - Region-specific LLM endpoints
   - Region-specific resource limits

6. **A/B Testing Framework:**
   - Percentage-based feature rollouts
   - User-based experimental features

---

**End of Config Module Requirements**

---

## Architectural Intent

The config module is:

- The **deterministic runtime brain** of the system
- The **single source of truth** for all thresholds, limits, and toggles
- The **fail-fast guardian** preventing misconfiguration

Every number in your system—3-second pause, 2-second timeout, 15-minute token expiry—originates here.

**No magic numbers. No scattered flags. One truth.**
