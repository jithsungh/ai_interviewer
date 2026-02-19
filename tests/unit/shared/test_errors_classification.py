"""
Unit Tests for Error Classification

Tests fatal vs recoverable error classification and log level determination.
"""

import pytest
from app.shared.errors.exceptions import (
    AuthenticationError,
    AuthorizationError,
    TenantIsolationViolation,
    ValidationError,
    NotFoundError,
    ConflictError,
    ProctoringViolation,
    DomainInvariantViolation,
    InternalServerError,
    InfrastructureError,
)
from app.shared.errors.classification import (
    is_fatal_error,
    get_log_level,
    should_send_to_client,
)


class TestFatalErrorClassification:
    """Test fatal vs recoverable error classification"""
    
    def test_authentication_error_is_fatal(self):
        """Test AuthenticationError is fatal (cannot continue without valid auth)"""
        error = AuthenticationError("Invalid token")
        
        assert is_fatal_error(error) is True
    
    def test_authorization_error_is_fatal(self):
        """Test AuthorizationError is fatal (cannot continue without permissions)"""
        error = AuthorizationError("Insufficient permissions")
        
        assert is_fatal_error(error) is True
    
    def test_tenant_isolation_violation_is_fatal(self):
        """Test TenantIsolationViolation is fatal (security violation)"""
        error = TenantIsolationViolation("Cross-tenant access")
        
        assert is_fatal_error(error) is True
    
    def test_domain_invariant_violation_is_fatal(self):
        """Test DomainInvariantViolation is fatal (system bug)"""
        error = DomainInvariantViolation(
            invariant="exchange_immutable",
            message="Exchange modified"
        )
        
        assert is_fatal_error(error) is True
    
    def test_validation_error_is_recoverable(self):
        """Test ValidationError is recoverable (user can retry)"""
        error = ValidationError("Invalid field")
        
        assert is_fatal_error(error) is False
    
    def test_not_found_error_is_recoverable(self):
        """Test NotFoundError is recoverable (user can try another resource)"""
        error = NotFoundError(resource_type="User", resource_id=42)
        
        assert is_fatal_error(error) is False
    
    def test_conflict_error_is_recoverable(self):
        """Test ConflictError is recoverable (user can resolve conflict)"""
        error = ConflictError("Already started")
        
        assert is_fatal_error(error) is False
    
    def test_proctoring_violation_is_recoverable(self):
        """Test ProctoringViolation is recoverable (advisory only)"""
        error = ProctoringViolation(
            event_type="face_not_visible",
            message="Face not detected",
            risk_score=0.7
        )
        
        assert is_fatal_error(error) is False
    
    def test_internal_server_error_is_recoverable(self):
        """Test InternalServerError is recoverable (5xx but not security issue)"""
        error = InternalServerError("Database timeout")
        
        assert is_fatal_error(error) is False


class TestLogLevelDetermination:
    """Test log level classification"""
    
    def test_domain_invariant_violation_critical(self):
        """Test DomainInvariantViolation logs at CRITICAL level"""
        error = DomainInvariantViolation(
            invariant="template_immutable",
            message="Template modified"
        )
        
        assert get_log_level(error) == "CRITICAL"
    
    def test_server_error_level(self):
        """Test 5xx errors log at ERROR level"""
        error = InternalServerError("Something went wrong")
        
        assert get_log_level(error) == "ERROR"
    
    def test_infrastructure_error_level(self):
        """Test InfrastructureError logs at ERROR level"""
        error = InfrastructureError(
            component="redis",
            message="Connection failed"
        )
        
        assert get_log_level(error) == "ERROR"
    
    def test_client_error_level(self):
        """Test 4xx errors log at WARN level"""
        errors = [
            AuthenticationError("Invalid token"),
            ValidationError("Invalid field"),
            NotFoundError(resource_type="User", resource_id=42),
            ConflictError("Already exists")
        ]
        
        for error in errors:
            assert get_log_level(error) == "WARN"
    
    def test_proctoring_violation_level(self):
        """Test ProctoringViolation logs at INFO level (advisory)"""
        error = ProctoringViolation(
            event_type="face_not_visible",
            message="Face not detected",
            risk_score=0.5
        )
        
        assert get_log_level(error) == "INFO"


class TestClientVisibilityShouldSendToClient:
    """Test error detail visibility for clients"""
    
    def test_4xx_always_sent_to_client(self):
        """Test 4xx errors always sent to client (in prod and dev)"""
        errors = [
            AuthenticationError("Invalid token"),
            ValidationError("Invalid field"),
            NotFoundError(resource_type="User", resource_id=42)
        ]
        
        for error in errors:
            assert should_send_to_client(error, is_production=True) is True
            assert should_send_to_client(error, is_production=False) is True
    
    def test_5xx_not_sent_in_production(self):
        """Test 5xx errors not sent to client in production (security)"""
        errors = [
            InternalServerError("Database failed"),
            InfrastructureError(component="redis", message="Connection lost")
        ]
        
        for error in errors:
            assert should_send_to_client(error, is_production=True) is False
    
    def test_5xx_sent_in_development(self):
        """Test 5xx errors sent to client in development (debugging)"""
        errors = [
            InternalServerError("Database failed"),
            InfrastructureError(component="redis", message="Connection lost")
        ]
        
        for error in errors:
            assert should_send_to_client(error, is_production=False) is True
    
    def test_proctoring_violation_always_sent(self):
        """Test ProctoringViolation always sent (2xx status, advisory)"""
        error = ProctoringViolation(
            event_type="multiple_faces",
            message="Multiple people detected",
            risk_score=0.9
        )
        
        assert should_send_to_client(error, is_production=True) is True
        assert should_send_to_client(error, is_production=False) is True


class TestClassificationEdgeCases:
    """Test classification edge cases"""
    
    def test_custom_http_status_classification(self):
        """Test classification works with custom HTTP status codes"""
        from app.shared.errors.exceptions import BaseError
        
        # Custom error with 418 status (teapot)
        error = BaseError(
            error_code="CUSTOM",
            message="Custom error",
            http_status_code=418
        )
        
        # Should be WARN (4xx range)
        assert get_log_level(error) == "WARN"
        assert is_fatal_error(error) is False
        assert should_send_to_client(error, is_production=True) is True
