"""
Episode Context Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from backend.models.api_models import EpisodeContextResponse
from backend.middleware.auth import verify_api_key
from backend.core.search import HybridSearch


router = APIRouter(prefix="/api", tags=["episodes"])

# Global search engine instance (will be injected via dependency)
search_engine = HybridSearch()


@router.get("/episode/{episode_id}", response_model=EpisodeContextResponse)
async def get_episode_context(
    episode_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get all context (document chunks) for a specific episode

    Episodes represent a single ingested document. This endpoint retrieves
    all chunks associated with that document, useful for:
    - Viewing full document after finding a relevant chunk
    - Reconstructing original document content
    - Analyzing document structure and chunking

    Args:
        episode_id: UUID of the episode to retrieve
        api_key: Validated API key from header

    Returns:
        EpisodeContextResponse: All chunks for the episode
    """
    try:
        context = search_engine.get_context_for_episode(episode_id)

        return EpisodeContextResponse(
            success=True,
            episode_id=context["episode_id"],
            chunks=context["chunks"],
            total_chunks=context["total_chunks"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve episode context: {str(e)}"
        )
