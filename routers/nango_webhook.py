"""
Nango webhook handler
Processes Nango webhook events and triggers background syncs
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nango", tags=["webhook"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NangoWebhook(BaseModel):
    """
    Nango webhook payload for connection events.
    See: https://docs.nango.dev/integrate/guides/webhooks
    """
    type: str  # Event type: "auth", "sync", "forward"
    connectionId: str  # This is the tenant/user ID
    providerConfigKey: str  # Integration unique key
    environment: str  # "dev" or "prod"
    success: Optional[bool] = None  # For auth events
    model: Optional[str] = None  # For sync events
    responseResults: Optional[Dict[str, Any]] = None  # For sync events

    class Config:
        extra = "allow"  # Allow additional fields from Nango
