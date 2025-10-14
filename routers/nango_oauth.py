"""
Nango OAuth routes
Handles OAuth flow initiation and callbacks
"""
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nango_services.database import save_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["oauth"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NangoOAuthCallback(BaseModel):
    """Nango OAuth callback payload."""
    tenantId: str
    providerConfigKey: str
    connectionId: str


# ============================================================================
# OAUTH CALLBACK ROUTE (SIMPLE - NO DEPENDENCIES)
# ============================================================================

@router.post("/nango/oauth/callback")
async def nango_oauth_callback(payload: NangoOAuthCallback):
    """
    Handle Nango OAuth callback.
    Saves connection information for the tenant.
    """
    logger.info(f"Received OAuth callback for tenant {payload.tenantId}")

    try:
        await save_connection(
            payload.tenantId,
            payload.providerConfigKey,
            payload.connectionId
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
