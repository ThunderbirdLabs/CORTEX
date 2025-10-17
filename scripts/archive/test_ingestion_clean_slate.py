"""
Test Email Ingestion (Clean Slate Expert Pattern)

Tests the new EmailIngestionPipeline:
1. Fetches 2 emails from Supabase
2. Ingests them using the expert pattern
3. Verifies chunks in Qdrant
4. Verifies Email/Person nodes in Neo4j
5. Verifies relationships (SENT_BY, SENT_TO)
"""
import sys
import os
import asyncio
import json

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.ingestion.llamaindex import EmailIngestionPipeline
from app.services.ingestion.llamaindex.config import (
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME,
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
)
from app.core.config import settings
from supabase import create_client
from qdrant_client import QdrantClient
from neo4j import GraphDatabase


async def test_ingestion():
    """Test email ingestion with 2 emails from Supabase."""

    print("="*80)
    print("EMAIL INGESTION TEST (Expert Pattern)")
    print("="*80)
    print()

    # Initialize clients
    print("Initializing clients...")
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
    neo4j_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    # Initialize pipeline
    print("Initializing EmailIngestionPipeline...")
    pipeline = EmailIngestionPipeline()
    print()

    # Fetch 2 emails from Supabase
    print("Fetching 2 emails from Supabase...")
    response = supabase.table("emails").select("*").limit(2).execute()
    emails = response.data

    if not emails:
        print("❌ No emails found in Supabase!")
        return

    print(f"✅ Found {len(emails)} emails")
    for email in emails:
        print(f"   - {email['subject']} (from {email.get('sender_name', 'Unknown')})")
    print()

    # Ingest emails
    print("="*80)
    print("INGESTING EMAILS")
    print("="*80)
    print()

    results = []
    for email in emails:
        result = await pipeline.ingest_email(email, extract_entities=True)
        results.append(result)

    # Verify ingestion results
    print("="*80)
    print("INGESTION RESULTS")
    print("="*80)
    print()

    success_count = sum(1 for r in results if r["status"] == "success")
    print(f"✅ Successfully ingested: {success_count}/{len(emails)}")

    for result in results:
        if result["status"] == "success":
            print(f"   ✅ {result['subject']}")
        else:
            print(f"   ❌ {result.get('email_id', 'Unknown')}: {result.get('error', 'Unknown error')}")
    print()

    # Verify Qdrant
    print("="*80)
    print("VERIFYING QDRANT")
    print("="*80)
    print()

    try:
        collection_info = qdrant_client.get_collection(QDRANT_COLLECTION_NAME)
        print(f"✅ Collection: {QDRANT_COLLECTION_NAME}")
        print(f"   Points count: {collection_info.points_count}")
        print(f"   Vectors count: {collection_info.vectors_count}")

        # Sample a few points to verify metadata
        points = qdrant_client.scroll(
            collection_name=QDRANT_COLLECTION_NAME,
            limit=5,
            with_payload=True,
            with_vectors=False
        )[0]

        print(f"\n   Sample points (showing {len(points)}):")
        for i, point in enumerate(points, 1):
            payload = point.payload
            email_id = payload.get("email_id", "N/A")
            subject = payload.get("subject", "N/A")
            text_preview = payload.get("text", "")[:100] if "text" in payload else "N/A"
            print(f"   {i}. email_id={email_id}, subject='{subject}'")
            print(f"      text_preview: {text_preview}...")
    except Exception as e:
        print(f"❌ Qdrant verification failed: {e}")

    print()

    # Verify Neo4j
    print("="*80)
    print("VERIFYING NEO4J")
    print("="*80)
    print()

    try:
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            # Count EMAIL nodes
            result = session.run("MATCH (e:EMAIL) RETURN count(e) as count")
            email_count = result.single()["count"]
            print(f"✅ EMAIL nodes: {email_count}")

            # Count PERSON nodes
            result = session.run("MATCH (p:PERSON) RETURN count(p) as count")
            person_count = result.single()["count"]
            print(f"✅ PERSON nodes: {person_count}")

            # Count COMPANY nodes
            result = session.run("MATCH (c:COMPANY) RETURN count(c) as count")
            company_count = result.single()["count"]
            print(f"✅ COMPANY nodes: {company_count}")

            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count")
            relationships = result.data()
            print(f"\n✅ Relationships:")
            for rel in relationships:
                print(f"   {rel['rel_type']}: {rel['count']}")

            # Show sample EMAIL nodes
            result = session.run("""
                MATCH (e:EMAIL)
                RETURN e.email_id as email_id, e.subject as subject, e.sender_name as sender
                LIMIT 5
            """)
            emails_sample = result.data()
            print(f"\n   Sample EMAIL nodes (showing {len(emails_sample)}):")
            for i, email in enumerate(emails_sample, 1):
                print(f"   {i}. {email['subject']} (from {email['sender']})")

            # Show sample PERSON nodes
            result = session.run("""
                MATCH (p:PERSON)
                RETURN p.name as name, p.email as email
                LIMIT 5
            """)
            persons_sample = result.data()
            print(f"\n   Sample PERSON nodes (showing {len(persons_sample)}):")
            for i, person in enumerate(persons_sample, 1):
                print(f"   {i}. {person['name']} ({person['email']})")

            # Show sample relationships
            result = session.run("""
                MATCH (e:EMAIL)-[r:SENT_BY]->(p:PERSON)
                RETURN e.subject as email_subject, p.name as person_name
                LIMIT 3
            """)
            sent_by_sample = result.data()
            print(f"\n   Sample SENT_BY relationships (showing {len(sent_by_sample)}):")
            for i, rel in enumerate(sent_by_sample, 1):
                print(f"   {i}. '{rel['email_subject']}' -[SENT_BY]-> {rel['person_name']}")

    except Exception as e:
        print(f"❌ Neo4j verification failed: {e}")

    print()

    # Get pipeline stats
    print("="*80)
    print("PIPELINE STATISTICS")
    print("="*80)
    print()

    stats = pipeline.get_stats()
    print(json.dumps(stats, indent=2))
    print()

    # Cleanup
    neo4j_driver.close()

    print("="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_ingestion())
