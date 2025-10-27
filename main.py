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
# PERIODIC TASKS (Handled by Dramatiq scheduler in separate process)
# ============================================================================
# Entity deduplication runs every 15 minutes via Dramatiq
# See: app/services/background/scheduler.py
# Run with: python -m app.services.background.scheduler


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

    # Periodic tasks (entity deduplication) run in separate Dramatiq scheduler process
    if settings.dedup_enabled:
        logger.info("✅ Entity deduplication: Enabled (runs every 15 min via Dramatiq)")
        logger.info(f"   Similarity threshold: {settings.dedup_similarity_threshold}")
        logger.info(f"   Levenshtein max distance: {settings.dedup_levenshtein_max_distance}")
    else:
        logger.info("⚠️ Entity deduplication: Disabled")

    logger.info("=" * 80)
    logger.info("✅ Application started successfully")
    logger.info("=" * 80)

    yield

    # Shutdown
    logger.info("Shutting down application...")

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

# Security headers (must be first to apply to all responses)
from app.middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)
logger.info("✅ Security headers enabled")

# CORS (after security headers)
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
# SENTRY DEBUG ENDPOINT (DEV/STAGING ONLY)
# ============================================================================

# SECURITY: Only expose debug endpoint in non-production environments
if settings.environment != "production":
    @app.get("/sentry-debug")
    async def trigger_sentry_error():
        """
        Test endpoint to verify Sentry error tracking is working.
        Triggers a division by zero error that gets captured by Sentry.

        SECURITY: Only available in dev/staging (disabled in production)
        """
        division_by_zero = 1 / 0
        return {"should": "never reach here"}

    logger.info("⚠️  DEV MODE: Sentry debug endpoint enabled at /sentry-debug")
else:
    logger.info("✅ PRODUCTION: Sentry debug endpoint disabled")

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
