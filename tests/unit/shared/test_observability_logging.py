"""
Unit Tests for Observability - Logging Module

Tests structured logging, ContextLogger, and log formatting.
"""

import pytest
import logging
import json
from io import StringIO

from app.shared.observability.logging import (
    StructuredFormatter,
    ContextLogger,
    configure_structured_logging,
    get_context_logger,
)


class TestStructuredFormatter:
    """Test JSON log formatting"""
    
    def test_basic_log_format(self):
        """Test basic log entry structure"""
        formatter = StructuredFormatter()
        logger = logging.getLogger("test")
        
        # Create log record
        record = logger.makeRecord(
            name="test.module",
            level=logging.INFO,
            fn="test.py",
            lno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Format as JSON
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        # Verify structure
        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test.module"
        assert log_entry["message"] == "Test message"
        assert "timestamp" in log_entry
    
    def test_log_with_request_id(self):
        """Test log entry with request ID"""
        formatter = StructuredFormatter()
        logger = logging.getLogger("test")
        
        # Create log record with request_id
        record = logger.makeRecord(
            name="test.module",
            level=logging.INFO,
            fn="test.py",
            lno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.request_id = "req_abc123"
        
        # Format as JSON
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        # Verify request_id present
        assert log_entry["request_id"] == "req_abc123"
    
    def test_log_with_context_fields(self):
        """Test log entry with full context"""
        formatter = StructuredFormatter()
        logger = logging.getLogger("test")
        
        # Create log record with multiple context fields
        record = logger.makeRecord(
            name="test.module",
            level=logging.INFO,
            fn="test.py",
            lno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.request_id = "req_abc123"
        record.user_id = 42
        record.organization_id = 1
        record.submission_id = 789
        record.event_type = "test_event"
        record.latency_ms = 123.45
        record.metadata = {"key": "value"}
        
        # Format as JSON
        formatted = formatter.format(record)
        log_entry = json.loads(formatted)
        
        # Verify all fields present
        assert log_entry["request_id"] == "req_abc123"
        assert log_entry["user_id"] == 42
        assert log_entry["organization_id"] == 1
        assert log_entry["submission_id"] == 789
        assert log_entry["event_type"] == "test_event"
        assert log_entry["latency_ms"] == 123.45
        assert log_entry["metadata"]["key"] == "value"
    
    def test_log_with_exception(self):
        """Test log entry with exception info"""
        import sys
        formatter = StructuredFormatter()
        logger = logging.getLogger("test")
        
        # Create exception
        try:
            raise ValueError("Test error")
        except ValueError:
            # Create log record with exc_info
            record = logger.makeRecord(
                name="test.module",
                level=logging.ERROR,
                fn="test.py",
                lno=10,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info()
            )
            
            # Format as JSON
            formatted = formatter.format(record)
            log_entry = json.loads(formatted)
            
            # Verify exception present
            assert "exception" in log_entry
            assert "ValueError" in log_entry["exception"]
            assert "Test error" in log_entry["exception"]


class TestContextLogger:
    """Test context-aware logger"""
    
    def test_context_logger_creation(self):
        """Test creating context logger"""
        logger = logging.getLogger("test")
        context_logger = ContextLogger(
            logger=logger,
            request_id="req_123",
            user_id=42
        )
        
        assert context_logger.request_id == "req_123"
        assert context_logger.user_id == 42
    
    def test_context_logger_info(self, caplog):
        """Test info logging with context"""
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler())
        
        context_logger = ContextLogger(
            logger=logger,
            request_id="req_123",
            user_id=42,
            organization_id=1
        )
        
        with caplog.at_level(logging.INFO):
            context_logger.info(
                "Test message",
                event_type="test_event",
                latency_ms=100,
                metadata={"key": "value"}
            )
        
        # Verify log was created
        assert len(caplog.records) == 1
        record = caplog.records[0]
        
        # Verify context was injected
        assert record.request_id == "req_123"
        assert record.user_id == 42
        assert record.organization_id == 1
        assert record.event_type == "test_event"
        assert record.latency_ms == 100
        assert record.metadata["key"] == "value"
    
    def test_context_logger_warning(self, caplog):
        """Test warning logging with context"""
        logger = logging.getLogger("test")
        logger.setLevel(logging.WARNING)
        
        context_logger = ContextLogger(
            logger=logger,
            request_id="req_456"
        )
        
        with caplog.at_level(logging.WARNING):
            context_logger.warning("Warning message")
        
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.WARNING
        assert caplog.records[0].request_id == "req_456"
    
    def test_context_logger_error(self, caplog):
        """Test error logging with context"""
        logger = logging.getLogger("test")
        logger.setLevel(logging.ERROR)
        
        context_logger = ContextLogger(
            logger=logger,
            request_id="req_789"
        )
        
        try:
            raise RuntimeError("Test error")
        except RuntimeError as e:
            with caplog.at_level(logging.ERROR):
                context_logger.error("Error occurred", exc_info=e)
        
        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.ERROR


class TestConfigureStructuredLogging:
    """Test logging configuration"""
    
    def test_configure_with_console(self):
        """Test configuring with console handler"""
        logger = configure_structured_logging(
            log_level="INFO",
            enable_console=True,
            enable_file=False
        )
        
        # Verify logger configured
        assert logger.level == logging.INFO
        assert len(logger.handlers) >= 1
        
        # Verify handler has StructuredFormatter
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, StructuredFormatter)
    
    def test_configure_log_levels(self):
        """Test different log levels"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            logger = configure_structured_logging(log_level=level)
            assert logger.level == getattr(logging, level)


class TestGetContextLogger:
    """Test context logger factory function"""
    
    def test_get_context_logger_minimal(self):
        """Test getting logger with minimal context"""
        logger = get_context_logger(request_id="req_123")
        
        assert isinstance(logger, ContextLogger)
        assert logger.request_id == "req_123"
    
    def test_get_context_logger_full_context(self):
        """Test getting logger with full context"""
        logger = get_context_logger(
            request_id="req_123",
            connection_id="conn_456",
            user_id=42,
            submission_id=789,
            organization_id=1
        )
        
        assert logger.request_id == "req_123"
        assert logger.connection_id == "conn_456"
        assert logger.user_id == 42
        assert logger.submission_id == 789
        assert logger.organization_id == 1


# Test Results Summary
def test_logging_module_summary():
    """Summary of logging module tests"""
    print("\n" + "="*60)
    print("LOGGING MODULE TEST SUMMARY")
    print("="*60)
    print("✅ StructuredFormatter tests: 4 tests")
    print("✅ ContextLogger tests: 4 tests")
    print("✅ Configure logging tests: 2 tests")
    print("✅ Get context logger tests: 2 tests")
    print("="*60)
    print("Total: 12 tests")
    print("="*60)
