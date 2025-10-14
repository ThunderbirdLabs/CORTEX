"""
Legacy Routes
Backward compatibility for old API endpoints
"""
import logging
from fastapi import APIRouter, Depends
from app.models.schemas import SearchQuery, SearchResponse
from app.core.security import verify_api_key
from app.api.v1.routes.search import search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["legacy"])


@router.post("/search-optimized", response_model=SearchResponse)
async def search_optimized_legacy(
    query: SearchQuery,
    api_key: str = Depends(verify_api_key)
):
    """
    Legacy endpoint for backward compatibility.
    Redirects to /api/v1/search
    """
    logger.info(f"Legacy endpoint /api/search-optimized called, forwarding to /api/v1/search")
    return await search(query, api_key)
