"""
LLM-Specific Errors

Extends shared error hierarchy with LLM provider error types.
All errors inherit from shared/errors/exceptions.py classes.
"""

from typing import Optional, Dict, Any
from app.shared.errors import (
    BaseError,
    AIProviderError,
    AIProviderTimeoutError,
    ValidationError,
    InfrastructureError
)


class LLMProviderError(AIProviderError):
    """
    LLM provider request failed.
    
    Wraps provider-specific errors (OpenAI, Anthropic, Groq, etc.)
    """
    
    def __init__(
        self,
        provider: str,
        message: str,
        provider_error_code: Optional[str] = None,
        retryable: bool = False,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "provider": provider,
            "provider_error_code": provider_error_code,
            "retryable": retryable
        })
        
        super().__init__(
            provider=provider,
            message=message,
            request_id=request_id,
            metadata=final_metadata
        )
        
        # Store for easy access
        self.provider = provider
        self.provider_error_code = provider_error_code
        self.retryable = retryable


class LLMTimeoutError(AIProviderTimeoutError):
    """
    LLM provider request timeout.
    
    Raised when provider call exceeds timeout threshold.
    Always retryable.
    """
    
    def __init__(
        self,
        provider: str,
        timeout_seconds: int,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata["retryable"] = True
        
        super().__init__(
            provider=provider,
            timeout_s=timeout_seconds,
            request_id=request_id
        )
        
        # Merge metadata
        self.metadata.update(final_metadata)
        self.retryable = True


class LLMRateLimitError(BaseError):
    """
    LLM provider rate limit exceeded.
    
    Always retryable with exponential backoff.
    """
    
    def __init__(
        self,
        provider: str,
        message: str = "Rate limit exceeded",
        retry_after_seconds: Optional[int] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "provider": provider,
            "retry_after_seconds": retry_after_seconds,
            "retryable": True
        })
        
        super().__init__(
            error_code="LLM_RATE_LIMIT",
            message=f"{provider} rate limit: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=429
        )
        
        self.provider = provider
        self.retry_after_seconds = retry_after_seconds
        self.retryable = True


class LLMAuthenticationError(BaseError):
    """
    LLM provider authentication failed.
    
    Not retryable (requires config fix).
    """
    
    def __init__(
        self,
        provider: str,
        message: str = "Authentication failed",
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "provider": provider,
            "retryable": False
        })
        
        super().__init__(
            error_code="LLM_AUTHENTICATION_FAILED",
            message=f"{provider} authentication: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=401
        )
        
        self.provider = provider
        self.retryable = False


class LLMSchemaValidationError(ValidationError):
    """
    LLM response failed schema validation.
    
    Retryable (may succeed with retry).
    """
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        expected_schema: Optional[Dict[str, Any]] = None,
        actual_response: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "expected_schema": expected_schema,
            "actual_response": actual_response,
            "retryable": True
        })
        
        super().__init__(
            message=f"Schema validation failed: {message}",
            field=field,
            request_id=request_id,
            metadata=final_metadata
        )
        
        self.retryable = True


class LLMContentFilterError(BaseError):
    """
    LLM response blocked by content filter.
    
    Provider detected unsafe content.
    Not retryable (indicates policy violation).
    """
    
    def __init__(
        self,
        provider: str,
        message: str = "Content policy violation",
        filter_type: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "provider": provider,
            "filter_type": filter_type,
            "retryable": False
        })
        
        super().__init__(
            error_code="LLM_CONTENT_FILTER",
            message=f"{provider} content filter: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=400
        )
        
        self.provider = provider
        self.filter_type = filter_type
        self.retryable = False


class LLMModelNotFoundError(BaseError):
    """
    Requested model not available.
    
    Model deprecated, incorrect name, or access restricted.
    Not retryable (requires config fix).
    """
    
    def __init__(
        self,
        provider: str,
        model_id: str,
        message: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "provider": provider,
            "model_id": model_id,
            "retryable": False
        })
        
        final_message = message or f"Model '{model_id}' not found or not accessible"
        
        super().__init__(
            error_code="LLM_MODEL_NOT_FOUND",
            message=f"{provider}: {final_message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=404
        )
        
        self.provider = provider
        self.model_id = model_id
        self.retryable = False


class LLMContextLengthError(BaseError):
    """
    Input exceeds model's context window.
    
    Not retryable without truncation.
    """
    
    def __init__(
        self,
        provider: str,
        model_id: str,
        max_tokens: int,
        actual_tokens: int,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "provider": provider,
            "model_id": model_id,
            "max_tokens": max_tokens,
            "actual_tokens": actual_tokens,
            "retryable": False
        })
        
        super().__init__(
            error_code="LLM_CONTEXT_LENGTH_EXCEEDED",
            message=f"{provider}: Input exceeds model context ({actual_tokens} > {max_tokens})",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=400
        )
        
        self.provider = provider
        self.model_id = model_id
        self.max_tokens = max_tokens
        self.actual_tokens = actual_tokens
        self.retryable = False


class LLMEmbeddingServiceError(InfrastructureError):
    """
    Self-hosted embedding service error.
    
    Connection failed, service down, or invalid response.
    """
    
    def __init__(
        self,
        message: str,
        service_url: str,
        retryable: bool = True,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "service_url": service_url,
            "retryable": retryable
        })
        
        super().__init__(
            component="embedding_service",
            message=message,
            request_id=request_id,
            metadata=final_metadata
        )
        
        self.service_url = service_url
        self.retryable = retryable


class LLMConfigurationError(BaseError):
    """
    LLM configuration error.
    
    Missing API key, invalid settings, etc.
    Not retryable (requires config fix).
    """
    
    def __init__(
        self,
        message: str,
        config_field: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        final_metadata = metadata or {}
        final_metadata.update({
            "config_field": config_field,
            "retryable": False
        })
        
        super().__init__(
            error_code="LLM_CONFIGURATION_ERROR",
            message=f"LLM configuration error: {message}",
            request_id=request_id,
            metadata=final_metadata,
            http_status_code=500
        )
        
        self.config_field = config_field
        self.retryable = False
