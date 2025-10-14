"""
Manual sync routes
Provides endpoints for manual sync testing
"""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from supabase import Client

from cortex_backend.core.pipeline import HybridRAGPipeline
from nango_services.sync_engine import run_gmail_sync, run_tenant_sync
from config.settings import NANGO_PROVIDER_KEY_OUTLOOK, NANGO_PROVIDER_KEY_GMAIL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class SyncResponse(BaseModel):
    """Response for manual sync endpoint."""
    status: str
    tenant_id: str
    users_synced: Optional[int] = None  # Only for Outlook
    messages_synced: int
    errors: list = []


# ============================================================================
# MANUAL SYNC ROUTES
# ============================================================================

@router.get("/once", response_model=SyncResponse)
async def sync_once(
    user_id: str,
    http_client: httpx.AsyncClient,
    supabase: Client,
    cortex_pipeline: Optional[HybridRAGPipeline]
):
    """
    Manual Outlook sync endpoint for testing.
    Runs sync in-process and returns results.

    Args:
        user_id: Authenticated user ID from Supabase JWT
        http_client: Global async HTTP client
        supabase: Supabase client
        cortex_pipeline: Cortex pipeline instance (or None)
    """
    logger.info(f"Manual Outlook sync requested for user {user_id}")

    try:
        # Use configured Outlook provider key
        result = await run_tenant_sync(
            http_client,
            supabase,
            cortex_pipeline,
            user_id,
            NANGO_PROVIDER_KEY_OUTLOOK
        )

        return SyncResponse(
            status=result["status"],
            tenant_id=result["tenant_id"],
            users_synced=result["users_synced"],
            messages_synced=result["messages_synced"],
            errors=result["errors"]
        )
    except Exception as e:
        logger.error(f"Error in manual Outlook sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/once/gmail")
async def sync_once_gmail(
    user_id: str,
    http_client: httpx.AsyncClient,
    supabase: Client,
    cortex_pipeline: Optional[HybridRAGPipeline],
    modified_after: Optional[str] = Query(None, description="ISO datetime to filter records (e.g., 2024-01-01T00:00:00Z)")
):
    """
    Manual Gmail sync endpoint for testing.
    Runs sync in-process and returns results.
    Supports optional modified_after parameter for quick testing.

    Args:
        user_id: Authenticated user ID from Supabase JWT
        http_client: Global async HTTP client
        supabase: Supabase client
        cortex_pipeline: Cortex pipeline instance (or None)
        modified_after: Optional ISO datetime to filter records
    """
    logger.info(f"Manual Gmail sync requested for user {user_id}")
    if modified_after:
        logger.info(f"Using modified_after filter: {modified_after}")

    try:
        # Use configured Gmail provider key
        result = await run_gmail_sync(
            http_client,
            supabase,
            cortex_pipeline,
            user_id,
            NANGO_PROVIDER_KEY_GMAIL,
            modified_after=modified_after
        )

        return {
            "status": result["status"],
            "tenant_id": result["tenant_id"],
            "messages_synced": result["messages_synced"],
            "errors": result["errors"]
        }
    except Exception as e:
        logger.error(f"Error in manual Gmail sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))
