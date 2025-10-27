"""
Ingest all documents from Supabase documents table into Qdrant + Neo4j

This script:
1. Fetches all rows from the 'documents' table in Supabase
2. Runs them through UniversalIngestionPipeline
3. Stores chunks in Qdrant and entities in Neo4j
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
from app.core.config import settings
from app.services.ingestion.llamaindex import UniversalIngestionPipeline


async def main():
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

    # Step 3: Single-document ingestion (fallback from broken batch method)
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

    # Step 4: Show results
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

    # Step 5: Verify
    print("\n5️⃣ Verification...")
    from qdrant_client import QdrantClient
    from neo4j import GraphDatabase

    # Check Qdrant
    qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    collection = qdrant.get_collection(settings.qdrant_collection_name)
    print(f"   Qdrant points: {collection.points_count}")

    # Check Neo4j
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )
    with driver.session(database="neo4j") as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"   Neo4j nodes: {count}")
    driver.close()

    print("\n" + "="*80)
    print("✅ INGESTION COMPLETE")
    print("="*80)
    print("\nYou can now:")
    print("1. Query via /api/v1/chat")
    print("2. Test with: 'What documents do I have?'")


if __name__ == "__main__":
    asyncio.run(main())
