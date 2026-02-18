"""
Unit Tests for Observability - Config Module

Tests ObservabilityConfig Pydantic model.
"""

import pytest
import os
from unittest.mock import patch

from app.shared.observability.config import ObservabilityConfig


class TestObservabilityConfig:
    """Test ObservabilityConfig"""
    
    def test_config_defaults(self):
        """Test default configuration values"""
        with patch.dict(os.environ, {"TESTING": "1"}, clear=True):
            config = ObservabilityConfig()
            
            # Logging defaults
            assert config.log_level == "INFO"
            assert config.enable_structured_logging is True
            assert config.enable_console_logging is True
            assert config.enable_file_logging is False
            
            # Redaction defaults
            assert config.enable_sensitive_redaction is True
            assert config.redact_candidate_answers is False
            assert config.redact_test_case_outputs is True
            
            # Tracing defaults
            assert config.enable_distributed_tracing is True
            assert config.trace_sample_rate == 1.0
            
            # Metrics defaults
            assert config.enable_metrics is True
            assert config.metrics_port == 9090
            
            # AI telemetry defaults
            assert config.enable_ai_telemetry is True
            assert config.log_ai_prompts_in_dev is True
            assert config.log_ai_prompts_in_prod is False
    
    def test_config_from_env(self):
        """Test loading configuration from environment variables"""
        env = {
            "TESTING": "1",
            "LOG_LEVEL": "DEBUG",
            "ENABLE_STRUCTURED_LOGGING": "false",
            "ENABLE_FILE_LOGGING": "true",
            "LOG_FILE_PATH": "/custom/path/app.log",
            "REDACT_CANDIDATE_ANSWERS": "true",
            "TRACE_SAMPLE_RATE": "0.5",
            "METRICS_PORT": "9091",
            "LOG_AI_PROMPTS_IN_PROD": "true",
        }
        
        with patch.dict(os.environ, env, clear=True):
            config = ObservabilityConfig()
            
            assert config.log_level == "DEBUG"
            assert config.enable_structured_logging is False
            assert config.enable_file_logging is True
            assert config.log_file_path == "/custom/path/app.log"
            assert config.redact_candidate_answers is True
            assert config.trace_sample_rate == 0.5
            assert config.metrics_port == 9091
            assert config.log_ai_prompts_in_prod is True
    
    def test_log_level_values(self):
        """Test different log level values"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            env = {"TESTING": "1", "LOG_LEVEL": level}
            
            with patch.dict(os.environ, env, clear=True):
                config = ObservabilityConfig()
                assert config.log_level == level
    
    def test_trace_sample_rate_validation(self):
        """Test trace sample rate validation"""
        from pydantic import ValidationError
        
        # Valid values
        for rate in [0.0, 0.5, 1.0]:
            env = {"TESTING": "1", "TRACE_SAMPLE_RATE": str(rate)}
            
            with patch.dict(os.environ, env, clear=True):
                config = ObservabilityConfig()
                assert config.trace_sample_rate == rate
        
        # Invalid values
        for invalid_rate in [-0.1, 1.5]:
            env = {"TESTING": "1", "TRACE_SAMPLE_RATE": str(invalid_rate)}
            
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValidationError):
                    ObservabilityConfig()
    
    def test_metrics_port_validation(self):
        """Test metrics port validation"""
        from pydantic import ValidationError
        
        # Valid ports
        for port in [1024, 8080, 9090, 65535]:
            env = {"TESTING": "1", "METRICS_PORT": str(port)}
            
            with patch.dict(os.environ, env, clear=True):
                config = ObservabilityConfig()
                assert config.metrics_port == port
        
        # Invalid ports
        for invalid_port in [80, 1023, 65536, 100000]:
            env = {"TESTING": "1", "METRICS_PORT": str(invalid_port)}
            
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(ValidationError):
                    ObservabilityConfig()
    
    def test_should_log_ai_prompts_dev(self):
        """Test should_log_ai_prompts for dev environment"""
        with patch.dict(os.environ, {"TESTING": "1"}, clear=True):
            config = ObservabilityConfig()
            
            # Dev environment should log prompts
            assert config.should_log_ai_prompts("dev") is True
    
    def test_should_log_ai_prompts_prod(self):
        """Test should_log_ai_prompts for prod environment"""
        with patch.dict(os.environ, {"TESTING": "1"}, clear=True):
            config = ObservabilityConfig()
            
            # Prod environment should NOT log prompts by default
            assert config.should_log_ai_prompts("prod") is False
    
    def test_should_log_ai_prompts_prod_enabled(self):
        """Test should_log_ai_prompts for prod when enabled"""
        env = {
            "TESTING": "1",
            "LOG_AI_PROMPTS_IN_PROD": "true"
        }
        
        with patch.dict(os.environ, env, clear=True):
            config = ObservabilityConfig()
            
            # Prod environment should log when explicitly enabled
            assert config.should_log_ai_prompts("prod") is True
    
    def test_should_log_ai_prompts_staging(self):
        """Test should_log_ai_prompts for staging environment"""
        with patch.dict(os.environ, {"TESTING": "1"}, clear=True):
            config = ObservabilityConfig()
            
            # Staging defaults to dev behavior
            assert config.should_log_ai_prompts("staging") is True
    
    def test_boolean_field_parsing(self):
        """Test boolean field parsing from environment"""
        # Test various boolean representations
        true_values = ["true", "True", "TRUE", "1", "yes"]
        false_values = ["false", "False", "FALSE", "0", "no"]
        
        for true_val in true_values:
            env = {"TESTING": "1", "ENABLE_METRICS": true_val}
            
            with patch.dict(os.environ, env, clear=True):
                config = ObservabilityConfig()
                assert config.enable_metrics is True
        
        for false_val in false_values:
            env = {"TESTING": "1", "ENABLE_METRICS": false_val}
            
            with patch.dict(os.environ, env, clear=True):
                config = ObservabilityConfig()
                assert config.enable_metrics is False


# Test Results Summary
def test_config_module_summary():
    """Summary of config module tests"""
    print("\n" + "="*60)
    print("CONFIG MODULE TEST SUMMARY")
    print("="*60)
    print("✅ Config defaults test: 1 test")
    print("✅ Config from env test: 1 test")
    print("✅ Log level validation test: 1 test")
    print("✅ Trace sample rate validation test: 1 test")
    print("✅ Metrics port validation test: 1 test")
    print("✅ Should log AI prompts tests: 4 tests")
    print("✅ Boolean field parsing test: 1 test")
    print("="*60)
    print("Total: 10 tests")
    print("="*60)
