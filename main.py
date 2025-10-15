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
Version: 1.0.0
"""
import logging
import nest_asyncio
from fastapi import FastAPI

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
    emails_router
)

# Enable nested asyncio for LlamaIndex/Graphiti compatibility
try:
    import asyncio
    loop = asyncio.get_event_loop()
    if not isinstance(loop, type(asyncio.new_event_loop())):
        pass
except:
    nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.environment == "production" else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="Email Connector & RAG Search API",
    description="Unified backend for email sync (Gmail/Outlook) and hybrid RAG search",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,  # Disable docs in production
    redoc_url="/redoc" if settings.debug else None
)

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

# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize all global clients and services."""
    logger.info("=" * 80)
    logger.info("Starting Email Connector & RAG Search Backend")
    logger.info("=" * 80)
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Port: {settings.port}")
    logger.info(f"Debug: {settings.debug}")
    
    # Initialize clients (HTTP, Supabase, RAG Pipeline)
    await initialize_clients()
    
    logger.info("=" * 80)
    logger.info("✅ Application started successfully")
    logger.info("=" * 80)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup all global clients."""
    logger.info("Shutting down application...")
    await shutdown_clients()
    logger.info("✅ Application shutdown complete")


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
