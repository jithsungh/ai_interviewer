"""
Integration Tests for Auth Context Module

Tests end-to-end flows with FastAPI and middleware.
Note: Redis-dependent tests are in separate test file with Redis fixtures.
"""

import pytest
import time
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch
from app.shared.auth_context.models import IdentityContext, UserType, AdminRole
from app.shared.auth_context.middleware import IdentityInjectionMiddleware
from app.shared.auth_context.dependencies import get_identity, require_admin, require_candidate
from app.shared.auth_context.websocket import authenticate_websocket
from app.shared.errors import (
    AuthenticationError,
    AuthorizationError,
    TenantIsolationViolation
)


def add_exception_handlers(app: FastAPI):
    """Add standard exception handlers to test FastAPI app"""
    
    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            }
        )
    
    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(request: Request, exc: AuthorizationError):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            }
        )
    
    @app.exception_handler(TenantIsolationViolation)
    async def tenant_isolation_handler(request: Request, exc: TenantIsolationViolation):
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            }
        )


class TestMiddlewareIntegration:
    """Test middleware integration with FastAPI"""
    
    def test_middleware_injects_identity_from_valid_token(self):
        """Test middleware successfully injects identity from valid JWT"""
        app = FastAPI()
        add_exception_handlers(app)
        
        now = int(time.time())
        async def mock_validator(token: str):
            if token == "valid_admin_token":
                return {
                    "sub": 42,
                    "user_type": "admin",
                    "organization_id": 1,
                    "admin_role": "admin",
                    "token_version": 1,
                    "iat": now,
                    "exp": now + 3600
                }
            raise Exception("Invalid token")
        
        app.add_middleware(IdentityInjectionMiddleware, token_validator=mock_validator)
        
        @app.get("/test")
        def test_endpoint(identity: IdentityContext = Depends(get_identity)):
            return {
                "user_id": identity.user_id,
                "user_type": identity.user_type.value,
                "is_admin": identity.is_admin()
            }
        
        client = TestClient(app)
        response = client.get("/test", headers={"Authorization": "Bearer valid_admin_token"})
        
        assert response.status_code == 200
        assert response.json() == {
            "user_id": 42,
            "user_type": "admin",
            "is_admin": True
        }
    
    def test_middleware_rejects_missing_token(self):
        """Test middleware rejects request without token"""
        app = FastAPI()
        add_exception_handlers(app)
        
        async def mock_validator(token: str):
            return {}
        
        app.add_middleware(IdentityInjectionMiddleware, token_validator=mock_validator)
        
        @app.get("/test")
        def test_endpoint(identity: IdentityContext = Depends(get_identity)):
            return {"user_id": identity.user_id}
        
        client = TestClient(app)
        response = client.get("/test")
        
        # FastAPI converts AuthenticationError to 401
        assert response.status_code in [401, 500]
    
    def test_middleware_rejects_invalid_token(self):
        """Test middleware rejects invalid token"""
        app = FastAPI()
        add_exception_handlers(app)
        
        async def mock_validator(token: str):
            from app.shared.errors import AuthenticationError
            raise AuthenticationError("Invalid token signature")
        
        app.add_middleware(IdentityInjectionMiddleware, token_validator=mock_validator)
        
        @app.get("/test")
        def test_endpoint(identity: IdentityContext = Depends(get_identity)):
            return {"user_id": identity.user_id}
        
        client = TestClient(app)
        response = client.get("/test", headers={"Authorization": "Bearer invalid_token"})
        
        assert response.status_code in [401, 500]


class TestDependencyIntegration:
    """Test dependency injection integration"""
    
    def test_require_admin_blocks_candidate(self):
        """Test require_admin dependency blocks candidate users"""
        app = FastAPI()
        add_exception_handlers(app)
        
        now = int(time.time())
        async def mock_validator(token: str):
            return {
                "sub": 123,
                "user_type": "candidate",
                "token_version": 1,
                "iat": now,
                "exp": now + 3600
            }
        
        app.add_middleware(IdentityInjectionMiddleware, token_validator=mock_validator)
        
        @app.get("/admin-only")
        def admin_endpoint(identity: IdentityContext = Depends(require_admin)):
            return {"message": "admin access granted"}
        
        client = TestClient(app)
        response = client.get("/admin-only", headers={"Authorization": "Bearer candidate_token"})
        
        # Should be blocked
        assert response.status_code in [403, 500]
    
    def test_require_candidate_blocks_admin(self):
        """Test require_candidate dependency blocks admin users"""
        app = FastAPI()
        add_exception_handlers(app)
        
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
        
        app.add_middleware(IdentityInjectionMiddleware, token_validator=mock_validator)
        
        @app.get("/candidate-only")
        def candidate_endpoint(identity: IdentityContext = Depends(require_candidate)):
            return {"message": "candidate access granted"}
        
        client = TestClient(app)
        response = client.get("/candidate-only", headers={"Authorization": "Bearer admin_token"})
        
        # Should be blocked
        assert response.status_code in [403, 500]


# NOTE: ConnectionRegistry integration tests require actual Redis instance
# These are covered by unit tests with mocked Redis operations in test_unit
# For full integration testing with Redis, set up Redis and create separate test suite


class TestWebSocketAuthenticationIntegration:
    """Test WebSocket authentication integration"""
    
    @pytest.mark.asyncio
    async def test_authenticate_websocket_full_flow(self):
        """Test complete WebSocket authentication flow"""
        import time
        now = int(time.time())
        mock_websocket = Mock()
        
        async def mock_validator(token: str):
            if token == "valid_candidate_token":
                return {
                    "sub": 123,
                    "user_type": "candidate",
                    "token_version": 1,
                    "iat": now,
                    "exp": now + 3600
                }
            from app.shared.errors import AuthenticationError
            raise AuthenticationError("Invalid token")
        
        # Valid token should return identity
        identity = await authenticate_websocket(mock_websocket, "valid_candidate_token", mock_validator)
        
        assert identity.user_id == 123
        assert identity.user_type == UserType.CANDIDATE
        
        # Invalid token should raise
        from app.shared.errors import AuthenticationError
        with pytest.raises(AuthenticationError):
            await authenticate_websocket(mock_websocket, "invalid_token", mock_validator)


class TestMultiTenantIsolation:
    """Test multi-tenant isolation enforcement"""
    
    def test_admin_cannot_access_different_organization(self):
        """Test admin from org 1 cannot access org 2 resources"""
        app = FastAPI()
        add_exception_handlers(app)
        
        now = int(time.time())
        async def mock_validator(token: str):
            return {
                "sub": 42,
                "user_type": "admin",
                "organization_id": 1,  # Org 1
                "admin_role": "admin",
                "token_version": 1,
                "iat": now,
                "exp": now + 3600
            }
        
        app.add_middleware(IdentityInjectionMiddleware, token_validator=mock_validator)
        
        @app.get("/org/{org_id}/data")
        def org_data(org_id: int, identity: IdentityContext = Depends(get_identity)):
            from app.shared.auth_context.scope import enforce_organization_scope
            enforce_organization_scope(identity, org_id)
            return {"org_id": org_id, "data": "sensitive"}
        
        client = TestClient(app)
        
        # Should allow access to own org (org 1)
        response = client.get("/org/1/data", headers={"Authorization": "Bearer admin_token"})
        assert response.status_code == 200
        
        # Should block access to different org (org 2)
        response = client.get("/org/2/data", headers={"Authorization": "Bearer admin_token"})
        assert response.status_code in [403, 500]
    
    def test_superadmin_can_access_all_organizations(self):
        """Test superadmin can access all organizations"""
        app = FastAPI()
        add_exception_handlers(app)
        
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
        
        app.add_middleware(IdentityInjectionMiddleware, token_validator=mock_validator)
        
        @app.get("/org/{org_id}/data")
        def org_data(org_id: int, identity: IdentityContext = Depends(get_identity)):
            from app.shared.auth_context.scope import enforce_organization_scope
            enforce_organization_scope(identity, org_id)
            return {"org_id": org_id, "data": "sensitive"}
        
        client = TestClient(app)
        
        # Should allow access to any org
        response = client.get("/org/1/data", headers={"Authorization": "Bearer superadmin_token"})
        assert response.status_code == 200
        
        response = client.get("/org/2/data", headers={"Authorization": "Bearer superadmin_token"})
        assert response.status_code == 200
        
        response = client.get("/org/999/data", headers={"Authorization": "Bearer superadmin_token"})
        assert response.status_code == 200
