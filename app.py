"""
Microsoft Graph & Gmail Email Sync Connector
=============================================
Production-grade FastAPI service that syncs Microsoft Graph and Gmail emails via Nango OAuth.

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
import nest_asyncio
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client, Client

# Import Cortex Hybrid RAG components
from cortex_backend.core.pipeline import HybridRAGPipeline
from cortex_backend.api.routers import search_llamaindex

# Import configuration
from config.settings import (
    PORT, SUPABASE_URL, SUPABASE_ANON_KEY,
    NANGO_PROVIDER_KEY_OUTLOOK, NANGO_PROVIDER_KEY_GMAIL,
    NANGO_SECRET
)

# Import services
from nango_services.sync_engine import run_gmail_sync, run_tenant_sync
from nango_services.database import get_connection, save_connection

# Import models
from routers.nango_oauth import NangoOAuthCallback
from routers.nango_webhook import NangoWebhook
from routers.sync import SyncResponse

# Enable nested asyncio for LlamaIndex/Graphiti (only if not using uvloop)
try:
    import asyncio
    loop = asyncio.get_event_loop()
    if not isinstance(loop, type(asyncio.new_event_loop())):
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

# CORS middleware
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

# Global clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
http_client: Optional[httpx.AsyncClient] = None
security = HTTPBearer()
cortex_pipeline: Optional[HybridRAGPipeline] = None


# ============================================================================
# AUTHENTICATION
# ============================================================================

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Validate Supabase JWT and extract user UUID."""
    token = credentials.credentials
    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(status_code=401, detail="Invalid authentication token")

        user_id = response.user.id
        if not user_id:
            raise HTTPException(status_code=401, detail="User ID not found in token")

        logger.debug(f"Authenticated user: {user_id}")
        return user_id
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired authentication token")


# ============================================================================
# ROUTES
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/status")
async def get_status(user_id: str = Depends(get_current_user_id)):
    """Get connection status for authenticated user."""
    try:
        outlook_connection = await get_connection(user_id, NANGO_PROVIDER_KEY_OUTLOOK) if NANGO_PROVIDER_KEY_OUTLOOK else None
        gmail_connection = await get_connection(user_id, NANGO_PROVIDER_KEY_GMAIL) if NANGO_PROVIDER_KEY_GMAIL else None

        return {
            "tenant_id": user_id,
            "providers": {
                "outlook": {
                    "configured": NANGO_PROVIDER_KEY_OUTLOOK is not None,
                    "connected": outlook_connection is not None,
                    "connection_id": outlook_connection
                },
                "gmail": {
                    "configured": NANGO_PROVIDER_KEY_GMAIL is not None,
                    "connected": gmail_connection is not None,
                    "connection_id": gmail_connection
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/connect/start")
async def connect_start(
    provider: str = Query(..., description="Provider name (microsoft or gmail)"),
    user_id: str = Depends(get_current_user_id)
):
    """Initiate OAuth flow by generating Nango OAuth URL."""
    logger.info(f"OAuth start requested for provider {provider}, user {user_id}")

    # Map provider to integration ID
    integration_id = None
    if provider.lower() in ["microsoft", "outlook"]:
        if not NANGO_PROVIDER_KEY_OUTLOOK:
            raise HTTPException(status_code=400, detail="Microsoft/Outlook provider not configured")
        integration_id = "outlook"
    elif provider.lower() == "gmail":
        if not NANGO_PROVIDER_KEY_GMAIL:
            raise HTTPException(status_code=400, detail="Gmail provider not configured")
        integration_id = "google-mail"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # Generate connect session token
    try:
        session_response = await http_client.post(
            "https://api.nango.dev/connect/sessions",
            headers={"Authorization": f"Bearer {NANGO_SECRET}"},
            json={
                "end_user": {
                    "id": user_id,
                    "email": f"{user_id}@app.internal",
                    "display_name": user_id[:8]
                },
                "allowed_integrations": [integration_id]
            }
        )
        session_response.raise_for_status()
        session_data = session_response.json()
        session_token = session_data["data"]["token"]

        logger.info(f"Generated connect session token for user {user_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to create Nango session: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to create OAuth session")
    except Exception as e:
        logger.error(f"Error creating Nango session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    redirect_uri = "https://connectorfrontend.vercel.app"
    oauth_url = f"https://api.nango.dev/oauth/connect/{integration_id}?connect_session_token={session_token}&user_scope=&callback_url={redirect_uri}"

    return {
        "auth_url": oauth_url,
        "provider": provider,
        "tenant_id": user_id
    }


@app.post("/nango/oauth/callback")
async def nango_oauth_callback(payload: NangoOAuthCallback):
    """Handle Nango OAuth callback."""
    logger.info(f"Received OAuth callback for tenant {payload.tenantId}")
    try:
        await save_connection(payload.tenantId, payload.providerConfigKey, payload.connectionId)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nango/webhook")
async def nango_webhook(
    payload: NangoWebhook,
    background_tasks: BackgroundTasks
):
    """Handle Nango webhook - triggers background sync."""
    nango_connection_id = payload.connectionId
    logger.info(f"Received Nango webhook: type={payload.type}, connection={nango_connection_id}, provider={payload.providerConfigKey}")

    # Handle auth events
    if payload.type == "auth" and payload.success:
        try:
            logger.info(f"Full webhook payload: {payload.model_dump_json()}")

            end_user_id = None
            if hasattr(payload, 'end_user') and payload.end_user:
                end_user_id = payload.end_user.get("id") if isinstance(payload.end_user, dict) else None

            if not end_user_id:
                conn_url = f"https://api.nango.dev/connection/{nango_connection_id}?provider_config_key={payload.providerConfigKey}"
                headers = {"Authorization": f"Bearer {NANGO_SECRET}"}
                response = await http_client.get(conn_url, headers=headers)
                response.raise_for_status()
                conn_data = response.json()
                end_user_id = conn_data.get("end_user", {}).get("id") if isinstance(conn_data.get("end_user"), dict) else None

            if not end_user_id:
                logger.error(f"Failed to retrieve end_user for connection {nango_connection_id}")
                return {"status": "error", "message": "Missing end_user information"}

            logger.info(f"OAuth successful for user {end_user_id}, saving connection")
            await save_connection(end_user_id, payload.providerConfigKey, nango_connection_id)
            return {"status": "connection_saved", "user": end_user_id}

        except Exception as e:
            logger.error(f"Error handling auth webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # Handle sync events
    try:
        conn_url = f"https://api.nango.dev/connection/{payload.providerConfigKey}/{nango_connection_id}"
        headers = {"Authorization": f"Bearer {NANGO_SECRET}"}
        response = await http_client.get(conn_url, headers=headers)
        response.raise_for_status()
        conn_data = response.json()
        tenant_id = conn_data.get("end_user", {}).get("id")

        if not tenant_id:
            logger.error(f"No end_user.id found for connection {nango_connection_id}")
            return {"status": "error", "message": "Missing end_user information"}

    except Exception as e:
        logger.error(f"Error fetching end_user from Nango: {e}")
        return {"status": "error", "message": str(e)}

    # Trigger background sync
    if payload.providerConfigKey == NANGO_PROVIDER_KEY_GMAIL:
        background_tasks.add_task(run_gmail_sync, http_client, supabase, cortex_pipeline, tenant_id, payload.providerConfigKey)
        logger.info(f"Triggered Gmail sync for tenant {tenant_id}")
    else:
        background_tasks.add_task(run_tenant_sync, http_client, supabase, cortex_pipeline, tenant_id, payload.providerConfigKey)
        logger.info(f"Triggered Outlook sync for tenant {tenant_id}")

    return {"status": "accepted"}


@app.get("/sync/once", response_model=SyncResponse)
async def sync_once(user_id: str = Depends(get_current_user_id)):
    """Manual Outlook sync endpoint for testing."""
    logger.info(f"Manual Outlook sync requested for user {user_id}")
    try:
        result = await run_tenant_sync(http_client, supabase, cortex_pipeline, user_id, NANGO_PROVIDER_KEY_OUTLOOK)
        return SyncResponse(
            status=result["status"],
            tenant_id=result["tenant_id"],
            users_synced=result.get("users_synced"),
            messages_synced=result["messages_synced"],
            errors=result["errors"]
        )
    except Exception as e:
        logger.error(f"Error in manual Outlook sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sync/once/gmail")
async def sync_once_gmail(
    user_id: str = Depends(get_current_user_id),
    modified_after: Optional[str] = Query(None, description="ISO datetime to filter records")
):
    """Manual Gmail sync endpoint for testing."""
    logger.info(f"Manual Gmail sync requested for user {user_id}")
    if modified_after:
        logger.info(f"Using modified_after filter: {modified_after}")

    try:
        result = await run_gmail_sync(http_client, supabase, cortex_pipeline, user_id, NANGO_PROVIDER_KEY_GMAIL, modified_after=modified_after)
        return {
            "status": result["status"],
            "tenant_id": result["tenant_id"],
            "messages_synced": result["messages_synced"],
            "errors": result["errors"]
        }
    except Exception as e:
        logger.error(f"Error in manual Gmail sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Mount Cortex search router
app.include_router(search_llamaindex.router)


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize HTTP client and Cortex pipeline on startup."""
    global http_client, cortex_pipeline

    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )
    logger.info("HTTP client initialized")

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
