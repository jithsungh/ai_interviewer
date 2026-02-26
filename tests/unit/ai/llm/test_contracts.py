"""
Unit Tests for LLM Contracts

Tests request/response DTOs, validation, and data structures.
"""

import pytest
from datetime import datetime
from app.ai.llm.contracts import (
    LLMRequest,
    LLMResponse,
    TelemetryData,
    LLMError,
    EmbeddingRequest,
    EmbeddingResponse,
    ClarificationRequest
)


class TestLLMRequest:
    """Test LLMRequest validation and normalization"""
    
    def test_valid_request(self):
        """Valid request with all required fields"""
        request = LLMRequest(
            prompt="Test prompt",
            model="llama-3.3-70b-versatile"
        )
        
        assert request.prompt == "Test prompt"
        assert request.model == "llama-3.3-70b-versatile"
        assert request.temperature == 0.7
        assert request.timeout_seconds == 60
    
    def test_deterministic_mode(self):
        """Deterministic mode forces temperature=0"""
        request = LLMRequest(
            prompt="Test",
            model="gpt-4",
            temperature=0.9,
            deterministic=True
        )
        
        assert request.temperature == 0.0
        assert request.top_p == 1.0
        assert request.deterministic is True
    
    def test_temperature_validation(self):
        """Temperature must be in [0.0, 2.0]"""
        with pytest.raises(ValueError, match="temperature must be in"):
            LLMRequest(
                prompt="Test",
                model="gpt-4",
                temperature=3.0
            )
        
        with pytest.raises(ValueError, match="temperature must be in"):
            LLMRequest(
                prompt="Test",
                model="gpt-4",
                temperature=-0.1
            )
    
    def test_timeout_validation(self):
        """Timeout must be in [10, 300] seconds"""
        with pytest.raises(ValueError, match="timeout_seconds must be in"):
            LLMRequest(
                prompt="Test",
                model="gpt-4",
                timeout_seconds=5
            )
        
        with pytest.raises(ValueError, match="timeout_seconds must be in"):
            LLMRequest(
                prompt="Test",
                model="gpt-4",
                timeout_seconds=400
            )
    
    def test_max_tokens_validation(self):
        """Max tokens must be positive"""
        with pytest.raises(ValueError, match="max_tokens must be > 0"):
            LLMRequest(
                prompt="Test",
                model="gpt-4",
                max_tokens=0
            )


class TestTelemetryData:
    """Test telemetry data validation and computation"""
    
    def test_telemetry_creation(self):
        """Create telemetry with valid data"""
        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=1250,
            success=True
        )
        
        assert telemetry.model_id == "gpt-4"
        assert telemetry.total_tokens == 150
        assert telemetry.success is True
    
    def test_total_tokens_computation(self):
        """Total tokens computed from prompt + completion"""
        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=999,  # Will be recomputed
            latency_ms=1000,
            success=True
        )
        
        # Total tokens recomputed in __post_init__
        assert telemetry.total_tokens == 150
    
    def test_negative_tokens_normalized(self):
        """Negative token counts normalized to 0"""
        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=-10,
            completion_tokens=-5,
            total_tokens=0,
            latency_ms=1000,
            success=False
        )
        
        assert telemetry.prompt_tokens == 0
        assert telemetry.completion_tokens == 0
        assert telemetry.total_tokens == 0


class TestLLMResponse:
    """Test LLMResponse validation"""
    
    def test_success_response(self):
        """Success response must have text"""
        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
            latency_ms=1000,
            success=True
        )
        
        response = LLMResponse(
            success=True,
            text="Generated text",
            telemetry=telemetry
        )
        
        assert response.success is True
        assert response.text == "Generated text"
        assert response.error is None
    
    def test_success_without_text_fails(self):
        """Success response without text raises error"""
        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=0,
            total_tokens=10,
            latency_ms=1000,
            success=False
        )
        
        with pytest.raises(ValueError, match="Success response must include text"):
            LLMResponse(
                success=True,
                text=None,
                telemetry=telemetry
            )
    
    def test_failure_response(self):
        """Failure response must have error"""
        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=0,
            total_tokens=10,
            latency_ms=1000,
            success=False,
            error_type="timeout"
        )
        
        error = LLMError(
            type="timeout",
            message="Request timeout",
            retryable=True
        )
        
        response = LLMResponse(
            success=False,
            telemetry=telemetry,
            error=error
        )
        
        assert response.success is False
        assert response.error.type == "timeout"
        assert response.error.retryable is True
    
    def test_failure_without_error_fails(self):
        """Failure response without error raises error"""
        telemetry = TelemetryData(
            model_id="gpt-4",
            provider="openai",
            prompt_tokens=10,
            completion_tokens=0,
            total_tokens=10,
            latency_ms=1000,
            success=False
        )
        
        with pytest.raises(ValueError, match="Failure response must include error"):
            LLMResponse(
                success=False,
                telemetry=telemetry,
                error=None
            )


class TestEmbeddingRequest:
    """Test embedding request validation"""
    
    def test_valid_embedding_request(self):
        """Valid embedding request"""
        request = EmbeddingRequest(
            text="Test text to embed",
            model="all-mpnet-base-v2"
        )
        
        assert request.text == "Test text to embed"
        assert request.model == "all-mpnet-base-v2"
        assert request.timeout_seconds == 30
    
    def test_empty_text_fails(self):
        """Empty text raises error"""
        with pytest.raises(ValueError, match="text cannot be empty"):
            EmbeddingRequest(text="", model="all-mpnet-base-v2")


class TestEmbeddingResponse:
    """Test embedding response validation"""
    
    def test_success_response(self):
        """Success response must have embedding"""
        telemetry = TelemetryData(
            model_id="all-mpnet-base-v2",
            provider="self_hosted",
            prompt_tokens=10,
            completion_tokens=0,
            total_tokens=10,
            latency_ms=500,
            success=True
        )
        
        embedding = [0.1] * 768
        response = EmbeddingResponse(
            success=True,
            embedding=embedding,
            telemetry=telemetry
        )
        
        assert response.success is True
        assert len(response.embedding) == 768
        assert response.dimensions == 768
    
    def test_dimensions_computed(self):
        """Dimensions computed from embedding length"""
        telemetry = TelemetryData(
            model_id="all-mpnet-base-v2",
            provider="self_hosted",
            prompt_tokens=10,
            completion_tokens=0,
            total_tokens=10,
            latency_ms=500,
            success=True
        )
        
        embedding = [0.1] * 1536  # OpenAI ada-002 size
        response = EmbeddingResponse(
            success=True,
            embedding=embedding,
            telemetry=telemetry
        )
        
        assert response.dimensions == 1536


class TestClarificationRequest:
    """Test clarification request validation"""
    
    def test_valid_clarification_request(self):
        """Valid clarification request"""
        request = ClarificationRequest(
            original_question="What is a binary search tree?",
            candidate_clarification_request="What are balanced trees?",
            model="gpt-4",
            submission_id=1,
            exchange_id=1
        )
        
        assert request.temperature == 0.0
        assert request.submission_id == 1
    
    def test_temperature_must_be_zero(self):
        """Clarifications must use temperature=0 for fairness"""
        with pytest.raises(ValueError, match="temperature=0.0 for fairness"):
            ClarificationRequest(
                original_question="Test",
                candidate_clarification_request="Clarify",
                model="gpt-4",
                temperature=0.7,
                submission_id=1,
                exchange_id=1
            )
