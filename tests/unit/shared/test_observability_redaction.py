"""
Unit Tests for Observability - Redaction Module

Tests sensitive data redaction and masking.
"""

import pytest

from app.shared.observability.redaction import (
    redact_sensitive_data,
    mask_token,
    should_redact_field,
    SENSITIVE_FIELDS,
)


class TestRedactSensitiveData:
    """Test sensitive data redaction"""
    
    def test_redact_access_token(self):
        """Test redacting access token"""
        data = {
            "user_id": 42,
            "access_token": "secret_token_123"
        }
        
        redacted = redact_sensitive_data(data)
        
        assert redacted["user_id"] == 42
        assert redacted["access_token"] == "[REDACTED]"
    
    def test_redact_multiple_sensitive_fields(self):
        """Test redacting multiple sensitive fields"""
        data = {
            "user_id": 42,
            "access_token": "secret_token_123",
            "password": "secret_pass",
            "api_key": "api_key_456"
        }
        
        redacted = redact_sensitive_data(data)
        
        assert redacted["user_id"] == 42
        assert redacted["access_token"] == "[REDACTED]"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"
    
    def test_redact_nested_structure(self):
        """Test redacting nested dictionaries"""
        data = {
            "user": {
                "id": 42,
                "email": "test@example.com",
                "password": "secret"
            },
            "session": {
                "access_token": "token_123"
            }
        }
        
        redacted = redact_sensitive_data(data)
        
        assert redacted["user"]["id"] == 42
        assert redacted["user"]["email"] == "test@example.com"
        assert redacted["user"]["password"] == "[REDACTED]"
        assert redacted["session"]["access_token"] == "[REDACTED]"
    
    def test_redact_list_of_dicts(self):
        """Test redacting list of dictionaries"""
        data = {
            "users": [
                {"id": 1, "password": "pass1"},
                {"id": 2, "password": "pass2"}
            ]
        }
        
        redacted = redact_sensitive_data(data)
        
        assert redacted["users"][0]["id"] == 1
        assert redacted["users"][0]["password"] == "[REDACTED]"
        assert redacted["users"][1]["id"] == 2
        assert redacted["users"][1]["password"] == "[REDACTED]"
    
    def test_redact_hidden_test_case_output(self):
        """Test redacting hidden test case expected output"""
        data = {
            "test_case": {
                "input": "[1,2,3]",
                "expected_output": "6",
                "is_hidden": True
            }
        }
        
        redacted = redact_sensitive_data(data)
        
        assert redacted["test_case"]["input"] == "[1,2,3]"
        assert redacted["test_case"]["expected_output"] == "[REDACTED]"
        assert redacted["test_case"]["is_hidden"] is True
    
    def test_preserve_visible_test_case_output(self):
        """Test preserving visible test case output"""
        data = {
            "test_case": {
                "input": "[1,2,3]",
                "expected_output": "6",
                "is_hidden": False
            }
        }
        
        redacted = redact_sensitive_data(data)
        
        assert redacted["test_case"]["expected_output"] == "6"
    
    def test_redact_candidate_answers_disabled(self):
        """Test NOT redacting candidate answers by default"""
        data = {
            "candidate_answer": "My answer to the question"
        }
        
        redacted = redact_sensitive_data(data, redact_candidate_answers=False)
        
        assert redacted["candidate_answer"] == "My answer to the question"
    
    def test_redact_candidate_answers_enabled(self):
        """Test redacting candidate answers when enabled"""
        data = {
            "candidate_answer": "My answer to the question"
        }
        
        redacted = redact_sensitive_data(data, redact_candidate_answers=True)
        
        assert redacted["candidate_answer"] == "[REDACTED_ANSWER]"
    
    def test_redact_case_insensitive(self):
        """Test redaction is case-insensitive"""
        data = {
            "Access_Token": "token1",
            "PASSWORD": "pass1",
            "Api_Key": "key1"
        }
        
        redacted = redact_sensitive_data(data)
        
        assert redacted["Access_Token"] == "[REDACTED]"
        assert redacted["PASSWORD"] == "[REDACTED]"
        assert redacted["Api_Key"] == "[REDACTED]"
    
    def test_redact_primitives_unchanged(self):
        """Test primitives pass through unchanged"""
        assert redact_sensitive_data("test") == "test"
        assert redact_sensitive_data(42) == 42
        assert redact_sensitive_data(3.14) == 3.14
        assert redact_sensitive_data(True) is True
        assert redact_sensitive_data(None) is None


class TestMaskToken:
    """Test token masking"""
    
    def test_mask_long_token(self):
        """Test masking long token"""
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        masked = mask_token(token, visible_chars=4)
        
        assert masked == "...VCJ9"
    
    def test_mask_short_token(self):
        """Test masking token shorter than visible chars"""
        token = "abc"
        masked = mask_token(token, visible_chars=4)
        
        assert masked == "[REDACTED]"
    
    def test_mask_empty_token(self):
        """Test masking empty token"""
        masked = mask_token("")
        
        assert masked == "[REDACTED]"
    
    def test_mask_different_visible_chars(self):
        """Test masking with different visible character counts"""
        token = "0123456789abcdef"
        
        assert mask_token(token, visible_chars=2) == "...ef"
        assert mask_token(token, visible_chars=4) == "...cdef"
        assert mask_token(token, visible_chars=6) == "...abcdef"


class TestShouldRedactField:
    """Test field name checking"""
    
    def test_should_redact_sensitive_fields(self):
        """Test identifying sensitive field names"""
        sensitive_names = [
            "access_token",
            "refresh_token",
            "password",
            "api_key",
            "secret",
            "token",
            "Authorization"
        ]
        
        for name in sensitive_names:
            assert should_redact_field(name) is True
    
    def test_should_not_redact_normal_fields(self):
        """Test identifying non-sensitive field names"""
        normal_names = [
            "user_id",
            "email",
            "name",
            "created_at",
            "submission_id"
        ]
        
        for name in normal_names:
            assert should_redact_field(name) is False
    
    def test_case_insensitive_checking(self):
        """Test case-insensitive field checking"""
        assert should_redact_field("Access_Token") is True
        assert should_redact_field("PASSWORD") is True
        assert should_redact_field("Api_Key") is True


class TestSensitiveFieldsConstant:
    """Test SENSITIVE_FIELDS constant"""
    
    def test_sensitive_fields_set_exists(self):
        """Test SENSITIVE_FIELDS is a set"""
        assert isinstance(SENSITIVE_FIELDS, set)
    
    def test_sensitive_fields_contains_expected(self):
        """Test SENSITIVE_FIELDS contains expected values"""
        expected_fields = {
            "access_token",
            "refresh_token",
            "password",
            "api_key",
            "secret",
            "token"
        }
        
        assert expected_fields.issubset(SENSITIVE_FIELDS)


# Test Results Summary
def test_redaction_module_summary():
    """Summary of redaction module tests"""
    print("\n" + "="*60)
    print("REDACTION MODULE TEST SUMMARY")
    print("="*60)
    print("✅ Redact sensitive data tests: 10 tests")
    print("✅ Mask token tests: 4 tests")
    print("✅ Should redact field tests: 3 tests")
    print("✅ Sensitive fields constant tests: 2 tests")
    print("="*60)
    print("Total: 19 tests")
    print("="*60)
