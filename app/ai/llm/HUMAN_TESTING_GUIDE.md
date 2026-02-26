# AI/LLM Module - Human Testing Guide

**Module:** `app/ai/llm`  
**Purpose:** Provider-agnostic LLM abstraction layer  
**Status:** ✅ Implemented (Groq provider functional, others stubbed)

---

## Overview

The AI/LLM module provides a unified interface for interacting with multiple LLM providers (Groq, Gemini, OpenAI, Anthropic). This guide helps engineers manually test the module functionality.

**Note:** This module is infrastructure-only and does NOT expose REST API endpoints. Testing is done via Python scripts or Jupyter notebooks.

---

## Prerequisites

### Environment Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**
   ```bash
   export GROQ_API_KEY="gsk_..."
   export GEMINI_API_KEY="AI..."  # Optional
   export OPENAI_API_KEY="sk-..."  # Optional
   export ANTHROPIC_API_KEY="sk-ant-..."  # Optional
   export EMBEDDING_MODEL_URL="http://localhost:8080"  # Self-hosted embedding service
   ```

3. **Verify Configuration**
   ```bash
   python -c "from app.config.settings import settings; print(settings.llm.groq_api_key[:10])"
   ```

---

## Test Scenarios

### Scenario 1: Basic Text Generation (Groq)

**Purpose:** Verify Groq provider generates text completions.

**Steps:**

1. Create test script `test_groq_basic.py`:
   ```python
   import asyncio
   from app.ai.llm import ProviderFactory, LLMRequest
   
   async def test_basic_generation():
       # Create Groq provider
       provider = ProviderFactory.create_text_provider("groq")
       
       # Build request
       request = LLMRequest(
           prompt="Explain what a binary search tree is in one sentence.",
           model="llama-3.3-70b-versatile",
           temperature=0.7,
           max_tokens=100,
           timeout_seconds=30
       )
       
       # Generate text
       response = await provider.generate_text(request)
       
       # Verify response
       print(f"Success: {response.success}")
       print(f"Text: {response.text}")
       print(f"Tokens: {response.telemetry.total_tokens}")
       print(f"Latency: {response.telemetry.latency_ms}ms")
       
       assert response.success is True
       assert response.text is not None
       assert len(response.text) > 0
       assert response.telemetry.latency_ms > 0
   
   if __name__ == "__main__":
       asyncio.run(test_basic_generation())
   ```

2. Run test:
   ```bash
   python test_groq_basic.py
   ```

**Expected Output:**
```
Success: True
Text: A binary search tree is a hierarchical data structure where each node has at most two children, with left child values less than the parent and right child values greater, enabling efficient searching in O(log n) time.
Tokens: 45
Latency: 856ms
```

**Verification:**
- [x] Response success = True
- [x] Text contains valid explanation
- [x] Telemetry includes token count
- [x] Latency is reasonable (<5s)

---

### Scenario 2: Structured JSON Output

**Purpose:** Verify JSON mode with schema validation.

**Steps:**

1. Create test script `test_structured_output.py`:
   ```python
   import asyncio
   import json
   from app.ai.llm import ProviderFactory, LLMRequest
   
   async def test_structured_output():
       provider = ProviderFactory.create_text_provider("groq")
       
       request = LLMRequest(
           prompt="""Generate a person profile with:
           - name (string)
           - age (number, 20-50)
           - skills (array of strings, at least 3)
           - experience_years (number)
           """,
           model="llama-3.3-70b-versatile",
           json_mode=True,
           temperature=0.0,
           timeout_seconds=30,
           schema={
               "type": "object",
               "required": ["name", "age", "skills", "experience_years"],
               "properties": {
                   "name": {"type": "string"},
                   "age": {"type": "number"},
                   "skills": {"type": "array"},
                   "experience_years": {"type": "number"}
               }
           }
       )
       
       response = await provider.generate_structured(request)
       
       print(f"Success: {response.success}")
       print(f"Raw JSON: {response.text}")
       
       # Parse and validate JSON
       data = json.loads(response.text)
       print(f"\nParsed data:")
       print(f"  Name: {data['name']}")
       print(f"  Age: {data['age']}")
       print(f"  Skills: {data['skills']}")
       print(f"  Experience: {data['experience_years']} years")
       
       # Validate schema
       assert response.success is True
       assert "name" in data
       assert "age" in data
       assert "skills" in data
       assert isinstance(data["skills"], list)
       assert len(data["skills"]) >= 3
       
       print("\n✅ Schema validation passed")
   
   if __name__ == "__main__":
       asyncio.run(test_structured_output())
   ```

2. Run test:
   ```bash
   python test_structured_output.py
   ```

**Expected Output:**
```
Success: True
Raw JSON: {"name": "John Doe", "age": 32, "skills": ["Python", "JavaScript", "SQL", "Docker"], "experience_years": 8}

Parsed data:
  Name: John Doe
  Age: 32
  Skills: ['Python', 'JavaScript', 'SQL', 'Docker']
  Experience: 8 years

✅ Schema validation passed
```

**Verification:**
- [x] Response is valid JSON
- [x] All required fields present
- [x] Field types match schema
- [x] No schema validation errors

---

### Scenario 3: Deterministic Mode

**Purpose:** Verify deterministic mode produces consistent results.

**Steps:**

1. Create test script `test_deterministic.py`:
   ```python
   import asyncio
   from app.ai.llm import ProviderFactory, LLMRequest
   
   async def test_deterministic():
       provider = ProviderFactory.create_text_provider("groq")
       
       request = LLMRequest(
           prompt="List the first 5 prime numbers, comma-separated.",
           model="llama-3.3-70b-versatile",
           deterministic=True,  # Forces temperature=0
           timeout_seconds=30
       )
       
       # Make 3 identical requests
       responses = []
       for i in range(3):
           response = await provider.generate_text(request)
           responses.append(response)
           print(f"Attempt {i+1}: {response.text}")
       
       # Verify all responses identical (or very similar)
       texts = [r.text for r in responses]
       all_identical = len(set(texts)) == 1
       
       print(f"\nAll responses identical: {all_identical}")
       
       if not all_identical:
           print("Note: Minor variance acceptable, check if semantically equivalent")
       
       assert all(r.success for r in responses)
       assert responses[0].telemetry.temperature == 0.0
   
   if __name__ == "__main__":
       asyncio.run(test_deterministic())
   ```

2. Run test:
   ```bash
   python test_deterministic.py
   ```

**Expected Output:**
```
Attempt 1: 2, 3, 5, 7, 11
Attempt 2: 2, 3, 5, 7, 11
Attempt 3: 2, 3, 5, 7, 11

All responses identical: True
```

**Verification:**
- [x] Temperature set to 0.0
- [x] Responses consistent across calls
- [x] Output semantically correct

---

### Scenario 4: Timeout Handling

**Purpose:** Verify timeout enforcement and error handling.

**Steps:**

1. Create test script `test_timeout.py`:
   ```python
   import asyncio
   from app.ai.llm import ProviderFactory, LLMRequest
   
   async def test_timeout():
       provider = ProviderFactory.create_text_provider("groq")
       
       # Request with very short timeout
       request = LLMRequest(
           prompt="Write a 5000-word essay on the history of computing.",
           model="llama-3.3-70b-versatile",
           max_tokens=5000,
           timeout_seconds=1  # Deliberately short
       )
       
       response = await provider.generate_text(request)
       
       print(f"Success: {response.success}")
       print(f"Error: {response.error}")
       print(f"Latency: {response.telemetry.latency_ms}ms")
       
       if not response.success:
           print(f"Error Type: {response.error.type}")
           print(f"Retryable: {response.error.retryable}")
           assert response.error.type in ["timeout", "provider_error"]
           assert response.error.retryable is True
       
       # Telemetry should be recorded even on failure
       assert response.telemetry is not None
       assert response.telemetry.success is False
   
   if __name__ == "__main__":
       asyncio.run(test_timeout())
   ```

2. Run test:
   ```bash
   python test_timeout.py
   ```

**Expected Output:**
```
Success: False
Error: LLMError(type='timeout', message='Groq request timeout after 1s', retryable=True)
Latency: 1002ms
Error Type: timeout
Retryable: True
```

**Verification:**
- [x] Response success = False
- [x] Error type = "timeout"
- [x] Retryable = True
- [x] Telemetry recorded even on failure

---

### Scenario 5: Embedding Generation

**Purpose:** Verify self-hosted embedding service integration.

**Prerequisites:** Embedding service running at `EMBEDDING_MODEL_URL`

**Steps:**

1. **Start Embedding Service** (if not already running):
   ```bash
   # Example using sentence-transformers
   docker run -p 8080:8080 ghcr.io/huggingface/text-embeddings-inference:latest \
     --model-id sentence-transformers/all-mpnet-base-v2
   
   # Or use your organization's deployed service
   ```

2. Create test script `test_embeddings.py`:
   ```python
   import asyncio
   from app.ai.llm import ProviderFactory, EmbeddingRequest
   
   async def test_embeddings():
       provider = ProviderFactory.create_embedding_provider()
       
       request = EmbeddingRequest(
           text="Python is a high-level programming language.",
           model="all-mpnet-base-v2",
           timeout_seconds=30
       )
       
       response = await provider.generate_embedding(request)
       
       print(f"Success: {response.success}")
       print(f"Dimensions: {response.dimensions}")
       print(f"Embedding (first 10 values): {response.embedding[:10]}")
       print(f"Latency: {response.telemetry.latency_ms}ms")
       
       assert response.success is True
       assert response.dimensions == 768
       assert len(response.embedding) == 768
       assert all(isinstance(v, float) for v in response.embedding)
       
       print("\n✅ Embedding generated successfully")
   
   if __name__ == "__main__":
       asyncio.run(test_embeddings())
   ```

3. Run test:
   ```bash
   python test_embeddings.py
   ```

**Expected Output:**
```
Success: True
Dimensions: 768
Embedding (first 10 values): [0.023, -0.045, 0.012, 0.089, -0.034, 0.067, -0.023, 0.011, 0.056, -0.078]
Latency: 124ms

✅ Embedding generated successfully
```

**Verification:**
- [x] Success = True
- [x] Embedding has 768 dimensions
- [x] Values are floats
- [x] Latency reasonable (<1s)

---

### Scenario 6: Provider Factory

**Purpose:** Verify provider factory correctly instantiates providers.

**Steps:**

1. Create test script `test_factory.py`:
   ```python
   from app.ai.llm import ProviderFactory, GroqProvider
   
   def test_factory():
       # Create provider by name
       provider = ProviderFactory.create_text_provider("groq")
       
       print(f"Provider type: {type(provider).__name__}")
       print(f"Provider name: {provider.get_provider_name()}")
       print(f"Supported models: {provider.get_supported_models()}")
       
       assert isinstance(provider, GroqProvider)
       assert "llama-3.3-70b-versatile" in provider.get_supported_models()
       
       # Test model support check
       assert provider.supports_model("llama-3.3-70b-versatile") is True
       assert provider.supports_model("gpt-4") is False
       
       print("\n✅ Factory working correctly")
   
   if __name__ == "__main__":
       test_factory()
   ```

2. Run test:
   ```bash
   python test_factory.py
   ```

**Expected Output:**
```
Provider type: GroqProvider
Provider name: groqprovider
Supported models: ['llama-3.3-70b-versatile', 'llama-3.1-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768', 'gemma2-9b-it']

✅ Factory working correctly
```

**Verification:**
- [x] Correct provider type instantiated
- [x] Supported models list not empty
- [x] Model support check works

---

## Error Cases to Test

### Missing API Key

```python
import os
from app.ai.llm import ProviderFactory
from app.ai.llm.errors import LLMConfigurationError

# Temporarily remove API key
original_key = os.environ.pop("GROQ_API_KEY", None)

try:
    provider = ProviderFactory.create_text_provider("groq")
    assert False, "Should have raised LLMConfigurationError"
except LLMConfigurationError as e:
    print(f"✅ Correctly raised: {e.message}")
finally:
    if original_key:
        os.environ["GROQ_API_KEY"] = original_key
```

### Invalid Model

```python
import asyncio
from app.ai.llm import ProviderFactory, LLMRequest

async def test_invalid_model():
    provider = ProviderFactory.create_text_provider("groq")
    
    request = LLMRequest(
        prompt="Test",
        model="nonexistent-model",
        timeout_seconds=30
    )
    
    response = await provider.generate_text(request)
    
    assert response.success is False
    assert response.error.type == "provider_error"
    print("✅ Invalid model handled correctly")

asyncio.run(test_invalid_model())
```

### Schema Validation Failure

```python
import asyncio
import json
from app.ai.llm import ProviderFactory, LLMRequest

async def test_schema_mismatch():
    provider = ProviderFactory.create_text_provider("groq")
    
    request = LLMRequest(
        prompt="Return JSON with field 'wrong_field': 'value'",
        model="llama-3.3-70b-versatile",
        json_mode=True,
        temperature=0.0,
        timeout_seconds=30,
        schema={
            "type": "object",
            "required": ["expected_field"],
            "properties": {
                "expected_field": {"type": "string"}
            }
        }
    )
    
    response = await provider.generate_structured(request)
    
    if not response.success:
        print(f"✅ Schema validation failed as expected: {response.error.message}")
        assert response.error.type == "schema_validation"

asyncio.run(test_schema_mismatch())
```

---

## Running Automated Tests

### Unit Tests

```bash
# Run all unit tests
pytest tests/unit/ai/llm/ -v

# Run specific test file
pytest tests/unit/ai/llm/test_contracts.py -v

# Run with coverage
pytest tests/unit/ai/llm/ --cov=app.ai.llm --cov-report=html
```

### Integration Tests

```bash
# Requires API keys set in environment

# Run all integration tests
pytest tests/integration/ai/llm/ -v

# Run Groq integration tests only
pytest tests/integration/ai/llm/test_groq_integration.py -v

# Skip tests if no API key
pytest tests/integration/ai/llm/ -v -m "not slow"
```

---

## Troubleshooting

### Issue: "Module not found" errors

**Solution:**
```bash
# Ensure PYTHONPATH includes project root
export PYTHONPATH=/home/jithsungh/projects/ai_interviewer:$PYTHONPATH
```

### Issue: Timeout errors with Groq

**Solution:**
- Increase `timeout_seconds` in request (default: 60s)
- Check network connectivity
- Verify API key is valid

### Issue: Embedding service connection refused

**Solution:**
- Verify embedding service is running: `curl http://localhost:8080/health`
- Check `EMBEDDING_MODEL_URL` environment variable
- Ensure firewall allows connection

### Issue: JSON mode not working

**Solution:**
- Ensure prompt explicitly requests JSON
- Add schema to guide output structure
- Use temperature=0 for more consistent formatting

---

## Performance Benchmarks

Expected latencies (p95):

- **Text generation (100 tokens):** <2s
- **Structured output (JSON):** <3s
- **Embedding generation:** <500ms
- **Deterministic mode:** Similar to standard (temperature doesn't affect latency significantly)

**Note:** Groq is extremely fast due to LPU architecture. Other providers may be slower.

---

## Next Steps

After manual testing:

1. **Implement remaining providers:**
   - Gemini provider (follow Groq pattern)
   - OpenAI provider (follow Groq pattern)
   - Anthropic provider (follow Groq pattern)

2. **Add retry logic:**
   - Exponential backoff for rate limits
   - Circuit breaker for provider failures

3. **Add caching (optional):**
   - Cache deterministic responses
   - TTL-based expiration

4. **Add monitoring:**
   - Prometheus metrics for token usage
   - Latency histograms
   - Error rate tracking

---

## Contact

For questions or issues:
- Review [REQUIREMENTS.md](REQUIREMENTS.md)
- Check [TESTING.md](TESTING.md)
- Review [REPO_ALIGNMENT_REPORT.md](REPO_ALIGNMENT_REPORT.md)
