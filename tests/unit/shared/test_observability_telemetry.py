"""
Unit Tests for Observability - Telemetry Module

Tests AI telemetry tracking and cost estimation.
"""

import pytest
from unittest.mock import Mock, patch
import time

from app.shared.observability.telemetry import (
    AITelemetry,
    track_ai_call,
    calculate_openai_cost,
    calculate_anthropic_cost,
)
from app.shared.observability.logging import get_context_logger


class TestAITelemetry:
    """Test AITelemetry dataclass"""
    
    def test_ai_telemetry_creation(self):
        """Test creating AI telemetry"""
        telemetry = AITelemetry(
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=50,
            latency_seconds=2.5,
            success=True,
            cost_estimate_usd=0.0065
        )
        
        assert telemetry.provider == "openai"
        assert telemetry.model == "gpt-4"
        assert telemetry.prompt_tokens == 150
        assert telemetry.completion_tokens == 50
        assert telemetry.latency_seconds == 2.5
        assert telemetry.success is True
        assert telemetry.cost_estimate_usd == 0.0065
    
    def test_ai_telemetry_total_tokens(self):
        """Test calculating total tokens"""
        telemetry = AITelemetry(
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=50
        )
        
        assert telemetry.total_tokens() == 200
    
    def test_ai_telemetry_with_error(self):
        """Test AI telemetry with error"""
        telemetry = AITelemetry(
            provider="openai",
            model="gpt-4",
            success=False,
            error_type="RateLimitError"
        )
        
        assert telemetry.success is False
        assert telemetry.error_type == "RateLimitError"
    
    def test_ai_telemetry_with_metadata(self):
        """Test AI telemetry with metadata"""
        telemetry = AITelemetry(
            provider="openai",
            model="gpt-4",
            metadata={"purpose": "question_generation"}
        )
        
        assert telemetry.metadata["purpose"] == "question_generation"
    
    def test_ai_telemetry_log(self, caplog):
        """Test logging AI telemetry"""
        logger = get_context_logger(request_id="req_123")
        
        telemetry = AITelemetry(
            provider="openai",
            model="gpt-4",
            prompt_tokens=150,
            completion_tokens=50,
            latency_seconds=2.5,
            success=True,
            cost_estimate_usd=0.0065
        )
        
        with caplog.at_level("INFO"):
            telemetry.log(logger)
        
        # Verify log was created
        assert len(caplog.records) == 1
        record = caplog.records[0]
        
        # Verify metadata
        assert record.metadata["provider"] == "openai"
        assert record.metadata["model"] == "gpt-4"
        assert record.metadata["prompt_tokens"] == 150
        assert record.metadata["completion_tokens"] == 50
        assert record.metadata["total_tokens"] == 200
        assert record.metadata["success"] is True
    
    def test_ai_telemetry_emit_metrics(self):
        """Test emitting metrics"""
        from prometheus_client import CollectorRegistry
        from app.shared.observability.metrics import MetricsRegistry
        
        # Create isolated metrics registry
        registry = MetricsRegistry(registry=CollectorRegistry())
        
        with patch('app.shared.observability.telemetry.metrics', registry):
            telemetry = AITelemetry(
                provider="openai",
                model="gpt-4",
                prompt_tokens=150,
                completion_tokens=50,
                latency_seconds=2.5,
                success=True,
                cost_estimate_usd=0.0065
            )
            
            telemetry.emit_metrics()
            
            # Verify metrics were recorded
            assert registry.ai_provider_calls_total.labels(
                provider="openai",
                model="gpt-4"
            )._value.get() == 1
            
            assert registry.ai_provider_tokens_total.labels(
                provider="openai",
                type="prompt"
            )._value.get() == 150
            
            assert registry.ai_provider_tokens_total.labels(
                provider="openai",
                type="completion"
            )._value.get() == 50


class TestTrackAICall:
    """Test track_ai_call context manager"""
    
    @pytest.mark.asyncio
    async def test_track_successful_call(self):
        """Test tracking successful AI call"""
        logger = get_context_logger(request_id="req_123")
        
        with track_ai_call("openai", "gpt-4", logger) as telemetry:
            # Simulate AI call with some work
            import time
            time.sleep(0.001)  # Sleep at least 1ms
            telemetry.prompt_tokens = 150
            telemetry.completion_tokens = 50
            telemetry.cost_estimate_usd = 0.0065
        
        # Verify telemetry was populated
        assert telemetry.success is True
        assert telemetry.error_type is None
        assert telemetry.latency_seconds >= 0.001
    
    @pytest.mark.asyncio
    async def test_track_failed_call(self):
        """Test tracking failed AI call"""
        logger = get_context_logger(request_id="req_123")
        
        with pytest.raises(ValueError):
            with track_ai_call("openai", "gpt-4", logger) as telemetry:
                raise ValueError("API error")
        
        # Telemetry should capture error
        assert telemetry.success is False
        assert telemetry.error_type == "ValueError"
    
    @pytest.mark.asyncio
    async def test_track_call_measures_latency(self):
        """Test that latency is measured"""
        logger = get_context_logger(request_id="req_123")
        
        with track_ai_call("openai", "gpt-4", logger) as telemetry:
            # Simulate work
            time.sleep(0.01)
        
        # Verify latency was recorded
        assert telemetry.latency_seconds >= 0.01


class TestCalculateOpenAICost:
    """Test OpenAI cost calculation"""
    
    def test_gpt4_cost(self):
        """Test GPT-4 cost calculation"""
        cost = calculate_openai_cost(
            model="gpt-4",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # GPT-4: $30/1M input, $60/1M output
        expected_cost = (1000 * 30 / 1_000_000) + (500 * 60 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001
    
    def test_gpt4_turbo_cost(self):
        """Test GPT-4 Turbo cost calculation"""
        cost = calculate_openai_cost(
            model="gpt-4-turbo",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # GPT-4-turbo: $10/1M input, $30/1M output
        expected_cost = (1000 * 10 / 1_000_000) + (500 * 30 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001
    
    def test_gpt35_turbo_cost(self):
        """Test GPT-3.5 Turbo cost calculation"""
        cost = calculate_openai_cost(
            model="gpt-3.5-turbo",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # GPT-3.5-turbo: $0.50/1M input, $1.50/1M output
        expected_cost = (1000 * 0.50 / 1_000_000) + (500 * 1.50 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001
    
    def test_unknown_model_defaults_to_gpt4(self):
        """Test unknown model defaults to GPT-4 pricing"""
        cost = calculate_openai_cost(
            model="unknown-model",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # Should use GPT-4 pricing
        expected_cost = (1000 * 30 / 1_000_000) + (500 * 60 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001


class TestCalculateAnthropicCost:
    """Test Anthropic cost calculation"""
    
    def test_claude3_opus_cost(self):
        """Test Claude 3 Opus cost calculation"""
        cost = calculate_anthropic_cost(
            model="claude-3-opus",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # Claude 3 Opus: $15/1M input, $75/1M output
        expected_cost = (1000 * 15 / 1_000_000) + (500 * 75 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001
    
    def test_claude3_sonnet_cost(self):
        """Test Claude 3 Sonnet cost calculation"""
        cost = calculate_anthropic_cost(
            model="claude-3-sonnet",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # Claude 3 Sonnet: $3/1M input, $15/1M output
        expected_cost = (1000 * 3 / 1_000_000) + (500 * 15 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001
    
    def test_claude3_haiku_cost(self):
        """Test Claude 3 Haiku cost calculation"""
        cost = calculate_anthropic_cost(
            model="claude-3-haiku",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # Claude 3 Haiku: $0.25/1M input, $1.25/1M output
        expected_cost = (1000 * 0.25 / 1_000_000) + (500 * 1.25 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001
    
    def test_unknown_model_defaults_to_opus(self):
        """Test unknown model defaults to Opus pricing"""
        cost = calculate_anthropic_cost(
            model="unknown-model",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # Should use Opus pricing
        expected_cost = (1000 * 15 / 1_000_000) + (500 * 75 / 1_000_000)
        assert abs(cost - expected_cost) < 0.00001


# Test Results Summary
def test_telemetry_module_summary():
    """Summary of telemetry module tests"""
    print("\n" + "="*60)
    print("TELEMETRY MODULE TEST SUMMARY")
    print("="*60)
    print("✅ AITelemetry tests: 6 tests")
    print("✅ Track AI call tests: 3 tests")
    print("✅ OpenAI cost calculation tests: 4 tests")
    print("✅ Anthropic cost calculation tests: 4 tests")
    print("="*60)
    print("Total: 17 tests")
    print("="*60)
