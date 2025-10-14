"""
OAuth Routes
Handles OAuth flow initiation and callbacks via Nango
"""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.config import settings
from app.core.security import get_current_user_id
from app.core.dependencies import get_http_client
from app.models.schemas import NangoOAuthCallback
from app.services.nango import save_connection, get_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["oauth"])


@router.get("/connect/start")
async def connect_start(
    provider: str = Query(..., description="Provider name (microsoft or gmail)"),
    user_id: str = Depends(get_current_user_id),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """
    Initiate OAuth flow by generating Nango OAuth URL.
    
    Flow:
    1. User clicks "Connect Gmail" or "Connect Outlook"
    2. Frontend calls this endpoint
    3. We generate a Nango Connect session token
    4. Frontend redirects user to Nango OAuth URL
    5. User completes OAuth
    6. Nango webhook fires (handled by /nango/webhook)
    """
    logger.info(f"OAuth start requested for provider {provider}, user {user_id}")

    # Map provider to integration ID
    integration_id = None
    if provider.lower() in ["microsoft", "outlook"]:
        if not settings.nango_provider_key_outlook:
            raise HTTPException(status_code=400, detail="Microsoft/Outlook provider not configured")
        integration_id = "outlook"
    elif provider.lower() == "gmail":
        if not settings.nango_provider_key_gmail:
            raise HTTPException(status_code=400, detail="Gmail provider not configured")
        integration_id = "google-mail"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # Generate connect session token
    try:
        session_response = await http_client.post(
            "https://api.nango.dev/connect/sessions",
            headers={"Authorization": f"Bearer {settings.nango_secret}"},
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


@router.post("/nango/oauth/callback")
async def nango_oauth_callback(payload: NangoOAuthCallback):
    """
    Handle Nango OAuth callback.
    Saves connection information for the tenant.
    """
    logger.info(f"Received OAuth callback for tenant {payload.tenantId}")
    try:
        await save_connection(payload.tenantId, payload.providerConfigKey, payload.connectionId)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status(user_id: str = Depends(get_current_user_id)):
    """
    Get connection status for authenticated user.
    Shows which providers are connected.
    """
    try:
        outlook_connection = await get_connection(user_id, settings.nango_provider_key_outlook) if settings.nango_provider_key_outlook else None
        gmail_connection = await get_connection(user_id, settings.nango_provider_key_gmail) if settings.nango_provider_key_gmail else None

        return {
            "tenant_id": user_id,
            "providers": {
                "outlook": {
                    "configured": settings.nango_provider_key_outlook is not None,
                    "connected": outlook_connection is not None,
                    "connection_id": outlook_connection
                },
                "gmail": {
                    "configured": settings.nango_provider_key_gmail is not None,
                    "connected": gmail_connection is not None,
                    "connection_id": gmail_connection
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
