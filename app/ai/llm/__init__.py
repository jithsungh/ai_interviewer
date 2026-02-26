"""
AI LLM Module

Provider-agnostic LLM abstraction layer.
Provides unified interface for Groq, Gemini, OpenAI, Anthropic.
"""

from .contracts import (
    LLMRequest,
    LLMResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    TelemetryData,
    LLMError,
    LLMProvider,
    LLMErrorType,
    ClarificationRequest,
    ClarificationResponse
)

from .errors import (
    LLMProviderError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMSchemaValidationError,
    LLMContentFilterError,
    LLMModelNotFoundError,
    LLMContextLengthError,
    LLMEmbeddingServiceError,
    LLMConfigurationError
)

from .base_provider import (
    BaseLLMProvider,
    BaseEmbeddingProvider,
    BaseTranscriptionProvider,
    ProviderCapabilities
)

from .provider_factory import (
    ProviderFactory,
    get_groq_provider,
    get_default_provider
)

from .providers import (
    GroqProvider,
    GeminiProvider,
    OpenAIProvider,
    AnthropicProvider,
   EmbeddingProvider
)

__all__ = [
    # Contracts
    "LLMRequest",
    "LLMResponse",
    "EmbeddingRequest",
    "EmbeddingResponse",
    "TranscriptionRequest",
    "TranscriptionResponse",
    "TelemetryData",
    "LLMError",
    "LLMProvider",
    "LLMErrorType",
    "ClarificationRequest",
    "ClarificationResponse",
    
    # Errors
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    "LLMSchemaValidationError",
    "LLMContentFilterError",
    "LLMModelNotFoundError",
    "LLMContextLengthError",
    "LLMEmbeddingServiceError",
    "LLMConfigurationError",
    
    # Base classes
    "BaseLLMProvider",
    "BaseEmbeddingProvider",
    "BaseTranscriptionProvider",
    "ProviderCapabilities",
    
    # Factory
    "ProviderFactory",
    "get_groq_provider",
    "get_default_provider",
    
    # Providers
    "GroqProvider",
    "GeminiProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "EmbeddingProvider",
]
