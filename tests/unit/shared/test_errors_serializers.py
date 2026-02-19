"""
Unit Tests for Error Serialization

Tests REST API and WebSocket error serialization.
"""

import pytest
from app.shared.errors.exceptions import (
    AuthenticationError,
    ValidationError,
    ConflictError,
    InternalServerError,
    ProctoringViolation,
)
from app.shared.errors.serializers import (
    serialize_rest_error,
    serialize_websocket_error,
    serialize_error_for_logging,
)


class TestRESTSerialization:
    """Test REST API error serialization"""
    
    def test_basic_rest_error_format(self):
        """Test basic REST error structure"""
        error = AuthenticationError(
            message="Token expired",
            request_id="req_123"
        )
        
        serialized = serialize_rest_error(error)
        
        assert serialized == {
            "error": {
                "code": "AUTHENTICATION_FAILED",
                "message": "Token expired",
                "request_id": "req_123"
            }
        }
    
    def test_rest_error_with_metadata(self):
        """Test REST error with metadata included"""
        error = ValidationError(
            message="Invalid email",
            field="email",
            request_id="req_123"
        )
        
        serialized = serialize_rest_error(error)
        
        assert serialized["error"]["code"] == "VALIDATION_ERROR"
        assert serialized["error"]["message"] == "Invalid email"
        assert serialized["error"]["request_id"] == "req_123"
        assert "metadata" in serialized["error"]
        assert serialized["error"]["metadata"]["field"] == "email"
    
    def test_rest_error_request_id_override(self):
        """Test REST error with request_id override"""
        error = ConflictError(
            message="Already exists",
            request_id="req_old"
        )
        
        serialized = serialize_rest_error(error, request_id="req_new")
        
        assert serialized["error"]["request_id"] == "req_new"
    
    def test_rest_error_without_metadata(self):
        """Test REST error without metadata (should not include empty metadata)"""
        error = InternalServerError(
            message="Something went wrong"
        )
        
        serialized = serialize_rest_error(error)
        
        assert "metadata" not in serialized["error"]
    
    def test_rest_error_no_request_id(self):
        """Test REST error without request_id"""
        error = AuthenticationError(message="Invalid token")
        
        serialized = serialize_rest_error(error)
        
        assert serialized["error"]["request_id"] is None


class TestWebSocketSerialization:
    """Test WebSocket error serialization"""
    
    def test_basic_websocket_error_format(self):
        """Test basic WebSocket error structure"""
        error = ValidationError(
            message="Invalid answer format"
        )
        
        serialized = serialize_websocket_error(error)
        
        assert serialized == {
            "event": "error",
            "payload": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid answer format"
            }
        }
    
    def test_websocket_error_with_metadata(self):
        """Test WebSocket error with metadata"""
        error = ProctoringViolation(
            event_type="face_not_visible",
            message="Face not detected",
            risk_score=0.8
        )
        
        serialized = serialize_websocket_error(error)
        
        assert serialized["event"] == "error"
        assert serialized["payload"]["code"] == "PROCTORING_VIOLATION"
        assert serialized["payload"]["message"] == "Face not detected"
        assert "metadata" in serialized["payload"]
        assert serialized["payload"]["metadata"]["event_type"] == "face_not_visible"
        assert serialized["payload"]["metadata"]["risk_score"] == 0.8
    
    def test_websocket_error_no_request_id(self):
        """Test WebSocket error omits request_id (uses connection_id instead)"""
        error = ConflictError(
            message="Already paused",
            request_id="req_123"
        )
        
        serialized = serialize_websocket_error(error)
        
        assert "request_id" not in serialized["payload"]
    
    def test_websocket_error_without_metadata(self):
        """Test WebSocket error without metadata"""
        error = AuthenticationError(message="Invalid token")
        
        serialized = serialize_websocket_error(error)
        
        assert "metadata" not in serialized["payload"]


class TestLoggingSerialization:
    """Test error serialization for logging"""
    
    def test_basic_logging_format(self):
        """Test basic logging format"""
        error = AuthenticationError(
            message="Token expired",
            request_id="req_123"
        )
        
        serialized = serialize_error_for_logging(error)
        
        assert serialized["error_code"] == "AUTHENTICATION_FAILED"
        assert serialized["message"] == "Token expired"
        assert serialized["http_status_code"] == 401
        assert serialized["request_id"] == "req_123"
        assert serialized["error_type"] == "AuthenticationError"
    
    def test_logging_with_metadata(self):
        """Test logging format includes metadata"""
        error = ValidationError(
            message="Invalid field",
            field="email",
            request_id="req_123"
        )
        
        serialized = serialize_error_for_logging(error)
        
        assert "metadata" in serialized
        assert serialized["metadata"]["field"] == "email"
    
    def test_logging_without_traceback(self):
        """Test logging without traceback (default)"""
        error = InternalServerError(message="Error")
        
        serialized = serialize_error_for_logging(error, include_traceback=False)
        
        assert "traceback" not in serialized
    
    def test_logging_with_traceback(self):
        """Test logging with traceback (dev/staging)"""
        error = InternalServerError(message="Error")
        
        # Simulate exception context
        try:
            raise error
        except BaseException:
            serialized = serialize_error_for_logging(error, include_traceback=True)
        
        assert "traceback" in serialized
        assert isinstance(serialized["traceback"], str)


class TestSerializationRoundTrip:
    """Test serialization preserves error information"""
    
    def test_rest_serialization_preserves_info(self):
        """Test REST serialization preserves all error information"""
        error = ValidationError(
            message="Invalid input",
            field="name",
            request_id="req_123"
        )
        
        serialized = serialize_rest_error(error)
        
        # Should be able to extract all original information
        assert serialized["error"]["code"] == error.error_code
        assert serialized["error"]["message"] == error.message
        assert serialized["error"]["request_id"] == error.request_id
        assert serialized["error"]["metadata"]["field"] == "name"
    
    def test_websocket_serialization_preserves_info(self):
        """Test WebSocket serialization preserves error information"""
        error = ConflictError(
            message="Interview already started",
            request_id="req_123",
            metadata={"submission_id": 789}
        )
        
        serialized = serialize_websocket_error(error)
        
        assert serialized["event"] == "error"
        assert serialized["payload"]["code"] == error.error_code
        assert serialized["payload"]["message"] == error.message
        assert serialized["payload"]["metadata"]["submission_id"] == 789
