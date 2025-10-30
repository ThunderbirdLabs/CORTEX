"""
Sync Routes
Background job-based sync endpoints for Gmail, Drive, and Outlook
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from supabase import Client

from app.core.security import get_current_user_id
from app.core.dependencies import get_supabase
from app.services.background.tasks import sync_gmail_task, sync_drive_task, sync_outlook_task, sync_quickbooks_task
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/once")
@limiter.limit("30/hour")  # 30 manual Outlook syncs per hour (increased for testing)
async def sync_once(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Start Outlook sync as background job.
    Returns immediately with job_id for status tracking.
    """
    logger.info(f"Enqueueing Outlook sync for user {user_id}")
    try:
        # Create job record
        job = supabase.table("sync_jobs").insert({
            "user_id": user_id,
            "job_type": "outlook",
            "status": "queued"
        }).execute()
        
        job_id = job.data[0]["id"]
        
        # Enqueue background task
        sync_outlook_task.send(user_id, job_id)
        
        logger.info(f"✅ Outlook sync job {job_id} queued")
        
        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Outlook sync started in background. Use GET /sync/jobs/{job_id} to check status."
        }
    except Exception as e:
        logger.error(f"Error enqueueing Outlook sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/once/gmail")
@limiter.limit("30/hour")  # 30 manual Gmail syncs per hour (increased for testing)
async def sync_once_gmail(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
    modified_after: Optional[str] = Query(None, description="ISO datetime to filter records")
):
    """
    Start Gmail sync as background job.
    Returns immediately with job_id for status tracking.
    """
    logger.info(f"Enqueueing Gmail sync for user {user_id}")
    if modified_after:
        logger.info(f"Using modified_after filter: {modified_after}")

    try:
        # Create job record
        job = supabase.table("sync_jobs").insert({
            "user_id": user_id,
            "job_type": "gmail",
            "status": "queued"
        }).execute()
        
        job_id = job.data[0]["id"]
        
        # Enqueue background task
        sync_gmail_task.send(user_id, job_id, modified_after)
        
        logger.info(f"✅ Gmail sync job {job_id} queued")
        
        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Gmail sync started in background. Use GET /sync/jobs/{job_id} to check status."
        }
    except Exception as e:
        logger.error(f"Error enqueueing Gmail sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/once/drive")
@limiter.limit("5/hour")  # Only 5 manual Drive syncs per hour
async def sync_once_drive(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
    folder_ids: Optional[str] = Query(None, description="Comma-separated folder IDs to sync (empty = entire Drive)")
):
    """
    Start Google Drive sync as background job.
    Returns immediately with job_id for status tracking.

    Examples:
    - Sync entire Drive: GET /sync/once/drive
    - Sync specific folders: GET /sync/once/drive?folder_ids=1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE,0BxiMVs...
    """
    logger.info(f"Enqueueing Drive sync for user {user_id}")

    # Parse folder IDs
    folder_list = None
    if folder_ids:
        folder_list = [fid.strip() for fid in folder_ids.split(",") if fid.strip()]
        logger.info(f"Syncing specific folders: {folder_list}")
    else:
        logger.info("Syncing entire Drive")

    try:
        # Create job record
        job = supabase.table("sync_jobs").insert({
            "user_id": user_id,
            "job_type": "drive",
            "status": "queued"
        }).execute()
        
        job_id = job.data[0]["id"]
        
        # Enqueue background task
        sync_drive_task.send(user_id, job_id, folder_list)
        
        logger.info(f"✅ Drive sync job {job_id} queued")
        
        return {
            "status": "queued",
            "job_id": job_id,
            "message": "Drive sync started in background. Use GET /sync/jobs/{job_id} to check status."
        }
    except Exception as e:
        logger.error(f"Error enqueueing Drive sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/once/quickbooks")
@limiter.limit("10/hour")  # 10 manual QuickBooks syncs per hour
async def sync_once_quickbooks(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Start QuickBooks sync as background job.

    Fetches invoices, bills, payments, customers from QuickBooks.
    Each record is ingested as a document into Supabase + Knowledge Graph.

    Returns immediately with job_id for status tracking.
    """
    logger.info(f"Enqueueing QuickBooks sync for user {user_id}")

    try:
        # Create job record
        job = supabase.table("sync_jobs").insert({
            "user_id": user_id,
            "job_type": "quickbooks",
            "status": "queued"
        }).execute()

        job_id = job.data[0]["id"]

        # Enqueue background task
        sync_quickbooks_task.send(user_id, job_id)

        logger.info(f"✅ QuickBooks sync job {job_id} queued")

        return {
            "status": "queued",
            "job_id": job_id,
            "message": "QuickBooks sync started in background. Use GET /sync/jobs/{job_id} to check status."
        }
    except Exception as e:
        logger.error(f"Error enqueueing QuickBooks sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get status of a background sync job.

    Returns:
    - status: queued, running, completed, failed
    - started_at: When job started processing
    - completed_at: When job finished
    - result: Job results (messages_synced, files_synced, etc)
    - error_message: Error details if failed
    """
    try:
        result = supabase.table("sync_jobs").select("*").eq("id", job_id).eq("user_id", user_id).single().execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Job not found")
        
        return result.data
    except Exception as e:
        logger.error(f"Error fetching job status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
