"""
Clear databases and reingest all documents from Supabase documents table
Works with all document types: emails, files, attachments, etc.
"""
import asyncio
import sys
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
from supabase import create_client

from app.core.config import settings
from app.services.ingestion.llamaindex import UniversalIngestionPipeline

load_dotenv()

async def main():
    print("="*80)
    print("CLEAR & REINGEST ALL DOCUMENTS")
    print("="*80)

    # Step 1: Clear Qdrant
    print("\n1️⃣ Clearing Qdrant...")
    qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    try:
        result = qdrant.get_collection(settings.qdrant_collection_name)
        before_count = result.points_count
        print(f"   Qdrant points before: {before_count}")

        qdrant.delete_collection(settings.qdrant_collection_name)
        print(f"   ✅ Deleted collection")

        qdrant.create_collection(
            collection_name=settings.qdrant_collection_name,
            vectors_config={"size": 1536, "distance": "Cosine"}
        )
        print(f"   ✅ Recreated collection: {settings.qdrant_collection_name}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")

    # Step 2: Clear Neo4j
    print("\n2️⃣ Clearing Neo4j...")
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )

    with driver.session(database="neo4j") as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        before_count = result.single()["count"]
        print(f"   Neo4j nodes before: {before_count}")

        session.run("MATCH (n) DETACH DELETE n")

        result = session.run("MATCH (n) RETURN count(n) as count")
        after_count = result.single()["count"]
        print(f"   ✅ Neo4j nodes after: {after_count}")

    # Step 3: Fetch all documents from Supabase
    print("\n3️⃣ Fetching documents from Supabase...")
    supabase = create_client(settings.supabase_url, settings.supabase_service_key)

    result = supabase.table('documents').select('*').execute()
    documents = result.data
    print(f"   Found {len(documents)} documents (emails, files, etc.)")

    # Step 4: Initialize pipeline
    print("\n4️⃣ Initializing UniversalIngestionPipeline...")
    pipeline = UniversalIngestionPipeline()
    print("   ✅ Pipeline ready")

    # Step 5: Batch ingest
    print(f"\n5️⃣ Ingesting {len(documents)} documents...")

    if documents:
        results = await pipeline.ingest_documents_batch(
            document_rows=documents,
            extract_entities=True,
            num_workers=4
        )

        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = sum(1 for r in results if r['status'] == 'error')

        print(f"\n   ✅ Success: {success_count}")
        print(f"   ❌ Errors: {error_count}")
    else:
        print("   ⚠️  No documents to ingest")

    # Step 6: Verify
    print("\n6️⃣ Verification...")
    result = qdrant.get_collection(settings.qdrant_collection_name)
    print(f"   Qdrant points: {result.points_count}")

    with driver.session(database="neo4j") as session:
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"   Neo4j nodes: {count}")

    driver.close()

    print("\n" + "="*80)
    print("✅ COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
