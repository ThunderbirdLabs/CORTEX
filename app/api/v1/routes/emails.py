"""
Email Routes
Fetch full emails from Supabase by episode_id
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
    Get full email(s) from Supabase by episode_id.
    
    This allows you to:
    1. Search with RAG (get episode_ids from Qdrant results)
    2. Fetch full emails from Supabase using those episode_ids
    3. Display complete email context to the user
    
    Args:
        episode_id: UUID from Qdrant vector search results
        user_id: Authenticated user (from JWT)
        supabase: Supabase client
        
    Returns:
        List of full email objects with all metadata
    """
    try:
        # Query Supabase for emails matching this episode_id and tenant_id
        result = supabase.table("emails").select("*").eq(
            "episode_id", episode_id
        ).eq(
            "tenant_id", user_id
        ).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail=f"No emails found for episode_id {episode_id}"
            )
        
        logger.info(f"Found {len(result.data)} email(s) for episode {episode_id}")
        
        return {
            "success": True,
            "episode_id": episode_id,
            "count": len(result.data),
            "emails": result.data
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
    Get full emails from Supabase for multiple episode_ids.
    
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
        # Query Supabase for all emails matching these episode_ids
        result = supabase.table("emails").select("*").in_(
            "episode_id", episode_ids
        ).eq(
            "tenant_id", user_id
        ).execute()
        
        if not result.data:
            return {
                "success": True,
                "count": 0,
                "emails_by_episode": {}
            }
        
        # Group emails by episode_id
        emails_by_episode = {}
        for email in result.data:
            ep_id = email.get("episode_id")
            if ep_id:
                if ep_id not in emails_by_episode:
                    emails_by_episode[ep_id] = []
                emails_by_episode[ep_id].append(email)
        
        logger.info(f"Found {len(result.data)} email(s) across {len(emails_by_episode)} episodes")
        
        return {
            "success": True,
            "count": len(result.data),
            "episodes_found": len(emails_by_episode),
            "emails_by_episode": emails_by_episode
        }
        
    except Exception as e:
        logger.error(f"Error fetching emails by episode_ids: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch emails: {str(e)}"
        )
