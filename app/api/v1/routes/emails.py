"""
Email Routes
Fetch full emails from Supabase documents table by episode_id
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.core.security import get_current_user_id
from app.core.dependencies import get_supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("/by-episode/{episode_id}")
async def get_emails_by_episode(
    episode_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get full email(s) from Supabase documents table by episode_id.
    
    This allows you to:
    1. Search with RAG (get episode_ids from Qdrant results)
    2. Fetch full emails from documents table using those episode_ids
    3. Display complete email context to the user
    
    Args:
        episode_id: UUID from Qdrant vector search results
        user_id: Authenticated user (from JWT)
        supabase: Supabase client
        
    Returns:
        List of full email objects with all metadata
    """
    try:
        # Query documents table for emails matching this episode_id and tenant_id
        # Use JSONB query for episode_id in metadata
        result = supabase.table("documents").select("*").eq(
            "document_type", "email"
        ).eq(
            "tenant_id", user_id
        ).filter("metadata->>episode_id", "eq", episode_id).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No emails found for episode_id {episode_id}"
            )
        
        logger.info(f"Found {len(result.data)} email(s) for episode {episode_id}")
        
        # Transform documents to email format for backwards compatibility
        emails = []
        for doc in result.data:
            email = {
                "id": doc.get("id"),
                "tenant_id": doc.get("tenant_id"),
                "source": doc.get("source"),
                "message_id": doc.get("source_id"),
                "subject": doc.get("title"),
                "full_body": doc.get("content"),
                "received_datetime": doc.get("source_created_at"),
                "sender_name": doc.get("metadata", {}).get("sender_name"),
                "sender_address": doc.get("metadata", {}).get("sender_address"),
                "to_addresses": doc.get("metadata", {}).get("to_addresses"),
                "web_link": doc.get("metadata", {}).get("web_link"),
                "episode_id": doc.get("metadata", {}).get("episode_id"),
                "raw_data": doc.get("raw_data")
            }
            emails.append(email)
        
        return {
            "success": True,
            "episode_id": episode_id,
            "count": len(emails),
            "emails": emails
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching emails by episode_id: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch emails: {str(e)}"
        )


@router.post("/by-episodes")
async def get_emails_by_episodes(
    episode_ids: List[str],
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get full emails from Supabase documents table for multiple episode_ids.
    
    Useful when you have multiple search results and want to fetch
    all related emails in one request.
    
    Args:
        episode_ids: List of episode UUIDs from search results
        user_id: Authenticated user (from JWT)
        supabase: Supabase client
        
    Returns:
        Dictionary mapping episode_ids to their emails
    """
    try:
        # Query documents table for all emails matching these episode_ids
        result = supabase.table("documents").select("*").eq(
            "document_type", "email"
        ).eq(
            "tenant_id", user_id
        ).execute()
        
        if not result.data:
            return {
                "success": True,
                "count": 0,
                "emails_by_episode": {}
            }
        
        # Filter by episode_ids and group emails by episode_id
        emails_by_episode = {}
        for doc in result.data:
            ep_id = doc.get("metadata", {}).get("episode_id")
            if ep_id and ep_id in episode_ids:
                if ep_id not in emails_by_episode:
                    emails_by_episode[ep_id] = []
                
                # Transform document to email format for backwards compatibility
                email = {
                    "id": doc.get("id"),
                    "tenant_id": doc.get("tenant_id"),
                    "source": doc.get("source"),
                    "message_id": doc.get("source_id"),
                    "subject": doc.get("title"),
                    "full_body": doc.get("content"),
                    "received_datetime": doc.get("source_created_at"),
                    "sender_name": doc.get("metadata", {}).get("sender_name"),
                    "sender_address": doc.get("metadata", {}).get("sender_address"),
                    "to_addresses": doc.get("metadata", {}).get("to_addresses"),
                    "web_link": doc.get("metadata", {}).get("web_link"),
                    "episode_id": ep_id,
                    "raw_data": doc.get("raw_data")
                }
                emails_by_episode[ep_id].append(email)
        
        total_emails = sum(len(emails) for emails in emails_by_episode.values())
        logger.info(f"Found {total_emails} email(s) across {len(emails_by_episode)} episodes")
        
        return {
            "success": True,
            "count": total_emails,
            "episodes_found": len(emails_by_episode),
            "emails_by_episode": emails_by_episode
        }
        
    except Exception as e:
        logger.error(f"Error fetching emails by episode_ids: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch emails: {str(e)}"
        )
