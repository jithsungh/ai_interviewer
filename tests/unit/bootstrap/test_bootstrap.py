"""
Unit Tests for Bootstrap Module

Tests application factory, middleware registration, exception handlers.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from app.bootstrap.exception_handlers import (
    base_error_handler,
    validation_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
)
from app.shared.errors import BaseError, AuthenticationError, ValidationError


class TestExceptionHandlers:
    """Test global exception handlers"""
    
    @pytest.mark.asyncio
    async def test_base_error_handler(self):
        """Test BaseError handler returns structured JSON"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "test-request-123"
        
        error = AuthenticationError(
            message="Invalid token",
            request_id="test-request-123"
        )
        
        response = await base_error_handler(request, error)
        
        assert isinstance(response, JSONResponse)
        assert response.status_code == 401
        
        # Parse response body
        import json
        body = json.loads(response.body.decode())
        
        assert body["error"]["code"] == "AUTHENTICATION_FAILED"
        assert body["error"]["message"] == "Invalid token"
        assert body["error"]["request_id"] == "test-request-123"
    
    @pytest.mark.asyncio
    async def test_base_error_handler_injects_request_id(self):
        """Test handler injects request_id if not present in error"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "injected-request-id"
        
        error = BaseError(
            error_code="test_error",
            message="Test error",
            http_status_code=400
        )
        
        response = await base_error_handler(request, error)
        
        import json
        body = json.loads(response.body.decode())
        
        assert body["error"]["request_id"] == "injected-request-id"
    
    @pytest.mark.asyncio
    async def test_http_exception_handler(self):
        """Test HTTPException handler returns structured format"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "test-request-456"
        
        exc = HTTPException(status_code=404, detail="Resource not found")
        
        response = await http_exception_handler(request, exc)
        
        assert response.status_code == 404
        
        import json
        body = json.loads(response.body.decode())
        
        assert body["error"]["code"] == "http_404"
        assert body["error"]["message"] == "Resource not found"
        assert body["error"]["request_id"] == "test-request-456"
    
    @pytest.mark.asyncio
    async def test_unhandled_exception_handler(self):
        """Test catch-all handler returns 500 without exposing internals"""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "test-request-789"
        request.url = Mock()
        request.url.__str__ = Mock(return_value="http://test.com/api/test")
        
        exc = ValueError("Internal error details")
        
        response = await unhandled_exception_handler(request, exc)
        
        assert response.status_code == 500
        
        import json
        body = json.loads(response.body.decode())
        
        assert body["error"]["code"] == "internal_server_error"
        # Should not expose internal error details  
        assert "ValueError" not in body["error"]["message"]
        assert "Internal error details" not in body["error"]["message"]
        assert body["error"]["request_id"] == "test-request-789"


class TestMiddlewareRegistration:
    """Test middleware registration order and configuration"""
    
    def test_middleware_order_is_documented(self):
        """Verify middleware order is explicitly documented"""
        from app.bootstrap import middleware
        
        # Check module docstring documents order
        assert "order" in middleware.__doc__.lower() or "Order" in middleware.__doc__
        
    @patch('app.bootstrap.middleware.logger')
    def test_register_middleware_logs_registration(self, mock_logger):
        """Test register_middleware logs each middleware registration"""
        app = FastAPI()
        
        from app.bootstrap.middleware import register_middleware
        
        register_middleware(app)
        
        # Should log start and completion
        assert mock_logger.info.call_count >= 2
        assert mock_logger.debug.call_count >= 5  # One per middleware


class TestLifespanManagement:
    """Test application lifespan (startup/shutdown)"""
    
    @pytest.mark.asyncio
    @patch('app.bootstrap.lifespan.global_settings')
    @patch('app.bootstrap.lifespan.init_engine')
    @patch('app.bootstrap.lifespan.init_session_factory')
    @patch('app.bootstrap.lifespan.check_postgres_connectivity')
    @patch('app.bootstrap.lifespan.init_redis_client')
    @patch('app.bootstrap.lifespan.init_qdrant_client')
    async def test_lifespan_startup_sequence(
        self,
        mock_init_qdrant,
        mock_init_redis,
        mock_postgres_check,
        mock_init_session,
        mock_init_engine,
        mock_settings
    ):
        """Test lifespan initializes components in correct order"""
        from app.bootstrap.lifespan import lifespan
        
        mock_postgres_check.return_value = True
        mock_settings.app.app_env = "test"
        mock_settings.database = Mock()
        mock_settings.redis = Mock()
        mock_settings.qdrant = Mock()
        
        app = FastAPI()
        
        async with lifespan(app):
            # Verify initialization calls
            mock_init_engine.assert_called_once()
            mock_init_session.assert_called_once()
            mock_postgres_check.assert_called_once()
            mock_init_redis.assert_called_once()
            mock_init_qdrant.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('app.bootstrap.lifespan.global_settings')
    @patch('app.bootstrap.lifespan.cleanup_engine')
    @patch('app.bootstrap.lifespan.cleanup_redis')
    @patch('app.bootstrap.lifespan.cleanup_qdrant')
    @patch('app.bootstrap.lifespan.init_engine')
    @patch('app.bootstrap.lifespan.init_session_factory')  
    @patch('app.bootstrap.lifespan.check_postgres_connectivity')
    @patch('app.bootstrap.lifespan.init_redis_client')
    @patch('app.bootstrap.lifespan.init_qdrant_client')
    async def test_lifespan_shutdown_sequence(
        self,
        mock_init_qdrant,
        mock_init_redis,
        mock_postgres_check,
        mock_init_session,
        mock_init_engine,
        mock_cleanup_qdrant,
        mock_cleanup_redis,
        mock_cleanup_engine,
        mock_settings
    ):
        """Test lifespan cleanup on shutdown"""
        from app.bootstrap.lifespan import lifespan
        
        mock_postgres_check.return_value = True
        mock_settings.app.app_env = "test"
        mock_settings.database = Mock()
        mock_settings.redis = Mock()
        mock_settings.qdrant = Mock()
        
        app = FastAPI()
        
        async with lifespan(app):
            pass  # Just enter and exit
        
        # Verify cleanup calls
        mock_cleanup_engine.assert_called_once()
        mock_cleanup_redis.assert_called_once()
        mock_cleanup_qdrant.assert_called_once()


class TestAppFactory:
    """Test application factory function"""
    
    @patch('app.bootstrap.app.register_middleware')
    @patch('app.bootstrap.app.register_routers')
    @patch('app.bootstrap.app.register_exception_handlers')
    def test_create_app_returns_fastapi_instance(
        self,
        mock_handlers,
        mock_routers,
        mock_middleware
    ):
        """Test create_app returns configured FastAPI app"""
        from app.bootstrap.app import create_app
        
        with patch('app.bootstrap.app.global_settings') as mock_settings:
            mock_settings.app.app_name = "Test App"
            mock_settings.app.api_version = "1.0.0"
            mock_settings.app.debug = True
            
            app = create_app()
            
            assert isinstance(app, FastAPI)
            assert app.title is not None
            assert app.version is not None
            
            # Verify registration functions called
            mock_middleware.assert_called_once()
            mock_routers.assert_called_once()
            mock_handlers.assert_called_once()
    
    @patch('app.bootstrap.app.register_middleware')
    @patch('app.bootstrap.app.register_routers')
    @patch('app.bootstrap.app.register_exception_handlers')
    def test_create_app_disables_docs_in_production(
        self,
        mock_handlers,
        mock_routers,
        mock_middleware
    ):
        """Test docs are disabled when debug=False"""
        from app.bootstrap.app import create_app
        
        with patch('app.bootstrap.app.global_settings') as mock_settings:
            mock_settings.app.app_name = "Test App"
            mock_settings.app.api_version = "1.0.0"
            mock_settings.app.debug = False
            mock_settings.app.app_env = "prod"
            
            app = create_app()
            
            # Docs should be disabled
            assert app.docs_url is None
            assert app.redoc_url is None
    
    @patch('app.bootstrap.app.register_middleware')
    @patch('app.bootstrap.app.register_routers')
    @patch('app.bootstrap.app.register_exception_handlers')
    def test_create_app_enables_docs_in_debug(
        self,
        mock_handlers,
        mock_routers,
        mock_middleware
    ):
        """Test docs are enabled when debug=True"""
        from app.bootstrap.app import create_app
        
        with patch('app.bootstrap.app.global_settings') as mock_settings:
            mock_settings.app.app_name = "Test App"
            mock_settings.app.api_version = "1.0.0"
            mock_settings.app.debug = True
            mock_settings.app.app_env = "dev"
            
            app = create_app()
            
            # Docs should be enabled
            assert app.docs_url == "/docs"
            assert app.redoc_url == "/redoc"


class TestDependencies:
    """Test dependency re-exports"""
    
    def test_database_dependencies_exported(self):
        """Test database dependencies are re-exported"""
        from app.bootstrap.dependencies import get_db_session, get_db_session_with_commit
        
        assert callable(get_db_session)
        assert callable(get_db_session_with_commit)
    
    def test_auth_dependencies_exported(self):
        """Test auth dependencies are re-exported"""
        from app.bootstrap.dependencies import (
            get_identity,
            require_admin,
            require_candidate,
            require_superadmin
        )
        
        assert callable(get_identity)
        assert callable(require_admin)
        assert callable(require_candidate)
        assert callable(require_superadmin)
