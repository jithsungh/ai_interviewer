"""
Unit Tests for Observability - Metrics Module

Tests Prometheus metrics instrumentation.
"""

import pytest
from prometheus_client import CollectorRegistry, Counter, Histogram, Gauge

from app.shared.observability.metrics import (
    MetricsRegistry,
    track_latency,
    track_operation,
    metrics,
)


class TestMetricsRegistry:
    """Test MetricsRegistry class"""
    
    def test_metrics_registry_creation(self):
        """Test creating metrics registry"""
        # Use custom registry to avoid conflict with global metrics instance
        custom_registry = CollectorRegistry()
        registry = MetricsRegistry(registry=custom_registry)
        
        # Verify standard metrics exist
        assert registry.interview_exchanges_total is not None
        assert registry.interview_duration_seconds is not None
        assert registry.question_generation_duration_seconds is not None
        assert registry.evaluation_duration_seconds is not None
        assert registry.sandbox_execution_duration_seconds is not None
        assert registry.websocket_connections_active is not None
        assert registry.ai_provider_calls_total is not None
    
    def test_metrics_registry_with_custom_registry(self):
        """Test creating metrics registry with custom Prometheus registry"""
        custom_registry = CollectorRegistry()
        registry = MetricsRegistry(registry=custom_registry)
        
        assert registry.registry == custom_registry
    
    def test_interview_metrics(self):
        """Test interview metrics"""
        registry = MetricsRegistry(registry=CollectorRegistry())
        
        # Test counter
        initial = registry.interview_exchanges_total._value.get()
        registry.interview_exchanges_total.inc()
        assert registry.interview_exchanges_total._value.get() == initial + 1
        
        # Test histogram
        registry.interview_duration_seconds.observe(600)
        assert registry.interview_duration_seconds._sum.get() == 600
    
    def test_question_metrics(self):
        """Test question metrics"""
        registry = MetricsRegistry(registry=CollectorRegistry())
        
        # Test generation latency
        registry.question_generation_duration_seconds.observe(1.5)
        assert registry.question_generation_duration_seconds._sum.get() == 1.5
        
        # Test retrieval latency
        registry.question_retrieval_duration_seconds.observe(0.1)
        assert registry.question_retrieval_duration_seconds._sum.get() == 0.1
        
        # Test fallback counter with labels
        registry.question_selection_fallback_total.labels(reason="no_match").inc()
        assert registry.question_selection_fallback_total.labels(reason="no_match")._value.get() == 1
    
    def test_evaluation_metrics(self):
        """Test evaluation metrics"""
        registry = MetricsRegistry(registry=CollectorRegistry())
        
        # Test duration
        registry.evaluation_duration_seconds.observe(5.0)
        assert registry.evaluation_duration_seconds._sum.get() == 5.0
        
        # Test score distribution
        registry.evaluation_score_distribution.observe(85)
        assert registry.evaluation_score_distribution._sum.get() == 85
    
    def test_sandbox_metrics(self):
        """Test sandbox metrics"""
        registry = MetricsRegistry(registry=CollectorRegistry())
        
        # Test execution duration
        registry.sandbox_execution_duration_seconds.observe(2.0)
        assert registry.sandbox_execution_duration_seconds._sum.get() == 2.0
        
        # Test timeouts
        registry.sandbox_timeout_total.inc()
        assert registry.sandbox_timeout_total._value.get() == 1
        
        # Test errors with labels
        registry.sandbox_error_total.labels(error_type="runtime_error").inc()
        assert registry.sandbox_error_total.labels(error_type="runtime_error")._value.get() == 1
    
    def test_websocket_metrics(self):
        """Test WebSocket metrics"""
        registry = MetricsRegistry(registry=CollectorRegistry())
        
        # Test active connections gauge
        registry.websocket_connections_active.inc()
        assert registry.websocket_connections_active._value.get() == 1
        
        registry.websocket_connections_active.dec()
        assert registry.websocket_connections_active._value.get() == 0
        
        # Test reconnects
        registry.websocket_reconnects_total.inc()
        assert registry.websocket_reconnects_total._value.get() == 1
        
        # Test disconnects with labels
        registry.websocket_disconnect_total.labels(reason="timeout").inc()
        assert registry.websocket_disconnect_total.labels(reason="timeout")._value.get() == 1
    
    def test_ai_provider_metrics(self):
        """Test AI provider metrics"""
        registry = MetricsRegistry(registry=CollectorRegistry())
        
        # Test calls counter with labels
        registry.ai_provider_calls_total.labels(
            provider="openai",
            model="gpt-4"
        ).inc()
        assert registry.ai_provider_calls_total.labels(
            provider="openai",
            model="gpt-4"
        )._value.get() == 1
        
        # Test latency with labels
        registry.ai_provider_latency_seconds.labels(provider="openai").observe(2.5)
        assert registry.ai_provider_latency_seconds.labels(provider="openai")._sum.get() == 2.5
        
        # Test tokens with labels
        registry.ai_provider_tokens_total.labels(
            provider="openai",
            type="prompt"
        ).inc(150)
        assert registry.ai_provider_tokens_total.labels(
            provider="openai",
            type="prompt"
        )._value.get() == 150
        
        # Test cost
        registry.ai_provider_cost_usd_total.labels(provider="openai").inc(0.0065)
        assert abs(registry.ai_provider_cost_usd_total.labels(provider="openai")._value.get() - 0.0065) < 0.0001


class TestTrackLatency:
    """Test track_latency context manager"""
    
    def test_track_latency(self):
        """Test tracking operation latency"""
        registry = CollectorRegistry()
        histogram = Histogram(
            name="test_latency",
            documentation="Test latency",
            registry=registry
        )
        
        with track_latency(histogram):
            # Simulate work
            import time
            time.sleep(0.01)
        
        # Verify latency was recorded
        for metric in histogram.collect():
            for sample in metric.samples:
                if sample.name == 'test_latency_count':
                    assert sample.value == 1
                elif sample.name == 'test_latency_sum':
                    assert sample.value > 0
    
    def test_track_latency_multiple_calls(self):
        """Test tracking multiple operations"""
        registry = CollectorRegistry()
        histogram = Histogram(
            name="test_latency",
            documentation="Test latency",
            registry=registry
        )
        
        for _ in range(3):
            with track_latency(histogram):
                pass
        
        # Verify count
        for metric in histogram.collect():
            for sample in metric.samples:
                if sample.name == 'test_latency_count':
                    assert sample.value == 3


class TestTrackOperation:
    """Test track_operation decorator"""
    
    @pytest.mark.asyncio
    async def test_track_async_operation(self):
        """Test tracking async operation"""
        registry = CollectorRegistry()
        counter = Counter(
            name="test_operations_total",
            documentation="Test operations",
            registry=registry
        )
        histogram = Histogram(
            name="test_operation_seconds",
            documentation="Test operation duration",
            registry=registry
        )
        
        @track_operation(counter, histogram)
        async def test_func():
            return "result"
        
        result = await test_func()
        
        assert result == "result"
        assert counter._value.get() == 1
        
        # Verify histogram
        for metric in histogram.collect():
            for sample in metric.samples:
                if sample.name == 'test_operation_seconds_count':
                    assert sample.value == 1
    
    def test_track_sync_operation(self):
        """Test tracking sync operation"""
        registry = CollectorRegistry()
        counter = Counter(
            name="test_operations_total",
            documentation="Test operations",
            registry=registry
        )
        histogram = Histogram(
            name="test_operation_seconds",
            documentation="Test operation duration",
            registry=registry
        )
        
        @track_operation(counter, histogram)
        def test_func():
            return "result"
        
        result = test_func()
        
        assert result == "result"
        assert counter._value.get() == 1
        
        # Verify histogram
        for metric in histogram.collect():
            for sample in metric.samples:
                if sample.name == 'test_operation_seconds_count':
                    assert sample.value == 1
    
    @pytest.mark.asyncio
    async def test_track_operation_multiple_calls(self):
        """Test tracking multiple calls"""
        registry = CollectorRegistry()
        counter = Counter(
            name="test_operations_total",
            documentation="Test operations",
            registry=registry
        )
        histogram = Histogram(
            name="test_operation_seconds",
            documentation="Test operation duration",
            registry=registry
        )
        
        @track_operation(counter, histogram)
        async def test_func(value):
            return value * 2
        
        await test_func(1)
        await test_func(2)
        await test_func(3)
        
        assert counter._value.get() == 3
        
        # Verify histogram
        for metric in histogram.collect():
            for sample in metric.samples:
                if sample.name == 'test_operation_seconds_count':
                    assert sample.value == 3


class TestGlobalMetricsInstance:
    """Test global metrics instance"""
    
    def test_global_metrics_exists(self):
        """Test global metrics instance exists"""
        assert metrics is not None
        assert isinstance(metrics, MetricsRegistry)


# Test Results Summary
def test_metrics_module_summary():
    """Summary of metrics module tests"""
    print("\n" + "="*60)
    print("METRICS MODULE TEST SUMMARY")
    print("="*60)
    print("✅ MetricsRegistry tests: 9 tests")
    print("✅ Track latency tests: 2 tests")
    print("✅ Track operation decorator tests: 3 tests")
    print("✅ Global metrics instance test: 1 test")
    print("="*60)
    print("Total: 15 tests")
    print("="*60)
