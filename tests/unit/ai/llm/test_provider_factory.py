"""
Unit Tests for Provider Factory

Tests provider instantiation, configuration loading, and error handling.
"""

import pytest
from unittest.mock import patch, MagicMock
from app.ai.llm.provider_factory import ProviderFactory
from app.ai.llm.providers.groq_provider import GroqProvider
from app.ai.llm.providers.embedding_provider import EmbeddingProvider
from app.ai.llm.errors import LLMConfigurationError


class TestProviderFactory:
    """Test provider factory functionality"""
    
    @patch('app.ai.llm.provider_factory.settings')
    def test_create_groq_provider(self, mock_settings):
        """Create Groq provider with API key"""
        mock_settings.llm.groq_api_key = "test-groq-key"
        
        provider = ProviderFactory.create_text_provider(
            provider_name="groq",
            api_key="test-groq-key"
        )
        
        assert isinstance(provider, GroqProvider)
        assert provider.api_key == "test-groq-key"
        assert provider.get_provider_name() == "groq"
    
    @patch('app.ai.llm.provider_factory.settings')
    def test_create_provider_loads_api_key_from_settings(self, mock_settings):
        """Provider factory loads API key from settings"""
        mock_settings.llm.groq_api_key = "settings-groq-key"
        
        provider = ProviderFactory.create_text_provider(provider_name="groq")
        
        assert provider.api_key == "settings-groq-key"
    
    @patch('app.ai.llm.provider_factory.settings')
    def test_use_default_provider_from_settings(self, mock_settings):
        """Use default provider from settings"""
        mock_settings.llm.default_llm_provider = "groq"
        mock_settings.llm.groq_api_key = "test-key"
        
        provider = ProviderFactory.create_text_provider()
        
        assert isinstance(provider, GroqProvider)
    
    def test_unknown_provider_raises_error(self):
        """Unknown provider name raises configuration error"""
        with pytest.raises(LLMConfigurationError, match="Unknown provider: invalid"):
            ProviderFactory.create_text_provider(
                provider_name="invalid",
                api_key="test-key"
            )
    
    @patch('app.ai.llm.provider_factory.settings')
    def test_missing_api_key_raises_error(self, mock_settings):
        """Missing API key raises configuration error"""
        mock_settings.llm.groq_api_key = None
        
        with pytest.raises(LLMConfigurationError, match="API key not configured"):
            ProviderFactory.create_text_provider(provider_name="groq")
    
    @patch('app.ai.llm.provider_factory.settings')
    def test_create_embedding_provider(self, mock_settings):
        """Create embedding provider"""
        mock_settings.llm.embedding_model_url = "http://localhost:8080"
        
        provider = ProviderFactory.create_embedding_provider()
        
        assert isinstance(provider, EmbeddingProvider)
        assert provider.service_url == "http://localhost:8080"
    
    def test_create_embedding_provider_with_custom_url(self):
        """Create embedding provider with custom URL"""
        provider = ProviderFactory.create_embedding_provider(
            service_url="http://custom:9000"
        )
        
        assert provider.service_url == "http://custom:9000"


class TestProviderCapabilities:
    """Test provider capability flags"""
    
    def test_groq_capabilities(self):
        """Groq provider capabilities"""
        provider = GroqProvider(api_key="test-key")
        
        assert provider.capabilities.text_generation is True
        assert provider.capabilities.structured_output is True
        assert provider.capabilities.embeddings is False
        assert provider.capabilities.transcription is False
    
    def test_groq_supported_models(self):
        """Groq supported models list"""
        provider = GroqProvider(api_key="test-key")
        models = provider.get_supported_models()
        
        assert "llama-3.3-70b-versatile" in models
        assert "mixtral-8x7b-32768" in models
        assert len(models) > 0
    
    def test_provider_supports_model(self):
        """Check if provider supports specific model"""
        provider = GroqProvider(api_key="test-key")
        
        assert provider.supports_model("llama-3.3-70b-versatile") is True
        assert provider.supports_model("gpt-4") is False
