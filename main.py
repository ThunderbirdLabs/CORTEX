"""
Unified Email Connector & RAG Search Backend
=============================================
Enterprise-grade FastAPI application combining:
- Email sync (Gmail/Outlook via Nango OAuth)
- Hybrid RAG search (Vector DB + Knowledge Graph)

Architecture:
- app/core/: Configuration, dependencies, security
- app/middleware/: Error handling, logging, CORS
- app/models/: Pydantic schemas
- app/services/: Business logic (connectors, nango, ingestion, search)
- app/api/v1/routes/: API endpoints

Author: Nicolas Codet
Version: 0.3.0
"""
import sys
import logging
import traceback
import nest_asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Startup error handling
try:
    # Import core components
    from app.core.config import settings
    from app.core.dependencies import initialize_clients, shutdown_clients

    # Import middleware
    from app.middleware.error_handler import ErrorHandlerMiddleware
    from app.middleware.logging import RequestLoggingMiddleware
    from app.middleware.cors import get_cors_middleware

    # Import routes
    from app.api.v1.routes import (
        health_router,
        oauth_router,
        webhook_router,
        sync_router,
        search_router,
        emails_router,
        upload_router,
        chat_router
    )
    from app.api.v1.routes.deduplication import router as deduplication_router

    # Import deduplication service for scheduled job
    from app.services.deduplication.entity_deduplication import run_entity_deduplication
except Exception as e:
    print(f"🚨 FATAL STARTUP ERROR: {e}", file=sys.stderr)
    print(f"Traceback:\n{traceback.format_exc()}", file=sys.stderr)
    sys.exit(1)

# Enable nested asyncio for LlamaIndex/Graphiti compatibility
try:
    import asyncio
    loop = asyncio.get_event_loop()
    if not isinstance(loop, type(asyncio.new_event_loop())):
        pass
except Exception as e:
    print(f"Applying nest_asyncio: {e}")
    nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.environment == "production" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# SENTRY ERROR TRACKING
# ============================================================================

if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=0.1,  # 10% of requests for performance monitoring
            profiles_sample_rate=0.1,
            integrations=[
                FastApiIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
            ]
        )
        logger.info("✅ Sentry error tracking initialized")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize Sentry: {e}")
else:
    logger.info("ℹ️  Sentry not configured (SENTRY_DSN not set)")

# ============================================================================
# SCHEDULER SETUP
# ============================================================================

scheduler = AsyncIOScheduler()


async def periodic_entity_deduplication():
    """Run entity deduplication periodically."""
    if not settings.dedup_enabled:
        logger.debug("Entity deduplication is disabled")
        return

    logger.info("⏰ Running scheduled entity deduplication...")

    try:
        results = run_entity_deduplication(
            neo4j_uri=settings.neo4j_uri,
            neo4j_password=settings.neo4j_password,
            dry_run=False,
            similarity_threshold=settings.dedup_similarity_threshold,
            levenshtein_max_distance=settings.dedup_levenshtein_max_distance
        )

        merged_count = results.get("entities_merged", 0)
        logger.info(f"✅ Scheduled deduplication complete: {merged_count} entities merged")

        # Alert if high merge count
        if merged_count > 100:
            logger.error(f"🚨 ALERT: High merge count - {merged_count} entities merged! Review thresholds.")

    except Exception as e:
        logger.error(f"❌ Scheduled deduplication failed: {e}", exc_info=True)


# ============================================================================
# LIFECYCLE MANAGEMENT
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown."""
    # Startup
    logger.info("=" * 80)
    logger.info("Starting Email Connector & RAG Search Backend")
    logger.info("=" * 80)
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"Debug: {settings.debug}")

    await initialize_clients()

    # Start deduplication scheduler
    if settings.dedup_enabled:
        scheduler.add_job(
            periodic_entity_deduplication,
            'interval',
            hours=settings.dedup_interval_hours,
            id='entity_deduplication',
            replace_existing=True
        )
        scheduler.start()
        logger.info(f"✅ Entity deduplication scheduler started (every {settings.dedup_interval_hours} hour(s))")
        logger.info(f"   Similarity threshold: {settings.dedup_similarity_threshold}")
        logger.info(f"   Levenshtein max distance: {settings.dedup_levenshtein_max_distance}")
    else:
        logger.info("⚠️ Entity deduplication is disabled")

    logger.info("=" * 80)
    logger.info("✅ Application started successfully")
    logger.info("=" * 80)

    yield

    # Shutdown
    logger.info("Shutting down application...")

    # Stop scheduler
    if settings.dedup_enabled and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("✅ Deduplication scheduler stopped")

    await shutdown_clients()
    logger.info("✅ Application shutdown complete")


# ============================================================================
# APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="Email Connector & RAG Search API",
    description="Unified backend for email sync (Gmail/Outlook) and hybrid RAG search",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# ============================================================================
# RATE LIMITING
# ============================================================================

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.middleware.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
logger.info("✅ Rate limiting enabled")

# ============================================================================
# MIDDLEWARE
# ============================================================================

# CORS (must be first)
cors_middleware, cors_config = get_cors_middleware()
app.add_middleware(cors_middleware, **cors_config)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Global error handler (must be last)
app.add_middleware(ErrorHandlerMiddleware)

# ============================================================================
# ROUTES
# ============================================================================

app.include_router(health_router)
app.include_router(oauth_router)
app.include_router(webhook_router)
app.include_router(sync_router)
app.include_router(search_router)
app.include_router(emails_router)
app.include_router(upload_router)
app.include_router(chat_router)
app.include_router(deduplication_router)

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
