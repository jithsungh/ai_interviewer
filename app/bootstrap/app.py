"""
FastAPI Application Bootstrap

App initialization, middleware registration, lifespan management.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.config import settings
from app.persistence.redis import redis_client
from app.persistence.qdrant import qdrant_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events for external connections.
    """
    # Startup
    print("🚀 Starting AI Interviewer Backend...")
    
    # Initialize Redis
    await redis_client.connect()
    print("✓ Redis connected")
    
    # Initialize Qdrant
    qdrant_client.connect()
    print("✓ Qdrant connected")
    
    # Initialize database (migrations handled separately)
    print("✓ Database ready")
    
    print("✅ Application started successfully")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down AI Interviewer Backend...")
    
    # Close Redis
    await redis_client.disconnect()
    print("✓ Redis disconnected")
    
    # Close Qdrant
    qdrant_client.disconnect()
    print("✓ Qdrant disconnected")
    
    print("✅ Application shutdown complete")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Returns:
        Configured FastAPI app instance
    """
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Multi-tenant AI interview orchestration platform",
        lifespan=lifespan,
        debug=settings.debug,
    )
    
    # CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Compression Middleware
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # TODO: Add authentication middleware
    # TODO: Add tenant isolation middleware (NFR-7.1)
    # TODO: Add request logging middleware (NFR-11)
    # TODO: Add rate limiting middleware
    
    # TODO: Register routers
    # app.include_router(auth_router, prefix=f"{settings.api_v1_prefix}/auth")
    # app.include_router(interview_router, prefix=f"{settings.api_v1_prefix}/interviews")
    # app.include_router(admin_router, prefix=f"{settings.api_v1_prefix}/admin")
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.environment
        }
    
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health"
        }
    
    return app


app = create_app()
