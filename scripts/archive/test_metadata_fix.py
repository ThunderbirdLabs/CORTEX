"""
Test Metadata Fix: Verify Entity Nodes Have Clean Properties

This test validates the critical fixes:
1. Entity nodes DON'T have document metadata (file_size, owner_name, etc.)
2. Entity nodes ONLY have entity-specific properties (name, email, etc.)
3. MENTIONED_IN relationships exist from entities to documents
4. Graph traversal works: Entity → Document → Related Entities

Tests with real data from all 3 Supabase tables:
- documents (Google Drive files)
- emails (Gmail messages)
- connections (metadata only)
"""
import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.ingestion.llamaindex import UniversalIngestionPipeline
from app.services.ingestion.llamaindex.config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
)
from app.core.config import settings
from supabase import create_client
from neo4j import GraphDatabase


async def clear_neo4j():
    """Clear Neo4j for clean test."""
    print("🗑️  Clearing Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    with driver.session(database=NEO4J_DATABASE) as session:
        session.run("MATCH (n) DETACH DELETE n")
        result = session.run("MATCH (n) RETURN count(n) as count")
        count = result.single()["count"]
        print(f"   ✅ Neo4j cleared (remaining nodes: {count})")
    driver.close()
    print()


async def test_document_ingestion():
    """Test document from documents table."""
    print("="*80)
    print("TEST 1: DOCUMENT INGESTION (documents table)")
    print("="*80)
    print()

    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    pipeline = UniversalIngestionPipeline()

    # Fetch 1 document
    result = supabase.table("documents").select("*").limit(1).execute()
    if not result.data:
        print("❌ No documents found")
        return False

    doc = result.data[0]
    print(f"📄 Ingesting: {doc['title']}")
    print(f"   Type: {doc['document_type']}")
    print(f"   Metadata fields: {len(doc.get('metadata', {}))}")
    print()

    # Ingest
    ingest_result = await pipeline.ingest_document(doc, extract_entities=True)

    if ingest_result['status'] != 'success':
        print(f"❌ Ingestion failed: {ingest_result.get('error')}")
        return False

    print("✅ Ingestion successful")
    print()
    return True


async def test_email_ingestion():
    """Test email from emails table."""
    print("="*80)
    print("TEST 2: EMAIL INGESTION (emails table)")
    print("="*80)
    print()

    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    pipeline = UniversalIngestionPipeline()

    # Fetch 1 email
    result = supabase.table("emails").select("*").limit(1).execute()
    if not result.data:
        print("❌ No emails found")
        return False

    email = result.data[0]
    email['document_type'] = 'email'  # Add document_type
    print(f"📧 Ingesting: {email['subject']}")
    print(f"   From: {email.get('sender_name', 'Unknown')}")
    print()

    # Ingest
    ingest_result = await pipeline.ingest_document(email, extract_entities=True)

    if ingest_result['status'] != 'success':
        print(f"❌ Ingestion failed: {ingest_result.get('error')}")
        return False

    print("✅ Ingestion successful")
    print()
    return True


async def verify_graph_structure():
    """Verify graph structure: clean entities + MENTIONED_IN relationships."""
    print("="*80)
    print("VERIFICATION: GRAPH STRUCTURE")
    print("="*80)
    print()

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with driver.session(database=NEO4J_DATABASE) as session:
        # Test 1: Check entity nodes for metadata pollution
        print("TEST: Entity nodes should NOT have document metadata")
        print("-"*80)

        result = session.run("""
            MATCH (n)
            WHERE any(label IN labels(n) WHERE label IN ['PERSON', 'COMPANY', 'TOPIC', 'PRODUCT', 'LOCATION'])
            RETURN labels(n)[0] as entity_type, n.name as name, properties(n) as props
            LIMIT 10
        """)

        entities = result.data()
        if not entities:
            print("⚠️  No entities extracted (may be expected for some documents)")
        else:
            # Document metadata keys that should NOT be on entities
            FORBIDDEN_KEYS = {
                'file_size', 'owner_name', 'owner_email', 'web_view_link',
                'parent_folders', 'file_name', 'file_type', 'characters',
                'parser', 'original_filename', 'original_mime_type',
                'content', 'source', 'source_id', 'tenant_id',
                'sender_address', 'to_addresses', 'received_datetime'
            }

            all_clean = True
            for entity in entities:
                entity_type = entity['entity_type']
                name = entity['name']
                props = entity['props']

                # Check for forbidden keys
                forbidden_found = FORBIDDEN_KEYS.intersection(set(props.keys()))

                if forbidden_found:
                    print(f"❌ FAIL: {entity_type} '{name}' has document metadata:")
                    print(f"   Forbidden properties: {forbidden_found}")
                    print(f"   All properties: {list(props.keys())}")
                    all_clean = False
                else:
                    print(f"✅ PASS: {entity_type} '{name}' has clean properties")
                    print(f"   Properties: {list(props.keys())}")

            print()
            if all_clean:
                print("✅ All entities have clean metadata (no document properties)")
            else:
                print("❌ Some entities have document metadata pollution")
            print()

        # Test 2: Check for MENTIONED_IN relationships
        print("TEST: MENTIONED_IN relationships should exist")
        print("-"*80)

        result = session.run("""
            MATCH (entity)-[r:MENTIONED_IN]->(doc)
            RETURN labels(entity)[0] as entity_type, entity.name as entity_name,
                   labels(doc)[0] as doc_type, doc.title as doc_title,
                   properties(r) as rel_props
            LIMIT 10
        """)

        mentioned_in_rels = result.data()
        if not mentioned_in_rels:
            print("❌ FAIL: No MENTIONED_IN relationships found")
            print("   Entities are not linked to source documents")
        else:
            print(f"✅ PASS: Found {len(mentioned_in_rels)} MENTIONED_IN relationships")
            for rel in mentioned_in_rels:
                print(f"   {rel['entity_type']} '{rel['entity_name']}' -[MENTIONED_IN]-> {rel['doc_type']} '{rel['doc_title']}'")
        print()

        # Test 3: Graph traversal query
        print("TEST: Graph traversal should work")
        print("-"*80)

        result = session.run("""
            MATCH (e1:PERSON)-[:MENTIONED_IN]->(doc)<-[:MENTIONED_IN]-(e2)
            WHERE e1 <> e2
            RETURN e1.name as person, doc.title as document,
                   labels(e2)[0] as related_type, e2.name as related_entity
            LIMIT 5
        """)

        traversal_results = result.data()
        if not traversal_results:
            print("⚠️  No multi-entity documents found (may be expected)")
        else:
            print(f"✅ Graph traversal works! Found {len(traversal_results)} related entities:")
            for row in traversal_results:
                print(f"   {row['person']} ← {row['document']} → {row['related_type']} '{row['related_entity']}'")
        print()

        # Summary stats
        print("="*80)
        print("GRAPH STATISTICS")
        print("="*80)

        # Node counts
        result = session.run("""
            MATCH (n)
            RETURN DISTINCT labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)
        print("Nodes:")
        for row in result.data():
            print(f"   {row['label']}: {row['count']}")
        print()

        # Relationship counts
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as rel_type, count(*) as count
            ORDER BY count DESC
        """)
        print("Relationships:")
        for row in result.data():
            print(f"   {row['rel_type']}: {row['count']}")
        print()

    driver.close()


async def main():
    """Run comprehensive metadata fix test."""
    print("\n")
    print("="*80)
    print("METADATA FIX VALIDATION TEST")
    print("="*80)
    print()

    # Clear Neo4j
    await clear_neo4j()

    # Test document ingestion
    doc_success = await test_document_ingestion()

    # Test email ingestion
    email_success = await test_email_ingestion()

    # Verify graph structure
    await verify_graph_structure()

    # Final summary
    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Document ingestion: {'✅ PASS' if doc_success else '❌ FAIL'}")
    print(f"Email ingestion: {'✅ PASS' if email_success else '❌ FAIL'}")
    print()
    print("✅ Metadata fix validation complete")
    print("   Check graph verification results above")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
