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
from app.core.security import get_current_user_id, get_current_user_context
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
    user_context: dict = Depends(get_current_user_context),
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

    SECURITY: Uses get_current_user_context to get BOTH user_id and company_id.
    user_id is passed to Nango as endUserId for per-user connection tracking.
    """
    user_id = user_context["user_id"]
    company_id = user_context["company_id"]
    logger.info(f"OAuth start requested for provider {provider}, user {user_id}, company {company_id}")

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
    # CRITICAL: Use actual user_id (not company_id) as Nango endUserId
    # This enables per-user OAuth connections and proper attribution
    try:
        # Get user email from JWT if available
        from app.core.config_master import MasterConfig
        master_config = MasterConfig()
        user_email = f"{user_id}@{company_id[:8]}.internal"  # Placeholder, will be overwritten by actual email

        # If we're in multi-tenant mode, try to get real email
        if master_config.is_multi_tenant:
            try:
                from supabase import create_client
                master_supabase = create_client(
                    master_config.master_supabase_url,
                    master_config.master_supabase_service_key
                )
                company_user = master_supabase.table("company_users")\
                    .select("email")\
                    .eq("user_id", user_id)\
                    .eq("company_id", company_id)\
                    .maybe_single()\
                    .execute()

                if company_user.data:
                    user_email = company_user.data["email"]
            except Exception as e:
                logger.warning(f"Could not fetch user email: {e}")

        session_response = await http_client.post(
            "https://api.nango.dev/connect/sessions",
            headers={"Authorization": f"Bearer {settings.nango_secret}"},
            json={
                "end_user": {
                    "id": user_id,          # Actual user ID (not company!)
                    "email": user_email,     # User's real email
                    "display_name": user_email.split("@")[0],
                    "organization_id": company_id,  # Company in metadata
                    "organization_display_name": f"Company {company_id[:8]}"
                },
                "allowed_integrations": [integration_id]
            }
        )
        session_response.raise_for_status()
        session_data = session_response.json()
        session_token = session_data["data"]["token"]

        logger.info(f"Generated connect session token for user {user_id} in company {company_id}")
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
        "tenant_id": company_id,  # For backward compat
        "user_id": user_id,       # NEW: return user_id
        "company_id": company_id  # NEW: return company_id explicitly
    }


@router.post("/nango/oauth/callback")
async def nango_oauth_callback(payload: NangoOAuthCallback):
    """
    Handle Nango OAuth callback.
    Saves connection information for the tenant.

    Note: When using Nango's Connect SDK with end_user model, the connection_id
    for API calls is the end_user.email format: <tenant_id>@app.internal
    """
    from app.core.config_master import master_config

    logger.info(f"Received OAuth callback for tenant {payload.tenantId}, nango internal ID: {payload.connectionId}")
    try:
        # Use end_user.id as connection_id for API calls (Nango Connect SDK uses /connections endpoint)
        await save_connection(payload.tenantId, payload.providerConfigKey, payload.tenantId)
        logger.info(f"Saved connection with ID: {payload.tenantId}")

        # Save to nango_original_connections if multi-tenant and first connection
        if master_config.is_multi_tenant:
            from supabase import create_client
            master_supabase = create_client(
                master_config.master_supabase_url,
                master_config.master_supabase_service_key
            )
            company_id = master_config.company_id

            # Check if connection already exists
            existing = master_supabase.table("nango_original_connections")\
                .select("id")\
                .eq("company_id", company_id)\
                .eq("tenant_id", payload.tenantId)\
                .eq("provider", payload.providerConfigKey)\
                .maybe_single()\
                .execute()

            if not existing.data:
                # First time connection - save original email
                # Note: We should get email from Nango metadata, but for now store connection
                master_supabase.table("nango_original_connections").insert({
                    "company_id": company_id,
                    "tenant_id": payload.tenantId,
                    "provider": payload.providerConfigKey,
                    "nango_connection_id": payload.connectionId,
                    "original_email": f"{payload.tenantId}@temp.internal",  # TODO: Get real email from Nango
                    "connected_by": "client_app"
                }).execute()

                logger.info(f"Saved original connection for {payload.providerConfigKey}:{payload.tenantId}")

                # Log to audit
                master_supabase.table("audit_log_global").insert({
                    "company_id": company_id,
                    "action": "connection_created",
                    "resource_type": "connection",
                    "resource_id": f"{payload.providerConfigKey}:{payload.tenantId}",
                    "details": {
                        "provider": payload.providerConfigKey,
                        "tenant_id": payload.tenantId,
                        "nango_connection_id": payload.connectionId
                    }
                }).execute()
            else:
                # Reconnection - update last_reconnected_at
                master_supabase.table("nango_original_connections")\
                    .update({
                        "last_reconnected_at": "now()",
                        "reconnection_count": master_supabase.table("nango_original_connections").select("reconnection_count").eq("id", existing.data["id"]).single().execute().data["reconnection_count"] + 1
                    })\
                    .eq("id", existing.data["id"])\
                    .execute()

                # Log to audit
                master_supabase.table("audit_log_global").insert({
                    "company_id": company_id,
                    "action": "connection_reconnected",
                    "resource_type": "connection",
                    "resource_id": f"{payload.providerConfigKey}:{payload.tenantId}",
                    "details": {
                        "provider": payload.providerConfigKey,
                        "tenant_id": payload.tenantId,
                        "nango_connection_id": payload.connectionId
                    }
                }).execute()

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/connect/reconnect")
@limiter.limit("20/hour")
async def reconnect_oauth(
    request: Request,
    provider: str = Query(..., description="Provider name (microsoft | gmail | google-drive | quickbooks)"),
    user_context: dict = Depends(get_current_user_context),
    http_client: httpx.AsyncClient = Depends(get_http_client)
):
    """
    Reconnect an existing OAuth connection.

    Enforces same-email policy by checking nango_original_connections table.
    Used when:
    - OAuth token expired
    - Connection is in error state
    - User needs to re-authorize after permissions change

    Flow:
    1. Check if original connection exists in master Supabase
    2. Generate new OAuth URL with login_hint for same email
    3. User completes OAuth (must match original email)
    4. Log reconnection to audit trail
    """
    from app.core.config_master import master_config
    from app.core.dependencies import get_master_supabase_client
    from fastapi import Depends as DependsReconnect

    user_id = user_context["user_id"]
    company_id_from_context = user_context["company_id"]

    logger.info(f"OAuth reconnect requested for provider {provider}, user {user_id}, company {company_id_from_context}")

    # Get master Supabase client if multi-tenant
    master_supabase = None
    original_email = None
    company_id = None

    if master_config.is_multi_tenant:
        from supabase import create_client
        master_supabase = create_client(
            master_config.master_supabase_url,
            master_config.master_supabase_service_key
        )
        company_id = master_config.company_id

        # Check for original connection
        result = master_supabase.table("nango_original_connections")\
            .select("original_email")\
            .eq("company_id", company_id)\
            .eq("tenant_id", user_id)\
            .eq("provider", provider)\
            .maybe_single()\
            .execute()

        if result.data:
            original_email = result.data["original_email"]
            logger.info(f"Found original connection with email: {original_email}")

    # Map provider to integration ID (same logic as connect_start)
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
        if settings.nango_provider_key_google_drive:
            integration_id = "google-drive"
        elif settings.nango_provider_key_gmail:
            integration_id = "google-mail"
        else:
            raise HTTPException(status_code=400, detail="Google Drive provider not configured")
    elif provider.lower() in ["quickbooks", "qbo", "intuit"]:
        if not settings.nango_provider_key_quickbooks:
            raise HTTPException(status_code=400, detail="QuickBooks provider not configured")
        integration_id = "quickbooks"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # Generate connect session token (same as connect_start)
    try:
        session_payload = {
            "end_user": {
                "id": user_id,
                "email": f"{user_id}@app.internal",
                "display_name": user_id[:8]
            },
            "allowed_integrations": [integration_id]
        }

        # Add login_hint if we have original email (helps enforce same-email)
        if original_email:
            session_payload["metadata"] = {
                "login_hint": original_email,
                "is_reconnect": True
            }

        session_response = await http_client.post(
            "https://api.nango.dev/connect/sessions",
            headers={"Authorization": f"Bearer {settings.nango_secret}"},
            json=session_payload
        )
        session_response.raise_for_status()
        session_data = session_response.json()
        session_token = session_data["data"]["token"]

        logger.info(f"Generated reconnect session token for user {user_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to create Nango reconnect session: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to create OAuth reconnect session")
    except Exception as e:
        logger.error(f"Error creating Nango reconnect session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    redirect_uri = "https://connectorfrontend.vercel.app"
    oauth_url = f"https://api.nango.dev/oauth/connect/{integration_id}?connect_session_token={session_token}&user_scope=&callback_url={redirect_uri}"

    if original_email:
        oauth_url += f"&login_hint={original_email}"

    # Log reconnection attempt to audit log
    if master_supabase and company_id:
        try:
            master_supabase.table("audit_log_global").insert({
                "company_id": company_id,
                "action": "connection_reconnect_initiated",
                "resource_type": "connection",
                "resource_id": f"{provider}:{user_id}",
                "details": {
                    "provider": provider,
                    "tenant_id": user_id,
                    "original_email": original_email,
                    "initiated_by": "client_app"
                }
            }).execute()
        except Exception as e:
            logger.warning(f"Failed to log reconnect to audit: {e}")

    return {
        "auth_url": oauth_url,
        "provider": provider,
        "tenant_id": user_id,
        "original_email": original_email,
        "message": f"Please reconnect using the same email: {original_email}" if original_email else "Please reconnect your account"
    }


@router.get("/status")
async def get_status(user_id: str = Depends(get_current_user_id)):
    """
    Get connection status for authenticated user.
    Shows which providers are connected, last sync time from Nango, and sync lock status.
    """
    import httpx
    from app.core.dependencies import get_supabase
    from fastapi import Depends as StatusDepends

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

        # Get sync lock status from connections table
        from supabase import create_client
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)

        sync_status = {}
        for provider_key in ["outlook", "gmail", "google_drive", "quickbooks"]:
            try:
                result = supabase.table("connections")\
                    .select("can_manual_sync, initial_sync_completed, initial_sync_started_at")\
                    .eq("tenant_id", user_id)\
                    .eq("provider_key", provider_key)\
                    .maybe_single()\
                    .execute()

                if result.data:
                    sync_status[provider_key] = {
                        "can_manual_sync": result.data.get("can_manual_sync", True),
                        "initial_sync_completed": result.data.get("initial_sync_completed", False),
                        "initial_sync_started_at": result.data.get("initial_sync_started_at")
                    }
                else:
                    # No record yet, default to allowing sync
                    sync_status[provider_key] = {
                        "can_manual_sync": True,
                        "initial_sync_completed": False,
                        "initial_sync_started_at": None
                    }
            except Exception as e:
                logger.warning(f"Failed to get sync status for {provider_key}: {e}")
                sync_status[provider_key] = {
                    "can_manual_sync": True,
                    "initial_sync_completed": False,
                    "initial_sync_started_at": None
                }

        return {
            "tenant_id": user_id,
            "providers": {
                "outlook": {
                    "configured": settings.nango_provider_key_outlook is not None,
                    "connected": outlook_connection is not None,
                    "connection_id": outlook_connection,
                    "last_sync": outlook_details.get("last_sync") if outlook_details else None,
                    "email": outlook_details.get("email") if outlook_details else None,
                    "can_manual_sync": sync_status.get("outlook", {}).get("can_manual_sync", True),
                    "initial_sync_completed": sync_status.get("outlook", {}).get("initial_sync_completed", False)
                },
                "gmail": {
                    "configured": settings.nango_provider_key_gmail is not None,
                    "connected": gmail_connection is not None,
                    "connection_id": gmail_connection,
                    "last_sync": gmail_details.get("last_sync") if gmail_details else None,
                    "email": gmail_details.get("email") if gmail_details else None,
                    "can_manual_sync": sync_status.get("gmail", {}).get("can_manual_sync", True),
                    "initial_sync_completed": sync_status.get("gmail", {}).get("initial_sync_completed", False)
                },
                "google_drive": {
                    "configured": (settings.nango_provider_key_google_drive is not None) or (settings.nango_provider_key_gmail is not None),
                    "connected": drive_connection is not None,
                    "connection_id": drive_connection,
                    "last_sync": drive_details.get("last_sync") if drive_details else None,
                    "can_manual_sync": sync_status.get("google_drive", {}).get("can_manual_sync", True),
                    "initial_sync_completed": sync_status.get("google_drive", {}).get("initial_sync_completed", False)
                },
                "quickbooks": {
                    "configured": settings.nango_provider_key_quickbooks is not None,
                    "connected": quickbooks_connection is not None,
                    "connection_id": quickbooks_connection,
                    "last_sync": quickbooks_details.get("last_sync") if quickbooks_details else None,
                    "can_manual_sync": sync_status.get("quickbooks", {}).get("can_manual_sync", True),
                    "initial_sync_completed": sync_status.get("quickbooks", {}).get("initial_sync_completed", False)
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
