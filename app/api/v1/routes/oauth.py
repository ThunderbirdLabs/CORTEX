"""
OAuth Routes
Handles OAuth flow initiation and callbacks via Nango

SECURITY:
- Rate limited to prevent OAuth abuse
- User authentication required
"""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import settings
from app.core.security import get_current_user_id
from app.core.dependencies import get_http_client
from app.models.schemas import NangoOAuthCallback
from app.services.nango import save_connection, get_connection
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["oauth"])


@router.get("/connect/start")
@limiter.limit("20/hour")  # SECURITY: Prevent OAuth abuse (20 attempts per hour)
async def connect_start(
    request: Request,  # Required for rate limiting
    provider: str = Query(..., description="Provider name (microsoft | gmail | google-drive | quickbooks)"),
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
    elif provider.lower() in ["google-drive", "drive", "googledrive"]:
        # Prefer dedicated Drive provider if configured; fall back to Gmail provider (same Google account)
        if settings.nango_provider_key_google_drive:
            integration_id = "google-drive"
        elif settings.nango_provider_key_gmail:
            # Allow connect via Gmail integration if Drive scopes are configured there
            integration_id = "google-mail"
        else:
            raise HTTPException(status_code=400, detail="Google Drive provider not configured")
    elif provider.lower() in ["quickbooks", "qbo", "intuit"]:
        logger.info(f"QuickBooks provider key value: {settings.nango_provider_key_quickbooks}")
        if not settings.nango_provider_key_quickbooks:
            raise HTTPException(status_code=400, detail="QuickBooks provider not configured. Check NANGO_PROVIDER_KEY_QUICKBOOKS env var.")
        integration_id = "quickbooks"
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
    
    Note: When using Nango's Connect SDK with end_user model, the connection_id
    for API calls is the end_user.email format: <tenant_id>@app.internal
    """
    logger.info(f"Received OAuth callback for tenant {payload.tenantId}, nango internal ID: {payload.connectionId}")
    try:
        # Use end_user.id as connection_id for API calls (Nango Connect SDK uses /connections endpoint)
        await save_connection(payload.tenantId, payload.providerConfigKey, payload.tenantId)
        logger.info(f"Saved connection with ID: {payload.tenantId}")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status(user_id: str = Depends(get_current_user_id)):
    """
    Get connection status for authenticated user.
    Shows which providers are connected and last sync time from Nango.
    """
    import httpx

    async def get_nango_connection_details(connection_id: str, provider_key: str) -> dict:
        """Fetch connection details from Nango API including last sync time."""
        if not connection_id or not provider_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                url = f"https://api.nango.dev/connection/{connection_id}?provider_config_key={provider_key}"
                headers = {"Authorization": f"Bearer {settings.nango_secret}"}
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    # Nango returns metadata with last sync info
                    return {
                        "last_sync": data.get("metadata", {}).get("last_synced_at"),
                        "email": data.get("metadata", {}).get("email"),
                        "status": data.get("credentials_status")
                    }
        except Exception as e:
            logger.warning(f"Failed to get Nango connection details: {e}")

        return None

    try:
        outlook_connection = await get_connection(user_id, settings.nango_provider_key_outlook) if settings.nango_provider_key_outlook else None
        gmail_connection = await get_connection(user_id, settings.nango_provider_key_gmail) if settings.nango_provider_key_gmail else None
        drive_connection = await get_connection(user_id, settings.nango_provider_key_google_drive) if settings.nango_provider_key_google_drive else gmail_connection
        quickbooks_connection = await get_connection(user_id, settings.nango_provider_key_quickbooks) if settings.nango_provider_key_quickbooks else None

        # Get detailed info from Nango for connected providers
        outlook_details = await get_nango_connection_details(outlook_connection, settings.nango_provider_key_outlook) if outlook_connection else None
        gmail_details = await get_nango_connection_details(gmail_connection, settings.nango_provider_key_gmail) if gmail_connection else None
        drive_details = await get_nango_connection_details(drive_connection, settings.nango_provider_key_google_drive) if drive_connection else None
        quickbooks_details = await get_nango_connection_details(quickbooks_connection, settings.nango_provider_key_quickbooks) if quickbooks_connection else None

        return {
            "tenant_id": user_id,
            "providers": {
                "outlook": {
                    "configured": settings.nango_provider_key_outlook is not None,
                    "connected": outlook_connection is not None,
                    "connection_id": outlook_connection,
                    "last_sync": outlook_details.get("last_sync") if outlook_details else None,
                    "email": outlook_details.get("email") if outlook_details else None
                },
                "gmail": {
                    "configured": settings.nango_provider_key_gmail is not None,
                    "connected": gmail_connection is not None,
                    "connection_id": gmail_connection,
                    "last_sync": gmail_details.get("last_sync") if gmail_details else None,
                    "email": gmail_details.get("email") if gmail_details else None
                },
                "google_drive": {
                    "configured": (settings.nango_provider_key_google_drive is not None) or (settings.nango_provider_key_gmail is not None),
                    "connected": drive_connection is not None,
                    "connection_id": drive_connection,
                    "last_sync": drive_details.get("last_sync") if drive_details else None
                },
                "quickbooks": {
                    "configured": settings.nango_provider_key_quickbooks is not None,
                    "connected": quickbooks_connection is not None,
                    "connection_id": quickbooks_connection,
                    "last_sync": quickbooks_details.get("last_sync") if quickbooks_details else None
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
