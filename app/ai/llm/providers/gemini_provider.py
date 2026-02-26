"""
Gemini Provider Implementation (Stub)

Implements BaseLLMProvider for Google's Gemini API.
Following same pattern as Groq provider.
"""

from ..base_provider import BaseLLMProvider
from ..contracts import LLMRequest, LLMResponse
from ..errors import LLMConfigurationError

class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider (TO BE IMPLEMENTED)"""
    
    SUPPORTED_MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-3.0-pro"
    ]
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        if not self.api_key:
            raise LLMConfigurationError(
                message="GEMINI_API_KEY not provided",
                config_field="gemini_api_key"
            )
    
    def get_supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS.copy()
    
    async def generate_text(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("Gemini provider not yet implemented")
    
    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("Gemini provider not yet implemented")
