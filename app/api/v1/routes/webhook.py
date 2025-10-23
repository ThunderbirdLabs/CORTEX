"""
Webhook Routes
Handles Nango webhook events and triggers background syncs
"""
import logging
import httpx
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends
from supabase import Client

from app.core.config import settings
from app.core.dependencies import get_http_client, get_supabase, get_rag_pipeline
from app.models.schemas import NangoWebhook
from app.services.nango import run_gmail_sync, run_tenant_sync
from app.services.nango import save_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nango", tags=["webhook"])


@router.post("/webhook")
async def nango_webhook(
    payload: dict,  # Accept raw dict to see what's coming in
    background_tasks: BackgroundTasks,
    http_client: httpx.AsyncClient = Depends(get_http_client),
    supabase: Client = Depends(get_supabase),
    rag_pipeline: Optional[any] = Depends(get_rag_pipeline)
):
    """
    Handle Nango webhook - triggers background sync.
    
    Webhook types:
    - auth: OAuth completion (success/failure)
    - sync: Incremental sync completion
    - forward: Passthrough API calls
    """
    logger.info(f"Received Nango webhook (raw): {payload}")
    
    # Parse webhook (flexible for different event types)
    webhook_type = payload.get("type")
    nango_connection_id = payload.get("connectionId")
    provider_key = payload.get("providerConfigKey")
    
    logger.info(f"Webhook parsed: type={webhook_type}, connection={nango_connection_id}, provider={provider_key}")

    # Handle auth events
    if webhook_type == "auth" and payload.get("success"):
        try:
            logger.info(f"Full webhook payload: {payload}")

            end_user_id = None
            end_user = payload.get('endUser') or payload.get('end_user')
            if end_user:
                end_user_id = end_user.get("endUserId") or end_user.get("id")

            if not end_user_id:
                conn_url = f"https://api.nango.dev/connection/{nango_connection_id}?provider_config_key={provider_key}"
                headers = {"Authorization": f"Bearer {settings.nango_secret}"}
                response = await http_client.get(conn_url, headers=headers)
                response.raise_for_status()
                conn_data = response.json()
                end_user_id = conn_data.get("end_user", {}).get("id") if isinstance(conn_data.get("end_user"), dict) else None

            if not end_user_id:
                logger.error(f"Failed to retrieve end_user for connection {nango_connection_id}")
                return {"status": "error", "message": "Missing end_user information"}

            logger.info(f"OAuth successful for user {end_user_id}, saving connection")
            # Use email format as connection_id for API calls (matches Nango Connect SDK behavior)
            connection_id_for_api = f"{end_user_id}@app.internal"
            await save_connection(end_user_id, provider_key, connection_id_for_api)
            logger.info(f"Saved connection with ID: {connection_id_for_api}")
            return {"status": "connection_saved", "user": end_user_id}

        except Exception as e:
            logger.error(f"Error handling auth webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # Handle sync events - get tenant_id
    if webhook_type == "sync":
        logger.info(f"Sync webhook received: model={payload.get('model')}, success={payload.get('success')}")
        # For now, just acknowledge sync webhooks
        return {"status": "sync_acknowledged"}
    
    # Other webhook types - get tenant_id
    try:
        conn_url = f"https://api.nango.dev/connection/{provider_key}/{nango_connection_id}"
        headers = {"Authorization": f"Bearer {settings.nango_secret}"}
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
    if payload.providerConfigKey == settings.nango_provider_key_gmail:
        background_tasks.add_task(run_gmail_sync, http_client, supabase, rag_pipeline, tenant_id, payload.providerConfigKey)
        logger.info(f"Triggered Gmail sync for tenant {tenant_id}")
    else:
        background_tasks.add_task(run_tenant_sync, http_client, supabase, rag_pipeline, tenant_id, payload.providerConfigKey)
        logger.info(f"Triggered Outlook sync for tenant {tenant_id}")

    return {"status": "accepted"}
