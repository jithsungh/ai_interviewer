"""
Unit Tests for PasswordHasher

Tests password hashing, verification, and complexity validation.
"""

import pytest
from app.auth.domain.password_hasher import PasswordHasher
from app.shared.errors import ValidationError


class TestPasswordHasher:
    """Test suite for PasswordHasher"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.hasher = PasswordHasher(
            cost_factor=4,  # Lower cost for faster tests
            min_length=8,
            require_uppercase=True,
            require_lowercase=True,
            require_digit=True,
            require_special=True
        )
    
    # ========================================================================
    # HASH AND VERIFY TESTS
    # ========================================================================
    
    def test_hash_creates_different_hashes_for_same_password(self):
        """Test that hashing same password twice produces different hashes (salt)"""
        password = "TestPass123!"
        hash1 = self.hasher.hash(password)
        hash2 = self.hasher.hash(password)
        
        assert hash1 != hash2
        assert self.hasher.verify(password, hash1)
        assert self.hasher.verify(password, hash2)
    
    def test_verify_correct_password(self):
        """Test password verification with correct password"""
        password = "TestPass123!"
        password_hash = self.hasher.hash(password)
        
        assert self.hasher.verify(password, password_hash) is True
    
    def test_verify_incorrect_password(self):
        """Test password verification with incorrect password"""
        password = "TestPass123!"
        password_hash = self.hasher.hash(password)
        
        assert self.hasher.verify("WrongPass123!", password_hash) is False
    
    def test_verify_returns_false_for_invalid_hash(self):
        """Test verification returns False for malformed hash"""
        password = "TestPass123!"
        
        assert self.hasher.verify(password, "invalid_hash") is False
    
    # ========================================================================
    # COMPLEXITY VALIDATION TESTS
    # ========================================================================
    
    def test_validate_complexity_success(self):
        """Test password that meets all requirements"""
        # Should not raise exception
        self.hasher.validate_complexity("TestPass123!")
    
    def test_validate_complexity_too_short(self):
        """Test password too short"""
        with pytest.raises(ValidationError) as exc_info:
            self.hasher.validate_complexity("Test1!")
        
        assert "at least 8 characters" in str(exc_info.value)
    
    def test_validate_complexity_no_uppercase(self):
        """Test password without uppercase letter"""
        with pytest.raises(ValidationError) as exc_info:
            self.hasher.validate_complexity("testpass123!")
        
        assert "uppercase letter" in str(exc_info.value)
    
    def test_validate_complexity_no_lowercase(self):
        """Test password without lowercase letter"""
        with pytest.raises(ValidationError) as exc_info:
            self.hasher.validate_complexity("TESTPASS123!")
        
        assert "lowercase letter" in str(exc_info.value)
    
    def test_validate_complexity_no_digit(self):
        """Test password without digit"""
        with pytest.raises(ValidationError) as exc_info:
            self.hasher.validate_complexity("TestPassword!")
        
        assert "digit" in str(exc_info.value)
    
    def test_validate_complexity_no_special_char(self):
        """Test password without special character"""
        with pytest.raises(ValidationError) as exc_info:
            self.hasher.validate_complexity("TestPass123")
        
        assert "special character" in str(exc_info.value)
    
    def test_validate_complexity_multiple_failures(self):
        """Test password with multiple validation failures"""
        with pytest.raises(ValidationError) as exc_info:
            self.hasher.validate_complexity("test")
        
        error_message = str(exc_info.value)
        assert "8 characters" in error_message
        assert "uppercase" in error_message
        assert "digit" in error_message
        assert "special" in error_message
    
    # ========================================================================
    # CONFIGURATION TESTS
    # ========================================================================
    
    def test_custom_min_length(self):
        """Test custom minimum length requirement"""
        hasher = PasswordHasher(
            min_length=12,
            require_uppercase=False,
            require_lowercase=False,
            require_digit=False,
            require_special=False
        )
        
        with pytest.raises(ValidationError):
            hasher.validate_complexity("short")
        
        # Should pass with 12+ chars
        hasher.validate_complexity("longpassword")
    
    def test_optional_requirements(self):
        """Test with optional complexity requirements disabled"""
        hasher = PasswordHasher(
            min_length=8,
            require_uppercase=False,
            require_lowercase=False,
            require_digit=False,
            require_special=False
        )
        
        # Simple password should pass
        hasher.validate_complexity("simplepassword")
    
    # ========================================================================
    # INTEGRATION TESTS
    # ========================================================================
    
    def test_hash_validates_complexity_before_hashing(self):
        """Test that hash() validates complexity before hashing"""
        with pytest.raises(ValidationError):
            self.hasher.hash("weak")
    
    def test_full_workflow(self):
        """Test complete workflow: validate -> hash -> verify"""
        password = "SecurePass123!"
        
        # Validate
        self.hasher.validate_complexity(password)
        
        # Hash
        password_hash = self.hasher.hash(password)
        
        # Verify
        assert self.hasher.verify(password, password_hash)
        assert not self.hasher.verify("WrongPass123!", password_hash)


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
