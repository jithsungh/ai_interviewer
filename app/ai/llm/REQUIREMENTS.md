# AI LLM Layer Requirements

## 1. Purpose

The LLM layer provides **provider abstractions** for Large Language Model interactions.

**Core Responsibilities:**

- Define base interface contract for all LLM providers
- Implement provider-specific adapters (OpenAI, Anthropic, local models)
- Handle API authentication and connection management
- Convert provider-specific responses to unified format
- Implement timeout enforcement at HTTP client level
- Support text generation, structured generation, and embeddings

**Design Principle:** All LLM providers implement the same interface. Swapping providers requires zero changes in calling code.

---

## 2. Owned Tables

**None** - LLM layer is stateless infrastructure

---

## 3. Input Constraints

### Base Provider Interface

Every provider MUST implement:

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: int = 60,
        **kwargs
    ) -> LLMResponse:
        """Generate unstructured text response"""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: dict,
        model: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        timeout_seconds: int = 60,
        **kwargs
    ) -> LLMResponse:
        """Generate JSON response matching schema"""
        pass

    @abstractmethod
    def generate_embedding(
        self,
        text: str,
        model: str = "default",
        timeout_seconds: int = 30
    ) -> EmbeddingResponse:
        """Generate vector embedding for text"""
        pass

    @abstractmethod
    def transcribe_audio(
        self,
        audio_data: bytes,
        model: str = "default",
        language: Optional[str] = None,
        timeout_seconds: int = 120
    ) -> TranscriptionResponse:
        """Transcribe audio to text"""
        pass
```

### Input Validation

- `prompt` MUST be non-empty string
- `model` MUST be valid model ID for provider
- `temperature` MUST be in range [0.0, 2.0]
- `max_tokens` (if provided) MUST be positive integer within model limits
- `timeout_seconds` MUST be in range [10, 300]
- `schema` (for structured generation) MUST be valid JSON schema dict

### Provider-Specific Requirements

#### OpenAI Provider

- API key from environment: `OPENAI_API_KEY`
- Supported models: `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo`, `gpt-4o`
- Structured output: Use `response_format={"type": "json_object"}` + schema in prompt
- Embeddings: `text-embedding-ada-002`, `text-embedding-3-small`, `text-embedding-3-large`
- Audio: `whisper-1`

#### Anthropic Provider

- API key from environment: `ANTHROPIC_API_KEY`
- Supported models: `claude-3-opus`, `claude-3-sonnet`, `claude-3-haiku`
- Structured output: Prompt engineering with schema validation
- No native embedding support (not implemented)
- No native audio support (not implemented)

#### Local Model Provider (Future)

- Model path from config
- Self-hosted inference endpoint
- Structured output via constrained decoding or post-validation

---

## 4. Output Guarantees

### LLMResponse Structure

```python
@dataclass
class LLMResponse:
    success: bool
    data: Optional[dict]  # Structured output or {"content": str} for text
    telemetry: TelemetryData
    error: Optional[LLMError] = None
    raw_response: Optional[dict] = None  # Provider-specific response for debugging
```

### TelemetryData Structure

```python
@dataclass
class TelemetryData:
    model_id: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_ms: int
    retry_count: int
    timestamp: datetime
    deterministic: bool
    temperature: float
```

### EmbeddingResponse Structure

```python
@dataclass
class EmbeddingResponse:
    success: bool
    embedding: Optional[List[float]]  # Vector dimensions vary by model
    dimensions: int
    model_id: str
    telemetry: TelemetryData
    error: Optional[LLMError] = None
```

### TranscriptionResponse Structure

```python
@dataclass
class TranscriptionResponse:
    success: bool
    text: Optional[str]
    language: Optional[str]
    confidence: Optional[float]
    model_id: str
    telemetry: TelemetryData
    error: Optional[LLMError] = None
```

### Error Response Structure

```python
@dataclass
class LLMError:
    type: str  # timeout | rate_limit | authentication | provider_error | schema_validation | unknown
    message: str
    retryable: bool
    provider_error_code: Optional[str] = None
    provider_error_details: Optional[dict] = None
```

### Performance Guarantees

- Timeout MUST be enforced at HTTP client level (not just provider SDK)
- Response MUST include telemetry even on failure
- Provider-specific errors MUST be wrapped in LLMError
- Success/failure MUST be explicit boolean, no implicit None checks

---

## 5. Invariants

### Interface Contract Invariant

```
ALL providers MUST implement BaseLLMProvider interface
NO provider-specific methods may be exposed publicly
```

**Enforcement:** Abstract base class with `@abstractmethod`, mypy type checking

### Timeout Enforcement Invariant

```
EVERY provider call MUST have explicit timeout
Timeout handled at HTTP client level (requests timeout, httpx timeout)
Provider SDK timeout is fallback, not primary
```

**Enforcement:** Timeout wrapper decorator on all provider methods

### Response Normalization Invariant

```
ALL providers MUST return LLMResponse with same structure
Provider-specific response stored in raw_response field only
```

**Enforcement:** Provider adapter layer normalizes before returning

### Telemetry Collection Invariant

```
Token usage MUST be recorded even on failure (partial telemetry)
Latency measured from call start to response/error
```

**Enforcement:** Try/finally block in provider base class

---

## 6. Forbidden Behaviors

### Provider Coupling

- SHALL NOT expose provider-specific classes/types in public API
- SHALL NOT allow provider-specific parameters in base interface
- SHALL NOT assume provider SDK behavior (always wrap exceptions)
- SHALL NOT hardcode API keys (environment/vault only)

### Error Propagation

- SHALL NOT raise provider-specific exceptions (wrap in LLMError)
- SHALL NOT let provider SDK errors bubble up unwrapped
- SHALL NOT return None on failure (explicit error in response)

### State Management

- SHALL NOT cache responses in provider layer (caching is separate concern)
- SHALL NOT maintain session state across calls
- SHALL NOT share HTTP clients unsafely across threads

### Schema Validation

- SHALL NOT skip schema validation for structured generation
- SHALL NOT silently fallback to unstructured on schema failure
- SHALL NOT modify schema to "fix" provider limitations

---

## 7. Dependent Modules

### Dependencies (Inbound)

- `openai` - OpenAI Python SDK
- `anthropic` - Anthropic Python SDK
- `requests` or `httpx` - HTTP client with timeout support
- `shared/errors` - Exception types (TimeoutError, RateLimitError, etc.)
- `shared/observability` - Logging
- `pydantic` - Response validation

### Dependents (Outbound)

- Parent `ai` module - Uses providers via factory
- `ai/telemetry` - Receives telemetry data from providers

### External Systems

- **OpenAI API** (`https://api.openai.com/v1`)
- **Anthropic API** (`https://api.anthropic.com/v1`)
- **Local Model Endpoint** (future, configurable URL)

---

## 8. Event Contracts Emitted

### Provider Call Metrics

```json
{
  "event": "llm.provider.call.started",
  "provider": "openai",
  "model": "gpt-4",
  "method": "generate_text",
  "timestamp": "2026-02-13T10:30:00Z"
}
```

```json
{
  "event": "llm.provider.call.completed",
  "provider": "openai",
  "model": "gpt-4",
  "method": "generate_structured",
  "tokens": 1630,
  "latency_ms": 3420,
  "timestamp": "2026-02-13T10:30:05Z"
}
```

```json
{
  "event": "llm.provider.call.failed",
  "provider": "anthropic",
  "model": "claude-3-sonnet",
  "error_type": "timeout",
  "latency_ms": 60000,
  "timestamp": "2026-02-13T10:31:00Z"
}
```

---

## 9. Acceptance Criteria

### Interface Contract

- [ ] OpenAI provider implements BaseLLMProvider fully
- [ ] Anthropic provider implements BaseLLMProvider fully
- [ ] Provider factory can instantiate any provider by name
- [ ] Switching provider in config requires zero code changes

### Timeout Enforcement

- [ ] All providers enforce timeout at HTTP client level
- [ ] Timeout exceeded raises TimeoutError (wrapped in LLMError)
- [ ] Timeout does not rely solely on provider SDK
- [ ] Partial telemetry recorded even when timeout occurs

### Response Normalization

- [ ] OpenAI responses normalized to LLMResponse
- [ ] Anthropic responses normalized to LLMResponse
- [ ] Provider-specific response accessible via raw_response field
- [ ] Telemetry structure identical across providers

### Error Handling

- [ ] OpenAI rate limit → LLMError(type="rate_limit", retryable=True)
- [ ] Anthropic authentication failure → LLMError(type="authentication", retryable=False)
- [ ] Network timeout → LLMError(type="timeout", retryable=True)
- [ ] Invalid schema → LLMError(type="schema_validation", retryable=True)
- [ ] Provider-specific error codes preserved in LLMError

### Structured Generation

- [ ] OpenAI structured generation uses JSON mode + schema prompt
- [ ] Anthropic structured generation uses prompt engineering
- [ ] Schema validation applied to all structured outputs
- [ ] Invalid JSON triggers retry (handled by retry layer)

### Embedding Generation

- [ ] OpenAI embedding returns vector of correct dimensions
- [ ] Embedding telemetry includes token count
- [ ] Unsupported provider returns clear error (not implemented)

### Audio Transcription

- [ ] OpenAI Whisper transcribes audio correctly
- [ ] Language detection works (if not specified)
- [ ] Confidence score included if available
- [ ] Unsupported provider returns clear error

### Thread Safety

- [ ] Provider HTTP clients are thread-safe
- [ ] Concurrent calls to same provider do not interfere
- [ ] Telemetry recording has no race conditions

---

## 10. Testing Guide

See [TESTING.md](TESTING.md) for comprehensive testing strategies.

**Key Testing Requirements:**

- Mock provider SDK calls (no real API in unit tests)
- Test timeout enforcement independently of provider SDK
- Verify response normalization across providers
- Test error wrapping for all provider-specific errors
- Validate thread safety with concurrent requests

---

## 11. Edge Cases

### Provider-Specific Quirks

- **OpenAI:** `max_tokens` exceeded returns truncated output (not error)
- **Anthropic:** Context window exceeded returns error (not truncation)
- **OpenAI:** Structured output may return plain text if model ignores instruction
- **Anthropic:** No native JSON mode, relies on prompting

### Token Counting Discrepancies

- Provider-reported tokens may differ from local count
- Always use provider-reported tokens for billing accuracy
- If provider doesn't report tokens, estimate conservatively

### Model Availability

- Model deprecated → Fallback to alternative (configured in model_map)
- Model not available in region → Clear error, no silent fallback
- Beta model access required → Authentication error with specific message

### Timeout Edge Cases

- Provider SDK hangs → HTTP client timeout enforces limit
- Streaming response interrupted → Capture partial response, mark as failed
- Connection established but no response → Read timeout enforced

### Structured Output Failures

- Model returns text instead of JSON → Parse failure, retry with stronger schema prompt
- JSON valid but schema invalid → Schema validation failure, retry
- Model prefixes JSON with explanation → Strip non-JSON content, parse remainder

---

## 12. Concurrency Concerns

### HTTP Client Thread Safety

- Use session pooling (requests.Session or httpx.Client)
- Configure max connections per host
- Connection pooling shared across threads safely

### Rate Limiting

- Provider rate limits apply globally (not per thread)
- Implement token bucket at provider level
- Coordinate retries across threads (exponential backoff with jitter)

### API Key Rotation

- If key rotation implemented, ensure atomic swap
- No race condition between key expiry and new key activation

### Telemetry Recording

- Token count increments must be atomic (if aggregated)
- Latency measurements use thread-safe timers
- Concurrent telemetry writes do not corrupt data

---

## 13. Provider Configuration

### Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...  # Optional

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Default models
DEFAULT_TEXT_MODEL=gpt-4
DEFAULT_EMBEDDING_MODEL=text-embedding-ada-002
DEFAULT_AUDIO_MODEL=whisper-1

# Timeouts
LLM_DEFAULT_TIMEOUT=60
LLM_MAX_TIMEOUT=300
```

### Model Configuration (Database or Config File)

```yaml
providers:
  openai:
    text_models:
      - gpt-4
      - gpt-4-turbo
      - gpt-3.5-turbo
    embedding_models:
      - text-embedding-ada-002
      - text-embedding-3-small
    audio_models:
      - whisper-1

  anthropic:
    text_models:
      - claude-3-opus
      - claude-3-sonnet
      - claude-3-haiku

model_fallbacks:
  gpt-4: gpt-4-turbo
  claude-3-opus: claude-3-sonnet
```

---

## 14. Provider Selection Strategy

### Explicit Override

Calling code specifies provider explicitly:

```python
provider = llm_factory.get_provider("openai")
response = provider.generate_text(...)
```

### Default from Prompt Template

Prompt template specifies preferred model:

```sql
SELECT model_id FROM prompt_templates WHERE prompt_type='evaluation' AND is_active=true
```

Provider inferred from model ID.

### Organization-Level Override

```sql
SELECT preferred_provider FROM organizations WHERE id=?
```

If set, override default provider for all AI calls.

### Feature Flag Experimentation

```python
if feature_flag("use_claude_for_evaluation", org_id):
    provider = "anthropic"
else:
    provider = "openai"
```

---

**End of AI LLM Layer Requirements**
