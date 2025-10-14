"""
Status and health check routes
"""
import logging

from fastapi import APIRouter, HTTPException

from nango_services.database import get_connection
from config.settings import NANGO_PROVIDER_KEY_OUTLOOK, NANGO_PROVIDER_KEY_GMAIL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["status"])


# ============================================================================
# STATUS ROUTES
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/status")
async def get_status(user_id: str):
    """
    Get connection status for authenticated user.
    Returns info about configured providers and connections.

    Args:
        user_id: Authenticated user ID from Supabase JWT
    """
    try:
        # Check Outlook connection
        outlook_connection = await get_connection(user_id, NANGO_PROVIDER_KEY_OUTLOOK) if NANGO_PROVIDER_KEY_OUTLOOK else None

        # Check Gmail connection
        gmail_connection = await get_connection(user_id, NANGO_PROVIDER_KEY_GMAIL) if NANGO_PROVIDER_KEY_GMAIL else None

        return {
            "tenant_id": user_id,
            "providers": {
                "outlook": {
                    "configured": NANGO_PROVIDER_KEY_OUTLOOK is not None,
                    "connected": outlook_connection is not None,
                    "connection_id": outlook_connection if outlook_connection else None
                },
                "gmail": {
                    "configured": NANGO_PROVIDER_KEY_GMAIL is not None,
                    "connected": gmail_connection is not None,
                    "connection_id": gmail_connection if gmail_connection else None
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))
