"""
Groq Provider Implementation

Implements BaseLLMProvider for Groq's LLM API.
Groq provides OpenAI-compatible API with extremely fast inference (LPU architecture).
"""

import json
import time
from typing import Optional, Dict, Any
import httpx

from app.shared.observability import get_context_logger
from ..base_provider import BaseLLMProvider, ProviderCapabilities
from ..contracts import (
    LLMRequest,
    LLMResponse,
    TelemetryData,
    LLMError
)
from ..errors import (
    LLMProviderError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMSchemaValidationError,
    LLMModelNotFoundError,
    LLMContextLengthError
)
from ..utils import create_http_client

logger = get_context_logger(__name__)


class GroqProvider(BaseLLMProvider):
    """
    Groq LLM Provider.
    
    Provider Details:
    - API Endpoint: https://api.groq.com/openai/v1
    - OpenAI-compatible API
    - Extremely fast inference (LPU architecture)
    - Supports JSON mode for structured output
    
    Supported Models:
    - llama-3.3-70b-versatile (recommended)
    - llama-3.1-70b-versatile
    - mixtral-8x7b-32768
    - gemma2-9b-it
    """
    
    API_BASE = "https://api.groq.com/openai/v1"
    
    SUPPORTED_MODELS = [
        "llama-3.3-70b-versatile",
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
    ]
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Groq provider.
        
        Args:
            api_key: Groq API key
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, **kwargs)
        
        if not self.api_key:
            raise LLMAuthenticationError(
                provider="groq",
                message="GROQ_API_KEY not provided"
            )
        
        self.capabilities = ProviderCapabilities(
            text_generation=True,
            structured_output=True,
            embeddings=False,  # Groq doesn't provide embeddings
            transcription=False,  # Groq doesn't provide transcription
            streaming=True,  # Supported but not implemented yet
            function_calling=False
        )
    
    def get_supported_models(self) -> list[str]:
        """Get list of supported models"""
        return self.SUPPORTED_MODELS.copy()
    
    async def generate_text(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text completion using Groq.
        
        Args:
            request: LLMRequest with prompt and parameters
        
        Returns:
            LLMResponse with generated text and telemetry
        """
        start_time = time.perf_counter()
        
        try:
            # Build request payload
            payload = self._build_payload(request, json_mode=False)
            
            # Make API call with timeout
            async with create_http_client(timeout_seconds=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self.API_BASE}/chat/completions",
                    json=payload,
                    headers=self._get_headers()
                )
            
            # Calculate latency
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            # Handle HTTP errors
            if response.status_code != 200:
                return self._handle_error(response, request, latency_ms)
            
            # Parse response
            response_data = response.json()
            
            # Extract completion
            completion_text = response_data['choices'][0]['message']['content']
            finish_reason = response_data['choices'][0].get('finish_reason', 'stop')
            
            # Extract telemetry
            usage = response_data.get('usage', {})
            telemetry = TelemetryData(
                model_id=request.model,
                provider="groq",
                prompt_tokens=usage.get('prompt_tokens', 0),
                completion_tokens=usage.get('completion_tokens', 0),
                total_tokens=usage.get('total_tokens', 0),
                latency_ms=latency_ms,
                success=True,
                retry_count=0,
                deterministic=request.deterministic,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                request_id=request.request_id,
                organization_id=request.organization_id
            )
            
            logger.info(
                f"Groq request completed: {request.model}",
                event_type="llm.groq.completed",
                latency_ms=latency_ms,
                metadata={
                    "model_id": request.model,
                    "tokens": telemetry.total_tokens
                }
            )
            
            return LLMResponse(
                success=True,
                text=completion_text,
                finish_reason=finish_reason,
                telemetry=telemetry,
                metadata={
                    "model": request.model,
                    "provider": "groq"
                },
                raw_response=response_data
            )
        
        except httpx.TimeoutException:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error = LLMError(
                type="timeout",
                message=f"Groq request timeout after {request.timeout_seconds}s",
                retryable=True
            )
            telemetry = self._create_error_telemetry(request, latency_ms, "timeout")
            
            logger.warning(
                "Groq timeout",
                event_type="llm.groq.timeout",
                metadata={
                    "timeout_seconds": request.timeout_seconds
                }
            )
            
            return LLMResponse(
                success=False,
                telemetry=telemetry,
                error=error
            )
        
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error = LLMError(
                type="unknown",
                message=f"Unexpected error: {str(e)}",
                retryable=False
            )
            telemetry = self._create_error_telemetry(request, latency_ms, "unknown")
            
            logger.error(
                f"Groq error: {str(e)}",
                event_type="llm.groq.error",
                exc_info=True
            )
            
            return LLMResponse(
                success=False,
                telemetry=telemetry,
                error=error
            )
    
    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        """
        Generate structured JSON output using Groq.
        
        Args:
            request: LLMRequest with json_mode=True
        
        Returns:
            LLMResponse with JSON-formatted text
        """
        start_time = time.perf_counter()
        
        try:
            # Build request payload with JSON mode
            payload = self._build_payload(request, json_mode=True)
            
            # Make API call
            async with create_http_client(timeout_seconds=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self.API_BASE}/chat/completions",
                    json=payload,
                    headers=self._get_headers()
                )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            if response.status_code != 200:
                return self._handle_error(response, request, latency_ms)
            
            response_data = response.json()
            completion_text = response_data['choices'][0]['message']['content']
            
            # Validate JSON
            try:
                json_obj = json.loads(completion_text)
            except json.JSONDecodeError as e:
                error = LLMError(
                    type="schema_validation",
                    message=f"Invalid JSON response: {str(e)}",
                    retryable=True
                )
                telemetry = self._create_error_telemetry(request, latency_ms, "schema_validation")
                
                return LLMResponse(
                    success=False,
                    telemetry=telemetry,
                    error=error
                )
            
            # Validate schema if provided
            if request.schema:
                validation_error = self._validate_schema(json_obj, request.schema)
                if validation_error:
                    error = LLMError(
                        type="schema_validation",
                        message=validation_error,
                        retryable=True
                    )
                    telemetry = self._create_error_telemetry(request, latency_ms, "schema_validation")
                    
                    return LLMResponse(
                        success=False,
                        telemetry=telemetry,
                        error=error
                    )
            
            # Success
            usage = response_data.get('usage', {})
            telemetry = TelemetryData(
                model_id=request.model,
                provider="groq",
                prompt_tokens=usage.get('prompt_tokens', 0),
                completion_tokens=usage.get('completion_tokens', 0),
                total_tokens=usage.get('total_tokens', 0),
                latency_ms=latency_ms,
                success=True,
                retry_count=0,
                deterministic=request.deterministic,
                temperature=request.temperature,
                request_id=request.request_id,
                organization_id=request.organization_id
            )
            
            return LLMResponse(
                success=True,
                text=completion_text,
                finish_reason=response_data['choices'][0].get('finish_reason', 'stop'),
                telemetry=telemetry,
                metadata={"model": request.model, "provider": "groq", "json_mode": True},
                raw_response=response_data
            )
        
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error = LLMError(
                type="unknown",
                message=f"Unexpected error: {str(e)}",
                retryable=False
            )
            telemetry = self._create_error_telemetry(request, latency_ms, "unknown")
            
            return LLMResponse(
                success=False,
                telemetry=telemetry,
                error=error
            )
    
    def _build_payload(self, request: LLMRequest, json_mode: bool = False) -> Dict[str, Any]:
        """Build Groq API request payload"""
        messages = []
        
        # Add system prompt if provided
        if request.system_prompt:
            messages.append({
                "role": "system",
                "content": request.system_prompt
            })
        
        # Add user prompt (with JSON instruction if json_mode enabled)
        user_prompt = request.prompt
        if json_mode:
            # Groq requires the word 'json' in the prompt when using JSON mode
            user_prompt = f"{request.prompt}\n\nRespond with valid JSON only."
        
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        payload = {
            "model": request.model,
            "messages": messages,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }
        
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        
        # Enable JSON mode if requested
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        
        # Add seed for deterministic mode (if supported)
        if request.deterministic:
            payload["seed"] = 0
        
        return payload
    
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for Groq API"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _handle_error(
        self,
        response: httpx.Response,
        request: LLMRequest,
        latency_ms: int
    ) -> LLMResponse:
        """Handle HTTP error responses"""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', response.text)
            error_code = error_data.get('error', {}).get('code', str(status_code))
        except:
            error_message = response.text
            error_code = str(status_code)
        
        # Map status codes to error types
        if status_code == 401:
            error_type = "authentication"
            retryable = False
        elif status_code == 429:
            error_type = "rate_limit"
            retryable = True
        elif status_code == 404:
            error_type = "provider_error"
            retryable = False
        elif status_code >= 500:
            error_type = "provider_error"
            retryable = True
        else:
            error_type = "provider_error"
            retryable = False
        
        error = LLMError(
            type=error_type,
            message=error_message,
            retryable=retryable,
            provider_error_code=error_code
        )
        
        telemetry = self._create_error_telemetry(request, latency_ms, error_type)
        
        logger.warning(
            f"Groq error: {status_code} - {error_message}",
            event_type="llm.groq.error",
            metadata={
                "status_code": status_code,
                "error_code": error_code
            }
        )
        
        return LLMResponse(
            success=False,
            telemetry=telemetry,
            error=error
        )
    
    def _create_error_telemetry(
        self,
        request: LLMRequest,
        latency_ms: int,
        error_type: str
    ) -> TelemetryData:
        """Create telemetry for error responses"""
        return TelemetryData(
            model_id=request.model,
            provider="groq",
            prompt_tokens=0,  # Not available on error
            completion_tokens=0,
            total_tokens=0,
            latency_ms=latency_ms,
            success=False,
            error_type=error_type,
            retry_count=0,
            deterministic=request.deterministic,
            temperature=request.temperature,
            request_id=request.request_id,
            organization_id=request.organization_id
        )
    
    def _validate_schema(self, json_obj: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
        """
        Validate JSON object against schema.
        
        Returns:
            Error message if validation fails, None otherwise
        """
        # Simple validation: check required fields
        required_fields = schema.get('required', [])
        for field in required_fields:
            if field not in json_obj:
                return f"Missing required field: {field}"
        
        # Check field types if specified
        properties = schema.get('properties', {})
        for field, field_schema in properties.items():
            if field in json_obj:
                expected_type = field_schema.get('type')
                actual_value = json_obj[field]
                
                if expected_type == 'string' and not isinstance(actual_value, str):
                    return f"Field '{field}' must be string, got {type(actual_value).__name__}"
                elif expected_type == 'number' and not isinstance(actual_value, (int, float)):
                    return f"Field '{field}' must be number, got {type(actual_value).__name__}"
                elif expected_type == 'boolean' and not isinstance(actual_value, bool):
                    return f"Field '{field}' must be boolean, got {type(actual_value).__name__}"
                elif expected_type == 'array' and not isinstance(actual_value, list):
                    return f"Field '{field}' must be array, got {type(actual_value).__name__}"
                elif expected_type == 'object' and not isinstance(actual_value, dict):
                    return f"Field '{field}' must be object, got {type(actual_value).__name__}"
        
        return None
