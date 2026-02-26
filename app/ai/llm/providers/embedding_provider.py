"""
Self-Hosted Embedding Provider

Implements BaseEmbeddingProvider for self-hosted all-mpnet-base-v2 model.
Uses OpenAI-compatible API endpoint.
"""

import time
from typing import Optional
import httpx

from app.shared.observability import get_context_logger
from ..base_provider import BaseEmbeddingProvider
from ..contracts import (
    EmbeddingRequest,
    EmbeddingResponse,
    TelemetryData,
    LLMError
)
from ..errors import LLMEmbeddingServiceError, LLMTimeoutError
from ..utils import create_http_client

logger = get_context_logger(__name__)


class EmbeddingProvider(BaseEmbeddingProvider):
    """
    Self-hosted embedding service provider.
    
    Model: all-mpnet-base-v2 (768 dimensions)
    API Format: OpenAI-compatible /v1/embeddings endpoint
    """
    
    def __init__(self, service_url: str, **kwargs):
        """
        Initialize embedding provider.
        
        Args:
            service_url: Embedding service base URL (e.g., http://localhost:8080)
            **kwargs: Additional configuration
        """
        super().__init__(api_key=None, **kwargs)
        self.service_url = service_url.rstrip('/')
        self.model = "all-mpnet-base-v2"
        self.embedding_dimension = 768
    
    async def generate_embedding(self, request: EmbeddingRequest) -> EmbeddingResponse:
        """
        Generate vector embedding.
        
        Args:
            request: EmbeddingRequest with text
        
        Returns:
            EmbeddingResponse with 768-dim vector
        """
        start_time = time.perf_counter()
        
        try:
            # Build payload (OpenAI-compatible format)
            payload = {
                "input": request.text,
                "model": request.model
            }
            
            # Make API call
            async with create_http_client(timeout_seconds=request.timeout_seconds) as client:
                response = await client.post(
                    f"{self.service_url}/v1/embeddings",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            if response.status_code != 200:
                error = LLMError(
                    type="provider_error",
                    message=f"Embedding service error: {response.status_code}",
                    retryable=response.status_code >= 500
                )
                telemetry = TelemetryData(
                    model_id=request.model,
                    provider="self_hosted_embedding",
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=latency_ms,
                    success=False,
                    error_type="provider_error",
                    request_id=request.request_id,
                    organization_id=request.organization_id
                )
                
                return EmbeddingResponse(
                    success=False,
                    telemetry=telemetry,
                    error=error
                )
            
            # Parse response
            response_data = response.json()
            embedding = response_data['data'][0]['embedding']
            
            # Create telemetry
            usage = response_data.get('usage', {})
            telemetry = TelemetryData(
                model_id=request.model,
                provider="self_hosted_embedding",
                prompt_tokens=usage.get('prompt_tokens', len(request.text) // 4),
                completion_tokens=0,
                total_tokens=usage.get('total_tokens', len(request.text) // 4),
                latency_ms=latency_ms,
                success=True,
                request_id=request.request_id,
                organization_id=request.organization_id
            )
            
            logger.info(
                f"Embedding generated: {len(embedding)} dimensions",
                extra={
                    "event_type": "llm.embedding.completed",
                    "dimensions": len(embedding),
                    "latency_ms": latency_ms
                }
            )
            
            return EmbeddingResponse(
                success=True,
                embedding=embedding,
                dimensions=len(embedding),
                telemetry=telemetry,
                raw_response=response_data
            )
        
        except httpx.TimeoutException:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            error = LLMError(
                type="timeout",
                message=f"Embedding service timeout after {request.timeout_seconds}s",
                retryable=True
            )
            telemetry = TelemetryData(
                model_id=request.model,
                provider="self_hosted_embedding",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=latency_ms,
                success=False,
                error_type="timeout",
                request_id=request.request_id,
                organization_id=request.organization_id
            )
            
            return EmbeddingResponse(
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
            telemetry = TelemetryData(
                model_id=request.model,
                provider="self_hosted_embedding",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=latency_ms,
                success=False,
                error_type="unknown",
                request_id=request.request_id,
                organization_id=request.organization_id
            )
            
            logger.error(
                f"Embedding error: {str(e)}",
                extra={"event_type": "llm.embedding.error"},
                exc_info=True
            )
            
            return EmbeddingResponse(
                success=False,
                telemetry=telemetry,
                error=error
            )
    
    def get_embedding_dimension(self, model: str) -> int:
        """Get embedding dimensionality"""
        return self.embedding_dimension
