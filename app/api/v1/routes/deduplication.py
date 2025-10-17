"""
Entity Deduplication API Endpoints

Manual triggering and monitoring of entity deduplication.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.dependencies import get_settings
from app.core.security import verify_api_key
from app.services.deduplication.entity_deduplication import EntityDeduplicationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/deduplication", tags=["deduplication"])


class DeduplicationResponse(BaseModel):
    """Response from deduplication operation."""
    success: bool
    results: dict


class DeduplicationStatsResponse(BaseModel):
    """Statistics about entities and potential duplicates."""
    total_entities: int
    entities_with_embeddings: int
    entities_without_embeddings: int


@router.post("/run", response_model=DeduplicationResponse)
async def run_deduplication(
    dry_run: bool = Query(False, description="If true, only preview duplicates without merging"),
    similarity_threshold: Optional[float] = Query(None, description="Cosine similarity threshold (0.0-1.0)"),
    levenshtein_max_distance: Optional[int] = Query(None, description="Max Levenshtein distance for name matching"),
    settings = Depends(get_settings),
    _ = Depends(verify_api_key)
):
    """
    Manually trigger entity deduplication.

    **Dry Run Mode** (dry_run=true):
    - Only identifies duplicate clusters
    - Does not merge entities
    - Returns list of duplicates for review

    **Merge Mode** (dry_run=false):
    - Actually merges duplicate entities
    - Combines relationships
    - Deletes duplicate nodes

    **Thresholds**:
    - similarity_threshold: 0.88 (aggressive) to 0.95 (conservative), default 0.92
    - levenshtein_max_distance: 2-5 characters, default 3
    """

    logger.info(f"= Deduplication request: dry_run={dry_run}")

    # Build service kwargs
    service_kwargs = {
        "neo4j_uri": settings.neo4j_uri,
        "neo4j_password": settings.neo4j_password
    }

    if similarity_threshold is not None:
        service_kwargs["similarity_threshold"] = similarity_threshold

    if levenshtein_max_distance is not None:
        service_kwargs["levenshtein_max_distance"] = levenshtein_max_distance

    service = EntityDeduplicationService(**service_kwargs)

    try:
        results = service.deduplicate_entities(dry_run=dry_run)

        # Alert if high merge count
        if not dry_run and service.should_alert(results):
            logger.error(f"=¨ ALERT: High merge count - {results.get('entities_merged')} entities merged!")

        return DeduplicationResponse(
            success=True,
            results=results
        )

    except Exception as e:
        logger.error(f"L Deduplication failed: {e}", exc_info=True)
        return DeduplicationResponse(
            success=False,
            results={"error": str(e)}
        )

    finally:
        service.close()


@router.get("/stats", response_model=DeduplicationStatsResponse)
async def get_deduplication_stats(
    settings = Depends(get_settings),
    _ = Depends(verify_api_key)
):
    """
    Get statistics about entities and potential duplicates.

    Returns:
    - total_entities: Total number of entities in graph
    - entities_with_embeddings: Entities that can be deduplicated
    - entities_without_embeddings: Entities without embeddings (skipped)
    """

    service = EntityDeduplicationService(
        neo4j_uri=settings.neo4j_uri,
        neo4j_password=settings.neo4j_password
    )

    try:
        stats = service.get_deduplication_stats()
        return DeduplicationStatsResponse(**stats)

    except Exception as e:
        logger.error(f"L Failed to get stats: {e}", exc_info=True)
        raise

    finally:
        service.close()
