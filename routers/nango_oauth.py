"""
Nango OAuth routes
Handles OAuth flow initiation and callbacks
"""
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from nango_services.database import save_connection
from config.settings import (
    NANGO_SECRET,
    NANGO_PROVIDER_KEY_OUTLOOK,
    NANGO_PROVIDER_KEY_GMAIL
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["oauth"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NangoOAuthCallback(BaseModel):
    """Nango OAuth callback payload."""
    tenantId: str
    providerConfigKey: str
    connectionId: str


# ============================================================================
# OAUTH ROUTES
# ============================================================================

@router.get("/connect/start")
async def connect_start(
    provider: str,
    user_id: str,
    http_client: httpx.AsyncClient
):
    """
    Initiate OAuth flow by generating Nango OAuth URL with connect session token.
    Returns the authorization URL that frontend should redirect to.

    Args:
        provider: Provider name (microsoft or gmail)
        user_id: Authenticated user ID from Supabase JWT
        http_client: Global async HTTP client
    """
    logger.info(f"OAuth start requested for provider {provider}, user {user_id}")

    # Map provider name to Nango integration ID
    integration_id = None
    if provider.lower() in ["microsoft", "outlook"]:
        if not NANGO_PROVIDER_KEY_OUTLOOK:
            raise HTTPException(status_code=400, detail="Microsoft/Outlook provider not configured")
        integration_id = "outlook"
    elif provider.lower() == "gmail":
        if not NANGO_PROVIDER_KEY_GMAIL:
            raise HTTPException(status_code=400, detail="Gmail provider not configured")
        integration_id = "google-mail"  # Actual Nango integration ID
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # Generate connect session token from Nango
    try:
        session_response = await http_client.post(
            "https://api.nango.dev/connect/sessions",
            headers={"Authorization": f"Bearer {NANGO_SECRET}"},
            json={
                "end_user": {
                    "id": user_id,  # Use Supabase UUID
                    "email": f"{user_id}@app.internal",  # Placeholder email (not used)
                    "display_name": user_id[:8]  # First 8 chars of UUID
                },
                "allowed_integrations": [integration_id]
            }
        )
        session_response.raise_for_status()
        session_data = session_response.json()
        session_token = session_data["data"]["token"]  # Access nested data.token field

        logger.info(f"Generated connect session token for user {user_id} with integration {integration_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to create Nango session: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to create OAuth session")
    except Exception as e:
        logger.error(f"Error creating Nango session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Generate Nango OAuth URL with session token and redirect
    # After OAuth, Nango will redirect user back to the frontend
    redirect_uri = "https://connectorfrontend.vercel.app"
    oauth_url = f"https://api.nango.dev/oauth/connect/{integration_id}?connect_session_token={session_token}&user_scope=&callback_url={redirect_uri}"

    logger.info(f"Generated OAuth URL for {provider}: {oauth_url}")

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
        await save_connection(
            payload.tenantId,
            payload.providerConfigKey,
            payload.connectionId
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
