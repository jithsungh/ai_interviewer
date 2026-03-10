"""
Unit Tests for WebSocket Authentication

Tests WebSocket authentication and connection ID generation.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.shared.auth_context.models import IdentityContext, UserType, AdminRole
from app.shared.auth_context.websocket import authenticate_websocket, generate_connection_id
from app.shared.errors import AuthenticationError


class TestGenerateConnectionId:
    """Test generate_connection_id()"""
    
    def test_generates_valid_uuid(self):
        """Test generates valid UUID format"""
        connection_id = generate_connection_id()
        
        # Should be a string
        assert isinstance(connection_id, str)
        
        # Should start with "conn_"
        assert connection_id.startswith("conn_")
        
        # Extract UUID part (after "conn_")
        uuid_part = connection_id[5:]  # Skip "conn_"
        
        # Should have UUID format (8-4-4-4-12)
        parts = uuid_part.split('-')
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12
    
    def test_generates_unique_ids(self):
        """Test generates unique IDs"""
        id1 = generate_connection_id()
        id2 = generate_connection_id()
        
        assert id1 != id2
    
    def test_generates_lowercase_hex(self):
        """Test generates lowercase hex characters"""
        connection_id = generate_connection_id()
        
        # Extract UUID part (after "conn_")
        uuid_part = connection_id[5:]
        
        # Remove hyphens and check all chars are lowercase hex
        hex_chars = uuid_part.replace('-', '')
        assert all(c in '0123456789abcdef-' for c in hex_chars)


class TestAuthenticateWebsocket:
    """Test authenticate_websocket()"""
    
    @pytest.mark.asyncio
    async def test_valid_token_returns_identity(self):
        """Test valid token returns identity context"""
        import time
        mock_websocket = Mock()
        
        now = int(time.time())
        async def mock_validator(token: str):
            return {
                "sub": 123,
                "user_type": "candidate",
                "candidate_id": 123,
                "token_version": 1,
                "iat": now,
                "exp": now + 3600  # 1 hour from now
            }
        
        identity = await authenticate_websocket(mock_websocket, "valid_token", mock_validator)
        
        assert identity.user_id == 123
        assert identity.user_type == UserType.CANDIDATE
        assert identity.organization_id is None
        assert identity.admin_role is None
    
    @pytest.mark.asyncio
    async def test_admin_token_returns_admin_identity(self):
        """Test admin token returns admin identity"""
        import time
        mock_websocket = Mock()
        
        now = int(time.time())
        async def mock_validator(token: str):
            return {
                "sub": 42,
                "user_type": "admin",
                "organization_id": 1,
                "admin_role": "admin",
                "token_version": 1,
                "iat": now,
                "exp": now + 3600
            }
        
        identity = await authenticate_websocket(mock_websocket, "admin_token", mock_validator)
        
        assert identity.user_id == 42
        assert identity.user_type == UserType.ADMIN
        assert identity.organization_id == 1
        assert identity.admin_role == AdminRole.ADMIN
    
    @pytest.mark.asyncio
    async def test_invalid_token_raises_authentication_error(self):
        """Test invalid token raises AuthenticationError"""
        mock_websocket = Mock()
        
        async def mock_validator(token: str):
            raise AuthenticationError("Invalid token signature")
        
        with pytest.raises(AuthenticationError, match="Invalid token signature"):
            await authenticate_websocket(mock_websocket, "invalid_token", mock_validator)
    
    @pytest.mark.asyncio
    async def test_missing_claims_raises_validation_error(self):
        """Test missing required claims raises ValidationError"""
        mock_websocket = Mock()
        
        async def mock_validator(token: str):
            return {
                "sub": 123,
                # Missing user_type
                "token_version": 1,
                "iat": 1700000000,
                "exp": 1700003600
            }
        
        with pytest.raises(Exception):  # ValidationError from builder
            await authenticate_websocket(mock_websocket, "token_with_missing_claims", mock_validator)
    
    @pytest.mark.asyncio
    async def test_malformed_claims_raises_validation_error(self):
        """Test malformed claims raises ValidationError"""
        mock_websocket = Mock()
        
        async def mock_validator(token: str):
            return {
                "sub": "not_an_int",  # Should be int
                "user_type": "candidate",
                "token_version": 1,
                "iat": 1700000000,
                "exp": 1700003600
            }
        
        with pytest.raises(Exception):  # ValidationError from builder
            await authenticate_websocket(mock_websocket, "token_with_bad_claims", mock_validator)
    
    @pytest.mark.asyncio
    async def test_empty_token_raises_error(self):
        """Test empty token raises error"""
        mock_websocket = Mock()
        
        async def mock_validator(token: str):
            if not token:
                raise AuthenticationError("Token is required")
            return {}
        
        with pytest.raises(AuthenticationError):
            await authenticate_websocket(mock_websocket, "", mock_validator)
    
    @pytest.mark.asyncio
    async def test_superadmin_token_returns_superadmin_identity(self):
        """Test superadmin token returns superadmin identity"""
        import time
        mock_websocket = Mock()
        
        now = int(time.time())
        async def mock_validator(token: str):
            return {
                "sub": 1,
                "user_type": "admin",
                "organization_id": 1,
                "admin_role": "superadmin",
                "token_version": 1,
                "iat": now,
                "exp": now + 3600
            }
        
        identity = await authenticate_websocket(mock_websocket, "superadmin_token", mock_validator)
        
        assert identity.user_id == 1
        assert identity.user_type == UserType.ADMIN
        assert identity.admin_role == AdminRole.SUPERADMIN
        assert identity.is_superadmin()
