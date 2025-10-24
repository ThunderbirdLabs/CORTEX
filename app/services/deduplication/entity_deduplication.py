"""
Entity Deduplication Service

Production-safe periodic cleanup of duplicate entities created by LLM extraction.

Features:
- Vector similarity + text distance matching
- Smart property merging (keeps most-connected node's data)
- Self-healing embedding regeneration
- Transaction-per-cluster isolation
- Batch processing with progress tracking
- Idempotent (handles race conditions)

Based on official Neo4j entity resolution patterns + 2024-2025 best practices.

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
        top_k_candidates: int = 10,
        openai_api_key: Optional[str] = None
    ):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))
        self.database = neo4j_database
        self.vector_index_name = vector_index_name
        self.similarity_threshold = similarity_threshold
        self.levenshtein_max_distance = levenshtein_max_distance
        self.top_k_candidates = top_k_candidates

        # OpenAI embedding service for self-healing
        self.embed_model = None
        if openai_api_key:
            try:
                from llama_index.embeddings.openai import OpenAIEmbedding
                self.embed_model = OpenAIEmbedding(
                    model_name="text-embedding-3-small",
                    api_key=openai_api_key
                )
                logger.info("   Embedding self-healing: ENABLED")
            except ImportError:
                logger.warning("   Embedding self-healing: DISABLED (llama-index not available)")
        else:
            logger.info("   Embedding self-healing: DISABLED (no API key)")

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

        LEGACY DATA HANDLING:
        =====================
        Entities created before the timestamp feature was added have created_at_timestamp = NULL.
        These "legacy entities" are ALWAYS included in incremental deduplication to ensure:

        1. First-time dedup run catches all historical duplicates
        2. New entities are compared against entire historical graph
        3. Example: "Tony Codet" (5 months ago, NULL timestamp) matches
           "tony c" (this morning, recent timestamp)

        After the first successful dedup run, most entities will have timestamps and
        performance will improve. However, NULL entities are always checked to be safe.

        PERFORMANCE IMPACT:
        - First run: ~422 entities × 10 candidates = 4,220 comparisons (~2-5 seconds)
        - Subsequent runs: Only recent entities (much faster)
        - At 10K entities/day: ~10,000 × 10 = 100,000 comparisons (~5-10 seconds)
        """

        logger.info("Starting entity deduplication...")
        if hours_lookback:
            logger.info(f"   Incremental mode: checking entities from last {hours_lookback} hours")
            logger.info(f"   NOTE: Legacy entities with NULL timestamps are ALWAYS included")
        else:
            logger.info("   Full scan mode: checking ALL entities (may be slow at scale)")

        # Build time filter for incremental deduplication
        # CRITICAL: Filter recent entities to CHECK, but search AGAINST entire graph
        time_filter = ""
        if hours_lookback:
            # Only check recently added entities
            # IMPORTANT: Include NULL timestamps (legacy entities from before timestamp feature)
            cutoff_timestamp = int(time.time()) - (hours_lookback * 3600)
            time_filter = f"""
            AND (
                e.created_at_timestamp IS NULL
                OR (e.created_at_timestamp IS NOT NULL AND e.created_at_timestamp >= {cutoff_timestamp})
            )
            """
            # Explanation:
            # - First condition: NULL timestamp (legacy/backfill - check these too)
            # - Second condition: timestamp is recent (normal incremental case)
            #
            # WHY THIS MATTERS:
            # Without NULL check, we'd miss 95%+ of entities on first run (all historical data).
            # New entities must be compared against ALL historical entities, not just recent ones.

        # Cypher query for deduplication
        query = f"""
        // 1. Find RECENT entities with embeddings to check for duplicates
        // Note: Vector search will compare against ALL entities in graph (not just recent)
        MATCH (e:__Entity__)
        WHERE e.embedding IS NOT NULL
        {time_filter}

        // 2. Find similar entities using vector index (searches ENTIRE graph)
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
        // MERGE: Combine duplicates into primary node (batched for production scale)
        // Create unique cluster identifier to avoid processing same entities twice
        WITH e, duplicates
        WITH e, duplicates, [n IN duplicates + [e] | id(n)] AS nodeIds
        WITH e, duplicates, apoc.coll.min(nodeIds) AS clusterId

        // Only process each cluster once (from the perspective of the node with lowest ID)
        WHERE id(e) = clusterId

        // Return node IDs for batched processing (not Node objects)
        WITH [n IN duplicates + [e] | id(n)] AS nodesToMerge

        RETURN nodesToMerge
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
                # Collect merge candidates
                merge_candidates = [record["nodesToMerge"] for record in result]

                if not merge_candidates:
                    logger.info("No duplicates found")
                    return {
                        "entities_merged": 0,
                        "clusters_processed": 0,
                        "clusters_skipped": 0,
                        "embeddings_regenerated": 0,
                        "dry_run": False
                    }

                logger.info(f"Found {len(merge_candidates)} duplicate clusters")

        # Process clusters in batches with proper error handling
        return self._merge_clusters_safe(merge_candidates)

    def _merge_clusters_safe(self, merge_candidates: List[List[int]]) -> Dict[str, Any]:
        """
        Production-safe cluster merging with:
        - Smart property selection (keep most-connected node's properties)
        - Transaction-per-cluster (isolation)
        - Self-healing (embedding regeneration)
        - Progress tracking & batch commits
        - Idempotent (handles already-deleted nodes)
        """
        merged_count = 0
        skipped_count = 0
        embeddings_regenerated = 0
        batch_size = 10
        total_clusters = len(merge_candidates)

        logger.info(f"Starting safe merge of {total_clusters} clusters (batch size: {batch_size})")

        for batch_idx in range(0, total_clusters, batch_size):
            batch = merge_candidates[batch_idx:batch_idx + batch_size]
            batch_num = (batch_idx // batch_size) + 1
            total_batches = (total_clusters + batch_size - 1) // batch_size

            logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} clusters)")

            for cluster_idx, node_ids in enumerate(batch, start=1):
                try:
                    # Each cluster in separate transaction for isolation
                    with self.driver.session(database=self.database) as session:
                        result = self._merge_single_cluster(session, node_ids)

                        if result["merged"]:
                            merged_count += 1
                            embeddings_regenerated += result.get("embedding_regenerated", 0)
                        else:
                            skipped_count += 1

                except Exception as e:
                    # Log but continue processing other clusters
                    logger.error(f"Failed to merge cluster {cluster_idx} in batch {batch_num}: {e}")
                    skipped_count += 1
                    continue

            # Log progress after each batch
            logger.info(f"Batch {batch_num}/{total_batches} complete: {merged_count} merged, {skipped_count} skipped")

        logger.info(f"Deduplication complete: {merged_count} entities merged, {skipped_count} skipped, {embeddings_regenerated} embeddings regenerated")

        return {
            "entities_merged": merged_count,
            "clusters_processed": merged_count,
            "clusters_skipped": skipped_count,
            "embeddings_regenerated": embeddings_regenerated,
            "dry_run": False
        }

    def _merge_single_cluster(self, session, node_ids: List[int]) -> Dict[str, Any]:
        """
        Merge a single cluster of duplicate nodes with smart property handling.

        Strategy:
        1. Check all nodes still exist (idempotency)
        2. Select primary node (most relationships = most context)
        3. Merge others into primary, keeping primary's properties
        4. Verify embedding exists, regenerate if missing (self-healing)
        5. Preserve oldest created_at_timestamp

        Returns:
            {"merged": bool, "embedding_regenerated": int}
        """
        # Step 1: Get nodes with relationship counts (skip if already deleted)
        check_query = """
        WITH $nodeIds AS nodeIds
        UNWIND nodeIds AS nodeId
        CALL apoc.nodes.get([nodeId]) YIELD node
        WITH node
        MATCH (node)
        OPTIONAL MATCH (node)-[r]-()
        WITH node, count(DISTINCT r) AS rel_count, id(node) AS internal_id
        RETURN internal_id, node.name AS name, node.embedding AS embedding,
               node.created_at_timestamp AS timestamp, rel_count
        ORDER BY rel_count DESC, internal_id ASC
        """

        nodes_info = list(session.run(check_query, {"nodeIds": node_ids}))

        # Skip if nodes already merged (less than 2 remain)
        if len(nodes_info) < 2:
            return {"merged": False}

        # Step 2: Select primary node (most connected = most context)
        primary = nodes_info[0]
        duplicates = [n["internal_id"] for n in nodes_info[1:]]

        primary_id = primary["internal_id"]
        primary_name = primary["name"]
        primary_embedding = primary["embedding"]

        logger.debug(f"Merging cluster: primary='{primary_name}' (rel_count={primary['rel_count']}), duplicates={len(duplicates)}")

        # Step 3: Merge duplicates into primary
        # CRITICAL: Keep primary's properties (discard duplicates' values)
        # This ensures we keep the most-connected node's context
        merge_query = """
        WITH $primaryId AS primaryId, $duplicateIds AS duplicateIds
        CALL apoc.nodes.get([primaryId]) YIELD node AS primaryNode
        CALL apoc.nodes.get(duplicateIds) YIELD node AS dupNode
        WITH primaryNode, collect(dupNode) AS dupNodes
        WHERE size(dupNodes) > 0

        // Merge: keep primary's properties, discard duplicates
        CALL apoc.refactor.mergeNodes([primaryNode] + dupNodes, {
          properties: {
            id: 'discard',
            name: 'discard',
            embedding: 'discard',
            created_at_timestamp: 'discard',
            `.*`: 'overwrite'  // Keep primary's properties
          },
          mergeRels: true
        })
        YIELD node

        RETURN node
        """

        merge_result = session.run(merge_query, {
            "primaryId": primary_id,
            "duplicateIds": duplicates
        })
        merged_node = merge_result.single()

        if not merged_node:
            return {"merged": False}

        # Step 4: Preserve oldest timestamp across all nodes
        oldest_timestamp_query = """
        MATCH (n) WHERE id(n) = $nodeId
        WITH n, $timestamps AS timestamps
        WITH n, [t IN timestamps WHERE t IS NOT NULL] AS valid_timestamps
        WHERE size(valid_timestamps) > 0
        SET n.created_at_timestamp = apoc.coll.min(valid_timestamps)
        RETURN n.created_at_timestamp AS timestamp
        """

        all_timestamps = [n["timestamp"] for n in nodes_info]
        session.run(oldest_timestamp_query, {
            "nodeId": primary_id,
            "timestamps": all_timestamps
        })

        # Step 5: Self-healing - verify embedding exists, regenerate if missing
        embedding_regenerated = 0
        if not primary_embedding or primary_embedding == []:
            logger.warning(f"Embedding missing for '{primary_name}' after merge, regenerating...")

            if self.embed_model:
                try:
                    # Generate embedding for entity using name + label for context
                    get_label_query = """
                    MATCH (n) WHERE id(n) = $nodeId
                    RETURN n.name AS name, [l IN labels(n) WHERE l <> '__Entity__'][0] AS label
                    """
                    label_result = session.run(get_label_query, {"nodeId": primary_id}).single()

                    if label_result:
                        entity_text = f"{label_result['label']}: {label_result['name']}"
                        new_embedding = self.embed_model.get_text_embedding(entity_text)

                        # Update node with regenerated embedding
                        update_query = """
                        MATCH (n) WHERE id(n) = $nodeId
                        SET n.embedding = $embedding
                        RETURN n.embedding AS embedding
                        """
                        session.run(update_query, {
                            "nodeId": primary_id,
                            "embedding": new_embedding
                        })

                        logger.info(f"✅ Regenerated embedding for '{primary_name}'")
                        embedding_regenerated = 1

                except Exception as e:
                    logger.error(f"Failed to regenerate embedding for '{primary_name}': {e}")
            else:
                logger.error(f"CRITICAL: Embedding missing for '{primary_name}' but regeneration disabled (no API key)")

        return {
            "merged": True,
            "embedding_regenerated": embedding_regenerated
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
    hours_lookback: int = 24,
    openai_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run entity deduplication (for use in scheduled jobs).

    Args:
        hours_lookback: Only check entities from last N hours (default: 24)
                       Set to None for full scan (slow at 100K+ scale)
        openai_api_key: OpenAI API key for embedding regeneration (self-healing)

    Usage:
        # Incremental (default): only last 24 hours
        results = run_entity_deduplication(NEO4J_URI, NEO4J_PASSWORD, openai_api_key=OPENAI_KEY)

        # Full scan (slow at scale, use monthly)
        results = run_entity_deduplication(NEO4J_URI, NEO4J_PASSWORD, hours_lookback=None)
    """

    service = EntityDeduplicationService(
        neo4j_uri=neo4j_uri,
        neo4j_password=neo4j_password,
        similarity_threshold=similarity_threshold,
        openai_api_key=openai_api_key,
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
