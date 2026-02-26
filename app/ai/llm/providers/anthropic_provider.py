"""
Anthropic Provider Implementation (Stub)

Implements BaseLLMProvider for Anthropic's Claude API.
Following same pattern as Groq provider.
"""

from ..base_provider import BaseLLMProvider
from ..contracts import LLMRequest, LLMResponse
from ..errors import LLMConfigurationError

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider (TO BE IMPLEMENTED)"""
    
    SUPPORTED_MODELS = [
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307"
    ]
    
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        if not self.api_key:
            raise LLMConfigurationError(
                message="ANTHROPIC_API_KEY not provided",
                config_field="anthropic_api_key"
            )
    
    def get_supported_models(self) -> list[str]:
        return self.SUPPORTED_MODELS.copy()
    
    async def generate_text(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("Anthropic provider not yet implemented")
    
    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("Anthropic provider not yet implemented")
