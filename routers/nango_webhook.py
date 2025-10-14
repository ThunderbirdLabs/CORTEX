"""
Nango webhook handler
Processes Nango webhook events and triggers background syncs
"""
import logging
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from supabase import Client

from cortex_backend.core.pipeline import HybridRAGPipeline
from nango_services.database import save_connection
from nango_services.sync_engine import run_gmail_sync, run_tenant_sync
from config.settings import NANGO_SECRET, NANGO_PROVIDER_KEY_GMAIL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nango", tags=["webhook"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NangoWebhook(BaseModel):
    """
    Nango webhook payload for connection events.
    See: https://docs.nango.dev/integrate/guides/webhooks
    """
    type: str  # Event type: "auth", "sync", "forward"
    connectionId: str  # This is the tenant/user ID
    providerConfigKey: str  # Integration unique key
    environment: str  # "dev" or "prod"
    success: Optional[bool] = None  # For auth events
    model: Optional[str] = None  # For sync events
    responseResults: Optional[Dict[str, Any]] = None  # For sync events

    class Config:
        extra = "allow"  # Allow additional fields from Nango


# ============================================================================
# WEBHOOK ROUTE
# ============================================================================

@router.post("/webhook")
async def nango_webhook(
    payload: NangoWebhook,
    background_tasks: BackgroundTasks,
    http_client: httpx.AsyncClient,
    supabase: Client,
    cortex_pipeline: Optional[HybridRAGPipeline]
):
    """
    Handle Nango webhook.
    Triggers background sync for the tenant (Outlook or Gmail).

    Webhook is called when:
    - "auth" event: User completes OAuth (saves connection automatically)
    - "sync" event: Nango sync completes (triggers our sync to pull data)

    TODO: Verify Nango signature for security

    Args:
        payload: Nango webhook payload
        background_tasks: FastAPI background tasks
        http_client: Global async HTTP client
        supabase: Supabase client
        cortex_pipeline: Cortex pipeline instance (or None)
    """
    nango_connection_id = payload.connectionId  # UUID from Nango

    logger.info(f"Received Nango webhook: type={payload.type}, connection={nango_connection_id}, provider={payload.providerConfigKey}")

    # Handle auth events - get end_user from Nango and save connection
    if payload.type == "auth" and payload.success:
        try:
            # Try to get end_user from the webhook payload first
            logger.info(f"Full webhook payload: {payload.model_dump_json()}")

            # Check if end_user is in the webhook (Nango might send it in some versions)
            if hasattr(payload, 'end_user') and payload.end_user:
                end_user_id = payload.end_user.get("id") if isinstance(payload.end_user, dict) else None
            else:
                end_user_id = None
                logger.error(f"No end_user in webhook payload for connection {nango_connection_id}")

            # If not in webhook, query Nango's connection metadata API
            if not end_user_id:
                logger.info(f"Attempting to fetch end_user from Nango connection metadata")

                # Use the metadata endpoint which should include end_user
                conn_url = f"https://api.nango.dev/connection/{nango_connection_id}?provider_config_key={payload.providerConfigKey}"
                headers = {"Authorization": f"Bearer {NANGO_SECRET}"}

                response = await http_client.get(conn_url, headers=headers)
                response.raise_for_status()
                conn_data = response.json()

                logger.info(f"Nango metadata response: {conn_data}")

                end_user_id = conn_data.get("end_user", {}).get("id") if isinstance(conn_data.get("end_user"), dict) else None

            if not end_user_id:
                logger.error(f"Failed to retrieve end_user for connection {nango_connection_id}")
                return {"status": "error", "message": "Missing end_user information"}

            logger.info(f"OAuth successful for user {end_user_id}, saving connection")

            # Save with user UUID as tenant_id and Nango UUID as connection_id
            await save_connection(end_user_id, payload.providerConfigKey, nango_connection_id)

            return {"status": "connection_saved", "user": end_user_id}

        except Exception as e:
            logger.error(f"Error handling auth webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # Handle sync events or trigger manual sync on auth success
    # For sync events, we need to look up the user email from connection_id
    try:
        # Query Nango to get end_user for this connection
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

    # Determine which sync function to use based on provider key
    if payload.providerConfigKey == NANGO_PROVIDER_KEY_GMAIL:
        # Gmail sync
        background_tasks.add_task(
            run_gmail_sync,
            http_client,
            supabase,
            cortex_pipeline,
            tenant_id,
            payload.providerConfigKey
        )
        logger.info(f"Triggered Gmail sync for tenant {tenant_id}")
    else:
        # Outlook/Microsoft Graph sync (default)
        background_tasks.add_task(
            run_tenant_sync,
            http_client,
            supabase,
            cortex_pipeline,
            tenant_id,
            payload.providerConfigKey
        )
        logger.info(f"Triggered Outlook sync for tenant {tenant_id}")

    # Return immediately
    return {"status": "accepted"}
