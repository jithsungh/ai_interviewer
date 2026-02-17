# AI LLM Layer Requirements

**See Also:** [Clarifications Architecture](../../docs/CLARIFICATIONS-ARCHITECTURE.md) - High-level overview of clarification LLM contract, fairness, and audit logging.

## 1. Purpose

The LLM layer provides **provider abstractions** for Large Language Model interactions.

**Core Responsibilities:**

- Define base interface contract for all LLM providers
- Implement provider-specific adapters (Groq, Gemini, OpenAI, Anthropic)
- Implement response formatters for each provider's output structure
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

#### Groq Provider (Development Primary)

- API key from environment: `GROQ_API_KEY`
- API endpoint: `https://api.groq.com/openai/v1`
- Supported models:
  - `llama-3.3-70b-versatile` (recommended for general use)
  - `openai-gpt-oss-120b` (using this probably for large tasks)
  - `llama-3.1-70b-versatile`
  - `llama-3.1-8b-instant` (fast inference)
  - `mixtral-8x7b-32768` (large context)
  - `gemma2-9b-it`
- Structured output:
  - Native JSON mode support via `response_format={"type": "json_object"}`
  - Schema enforcement via prompt engineering
  - Response formatter validates and normalizes output
- Embeddings: Not supported natively
- Audio: Not supported natively
- Key features:
  - Extremely fast inference (optimized LPU architecture)
  - Cost-effective for development
  - OpenAI-compatible API format
- Response formatter requirements:
  - Parse streaming and non-streaming responses
  - Handle rate limit headers
  - Extract usage metadata (prompt_tokens, completion_tokens, total_tokens)
  - Normalize error codes to standard format

#### Gemini Provider (Development Primary)

- API key from environment: `GEMINI_API_KEY`
- API endpoint: `https://generativelanguage.googleapis.com/v1beta`
- Supported models:
  - `gemini-2.0-flash-exp` (recommended, fast and capable)
  - `gemini-2.5-pro` (advanced reasoning)
  - `gemini-2.5-flash` (fast responses)
  - `gemini-2.5-flash-8b` (lightweight)
  - `gemini-3.0-pro` (latest, most capable)
- Structured output:
  - Native JSON mode via `generation_config.response_mime_type = "application/json"`
  - Schema validation via `generation_config.response_schema`
  - Response formatter validates against expected schema
- Embeddings:
  - `text-embedding-004` (768 dimensions)
  - `embedding-001` (legacy, 768 dimensions)
- Audio: Not implemented for this use case
- Key features:
  - Large context windows (up to 2M tokens)
  - Multimodal capabilities (text, images, video)
  - Cost-effective for development
  - Grounding with Google Search (optional)
- Response formatter requirements:
  - Parse Google-specific response structure
  - Handle safety ratings and content filtering
  - Extract usage metadata (promptTokenCount, candidatesTokenCount, totalTokenCount)
  - Convert finish_reason to standard format
  - Handle blocked responses gracefully

#### OpenAI Provider (Production Primary)

- API key from environment: `OPENAI_API_KEY`
- API endpoint: `https://api.openai.com/v1`
- Supported models:
  - `gpt-4o` (recommended, latest GPT-4 optimized)
  - `gpt-4-turbo` (advanced reasoning)
  - `gpt-4` (original GPT-4)
  - `gpt-3.5-turbo` (cost-effective)
- Structured output:
  - Native JSON mode via `response_format={"type": "json_object"}`
  - Structured Outputs with schema via `response_format={"type": "json_schema", "json_schema": {...}}`
  - Response formatter validates JSON structure
- Embeddings:
  - `text-embedding-3-large` (3072 dimensions, best quality)
  - `text-embedding-3-small` (1536 dimensions, cost-effective)
  - `text-embedding-ada-002` (1536 dimensions, legacy)
- Audio:
  - `whisper-1` (speech-to-text)
  - `tts-1` / `tts-1-hd` (text-to-speech, optional)
- Key features:
  - Best-in-class reasoning and instruction following
  - Function calling capabilities
  - Vision capabilities (GPT-4V)
  - Production-ready reliability
- Response formatter requirements:
  - Parse choices array and handle multiple completions
  - Extract usage data (prompt_tokens, completion_tokens, total_tokens)
  - Handle finish_reason mapping (stop, length, content_filter, function_call)
  - Support streaming response aggregation
  - Handle function calling responses (if enabled)

#### Anthropic Provider (Production Fallback)

- API key from environment: `ANTHROPIC_API_KEY`
- API endpoint: `https://api.anthropic.com/v1`
- Supported models:
  - `claude-3-5-sonnet-20241022` (recommended, latest Sonnet)
  - `claude-3-5-haiku-20241022` (fast, cost-effective)
  - `claude-3-opus-20240229` (most capable, expensive)
  - `claude-3-sonnet-20240229` (balanced)
  - `claude-3-haiku-20240307` (fast responses)
- Structured output:
  - No native JSON mode
  - Schema enforcement via system prompt + user prompt engineering
  - Response formatter validates and extracts JSON from markdown code blocks
  - Extended Thinking mode for complex reasoning (claude-3-7-sonnet)
- Embeddings: Not supported natively (use Voyage AI integration or third-party)
- Audio: Not supported natively
- Key features:
  - Long context windows (200K tokens)
  - Strong reasoning and analysis capabilities
  - High reliability and safety
  - Extended Thinking mode for complex problems
- Response formatter requirements:
  - Parse content array with text and tool_use blocks
  - Extract JSON from markdown code blocks (```json ... ```)
  - Handle stop_reason mapping (end_turn, max_tokens, stop_sequence)
  - Extract usage data (input_tokens, output_tokens)
  - Support Claude-specific thinking blocks
  - Handle multi-turn conversation format

#### Local Model Provider (Future)

- Model path from config
- Self-hosted inference endpoint
- Structured output via constrained decoding or post-validation

---

## 4. Clarification Prompt Contract (Strict Mode)

### Purpose

Define the **bounded, auditable contract** for LLM clarification requests during interviews.

> **Every clarification must be fair, safe, and auditable.**
> **No LLM drift. No leaked hints. No moving goalposts.**

---

### Clarification System Prompt (Template)

```
You are a **clarification assistant** for technical interviews.

ROLE: You answer candidate questions about the interview question, NOT solve the problem.

ORIGINAL QUESTION:
{original_question}

CANDIDATE'S CLARIFICATION REQUEST:
{candidate_clarification_request}

---

YOU MAY:
✓ Rephrase the question in different words
✓ Define ambiguous terms (e.g., "optimal" means fewest operations)
✓ Clarify constraints (e.g., "Input is sorted")
✓ Ask the candidate to clarify their OWN understanding

YOU MAY RARELY:
~ Provide ONE abstract analogy per question (e.g., "like sorting cards")
  - Analogy must NOT show solution structure
  - Analogy must be simple and conceptual

YOU MUST NEVER:
✗ Suggest algorithms (use DFS, use dynamic programming, etc.)
✗ Suggest data structures (hash table, queue, tree, etc.)
✗ Describe steps or approach ("first you would", "next do", etc.)
✗ Give hints about structure ("you'll need recursion", "think about trees")
✗ Validate their attempt ("that's right", "you're on the right track")
✗ Use encouraging language ("great question", "excellent thinking")
✗ Describe the answer or solution
✗ Provide code examples or solution patterns
✗ Suggest testing approaches or edge cases to consider

---

CONSTRAINTS:
- Maximum response length: 120 words
- Response format: Natural language only (no JSON, no scoring)
- No meta-commentary (don't mention these rules)
- If you cannot provide safe clarification, ask candidate to rephrase their question

---

Provide a brief, direct clarification.
```

---

### Clarification Request Contract

```python
@dataclass
class ClarificationRequestContract:
    """
    Strict contract for clarification requests.
    All clarifications MUST conform to this contract.
    """
    
    # Identity
    submission_id: int                   # REQUIRED: Audit trail linkage
    exchange_sequence: int               # REQUIRED: Question number
    question_id: int                     # REQUIRED: For traceability
    
    # Question Context
    original_question: str               # REQUIRED: Verbatim question
    candidate_clarification_request: str # REQUIRED: How they asked
    
    # Counter
    clarification_number: int            # REQUIRED: 1, 2, or 3 (0-indexed)
    
    # Policy Constraints
    constraints: ClarificationConstraints
    
    # Metadata
    timestamp: datetime                  # When requested
    asr_confidence: Optional[float] = None  # Transcription confidence


@dataclass
class ClarificationConstraints:
    """Hard bounds for clarification responses."""
    
    max_words: int = 120
    allow_analogy: bool = True
    max_analogies: int = 1              # Per question
    allow_hint: bool = False             # RECOMMEND: False
    max_hints: int = 0                   # If hints enabled, max per question
    
    # Prohibition list (must not appear in response)
    prohibitions: List[str] = None       # Auto-set from above
    
    def __post_init__(self):
        if self.prohibitions is None:
            self.prohibitions = [
                "algorithm", "approach", "dynamic programming", "dfs", "bfs", 
                "dijkstra", "recursion", "hash table", "queue", "stack", "tree",
                "linked list", "binary search", "bubble sort", "merge sort",
                "would", "suggest", "use", "try", "first", "next", "then",
                "you're right", "correct", "that's", "good", "excellent",
                "right track", "on the right", "brilliant", "great"
            ]
```

---

### Clarification Response Contract

```python
@dataclass
class ClarificationResponseContract:
    """
    Response from LLM for clarification.
    MUST pass validation before delivering to client.
    """
    
    # Content
    clarification_text: str              # LLM response
    word_count: int                      # Actual word count
    
    # Compliance
    violates_policy: bool                # True if policy violation
    violation_reason: Optional[str] = None  # If violated
    contains_analogy: bool = False       # Did we use analogy?
    contains_hint: bool = False          # Did we give hint?
    
    # Auditing
    model_used: str                      # Which model generated this
    temperature_used: float              # Should be 0.0 or near 0
    telemetry: Optional[dict] = None     # Token usage, latency
```

---

### Validation & Policy Enforcement

```python
class ClarificationValidator:
    """Validate clarification responses against policy."""
    
    PROHIBITED_PATTERNS = {
        "algorithm": r'\b(algorithm|approach|solution|strategy|method)\b',
        "data_structure": r'\b(tree|list|queue|stack|heap|graph|table|hash)\b',
        "hint": r'\b(recursion|recursive|loop|cycle|try|think about|consider)\b',
        "validation": r'\b(right|correct|good|yes|exactly|that[\s\']s|you[\s\']re|on the right)\b',
        "code": r'(\{\{|>>>|code|function|implement|write)',
    }
    
    MAX_WORDS = 120
    MAX_ANALOGIES_PER_QUESTION = 1
    
    def validate(
        self, 
        response: ClarificationResponseContract,
        constraints: ClarificationConstraints
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate response.
        
        Returns:
            (is_valid: bool, violation_reason: Optional[str])
        """
        
        # Check word count
        if response.word_count > constraints.max_words:
            return False, f"Exceeds max words ({response.word_count} > {constraints.max_words})"
        
        # Check prohibited patterns
        text_lower = response.clarification_text.lower()
        for category, pattern in self.PROHIBITED_PATTERNS.items():
            if re.search(pattern, text_lower):
                return False, f"Contains prohibited pattern: {category}"
        
        # Check for prohibited words in constraints list
        for prohibited in constraints.prohibitions:
            if prohibited in text_lower:
                return False, f"Contains prohibited word: {prohibited}"
        
        # If hints disabled, check not present
        if not constraints.allow_hint and response.contains_hint:
            return False, "Hints not allowed but hint detected"
        
        # If analogies limited, check count
        if response.contains_analogy and constraints.max_analogies == 0:
            return False, "Analogies not allowed but analogy detected"
        
        return True, None
```

---

### Temperature = 0 Requirement

```python
async def generate_clarification(
    llm_provider: BaseLLMProvider,
    request: ClarificationRequestContract
) -> ClarificationResponseContract:
    """
    Generate clarification with strict temperature control.
    
    CRITICAL: temperature=0 (or near 0) ensures:
    - Deterministic output (same input → same output)
    - No randomness or creativity
    - Fair treatment across all candidates
    - Reproducible audit trail
    """
    
    system_prompt = CLARIFICATION_SYSTEM_PROMPT_TEMPLATE.format(
        original_question=request.original_question,
        candidate_clarification_request=request.candidate_clarification_request
    )
    
    response = await llm_provider.generate_text(
        prompt="",  # Empty, using system prompt only
        system=system_prompt,
        model="gpt-4o",  # or similar
        temperature=0.0,  # ⭐ DETERMINISTIC
        max_tokens=150,
        timeout_seconds=5
    )
    
    if not response.success:
        raise ClarificationGenerationError(f"LLM call failed: {response.error}")
    
    text = response.data.get('content', '').strip()
    word_count = len(text.split())
    
    # Validate immediately
    validation_response = ClarificationResponseContract(
        clarification_text=text,
        word_count=word_count,
        violates_policy=False,
        model_used=response.telemetry.model_id,
        temperature_used=0.0,
        telemetry=asdict(response.telemetry)
    )
    
    # Run policy validation
    validator = ClarificationValidator()
    is_valid, violation_reason = validator.validate(validation_response, request.constraints)
    
    if not is_valid:
        # Log violation for audit
        log_violation({
            "submission_id": request.submission_id,
            "reason": violation_reason,
            "clarification_text": text
        })
        
        # Return safe fallback
        return ClarificationResponseContract(
            clarification_text="I can't provide that clarification. Could you rephrase your question?",
            word_count=9,
            violates_policy=True,
            violation_reason=violation_reason,
            model_used=response.telemetry.model_id,
            temperature_used=0.0,
            telemetry=asdict(response.telemetry)
        )
    
    return validation_response
```

---

### Audit Logging

Every clarification request MUST be logged immutably:

```python
def log_clarification(
    request: ClarificationRequestContract,
    response: ClarificationResponseContract
) -> None:
    """Log clarification for audit trail."""
    
    audit_entry = {
        "event_type": "clarification",
        "submission_id": request.submission_id,
        "exchange_sequence": request.exchange_sequence,
        "question_id": request.question_id,
        "clarification_number": request.clarification_number,
        "candidate_request": request.candidate_clarification_request,
        "llm_response": response.clarification_text,
        "violates_policy": response.violates_policy,
        "word_count": response.word_count,
        "model": response.model_used,
        "temperature": response.temperature_used,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Write to immutable log (database or append-only file)
    audit_log.append(audit_entry)
```

---

## 6. Output Guarantees

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

## 7. Invariants

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

- `groq` - Groq Python SDK (optional, can use requests directly)
- `google-generativeai` - Google Gemini Python SDK
- `openai` - OpenAI Python SDK (may not require for Groq compatibility)
- `anthropic` - Anthropic Python SDK
- `requests` or `httpx` - HTTP client with timeout support (for direct API calls)
- `shared/errors` - Exception types (TimeoutError, RateLimitError, etc.)
- `shared/observability` - Logging
- `pydantic` - Response validation

### Dependents (Outbound)

- Parent `ai` module - Uses providers via factory
- `ai/telemetry` - Receives telemetry data from providers

### External Systems

- **Groq API** (`https://api.groq.com/openai/v1`)
- **Gemini API** (`https://generativelanguage.googleapis.com/v1beta`)
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

- [ ] Groq provider implements BaseLLMProvider fully
- [ ] Gemini provider implements BaseLLMProvider fully
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

- [ ] Groq responses normalized to LLMResponse
- [ ] Gemini responses normalized to LLMResponse
- [ ] OpenAI responses normalized to LLMResponse
- [ ] Anthropic responses normalized to LLMResponse
- [ ] Provider-specific response accessible via raw_response field
- [ ] Telemetry structure identical across providers

### Error Handling

- [ ] Groq rate limit → LLMError(type="rate_limit", retryable=True)
- [ ] Gemini quota exceeded → LLMError(type="rate_limit", retryable=True)
- [ ] OpenAI rate limit → LLMError(type="rate_limit", retryable=True)
- [ ] Anthropic authentication failure → LLMError(type="authentication", retryable=False)
- [ ] Network timeout → LLMError(type="timeout", retryable=True)
- [ ] Invalid schema → LLMError(type="schema_validation", retryable=True)
- [ ] Provider-specific error codes preserved in LLMError

### Structured Generation

- [ ] Groq structured generation uses JSON mode + schema prompt
- [ ] Gemini structured generation uses native JSON schema support
- [ ] OpenAI structured generation uses JSON mode + schema prompt
- [ ] Anthropic structured generation uses prompt engineering
- [ ] Schema validation applied to all structured outputs
- [ ] Invalid JSON triggers retry (handled by retry layer)

### Embedding Generation

- [ ] Gemini embedding returns vector of correct dimensions (768)
- [ ] OpenAI embedding returns vector of correct dimensions (1536/3072)
- [ ] Embedding telemetry includes token count
- [ ] Unsupported provider returns clear error (not implemented)

### Audio Transcription

- [ ] OpenAI Whisper transcribes audio correctly
- [ ] Language detection works (if not specified)
- [ ] Confidence score included if available
- [ ] Unsupported provider returns clear error

### Response Formatters

- [ ] Groq response formatter extracts usage and content correctly
- [ ] Gemini response formatter handles safety ratings and content filtering
- [ ] OpenAI response formatter handles choices array and function calls
- [ ] Anthropic response formatter extracts JSON from markdown code blocks
- [ ] All formatters normalize finish_reason to standard values
- [ ] All formatters preserve raw_response for debugging

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

- **Groq:** OpenAI-compatible API, extremely fast responses due to LPU architecture
- **Groq:** May return responses faster than expected, ensure proper timeout handling
- **Gemini:** Content filtering may block responses based on safety ratings
- **Gemini:** Required to handle SAFETY_RATING responses and RECITATION blocks
- **Gemini:** Token counting uses promptTokenCount/candidatesTokenCount naming
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
# Groq (Development Primary)
GROQ_API_KEY=gsk_...

# Gemini (Development Primary)
GEMINI_API_KEY=AI...

# OpenAI (Production Primary)
OPENAI_API_KEY=sk-...
OPENAI_ORG_ID=org-...  # Optional

# Anthropic (Production Fallback)
ANTHROPIC_API_KEY=sk-ant-...

# Default models (per environment)
DEFAULT_TEXT_MODEL_DEV=llama-3.3-70b-versatile  # Groq for development
DEFAULT_TEXT_MODEL_PROD=gpt-4o                  # OpenAI for production
DEFAULT_EMBEDDING_MODEL=text-embedding-3-small  # OpenAI
DEFAULT_AUDIO_MODEL=whisper-1                   # OpenAI

# Timeouts
LLM_DEFAULT_TIMEOUT=60
LLM_MAX_TIMEOUT=300
```

### Model Configuration (Database or Config File)

```yaml
providers:
  groq:
    text_models:
      - llama-3.3-70b-versatile
      - llama-3.1-70b-versatile
      - llama-3.1-8b-instant
      - mixtral-8x7b-32768
      - gemma2-9b-it
    embedding_models: []  # Not supported
    audio_models: []      # Not supported

  gemini:
    text_models:
      - gemini-2.0-flash-exp
      - gemini-1.5-pro
      - gemini-1.5-flash
      - gemini-1.5-flash-8b
    embedding_models:
      - text-embedding-004
      - embedding-001
    audio_models: []      # Not implemented

  openai:
    text_models:
      - gpt-4o
      - gpt-4-turbo
      - gpt-4
      - gpt-3.5-turbo
    embedding_models:
      - text-embedding-3-large
      - text-embedding-3-small
      - text-embedding-ada-002
    audio_models:
      - whisper-1

  anthropic:
    text_models:
      - claude-3-5-sonnet-20241022
      - claude-3-5-haiku-20241022
      - claude-3-opus-20240229
      - claude-3-sonnet-20240229
      - claude-3-haiku-20240307
    embedding_models: []  # Not supported
    audio_models: []      # Not supported

model_fallbacks:
  # Development fallbacks
  llama-3.3-70b-versatile: mixtral-8x7b-32768
  gemini-2.0-flash-exp: gemini-1.5-flash

  # Production fallbacks
  gpt-4o: gpt-4-turbo
  claude-3-5-sonnet-20241022: claude-3-sonnet-20240229
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
