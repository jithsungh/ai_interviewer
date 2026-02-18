# AI LLM Layer Testing Guide

## Testing Philosophy

The LLM layer MUST be fully testable **without making real API calls**. All unit tests use mocked provider SDKs.

**Test Priorities:**

1. Interface contract compliance (all providers implement same interface)
2. Response normalization (provider-specific → unified format)
3. Timeout enforcement (independent of provider SDK)
4. Error wrapping (all provider errors → LLMError)
5. Thread safety (concurrent requests)

---

## Test Structure

```
tests/
├── unit/
│   └── ai/
│       └── llm/
│           ├── test_base_interface.py
│           ├── test_openai_provider.py
│           ├── test_anthropic_provider.py
│           ├── test_provider_factory.py
│           ├── test_timeout_enforcement.py
│           └── test_response_normalization.py
├── integration/
│   └── ai/
│       └── llm/
│           ├── test_openai_real.py
│           ├── test_anthropic_real.py
│           └── test_embedding_generation.py
└── e2e/
    └── ai/
        └── llm/
            └── test_provider_switching.py
```

---

## 1. Unit Tests (Mocked SDKs)

### Base Interface Tests

```python
# tests/unit/ai/llm/test_base_interface.py

import pytest
from abc import ABC
from app.ai.llm.base import BaseLLMProvider
from app.ai.llm.openai_provider import OpenAIProvider
from app.ai.llm.anthropic_provider import AnthropicProvider

def test_base_provider_is_abstract():
    """Cannot instantiate base provider directly"""
    with pytest.raises(TypeError):
        BaseLLMProvider()

def test_all_providers_implement_interface():
    """All providers must implement required methods"""
    providers = [OpenAIProvider, AnthropicProvider]
    required_methods = ['generate_text', 'generate_structured', 'generate_embedding', 'transcribe_audio']

    for provider_class in providers:
        for method in required_methods:
            assert hasattr(provider_class, method)
            assert callable(getattr(provider_class, method))

def test_interface_signature_consistency():
    """All providers have consistent method signatures"""
    import inspect

    openai_sig = inspect.signature(OpenAIProvider.generate_text)
    anthropic_sig = inspect.signature(AnthropicProvider.generate_text)

    # Same parameter names and order
    assert list(openai_sig.parameters.keys()) == list(anthropic_sig.parameters.keys())
```

### OpenAI Provider Tests

```python
# tests/unit/ai/llm/test_openai_provider.py

from unittest.mock import Mock, patch, MagicMock
import pytest
from app.ai.llm.openai_provider import OpenAIProvider
from app.ai.llm.errors import LLMError, TimeoutError, RateLimitError

@pytest.fixture
def mock_openai_client():
    with patch('openai.ChatCompletion.create') as mock:
        yield mock

def test_generate_text_success(mock_openai_client):
    """Successful text generation returns LLMResponse"""
    mock_openai_client.return_value = {
        'id': 'chatcmpl-123',
        'choices': [{
            'message': {'content': 'Generated text'},
            'finish_reason': 'stop'
        }],
        'usage': {
            'prompt_tokens': 10,
            'completion_tokens': 5,
            'total_tokens': 15
        },
        'model': 'gpt-4'
    }

    provider = OpenAIProvider(api_key="test-key")
    response = provider.generate_text(
        prompt="Test prompt",
        model="gpt-4",
        temperature=0.7
    )

    assert response.success is True
    assert response.data['content'] == 'Generated text'
    assert response.telemetry.total_tokens == 15
    assert response.telemetry.model_id == 'gpt-4'
    assert response.error is None

def test_generate_structured_with_json_mode(mock_openai_client):
    """Structured generation uses JSON mode"""
    mock_openai_client.return_value = {
        'choices': [{
            'message': {'content': '{"result": "success"}'},
            'finish_reason': 'stop'
        }],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
        'model': 'gpt-4'
    }

    provider = OpenAIProvider(api_key="test-key")
    schema = {
        "type": "object",
        "properties": {"result": {"type": "string"}},
        "required": ["result"]
    }

    response = provider.generate_structured(
        prompt="Test",
        schema=schema,
        model="gpt-4"
    )

    assert response.success is True
    assert response.data['result'] == 'success'
    # Verify JSON mode was requested
    mock_openai_client.assert_called_once()
    call_kwargs = mock_openai_client.call_args[1]
    assert call_kwargs.get('response_format') == {"type": "json_object"}

def test_rate_limit_error_wrapped(mock_openai_client):
    """Rate limit error wrapped in LLMError"""
    from openai.error import RateLimitError as OpenAIRateLimitError

    mock_openai_client.side_effect = OpenAIRateLimitError("Rate limit exceeded")

    provider = OpenAIProvider(api_key="test-key")
    response = provider.generate_text(prompt="Test", model="gpt-4")

    assert response.success is False
    assert response.error.type == "rate_limit"
    assert response.error.retryable is True
    assert "Rate limit" in response.error.message

def test_authentication_error_wrapped(mock_openai_client):
    """Authentication error wrapped as non-retryable"""
    from openai.error import AuthenticationError

    mock_openai_client.side_effect = AuthenticationError("Invalid API key")

    provider = OpenAIProvider(api_key="invalid-key")
    response = provider.generate_text(prompt="Test", model="gpt-4")

    assert response.success is False
    assert response.error.type == "authentication"
    assert response.error.retryable is False

def test_telemetry_on_failure(mock_openai_client):
    """Telemetry recorded even when call fails"""
    mock_openai_client.side_effect = Exception("Provider error")

    provider = OpenAIProvider(api_key="test-key")
    response = provider.generate_text(prompt="Test", model="gpt-4")

    assert response.success is False
    assert response.telemetry is not None
    assert response.telemetry.latency_ms > 0
    assert response.telemetry.prompt_tokens == 0  # No usage on error
```

### Anthropic Provider Tests

```python
# tests/unit/ai/llm/test_anthropic_provider.py

from unittest.mock import patch
import pytest
from app.ai.llm.anthropic_provider import AnthropicProvider

@pytest.fixture
def mock_anthropic_client():
    with patch('anthropic.Anthropic') as mock:
        yield mock

def test_generate_text_success(mock_anthropic_client):
    """Anthropic text generation works"""
    mock_client = mock_anthropic_client.return_value
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Generated by Claude")],
        usage=MagicMock(
            input_tokens=10,
            output_tokens=5
        ),
        model="claude-3-sonnet-20240229"
    )

    provider = AnthropicProvider(api_key="test-key")
    response = provider.generate_text(
        prompt="Test",
        model="claude-3-sonnet"
    )

    assert response.success is True
    assert response.data['content'] == "Generated by Claude"
    assert response.telemetry.total_tokens == 15

def test_structured_output_via_prompt_engineering(mock_anthropic_client):
    """Anthropic uses prompting for structured output"""
    mock_client = mock_anthropic_client.return_value
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"score": 8}')],
        usage=MagicMock(input_tokens=20, output_tokens=3),
        model="claude-3-sonnet-20240229"
    )

    provider = AnthropicProvider(api_key="test-key")
    schema = {"type": "object", "properties": {"score": {"type": "number"}}}

    response = provider.generate_structured(
        prompt="Evaluate this",
        schema=schema,
        model="claude-3-sonnet"
    )

    assert response.success is True
    assert response.data['score'] == 8
    # Verify schema was injected into prompt
    call_args = mock_client.messages.create.call_args
    assert 'schema' in str(call_args) or 'JSON' in str(call_args)

def test_embedding_not_supported():
    """Anthropic doesn't support embeddings"""
    provider = AnthropicProvider(api_key="test-key")
    response = provider.generate_embedding(text="test")

    assert response.success is False
    assert "not supported" in response.error.message.lower()
```

### Timeout Enforcement Tests

```python
# tests/unit/ai/llm/test_timeout_enforcement.py

import time
import pytest
from unittest.mock import patch, MagicMock
from app.ai.llm.openai_provider import OpenAIProvider
from app.ai.llm.errors import TimeoutError

def test_timeout_enforced_at_http_level():
    """Timeout enforced independent of SDK"""
    def slow_response(*args, **kwargs):
        time.sleep(3)
        return {}

    with patch('openai.ChatCompletion.create', side_effect=slow_response):
        provider = OpenAIProvider(api_key="test-key")

        response = provider.generate_text(
            prompt="Test",
            model="gpt-4",
            timeout_seconds=1
        )

        assert response.success is False
        assert response.error.type == "timeout"
        assert response.error.retryable is True

def test_timeout_includes_latency():
    """Timeout response includes elapsed time"""
    def slow_response(*args, **kwargs):
        time.sleep(0.5)
        raise TimeoutError("Timeout")

    with patch('openai.ChatCompletion.create', side_effect=slow_response):
        provider = OpenAIProvider(api_key="test-key")
        response = provider.generate_text(prompt="Test", model="gpt-4", timeout_seconds=1)

        assert response.telemetry.latency_ms >= 500
```

### Response Normalization Tests

```python
# tests/unit/ai/llm/test_response_normalization.py

from app.ai.llm.openai_provider import OpenAIProvider
from app.ai.llm.anthropic_provider import AnthropicProvider
from app.ai.llm.response import LLMResponse

def test_response_structure_identical_across_providers():
    """All providers return same response structure"""
    # Mock both providers
    with patch('openai.ChatCompletion.create') as mock_openai, \
         patch('anthropic.Anthropic') as mock_anthropic:

        mock_openai.return_value = {
            'choices': [{'message': {'content': 'OpenAI'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            'model': 'gpt-4'
        }

        mock_anthropic_client = mock_anthropic.return_value
        mock_anthropic_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Anthropic")],
            usage=MagicMock(input_tokens=10, output_tokens=5),
            model="claude-3-sonnet"
        )

        openai_provider = OpenAIProvider(api_key="test")
        anthropic_provider = AnthropicProvider(api_key="test")

        openai_response = openai_provider.generate_text(prompt="Test", model="gpt-4")
        anthropic_response = anthropic_provider.generate_text(prompt="Test", model="claude-3-sonnet")

        # Same fields
        assert type(openai_response) == type(anthropic_response)
        assert openai_response.success is True
        assert anthropic_response.success is True
        assert hasattr(openai_response, 'telemetry')
        assert hasattr(anthropic_response, 'telemetry')
        assert openai_response.telemetry.total_tokens == 15
        assert anthropic_response.telemetry.total_tokens == 15
```

---

## 2. Integration Tests (Real APIs)

```python
# tests/integration/ai/llm/test_openai_real.py

import pytest
import os
from app.ai.llm.openai_provider import OpenAIProvider

@pytest.fixture
def openai_provider():
    api_key = os.getenv("OPENAI_TEST_KEY")
    if not api_key:
        pytest.skip("OPENAI_TEST_KEY not set")
    return OpenAIProvider(api_key=api_key)

@pytest.mark.integration
def test_real_openai_text_generation(openai_provider):
    """Real API call to OpenAI"""
    response = openai_provider.generate_text(
        prompt="Say 'test' and nothing else",
        model="gpt-3.5-turbo",
        temperature=0,
        max_tokens=5
    )

    assert response.success is True
    assert 'test' in response.data['content'].lower()
    assert response.telemetry.total_tokens > 0

@pytest.mark.integration
def test_real_openai_structured_output(openai_provider):
    """Real structured generation"""
    schema = {"type": "object", "properties": {"count": {"type": "integer"}}, "required": ["count"]}

    response = openai_provider.generate_structured(
        prompt="Return JSON with count=5",
        schema=schema,
        model="gpt-3.5-turbo",
        temperature=0
    )

    assert response.success is True
    assert response.data['count'] == 5

@pytest.mark.integration
def test_real_embedding_generation_self_hosted():
    """Generate real embedding from self-hosted service"""
    from app.ai.llm.embedding_provider import SelfHostedEmbeddingProvider

    provider = SelfHostedEmbeddingProvider(
        api_url=os.getenv("EMBEDDING_MODEL_URL")
    )
    response = provider.generate_embedding(
        text="Test embedding: Explain dependency injection in Python",
        model="all-mpnet-base-v2"
    )

    assert response.success is True
    assert len(response.embedding) == 768  # all-mpnet-base-v2 dimensions
    assert response.model_id == "all-mpnet-base-v2"
    assert response.telemetry.prompt_tokens > 0

@pytest.mark.integration
def test_real_embedding_generation_openai(openai_provider):
    """Generate real embedding from OpenAI (alternative)"""
    response = openai_provider.generate_embedding(
        text="Test embedding",
        model="text-embedding-ada-002"
    )

    assert response.success is True
    assert len(response.embedding) == 1536  # Ada-002 dimensions
```

---

## 3. E2E Tests (Provider Switching)

```python
# tests/e2e/ai/llm/test_provider_switching.py

@pytest.mark.e2e
def test_switch_provider_without_code_change():
    """Switching provider requires only config change"""
    from app.ai.llm.factory import LLMProviderFactory

    factory = LLMProviderFactory()

    # Use OpenAI
    openai = factory.get_provider("openai")
    response1 = openai.generate_text(prompt="Say 'hello'", model="gpt-3.5-turbo")

    # Switch to Anthropic
    anthropic = factory.get_provider("anthropic")
    response2 = anthropic.generate_text(prompt="Say 'hello'", model="claude-3-haiku")

    # Same interface, same response structure
    assert type(response1) == type(response2)
    assert response1.success is True
    assert response2.success is True
```

---

## 4. Thread Safety Tests

```python
# tests/unit/ai/llm/test_thread_safety.py

from concurrent.futures import ThreadPoolExecutor
import pytest

def test_concurrent_requests_no_interference():
    """Multiple threads can call provider simultaneously"""
    with patch('openai.ChatCompletion.create') as mock:
        mock.return_value = {
            'choices': [{'message': {'content': 'Response'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            'model': 'gpt-4'
        }

        provider = OpenAIProvider(api_key="test")

        def make_call(i):
            return provider.generate_text(prompt=f"Test {i}", model="gpt-4")

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_call, i) for i in range(50)]
            results = [f.result() for f in futures]

        assert all(r.success for r in results)
        assert len(results) == 50
```

---

## Test Coverage Requirements

- **Unit Tests:** >95% code coverage
- **Integration Tests:** All providers with real APIs
- **E2E Tests:** Provider switching scenarios
- **Thread Safety:** Concurrent access validation

---

## Running Tests

```bash
# Unit tests (mocked, fast)
pytest tests/unit/ai/llm/ -v

# Integration tests (real API)
pytest tests/integration/ai/llm/ -v --integration

# E2E tests
pytest tests/e2e/ai/llm/ -v --e2e

# Coverage
pytest tests/unit/ai/llm/ --cov=app/ai/llm --cov-report=html
```

---

**End of AI LLM Testing Guide**
