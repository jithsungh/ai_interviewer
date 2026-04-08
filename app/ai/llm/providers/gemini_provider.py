"""
Gemini Provider Implementation

Implements BaseLLMProvider for Google's Gemini API.
Supports Gemini 1.5 Flash, Pro, and other models.
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
    LLMError,
)
from ..errors import (
    LLMProviderError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMSchemaValidationError,
    LLMConfigurationError,
)
from ..utils import create_http_client

logger = get_context_logger(__name__)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini LLM Provider.
    
    Provider Details:
    - API Endpoint: https://generativelanguage.googleapis.com/v1beta/
    - RESTful API with streaming support
    - Supports JSON mode via response_schema
    - Extremely fast inference (via LPU optimization)
    
    Supported Models:
    - gemini-2.0-flash-exp (latest, fastest)
    - gemini-1.5-flash (fast, default)
    - gemini-1.5-pro (higher quality)
    """
    
    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS_LIST_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS_CACHE_TTL_SECONDS = 300
    
    SUPPORTED_MODELS = [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro-latest",
        "gemini-1.5-flash-8b",
    ]

    MODEL_ALIASES = {
        "gemini-1.5-flash": ["gemini-1.5-flash-latest", "gemini-2.0-flash"],
        "gemini-1.5-flash-latest": ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"],
        "gemini-1.5-pro": ["gemini-1.5-pro-latest", "gemini-2.0-flash"],
        "gemini-1.5-pro-latest": ["gemini-1.5-pro", "gemini-2.0-flash"],
        "gemini-2.0-flash-exp": ["gemini-2.0-flash"],
    }
    
    def __init__(self, api_key: str, **kwargs):
        """
        Initialize Gemini provider.
        
        Args:
            api_key: Google API key for Gemini
            **kwargs: Additional configuration
        """
        super().__init__(api_key=api_key, **kwargs)
        
        if not self.api_key:
            raise LLMConfigurationError(
                message="GEMINI_API_KEY not provided",
                config_field="gemini_api_key"
            )
        
        self.capabilities = ProviderCapabilities(
            text_generation=True,
            structured_output=True,
            embeddings=False,
            transcription=False,
            streaming=True,
            function_calling=False,
        )

        self._available_models_cache: Optional[list[str]] = None
        self._available_models_cache_ts: float = 0.0
    
    def get_supported_models(self) -> list[str]:
        """Get list of supported models."""
        return self.SUPPORTED_MODELS.copy()
    
    async def generate_text(self, request: LLMRequest) -> LLMResponse:
        """
        Generate text completion using Gemini.
        
        Args:
            request: LLMRequest with prompt and parameters
        
        Returns:
            LLMResponse with generated text and telemetry
        """
        start_time = time.perf_counter()
        
        try:
            payload = self._build_payload(request, json_mode=False)
            response, resolved_model = await self._post_with_model_fallback(
                request=request,
                payload=payload,
            )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            if response.status_code != 200:
                return self._handle_error(response, request, latency_ms)
            
            response_data = response.json()
            
            # Extract completion from Gemini response format
            if "candidates" not in response_data or not response_data["candidates"]:
                error = LLMError(
                    type="provider_error",
                    message="Empty response from Gemini",
                    retryable=True,
                )
                telemetry = self._create_error_telemetry(request, latency_ms, "empty_response")
                return LLMResponse(success=False, telemetry=telemetry, error=error)
            
            candidate = response_data["candidates"][0]
            content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
            finish_reason = candidate.get("finishReason", "STOP")
            
            # Extract usage
            usage = response_data.get("usageMetadata", {})
            telemetry = TelemetryData(
                model_id=resolved_model,
                provider="gemini",
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
                total_tokens=usage.get("totalTokenCount", 0),
                latency_ms=latency_ms,
                success=True,
                retry_count=0,
                deterministic=request.deterministic,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                request_id=request.request_id,
                organization_id=request.organization_id,
            )
            
            logger.info(
                "Gemini request completed",
                extra={
                    "model": resolved_model,
                    "requested_model": request.model,
                    "latency_ms": latency_ms,
                    "tokens": telemetry.total_tokens,
                },
            )
            
            return LLMResponse(
                success=True,
                text=content,
                finish_reason=finish_reason,
                telemetry=telemetry,
                metadata={
                    "model": resolved_model,
                    "requested_model": request.model,
                    "provider": "gemini",
                },
                raw_response=response_data,
            )
        
        except httpx.TimeoutException:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error = LLMError(
                type="timeout",
                message=f"Gemini request timeout after {request.timeout_seconds}s",
                retryable=True,
            )
            telemetry = self._create_error_telemetry(request, latency_ms, "timeout")
            
            logger.warning(
                "Gemini timeout",
                extra={"timeout_seconds": request.timeout_seconds},
            )
            
            return LLMResponse(success=False, telemetry=telemetry, error=error)
        
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error = LLMError(
                type="unknown",
                message=f"Unexpected error: {str(e)}",
                retryable=False,
            )
            telemetry = self._create_error_telemetry(request, latency_ms, "unknown")
            
            logger.error(
                f"Gemini error: {str(e)}",
                exc_info=True,
            )
            
            return LLMResponse(success=False, telemetry=telemetry, error=error)
    
    async def generate_structured(self, request: LLMRequest) -> LLMResponse:
        """
        Generate structured JSON output using Gemini.
        
        Args:
            request: LLMRequest with json_mode=True and schema
        
        Returns:
            LLMResponse with JSON-formatted text
        """
        start_time = time.perf_counter()
        
        try:
            payload = self._build_payload(request, json_mode=True, include_provider_json_controls=True)
            response, resolved_model = await self._post_with_model_fallback(
                request=request,
                payload=payload,
            )

            if response.status_code == 400 and self._is_json_mode_field_error(response):
                logger.warning(
                    "Gemini endpoint rejected responseMimeType/responseSchema; retrying structured request without provider JSON controls",
                    extra={"model": resolved_model, "requested_model": request.model},
                )
                fallback_payload = self._build_payload(
                    request,
                    json_mode=True,
                    include_provider_json_controls=False,
                )
                response, resolved_model = await self._post_with_model_fallback(
                    request=request,
                    payload=fallback_payload,
                )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            if response.status_code != 200:
                return self._handle_error(response, request, latency_ms)
            
            response_data = response.json()
            
            if "candidates" not in response_data or not response_data["candidates"]:
                error = LLMError(
                    type="provider_error",
                    message="Empty response from Gemini",
                    retryable=True,
                )
                telemetry = self._create_error_telemetry(request, latency_ms, "empty_response")
                return LLMResponse(success=False, telemetry=telemetry, error=error)
            
            candidate = response_data["candidates"][0]
            content = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")
            
            # Validate JSON
            try:
                json_obj = json.loads(content)
            except json.JSONDecodeError as e:
                error = LLMError(
                    type="schema_validation",
                    message=f"Invalid JSON response: {str(e)}",
                    retryable=True,
                )
                telemetry = self._create_error_telemetry(request, latency_ms, "schema_validation")
                return LLMResponse(success=False, telemetry=telemetry, error=error)
            
            # Validate schema if provided
            if request.schema:
                validation_error = self._validate_schema(json_obj, request.schema)
                if validation_error:
                    error = LLMError(
                        type="schema_validation",
                        message=validation_error,
                        retryable=True,
                    )
                    telemetry = self._create_error_telemetry(request, latency_ms, "schema_validation")
                    return LLMResponse(success=False, telemetry=telemetry, error=error)
            
            # Success
            usage = response_data.get("usageMetadata", {})
            telemetry = TelemetryData(
                model_id=resolved_model,
                provider="gemini",
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
                total_tokens=usage.get("totalTokenCount", 0),
                latency_ms=latency_ms,
                success=True,
                retry_count=0,
                deterministic=request.deterministic,
                temperature=request.temperature,
                request_id=request.request_id,
                organization_id=request.organization_id,
            )
            
            return LLMResponse(
                success=True,
                text=content,
                finish_reason=candidate.get("finishReason", "STOP"),
                telemetry=telemetry,
                metadata={
                    "model": resolved_model,
                    "requested_model": request.model,
                    "provider": "gemini",
                    "json_mode": True,
                },
                raw_response=response_data,
            )
        
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error = LLMError(
                type="unknown",
                message=f"Unexpected error: {str(e)}",
                retryable=False,
            )
            telemetry = self._create_error_telemetry(request, latency_ms, "unknown")
            
            logger.error(
                f"Gemini structured generation error: {str(e)}",
                exc_info=True,
            )
            
            return LLMResponse(success=False, telemetry=telemetry, error=error)
    
    def _build_payload(
        self,
        request: LLMRequest,
        json_mode: bool = False,
        include_provider_json_controls: bool = True,
    ) -> Dict[str, Any]:
        """Build Gemini API request payload."""
        # Build messages
        messages = []
        
        # Add system prompt as part of the message
        user_content = request.prompt
        if request.system_prompt:
            user_content = f"{request.system_prompt}\n\n{request.prompt}"
        
        if json_mode:
            user_content += "\n\nRespond with valid JSON only."
        
        messages.append({"role": "user", "parts": [{"text": user_content}]})
        
        payload = {
            "contents": messages,
            "generationConfig": {
                "temperature": request.temperature,
                "topP": request.top_p,
                "maxOutputTokens": request.max_tokens or 2048,
            },
        }
        
        # Add JSON schema for structured output
        if json_mode and include_provider_json_controls:
            payload["generationConfig"]["responseMimeType"] = "application/json"

            if request.schema:
                sanitized_schema = self._sanitize_schema_for_gemini(request.schema)
                if sanitized_schema:
                    payload["generationConfig"]["responseSchema"] = sanitized_schema
                else:
                    logger.warning(
                        "Skipping Gemini responseSchema due to unsupported schema features; using JSON mime mode only"
                    )
        
        return payload

    async def _post_with_model_fallback(
        self,
        request: LLMRequest,
        payload: Dict[str, Any],
    ) -> tuple[httpx.Response, str]:
        """Post request with model alias fallback for 404 model-not-found errors."""
        requested_model = self._normalize_model_name(request.model)
        candidates = self._build_model_candidates(requested_model)
        available_models = await self._get_available_generate_models(request.timeout_seconds)
        if available_models:
            candidates = self._prioritize_candidates(
                requested_model=requested_model,
                baseline_candidates=candidates,
                available_models=available_models,
            )
        last_response: Optional[httpx.Response] = None

        async with create_http_client(timeout_seconds=request.timeout_seconds) as client:
            for model in candidates:
                response = await client.post(
                    f"{self.API_BASE}/{model}:generateContent",
                    json=payload,
                    params={"key": self.api_key},
                )

                if response.status_code == 404 and self._is_model_not_found_error(response):
                    last_response = response
                    logger.warning(
                        "Gemini model not found, trying fallback model",
                        extra={
                            "requested_model": request.model,
                            "attempt_model": model,
                            "remaining_fallbacks": len(candidates) - candidates.index(model) - 1,
                        },
                    )
                    continue

                return response, model

        if last_response is not None:
            return last_response, requested_model

        # Defensive fallback (should not happen)
        async with create_http_client(timeout_seconds=request.timeout_seconds) as client:
            response = await client.post(
                f"{self.API_BASE}/{requested_model}:generateContent",
                json=payload,
                params={"key": self.api_key},
            )
        return response, requested_model

    def _normalize_model_name(self, model: str) -> str:
        """Normalize model name (strip optional leading 'models/')."""
        if model.startswith("models/"):
            return model.split("models/", 1)[1]
        return model

    def _build_model_candidates(self, model: str) -> list[str]:
        """Build unique candidate list for model fallback resolution."""
        candidates = [model]
        aliases = self.MODEL_ALIASES.get(model, [])
        candidates.extend(aliases)

        unique_candidates: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in unique_candidates:
                unique_candidates.append(candidate)
        return unique_candidates

    def _prioritize_candidates(
        self,
        requested_model: str,
        baseline_candidates: list[str],
        available_models: list[str],
    ) -> list[str]:
        """Prioritize candidate models against ListModels-supported generateContent models."""
        available_set = set(available_models)

        prioritized: list[str] = []
        for candidate in baseline_candidates:
            if candidate in available_set and candidate not in prioritized:
                prioritized.append(candidate)

        requested_lower = requested_model.lower()
        if "flash" in requested_lower:
            family = [m for m in available_models if "flash" in m.lower()]
        elif "pro" in requested_lower:
            family = [m for m in available_models if "pro" in m.lower()]
        else:
            family = []

        for model in family:
            if model not in prioritized:
                prioritized.append(model)

        for model in available_models:
            if model not in prioritized:
                prioritized.append(model)

        for candidate in baseline_candidates:
            if candidate not in prioritized:
                prioritized.append(candidate)

        return prioritized

    async def _get_available_generate_models(self, timeout_seconds: int) -> list[str]:
        """Fetch and cache models that support generateContent for this API key."""
        now = time.time()
        if (
            self._available_models_cache is not None
            and now - self._available_models_cache_ts < self.MODELS_CACHE_TTL_SECONDS
        ):
            return self._available_models_cache

        try:
            async with create_http_client(timeout_seconds=timeout_seconds) as client:
                response = await client.get(
                    self.MODELS_LIST_URL,
                    params={"key": self.api_key},
                )

            if response.status_code != 200:
                logger.warning(
                    "Failed to list Gemini models; continuing with static fallback list",
                    extra={"status_code": response.status_code},
                )
                return self._available_models_cache or []

            payload = response.json() or {}
            models = payload.get("models", [])

            available: list[str] = []
            for model in models:
                methods = model.get("supportedGenerationMethods") or []
                if "generateContent" not in methods:
                    continue

                name = model.get("name") or ""
                normalized = self._normalize_model_name(name)
                if normalized and normalized not in available:
                    available.append(normalized)

            self._available_models_cache = available
            self._available_models_cache_ts = now

            logger.info(
                "Loaded available Gemini models for generateContent",
                extra={"model_count": len(available)},
            )
            return available

        except Exception as e:
            logger.warning(
                "Error listing Gemini models; continuing with static fallback list",
                extra={"error": str(e)},
            )
            return self._available_models_cache or []

    def _is_model_not_found_error(self, response: httpx.Response) -> bool:
        """Detect provider 404 model-not-found errors."""
        try:
            error_data = response.json()
            message = (error_data.get("error", {}) or {}).get("message", "")
        except Exception:
            message = response.text or ""

        lowered = message.lower()
        return "not found" in lowered or "not supported for generatecontent" in lowered

    def _is_json_mode_field_error(self, response: httpx.Response) -> bool:
        """Detect payload field incompatibility for responseMimeType/responseSchema."""
        try:
            error_data = response.json()
            message = (error_data.get("error", {}) or {}).get("message", "")
        except Exception:
            message = response.text or ""

        lowered = message.lower()
        return (
            "unknown name \"responsemimetype\"" in lowered
            or "unknown name \"responseschema\"" in lowered
        )

    def _sanitize_schema_for_gemini(self, schema: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Convert JSON Schema into Gemini-compatible responseSchema.

        Gemini rejects many JSON Schema keywords (e.g. $ref/$defs/additionalProperties).
        This method resolves simple local refs and strips unsupported keys.
        """
        if not isinstance(schema, dict):
            return None

        defs = schema.get("$defs") or schema.get("definitions") or {}

        def resolve_ref(ref_value: str) -> Optional[Dict[str, Any]]:
            if not isinstance(ref_value, str):
                return None
            if ref_value.startswith("#/$defs/"):
                key = ref_value.split("#/$defs/", 1)[1]
                return defs.get(key)
            if ref_value.startswith("#/definitions/"):
                key = ref_value.split("#/definitions/", 1)[1]
                return defs.get(key)
            return None

        allowed_keys = {
            "type",
            "format",
            "description",
            "nullable",
            "enum",
            "items",
            "properties",
            "required",
            "minItems",
            "maxItems",
            "minimum",
            "maximum",
            "minLength",
            "maxLength",
            "anyOf",
            "oneOf",
        }

        def normalize_type(value: Any) -> Any:
            if isinstance(value, str):
                return value.lower()
            return value

        def clean(node: Any, depth: int = 0) -> Any:
            if depth > 20:
                return {"type": "string"}

            if isinstance(node, dict):
                if "$ref" in node:
                    resolved = resolve_ref(node["$ref"])
                    if resolved is None:
                        return {"type": "string"}
                    return clean(resolved, depth + 1)

                cleaned: Dict[str, Any] = {}

                for key, value in node.items():
                    if key in {"$defs", "definitions", "title", "default", "examples", "additionalProperties", "$schema", "$id"}:
                        continue
                    if key not in allowed_keys:
                        continue

                    if key == "type":
                        cleaned[key] = normalize_type(value)
                    elif key in {"properties", "items", "anyOf", "oneOf"}:
                        cleaned_value = clean(value, depth + 1)
                        if cleaned_value is not None:
                            cleaned[key] = cleaned_value
                    elif key == "required":
                        if isinstance(value, list):
                            cleaned[key] = [str(v) for v in value]
                    else:
                        cleaned[key] = value

                if cleaned.get("type") == "object" and "properties" not in cleaned:
                    cleaned["properties"] = {}

                return cleaned

            if isinstance(node, list):
                return [clean(item, depth + 1) for item in node if item is not None]

            return node

        root = clean(schema)
        if not isinstance(root, dict):
            return None

        def prune_required(node: Any) -> Any:
            if isinstance(node, dict):
                properties = node.get("properties")
                required = node.get("required")

                if isinstance(properties, dict):
                    property_keys = set(properties.keys())

                    if isinstance(required, list):
                        filtered_required = [
                            key for key in required
                            if isinstance(key, str) and key in property_keys
                        ]
                        if filtered_required:
                            node["required"] = filtered_required
                        else:
                            node.pop("required", None)

                    for prop_name, prop_schema in list(properties.items()):
                        properties[prop_name] = prune_required(prop_schema)
                else:
                    node.pop("required", None)

                if "items" in node:
                    node["items"] = prune_required(node["items"])

                if "anyOf" in node and isinstance(node["anyOf"], list):
                    node["anyOf"] = [prune_required(item) for item in node["anyOf"]]

                if "oneOf" in node and isinstance(node["oneOf"], list):
                    node["oneOf"] = [prune_required(item) for item in node["oneOf"]]

                return node

            if isinstance(node, list):
                return [prune_required(item) for item in node]

            return node

        root = prune_required(root)

        if "type" not in root:
            root["type"] = "object"
        if root.get("type") == "object" and "properties" not in root:
            root["properties"] = {}

        return root
    
    def _handle_error(
        self,
        response: httpx.Response,
        request: LLMRequest,
        latency_ms: int,
    ) -> LLMResponse:
        """Handle HTTP error responses."""
        status_code = response.status_code
        
        try:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", response.text)
        except Exception:
            error_message = response.text
        
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
        elif status_code == 400:
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
        )
        
        telemetry = self._create_error_telemetry(request, latency_ms, error_type)
        
        logger.warning(
            f"Gemini error: {status_code} - {error_message}",
            extra={"status_code": status_code},
        )
        
        return LLMResponse(success=False, telemetry=telemetry, error=error)
    
    def _create_error_telemetry(
        self,
        request: LLMRequest,
        latency_ms: int,
        error_type: str,
    ) -> TelemetryData:
        """Create telemetry for error responses."""
        return TelemetryData(
            model_id=request.model,
            provider="gemini",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=latency_ms,
            success=False,
            error_type=error_type,
            retry_count=0,
            deterministic=request.deterministic,
            temperature=request.temperature,
            request_id=request.request_id,
            organization_id=request.organization_id,
        )
    
    def _validate_schema(
        self,
        json_obj: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Optional[str]:
        """Validate JSON object against schema."""
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in json_obj:
                return f"Missing required field: {field}"
        
        properties = schema.get("properties", {})
        for field, field_schema in properties.items():
            if field in json_obj:
                expected_type = field_schema.get("type")
                actual_value = json_obj[field]
                
                if expected_type == "string" and not isinstance(actual_value, str):
                    return f"Field '{field}' must be string, got {type(actual_value).__name__}"
                elif expected_type == "number" and not isinstance(actual_value, (int, float)):
                    return f"Field '{field}' must be number, got {type(actual_value).__name__}"
                elif expected_type == "boolean" and not isinstance(actual_value, bool):
                    return f"Field '{field}' must be boolean, got {type(actual_value).__name__}"
                elif expected_type == "array" and not isinstance(actual_value, list):
                    return f"Field '{field}' must be array, got {type(actual_value).__name__}"
        
        return None
