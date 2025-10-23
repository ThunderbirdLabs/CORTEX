"""
Dependency Injection
Provides global clients and services to routes via FastAPI dependencies
"""
from typing import Optional, Any
import logging
import httpx
from supabase import Client, create_client

from app.core.config import settings

logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL CLIENTS (initialized at startup)
# ============================================================================

http_client: Optional[httpx.AsyncClient] = None
supabase_client: Optional[Client] = None
rag_pipeline: Optional[Any] = None  # UniversalIngestionPipeline instance


# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

async def get_http_client() -> httpx.AsyncClient:
    """Get global HTTP client."""
    if not http_client:
        raise RuntimeError("HTTP client not initialized")
    return http_client


async def get_supabase() -> Client:
    """Get Supabase client."""
    if not supabase_client:
        raise RuntimeError("Supabase client not initialized")
    return supabase_client


async def get_rag_pipeline():
    """Get RAG pipeline instance."""
    return rag_pipeline  # Can be None if not initialized


# Alias for consistency (some routes use get_cortex_pipeline)
async def get_cortex_pipeline():
    """Get Cortex pipeline instance (alias for get_rag_pipeline)."""
    return rag_pipeline


# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================

async def initialize_clients():
    """Initialize all global clients at startup."""
    global http_client, supabase_client, rag_pipeline

    # HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )

    # Supabase client
    supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)

    # RAG Pipeline (lazy import to avoid circular dependencies)
    # Initialize lazily on first use instead of at startup
    # This prevents startup failures if Neo4j/Qdrant are temporarily unavailable
    try:
        from app.services.ingestion.llamaindex import UniversalIngestionPipeline
        rag_pipeline = UniversalIngestionPipeline()
        logger.info("✅ RAG pipeline initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize RAG pipeline: {e}")
        logger.warning(f"   This is OK - pipeline will initialize on first use")
        logger.warning(f"   Common causes: Neo4j/Qdrant connection issues, missing env vars")
        rag_pipeline = None


async def shutdown_clients():
    """Cleanup clients at shutdown."""
    global http_client

    if http_client:
        await http_client.aclose()
