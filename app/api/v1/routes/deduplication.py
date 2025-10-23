"""
Entity Deduplication API Endpoints

Manual triggering and monitoring of entity deduplication.
"""

import logging
import time
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.security import verify_api_key
from app.services.deduplication.entity_deduplication import EntityDeduplicationService
from neo4j import GraphDatabase

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


class EntityTimestampStats(BaseModel):
    """Statistics about entity timestamps for deduplication monitoring."""
    total_entities: int
    entities_with_null_timestamp: int
    entities_with_timestamp: int
    null_timestamp_percentage: float
    recent_entities_last_24h: int
    recent_entities_last_1h: int


class DeduplicationStatusResponse(BaseModel):
    """Real-time status of deduplication system."""
    scheduler_enabled: bool
    interval_minutes: int
    similarity_threshold: float
    levenshtein_max_distance: int
    timestamp_stats: EntityTimestampStats
    estimated_next_run_entities: int


@router.post("/run", response_model=DeduplicationResponse)
async def run_deduplication(
    dry_run: bool = Query(False, description="If true, only preview duplicates without merging"),
    similarity_threshold: Optional[float] = Query(None, description="Cosine similarity threshold (0.0-1.0)"),
    levenshtein_max_distance: Optional[int] = Query(None, description="Max Levenshtein distance for name matching"),
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

    logger.info(f"Deduplication request: dry_run={dry_run}")

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
            logger.error(f"ALERT: High merge count - {results.get('entities_merged')} entities merged!")

        return DeduplicationResponse(
            success=True,
            results=results
        )

    except Exception as e:
        logger.error(f"Deduplication failed: {e}", exc_info=True)
        return DeduplicationResponse(
            success=False,
            results={"error": str(e)}
        )

    finally:
        service.close()


@router.get("/stats", response_model=DeduplicationStatsResponse)
async def get_deduplication_stats(
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
        logger.error(f"Failed to get stats: {e}", exc_info=True)
        raise

    finally:
        service.close()


@router.get("/status", response_model=DeduplicationStatusResponse)
async def get_deduplication_status(
    _ = Depends(verify_api_key)
):
    """
    Get real-time status of the deduplication system.

    Shows:
    - Configuration (enabled, interval, thresholds)
    - Entity timestamp statistics
    - How many entities will be checked in next run
    - Percentage of legacy entities (NULL timestamps)

    Use this to verify the scheduler is working and monitor deduplication health.
    """

    driver = GraphDatabase.driver(settings.neo4j_uri, auth=("neo4j", settings.neo4j_password))

    try:
        with driver.session(database="neo4j") as session:
            # Get timestamp statistics
            stats_query = """
            MATCH (e:__Entity__)
            WITH count(e) AS total,
                 sum(CASE WHEN e.created_at_timestamp IS NULL THEN 1 ELSE 0 END) AS null_count,
                 sum(CASE WHEN e.created_at_timestamp IS NOT NULL THEN 1 ELSE 0 END) AS has_timestamp_count

            // Calculate recent entities (last 24 hours)
            WITH total, null_count, has_timestamp_count, (timestamp() / 1000) AS now
            MATCH (e:__Entity__)
            WHERE e.created_at_timestamp IS NOT NULL
              AND e.created_at_timestamp >= (now - 86400)
            WITH total, null_count, has_timestamp_count, count(e) AS recent_24h, now

            // Calculate recent entities (last 1 hour)
            MATCH (e:__Entity__)
            WHERE e.created_at_timestamp IS NOT NULL
              AND e.created_at_timestamp >= (now - 3600)

            RETURN total, null_count, has_timestamp_count, recent_24h, count(e) AS recent_1h
            """

            result = session.run(stats_query)
            record = result.single()

            total = record["total"]
            null_count = record["null_count"]
            has_timestamp_count = record["has_timestamp_count"]
            recent_24h = record["recent_24h"]
            recent_1h = record["recent_1h"]

            # Calculate what next run will check (NULL + last 24h)
            estimated_next_run = null_count + recent_24h

            timestamp_stats = EntityTimestampStats(
                total_entities=total,
                entities_with_null_timestamp=null_count,
                entities_with_timestamp=has_timestamp_count,
                null_timestamp_percentage=round((null_count / total * 100) if total > 0 else 0, 1),
                recent_entities_last_24h=recent_24h,
                recent_entities_last_1h=recent_1h
            )

            return DeduplicationStatusResponse(
                scheduler_enabled=settings.dedup_enabled,
                interval_minutes=15,  # From scheduler.py
                similarity_threshold=settings.dedup_similarity_threshold,
                levenshtein_max_distance=settings.dedup_levenshtein_max_distance,
                timestamp_stats=timestamp_stats,
                estimated_next_run_entities=estimated_next_run
            )

    except Exception as e:
        logger.error(f"Failed to get deduplication status: {e}", exc_info=True)
        raise

    finally:
        driver.close()
