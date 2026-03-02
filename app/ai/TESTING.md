# AI Module Testing Guide

## Testing Philosophy

The AI module is infrastructure-only and MUST be fully testable **without making real API calls** to LLM providers. All tests should use mocked providers to ensure:

- Fast execution (<1s per test)
- No external dependencies
- Deterministic results
- No API costs
- Isolated from provider outages

---

## Test Structure

```
tests/
├── unit/
│   └── ai/
│       ├── test_provider_abstraction.py
│       ├── test_schema_validation.py
│       ├── test_timeout_retry.py
│       └── test_telemetry.py
├── integration/
│   └── ai/
│       ├── test_openai_provider.py
│       ├── test_anthropic_provider.py
│       └── test_prompt_rendering.py
└── e2e/
    └── ai/
        └── test_use_cases.py
```

---

## 1. Unit Tests (Mocked Providers)

### Provider Abstraction Tests

```python
# tests/unit/ai/test_provider_abstraction.py

from unittest.mock import Mock, patch
import pytest
from app.ai.llm.base import BaseLLMProvider
from app.ai.llm.openai_provider import OpenAIProvider

def test_provider_interface_contract():
    """All providers must implement base interface"""
    provider = OpenAIProvider(api_key="test")

    assert hasattr(provider, 'generate_text')
    assert hasattr(provider, 'generate_structured')
    assert hasattr(provider, 'generate_embedding')
    assert callable(provider.generate_text)

@patch('openai.ChatCompletion.create')
def test_generate_text_with_mock(mock_openai):
    """Test text generation with mocked OpenAI"""
    mock_openai.return_value = {
        'choices': [{'message': {'content': 'Test response'}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
        'model': 'gpt-4'
    }

    provider = OpenAIProvider(api_key="test")
    response = provider.generate_text(
        prompt="Test prompt",
        model="gpt-4",
        temperature=0.7
    )

    assert response.success is True
    assert response.data['content'] == 'Test response'
    assert response.telemetry.total_tokens == 15

def test_provider_switching():
    """Switching providers should not require API changes"""
    providers = [
        OpenAIProvider(api_key="test"),
        AnthropicProvider(api_key="test")
    ]

    for provider in providers:
        # Same interface for all providers
        result = provider.generate_text(prompt="test", model="default")
        assert hasattr(result, 'success')
        assert hasattr(result, 'telemetry')
```

### Schema Validation Tests

```python
# tests/unit/ai/test_schema_validation.py

from app.ai.llm.schema_validator import SchemaValidator
from app.ai.errors import SchemaValidationError

def test_valid_schema_passes():
    """Valid output passes schema validation"""
    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "number"},
            "justification": {"type": "string"}
        },
        "required": ["score", "justification"]
    }

    output = {
        "score": 8.5,
        "justification": "Good answer"
    }

    validator = SchemaValidator(schema)
    result = validator.validate(output)
    assert result.is_valid is True

def test_missing_required_field_fails():
    """Missing required field fails validation"""
    schema = {
        "type": "object",
        "properties": {
            "score": {"type": "number"},
            "justification": {"type": "string"}
        },
        "required": ["score", "justification"]
    }

    output = {"score": 8.5}  # Missing justification

    validator = SchemaValidator(schema)
    result = validator.validate(output)
    assert result.is_valid is False
    assert "justification" in result.errors[0].message

def test_type_coercion_permitted():
    """Permissive validation allows type coercion"""
    schema = {
        "type": "object",
        "properties": {"experience_years": {"type": "integer"}},
        "required": ["experience_years"]
    }

    output = {"experience_years": "5"}  # String instead of int

    validator = SchemaValidator(schema, strict=False)
    result = validator.validate(output)
    assert result.is_valid is True
    assert result.coerced_output["experience_years"] == 5
```

### Timeout & Retry Tests

```python
# tests/unit/ai/test_timeout_retry.py

from unittest.mock import Mock, patch
import pytest
import time
from app.ai.llm.retry_handler import RetryHandler
from app.ai.errors import TimeoutError, RateLimitError

def test_timeout_enforced():
    """Provider call times out after configured duration"""
    def slow_call():
        time.sleep(3)
        return "response"

    handler = RetryHandler(timeout_seconds=1)

    with pytest.raises(TimeoutError):
        handler.execute(slow_call)

def test_retry_on_rate_limit():
    """Rate limit error triggers retry with backoff"""
    call_count = 0

    def flaky_call():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RateLimitError("Rate limited")
        return "success"

    handler = RetryHandler(max_retries=3, backoff_base=0.1)
    result = handler.execute(flaky_call)

    assert result == "success"
    assert call_count == 3

def test_non_retryable_error_fails_immediately():
    """Authentication errors should not retry"""
    def auth_fail():
        raise AuthenticationError("Invalid API key")

    handler = RetryHandler(max_retries=3)

    with pytest.raises(AuthenticationError):
        handler.execute(auth_fail)

    # Should fail immediately, not retry

def test_exponential_backoff():
    """Retry delays should increase exponentially"""
    handler = RetryHandler(backoff_base=1, max_retries=3)

    delays = handler.calculate_delays()
    assert delays == [1, 2, 4]  # Exponential progression

def test_jitter_prevents_stampede():
    """Jitter should randomize retry timing"""
    handler = RetryHandler(backoff_base=1, jitter=True)

    delays1 = [handler.calculate_delay(i) for i in range(3)]
    delays2 = [handler.calculate_delay(i) for i in range(3)]

    # With jitter, delays should differ
    assert delays1 != delays2
```

### Telemetry Tests

```python
# tests/unit/ai/test_telemetry.py

from app.ai.telemetry.tracker import TelemetryTracker

def test_telemetry_captured_on_success():
    """Successful calls record full telemetry"""
    tracker = TelemetryTracker()

    with tracker.track("evaluation") as span:
        span.record_tokens(prompt=100, completion=50)
        span.record_model("gpt-4")

    telemetry = span.finalize()
    assert telemetry.prompt_tokens == 100
    assert telemetry.completion_tokens == 50
    assert telemetry.total_tokens == 150
    assert telemetry.model_id == "gpt-4"
    assert telemetry.latency_ms > 0

def test_telemetry_captured_on_failure():
    """Failed calls still record partial telemetry"""
    tracker = TelemetryTracker()

    try:
        with tracker.track("question_generation") as span:
            span.record_tokens(prompt=50, completion=0)
            raise TimeoutError("Request timed out")
    except TimeoutError:
        pass

    telemetry = span.finalize()
    assert telemetry.prompt_tokens == 50
    assert telemetry.completion_tokens == 0
    assert telemetry.error_type == "timeout"

def test_cost_estimation():
    """Token usage converted to estimated cost"""
    tracker = TelemetryTracker()

    cost = tracker.estimate_cost(
        model="gpt-4",
        prompt_tokens=1000,
        completion_tokens=500
    )

    # GPT-4 pricing: ~$0.03/1K prompt, ~$0.06/1K completion
    expected = (1000 * 0.03 / 1000) + (500 * 0.06 / 1000)
    assert abs(cost - expected) < 0.001
```

---

## 2. Integration Tests (Real Provider, Test Mode)

### OpenAI Provider Integration

```python
# tests/integration/ai/test_openai_provider.py

import pytest
from app.ai.llm.openai_provider import OpenAIProvider

@pytest.fixture
def openai_provider():
    # Uses test API key from environment
    return OpenAIProvider(api_key=os.getenv("OPENAI_TEST_KEY"))

@pytest.mark.integration
def test_openai_text_generation(openai_provider):
    """Real API call to OpenAI (uses test credits)"""
    response = openai_provider.generate_text(
        prompt="Say 'test successful' and nothing else",
        model="gpt-3.5-turbo",
        temperature=0,
        max_tokens=10
    )

    assert response.success is True
    assert "test successful" in response.data['content'].lower()
    assert response.telemetry.total_tokens > 0

@pytest.mark.integration
def test_openai_structured_output(openai_provider):
    """Test structured output with schema validation"""
    schema = {
        "type": "object",
        "properties": {
            "result": {"type": "string"}
        },
        "required": ["result"]
    }

    response = openai_provider.generate_structured(
        prompt="Return JSON: {'result': 'success'}",
        schema=schema,
        model="gpt-3.5-turbo",
        temperature=0
    )

    assert response.success is True
    assert response.data['result'] == 'success'
```

### Anthropic Provider Integration

```python
# tests/integration/ai/test_anthropic_provider.py

@pytest.mark.integration
def test_anthropic_text_generation(anthropic_provider):
    """Real API call to Anthropic"""
    response = anthropic_provider.generate_text(
        prompt="Say 'test successful' and nothing else",
        model="claude-3-sonnet",
        temperature=0
    )

    assert response.success is True
    assert "test successful" in response.data['content'].lower()
```

### Prompt Rendering Integration

```python
# tests/integration/ai/test_prompt_rendering.py

def test_prompt_retrieved_from_database(db_session):
    """Prompt templates retrieved from database"""
    from app.ai.prompts.repository import PromptRepository

    repo = PromptRepository(db_session)
    prompt = repo.get_active_prompt(
        prompt_type="evaluation",
        organization_id=1
    )

    assert prompt is not None
    assert prompt.is_active is True
    assert prompt.content is not None

def test_variable_interpolation():
    """Prompt variables replaced correctly"""
    from app.ai.prompts.renderer import PromptRenderer

    template = "Evaluate the following answer: {answer}"
    renderer = PromptRenderer(template)

    result = renderer.render(answer="This is a test")
    assert result == "Evaluate the following answer: This is a test"
```

---

## 3. End-to-End Tests (Full Use Cases)

### Question Generation E2E

```python
# tests/e2e/ai/test_use_cases.py

@pytest.mark.e2e
def test_question_generation_use_case(mock_llm):
    """Complete question generation workflow"""
    from app.ai import generate_question

    response = generate_question(
        role="Software Engineer",
        topics=["Python", "Algorithms"],
        difficulty="medium",
        resume_context="5 years Python experience"
    )

    assert response.success is True
    assert 'question_text' in response.data
    assert response.data['difficulty'] == 'medium'
    assert response.telemetry.prompt_type == 'question_generation'

@pytest.mark.e2e
def test_evaluation_use_case(mock_llm):
    """Complete evaluation workflow"""
    from app.ai import evaluate_response

    response = evaluate_response(
        question="Explain Python decorators",
        candidate_response="Decorators are functions that modify other functions.",
        rubric_dimensions=[
            {
                "name": "Correctness",
                "criteria": "Answer is factually correct",
                "max_score": 10
            },
            {
                "name": "Completeness",
                "criteria": "Answer covers key concepts",
                "max_score": 10
            }
        ],
        deterministic=True
    )

    assert response.success is True
    assert 'dimension_scores' in response.data
    assert len(response.data['dimension_scores']) == 2
    assert all('score' in d for d in response.data['dimension_scores'])
    assert all('justification' in d for d in response.data['dimension_scores'])

@pytest.mark.e2e
def test_resume_parsing_use_case(mock_llm):
    """Complete resume parsing workflow"""
    from app.ai import parse_resume

    resume_text = """
    John Doe
    Software Engineer
    Skills: Python, JavaScript, React
    Experience: 5 years
    """

    response = parse_resume(resume_text)

    assert response.success is True
    assert 'skills' in response.data
    assert 'experience_years' in response.data
    assert response.data['experience_years'] == 5
    assert 'Python' in response.data['skills']
```

---

## 4. Performance Tests

```python
# tests/performance/ai/test_latency.py

@pytest.mark.performance
def test_evaluation_latency_within_sla(mock_llm):
    """Evaluation should complete within 10s p95"""
    from app.ai import evaluate_response
    import time

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        response = evaluate_response(
            question="Test question",
            candidate_response="Test response",
            rubric_dimensions=[{"name": "Test", "criteria": "Test", "max_score": 10}]
        )
        latencies.append(time.perf_counter() - start)

    p95 = sorted(latencies)[94]
    assert p95 < 10.0, f"P95 latency {p95}s exceeds 10s SLA"

@pytest.mark.performance
def test_concurrent_requests(mock_llm):
    """System handles concurrent AI requests"""
    from concurrent.futures import ThreadPoolExecutor
    from app.ai import generate_question

    def make_request():
        return generate_question(role="Engineer", topics=["Python"], difficulty="easy")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(make_request) for _ in range(50)]
        results = [f.result() for f in futures]

    assert all(r.success for r in results)
```

---

## 5. Error Scenario Tests

```python
# tests/unit/ai/test_error_scenarios.py

def test_schema_validation_failure_retries():
    """Schema validation failure triggers retry"""
    call_count = 0

    def mock_provider_bad_then_good():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"invalid": "schema"}  # Missing required fields
        return {"score": 8, "justification": "Good"}  # Valid

    schema = {
        "type": "object",
        "properties": {"score": {"type": "number"}, "justification": {"type": "string"}},
        "required": ["score", "justification"]
    }

    response = generate_with_retry(mock_provider_bad_then_good, schema=schema, max_retries=3)

    assert response.success is True
    assert call_count == 2  # Retried once

def test_timeout_error_surface():
    """Timeout errors surfaced correctly"""
    from app.ai import generate_question

    with patch('app.ai.llm.openai_provider.OpenAIProvider.generate_text') as mock:
        mock.side_effect = TimeoutError("Request timed out")

        response = generate_question(role="Engineer", topics=["Python"], difficulty="easy")

        assert response.success is False
        assert response.error.type == "timeout"
        assert response.error.retryable is True

def test_rate_limit_with_backoff():
    """Rate limit error triggers exponential backoff"""
    call_times = []

    def rate_limited_call():
        call_times.append(time.perf_counter())
        if len(call_times) < 3:
            raise RateLimitError("Rate limited")
        return "success"

    response = execute_with_retry(rate_limited_call, max_retries=3)

    # Verify exponential backoff between calls
    assert call_times[1] - call_times[0] >= 1.0  # First retry after 1s
    assert call_times[2] - call_times[1] >= 2.0  # Second retry after 2s
```

---

## 6. Domain Isolation Tests

```python
# tests/unit/ai/test_domain_isolation.py

def test_ai_module_does_not_import_domain():
    """AI module must not import domain modules"""
    import ast
    import os

    ai_module_path = "app/ai"
    forbidden_imports = ["interview", "evaluation", "admin", "coding", "question"]

    for root, dirs, files in os.walk(ai_module_path):
        for file in files:
            if file.endswith(".py"):
                with open(os.path.join(root, file)) as f:
                    tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                assert not any(f in alias.name for f in forbidden_imports), \
                                    f"AI module imports forbidden module: {alias.name}"

def test_ai_response_does_not_reference_domain_entities():
    """AI responses should not reference domain entities"""
    from app.ai import generate_question

    response = generate_question(role="Engineer", topics=["Python"], difficulty="easy")

    # Response should not contain domain-specific fields
    assert 'submission_id' not in response.data
    assert 'exchange_id' not in response.data
    assert 'template_id' not in response.data
```

---

## 7. Mock Fixtures

```python
# tests/conftest.py

@pytest.fixture
def mock_openai_provider():
    """Mocked OpenAI provider for fast unit tests"""
    with patch('app.ai.llm.openai_provider.openai.ChatCompletion.create') as mock:
        mock.return_value = {
            'choices': [{'message': {'content': 'Mocked response'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            'model': 'gpt-4'
        }
        yield mock

@pytest.fixture
def mock_schema_validator():
    """Always passes schema validation in tests"""
    with patch('app.ai.llm.schema_validator.SchemaValidator.validate') as mock:
        mock.return_value = ValidationResult(is_valid=True, errors=[])
        yield mock
```

---

## Test Coverage Requirements

- **Unit Tests:** >90% code coverage
- **Integration Tests:** Cover all provider implementations
- **E2E Tests:** Cover all 5 use cases (question gen, evaluation, resume parse, JD parse, report gen)
- **Error Scenarios:** Cover all error types (timeout, rate limit, schema validation, auth failure)
- **Performance Tests:** Verify latency SLAs

---

## Running Tests

```bash
# Unit tests only (fast, no external calls)
pytest tests/unit/ai/ -v

# Integration tests (requires test API keys)
pytest tests/integration/ai/ -v --integration

# E2E tests (full workflows)
pytest tests/e2e/ai/ -v --e2e

# Performance tests
pytest tests/performance/ai/ -v --performance

# All tests
pytest tests/ai/ -v --all

# Coverage report
pytest tests/ai/ --cov=app/ai --cov-report=html
```

---

**End of AI Module Testing Guide**
