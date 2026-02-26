"""
Base LLM Provider Interface

Abstract base class defining contract for all LLM providers.
All provider implementations MUST inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Optional
from .contracts import (
    LLMRequest,
    LLMResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    TelemetryData
)


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers (Groq, Gemini, OpenAI, Anthropic) MUST implement
    these methods with identical signatures.
    
    Design Principle: Swapping providers requires zero changes in calling code.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize provider.
        
        Args:
            api_key: Provider API key (from settings or override)
            **kwargs: Provider-specific configuration
        """
        self.api_key = api_key
        self.provider_name = self.__class__.__name__.replace("Provider", "").lower()
    
    @abstractmethod
    async def generate_text(
        self,
        request: LLMRequest
    ) -> LLMResponse:
        """
        Generate text completion.
        
        Args:
            request: LLMRequest with prompt, model, parameters
        
        Returns:
            LLMResponse with generated text and telemetry
        
        Raises:
            LLMProviderError: Provider-specific error
            LLMTimeoutError: Request timeout
            LLMRateLimitError: Rate limit exceeded
            LLMAuthenticationError: Authentication failed
        
        MUST:
        - Enforce timeout at HTTP client level
        - Record telemetry even on failure
        - Wrap all provider exceptions in LLM-specific errors
        - Return normalized LLMResponse structure
        - Store raw provider response in raw_response field
        """
        pass
    
    @abstractmethod
    async def generate_structured(
        self,
        request: LLMRequest
    ) -> LLMResponse:
        """
        Generate structured output (JSON mode).
        
        Args:
            request: LLMRequest with json_mode=True and optional schema
        
        Returns:
            LLMResponse with JSON-formatted text and telemetry
        
        Raises:
            LLMSchemaValidationError: Response doesn't match schema
            LLMProviderError: Provider-specific error
        
        MUST:
        - Enable JSON mode (provider-specific)
        - Validate response against schema if provided
        - Parse JSON and validate structure
        - Retry on parse failure (up to max retries)
        """
        pass
    
    @abstractmethod
    def get_supported_models(self) -> list[str]:
        """
        Get list of supported model IDs.
        
        Returns:
            List of model ID strings
        """
        pass
    
    def supports_model(self, model_id: str) -> bool:
        """
        Check if model is supported.
        
        Args:
            model_id: Model ID to check
        
        Returns:
            True if supported
        """
        return model_id in self.get_supported_models()
    
    def get_provider_name(self) -> str:
        """Get provider name"""
        return self.provider_name


class BaseEmbeddingProvider(ABC):
    """
    Abstract base class for embedding providers.
    
    Separate from text generation providers since not all LLM providers
    support embeddings (e.g., Anthropic).
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize embedding provider"""
        self.api_key = api_key
        self.provider_name = self.__class__.__name__.replace("Provider", "").lower()
    
    @abstractmethod
    async def generate_embedding(
        self,
        request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """
        Generate vector embedding.
        
        Args:
            request: EmbeddingRequest with text and model
        
        Returns:
            EmbeddingResponse with vector and telemetry
        
        Raises:
            LLMEmbeddingServiceError: Service error
            LLMTimeoutError: Request timeout
        
        MUST:
        - Return consistent dimensionality for model
        - Normalize vector (if provider doesn't)
        - Record token usage in telemetry
        """
        pass
    
    @abstractmethod
    def get_embedding_dimension(self, model: str) -> int:
        """
        Get embedding dimensionality for model.
        
        Args:
            model: Embedding model ID
        
        Returns:
            Embedding vector dimension
        """
        pass


class BaseTranscriptionProvider(ABC):
    """
    Abstract base class for audio transcription providers.
    
    Separate interface since transcription is a different capability.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize transcription provider"""
        self.api_key = api_key
        self.provider_name = self.__class__.__name__.replace("Provider", "").lower()
    
    @abstractmethod
    async def transcribe_audio(
        self,
        request: TranscriptionRequest
    ) -> TranscriptionResponse:
        """
        Transcribe audio to text.
        
        Args:
            request: TranscriptionRequest with audio data
        
        Returns:
            TranscriptionResponse with text and telemetry
        
        Raises:
            LLMProviderError: Provider error
            LLMTimeoutError: Request timeout
        
        MUST:
        - Detect language if not provided
        - Return confidence score if available
        - Handle multiple audio formats
        """
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """
        Get supported audio formats.
        
        Returns:
            List of format strings (e.g., ['wav', 'mp3', 'opus'])
        """
        pass


class ProviderCapabilities:
    """
    Provider capability flags.
    
    Declares what features a provider supports.
    """
    
    def __init__(
        self,
        text_generation: bool = False,
        structured_output: bool = False,
        embeddings: bool = False,
        transcription: bool = False,
        streaming: bool = False,
        function_calling: bool = False
    ):
        self.text_generation = text_generation
        self.structured_output = structured_output
        self.embeddings = embeddings
        self.transcription = transcription
        self.streaming = streaming
        self.function_calling = function_calling
