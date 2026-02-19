"""
Integration Tests for Error Module

Tests end-to-end error handling scenarios.
"""

import pytest
from app.shared.errors import (
    AuthenticationError,
    ValidationError,
    DomainInvariantViolation,
    serialize_rest_error,
    serialize_websocket_error,
    is_fatal_error,
    get_log_level,
    error_config,
)


class TestErrorEndToEnd:
    """Test complete error handling workflows"""
    
    def test_rest_api_authentication_error_flow(self):
        """Test complete REST API authentication error flow"""
        # 1. Create error
        error = AuthenticationError(
            message="Access token expired at 2026-02-19T10:00:00Z",
            request_id="req_abc123",
            metadata={"expired_at": "2026-02-19T10:00:00Z"}
        )
        
        # 2. Serialize for REST response
        response = serialize_rest_error(error)
        
        # 3. Verify response structure
        assert response["error"]["code"] == "AUTHENTICATION_FAILED"
        assert response["error"]["message"] == "Access token expired at 2026-02-19T10:00:00Z"
        assert response["error"]["request_id"] == "req_abc123"
        assert response["error"]["metadata"]["expired_at"] == "2026-02-19T10:00:00Z"
        
        # 4. Verify error properties
        assert error.http_status_code == 401
        assert is_fatal_error(error) is True
        assert get_log_level(error) == "WARN"
    
    def test_websocket_validation_error_flow(self):
        """Test complete WebSocket validation error flow (recoverable)"""
        # 1. Create error
        error = ValidationError(
            message="Invalid answer format",
            field="answer_text",
            request_id="req_xyz789"
        )
        
        # 2. Check if recoverable (should keep connection open)
        assert is_fatal_error(error) is False
        
        # 3. Serialize for WebSocket event
        event = serialize_websocket_error(error)
        
        # 4. Verify event structure
        assert event["event"] == "error"
        assert event["payload"]["code"] == "VALIDATION_ERROR"
        assert event["payload"]["message"] == "Invalid answer format"
        assert event["payload"]["metadata"]["field"] == "answer_text"
        
        # 5. Verify should send error event but keep connection
        assert error_config.send_error_event_on_recoverable is True
        assert error.http_status_code == 422
    
    def test_websocket_fatal_error_flow(self):
        """Test complete WebSocket fatal error flow (close connection)"""
        # 1. Create error
        error = DomainInvariantViolation(
            invariant="exchange_immutable",
            message="Exchange was modified after creation",
            request_id="req_critical_001",
            metadata={"exchange_id": 42}
        )
        
        # 2. Check if fatal (should close connection)
        assert is_fatal_error(error) is True
        
        # 3. Serialize for WebSocket event
        event = serialize_websocket_error(error)
        
        # 4. Send event
        assert event["event"] == "error"
        assert event["payload"]["code"] == "DOMAIN_INVARIANT_VIOLATION"
        
        # 5. Get close code for WebSocket
        close_code = error_config.websocket_close_code_fatal
        assert close_code == 1008  # Policy Violation
        
        # 6. Verify critical logging
        assert get_log_level(error) == "CRITICAL"
        assert error.http_status_code == 500
    
    def test_error_propagation_with_context_enrichment(self):
        """Test error enrichment as it propagates up the stack"""
        # Low-level error without context
        error = ValidationError(message="Invalid email")
        
        # Mid-level adds field context
        error.metadata["field"] = "email"
        error.metadata["attempted_value"] = "not-an-email"
        
        # High-level adds request context
        error.request_id = "req_enriched_123"
        
        # Serialize with full context
        response = serialize_rest_error(error)
        
        assert response["error"]["request_id"] == "req_enriched_123"
        assert response["error"]["metadata"]["field"] == "email"
        assert response["error"]["metadata"]["attempted_value"] == "not-an-email"
    
    def test_backward_compatibility_with_existing_code(self):
        """Test backward compatibility with existing ApplicationError usage"""
        from app.shared.errors import ApplicationError
        
        # Old-style initialization (as used in redis/locks.py)
        error = ApplicationError(
            message="Failed to acquire lock",
            status_code=409,
            error_code="LOCK_ACQUISITION_FAILED"
        )
        
        # Verify works with new serialization
        response = serialize_rest_error(error)
        
        assert response["error"]["code"] == "LOCK_ACQUISITION_FAILED"
        assert response["error"]["message"] == "Failed to acquire lock"
        
        # Verify backward compat properties
        assert error.status_code == 409
        assert error.http_status_code == 409
        assert error.details == {}


class TestMultiProtocolErrorHandling:
    """Test error handling across multiple protocols"""
    
    def test_same_error_different_serializations(self):
        """Test same error serialized differently for REST vs WebSocket"""
        error = ValidationError(
            message="Invalid input",
            field="name",
            request_id="req_multi_001"
        )
        
        # REST serialization
        rest_response = serialize_rest_error(error)
        assert "error" in rest_response
        assert rest_response["error"]["request_id"] == "req_multi_001"
        
        # WebSocket serialization
        ws_event = serialize_websocket_error(error)
        assert "event" in ws_event
        assert ws_event["event"] == "error"
        assert "request_id" not in ws_event["payload"]  # WebSocket uses connection_id
        
        # Same error code and message
        assert rest_response["error"]["code"] == ws_event["payload"]["code"]
        assert rest_response["error"]["message"] == ws_event["payload"]["message"]
