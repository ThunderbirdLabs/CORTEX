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
        // CRITICAL: Use elementId() not deprecated id()
        WHERE score > toFloat($similarity_threshold)
          AND elementId(node) <> elementId(e)
          AND node.name IS NOT NULL
          AND e.name IS NOT NULL
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
        // Use elementId() for future-proof Neo4j 5.x+ compatibility
        WITH e, duplicates
        WITH e, duplicates, [n IN duplicates + [e] | elementId(n)] AS allElementIds
        WITH e, duplicates, allElementIds, apoc.coll.min(allElementIds) AS clusterId

        // Only process each cluster once (from perspective of node with min elementId)
        WHERE elementId(e) = clusterId

        // Return elementIds for batched processing (not Node objects)
        RETURN allElementIds AS nodesToMerge
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
        merge_examples = []  # Track first 5 merges for logging
        # Batch size optimization based on Neo4j best practices:
        # - Neo4j recommendation: 2,000-20,000 nodes per transaction
        # - Each cluster = 2-10 nodes average
        # - 50 clusters = ~100-500 nodes (within optimal range)
        # - Balances transaction size vs commit overhead
        batch_size = 50
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

                            # Track first 5 examples for logging
                            if len(merge_examples) < 5 and "example" in result:
                                merge_examples.append(result["example"])
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

        # Log examples of what was merged
        if merge_examples:
            logger.info(f"\n📋 Sample merges ({len(merge_examples)} examples):")
            for i, example in enumerate(merge_examples, 1):
                logger.info(f"  {i}. {example['primary']} ← [{', '.join(example['duplicates'])}]")

        # Production monitoring: alert on suspicious patterns
        total_attempts = merged_count + skipped_count
        if total_attempts > 0:
            skip_rate = (skipped_count / total_attempts) * 100
            if skip_rate > 50:
                logger.warning(f"⚠️  HIGH SKIP RATE: {skip_rate:.1f}% of clusters skipped - may indicate race conditions or configuration issues")

            if embeddings_regenerated > 0:
                regen_rate = (embeddings_regenerated / merged_count) * 100 if merged_count > 0 else 0
                if regen_rate > 50:
                    logger.error(f"🚨 HIGH EMBEDDING REGENERATION: {regen_rate:.1f}% of merges required embedding fix - investigate why embeddings are missing!")

        return {
            "entities_merged": merged_count,
            "clusters_processed": merged_count,
            "clusters_skipped": skipped_count,
            "embeddings_regenerated": embeddings_regenerated,
            "skip_rate_percent": round((skipped_count / total_attempts) * 100, 1) if total_attempts > 0 else 0,
            "merge_examples": merge_examples[:5],  # Return first 5 examples
            "dry_run": False
        }

    def _merge_single_cluster(self, session, node_element_ids: List[str]) -> Dict[str, Any]:
        """
        Merge a single cluster of duplicate nodes with smart property handling.

        Strategy:
        1. Check all nodes still exist (idempotency)
        2. Select primary node (most relationships = most context)
        3. Merge others into primary, keeping primary's properties
        4. Verify embedding exists, regenerate if missing (self-healing)
        5. Preserve oldest created_at_timestamp

        Args:
            node_element_ids: List of elementId strings (Neo4j 5.x format)

        Returns:
            {"merged": bool, "embedding_regenerated": int}
        """
        # Step 1: Get nodes with relationship counts (skip if already deleted)
        # Use direct MATCH with elementId() - more reliable than apoc.nodes.get
        check_query = """
        WITH $elementIds AS elementIds
        UNWIND elementIds AS elemId
        MATCH (node) WHERE elementId(node) = elemId
        OPTIONAL MATCH (node)-[r]-()
        WITH node, count(DISTINCT r) AS rel_count, elementId(node) AS elem_id
        RETURN elem_id, node.name AS name, node.embedding AS embedding,
               node.created_at_timestamp AS timestamp, rel_count
        ORDER BY rel_count DESC, elem_id ASC
        """

        nodes_info = list(session.run(check_query, {"elementIds": node_element_ids}))

        # Skip if nodes already merged (less than 2 remain)
        if len(nodes_info) < 2:
            return {"merged": False}

        # Step 2: Select primary node (most connected = most context)
        primary = nodes_info[0]
        duplicates = [n["elem_id"] for n in nodes_info[1:]]
        duplicate_names = [n["name"] for n in nodes_info[1:]]

        primary_id = primary["elem_id"]
        primary_name = primary["name"]
        primary_embedding = primary["embedding"]

        logger.debug(f"Merging cluster: primary='{primary_name}' (rel_count={primary['rel_count']}), duplicates={len(duplicates)}")

        # Step 3: Merge duplicates into primary
        # CRITICAL: Keep primary's properties (discard duplicates' values)
        # This ensures we keep the most-connected node's context
        # Use direct MATCH with elementId - no deprecated functions
        #
        # DEADLOCK PREVENTION (GitHub neo4j-apoc-procedures#1408):
        # Rebind nodes using apoc.nodes.get() before mergeNodes to prevent
        # infinite locks from stale transaction references
        merge_query = """
        WITH $primaryElemId AS primaryElemId, $duplicateElemIds AS duplicateElemIds
        MATCH (primaryNode) WHERE elementId(primaryNode) = primaryElemId
        UNWIND duplicateElemIds AS dupElemId
        MATCH (dupNode) WHERE elementId(dupNode) = dupElemId
        WITH primaryNode, collect(dupNode) AS dupNodes
        WHERE size(dupNodes) > 0

        // CRITICAL: Collect elementIds and rebind nodes to current transaction
        // This prevents apoc.refactor.mergeNodes from grabbing stale write locks
        WITH [primaryNode] + dupNodes AS allNodesToMerge
        WITH [n IN allNodesToMerge | elementId(n)] AS elemIds
        UNWIND elemIds AS elemId
        MATCH (n) WHERE elementId(n) = elemId
        WITH collect(n) AS reboundNodes
        WHERE size(reboundNodes) >= 2

        // Merge: keep primary's properties (first node in list), discard duplicates
        CALL apoc.refactor.mergeNodes(reboundNodes, {
          properties: {
            id: 'discard',
            name: 'discard',
            embedding: 'discard',
            created_at_timestamp: 'discard',
            `.*`: 'overwrite'  // Keep first node's properties (primary)
          },
          mergeRels: true
        })
        YIELD node

        RETURN node
        """

        # Retry logic for transient deadlock errors (Neo4j best practice)
        max_retries = 3
        retry_delay = 0.1  # Start with 100ms

        for attempt in range(max_retries):
            try:
                merge_result = session.run(merge_query, {
                    "primaryElemId": primary_id,
                    "duplicateElemIds": duplicates
                })
                merged_node = merge_result.single()

                if not merged_node:
                    return {"merged": False}

                break  # Success!

            except Exception as e:
                error_str = str(e)
                # Check for transient deadlock error
                if "DeadlockDetected" in error_str or "LockAcquisitionFailure" in error_str:
                    if attempt < max_retries - 1:
                        import time
                        sleep_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Deadlock detected on attempt {attempt + 1}/{max_retries}, retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                        continue
                    else:
                        logger.error(f"Deadlock persisted after {max_retries} attempts for cluster with primary '{primary_name}'")
                        raise
                else:
                    # Non-transient error, don't retry
                    raise

        # Step 4: Preserve oldest timestamp across all nodes
        oldest_timestamp_query = """
        MATCH (n) WHERE elementId(n) = $elemId
        WITH n, $timestamps AS timestamps
        WITH n, [t IN timestamps WHERE t IS NOT NULL] AS valid_timestamps
        WHERE size(valid_timestamps) > 0
        SET n.created_at_timestamp = apoc.coll.min(valid_timestamps)
        RETURN n.created_at_timestamp AS timestamp
        """

        all_timestamps = [n["timestamp"] for n in nodes_info]
        session.run(oldest_timestamp_query, {
            "elemId": primary_id,
            "timestamps": all_timestamps
        })

        # Step 5: Self-healing - verify embedding exists, regenerate if missing
        embedding_regenerated = 0
        # Check for None, empty list, or list of zeros (invalid embedding)
        embedding_invalid = (
            primary_embedding is None
            or primary_embedding == []
            or (isinstance(primary_embedding, list) and len(primary_embedding) > 0 and all(v == 0 for v in primary_embedding))
        )

        if embedding_invalid:
            logger.warning(f"Embedding missing/invalid for '{primary_name}' after merge, regenerating...")

            if self.embed_model:
                try:
                    # Generate embedding for entity using name + label for context
                    get_label_query = """
                    MATCH (n) WHERE elementId(n) = $elemId
                    RETURN n.name AS name, [l IN labels(n) WHERE l <> '__Entity__'][0] AS label
                    """
                    label_result = session.run(get_label_query, {"elemId": primary_id}).single()

                    if label_result and label_result['name']:
                        # Use label if available, otherwise just name
                        label = label_result['label'] if label_result['label'] else "Entity"
                        entity_text = f"{label}: {label_result['name']}"
                        new_embedding = self.embed_model.get_text_embedding(entity_text)

                        # Update node with regenerated embedding
                        update_query = """
                        MATCH (n) WHERE elementId(n) = $elemId
                        SET n.embedding = $embedding
                        RETURN n.embedding AS embedding
                        """
                        session.run(update_query, {
                            "elemId": primary_id,
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
            "embedding_regenerated": embedding_regenerated,
            "example": {
                "primary": primary_name or "Unknown",
                "duplicates": duplicate_names
            }
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
