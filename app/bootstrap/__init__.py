"""
Bootstrap Module

Application assembly layer for FastAPI.

Responsibilities:
- Application factory (create_app)
- Lifespan management (startup/shutdown)
- Middleware registration
- Router registration  
- Exception handler registration
- Dependency injection wiring

Public API:
- create_app(): Factory function to create configured FastAPI app
- app: Pre-configured application instance (for uvicorn)
- dependencies: Re-exported common dependencies for convenience

Usage:
    # In main.py or tests
    from app.bootstrap import app, create_app
    
    # Run with uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
    # Or create custom instance
    custom_app = create_app()
"""

from .app import create_app, app
from . import dependencies

__all__ = [
    "create_app",
    "app",
    "dependencies",
]
