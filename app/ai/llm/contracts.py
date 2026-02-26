"""
LLM Module Contracts (DTOs)

Defines request/response contracts for LLM provider interactions.
All providers MUST return responses matching these contracts.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers"""
    GROQ = "groq"
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class LLMErrorType(str, Enum):
    """LLM error classification"""
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    AUTHENTICATION = "authentication"
    PROVIDER_ERROR = "provider_error"
    SCHEMA_VALIDATION = "schema_validation"
    UNKNOWN = "unknown"


@dataclass
class LLMRequest:
    """
    Unified request contract for LLM text generation.
    
    All provider-specific parameters normalized to this structure.
    """
    
    # Required
    prompt: str  # User prompt (main query)
    model: str  # Provider-specific model ID
    
    # Optional prompting
    system_prompt: Optional[str] = None  # System message (if supported)
    
    # Generation parameters
    temperature: float = 0.7  # 0.0-2.0, controls randomness
    max_tokens: Optional[int] = None  # Maximum completion tokens
    top_p: float = 1.0  # Nucleus sampling threshold
    
    # Structured output
    json_mode: bool = False  # Request JSON response
    schema: Optional[Dict[str, Any]] = None  # JSON schema for validation
    
    # Control parameters
    timeout_seconds: int = 60  # Request timeout
    deterministic: bool = False  # If True, sets temperature=0, top_p=1, seed=0
    
    # Context
    request_id: Optional[str] = None  # Request correlation ID
    organization_id: Optional[int] = None  # For telemetry/cost tracking
    
    def __post_init__(self):
        """Validate and normalize request"""
        # Enforce deterministic mode
        if self.deterministic:
            self.temperature = 0.0
            self.top_p = 1.0
        
        # Validate ranges
        if not (0.0 <= self.temperature <= 2.0):
            raise ValueError(f"temperature must be in [0.0, 2.0], got {self.temperature}")
        
        if not (0.0 <= self.top_p <= 1.0):
            raise ValueError(f"top_p must be in [0.0, 1.0], got {self.top_p}")
        
        if not (10 <= self.timeout_seconds <= 300):
            raise ValueError(f"timeout_seconds must be in [10, 300], got {self.timeout_seconds}")
        
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError(f"max_tokens must be > 0, got {self.max_tokens}")
        
        # JSON mode requires schema (best practice)
        if self.json_mode and not self.schema:
            # Allow without schema, but log warning in provider
            pass


@dataclass
class TelemetryData:
    """
    Telemetry data for LLM operations.
    
    Returned with every response (success or failure).
    Caller is responsible for persisting this data.
    """
    
    # Core metrics
    model_id: str
    provider: str  # groq | gemini | openai | anthropic | local
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int  # Computed: prompt + completion
    latency_ms: int  # Wall time from request start to end
    
    # Success/failure
    success: bool
    error_type: Optional[str] = None  # If success=False
    retry_count: int = 0
    
    # Context
    timestamp: datetime = field(default_factory=lambda: datetime.utcnow())
    deterministic: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    request_id: Optional[str] = None
    organization_id: Optional[int] = None
    
    # Cost estimation (optional)
    estimated_cost_usd: Optional[float] = None
    
    def __post_init__(self):
        """Validate telemetry data"""
        if self.prompt_tokens < 0:
            self.prompt_tokens = 0
        if self.completion_tokens < 0:
            self.completion_tokens = 0
        self.total_tokens = self.prompt_tokens + self.completion_tokens


@dataclass
class LLMError:
    """
    LLM error information.
    
    Wraps provider-specific errors in unified format.
    """
    
    type: str  # timeout | rate_limit | authentication | provider_error | schema_validation | unknown
    message: str
    retryable: bool  # Whether operation should be retried
    provider_error_code: Optional[str] = None  # Provider-specific error code
    provider_error_details: Optional[Dict[str, Any]] = None  # Raw provider error


@dataclass
class LLMResponse:
    """
    Unified response contract for LLM operations.
    
    All providers MUST return responses matching this structure.
    """
    
    success: bool
    text: Optional[str] = None  # Generated text (if success=True)
    finish_reason: Optional[str] = None  # stop | length | content_filter | error
    telemetry: Optional[TelemetryData] = None  # Always included
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional context
    error: Optional[LLMError] = None  # Error details (if success=False)
    raw_response: Optional[Dict[str, Any]] = None  # Provider-specific response (debugging)
    
    def __post_init__(self):
        """Validate response consistency"""
        if self.success and not self.text:
            raise ValueError("Success response must include text")
        if not self.success and not self.error:
            raise ValueError("Failure response must include error")


@dataclass
class EmbeddingRequest:
    """
    Request contract for embedding generation.
    """
    
    text: str  # Text to embed (or list of texts)
    model: str = "all-mpnet-base-v2"  # Embedding model ID
    timeout_seconds: int = 30  # Request timeout
    request_id: Optional[str] = None
    organization_id: Optional[int] = None
    
    def __post_init__(self):
        """Validate embedding request"""
        if not self.text:
            raise ValueError("text cannot be empty")
        if not (10 <= self.timeout_seconds <= 300):
            raise ValueError(f"timeout_seconds must be in [10, 300], got {self.timeout_seconds}")


@dataclass
class EmbeddingResponse:
    """
    Response contract for embedding generation.
    """
    
    success: bool
    embedding: Optional[List[float]] = None  # Vector embedding (if success=True)
    dimensions: Optional[int] = None  # Embedding dimensionality
    telemetry: Optional[TelemetryData] = None
    error: Optional[LLMError] = None  # Error details (if success=False)
    raw_response: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate response"""
        if self.success and not self.embedding:
            raise ValueError("Success response must include embedding")
        if self.success and self.embedding:
            self.dimensions = len(self.embedding)
        if not self.success and not self.error:
            raise ValueError("Failure response must include error")


@dataclass
class TranscriptionRequest:
    """
    Request contract for audio transcription.
    """
    
    audio_data: bytes  # Raw audio bytes
    audio_format: str  # wav | mp3 | opus | etc.
    language: Optional[str] = None  # ISO 639-1 code (e.g., 'en')
    model: str = "whisper-1"
    timeout_seconds: int = 60
    request_id: Optional[str] = None
    organization_id: Optional[int] = None
    
    def __post_init__(self):
        """Validate transcription request"""
        if not self.audio_data:
            raise ValueError("audio_data cannot be empty")
        if not (10 <= self.timeout_seconds <= 300):
            raise ValueError(f"timeout_seconds must be in [10, 300], got {self.timeout_seconds}")


@dataclass
class TranscriptionResponse:
    """
    Response contract for audio transcription.
    """
    
    success: bool
    text: Optional[str] = None  # Transcribed text
    language: Optional[str] = None  # Detected language (if not provided)
    confidence: Optional[float] = None  # Transcription confidence (0.0-1.0)
    telemetry: Optional[TelemetryData] = None
    error: Optional[LLMError] = None
    raw_response: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate response"""
        if self.success and not self.text:
            raise ValueError("Success response must include text")
        if not self.success and not self.error:
            raise ValueError("Failure response must include error")


@dataclass
class ClarificationRequest:
    """
    Request contract for candidate clarification (strict mode).
    
    Used for interview clarifications with strict policy enforcement.
    """
    
    original_question: str
    candidate_clarification_request: str
    model: str
    submission_id: int
    exchange_id: int
    temperature: float = 0.0  # Always deterministic for fairness
    max_response_length: int = 120  # Word limit
    timeout_seconds: int = 30
    request_id: Optional[str] = None
    organization_id: Optional[int] = None
    
    def __post_init__(self):
        """Validate clarification request"""
        if not self.original_question:
            raise ValueError("original_question cannot be empty")
        if not self.candidate_clarification_request:
            raise ValueError("candidate_clarification_request cannot be empty")
        # Enforce deterministic mode for clarifications (fairness)
        if self.temperature != 0.0:
            raise ValueError("Clarifications must use temperature=0.0 for fairness")


@dataclass
class ClarificationResponse:
    """
    Response contract for candidate clarification.
    """
    
    success: bool
    clarification_text: Optional[str] = None
    policy_compliant: bool = True  # Whether response passed policy validation
    policy_violations: List[str] = field(default_factory=list)  # List of violations detected
    word_count: Optional[int] = None
    telemetry: Optional[TelemetryData] = None
    error: Optional[LLMError] = None
    raw_response: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Validate response"""
        if self.success and not self.clarification_text:
            raise ValueError("Success response must include clarification_text")
        if self.success and self.clarification_text:
            self.word_count = len(self.clarification_text.split())
        if not self.success and not self.error:
            raise ValueError("Failure response must include error")
