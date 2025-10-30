"""
Dependency Injection
Provides global clients and services to routes via FastAPI dependencies

MULTI-TENANT SUPPORT:
- master_supabase_client: Control plane (schemas, settings, companies)
- supabase_client: Company operational data (documents, jobs, oauth)
- Backward compatible: If no COMPANY_ID env var, works like before
"""
from typing import Optional, Any
import logging
import httpx
from supabase import Client, create_client

from app.core.config import settings
from app.core.config_master import master_config, is_multi_tenant

logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL CLIENTS (initialized at startup)
# ============================================================================

http_client: Optional[httpx.AsyncClient] = None

# Multi-tenant: Dual Supabase support
master_supabase_client: Optional[Client] = None  # Master control plane (NEW!)
supabase_client: Optional[Client] = None  # Company operational data (EXISTING)

rag_pipeline: Optional[Any] = None  # UniversalIngestionPipeline instance
query_engine: Optional[Any] = None  # HybridQueryEngine instance


# ============================================================================
# DEPENDENCY FUNCTIONS
# ============================================================================

async def get_http_client() -> httpx.AsyncClient:
    """Get global HTTP client."""
    if not http_client:
        raise RuntimeError("HTTP client not initialized")
    return http_client


async def get_supabase() -> Client:
    """
    Get company Supabase client (operational data: documents, jobs, oauth).
    BACKWARD COMPATIBLE: Works for both single-tenant and multi-tenant mode.
    """
    if not supabase_client:
        raise RuntimeError("Supabase client not initialized")
    return supabase_client


async def get_master_supabase() -> Client:
    """
    Get master Supabase client (control plane: schemas, settings, companies).
    MULTI-TENANT ONLY: Returns None in single-tenant mode for backward compatibility.
    """
    if not is_multi_tenant():
        # Single-tenant mode: return company Supabase (backward compatible)
        logger.debug("Single-tenant mode: get_master_supabase() returns company Supabase")
        return await get_supabase()

    if not master_supabase_client:
        raise RuntimeError("Master Supabase client not initialized (multi-tenant mode)")

    return master_supabase_client


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
    global http_client, master_supabase_client, supabase_client, rag_pipeline, query_engine

    # HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )

    # Multi-tenant mode: Initialize master Supabase
    if is_multi_tenant():
        logger.info("🏢 Initializing MULTI-TENANT mode...")

        # Master Supabase (control plane)
        master_supabase_client = create_client(
            master_config.master_supabase_url,
            master_config.master_supabase_service_key
        )
        logger.info(f"✅ Master Supabase connected (Company ID: {master_config.company_id})")

        # Company Supabase (operational data)
        supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
        logger.info(f"✅ Company Supabase connected")

    else:
        # Single-tenant mode (backward compatible)
        logger.info("🏠 Initializing SINGLE-TENANT mode (backward compatible)...")
        supabase_client = create_client(settings.supabase_url, settings.supabase_anon_key)
        logger.info("✅ Supabase connected")

    # Database Indexes (ensure indexes exist before querying - production autopilot)
    try:
        from app.services.ingestion.llamaindex.index_manager import ensure_neo4j_indexes, ensure_qdrant_indexes
        logger.info("🔍 Ensuring database indexes exist...")
        await ensure_neo4j_indexes()
        await ensure_qdrant_indexes()
        logger.info("✅ Database indexes configured (Neo4j + Qdrant)")
    except Exception as e:
        logger.warning(f"⚠️  Failed to create database indexes: {e}")
        logger.warning("   Queries may be slow without indexes!")

    # RAG Pipeline (lazy import to avoid circular dependencies)
    try:
        from app.services.ingestion.llamaindex import UniversalIngestionPipeline
        rag_pipeline = UniversalIngestionPipeline()
        logger.info("✅ RAG pipeline initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize RAG pipeline: {e}")
        logger.warning(f"   This is OK - pipeline will initialize on first use")
        rag_pipeline = None

    # Query Engine (initialize at startup to avoid first-query stall)
    # CRITICAL: Pre-loads reranker model (600MB) to prevent 2+ minute delay on first query
    try:
        from app.services.ingestion.llamaindex import HybridQueryEngine
        query_engine = HybridQueryEngine()
        logger.info("✅ Query engine initialized successfully (reranker model loaded)")
    except Exception as e:
        logger.warning(f"⚠️  Failed to initialize query engine: {e}")
        logger.warning(f"   This is OK - query engine will initialize on first use")
        query_engine = None


async def shutdown_clients():
    """Cleanup clients at shutdown."""
    global http_client, query_engine

    # Close HTTP client to prevent socket exhaustion
    if http_client:
        await http_client.aclose()
        logger.info("✅ HTTP client closed")

    # Cleanup query engine connections (Neo4j/Qdrant)
    # This is the main production resource that needs cleanup
    if query_engine:
        try:
            await query_engine.cleanup()
            logger.info("✅ Query engine connections closed")
        except Exception as e:
            logger.warning(f"⚠️  Failed to cleanup query engine: {e}")
