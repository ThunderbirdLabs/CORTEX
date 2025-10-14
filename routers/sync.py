"""
Manual sync routes
Provides endpoints for manual sync testing
"""
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

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
