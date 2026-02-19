"""
Unit Tests for Error Exceptions

Tests all exception types, their initialization, and properties.
"""

import pytest
from app.shared.errors.exceptions import (
    BaseError,
    ApplicationError,
    AuthenticationError,
    AuthorizationError,
    TenantIsolationViolation,
    NotFoundError,
    ConflictError,
    ValidationError,
    RateLimitExceeded,
    InterviewNotActiveError,
    InterviewWindowClosedError,
    ConsentNotCapturedError,
    ExchangeImmutabilityViolation,
    TemplateImmutabilityViolation,
    DomainInvariantViolation,
    ProctoringViolation,
    AIProviderError,
    AIProviderTimeoutError,
    SandboxExecutionError,
    SandboxTimeoutError,
    InfrastructureError,
    DatabaseError,
    CacheError,
    ConfigurationError,
    InternalServerError,
)


class TestBaseError:
    """Test BaseError foundation class"""
    
    def test_base_error_structure(self):
        """Test BaseError includes all required fields"""
        error = BaseError(
            error_code="TEST_ERROR",
            message="Test message",
            request_id="req_123",
            metadata={"key": "value"},
            http_status_code=500
        )
        
        assert error.error_code == "TEST_ERROR"
        assert error.message == "Test message"
        assert error.request_id == "req_123"
        assert error.metadata == {"key": "value"}
        assert error.http_status_code == 500
    
    def test_metadata_initialized_if_none(self):
        """Test metadata is initialized to empty dict if None"""
        error = BaseError(
            error_code="TEST",
            message="Message"
        )
        
        assert error.metadata == {}
    
    def test_backward_compat_properties(self):
        """Test backward compatibility properties"""
        error = BaseError(
            error_code="TEST",
            message="Message",
            http_status_code=404,
            metadata={"field": "value"}
        )
        
        assert error.status_code == 404  # Alias
        assert error.details == {"field": "value"}  # Alias
    
    def test_is_exception(self):
        """Test BaseError is an Exception"""
        error = BaseError(
            error_code="TEST",
            message="Test"
        )
        
        assert isinstance(error, Exception)
        assert str(error) == "Test"


class TestApplicationError:
    """Test ApplicationError backward compatibility"""
    
    def test_old_style_initialization(self):
        """Test ApplicationError with old-style parameters (status_code, details)"""
        error = ApplicationError(
            message="Test error",
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource": "user"}
        )
        
        assert error.message == "Test error"
        assert error.http_status_code == 404
        assert error.error_code == "NOT_FOUND"
        assert error.metadata == {"resource": "user"}
    
    def test_new_style_initialization(self):
        """Test ApplicationError with new-style parameters (http_status_code, metadata)"""
        error = ApplicationError(
            message="Test error",
            http_status_code=500,
            error_code="SERVER_ERROR",
            metadata={"component": "database"}
        )
        
        assert error.message == "Test error"
        assert error.http_status_code == 500
        assert error.error_code == "SERVER_ERROR"
        assert error.metadata == {"component": "database"}
    
    def test_default_error_code(self):
        """Test error_code defaults to class name"""
        error = ApplicationError(message="Test")
        
        assert error.error_code == "ApplicationError"


class TestClientErrors:
    """Test client error types (4xx)"""
    
    def test_authentication_error(self):
        """Test AuthenticationError (401)"""
        error = AuthenticationError(
            message="Token expired",
            request_id="req_123"
        )
        
        assert error.error_code == "AUTHENTICATION_FAILED"
        assert error.message == "Token expired"
        assert error.http_status_code == 401
        assert error.request_id == "req_123"
    
    def test_authorization_error(self):
        """Test AuthorizationError (403)"""
        error = AuthorizationError(
            message="Admin only",
            request_id="req_123"
        )
        
        assert error.error_code == "AUTHORIZATION_FAILED"
        assert error.message == "Admin only"
        assert error.http_status_code == 403
    
    def test_tenant_isolation_violation(self):
        """Test TenantIsolationViolation (403)"""
        error = TenantIsolationViolation(
            message="Cross-tenant access",
            request_id="req_123"
        )
        
        assert error.error_code == "TENANT_VIOLATION"
        assert error.http_status_code == 403
    
    def test_not_found_error(self):
        """Test NotFoundError (404)"""
        error = NotFoundError(
            resource_type="User",
            resource_id=42,
            request_id="req_123"
        )
        
        assert error.error_code == "NOT_FOUND"
        assert "User" in error.message
        assert "42" in error.message
        assert error.http_status_code == 404
        assert error.metadata["resource_type"] == "User"
        assert error.metadata["resource_id"] == 42
    
    def test_not_found_error_backward_compat(self):
        """Test NotFoundError with old parameter names"""
        error = NotFoundError(
            resource="Submission",
            identifier=789
        )
        
        assert "Submission" in error.message
        assert "789" in error.message
    
    def test_conflict_error(self):
        """Test ConflictError (409)"""
        error = ConflictError(
            message="Interview already started",
            request_id="req_123"
        )
        
        assert error.error_code == "CONFLICT"
        assert error.http_status_code == 409
    
    def test_validation_error(self):
        """Test ValidationError (422)"""
        error = ValidationError(
            message="Invalid email",
            field="email",
            request_id="req_123"
        )
        
        assert error.error_code == "VALIDATION_ERROR"
        assert error.http_status_code == 422
        assert error.metadata["field"] == "email"
    
    def test_rate_limit_exceeded(self):
        """Test RateLimitExceeded (429)"""
        error = RateLimitExceeded(
            limit=100,
            window_seconds=60,
            retry_after_seconds=30,
            request_id="req_123"
        )
        
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.http_status_code == 429
        assert error.metadata["limit"] == 100
        assert error.metadata["window_seconds"] == 60
        assert error.metadata["retry_after_seconds"] == 30


class TestBusinessLogicErrors:
    """Test business logic error types"""
    
    def test_interview_not_active_error(self):
        """Test InterviewNotActiveError"""
        error = InterviewNotActiveError(
            submission_id=123,
            request_id="req_123"
        )
        
        assert error.error_code == "INTERVIEW_NOT_ACTIVE"
        assert "123" in error.message
        assert error.http_status_code == 400
        assert error.metadata["submission_id"] == 123
    
    def test_interview_window_closed_error(self):
        """Test InterviewWindowClosedError"""
        error = InterviewWindowClosedError(
            window_id=456,
            request_id="req_123"
        )
        
        assert error.error_code == "INTERVIEW_WINDOW_CLOSED"
        assert "456" in error.message
        assert error.http_status_code == 400
    
    def test_consent_not_captured_error(self):
        """Test ConsentNotCapturedError"""
        error = ConsentNotCapturedError(request_id="req_123")
        
        assert error.error_code == "CONSENT_REQUIRED"
        assert "consent" in error.message.lower()
        assert error.http_status_code == 400


class TestDomainErrors:
    """Test domain error types"""
    
    def test_exchange_immutability_violation(self):
        """Test ExchangeImmutabilityViolation"""
        error = ExchangeImmutabilityViolation(
            exchange_id=789,
            request_id="req_123"
        )
        
        assert error.error_code == "EXCHANGE_IMMUTABLE"
        assert "789" in error.message
        assert "immutable" in error.message.lower()
        assert error.http_status_code == 400
    
    def test_template_immutability_violation(self):
        """Test TemplateImmutabilityViolation"""
        error = TemplateImmutabilityViolation(
            template_id=101,
            request_id="req_123"
        )
        
        assert error.error_code == "TEMPLATE_IMMUTABLE"
        assert "101" in error.message
        assert error.http_status_code == 400
    
    def test_domain_invariant_violation(self):
        """Test DomainInvariantViolation"""
        error = DomainInvariantViolation(
            invariant="exchange_immutable",
            message="Exchange was modified",
            request_id="req_123",
            metadata={"exchange_id": 42}
        )
        
        assert error.error_code == "DOMAIN_INVARIANT_VIOLATION"
        assert "exchange_immutable" in error.message
        assert "violated" in error.message.lower()
        assert error.http_status_code == 500  # System bug, not user error
        assert error.metadata["invariant"] == "exchange_immutable"
        assert error.metadata["exchange_id"] == 42
    
    def test_proctoring_violation(self):
        """Test ProctoringViolation (advisory, not punitive)"""
        error = ProctoringViolation(
            event_type="face_not_visible",
            message="Face not detected in frame",
            risk_score=0.8,
            request_id="req_123"
        )
        
        assert error.error_code == "PROCTORING_VIOLATION"
        assert error.http_status_code == 200  # Not an error, advisory event
        assert error.metadata["event_type"] == "face_not_visible"
        assert error.metadata["risk_score"] == 0.8


class TestExternalServiceErrors:
    """Test external service error types (5xx)"""
    
    def test_ai_provider_error(self):
        """Test AIProviderError"""
        error = AIProviderError(
            provider="openai",
            message="Rate limit exceeded",
            request_id="req_123"
        )
        
        assert error.error_code == "AI_PROVIDER_ERROR"
        assert "openai" in error.message
        assert error.http_status_code == 502
        assert error.metadata["provider"] == "openai"
    
    def test_ai_provider_timeout_error(self):
        """Test AIProviderTimeoutError"""
        error = AIProviderTimeoutError(
            provider="claude",
            timeout_s=30,
            request_id="req_123"
        )
        
        assert error.error_code == "AI_TIMEOUT"
        assert "claude" in error.message
        assert "30" in error.message
        assert error.http_status_code == 504
        assert error.metadata["timeout_seconds"] == 30
    
    def test_sandbox_execution_error(self):
        """Test SandboxExecutionError"""
        error = SandboxExecutionError(
            message="Runtime error in code",
            request_id="req_123"
        )
        
        assert error.error_code == "SANDBOX_EXECUTION_ERROR"
        assert error.http_status_code == 500
    
    def test_sandbox_timeout_error(self):
        """Test SandboxTimeoutError"""
        error = SandboxTimeoutError(
            timeout_s=10,
            request_id="req_123"
        )
        
        assert error.error_code == "EXECUTION_TIMEOUT"
        assert "10" in error.message
        assert error.http_status_code == 408


class TestSystemErrors:
    """Test system error types (5xx)"""
    
    def test_infrastructure_error(self):
        """Test InfrastructureError"""
        error = InfrastructureError(
            component="redis",
            message="Connection timeout",
            request_id="req_123"
        )
        
        assert error.error_code == "INFRASTRUCTURE_ERROR"
        assert "redis" in error.message
        assert error.http_status_code == 500
        assert error.metadata["component"] == "redis"
    
    def test_database_error(self):
        """Test DatabaseError"""
        error = DatabaseError(
            message="Connection failed",
            request_id="req_123"
        )
        
        assert error.error_code == "DATABASE_ERROR"
        assert error.http_status_code == 500
    
    def test_cache_error(self):
        """Test CacheError"""
        error = CacheError(
            message="Redis unavailable",
            request_id="req_123"
        )
        
        assert error.error_code == "CACHE_ERROR"
        assert error.http_status_code == 500
    
    def test_configuration_error(self):
        """Test ConfigurationError"""
        error = ConfigurationError(
            message="Missing API key",
            request_id="req_123"
        )
        
        assert error.error_code == "CONFIG_ERROR"
        assert error.http_status_code == 500
    
    def test_internal_server_error(self):
        """Test InternalServerError"""
        error = InternalServerError(
            message="Unexpected error",
            request_id="req_123"
        )
        
        assert error.error_code == "INTERNAL_SERVER_ERROR"
        assert error.http_status_code == 500
