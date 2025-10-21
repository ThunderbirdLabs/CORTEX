"""
Dramatiq Background Tasks
Handles long-running sync operations (Gmail, Drive, Outlook) asynchronously
"""
import dramatiq
import asyncio
import logging
import httpx
from typing import Optional
from supabase import create_client

logger = logging.getLogger(__name__)


def get_sync_dependencies():
    """
    Create fresh instances of dependencies for background tasks.
    Dramatiq workers run in separate processes, so we can't share global clients.
    """
    from app.core.config import settings
    from app.services.ingestion.llamaindex import UniversalIngestionPipeline
    
    # Create fresh HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(60.0),  # Longer timeout for background jobs
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
    )
    
    # Create fresh Supabase client
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    
    # Create fresh RAG pipeline
    try:
        rag_pipeline = UniversalIngestionPipeline()
    except Exception as e:
        logger.error(f"Failed to initialize RAG pipeline in worker: {e}")
        rag_pipeline = None
    
    return http_client, supabase, rag_pipeline


@dramatiq.actor(max_retries=3)
def sync_gmail_task(user_id: str, job_id: str, modified_after: Optional[str] = None):
    """
    Background job for Gmail sync.
    
    Args:
        user_id: User/tenant ID
        job_id: Sync job ID for status tracking
        modified_after: Optional ISO datetime filter
    """
    from app.services.nango import run_gmail_sync
    from app.core.config import settings
    
    logger.info(f"🚀 Starting Gmail sync job {job_id} for user {user_id}")
    
    http_client, supabase, rag_pipeline = get_sync_dependencies()
    
    try:
        # Update job status to running
        supabase.table("sync_jobs").update({
            "status": "running",
            "started_at": "now()"
        }).eq("id", job_id).execute()
        
        # Run the sync
        result = asyncio.run(run_gmail_sync(
            http_client, supabase, rag_pipeline, 
            user_id, settings.nango_provider_key_gmail,
            modified_after=modified_after
        ))
        
        # Update job status to completed
        supabase.table("sync_jobs").update({
            "status": "completed",
            "completed_at": "now()",
            "result": result
        }).eq("id", job_id).execute()
        
        logger.info(f"✅ Gmail sync job {job_id} complete: {result.get('messages_synced', 0)} messages")
        return result
        
    except Exception as e:
        logger.error(f"❌ Gmail sync job {job_id} failed: {e}")
        
        # Update job status to failed
        supabase.table("sync_jobs").update({
            "status": "failed",
            "completed_at": "now()",
            "error_message": str(e)
        }).eq("id", job_id).execute()
        
        raise  # Re-raise for Dramatiq retry logic
    
    finally:
        # Cleanup HTTP client
        asyncio.run(http_client.aclose())


@dramatiq.actor(max_retries=3)
def sync_drive_task(user_id: str, job_id: str, folder_ids: Optional[list] = None):
    """
    Background job for Google Drive sync.
    
    Args:
        user_id: User/tenant ID
        job_id: Sync job ID for status tracking
        folder_ids: Optional list of folder IDs to sync
    """
    from app.services.nango.drive_sync import run_drive_sync
    from app.core.config import settings
    
    logger.info(f"🚀 Starting Drive sync job {job_id} for user {user_id}")
    
    http_client, supabase, rag_pipeline = get_sync_dependencies()
    
    try:
        # Update job status to running
        supabase.table("sync_jobs").update({
            "status": "running",
            "started_at": "now()"
        }).eq("id", job_id).execute()
        
        # Run the sync
        result = asyncio.run(run_drive_sync(
            http_client, supabase, rag_pipeline,
            user_id, settings.nango_provider_key_google_drive,
            folder_ids=folder_ids
        ))
        
        # Update job status to completed
        supabase.table("sync_jobs").update({
            "status": "completed",
            "completed_at": "now()",
            "result": result
        }).eq("id", job_id).execute()
        
        logger.info(f"✅ Drive sync job {job_id} complete: {result.get('files_synced', 0)} files")
        return result
        
    except Exception as e:
        logger.error(f"❌ Drive sync job {job_id} failed: {e}")
        
        # Update job status to failed
        supabase.table("sync_jobs").update({
            "status": "failed",
            "completed_at": "now()",
            "error_message": str(e)
        }).eq("id", job_id).execute()
        
        raise  # Re-raise for Dramatiq retry logic
    
    finally:
        # Cleanup HTTP client
        asyncio.run(http_client.aclose())


@dramatiq.actor(max_retries=3)
def sync_outlook_task(user_id: str, job_id: str):
    """
    Background job for Outlook sync.
    
    Args:
        user_id: User/tenant ID
        job_id: Sync job ID for status tracking
    """
    from app.services.nango import run_tenant_sync
    from app.core.config import settings
    
    logger.info(f"🚀 Starting Outlook sync job {job_id} for user {user_id}")
    
    http_client, supabase, rag_pipeline = get_sync_dependencies()
    
    try:
        # Update job status to running
        supabase.table("sync_jobs").update({
            "status": "running",
            "started_at": "now()"
        }).eq("id", job_id).execute()
        
        # Run the sync
        result = asyncio.run(run_tenant_sync(
            http_client, supabase, rag_pipeline,
            user_id, settings.nango_provider_key_outlook
        ))
        
        # Update job status to completed
        supabase.table("sync_jobs").update({
            "status": "completed",
            "completed_at": "now()",
            "result": result
        }).eq("id", job_id).execute()
        
        logger.info(f"✅ Outlook sync job {job_id} complete: {result.get('messages_synced', 0)} messages")
        return result
        
    except Exception as e:
        logger.error(f"❌ Outlook sync job {job_id} failed: {e}")
        
        # Update job status to failed
        supabase.table("sync_jobs").update({
            "status": "failed",
            "completed_at": "now()",
            "error_message": str(e)
        }).eq("id", job_id).execute()
        
        raise  # Re-raise for Dramatiq retry logic
    
    finally:
        # Cleanup HTTP client
        asyncio.run(http_client.aclose())

