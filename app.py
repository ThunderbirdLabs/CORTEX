"""
Microsoft Graph & Gmail Email Sync Connector
=============================================
Production-grade FastAPI service that syncs Microsoft Graph and Gmail emails via Nango OAuth.

RUN STEPS:
1. pip install -r requirements.txt
2. Create database with schema.sql
3. Set environment variables (see .env.example)
4. Run: uvicorn app:app --host 0.0.0.0 --port $PORT

ROUTES:
- POST /nango/oauth/callback - Saves tenant connection from Nango
- POST /nango/webhook - Triggers background sync on Nango events (Outlook or Gmail)
- GET /sync/once - Manual Outlook sync endpoint for testing
- GET /sync/once/gmail - Manual Gmail sync endpoint for testing
- POST /api/search-optimized - Hybrid RAG search endpoint (Cortex)
"""

import logging
from typing import Optional

import httpx
import jwt
import nest_asyncio
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client, Client

# Import Cortex Hybrid RAG components
from cortex_backend.core.pipeline import HybridRAGPipeline
from cortex_backend.api.routers import search_llamaindex

# Import configuration
from config.settings import PORT, SUPABASE_URL, SUPABASE_ANON_KEY, NANGO_PROVIDER_KEY_OUTLOOK, NANGO_PROVIDER_KEY_GMAIL

# Import services and routers
from nango_services.sync_engine import run_gmail_sync, run_tenant_sync
from nango_services.database import get_connection
from routers.nango_oauth import NangoOAuthCallback
from routers.nango_webhook import NangoWebhook
from routers.sync import SyncResponse

# Enable nested asyncio for LlamaIndex/Graphiti (only if not using uvloop)
try:
    import asyncio
    loop = asyncio.get_event_loop()
    if not isinstance(loop, type(asyncio.new_event_loop())):
        # Only apply if not already using uvloop
        pass
except:
    nest_asyncio.apply()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="Microsoft Graph & Gmail Email Sync Connector")

# CORS middleware - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://connectorfrontend.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# HTTP client with retry configuration
http_client: Optional[httpx.AsyncClient] = None

# Security
security = HTTPBearer()

# Cortex Hybrid RAG Pipeline (initialized on startup)
cortex_pipeline: Optional[HybridRAGPipeline] = None


# ============================================================================
# AUTHENTICATION
# ============================================================================

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Validate Supabase JWT and extract user UUID.

    Args:
        credentials: HTTP Bearer token from Authorization header

    Returns:
        User's UUID from Supabase auth (used as tenant_id)

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    try:
        # Verify JWT using Supabase client
        response = supabase.auth.get_user(token)

        if not response or not response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )

        user = response.user
        user_id = user.id

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID not found in token"
            )

        logger.debug(f"Authenticated user: {user_id} ({user.email})")
        return user_id

    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )


# ============================================================================
# ROUTES - Using imported logic from routers/
# ============================================================================

# Import route handlers
from routers.nango_oauth import nango_oauth_callback
from routers.nango_webhook import nango_webhook
from routers.status import health_check

# Mount simple routes directly
app.post("/nango/oauth/callback")(nango_oauth_callback)
app.get("/health")(health_check)

# Routes that need global state injected
@app.get("/connect/start")
async def connect_start(
    provider: str = Query(..., description="Provider name (microsoft or gmail)"),
    user_id: str = Depends(get_current_user_id)
):
    """Initiate OAuth flow - delegates to router logic."""
    from routers.nango_oauth import connect_start as oauth_connect_start
    return await oauth_connect_start(provider, user_id, http_client)


@app.post("/nango/webhook")
async def webhook_handler(
    payload: NangoWebhook,
    background_tasks: BackgroundTasks
):
    """Handle Nango webhook - delegates to router logic."""
    return await nango_webhook(payload, background_tasks, http_client, supabase, cortex_pipeline)


@app.get("/sync/once", response_model=SyncResponse)
async def sync_once_route(user_id: str = Depends(get_current_user_id)):
    """Manual Outlook sync - delegates to router logic."""
    from routers.sync import sync_once
    return await sync_once(user_id, http_client, supabase, cortex_pipeline)


@app.get("/sync/once/gmail")
async def sync_once_gmail_route(
    user_id: str = Depends(get_current_user_id),
    modified_after: Optional[str] = Query(None, description="ISO datetime to filter records")
):
    """Manual Gmail sync - delegates to router logic."""
    from routers.sync import sync_once_gmail
    return await sync_once_gmail(user_id, http_client, supabase, cortex_pipeline, modified_after)


@app.get("/status")
async def status_route(user_id: str = Depends(get_current_user_id)):
    """Get connection status - delegates to router logic."""
    from routers.status import get_status
    return await get_status(user_id)


# Mount Cortex search router (already self-contained)
app.include_router(search_llamaindex.router)


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize HTTP client and Cortex pipeline on startup."""
    global http_client, cortex_pipeline

    # Initialize HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )
    logger.info("HTTP client initialized")

    # Initialize Cortex Hybrid RAG Pipeline
    try:
        cortex_pipeline = HybridRAGPipeline()
        logger.info("Cortex Hybrid RAG Pipeline initialized")
        logger.info("  - Vector DB: Qdrant")
        logger.info("  - Knowledge Graph: Neo4j + Graphiti")
    except Exception as e:
        logger.error(f"Failed to initialize Cortex pipeline: {e}")
        logger.warning("Cortex ingestion will be disabled")
        cortex_pipeline = None

    logger.info("FastAPI application started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup HTTP client on shutdown."""
    if http_client:
        await http_client.aclose()
    logger.info("FastAPI application shutdown")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info"
    )
