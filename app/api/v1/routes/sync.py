"""
Sync Routes
Manual sync endpoints for testing
"""
import logging
import httpx
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.core.config import settings
from app.core.security import get_current_user_id
from app.core.dependencies import get_http_client, get_supabase, get_rag_pipeline
from app.models.schemas import SyncResponse
from app.services.nango import run_gmail_sync, run_tenant_sync

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/once", response_model=SyncResponse)
async def sync_once(
    user_id: str = Depends(get_current_user_id),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    supabase: Client = Depends(get_supabase),
    rag_pipeline: Optional[any] = Depends(get_rag_pipeline)
):
    """
    Manual Outlook sync endpoint for testing.
    Immediately syncs all mailboxes for the user.
    """
    logger.info(f"Manual Outlook sync requested for user {user_id}")
    try:
        result = await run_tenant_sync(http_client, supabase, rag_pipeline, user_id, settings.nango_provider_key_outlook)
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


@router.get("/once/gmail")
async def sync_once_gmail(
    user_id: str = Depends(get_current_user_id),
    http_client: httpx.AsyncClient = Depends(get_http_client),
    supabase: Client = Depends(get_supabase),
    rag_pipeline: Optional[any] = Depends(get_rag_pipeline),
    modified_after: Optional[str] = Query(None, description="ISO datetime to filter records")
):
    """
    Manual Gmail sync endpoint for testing.
    Immediately syncs Gmail messages for the user.
    """
    logger.info(f"Manual Gmail sync requested for user {user_id}")
    if modified_after:
        logger.info(f"Using modified_after filter: {modified_after}")

    try:
        result = await run_gmail_sync(http_client, supabase, rag_pipeline, user_id, settings.nango_provider_key_gmail, modified_after=modified_after)
        return {
            "status": result["status"],
            "tenant_id": result["tenant_id"],
            "messages_synced": result["messages_synced"],
            "errors": result["errors"]
        }
    except Exception as e:
        logger.error(f"Error in manual Gmail sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))
