# Config Module Tests

Comprehensive test suite for the configuration module, including unit tests and integration tests.

## Test Structure

```
tests/
├── conftest.py                          # Shared fixtures and pytest configuration
├── unit/
│   └── config/
│       ├── test_settings_validation.py  # Settings validation tests
│       ├── test_feature_flags.py        # Feature flags tests
│       ├── test_security.py             # Security config tests
│       ├── test_constants.py            # Constants tests
│       └── test_environments.py         # Environment config tests
└── integration/
    └── config/
        └── test_config_integration.py   # Full config integration tests
```

## Running Tests

### Quick Start

Run all config tests:

```bash
python3 -m pytest tests/unit/config/ tests/integration/config/ -v
```

### Using Test Runners

#### Python runner:

```bash
python3 run_config_tests.py
```

#### Bash runner (Linux/Mac):

```bash
chmod +x run_config_tests.sh
./run_config_tests.sh
```

### Specific Test Categories

Unit tests only:

```bash
python3 -m pytest tests/unit/config/ -v
```

Integration tests only:

```bash
python3 -m pytest tests/integration/config/ -v
```

Specific test file:

```bash
python3 -m pytest tests/unit/config/test_settings_validation.py -v
```

Specific test class:

```bash
python3 -m pytest tests/unit/config/test_settings_validation.py::TestAppSettings -v
```

Specific test function:

```bash
python3 -m pytest tests/unit/config/test_settings_validation.py::TestAppSettings::test_app_settings_defaults -v
```

### Test Output Options

Verbose output:

```bash
python3 -m pytest tests/unit/config/ -v
```

Quiet output (summary only):

```bash
python3 -m pytest tests/unit/config/ -q
```

Show local variables on failures:

```bash
python3 -m pytest tests/unit/config/ --showlocals
```

Stop at first failure:

```bash
python3 -m pytest tests/unit/config/ -x
```

Show print statements:

```bash
python3 -m pytest tests/unit/config/ -s
```

## Test Coverage

### Unit Tests

#### Settings Validation Tests (`test_settings_validation.py`)

- ✓ App settings with defaults and environment variables
- ✓ Production environment validation (no debug, HTTPS)
- ✓ Database settings validation (required fields, SSL)
- ✓ Redis settings validation
- ✓ Qdrant settings and environment-aware collection names
- ✓ LLM provider settings and API key validation
- ✓ Sandbox resource limits validation
- ✓ Security settings (JWT algorithms, key requirements)
- ✓ Audio processing settings
- ✓ Rate limiting settings
- ✓ Feature flags settings

#### Feature Flags Tests (`test_feature_flags.py`)

- ✓ Feature flag creation from settings
- ✓ Immutability of feature flags
- ✓ Boolean type validation
- ✓ Factory function creation
- ✓ All enabled/disabled scenarios

#### Security Tests (`test_security.py`)

- ✓ Security config for dev/staging/prod environments
- ✓ CORS configuration
- ✓ Password policy validation
- ✓ Password validation rules (length, uppercase, lowercase, digit, special char)
- ✓ Immutability of security objects

#### Constants Tests (`test_constants.py`)

- ✓ Code execution constants
- ✓ Interview constants
- ✓ Evaluation constants
- ✓ Audio constants
- ✓ Status values
- ✓ Time conversion constants
- ✓ File size constants
- ✓ Pagination constants
- ✓ Password constants
- ✓ API constants
- ✓ Question type constants
- ✓ User role constants
- ✓ Proctoring constants
- ✓ Embedding constants
- ✓ Vector search constants

#### Environment Tests (`test_environments.py`)

- ✓ Dev/staging/prod environment configuration
- ✓ Environment-specific log levels
- ✓ Database pool size by environment
- ✓ SSL requirements by environment
- ✓ Error detail levels by environment
- ✓ Immutability of environment config

### Integration Tests

#### Config Integration Tests (`test_config_integration.py`)

- ✓ Complete settings loading
- ✓ Config module exports
- ✓ Feature flags integration
- ✓ Production config integration
- ✓ Qdrant environment suffix
- ✓ Sandbox config integration
- ✓ Password policy integration
- ✓ Constants accessibility
- ✓ Staging environment integration
- ✓ Validation failure scenarios
- ✓ Common usage patterns

## Test Fixtures

Available fixtures in `conftest.py`:

- `minimal_env`: Minimal environment variables for testing
- `dev_env`: Development environment variables
- `staging_env`: Staging environment variables
- `prod_env`: Production environment variables
- `mock_env`: Mocked environment with patch.dict
- `sample_passwords`: Valid and invalid password samples
- `security_settings_hs256`: Sample SecuritySettings with HS256
- `feature_flags_all_enabled`: All features enabled
- `feature_flags_all_disabled`: All features disabled
- `reset_config_module`: Auto-cleanup between tests

## Expected Test Results

When all tests pass, you should see:

```
tests/unit/config/test_settings_validation.py::TestAppSettings::test_app_settings_defaults PASSED
tests/unit/config/test_settings_validation.py::TestAppSettings::test_app_settings_from_env PASSED
tests/unit/config/test_settings_validation.py::TestAppSettings::test_production_requires_no_debug PASSED
... (many more) ...

======================== X passed in Y.YYs ========================
```

### Test Count Summary

- **Unit Tests**: ~80+ tests
  - Settings validation: ~25 tests
  - Feature flags: ~8 tests
  - Security: ~20 tests
  - Constants: ~25 tests
  - Environments: ~12 tests

- **Integration Tests**: ~15+ tests
  - Config loading: ~10 tests
  - Validation: ~3 tests
  - Usage patterns: ~3 tests

**Total: ~95+ tests**

## Continuous Integration

To run tests in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Config Tests
  run: |
    pip install -r requirements.txt
    python3 -m pytest tests/unit/config/ tests/integration/config/ -v --junitxml=junit.xml
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError: No module named 'app'`:

```bash
# Add project root to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

Or run from project root:

```bash
cd /path/to/ai_interviewer
python3 -m pytest tests/unit/config/ -v
```

### Pydantic Not Found

```bash
pip3 install pydantic pydantic-settings python-dotenv
```

Or install all requirements:

```bash
pip3 install -r requirements.txt
```

### Tests Failing Due to .env File

The tests use mocked environments, but if there's a `.env` file it might interfere. The `reset_config_module` fixture should prevent this, but if issues persist, temporarily rename `.env`:

```bash
mv .env .env.backup
python3 -m pytest tests/unit/config/ -v
mv .env.backup .env
```

## Writing New Tests

### Example Unit Test

```python
import pytest
from app.config.settings import AppSettings

class TestNewFeature:
    """Test new feature"""

    def test_feature_works(self):
        """Test that feature works correctly"""
        # Arrange
        settings = AppSettings(app_env="dev")

        # Act
        result = settings.app_env

        # Assert
        assert result == "dev"
```

### Example Integration Test

```python
import pytest
import os
from unittest.mock import patch

@patch.dict(os.environ, {
    "APP_ENV": "dev",
    "DATABASE_URL": "postgresql://localhost/db",
    # ... other required vars
}, clear=True)
def test_feature_integration():
    """Test feature integration"""
    from app.config import settings

    assert settings.app.app_env == "dev"
```

## Best Practices

1. **Use fixtures**: Reuse common test data from `conftest.py`
2. **Mock environment**: Use `@patch.dict(os.environ, ...)` for clean tests
3. **Test validation**: Always test both valid and invalid inputs
4. **Test immutability**: Verify frozen dataclasses can't be modified
5. **Test integration**: Verify components work together
6. **Clear names**: Use descriptive test function names
7. **One assertion focus**: Each test should test one specific thing

## Contributing

When adding new configuration:

1. Add unit tests for the new settings class
2. Add validation tests for new validators
3. Add integration tests for new config usage
4. Update this README with new test counts
5. Run all tests before committing

## Support

For issues with tests:

1. Check that all dependencies are installed
2. Ensure you're running from project root
3. Check that `.env` file isn't interfering
4. Review test output for specific error messages
