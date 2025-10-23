"""
Entity Deduplication Script for Continuous Production Ingestion

This script implements the expert-recommended 3-layer deduplication strategy:
1. Document-level: Handled by RedisDocumentStore + UPSERTS (automatic)
2. Entity-level: Vector similarity + word distance (THIS SCRIPT)
3. Relationship-level: Neo4j MERGE (automatic)

Run this script:
- Hourly via cron/scheduler for continuous production
- On-demand after large ingestions
- Weekly for deep cleaning

Algorithm:
1. Create vector index on entity embeddings
2. Find duplicate candidates using cosine similarity
3. Filter by word edit distance (Levenshtein)
4. Merge duplicate nodes with APOC (preserves all relationships)

Based on:
- Neo4j/LlamaIndex official guide (April 2025)
- Expert recommendations for 24/7 continuous ingestion
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import logging
from typing import Dict, List, Tuple
from neo4j import GraphDatabase
from llama_index.embeddings.openai import OpenAIEmbedding

from app.services.ingestion.llamaindex.config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE,
    OPENAI_API_KEY, EMBEDDING_MODEL
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EntityDeduplicator:
    """
    Entity deduplication using vector similarity + word distance.

    Identifies and merges duplicate entities like:
    - "Alex Thompson", "alex thompson", "A. Thompson" → single node
    - "Microsoft", "MSFT", "Microsoft Corp" → single node

    Critical for continuous ingestion where LLM extracts same entity
    with slight variations across documents.
    """

    def __init__(
        self,
        neo4j_uri: str = NEO4J_URI,
        neo4j_username: str = NEO4J_USERNAME,
        neo4j_password: str = NEO4J_PASSWORD,
        neo4j_database: str = NEO4J_DATABASE,
        embedding_model: str = EMBEDDING_MODEL,
        openai_api_key: str = OPENAI_API_KEY
    ):
        self.driver = GraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_username, neo4j_password)
        )
        self.database = neo4j_database

        # OpenAI embedding model (same as ingestion pipeline)
        self.embed_model = OpenAIEmbedding(
            model_name=embedding_model,
            api_key=openai_api_key
        )

        logger.info(f"✅ EntityDeduplicator initialized")
        logger.info(f"   Neo4j: {neo4j_uri}")
        logger.info(f"   Database: {neo4j_database}")
        logger.info(f"   Embedding model: {embedding_model}")

    def setup_vector_index(self):
        """
        Create vector index for entity embeddings.
        Required for fast similarity search.
        """
        logger.info("\n" + "="*80)
        logger.info("SETTING UP VECTOR INDEX")
        logger.info("="*80)

        with self.driver.session(database=self.database) as session:
            # Check if index already exists
            result = session.run("""
                SHOW INDEXES
                YIELD name, type
                WHERE name = 'entity_dedup_vector_index'
                RETURN count(*) as count
            """)

            if result.single()["count"] > 0:
                logger.info("✅ Vector index 'entity_dedup_vector_index' already exists")
                return

            # Create vector index on __Entity__ nodes
            try:
                session.run("""
                    CREATE VECTOR INDEX entity_dedup_vector_index IF NOT EXISTS
                    FOR (m:__Entity__)
                    ON m.embedding
                    OPTIONS {indexConfig: {
                        `vector.dimensions`: 1536,
                        `vector.similarity_function`: 'cosine'
                    }}
                """)
                logger.info("✅ Created vector index 'entity_dedup_vector_index'")
                logger.info("   Dimensions: 1536")
                logger.info("   Similarity: cosine")
            except Exception as e:
                logger.error(f"❌ Failed to create vector index: {e}")
                raise

    def generate_embeddings(self, batch_size: int = 100):
        """
        Generate embeddings for entities that don't have them.
        Only processes entities without embeddings (efficient for continuous ingestion).
        """
        logger.info("\n" + "="*80)
        logger.info("GENERATING ENTITY EMBEDDINGS")
        logger.info("="*80)

        with self.driver.session(database=self.database) as session:
            # Count entities without embeddings
            result = session.run("""
                MATCH (e:__Entity__)
                WHERE e.embedding IS NULL
                RETURN count(e) as count
            """)
            total = result.single()["count"]

            if total == 0:
                logger.info("✅ All entities already have embeddings")
                return

            logger.info(f"📊 Found {total} entities without embeddings")

            # Fetch entities in batches
            offset = 0
            processed = 0

            while offset < total:
                # Get batch of entities
                result = session.run("""
                    MATCH (e:__Entity__)
                    WHERE e.embedding IS NULL
                    RETURN e.name as name, elementId(e) as element_id
                    SKIP $offset
                    LIMIT $batch_size
                """, offset=offset, batch_size=batch_size)

                entities = list(result)
                if not entities:
                    break

                # Generate embeddings
                names = [e["name"] for e in entities]
                embeddings = self.embed_model.get_text_embedding_batch(names)

                # Update Neo4j
                for entity, embedding in zip(entities, embeddings):
                    session.run("""
                        MATCH (e:__Entity__)
                        WHERE elementId(e) = $element_id
                        SET e.embedding = $embedding
                    """, element_id=entity["element_id"], embedding=embedding)

                processed += len(entities)
                offset += batch_size

                logger.info(f"   Processed {processed}/{total} entities...")

            logger.info(f"✅ Generated embeddings for {processed} entities")

    def find_duplicates(
        self,
        similarity_threshold: float = 0.92,
        word_distance_threshold: int = 3,
        limit_per_entity: int = 10
    ) -> List[Tuple[str, str, float, int]]:
        """
        Find duplicate entity candidates using vector similarity + word distance.

        Args:
            similarity_threshold: Cosine similarity cutoff (0.92 = 92% similar)
            word_distance_threshold: Max Levenshtein distance (3 = 3 character edits)
            limit_per_entity: Max duplicates to check per entity

        Returns:
            List of (entity1_id, entity2_id, similarity_score, edit_distance) tuples
        """
        logger.info("\n" + "="*80)
        logger.info("FINDING DUPLICATE ENTITIES")
        logger.info("="*80)
        logger.info(f"   Similarity threshold: {similarity_threshold}")
        logger.info(f"   Word distance threshold: {word_distance_threshold}")

        with self.driver.session(database=self.database) as session:
            # Find duplicates using vector similarity + word distance
            result = session.run("""
                MATCH (e1:__Entity__)
                WHERE e1.embedding IS NOT NULL

                CALL db.index.vector.queryNodes(
                    'entity_dedup_vector_index',
                    $limit_per_entity,
                    e1.embedding
                )
                YIELD node as e2, score

                WHERE elementId(e1) < elementId(e2)  // Avoid duplicate pairs
                  AND score >= $similarity_threshold
                  AND apoc.text.levenshteinDistance(
                        toLower(e1.name),
                        toLower(e2.name)
                      ) <= $word_distance_threshold

                RETURN
                    elementId(e1) as id1,
                    e1.name as name1,
                    elementId(e2) as id2,
                    e2.name as name2,
                    score,
                    apoc.text.levenshteinDistance(
                        toLower(e1.name),
                        toLower(e2.name)
                    ) as edit_distance
                ORDER BY score DESC
            """,
            similarity_threshold=similarity_threshold,
            word_distance_threshold=word_distance_threshold,
            limit_per_entity=limit_per_entity
            )

            duplicates = []
            for record in result:
                duplicates.append({
                    "id1": record["id1"],
                    "name1": record["name1"],
                    "id2": record["id2"],
                    "name2": record["name2"],
                    "similarity": record["score"],
                    "edit_distance": record["edit_distance"]
                })

            logger.info(f"✅ Found {len(duplicates)} duplicate pairs")

            if duplicates:
                logger.info("\n📋 Sample duplicates:")
                for dup in duplicates[:10]:
                    logger.info(f"   '{dup['name1']}' ↔ '{dup['name2']}' "
                              f"(similarity: {dup['similarity']:.3f}, "
                              f"edit_distance: {dup['edit_distance']})")

            return duplicates

    def merge_duplicates(
        self,
        duplicates: List[Dict],
        dry_run: bool = False
    ) -> int:
        """
        Merge duplicate entity nodes using APOC.

        Preserves:
        - All relationships from both nodes
        - Combined properties (first node wins for conflicts)

        Args:
            duplicates: List of duplicate pairs from find_duplicates()
            dry_run: If True, only show what would be merged (don't actually merge)

        Returns:
            Number of nodes merged
        """
        if not duplicates:
            logger.info("✅ No duplicates to merge")
            return 0

        logger.info("\n" + "="*80)
        if dry_run:
            logger.info("DRY RUN: WOULD MERGE THESE DUPLICATES")
        else:
            logger.info("MERGING DUPLICATE ENTITIES")
        logger.info("="*80)

        merged_count = 0

        with self.driver.session(database=self.database) as session:
            for dup in duplicates:
                if dry_run:
                    logger.info(f"   Would merge: '{dup['name1']}' ← '{dup['name2']}'")
                    merged_count += 1
                else:
                    try:
                        # Merge e2 into e1 (keep e1, delete e2)
                        session.run("""
                            MATCH (e1:__Entity__)
                            WHERE elementId(e1) = $id1

                            MATCH (e2:__Entity__)
                            WHERE elementId(e2) = $id2

                            // Merge nodes (e1 is primary, e2 gets merged into it)
                            CALL apoc.refactor.mergeNodes([e1, e2], {
                                properties: 'discard',  // Keep e1 properties
                                mergeRels: true         // Combine all relationships
                            })
                            YIELD node

                            RETURN node.name as merged_name
                        """, id1=dup["id1"], id2=dup["id2"])

                        logger.info(f"   ✅ Merged: '{dup['name1']}' ← '{dup['name2']}'")
                        merged_count += 1
                    except Exception as e:
                        logger.error(f"   ❌ Failed to merge '{dup['name1']}' ← '{dup['name2']}': {e}")

        if dry_run:
            logger.info(f"\n📊 Would merge {merged_count} duplicate pairs")
        else:
            logger.info(f"\n✅ Merged {merged_count} duplicate pairs")

        return merged_count

    def run_deduplication(
        self,
        similarity_threshold: float = 0.92,
        word_distance_threshold: int = 3,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Complete deduplication workflow.

        Steps:
        1. Setup vector index (if needed)
        2. Generate embeddings for new entities
        3. Find duplicates
        4. Merge duplicates

        Args:
            similarity_threshold: Cosine similarity cutoff (0.92 = 92% similar)
            word_distance_threshold: Max Levenshtein distance (3 = 3 character edits)
            dry_run: If True, only show what would be merged

        Returns:
            Dictionary with statistics
        """
        logger.info("\n" + "="*80)
        logger.info("ENTITY DEDUPLICATION WORKFLOW")
        logger.info("="*80)

        # Step 1: Setup vector index
        self.setup_vector_index()

        # Step 2: Generate embeddings
        self.generate_embeddings()

        # Step 3: Find duplicates
        duplicates = self.find_duplicates(
            similarity_threshold=similarity_threshold,
            word_distance_threshold=word_distance_threshold
        )

        # Step 4: Merge duplicates
        merged_count = self.merge_duplicates(duplicates, dry_run=dry_run)

        # Summary
        logger.info("\n" + "="*80)
        logger.info("DEDUPLICATION COMPLETE")
        logger.info("="*80)
        logger.info(f"✅ Found {len(duplicates)} duplicate pairs")
        logger.info(f"✅ Merged {merged_count} entities")

        return {
            "duplicates_found": len(duplicates),
            "entities_merged": merged_count,
            "dry_run": dry_run
        }

    def close(self):
        """Close Neo4j driver."""
        self.driver.close()


def main():
    """
    Run entity deduplication.

    Usage:
        python3 scripts/maintenance/deduplicate_entities.py [--dry-run]
    """
    import argparse

    parser = argparse.ArgumentParser(description="Deduplicate entities in Neo4j knowledge graph")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without actually merging"
    )
    parser.add_argument(
        "--similarity",
        type=float,
        default=0.92,
        help="Similarity threshold (0.0-1.0, default: 0.92)"
    )
    parser.add_argument(
        "--word-distance",
        type=int,
        default=3,
        help="Max word edit distance (default: 3)"
    )

    args = parser.parse_args()

    deduplicator = EntityDeduplicator()

    try:
        results = deduplicator.run_deduplication(
            similarity_threshold=args.similarity,
            word_distance_threshold=args.word_distance,
            dry_run=args.dry_run
        )

        if args.dry_run:
            logger.info("\n💡 Run without --dry-run to actually merge duplicates")

        return 0

    except Exception as e:
        logger.error(f"❌ Deduplication failed: {e}", exc_info=True)
        return 1

    finally:
        deduplicator.close()


if __name__ == "__main__":
    sys.exit(main())
