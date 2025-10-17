"""
Test SchemaLLMPathExtractor ingestion with 5 real emails from Supabase
"""
import asyncio
import json
import nest_asyncio
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

from app.services.ingestion.llamaindex import UniversalIngestionPipeline
from app.core.config import settings
from supabase import create_client

async def test_schema_ingestion():
    print("\n" + "="*80)
    print("TESTING SchemaLLMPathExtractor WITH 5 REAL EMAILS")
    print("="*80 + "\n")

    # Initialize pipeline
    print("🚀 Initializing Universal Ingestion Pipeline...")
    pipeline = UniversalIngestionPipeline()
    print("✅ Pipeline initialized\n")

    # Fetch 5 emails from Supabase
    print("📧 Fetching 5 emails from Supabase...")
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    result = supabase.table('emails').select('*').limit(5).execute()
    emails = result.data
    print(f"✅ Fetched {len(emails)} emails\n")

    # Ingest each email
    for i, email_row in enumerate(emails, 1):
        print(f"\n{'='*80}")
        print(f"INGESTING EMAIL {i}/5")
        print(f"{'='*80}")
        print(f"Subject: {email_row['subject']}")
        print(f"From: {email_row['sender_address']}")
        print(f"To: {email_row.get('to_addresses', [])}")
        print()

        # Ensure document_type is set
        email_row['document_type'] = 'email'

        # Ingest through pipeline
        result = await pipeline.ingest_document(
            document_row=email_row,
            extract_entities=True
        )

        if result['status'] == 'success':
            print(f"\n✅ Email {i} ingested successfully")
            print(f"   Document ID: {result['document_id']}")
            print(f"   Title: {result['title']}")
            print(f"   Characters: {result['characters']}")
            print(f"   Nodes created: {result['nodes_created']}")
        else:
            print(f"\n❌ Email {i} failed: {result.get('error')}")

    print("\n" + "="*80)
    print("INGESTION COMPLETE - VERIFICATION")
    print("="*80 + "\n")

    # Get stats
    stats = pipeline.get_stats()
    print(f"📊 Database Statistics:")
    print(f"   Qdrant points: {stats.get('qdrant_points', 0)}")
    print(f"   Neo4j nodes: {stats.get('neo4j_nodes', 0)}")
    print(f"   Neo4j relationships: {stats.get('neo4j_relationships', 0)}")

    return stats

if __name__ == "__main__":
    stats = asyncio.run(test_schema_ingestion())
    print("\n✅ Test complete!")
