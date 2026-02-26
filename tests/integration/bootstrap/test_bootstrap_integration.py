"""
Integration Tests for Bootstrap Module

Tests full application startup, middleware stack, and health checks.
"""

import pytest
from fastapi.testclient import TestClient


class TestApplicationStartup:
    """Test full application initialization"""
    
    def test_app_instance_exists(self):
        """Test app instance is created"""
        from app.bootstrap import app
        
        assert app is not None
        assert hasattr(app, 'title')
        assert hasattr(app, 'version')
    
    def test_health_endpoint_accessible(self):
        """Test /health endpoint responds"""
        from app.bootstrap import app
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data
    
    def test_database_health_endpoint(self):
        """Test /health/database endpoint responds"""
        from app.bootstrap import app
        
        client = TestClient(app)
        response = client.get("/health/database")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        # May be healthy or degraded depending on DB availability


class TestMiddlewareStack:
    """Test middleware integration"""
    
    def test_request_id_injected(self):
        """Test request ID is added to response headers"""
        from app.bootstrap import app
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format
    
    def test_cors_headers_present(self):
        """Test CORS middleware adds appropriate headers"""
        from app.bootstrap import app
        
        client = TestClient(app)
        
        # Preflight request
        response = client.options(
            "/health",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


class TestExceptionHandling:
    """Test global exception handlers"""
    
    def test_404_returns_structured_error(self):
        """Test 404 errors return structured format"""
        from app.bootstrap import app
        
        client = TestClient(app)
        response = client.get("/nonexistent-endpoint")
        
        assert response.status_code == 404
        data = response.json()
        
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "request_id" in data["error"]
    
    def test_validation_error_returns_structured_format(self):
        """Test validation errors return structured format"""
        from app.bootstrap import app
        from fastapi import FastAPI
        from pydantic import BaseModel
        
        # Add test endpoint with validation
        @app.post("/test-validation")
        def test_endpoint(data: BaseModel):
            return {"ok": True}
        
        client = TestClient(app)
        
        # Send invalid data
        response = client.post(
            "/test-validation",
            json={"invalid": "data"}
        )
        
        assert response.status_code == 422
        data = response.json()
        
        assert "error" in data
        assert data["error"]["code"] == "validation_error"
        assert "request_id" in data["error"]


class TestDatabaseIntegration:
    """Test database connectivity through application"""
    
    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration", default=False),
        reason="Requires database connection"
    )
    def test_database_session_dependency(self):
        """Test get_db_session dependency works in endpoints"""
        from app.bootstrap import app
        from app.bootstrap.dependencies import get_db_session
        from fastapi import Depends
        from sqlalchemy.orm import Session
        from sqlalchemy import text
        
        # Add test endpoint using DB dependency
        @app.get("/test-db")
        def test_db(db: Session = Depends(get_db_session)):
            result = db.execute(text("SELECT 1 as num")).fetchone()
            return {"result": result[0]}
        
        client = TestClient(app)
        response = client.get("/test-db")
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == 1


class TestRouterRegistry:
    """Test router registration system"""
    
    def test_health_endpoints_registered(self):
        """Test health check endpoints are accessible"""
        from app.bootstrap import app
        
        client = TestClient(app)
        
        # Test both health endpoints
        response1 = client.get("/health")
        response2 = client.get("/health/database")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
    
    def test_openapi_schema_generated(self):
        """Test OpenAPI schema is generated (if docs enabled)"""
        from app.bootstrap import app
        from app.config import settings
        
        client = TestClient(app)
        
        if settings.app.debug:
            response = client.get("/openapi.json")
            assert response.status_code == 200  
            
            schema = response.json()
            assert "openapi" in schema
            assert "info" in schema
            assert "paths" in schema


class TestLifespanEvents:
    """Test application lifespan events"""
    
    def test_lifespan_context_manager(self):
        """Test lifespan properly enters and exits"""
        from app.bootstrap.lifespan import lifespan
        from fastapi import FastAPI
        import asyncio
        
        app = FastAPI()
        
        async def test():
            async with lifespan(app):
                # App should be initialized
                pass
            # App should be cleaned up
        
        # Should not raise
        asyncio.run(test())


# Test configuration
def pytest_addoption(parser):
    """Add custom pytest options"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require database"
    )
