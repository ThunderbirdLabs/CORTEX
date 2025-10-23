"""
Entity Deduplication Service

Periodic cleanup of duplicate entities created by LLM extraction.
Uses vector similarity + text distance to find and merge duplicates.

Based on official Neo4j entity resolution patterns.

PERFORMANCE:
- Incremental mode (default): Only checks entities from last N hours
- Full scan mode: Checks ALL entities (slow at 100K+ scale, use sparingly)
"""

import logging
import time
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class EntityDeduplicationService:
    """
    Deduplicate entities using vector similarity and text distance.

    Algorithm:
    1. For each entity with embedding, find top K similar entities
    2. Filter by cosine similarity threshold (default 0.92)
    3. Apply text distance checks (substring match + Levenshtein)
    4. Merge duplicates using apoc.refactor.mergeNodes
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_password: str,
        neo4j_database: str = "neo4j",
        vector_index_name: str = "entity",
        similarity_threshold: float = 0.92,
        levenshtein_max_distance: int = 3,
        top_k_candidates: int = 10
    ):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))
        self.database = neo4j_database
        self.vector_index_name = vector_index_name
        self.similarity_threshold = similarity_threshold
        self.levenshtein_max_distance = levenshtein_max_distance
        self.top_k_candidates = top_k_candidates

        logger.info("EntityDeduplicationService initialized")
        logger.info(f"   Vector index: {vector_index_name}")
        logger.info(f"   Similarity threshold: {similarity_threshold}")
        logger.info(f"   Levenshtein max distance: {levenshtein_max_distance}")

    def deduplicate_entities(self, dry_run: bool = False, hours_lookback: Optional[int] = None) -> Dict[str, Any]:
        """
        Find and merge duplicate entities.

        Args:
            dry_run: If True, only report duplicates without merging
            hours_lookback: Only check entities created in last N hours (for incremental dedup)
                          If None, checks all entities (full scan - slow at scale)

        Returns:
            Dict with results: {
                "duplicates_found": int,
                "entities_merged": int,
                "clusters": List[Dict]
            }
        """

        logger.info("Starting entity deduplication...")
        if hours_lookback:
            logger.info(f"   Incremental mode: checking entities from last {hours_lookback} hours")
        else:
            logger.info("   Full scan mode: checking ALL entities (may be slow at scale)")

        # Build time filter for incremental deduplication
        time_filter = ""
        if hours_lookback:
            # Only check recently added entities
            cutoff_timestamp = int(time.time()) - (hours_lookback * 3600)
            time_filter = f"AND e.created_at_timestamp >= {cutoff_timestamp}"

        # Cypher query for deduplication
        query = f"""
        // 1. Find entities with embeddings (optionally filtered by time)
        MATCH (e:__Entity__)
        WHERE e.embedding IS NOT NULL
        {time_filter}

        // 2. Find similar entities using vector index
        CALL db.index.vector.queryNodes($index_name, $top_k, e.embedding)
        YIELD node, score

        // 3. Filter by similarity threshold + text distance
        WHERE score > toFloat($similarity_threshold)
          AND node.id <> e.id
          AND (
            toLower(node.name) CONTAINS toLower(e.name)
            OR toLower(e.name) CONTAINS toLower(node.name)
            OR apoc.text.distance(toLower(node.name), toLower(e.name)) < $max_distance
          )

        // 4. Group duplicates
        WITH e, collect(DISTINCT node) AS duplicates, collect(score) AS scores
        WHERE size(duplicates) > 0

        """ + ("""
        // DRY RUN: Just return clusters
        WITH e, duplicates, scores
        ORDER BY size(duplicates) DESC
        RETURN e.name AS primary_name,
               e.id AS primary_id,
               [d in duplicates | d.name] AS duplicate_names,
               [d in duplicates | d.id] AS duplicate_ids,
               scores
        LIMIT 100
        """ if dry_run else """
        // MERGE: Combine duplicates into primary node
        // Create unique cluster identifier to avoid processing same entities twice
        WITH e, duplicates
        WITH e, duplicates, [n IN duplicates + [e] | id(n)] AS nodeIds
        WITH e, duplicates, apoc.coll.min(nodeIds) AS clusterId

        // Only process each cluster once (from the perspective of the node with lowest ID)
        WHERE id(e) = clusterId

        WITH duplicates + [e] AS nodesToMerge

        // CRITICAL: Must discard 'id' to prevent array IDs
        // If 'id' is combined, it creates arrays like ['Cortex', 'Cortex Solutions']
        // This breaks Neo4j queries that expect single string values (e.g., toString())
        CALL apoc.refactor.mergeNodes(nodesToMerge, {
          properties: {
            id: 'discard',
            name: 'discard',
            embedding: 'discard',
            `.*`: 'combine'
          },
          mergeRels: true
        })
        YIELD node

        RETURN count(node) AS merged_count
        """)

        with self.driver.session(database=self.database) as session:
            result = session.run(query, {
                "index_name": self.vector_index_name,
                "top_k": self.top_k_candidates,
                "similarity_threshold": self.similarity_threshold,
                "max_distance": self.levenshtein_max_distance
            })

            if dry_run:
                clusters = []
                total_duplicates = 0

                for record in result:
                    cluster = {
                        "primary_name": record["primary_name"],
                        "primary_id": record["primary_id"],
                        "duplicate_names": record["duplicate_names"],
                        "duplicate_ids": record["duplicate_ids"],
                        "similarity_scores": record["scores"]
                    }
                    clusters.append(cluster)
                    total_duplicates += len(cluster["duplicate_names"])

                logger.info(f"Dry run complete: {total_duplicates} duplicates in {len(clusters)} clusters")

                return {
                    "duplicates_found": total_duplicates,
                    "clusters": clusters,
                    "dry_run": True
                }
            else:
                records = list(result)
                merged_count = sum(r["merged_count"] for r in records) if records else 0

                logger.info(f"Deduplication complete: {merged_count} entities merged")

                return {
                    "entities_merged": merged_count,
                    "dry_run": False
                }

    def get_deduplication_stats(self) -> Dict[str, Any]:
        """Get statistics about potential duplicates."""

        query = """
        // Count entities with/without embeddings
        MATCH (e:__Entity__)
        WITH count(e) AS total_entities,
             sum(CASE WHEN e.embedding IS NOT NULL THEN 1 ELSE 0 END) AS entities_with_embeddings

        RETURN total_entities, entities_with_embeddings
        """

        with self.driver.session(database=self.database) as session:
            result = session.run(query)
            record = result.single()

            return {
                "total_entities": record["total_entities"],
                "entities_with_embeddings": record["entities_with_embeddings"],
                "entities_without_embeddings": record["total_entities"] - record["entities_with_embeddings"]
            }

    def should_alert(self, results: Dict[str, Any]) -> bool:
        """Alert if deduplication merges suspiciously high number of entities."""

        merged_count = results.get("entities_merged", 0)

        # Alert if >100 entities merged in single run (possible threshold misconfiguration)
        if merged_count > 100:
            logger.warning(f"High merge count: {merged_count} entities merged!")
            return True

        return False

    def close(self):
        """Close Neo4j driver."""
        self.driver.close()


# Convenience function for scheduled jobs
def run_entity_deduplication(
    neo4j_uri: str,
    neo4j_password: str,
    dry_run: bool = False,
    similarity_threshold: float = 0.92,
    levenshtein_max_distance: int = 3,
    hours_lookback: int = 24
) -> Dict[str, Any]:
    """
    Run entity deduplication (for use in scheduled jobs).

    Args:
        hours_lookback: Only check entities from last N hours (default: 24)
                       Set to None for full scan (slow at 100K+ scale)

    Usage:
        # Incremental (default): only last 24 hours
        results = run_entity_deduplication(NEO4J_URI, NEO4J_PASSWORD)

        # Full scan (slow at scale, use monthly)
        results = run_entity_deduplication(NEO4J_URI, NEO4J_PASSWORD, hours_lookback=None)
    """

    service = EntityDeduplicationService(
        neo4j_uri=neo4j_uri,
        neo4j_password=neo4j_password,
        similarity_threshold=similarity_threshold,
        levenshtein_max_distance=levenshtein_max_distance
    )

    try:
        results = service.deduplicate_entities(dry_run=dry_run, hours_lookback=hours_lookback)

        # Check for alerts
        if not dry_run and service.should_alert(results):
            logger.error(f"ALERT: Deduplication merged {results.get('entities_merged')} entities - review thresholds!")

        return results
    finally:
        service.close()
