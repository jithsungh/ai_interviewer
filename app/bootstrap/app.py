"""
FastAPI Application Factory

Creates and configures the FastAPI application with all middleware,
routers, and exception handlers.

This is the application assembly layer - it wires everything together
but contains NO business logic.
"""

from fastapi import FastAPI

from app.config import settings as global_settings
from app.shared.observability import get_context_logger

from .lifespan import lifespan
from .middleware import register_middleware
from .exception_handlers import register_exception_handlers
from .router_registry import register_routers

# Get logger instance
logger = get_context_logger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.
    
    Assembly order:
    1. Create FastAPI instance with lifespan
    2. Register middleware (order critical)
    3. Register routers (incremental as implemented)
    4. Register exception handlers
    
    Returns:
        Fully configured FastAPI application
    """
    
    # Load settings if in testing mode (where global_settings is None)
    if global_settings is None:
        from app.config.settings import Settings
        settings = Settings.load()
    else:
        settings = global_settings
    
    logger.info("Creating FastAPI application...", event_type="app.factory.begin")
    
    # ==========================================
    # 1. Create FastAPI Instance
    # ==========================================
    
    app = FastAPI(
        title=settings.app.app_name,
        version=settings.app.api_version,
        description="Multi-tenant AI interview orchestration platform",
        lifespan=lifespan,
        debug=settings.app.debug,
        docs_url="/docs" if settings.app.debug else None,
        redoc_url="/redoc" if settings.app.debug else None,
    )
    
    logger.debug(
        "FastAPI instance created",
        metadata={
            "title": settings.app.app_name,
            "version": settings.app.api_version,
            "debug": settings.app.debug,
            "docs_enabled": settings.app.debug
        }
    )
    
    # ==========================================
    # 2. Register Middleware
    # ==========================================
    
    register_middleware(app)
    
    # ==========================================
    # 3. Register Routers
    # ==========================================
    
    register_routers(app)
    
    # ==========================================
    # 4. Register Exception Handlers
    # ==========================================
    
    register_exception_handlers(app)
    
    # ==========================================
    # Done
    # ==========================================
    
    logger.info(
        "✅ FastAPI application created successfully",
        event_type="app.factory.complete",
        metadata={
            "environment": settings.app.app_env,
            "debug": settings.app.debug
        }
    )
    
    return app


# ==========================================
# Application Instance
# ==========================================

# Only create app instance if not in testing mode
app = create_app() if global_settings is not None else None
