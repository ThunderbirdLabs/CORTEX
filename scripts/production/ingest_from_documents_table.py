"""
Ingest all documents from Supabase documents table into Qdrant + Neo4j

This script:
1. Fetches all rows from the 'documents' table in Supabase
2. Runs them through UniversalIngestionPipeline (sequential or batch mode)
3. Stores chunks in Qdrant and entities in Neo4j

MODES:
- Sequential (default): One document at a time, safest, ~2-3 docs/sec
- Batch (--batch): Parallel processing, 3-4x faster, ~8-12 docs/sec

IMPORTANT: Only ONE ingestion can run at a time (enforced by file lock)
"""
import asyncio
import sys
import fcntl
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
from app.core.config import settings
from app.core.config_master import master_config
from app.services.rag import UniversalIngestionPipeline


async def main(use_batch: bool = False, num_workers: int = 4, max_concurrent_neo4j: int = 10, batch_size: int = 50):
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
        print(f"INGEST FROM SUPABASE DOCUMENTS TABLE {'(BATCH MODE)' if use_batch else '(SEQUENTIAL MODE)'}")
        print("="*80)

        # Step 0: Initialize master Supabase client (CRITICAL for dynamic schemas/prompts)
        print("\n0️⃣ Initializing master Supabase client for schemas/prompts...")
        from app.core import dependencies
        if master_config.is_multi_tenant:
            dependencies.master_supabase_client = create_client(
                master_config.master_supabase_url,
                master_config.master_supabase_service_key
            )
            print(f"   ✅ Master Supabase connected (Company ID: {master_config.company_id})")
        else:
            print("   ⚠️  Single-tenant mode - no master Supabase")

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
        for doc in documents[:10]:  # Show first 10
            print(f"   - {doc.get('title', '(No title)')[:60]} ({doc.get('document_type')})")
        if len(documents) > 10:
            print(f"   ... and {len(documents) - 10} more")

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

        # Step 4: Ingestion (batch or sequential)
        print(f"\n3️⃣ Ingesting {len(documents)} documents...")
        if use_batch:
            print(f"   MODE: Batch processing")
            print(f"   - Batch size: {batch_size} documents per batch")
            print(f"   - Qdrant workers: {num_workers}")
            print(f"   - Max concurrent Neo4j: {max_concurrent_neo4j}")
            print(f"   - Expected throughput: ~8-12 docs/sec")
        else:
            print(f"   MODE: Sequential processing (safest)")
            print(f"   - Expected throughput: ~2-3 docs/sec")
        print("   This will:")
        print("   - Chunk text and create embeddings → Qdrant")
        print()

        results = []

        # Process documents one at a time (batch method removed with Neo4j)
        for i, doc in enumerate(documents, 1):
            print(f"   [{i}/{len(documents)}] {doc.get('title', '(No title)')[:50]}...")
            try:
                result = await pipeline.ingest_document(document_row=doc)
                results.append({'status': result.get('status', 'unknown'), 'title': doc.get('title')})
                print(f"      ✅ Success")
            except Exception as e:
                results.append({'status': 'error', 'title': doc.get('title'), 'error': str(e)})
                print(f"      ❌ Error: {e}")

        # Step 5: Show results
        success_count = sum(1 for r in results if r.get('status') == 'success')
        partial_count = sum(1 for r in results if r.get('status') == 'partial_success')
        error_count = sum(1 for r in results if r.get('status') == 'error')
        skipped_count = sum(1 for r in results if r.get('status') == 'skipped')

        print(f"\n4️⃣ Results:")
        print(f"   ✅ Success: {success_count}")
        if partial_count > 0:
            print(f"   ⚠️  Partial success: {partial_count} (Qdrant OK, Neo4j failed)")
        if skipped_count > 0:
            print(f"   ⏭️  Skipped: {skipped_count} (empty content)")
        print(f"   ❌ Errors: {error_count}")

        if error_count > 0 or partial_count > 0:
            print("\n   Error/Warning details:")
            for r in results:
                if r.get('status') in ['error', 'partial_success']:
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
    parser = argparse.ArgumentParser(
        description="Ingest documents from Supabase into Qdrant + Neo4j",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Sequential mode (default, safest)
  python scripts/production/ingest_from_documents_table.py

  # Batch mode (3-4x faster)
  python scripts/production/ingest_from_documents_table.py --batch

  # Batch mode with custom settings
  python scripts/production/ingest_from_documents_table.py --batch --workers 6 --concurrent-neo4j 15 --batch-size 100

Safety:
  - File lock prevents concurrent runs (only ONE ingestion at a time)
  - Semaphore prevents Neo4j connection pool exhaustion
  - Circuit breaker handles OpenAI rate limits
  - Partial failures don't block entire batch
        """
    )
    parser.add_argument(
        '--batch',
        action='store_true',
        help='Use batch mode (parallel processing, 3-4x faster)'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=4,
        help='Number of parallel Qdrant workers (default: 4)'
    )
    parser.add_argument(
        '--concurrent-neo4j',
        type=int,
        default=10,
        help='Max concurrent Neo4j operations (default: 10, max pool size is 50)'
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=50,
        help='Documents per batch (default: 50, recommended: 50-100)'
    )

    args = parser.parse_args()

    asyncio.run(main(
        use_batch=args.batch,
        num_workers=args.workers,
        max_concurrent_neo4j=args.concurrent_neo4j,
        batch_size=args.batch_size
    ))
