"""
OpenAI Provider Implementation (Stub)

Implements BaseLLMProvider for OpenAI's API.
Following same pattern as Groq provider.
"""

from ..base_provider import BaseLLMProvider
from ..contracts import LLMRequest, LLMResponse
from ..errors import LLMConfigurationError

class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider (TO BE IMPLEMENTED)"""
    
    SUPPORTED_MODELS = [
        "gpt-4o",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo"
    ]
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        if not self.api_key:
            raise LLMConfigurationError(
                message="OPENAI_API_KEY not provided",
                config_field="openai_api_key"
            )
    
    def get_supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS.copy()
    
    async def generate_text(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("OpenAI provider not yet implemented")
    
    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("OpenAI provider not yet implemented")
