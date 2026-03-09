"""
Router Registry

Centralized registration of all API routers.

This module provides a single place to register all domain API routers
as they are implemented. Currently a skeleton awaiting router implementations.

Design:
- Each router is registered with a prefix (e.g., /api/v1/auth)
- Routers are added incrementally as domain modules are completed
- Tags organize endpoints in OpenAPI docs
"""

from fastapi import FastAPI

from app.config import settings as global_settings
from app.shared.observability import get_context_logger

logger = get_context_logger(__name__)


def register_routers(app: FastAPI) -> None:
    """
    Register all API routers with the FastAPI application.
    
    Args:
        app: FastAPI application instance
    
    Routers are organized by domain:
    - /api/v1/auth: Authentication endpoints
    - /api/v1/admin: Admin management endpoints
    - /api/v1/interviews: Interview session endpoints
    - /api/v1/questions: Question bank endpoints
    - /api/v1/evaluations: Evaluation and scoring endpoints
    - /api/v1/coding: Code execution endpoints
    - /api/v1/proctoring: Anti-cheating endpoints
    - /api/v1/audio: Audio processing endpoints
    
    As domain modules are implemented, uncomment and import their routers here.
    """
    
    logger.info("Registering API routers...", event_type="routers.registration.begin")
    
    # API version prefix
    api_prefix = "/api/v1"
    
    # ==========================================
    # ROUTERS (Uncomment as implemented)
    # ==========================================
    
    # Auth Module
    from app.auth.api.routes import router as auth_router
    app.include_router(
        auth_router,
        prefix=f"{api_prefix}/auth",
        tags=["Authentication"]
    )
    logger.debug("✓ Auth router registered")
    
    # Admin Module
    from app.admin.api.routes import router as admin_router
    app.include_router(
        admin_router,
        prefix=f"{api_prefix}/admin",
        tags=["Admin"]
    )
    logger.debug("✓ Admin router registered")
    
    # Candidate Module
    from app.candidate.api.routes import router as candidate_router
    app.include_router(
        candidate_router,
        prefix=f"{api_prefix}/candidate",
        tags=["Candidate"]
    )
    logger.debug("✓ Candidate router registered")
    
    # Interview Module (parent)
    from app.interview.api.routes import router as interview_router
    app.include_router(
        interview_router,
        prefix=f"{api_prefix}/interviews",
        tags=["Interviews"]
    )
    logger.debug("✓ Interview router registered")

    # Interview Session Sub-Module
    from app.interview.session.api.routes import router as session_router
    app.include_router(
        session_router,
        prefix=f"{api_prefix}/interviews/sessions",
        tags=["Interview Sessions"]
    )
    logger.debug("✓ Interview session router registered")
    
    # # Question Module (parent — uncomment when question.api.routes exists)
    # from app.question.api.routes import router as question_router
    # app.include_router(
    #     question_router,
    #     prefix=f"{api_prefix}/questions",
    #     tags=["Questions"]
    # )
    # logger.debug("✓ Question router registered")

    # Question Selection Sub-Module (admin diagnostics)
    from app.question.selection.api import router as selection_router
    app.include_router(
        selection_router,
        prefix=f"{api_prefix}/questions/selection",
        tags=["Question Selection"],
    )
    logger.debug("✓ Question selection router registered")
    
    # Evaluation Module
    from app.evaluation.api.routes import router as evaluation_router
    app.include_router(
        evaluation_router,
        prefix=f"{api_prefix}/evaluations",
        tags=["Evaluations"]
    )
    logger.debug("✓ Evaluation router registered")
    
    # Coding Module
    from app.coding.api.routes import router as coding_router
    app.include_router(
        coding_router,
        prefix=f"{api_prefix}/coding",
        tags=["Coding"]
    )
    logger.debug("✓ Coding router registered")
    
    # Proctoring Ingestion Sub-Module
    from app.proctoring.ingestion.api.routes import router as proctoring_ingestion_router
    app.include_router(
        proctoring_ingestion_router,
        prefix=f"{api_prefix}/proctoring",
        tags=["Proctoring"],
    )
    logger.debug("✓ Proctoring ingestion router registered")

    # Proctoring Risk Model Sub-Module
    from app.proctoring.risk_model.api.routes import router as proctoring_risk_router
    app.include_router(
        proctoring_risk_router,
        prefix=f"{api_prefix}/proctoring",
        tags=["Proctoring"],
    )
    logger.debug("✓ Proctoring risk model router registered")
    
    # Audio Ingestion Module
    from app.audio.ingestion.api.routes import router as audio_ingestion_router
    app.include_router(
        audio_ingestion_router,
        prefix=f"{api_prefix}/audio/ingestion",
        tags=["Audio Ingestion"]
    )
    logger.debug("✓ Audio ingestion router registered")
    
    # Audio Transcription Module
    from app.audio.transcription.api.routes import router as audio_transcription_router
    app.include_router(
        audio_transcription_router,
        prefix=f"{api_prefix}/audio/transcription",
        tags=["Audio Transcription"]
    )
    logger.debug("✓ Audio transcription router registered")
    
    # Interview Realtime Module (WebSocket)
    from app.interview.realtime.api.routes import router as realtime_router
    app.include_router(
        realtime_router,
        tags=["Interview Realtime"]
    )
    logger.debug("✓ Interview realtime router registered")
    
    # Storage Module (Azure Blob Storage)
    from app.shared.storage.routes import router as storage_router
    app.include_router(
        storage_router,
        prefix=f"{api_prefix}/storage",
        tags=["Storage"]
    )
    logger.debug("✓ Storage router registered")
    
    # ==========================================
    # Health Check Endpoints
    # ==========================================
    
    from app.persistence.postgres import get_health_check_endpoint_response
    
    @app.get("/health", tags=["System"])
    async def health_check():
        """Basic health check endpoint"""
        # Load settings if in testing mode
        if global_settings is None:
            from app.config.settings import Settings
            settings = Settings.load()
        else:
            settings = global_settings
            
        return {
            "status": "healthy",
            "version": settings.app.api_version,
            "environment": settings.app.app_env
        }
    
    @app.get("/health/database", tags=["System"])
    async def database_health():
        """Database health check with connection pool status"""
        return get_health_check_endpoint_response()
    
    logger.debug("✓ Health check endpoints registered")
    
    # ==========================================
    # Summary
    # ==========================================
    
    registered_count = 1  # Auth router registered
    
    logger.info(
        "✅ Router registration complete",
        event_type="routers.registration.complete",
        metadata={
            "router_count": registered_count,
            "health_endpoints": 2
        }
    )
