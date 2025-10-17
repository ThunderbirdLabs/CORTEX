"""
Production Flow Test - Clean Slate
1. Clear Neo4j and Qdrant
2. Fetch 5 documents from Supabase
3. Ingest using production pipeline
4. Verify results
"""
import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.ingestion.llamaindex import UniversalIngestionPipeline
from app.services.ingestion.llamaindex.config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME
)
from app.core.config import settings
from supabase import create_client
from qdrant_client import QdrantClient
from neo4j import GraphDatabase


async def clear_databases():
    """Clear Neo4j and Qdrant databases."""
    print("="*80)
    print("CLEARING DATABASES")
    print("="*80)
    print()

    # Clear Neo4j
    print("🗑️  Clearing Neo4j...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as session:
            # Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")

            # Verify
            result = session.run("MATCH (n) RETURN count(n) as count")
            count = result.single()["count"]
            print(f"   ✅ Neo4j cleared (remaining nodes: {count})")
        driver.close()
    except Exception as e:
        print(f"   ❌ Neo4j clear failed: {e}")
        raise

    # Clear Qdrant
    print("🗑️  Clearing Qdrant...")
    try:
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

        # Delete collection if exists
        try:
            qdrant_client.delete_collection(QDRANT_COLLECTION_NAME)
            print(f"   ✅ Qdrant collection deleted: {QDRANT_COLLECTION_NAME}")
        except Exception as e:
            print(f"   ℹ️  Collection didn't exist or already deleted")

        # Recreate empty collection
        from qdrant_client.models import Distance, VectorParams
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
        )
        print(f"   ✅ Qdrant collection recreated: {QDRANT_COLLECTION_NAME}")

        # Verify
        collection = qdrant_client.get_collection(QDRANT_COLLECTION_NAME)
        print(f"   ✅ Qdrant cleared (points: {collection.points_count})")
    except Exception as e:
        print(f"   ❌ Qdrant clear failed: {e}")
        raise

    print()


async def fetch_supabase_documents(limit=5):
    """Fetch documents from Supabase (tries documents table first, then emails)."""
    print("="*80)
    print("FETCHING FROM SUPABASE")
    print("="*80)
    print()

    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)

    # Try documents table first
    print("📥 Fetching from 'documents' table...")
    try:
        response = supabase.table("documents").select("*").limit(limit).execute()
        if response.data and len(response.data) > 0:
            print(f"   ✅ Found {len(response.data)} documents")
            for doc in response.data:
                print(f"      - {doc.get('title', 'Untitled')} ({doc.get('document_type', 'unknown')})")
            print()
            return response.data
    except Exception as e:
        print(f"   ℹ️  Documents table not available: {e}")

    # Fallback to emails table
    print("📥 Fetching from 'emails' table...")
    try:
        response = supabase.table("emails").select("*").limit(limit).execute()
        if response.data and len(response.data) > 0:
            print(f"   ✅ Found {len(response.data)} emails")
            for email in response.data:
                # Add document_type for universal pipeline
                email['document_type'] = 'email'
                print(f"      - {email.get('subject', 'No Subject')} (from {email.get('sender_name', 'Unknown')})")
            print()
            return response.data
        else:
            print(f"   ❌ No emails found!")
            return []
    except Exception as e:
        print(f"   ❌ Failed to fetch emails: {e}")
        return []


async def ingest_documents(documents, pipeline):
    """Ingest documents through production pipeline."""
    print("="*80)
    print("PRODUCTION INGESTION")
    print("="*80)
    print()

    results = []
    for i, doc in enumerate(documents, 1):
        doc_type = doc.get('document_type', 'email')
        title = doc.get('title') or doc.get('subject', 'Untitled')

        print(f"[{i}/{len(documents)}] Ingesting: {title} ({doc_type})")
        print("-" * 80)

        # Use production pipeline
        result = await pipeline.ingest_document(
            document_row=doc,
            extract_entities=True  # Production setting
        )

        results.append(result)

        if result['status'] == 'success':
            print(f"✅ SUCCESS\n")
        else:
            print(f"❌ FAILED: {result.get('error', 'Unknown error')}\n")

    return results


async def verify_results(pipeline):
    """Verify ingestion results in both databases."""
    print("="*80)
    print("VERIFICATION")
    print("="*80)
    print()

    # Get stats from pipeline
    stats = pipeline.get_stats()

    print("📊 Database Statistics:")
    print(json.dumps(stats, indent=2))
    print()

    # Detailed Neo4j verification
    print("="*80)
    print("NEO4J GRAPH VERIFICATION")
    print("="*80)
    print()

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DATABASE) as session:
            # Get all node types
            result = session.run("""
                MATCH (n)
                RETURN DISTINCT labels(n)[0] as label, count(*) as count
                ORDER BY count DESC
            """)
            node_types = result.data()

            print("📦 Node Types:")
            for node_type in node_types:
                print(f"   {node_type['label']}: {node_type['count']}")
            print()

            # Get all relationship types
            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(*) as count
                ORDER BY count DESC
            """)
            rel_types = result.data()

            print("🔗 Relationship Types:")
            for rel_type in rel_types:
                print(f"   {rel_type['rel_type']}: {rel_type['count']}")
            print()

            # Sample nodes
            result = session.run("""
                MATCH (n)
                WHERE NOT n:__Node__ AND NOT n:__Entity__
                RETURN labels(n)[0] as label, n.title as title, n.name as name
                LIMIT 10
            """)
            samples = result.data()

            print("📄 Sample Nodes:")
            for sample in samples:
                name = sample['title'] or sample['name'] or 'N/A'
                print(f"   {sample['label']}: {name}")
            print()

        driver.close()
    except Exception as e:
        print(f"❌ Neo4j verification failed: {e}")
        print()

    # Qdrant verification
    print("="*80)
    print("QDRANT VECTOR VERIFICATION")
    print("="*80)
    print()

    try:
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        collection = qdrant_client.get_collection(QDRANT_COLLECTION_NAME)

        print(f"📊 Collection: {QDRANT_COLLECTION_NAME}")
        print(f"   Points: {collection.points_count}")
        print(f"   Vector size: {collection.config.params.vectors.size}")
        print()

        # Sample points
        points = qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=5,
            with_payload=True,
            with_vectors=False
        )[0]

        print("📄 Sample Chunks:")
        for point in points:
            payload = point.payload
            title = payload.get('title', 'N/A')
            doc_type = payload.get('document_type', 'N/A')
            text_preview = payload.get('text', '')[:80] + '...' if 'text' in payload else 'N/A'
            print(f"   {doc_type}: {title}")
            print(f"      {text_preview}")
            print()

    except Exception as e:
        print(f"❌ Qdrant verification failed: {e}")
        print()


async def main():
    """Run production flow test."""
    print("\n")
    print("="*80)
    print("PRODUCTION FLOW TEST - CLEAN SLATE")
    print("="*80)
    print()

    # Step 1: Clear databases
    await clear_databases()

    # Step 2: Fetch documents from Supabase
    documents = await fetch_supabase_documents(limit=5)

    if not documents:
        print("❌ No documents to ingest. Exiting.")
        return

    # Step 3: Initialize production pipeline
    print("="*80)
    print("INITIALIZING PRODUCTION PIPELINE")
    print("="*80)
    print()

    pipeline = UniversalIngestionPipeline()
    print()

    # Step 4: Ingest documents
    results = await ingest_documents(documents, pipeline)

    # Step 5: Verify results
    await verify_results(pipeline)

    # Step 6: Summary
    print("="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print()

    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')

    print(f"✅ Successful ingestions: {success_count}/{len(documents)}")
    print(f"❌ Failed ingestions: {error_count}/{len(documents)}")
    print()

    if error_count > 0:
        print("❌ Errors:")
        for result in results:
            if result['status'] == 'error':
                title = result.get('title', result.get('document_id', 'Unknown'))
                print(f"   - {title}: {result.get('error', 'Unknown error')}")
        print()

    print("="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
