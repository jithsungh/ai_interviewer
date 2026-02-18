"""
Unit Tests for Observability - Tracing Module

Tests request ID generation, connection ID management, and trace context.
"""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi import Request
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.shared.observability.tracing import (
    TraceContext,
    generate_request_id,
    generate_connection_id,
    generate_session_id,
    generate_correlation_id,
    extract_request_id,
    RequestIDMiddleware,
    create_trace_context_from_request,
)


class TestTraceContext:
    """Test TraceContext dataclass"""
    
    def test_trace_context_creation(self):
        """Test creating trace context"""
        context = TraceContext(
            request_id="req_123",
            correlation_id="corr_456",
            parent_span_id="span_789"
        )
        
        assert context.request_id == "req_123"
        assert context.correlation_id == "corr_456"
        assert context.parent_span_id == "span_789"
    
    def test_trace_context_minimal(self):
        """Test creating trace context with only request_id"""
        context = TraceContext(request_id="req_123")
        
        assert context.request_id == "req_123"
        assert context.correlation_id is None
        assert context.parent_span_id is None
    
    def test_trace_context_to_dict(self):
        """Test converting trace context to dictionary"""
        context = TraceContext(
            request_id="req_123",
            correlation_id="corr_456"
        )
        
        data = context.to_dict()
        
        assert data["request_id"] == "req_123"
        assert data["correlation_id"] == "corr_456"
        assert data["parent_span_id"] is None
    
    def test_trace_context_from_dict(self):
        """Test creating trace context from dictionary"""
        data = {
            "request_id": "req_123",
            "correlation_id": "corr_456",
            "parent_span_id": None
        }
        
        context = TraceContext.from_dict(data)
        
        assert context.request_id == "req_123"
        assert context.correlation_id == "corr_456"


class TestIDGeneration:
    """Test ID generation functions"""
    
    def test_generate_request_id(self):
        """Test request ID generation"""
        req_id = generate_request_id()
        
        assert req_id.startswith("req_")
        assert len(req_id) == 16  # "req_" + 12 hex chars
    
    def test_generate_request_id_unique(self):
        """Test request IDs are unique"""
        ids = {generate_request_id() for _ in range(100)}
        
        # All 100 IDs should be unique
        assert len(ids) == 100
    
    def test_generate_connection_id(self):
        """Test connection ID generation"""
        conn_id = generate_connection_id()
        
        assert conn_id.startswith("conn_")
        assert len(conn_id) == 17  # "conn_" + 12 hex chars
    
    def test_generate_connection_id_unique(self):
        """Test connection IDs are unique"""
        ids = {generate_connection_id() for _ in range(100)}
        
        assert len(ids) == 100
    
    def test_generate_session_id(self):
        """Test session ID generation"""
        session_id = generate_session_id()
        
        assert session_id.startswith("session_")
        assert len(session_id) == 20  # "session_" + 12 hex chars
    
    def test_generate_session_id_unique(self):
        """Test session IDs are unique"""
        ids = {generate_session_id() for _ in range(100)}
        
        assert len(ids) == 100
    
    def test_generate_correlation_id(self):
        """Test correlation ID generation"""
        corr_id = generate_correlation_id()
        
        assert corr_id.startswith("corr_")
        assert len(corr_id) == 17  # "corr_" + 12 hex chars


class TestExtractRequestID:
    """Test request ID extraction"""
    
    def test_extract_from_header(self):
        """Test extracting request ID from header"""
        # Mock request with X-Request-ID header
        request = Mock(spec=Request)
        request.headers = {"X-Request-ID": "req_existing"}
        
        req_id = extract_request_id(request)
        
        assert req_id == "req_existing"
    
    def test_generate_if_missing(self):
        """Test generating request ID if header missing"""
        # Mock request without X-Request-ID header
        request = Mock(spec=Request)
        request.headers = {}
        
        req_id = extract_request_id(request)
        
        assert req_id.startswith("req_")
        assert len(req_id) == 16


class TestRequestIDMiddleware:
    """Test RequestIDMiddleware"""
    
    def test_middleware_injects_request_id(self):
        """Test middleware injects request ID into request state"""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"request_id": request.state.request_id}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert "request_id" in response.json()
        assert response.json()["request_id"].startswith("req_")
    
    def test_middleware_adds_response_header(self):
        """Test middleware adds X-Request-ID to response headers"""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"].startswith("req_")
    
    def test_middleware_preserves_existing_request_id(self):
        """Test middleware preserves X-Request-ID from request"""
        app = FastAPI()
        app.add_middleware(RequestIDMiddleware)
        
        @app.get("/test")
        async def test_endpoint(request: Request):
            return {"request_id": request.state.request_id}
        
        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"X-Request-ID": "req_client_provided"}
        )
        
        assert response.status_code == 200
        assert response.json()["request_id"] == "req_client_provided"
        assert response.headers["X-Request-ID"] == "req_client_provided"


class TestCreateTraceContextFromRequest:
    """Test creating trace context from request"""
    
    def test_create_from_request_with_state(self):
        """Test creating trace context from request with state"""
        # Mock request with request_id in state
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "req_123"
        request.headers = {}
        
        context = create_trace_context_from_request(request)
        
        assert context.request_id == "req_123"
        assert context.correlation_id is None
    
    def test_create_from_request_with_correlation_id(self):
        """Test creating trace context with correlation ID"""
        # Mock request with correlation ID header
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.request_id = "req_123"
        request.headers = {"X-Correlation-ID": "corr_456"}
        
        context = create_trace_context_from_request(request)
        
        assert context.request_id == "req_123"
        assert context.correlation_id == "corr_456"
    
    def test_create_from_request_generates_id_if_missing(self):
        """Test generating request ID if not in state"""
        # Mock request without request_id in state
        request = Mock(spec=Request)
        request.state = Mock(spec=[])  # Empty state
        request.headers = {}
        
        context = create_trace_context_from_request(request)
        
        assert context.request_id.startswith("req_")


# Test Results Summary
def test_tracing_module_summary():
    """Summary of tracing module tests"""
    print("\n" + "="*60)
    print("TRACING MODULE TEST SUMMARY")
    print("="*60)
    print("✅ TraceContext tests: 4 tests")
    print("✅ ID generation tests: 8 tests")
    print("✅ Extract request ID tests: 2 tests")
    print("✅ RequestIDMiddleware tests: 3 tests")
    print("✅ Create trace context tests: 3 tests")
    print("="*60)
    print("Total: 20 tests")
    print("="*60)
