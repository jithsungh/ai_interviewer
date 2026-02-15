# Config Module - Usage Guide

## Overview

The config module provides centralized configuration management for the AI Interviewer application. All runtime configuration, feature flags, constants, and security policies are defined here.

## Quick Start

### 1. Set Up Environment Variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Import and Use Configuration

```python
from app.config import settings, feature_flags, constants

# Access nested settings
print(settings.app.app_env)  # "dev"
print(settings.database.database_url)
print(settings.llm.groq_api_key)

# Check feature flags
if feature_flags.ENABLE_AI_EVALUATION:
    # AI evaluation is enabled
    pass

# Use constants
max_code_size = constants.MAX_CODE_SIZE_BYTES
supported_langs = constants.SUPPORTED_LANGUAGES
```

## Module Structure

```
config/
├── settings.py          # All Pydantic settings classes
├── constants.py         # Immutable domain constants
├── feature_flags.py     # Feature toggle flags
├── security.py          # Security policies & password rules
├── environments.py      # Environment-specific behavior
└── __init__.py          # Exports all config objects
```

## Configuration Categories

### 1. Application Settings

```python
from app.config import settings

# Access application config
env = settings.app.app_env  # "dev", "staging", or "prod"
debug = settings.app.debug
base_url = settings.app.base_url
```

### 2. Database Settings

```python
# PostgreSQL configuration
db_url = settings.database.database_url
pool_size = settings.database.db_pool_size
```

### 3. Redis Settings

```python
# Redis configuration
redis_url = settings.redis.redis_url
session_ttl = settings.redis.redis_session_ttl
```

### 4. Qdrant Settings

```python
# Vector database configuration
qdrant_url = settings.qdrant.qdrant_url
embedding_dim = settings.qdrant.qdrant_embedding_dim

# Get environment-aware collection name
collection = settings.qdrant.get_collection_name_with_env(settings.app.app_env)
```

### 5. LLM Provider Settings

```python
# LLM configuration
provider = settings.llm.default_llm_provider  # "openai", "anthropic", "groq"
api_key = settings.llm.groq_api_key
model = settings.llm.llm_model_evaluation
temperature = settings.llm.llm_temperature
```

### 6. Sandbox Settings

```python
# Code execution sandbox configuration
time_limit = settings.sandbox.sandbox_time_limit_ms
memory_limit = settings.sandbox.sandbox_memory_limit_kb
python_image = settings.sandbox.sandbox_image_python
```

### 7. Security Settings

```python
from app.config import security_config, password_policy

# JWT configuration
jwt_algo = settings.security.jwt_algorithm
token_expiry = settings.security.access_token_expire_minutes

# Password validation
is_valid, error = password_policy.validate("MyPassword123!")
if not is_valid:
    print(error)
```

### 8. Feature Flags

```python
from app.config import feature_flags

# Check if features are enabled
if feature_flags.ENABLE_AI_EVALUATION:
    await evaluate_with_ai(submission)

if feature_flags.ENABLE_CODE_EXECUTION:
    await execute_code(submission)

if feature_flags.ENABLE_PROCTORING:
    await check_proctoring_violations()
```

### 9. Constants

```python
from app.config import constants

# Use domain constants
if language in constants.SUPPORTED_LANGUAGES:
    # Process code
    pass

max_question_len = constants.MAX_QUESTION_LENGTH
interview_statuses = constants.INTERVIEW_STATUS_VALUES
```

### 10. Environment Config

```python
from app.config import env_config

# Environment-specific behavior
if env_config.is_prod:
    # Production-specific logic
    pass

log_level = env_config.get_log_level()
should_use_ssl = env_config.should_use_ssl()
```

## Environment Variables Reference

### Required Variables

These MUST be set for the application to start:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `QDRANT_URL`: Qdrant server URL
- `GROQ_API_KEY`: Groq API key (when using Groq provider)
- `JWT_SECRET_KEY`: Secret key for JWT signing (when using HS256)

### Optional Variables

These have sensible defaults but can be overridden:

- `APP_ENV`: Environment (default: "dev")
- `DEBUG`: Debug mode (default: false)
- `QDRANT_EMBEDDING_DIM`: Embedding dimensions (default: 768)
- `LLM_TEMPERATURE`: LLM temperature (default: 0.7)
- `SANDBOX_TIME_LIMIT_MS`: Code execution timeout (default: 2000)

See `.env.example` for complete list with descriptions.

## Configuration Validation

The config module validates settings at startup and fails fast with clear error messages:

```python
# Example validation errors:

# Missing required variable
# ValueError: GROQ_API_KEY required when DEFAULT_LLM_PROVIDER=groq

# Invalid resource limit
# ValueError: SANDBOX_TIME_LIMIT_MS must be >= 100ms

# Production safety check
# ValueError: DEBUG must be False in production
```

## Adding New Configuration

### 1. Add to Settings Class

```python
# In settings.py
class MyNewSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    my_setting: str = Field(..., env="MY_SETTING")

    @model_validator(mode='after')
    def validate_my_setting(self):
        # Add validation logic
        return self
```

### 2. Add to Master Settings

```python
# In settings.py
class Settings(BaseSettings):
    # ... existing settings ...
    my_new: MyNewSettings

    @classmethod
    def load(cls) -> "Settings":
        settings = cls(
            # ... existing ...
            my_new=MyNewSettings()
        )
        return settings
```

### 3. Export from **init**.py

```python
# In __init__.py
from .settings import MyNewSettings

__all__ = [
    # ... existing ...
    "MyNewSettings",
]
```

### 4. Add to .env and .env.example

```bash
# In .env and .env.example
MY_SETTING=my-value
```

## Best Practices

### ✅ DO

- Import settings from `app.config`
- Use feature flags for conditional features
- Use constants instead of magic numbers
- Validate configuration at module boundaries
- Use environment-aware collection names

### ❌ DON'T

- Access `os.environ` directly (use settings)
- Hardcode magic numbers (use constants)
- Change settings after startup (immutable)
- Log sensitive values (API keys, passwords)
- Skip validation in production

## Testing

```python
import pytest
from app.config import settings, feature_flags

def test_settings_loaded():
    assert settings.app.app_env in ["dev", "staging", "prod"]
    assert settings.database.database_url

def test_feature_flags():
    assert isinstance(feature_flags.ENABLE_AI_EVALUATION, bool)

def test_constants_immutable():
    from app.config import constants
    # Constants should be immutable
    with pytest.raises(TypeError):
        constants.SUPPORTED_LANGUAGES.append("rust")
```

## Troubleshooting

### "Import pydantic_settings could not be resolved"

Install dependencies:

```bash
pip install -r requirements.txt
```

### "Configuration validation failed"

Check your `.env` file has all required variables. Compare with `.env.example`.

### "DATABASE_URL must use SSL in production"

In production, ensure your `DATABASE_URL` includes `?ssl=require` or `?sslmode=require`.

### Settings not loading

Make sure `.env` file is in the project root (same level as `main.py`).

## Current Configuration (Dev Environment)

```
Environment: dev
Database: 100.95.213.103
Redis: 100.95.213.103:6379
Qdrant: 100.95.213.103:6333
LLM Provider: Groq AI (gpt-oss-120b)
Embedding Dimension: 768
```

## Security Notes

- Never commit `.env` to version control (use `.env.example`)
- Rotate API keys regularly
- Use strong JWT secret keys (min 32 chars)
- Enable HTTPS in production
- Review security settings before deployment

## Support

For configuration issues, check:

1. `.env` file exists and is complete
2. All required packages are installed
3. Database/Redis/Qdrant services are running
4. API keys are valid

Refer to `app/config/REQUIREMENTS.md` for detailed specifications.
