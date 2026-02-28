"""
Unit Tests for JWTService

Tests JWT access token generation, refresh token generation, and token validation.
"""

import pytest
import jwt
import time
from datetime import datetime, timedelta, timezone

from app.auth.domain.jwt_service import JWTService
from app.shared.errors import AuthenticationError


# Test RSA key pair (generated for testing only)
TEST_PRIVATE_KEY = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAmqw5by3iNHHjl8B3SIGQG/jiSErDdHqVsH3Wy2Oops2KWrEt
CamYWffxBdFrJPK88alEcnS2K7CHTo+VjmQyugUOJ/mHgOZI89ZDgkjr19KA+2k8
nu5/8Jch2xm7JwvN/2IDKnihfjErLHoeB5zZyUAFA2mMhzqM6lP6FMHq7aSKm4r9
duSUcs3MCzmr9T8lnaFOYYolJXoAEMzH8iySyz51tRbF/RfiOQvTW9qq9tyGPUgF
/1JqR+rHeaCdFXG2gEW8D+ZebjUwJl7uRSN2SUk3AJcR8jt2hQMYBXlXFAtvHH0z
NT9VJrZfwbgZSn2ibzG29j3E5Rk+VAy7bOhUfwIDAQABAoIBADqrV0HX2rTf+l+G
jvh+xMYHevXG/irBkOQYZ5BQphlXX8KU8Ct5HCQMS21UiVrDhG36Mc9ke/FIjZp8
FlOjqCYtYrhBC2gWcdekD4ls1aDQ5UH4Ihl7CCaffSUZtobSEHptmBvVFBTE28aM
L7XdhjKzSPOJZteomukLn5GeGNm4+CErY7sHv9TIiGjyeEf+x5piooXa3TMoGh7M
aS9rG/9HnM1P0z2rG2N0P1F7I54Qlc23TucmlUdQbnFwwhrxXUkMICPZjtFFCZH2
w9vw2mAsSDCPpgt3OYp+B53DsEk2kTNQZ/tL0J8hYVhUGAuaF2u1mCllxiQPluzR
OeBfIskCgYEAzMEmgoSJAo2uxaWPR62o/6m6TDcWHUmPll/h9pqzrxfsKnRbiPWz
I/lO0A7f3Fkz/NWQcWFG6SqAE65ZsTmc+26sdYY5gn9XpJE2FWO0BdRDG5iBV4y6
PeOsIked8a2T6uUwaZQQFGOspJJFjsDcCDG/E/iH14IZJn8L79p6kD0CgYEAwWJH
16KqjBy/Z8KzH0R0jLx3IYyhlBvAGF4/xEu4FaHBx7db3LdVKV0konCTUhbf/kZk
MMsYEuqMGfu082Ef35zF585V7RdpE1pARvMUMe1J0tEoabMWdf/Zf042XmtO9/pc
JjkFhqfPU2zEmkv8TCbX5ie833nIUZ7lOvsT52sCgYBLA3BiXL/9SX8ANhl5/ytt
DveLuJrHfA2438PfHuo5eaAyJZLraGiLA2lWXDyzc5LSTEOw5hyei82EaFm/zgWv
L+rK27PyFUk8p16TE4X+pLc5QvQP6STKS8Dihi5dPmR0qCbGZ1JExgeX+2a0V//E
mMUSQfkygR1Jtz3eT8KbWQKBgQCONjtE7Z/j5+QuZvUY4luff51QM75DT+EFSpI0
Rca7SbhaqZHJj5z2DUQ6nPUJ4j6ZHKTjaQdsKcYb+YnJjTxGUmELpiZ0c8nW7IDm
bC4GxUyL1zqT+Jpk7mDBCQBckSeCnz+S8E4LB28lF5DBM233hn0xCToRUdqpg2Np
62hovwKBgQC5UcZeiRRPXuhL5nRzWRfYK3fTsQX1saO3ySndysopyCkQQWy3c0qf
p2z+1ze0Gh+ZRKPndo0NkVclQTJADk996bvzXUN8CVSLkQ6GsEKH8RaDTPnQ9eBP
0Icu+HXZfNr1vUR6SlisfiwoOJQNWcPpsRiM8EwI9Dux87/aYT6Q0Q==
-----END RSA PRIVATE KEY-----"""

TEST_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAmqw5by3iNHHjl8B3SIGQ
G/jiSErDdHqVsH3Wy2Oops2KWrEtCamYWffxBdFrJPK88alEcnS2K7CHTo+VjmQy
ugUOJ/mHgOZI89ZDgkjr19KA+2k8nu5/8Jch2xm7JwvN/2IDKnihfjErLHoeB5zZ
yUAFA2mMhzqM6lP6FMHq7aSKm4r9duSUcs3MCzmr9T8lnaFOYYolJXoAEMzH8iyS
yz51tRbF/RfiOQvTW9qq9tyGPUgF/1JqR+rHeaCdFXG2gEW8D+ZebjUwJl7uRSN2
SUk3AJcR8jt2hQMYBXlXFAtvHH0zNT9VJrZfwbgZSn2ibzG29j3E5Rk+VAy7bOhU
fwIDAQAB
-----END PUBLIC KEY-----"""


class TestJWTService:
    """Test suite for JWTService"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.jwt_service = JWTService(
            private_key=TEST_PRIVATE_KEY,
            public_key=TEST_PUBLIC_KEY,
            algorithm="RS256",
            access_token_ttl_minutes=15,
            refresh_token_ttl_days=30
        )
    
    # ========================================================================
    # ACCESS TOKEN GENERATION TESTS
    # ========================================================================
    
    def test_generate_admin_access_token(self):
        """Test generating access token for admin"""
        token = self.jwt_service.generate_access_token(
            user_id=1,
            user_type='admin',
            token_version=1,
            admin_id=10,
            organization_id=5,
            admin_role='admin'
        )
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Decode and verify claims
        claims = jwt.decode(token, TEST_PUBLIC_KEY, algorithms=['RS256'])
        assert claims['sub'] == 1
        assert claims['type'] == 'admin'
        assert claims['admin_id'] == 10
        assert claims['organization_id'] == 5
        assert claims['role'] == 'admin'
        assert 'jti' in claims
        assert 'iat' in claims
        assert 'exp' in claims
    
    def test_generate_candidate_access_token(self):
        """Test generating access token for candidate"""
        token = self.jwt_service.generate_access_token(
            user_id=2,
            user_type='candidate',
            token_version=1,
            candidate_id=20
        )
        
        assert isinstance(token, str)
        
        claims = jwt.decode(token, TEST_PUBLIC_KEY, algorithms=['RS256'])
        assert claims['sub'] == 2
        assert claims['type'] == 'candidate'
        assert claims['candidate_id'] == 20
        assert 'admin_id' not in claims
        assert 'organization_id' not in claims
    
    def test_generate_admin_token_requires_admin_fields(self):
        """Test that admin tokens require admin_id, organization_id, admin_role"""
        with pytest.raises(ValueError):
            self.jwt_service.generate_access_token(
                user_id=1,
                user_type='admin',
                token_version=1
                # Missing admin_id, organization_id, admin_role
            )
    
    def test_generate_candidate_token_requires_candidate_id(self):
        """Test that candidate tokens require candidate_id"""
        with pytest.raises(ValueError):
            self.jwt_service.generate_access_token(
                user_id=2,
                user_type='candidate',
                token_version=1
                # Missing candidate_id
            )
    
    def test_access_token_expiration(self):
        """Test that access token has correct expiration"""
        token = self.jwt_service.generate_access_token(
            user_id=1,
            user_type='candidate',
            token_version=1,
            candidate_id=20
        )
        
        claims = jwt.decode(token, TEST_PUBLIC_KEY, algorithms=['RS256'])
        
        # Check expiration is ~15 minutes from now
        exp_time = datetime.fromtimestamp(claims['exp'], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        time_diff = (exp_time - now).total_seconds()
        
        # Should be approximately 15 minutes (900 seconds) ± 5 seconds
        assert 895 <= time_diff <= 905
    
    # ========================================================================
    # TOKEN VERIFICATION TESTS
    # ========================================================================
    
    def test_verify_valid_token(self):
        """Test verifying a valid access token"""
        token = self.jwt_service.generate_access_token(
            user_id=1,
            user_type='admin',
            token_version=1,
            admin_id=10,
            organization_id=5,
            admin_role='admin'
        )
        
        claims = self.jwt_service.verify_access_token(token)
        
        assert claims['sub'] == 1
        assert claims['type'] == 'admin'
        assert claims['admin_id'] == 10
    
    def test_verify_expired_token(self):
        """Test verifying an expired token"""
        # Manually craft an already-expired token using PyJWT directly
        # to avoid timing issues with zero-TTL generation
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        past_iat = now - timedelta(hours=1)
        past_exp = now - timedelta(minutes=30)

        payload = {
            "sub": 1,
            "type": "candidate",
            "token_version": 1,
            "candidate_id": 20,
            "iat": int(past_iat.timestamp()),
            "exp": int(past_exp.timestamp()),
            "jti": "test-expired-jti",
        }
        expired_token = jwt.encode(payload, TEST_PRIVATE_KEY, algorithm="RS256")

        with pytest.raises(AuthenticationError) as exc_info:
            self.jwt_service.verify_access_token(expired_token)

        assert "expired" in str(exc_info.value).lower()
    
    def test_verify_tampered_token(self):
        """Test verifying a token with tampered claims"""
        token = self.jwt_service.generate_access_token(
            user_id=1,
            user_type='candidate',
            token_version=1,
            candidate_id=20
        )
        
        # Tamper with token by changing a character
        tampered_token = token[:-5] + "XXXXX"
        
        with pytest.raises(AuthenticationError):
            self.jwt_service.verify_access_token(tampered_token)
    
    def test_verify_malformed_token(self):
        """Test verifying a malformed token"""
        with pytest.raises(AuthenticationError):
            self.jwt_service.verify_access_token("not.a.valid.token")
    
    # ========================================================================
    # REFRESH TOKEN TESTS
    # ========================================================================
    
    def test_generate_refresh_token(self):
        """Test generating refresh token"""
        token = self.jwt_service.generate_refresh_token()
        
        assert isinstance(token, str)
        assert len(token) == 128  # 64 bytes hex-encoded = 128 chars
    
    def test_refresh_tokens_are_unique(self):
        """Test that each refresh token is unique"""
        token1 = self.jwt_service.generate_refresh_token()
        token2 = self.jwt_service.generate_refresh_token()
        
        assert token1 != token2
    
    def test_hash_refresh_token(self):
        """Test hashing refresh token"""
        token = self.jwt_service.generate_refresh_token()
        hash1 = self.jwt_service.hash_refresh_token(token)
        hash2 = self.jwt_service.hash_refresh_token(token)
        
        # Same token should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex = 64 chars
    
    def test_different_tokens_produce_different_hashes(self):
        """Test that different tokens produce different hashes"""
        token1 = self.jwt_service.generate_refresh_token()
        token2 = self.jwt_service.generate_refresh_token()
        
        hash1 = self.jwt_service.hash_refresh_token(token1)
        hash2 = self.jwt_service.hash_refresh_token(token2)
        
        assert hash1 != hash2
    
    # ========================================================================
    # EXPIRY CALCULATION TESTS
    # ========================================================================
    
    def test_get_refresh_token_expiry(self):
        """Test refresh token expiry calculation"""
        expiry = self.jwt_service.get_refresh_token_expiry()
        
        now = datetime.now(timezone.utc)
        expected_expiry = now + timedelta(days=30)
        
        # Should be approximately 30 days from now
        time_diff = abs((expiry - expected_expiry).total_seconds())
        assert time_diff < 5  # Within 5 seconds


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
