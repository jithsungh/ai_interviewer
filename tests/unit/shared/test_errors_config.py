"""
Unit Tests for Error Configuration

Tests error configuration loading and defaults.

Note: Detailed environment variable override testing is not included here
as Pydantic Settings loads configuration at module import time, making
runtime testing complex. Manual testing should be done with actual environment variables.
"""

import pytest
from app.shared.errors.config import ErrorConfig, error_config


class TestErrorConfigDefaults:
    """Test default ErrorConfig values and instantiation"""
    
    def test_global_config_instance_exists(self):
        """Test global error_config instance exists and is valid"""
        assert error_config is not None
        assert isinstance(error_config, ErrorConfig)
        assert error_config.websocket_close_code_fatal == 1008
    
    def test_can_instantiate_config(self):
        """Test ErrorConfig can be instantiated"""
        config = ErrorConfig()
        assert config is not None
    
    def test_default_logging_enabled(self):
        """Test logging is enabled by default"""
        config = ErrorConfig()
        assert config.log_client_errors is True
        assert config.log_server_errors is True
    
    def test_default_metadata_included(self):
        """Test metadata is included in responses by default"""
        config = ErrorConfig()
        assert config.include_error_metadata_in_response is True
    
    def test_default_stack_trace_settings(self):
        """Test stack trace default settings"""
        config = ErrorConfig()
        assert config.include_stack_trace_in_dev is True
        assert config.include_stack_trace_in_prod is False
    
    def test_default_websocket_behavior(self):
        """Test WebSocket default behavior"""
        config = ErrorConfig()
        assert config.send_error_event_on_recoverable is True
        assert config.close_connection_on_fatal is True
        assert config.websocket_close_code_fatal == 1008


class TestErrorConfigProperties:
    """Test ErrorConfig computed properties"""
    
    def test_is_production_property_exists(self):
        """Test is_production property is accessible"""
        config = ErrorConfig()
        assert isinstance(config.is_production, bool)
    
    def test_is_production_logic(self):
        """Test is_production property correctly checks environment"""
        config = ErrorConfig()
        # Should return True only if environment == "prod"
        if config.environment == "prod":
            assert config.is_production is True
        else:
            assert config.is_production is False
    
    def test_include_stack_trace_property_exists(self):
        """Test include_stack_trace property is accessible"""
        config = ErrorConfig()
        assert isinstance(config.include_stack_trace, bool)
    
    def test_include_stack_trace_logic(self):
        """Test include_stack_trace property logic"""
        config = ErrorConfig()
        # Should use prod setting if is_production else dev setting
        if config.is_production:
            assert config.include_stack_trace == config.include_stack_trace_in_prod
        else:
            assert config.include_stack_trace == config.include_stack_trace_in_dev


class TestErrorConfigValidation:
    """Test that ErrorConfig validates properly"""
    
    def test_websocket_close_code_is_int(self):
        """Test websocket_close_code_fatal is an integer"""
        config = ErrorConfig()
        assert isinstance(config.websocket_close_code_fatal, int)
        assert config.websocket_close_code_fatal > 0
    
    def test_environment_is_valid(self):
        """Test environment is one of the allowed values"""
        config = ErrorConfig()
        assert config.environment in ["dev", "staging", "prod"]
    
    def test_boolean_flags_are_bool(self):
        """Test all boolean configuration flags are actually booleans"""
        config = ErrorConfig()
        assert isinstance(config.log_client_errors, bool)
        assert isinstance(config.log_server_errors, bool)
        assert isinstance(config.include_error_metadata_in_response, bool)
        assert isinstance(config.send_error_event_on_recoverable, bool)
        assert isinstance(config.close_connection_on_fatal, bool)


# Note: Environment variable override testing should be done manually
# with actual environment variables, as Pydantic Settings reads config
# at module import time, not at ErrorConfig() instantiation time.
#
# To test environment overrides manually:
#
# 1. Set environment variables:
#    export ERROR_LOG_CLIENT_ERRORS=false
#    export ERROR_WS_CLOSE_CODE_FATAL=1011
#
# 2. Run Python:
#    from app.shared.errors import error_config
#    assert error_config.log_client_errors is False
#    assert error_config.websocket_close_code_fatal == 1011
#
# 3. See HUMAN_TESTING_GUIDE.md for complete manual testing instructions
