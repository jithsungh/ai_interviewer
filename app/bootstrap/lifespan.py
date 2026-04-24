"""
Application Lifespan Management

Handles startup and shutdown events for infrastructure connections.
Ensures proper initialization order and graceful cleanup.
"""

import asyncio
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config import settings as global_settings
from app.shared.observability import get_context_logger
from app.persistence.postgres import (
    init_engine,
    init_session_factory,
    cleanup_engine,
    check_postgres_connectivity
)
from app.persistence.redis import (
    init_redis_client,
    cleanup_redis,
)
from app.persistence.qdrant import (
    init_qdrant_client,
    cleanup_qdrant,
)
from app.persistence.blob import (
    init_blob_client,
    cleanup_blob,
)
from app.persistence.postgres.session import get_session_factory
from app.interview.session.expiry.service import SubmissionExpiryService

logger = get_context_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    
    Manages startup and shutdown of all infrastructure connections:
    1. Logging (first, so all subsequent steps can log)
    2. Database (engine + session factory)
    3. Redis (sessions, caching, rate limiting)
    4. Qdrant (vector search for questions)
    
    Yields:
        Control to application (FastAPI runs during yield)
    
    Cleanup:
        Gracefully closes all connections on shutdown
    """
    
    # Load settings if in testing mode (where global_settings is None)
    if global_settings is None:
        from app.config.settings import Settings
        settings = Settings.load()
    else:
        settings = global_settings
    
    # ==================
    # STARTUP
    # ==================
    
    logger.info(
        "🚀 Starting AI Interviewer Backend",
        event_type="app.startup.begin",
        metadata={"environment": settings.app.app_env}
    )
    
    expiry_worker_task = None

    try:
        # 1. Logging already initialized (imported at module level)
        logger.info("✓ Logging configured", event_type="startup.logging.complete")
        
        # 2. Initialize PostgreSQL
        logger.info("Initializing PostgreSQL...", event_type="startup.postgres.begin")
        init_engine(settings.database)
        init_session_factory()
        
        # Verify connectivity
        if check_postgres_connectivity():
            logger.info("✓ PostgreSQL connected", event_type="startup.postgres.complete")
        else:
            logger.warning(
                "⚠️  PostgreSQL connectivity check failed",
                event_type="startup.postgres.warning"
            )
        
        # 3. Initialize Redis
        logger.info("Initializing Redis...", event_type="startup.redis.begin")
        try:
            init_redis_client(settings.redis)
            logger.info("✓ Redis connected", event_type="startup.redis.complete")
        except Exception as e:
            logger.warning(
                f"⚠️  Redis connection failed: {e}",
                event_type="startup.redis.warning",
                metadata={"error": str(e)}
            )
        
        # 4. Initialize Qdrant
        logger.info("Initializing Qdrant...", event_type="startup.qdrant.begin")
        try:
            init_qdrant_client(settings.qdrant)
            logger.info("✓ Qdrant connected", event_type="startup.qdrant.complete")
        except Exception as e:
            logger.warning(
                f"⚠️  Qdrant connection failed: {e}",
                event_type="startup.qdrant.warning",
                metadata={"error": str(e)}
            )
        
        # 5. Initialize Azure Blob Storage (optional)
        if settings.azure_storage is not None:
            logger.info("Initializing Azure Blob Storage...", event_type="startup.blob.begin")
            try:
                # Use timeout to prevent hanging on network issues
                try:
                    blob_task = asyncio.create_task(asyncio.to_thread(init_blob_client, settings.azure_storage))
                    await asyncio.wait_for(blob_task, timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning(
                        "⚠️  Azure Blob Storage connection timeout (skipping)",
                        event_type="startup.blob.timeout",
                    )
                else:
                    logger.info("✓ Azure Blob Storage connected", event_type="startup.blob.complete")
            except Exception as e:
                logger.warning(
                    f"⚠️  Azure Blob Storage connection failed: {e}",
                    event_type="startup.blob.warning",
                    metadata={"error": str(e)}
                )
        else:
            logger.info("Azure Blob Storage not configured, skipping", event_type="startup.blob.skipped")

        expiry_worker_enabled = os.getenv("INTERVIEW_EXPIRY_WORKER_ENABLED", "false").lower() == "true"
        expiry_worker_interval = int(os.getenv("INTERVIEW_EXPIRY_WORKER_INTERVAL_SECONDS", "60"))
        expiry_worker_batch = int(os.getenv("INTERVIEW_EXPIRY_WORKER_BATCH_SIZE", "500"))

        if expiry_worker_enabled:
            async def _expiry_worker_loop() -> None:
                while True:
                    await asyncio.sleep(expiry_worker_interval)
                    db = get_session_factory()()
                    try:
                        svc = SubmissionExpiryService(db)
                        expired = svc.expire_overdue_submissions(
                            actor="system:expiry_worker",
                            limit=expiry_worker_batch,
                        )
                        db.commit()
                        if expired > 0:
                            logger.info(
                                "Expiry worker processed overdue submissions",
                                event_type="expiry_worker.tick",
                                metadata={"expired_count": expired},
                            )
                    except Exception:
                        db.rollback()
                        logger.error(
                            "Expiry worker tick failed",
                            event_type="expiry_worker.error",
                            exc_info=True,
                        )
                    finally:
                        db.close()

            expiry_worker_task = asyncio.create_task(_expiry_worker_loop())
            logger.info(
                "✓ Interview expiry worker started",
                event_type="startup.expiry_worker.complete",
                metadata={
                    "interval_seconds": expiry_worker_interval,
                    "batch_size": expiry_worker_batch,
                },
            )
        else:
            logger.info(
                "Interview expiry worker disabled",
                event_type="startup.expiry_worker.skipped",
            )
        
        logger.info(
            "✅ Application startup complete",
            event_type="app.startup.complete",
            metadata={
                "environment": settings.app.app_env,
                "version": settings.app.api_version
            }
        )
        
    except Exception as e:
        logger.critical(
            f"❌ Application startup failed: {e}",
            event_type="app.startup.failed",
            exc_info=True
        )
        raise
    
    # ==================
    # APPLICATION RUNNING
    # ==================
    
    yield
    
    # ==================
    # SHUTDOWN
    # ==================
    
    logger.info("🛑 Shutting down AI Interviewer Backend", event_type="app.shutdown.begin")
    
    try:
        if expiry_worker_task is not None:
            expiry_worker_task.cancel()
            try:
                await expiry_worker_task
            except asyncio.CancelledError:
                logger.info(
                    "✓ Interview expiry worker stopped",
                    event_type="shutdown.expiry_worker.complete",
                )

        # 1. Close Azure Blob Storage
        try:
            cleanup_blob()
            logger.info("✓ Azure Blob Storage disconnected", event_type="shutdown.blob.complete")
        except Exception as e:
            logger.warning(
                f"⚠️  Azure Blob Storage disconnect warning: {e}",
                event_type="shutdown.blob.warning"
            )
        
        # 2. Close Qdrant
        try:
            cleanup_qdrant()
            logger.info("✓ Qdrant disconnected", event_type="shutdown.qdrant.complete")
        except Exception as e:
            logger.warning(
                f"⚠️  Qdrant disconnect warning: {e}",
                event_type="shutdown.qdrant.warning"
            )
        
        # 2. Close Redis
        try:
            cleanup_redis()
            logger.info("✓ Redis disconnected", event_type="shutdown.redis.complete")
        except Exception as e:
            logger.warning(
                f"⚠️  Redis disconnect warning: {e}",
                event_type="shutdown.redis.warning"
            )
        
        # 3. Close PostgreSQL
        try:
            cleanup_engine()
            logger.info("✓ PostgreSQL disconnected", event_type="shutdown.postgres.complete")
        except Exception as e:
            logger.warning(
                f"⚠️  PostgreSQL cleanup warning: {e}",
                event_type="shutdown.postgres.warning"
            )
        
        logger.info("✅ Application shutdown complete", event_type="app.shutdown.complete")
        
    except Exception as e:
        logger.error(
            f"❌ Shutdown encountered errors: {e}",
            event_type="app.shutdown.error",
            exc_info=True
        )
