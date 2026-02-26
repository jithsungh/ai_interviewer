"""
Provider Factory

Creates LLM provider instances based on provider name and configuration.
"""

from typing import Optional
from app.config.settings import settings
from app.shared.observability import get_context_logger

from .base_provider import BaseLLMProvider, BaseEmbeddingProvider
from .providers.groq_provider import GroqProvider
from .errors import LLMConfigurationError

logger = get_context_logger(__name__)


class ProviderFactory:
    """
    Factory for creating LLM provider instances.
    
    Handles provider instantiation, API key loading, and configuration.
    """
    
    @staticmethod
    def create_text_provider(
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None,
        **kwargs
    ) -> BaseLLMProvider:
        """
        Create text generation provider.
        
        Args:
            provider_name: Provider name (groq | gemini | openai | anthropic)
                          If None, uses default from settings
            api_key: Override API key (if None, loads from settings)
            **kwargs: Provider-specific configuration
        
        Returns:
            BaseLLMProvider instance
        
        Raises:
            LLMConfigurationError: Invalid provider or missing API key
        """
        # Use default provider if not specified
        if not provider_name:
            provider_name = settings.llm.default_llm_provider
        
        provider_name = provider_name.lower()
        
        # Load API key from settings if not provided
        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)
        
        # Instantiate provider
        if provider_name == "groq":
            return GroqProvider(api_key=api_key, **kwargs)
        elif provider_name == "gemini":
            # Import here to avoid loading SDKs unnecessarily
            from .providers.gemini_provider import GeminiProvider
            return GeminiProvider(api_key=api_key, **kwargs)
        elif provider_name == "openai":
            from .providers.openai_provider import OpenAIProvider
            return OpenAIProvider(api_key=api_key, **kwargs)
        elif provider_name == "anthropic":
            from .providers.anthropic_provider import AnthropicProvider
            return AnthropicProvider(api_key=api_key, **kwargs)
        else:
            raise LLMConfigurationError(
                message=f"Unknown provider: {provider_name}",
                config_field="provider_name"
            )
    
    @staticmethod
    def create_embedding_provider(
        api_key: Optional[str] = None,
        service_url: Optional[str] = None,
        **kwargs
    ) -> BaseEmbeddingProvider:
        """
        Create embedding provider (self-hosted service).
        
        Args:
            api_key: Optional API key (not needed for self-hosted)
            service_url: Embedding service URL (default from settings)
            **kwargs: Additional configuration
        
        Returns:
            BaseEmbeddingProvider instance
        """
        from .providers.embedding_provider import EmbeddingProvider
        
        if not service_url:
            service_url = settings.llm.embedding_model_url
        
        return EmbeddingProvider(service_url=service_url, **kwargs)
    
    @staticmethod
    def _get_api_key(provider_name: str) -> str:
        """Load API key from settings"""
        if provider_name == "groq":
            api_key = settings.llm.groq_api_key
        elif provider_name == "gemini":
            api_key = settings.llm.gemini_api_key
        elif provider_name == "openai":
            api_key = settings.llm.openai_api_key
        elif provider_name == "anthropic":
            api_key = settings.llm.anthropic_api_key
        else:
            raise LLMConfigurationError(
                message=f"Unknown provider: {provider_name}",
                config_field="provider_name"
            )
        
        if not api_key:
            raise LLMConfigurationError(
                message=f"API key not configured for provider: {provider_name}",
                config_field=f"{provider_name}_api_key"
            )
        
        return api_key


# Convenience functions for direct provider creation
def get_groq_provider(api_key: Optional[str] = None) -> GroqProvider:
    """Get Groq provider instance"""
    return ProviderFactory.create_text_provider("groq", api_key)


def get_default_provider(api_key: Optional[str] = None) -> BaseLLMProvider:
    """Get default provider from settings"""
    return ProviderFactory.create_text_provider(None, api_key)
