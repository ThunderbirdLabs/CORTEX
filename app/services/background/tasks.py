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


async def _run_gmail_sync_with_cleanup(http_client: httpx.AsyncClient, supabase, rag_pipeline, user_id: str, provider_key: str, modified_after: Optional[str] = None):
    """
    Async wrapper that runs Gmail sync and handles HTTP client cleanup properly.
    """
    from app.services.nango import run_gmail_sync
    
    try:
        result = await run_gmail_sync(http_client, supabase, rag_pipeline, user_id, provider_key, modified_after)
        return result
    finally:
        # Cleanup HTTP client in the same event loop
        await http_client.aclose()


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
        
        # Run the sync with proper cleanup
        result = asyncio.run(_run_gmail_sync_with_cleanup(
            http_client, supabase, rag_pipeline, 
            user_id, settings.nango_provider_key_gmail,
            modified_after
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


async def _run_outlook_sync_with_cleanup(http_client: httpx.AsyncClient, supabase, rag_pipeline, user_id: str, provider_key: str):
    """
    Async wrapper that runs sync and handles HTTP client cleanup properly.
    """
    from app.services.nango import run_tenant_sync
    
    try:
        result = await run_tenant_sync(http_client, supabase, rag_pipeline, user_id, provider_key)
        return result
    finally:
        # Cleanup HTTP client in the same event loop
        await http_client.aclose()


@dramatiq.actor(max_retries=3)
def sync_outlook_task(user_id: str, job_id: str):
    """
    Background job for Outlook sync.
    
    Args:
        user_id: User/tenant ID
        job_id: Sync job ID for status tracking
    """
    from app.core.config import settings
    
    logger.info(f"🚀 Starting Outlook sync job {job_id} for user {user_id}")
    
    http_client, supabase, rag_pipeline = get_sync_dependencies()
    
    try:
        # Update job status to running
        supabase.table("sync_jobs").update({
            "status": "running",
            "started_at": "now()"
        }).eq("id", job_id).execute()
        
        # Run the sync with proper cleanup
        result = asyncio.run(_run_outlook_sync_with_cleanup(
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


@dramatiq.actor(max_retries=2, time_limit=300000)  # 5 min timeout
def deduplicate_entities_task():
    """
    Periodic entity deduplication task (runs every 15 minutes).

    Merges duplicate entities created during batch ingestion using:
    - Vector similarity (cosine > 0.92)
    - Levenshtein distance (< 3 chars)

    Production-ready for Render with Dramatiq distributed locking.
    """
    from app.services.deduplication.entity_deduplication import run_entity_deduplication
    from app.core.config import settings

    logger.info("⏰ Running scheduled entity deduplication...")

    try:
        results = run_entity_deduplication(
            neo4j_uri=settings.neo4j_uri,
            neo4j_password=settings.neo4j_password,
            dry_run=False,
            similarity_threshold=settings.dedup_similarity_threshold,
            levenshtein_max_distance=settings.dedup_levenshtein_max_distance
        )

        merged_count = results.get("entities_merged", 0)

        if merged_count > 0:
            logger.info(f"✅ Entity deduplication complete: {merged_count} entities merged")
        else:
            logger.debug("✅ Entity deduplication complete: no duplicates found")

        # Alert if suspiciously high merge count
        if merged_count > 100:
            logger.warning(f"🚨 High merge count: {merged_count} entities merged! Review thresholds.")

        return results

    except Exception as e:
        logger.error(f"❌ Entity deduplication failed: {e}")
        raise  # Re-raise for Dramatiq retry logic

