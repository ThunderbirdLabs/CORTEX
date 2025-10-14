"""
Status and health check routes
"""
import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["status"])


# ============================================================================
# STATUS ROUTES
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
