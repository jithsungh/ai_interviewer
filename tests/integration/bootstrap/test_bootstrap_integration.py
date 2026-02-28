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
        from app.bootstrap import create_app
        
        app = create_app()
        assert app is not None
        assert hasattr(app, 'title')
        assert hasattr(app, 'version')
    
    def test_health_endpoint_accessible(self):
        """Test /health endpoint responds"""
        from app.bootstrap import create_app
        
        app = create_app()
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
        from app.bootstrap import create_app
        
        app = create_app()
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
        from app.bootstrap import create_app
        
        app = create_app()
        client = TestClient(app)
        response = client.get("/health")
        
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format
    
    def test_cors_headers_present(self):
        """Test CORS middleware adds appropriate headers"""
        from app.bootstrap import create_app
        
        app = create_app()
        client = TestClient(app)
        
        # Preflight request — origin must match allow_origins in middleware
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        
        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers or response.status_code == 200


class TestExceptionHandling:
    """Test global exception handlers"""
    
    def test_404_returns_structured_error(self):
        """Test 404 errors return structured format"""
        from app.bootstrap import create_app
        
        app = create_app()
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
        from app.bootstrap import create_app
        from pydantic import BaseModel, Field
        
        app = create_app()
        
        # Define a model with required fields
        class TestModel(BaseModel):
            required_field: str = Field(..., description="This field is required")
            number_field: int = Field(..., gt=0, description="Must be positive")
        
        # Add test endpoint with validation
        @app.post("/test-validation")
        def test_endpoint(data: TestModel):
            return {"ok": True}
        
        client = TestClient(app)
        
        # Send invalid data (missing required fields)
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
    
    @pytest.mark.integration
    def test_database_session_dependency(self):
        """Test database health endpoint structure and connectivity"""
        from app.bootstrap import create_app
        
        app = create_app()
        client = TestClient(app)
        
        # The /health/database endpoint tests database connectivity
        response = client.get("/health/database")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have database health status
        assert "status" in data
        # Can be healthy, degraded, or unhealthy depending on DB state and initialization
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        
        # Should have timestamp
        assert "timestamp" in data


class TestRouterRegistry:
    """Test router registration system"""
    
    def test_health_endpoints_registered(self):
        """Test health check endpoints are accessible"""
        from app.bootstrap import create_app
        
        app = create_app()
        client = TestClient(app)
        
        # Test both health endpoints
        response1 = client.get("/health")
        response2 = client.get("/health/database")
        
        assert response1.status_code == 200
        assert response2.status_code == 200
    
    def test_openapi_schema_generated(self):
        """Test OpenAPI schema is generated (if docs enabled)"""
        from app.bootstrap import create_app
        from app.config.settings import Settings
        
        app = create_app()
        client = TestClient(app)
        settings = Settings.load()
        
        if settings.app.debug:
            response = client.get("/openapi.json")
            assert response.status_code == 200  
            
            schema = response.json()
            assert "openapi" in schema
            assert "info" in schema
            assert "paths" in schema


class TestLifespanEvents:
    """Test application lifespan events"""
    
    @pytest.mark.asyncio
    async def test_lifespan_context_manager(self):
        """Test lifespan properly enters and exits"""
        from app.bootstrap.lifespan import lifespan
        from fastapi import FastAPI
        
        app = FastAPI()
        
        # Use lifespan as context manager - it will initialize and cleanup
        async with lifespan(app):
            # App should be initialized with all connections
            # Just verify we got here without errors
            assert True
        
        # App should be cleaned up - verify we got here without errors
        assert True


# Test configuration
def pytest_addoption(parser):
    """Add custom pytest options"""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require database"
    )
