"""
Ingest all documents from Supabase documents table into Qdrant + Neo4j

This script:
1. Fetches all rows from the 'documents' table in Supabase
2. Runs them through UniversalIngestionPipeline
3. Stores chunks in Qdrant and entities in Neo4j

IMPORTANT: Only ONE ingestion can run at a time (enforced by file lock)
"""
import asyncio
import sys
import fcntl
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
from app.core.config import settings
from app.services.ingestion.llamaindex import UniversalIngestionPipeline


async def main():
    # Acquire file lock to prevent concurrent ingestion
    lock_file_path = "/tmp/cortex_ingestion.lock"
    lock_file = None
    try:
        lock_file = open(lock_file_path, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        print("=" * 80)
        print("⚠️  ANOTHER INGESTION IS ALREADY RUNNING")
        print("=" * 80)
        print("\nOnly ONE ingestion can run at a time to prevent:")
        print("  - Neo4j connection pool exhaustion")
        print("  - Qdrant write conflicts")
        print("  - Race conditions in entity deduplication")
        print("\nPlease wait for the current ingestion to complete.")
        print(f"Lock file: {lock_file_path}")
        if lock_file:
            lock_file.close()
        sys.exit(1)

    try:
        print("="*80)
        print("INGEST FROM SUPABASE DOCUMENTS TABLE")
        print("="*80)

        # Step 1: Connect to Supabase
        print("\n1️⃣ Connecting to Supabase...")
        supabase = create_client(settings.supabase_url, settings.supabase_service_key)

        # Fetch all documents
        result = supabase.table('documents').select('*').execute()
        documents = result.data
        print(f"   Found {len(documents)} documents in Supabase")

        if not documents:
            print("   ⚠️  No documents found - nothing to ingest")
            return

        # Show what we found
        print("\n   Documents to ingest:")
        for doc in documents:
            print(f"   - {doc.get('title', '(No title)')[:60]} ({doc.get('document_type')})")

        # Step 2: Initialize pipeline
        print("\n2️⃣ Initializing UniversalIngestionPipeline...")
        pipeline = UniversalIngestionPipeline()
        print("   ✅ Pipeline ready")

        # Step 3: Get initial counts for verification
        from qdrant_client import QdrantClient
        from neo4j import GraphDatabase

        qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
        qdrant_before = qdrant.get_collection(settings.qdrant_collection_name).points_count

        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password)
        )
        with driver.session(database="neo4j") as session:
            neo4j_before = session.run("MATCH (n) RETURN count(n) as count").single()["count"]

        # Step 4: Single-document ingestion
        print(f"\n3️⃣ Ingesting {len(documents)} documents...")
        print("   This will:")
        print("   - Chunk text and create embeddings → Qdrant")
        print("   - Extract entities and relationships → Neo4j")
        print()

        results = []
        for i, doc in enumerate(documents, 1):
            print(f"   [{i}/{len(documents)}] {doc.get('title', '(No title)')[:50]}...")
            try:
                await pipeline.ingest_document(
                    document_row=doc,
                    extract_entities=True
                )
                results.append({'status': 'success', 'title': doc.get('title')})
                print(f"      ✅ Success")
            except Exception as e:
                results.append({'status': 'error', 'title': doc.get('title'), 'error': str(e)})
                print(f"      ❌ Error: {e}")

        # Step 5: Show results
        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = sum(1 for r in results if r['status'] == 'error')

        print(f"\n4️⃣ Results:")
        print(f"   ✅ Success: {success_count}")
        print(f"   ❌ Errors: {error_count}")

        if error_count > 0:
            print("\n   Error details:")
            for r in results:
                if r['status'] == 'error':
                    print(f"   - {r.get('title', 'Unknown')}: {r.get('error', 'Unknown error')}")

        # Step 6: Verify data was actually written
        print("\n5️⃣ Verification...")

        # Check Qdrant
        qdrant_after = qdrant.get_collection(settings.qdrant_collection_name).points_count
        qdrant_added = qdrant_after - qdrant_before
        print(f"   Qdrant: {qdrant_before} → {qdrant_after} (+{qdrant_added} points)")

        # Check Neo4j
        with driver.session(database="neo4j") as session:
            neo4j_after = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
        neo4j_added = neo4j_after - neo4j_before
        print(f"   Neo4j: {neo4j_before} → {neo4j_after} (+{neo4j_added} nodes)")
        driver.close()

        # Warn if nothing was added despite "success"
        if success_count > 0 and qdrant_added == 0:
            print("\n   ⚠️  WARNING: Scripts reported success but Qdrant has 0 new points!")
            print("      This indicates a silent failure. Check Qdrant connection.")

        if success_count > 0 and neo4j_added == 0:
            print("\n   ⚠️  WARNING: Scripts reported success but Neo4j has 0 new nodes!")
            print("      This indicates entity extraction failed or connection issue.")

        print("\n" + "="*80)
        print("✅ INGESTION COMPLETE")
        print("="*80)
        print("\nYou can now:")
        print("1. Query via /api/v1/chat")
        print("2. Test with: 'What documents do I have?'")

    finally:
        # Release file lock
        if lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()


if __name__ == "__main__":
    asyncio.run(main())
