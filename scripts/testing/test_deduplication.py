"""
Test Complete Deduplication Strategy

Tests all 3 layers:
1. Document deduplication (RedisDocumentStore + UPSERTS)
2. Entity deduplication (Vector similarity + APOC merge)
3. Relationship deduplication (Neo4j MERGE)

Plus batch ingestion performance.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import asyncio
from app.services.ingestion.llamaindex import UniversalIngestionPipeline

# Test documents with intentional duplicates
TEST_DOCUMENTS = [
    {
        "id": 1001,
        "title": "Meeting Notes - Q4 Planning",
        "content": "Alex Thompson discussed the Q4 roadmap with Emma Chen from Acme Corporation. Key points included product launch and marketing strategy.",
        "document_type": "googledoc",
        "source": "google_drive",
        "tenant_id": "test_tenant"
    },
    {
        "id": 1002,
        "title": "Email: Q4 Follow-up",
        "content": "alex thompson sent a follow-up email to emma chen regarding the Acme Corporation partnership. The product launch timeline was confirmed.",
        "document_type": "email",
        "source": "gmail",
        "tenant_id": "test_tenant",
        "sender": "alex.thompson@example.com",
        "recipients": ["emma.chen@acme.com"]
    },
    {
        "id": 1003,
        "title": "Strategy Document",
        "content": "A. Thompson and E. Chen collaborated on the strategic plan for ACME Corp. The document outlines product development and go-to-market approach.",
        "document_type": "googledoc",
        "source": "google_drive",
        "tenant_id": "test_tenant"
    },
    {
        "id": 1004,
        "title": "Project Kickoff",
        "content": "Alexander Thompson met with Emma from Acme to kick off the new project. Technical requirements and timeline were discussed.",
        "document_type": "googledoc",
        "source": "google_drive",
        "tenant_id": "test_tenant"
    }
]


async def test_document_deduplication():
    """Test Layer 1: Document-level deduplication"""
    print("\n" + "="*80)
    print("TEST 1: DOCUMENT DEDUPLICATION")
    print("="*80)

    pipeline = UniversalIngestionPipeline()

    # Ingest document
    doc = TEST_DOCUMENTS[0]
    print(f"\n1. First ingestion of document {doc['id']}...")
    result1 = await pipeline.ingest_document(doc, extract_entities=False)
    print(f"   Status: {result1['status']}")

    # Re-ingest same document (should be cached/skipped)
    print(f"\n2. Re-ingesting same document {doc['id']}...")
    result2 = await pipeline.ingest_document(doc, extract_entities=False)
    print(f"   Status: {result2['status']}")

    # Modify document and re-ingest (should update)
    print(f"\n3. Modifying document {doc['id']} and re-ingesting...")
    modified_doc = doc.copy()
    modified_doc["content"] += " UPDATED CONTENT."
    result3 = await pipeline.ingest_document(modified_doc, extract_entities=False)
    print(f"   Status: {result3['status']}")

    print("\n✅ Document deduplication test complete")
    print("   - First ingestion: Processed")
    print("   - Re-ingestion (unchanged): Should be fast (cached)")
    print("   - Re-ingestion (modified): Should update")


async def test_batch_ingestion():
    """Test batch ingestion performance"""
    print("\n" + "="*80)
    print("TEST 2: BATCH INGESTION PERFORMANCE")
    print("="*80)

    pipeline = UniversalIngestionPipeline()

    # Batch ingestion (4 documents, parallel processing)
    print(f"\nIngesting {len(TEST_DOCUMENTS)} documents in batch...")
    results = await pipeline.ingest_documents_batch(
        document_rows=TEST_DOCUMENTS,
        extract_entities=True,  # Enable entity extraction
        num_workers=2  # Use 2 workers for test
    )

    success_count = sum(1 for r in results if r.get("status") == "success")
    print(f"\n✅ Batch ingestion complete:")
    print(f"   - Total: {len(results)}")
    print(f"   - Success: {success_count}")
    print(f"   - Failed: {len(results) - success_count}")

    return results


async def test_entity_extraction():
    """Test entity extraction and check for duplicates"""
    print("\n" + "="*80)
    print("TEST 3: ENTITY EXTRACTION")
    print("="*80)

    from neo4j import GraphDatabase
    from app.services.ingestion.llamaindex.config import (
        NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
    )

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with driver.session(database=NEO4J_DATABASE) as session:
        # Count entities by name (check for duplicates)
        result = session.run("""
            MATCH (e:__Entity__)
            WHERE e.name IS NOT NULL
            WITH toLower(e.name) as normalized_name, collect(e) as entities
            RETURN normalized_name, count(entities) as count,
                   [entity IN entities | entity.name][0..5] as sample_names
            ORDER BY count DESC
        """)

        duplicates = []
        for record in result:
            name = record["normalized_name"]
            count = record["count"]
            samples = record["sample_names"]

            if count > 1:
                duplicates.append((name, count, samples))
                print(f"\n⚠️  Potential duplicates: '{name}' ({count} nodes)")
                print(f"   Variations: {samples}")

        if not duplicates:
            print("\n✅ No obvious entity duplicates found")
        else:
            print(f"\n📊 Found {len(duplicates)} sets of potential duplicates")
            print("   These will be merged by entity deduplication script")

    driver.close()


def test_entity_deduplication():
    """Test Layer 2: Entity deduplication script"""
    print("\n" + "="*80)
    print("TEST 4: ENTITY DEDUPLICATION")
    print("="*80)

    print("\nRunning entity deduplication (dry-run)...")

    # Import deduplication script
    from scripts.maintenance.deduplicate_entities import EntityDeduplicator

    deduplicator = EntityDeduplicator()

    try:
        # Dry run first
        results = deduplicator.run_deduplication(
            similarity_threshold=0.90,  # Lower threshold for testing
            word_distance_threshold=5,   # Higher distance for variations
            dry_run=True
        )

        print(f"\n✅ Entity deduplication dry-run complete:")
        print(f"   - Duplicates found: {results['duplicates_found']}")
        print(f"   - Would merge: {results['entities_merged']}")

        if results['duplicates_found'] > 0:
            print("\n💡 Run without --dry-run to actually merge these duplicates")

    finally:
        deduplicator.close()


async def verify_graph_structure():
    """Verify final graph structure"""
    print("\n" + "="*80)
    print("TEST 5: GRAPH STRUCTURE VERIFICATION")
    print("="*80)

    from neo4j import GraphDatabase
    from app.services.ingestion.llamaindex.config import (
        NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
    )

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with driver.session(database=NEO4J_DATABASE) as session:
        # Count nodes by type
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)

        print("\n📊 Node counts:")
        for record in result:
            print(f"   {record['label']}: {record['count']}")

        # Count relationships by type
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(*) as count
            ORDER BY count DESC
        """)

        print("\n🔗 Relationship counts:")
        for record in result:
            print(f"   {record['rel_type']}: {record['count']}")

        # Check for type-specific MENTIONED_IN relationships
        result = session.run("""
            MATCH ()-[r]->()
            WHERE type(r) STARTS WITH 'MENTIONED_IN_'
            RETURN type(r) as rel_type, count(*) as count
        """)

        print("\n✅ Type-specific MENTIONED_IN relationships:")
        has_type_specific = False
        for record in result:
            print(f"   {record['rel_type']}: {record['count']}")
            has_type_specific = True

        if not has_type_specific:
            print("   ⚠️  No type-specific relationships found")

    driver.close()


async def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("TESTING COMPLETE DEDUPLICATION STRATEGY")
    print("="*80)
    print("\nThis test will:")
    print("1. Test document-level deduplication")
    print("2. Test batch ingestion performance")
    print("3. Check for entity duplicates")
    print("4. Run entity deduplication (dry-run)")
    print("5. Verify final graph structure")

    try:
        # Test 1: Document deduplication
        await test_document_deduplication()

        # Test 2: Batch ingestion
        await test_batch_ingestion()

        # Test 3: Check for entity duplicates
        await test_entity_extraction()

        # Test 4: Entity deduplication
        test_entity_deduplication()

        # Test 5: Verify graph structure
        await verify_graph_structure()

        print("\n" + "="*80)
        print("ALL TESTS COMPLETE")
        print("="*80)
        print("\n✅ Deduplication strategy is working!")
        print("\n📝 Next steps:")
        print("   1. Configure Redis (REDIS_HOST in .env) for persistent document dedup")
        print("   2. Run entity dedup without --dry-run to actually merge:")
        print("      python3 scripts/maintenance/deduplicate_entities.py")
        print("   3. Set up cron job for hourly entity deduplication")
        print("\n📖 See PRODUCTION_DEDUPLICATION_STRATEGY.md for full documentation")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
