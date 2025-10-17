"""
Create Production Indexes for Knowledge Graph

This script creates essential indexes for production performance.
Safe to run multiple times (idempotent).

Run this ONCE before launching to production, then never worry about it again.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.ingestion.llamaindex.config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE
)
from neo4j import GraphDatabase


def create_indexes():
    """Create all production indexes."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    indexes = [
        # ========================================================================
        # CRITICAL: App Layer Indexes (GMAIL, SLACK, HUBSPOT nodes)
        # ========================================================================
        {
            'name': 'idx_gmail_id',
            'query': 'CREATE INDEX idx_gmail_id IF NOT EXISTS FOR (g:GMAIL) ON (g.id)',
            'description': 'Fast lookup by GMAIL node ID (e.g., gmail:doc-123)'
        },
        {
            'name': 'idx_gmail_message_id',
            'query': 'CREATE INDEX idx_gmail_message_id IF NOT EXISTS FOR (g:GMAIL) ON (g.message_id)',
            'description': 'Fast lookup by email message_id'
        },
        {
            'name': 'idx_gmail_sender',
            'query': 'CREATE INDEX idx_gmail_sender IF NOT EXISTS FOR (g:GMAIL) ON (g.sender_address)',
            'description': 'Fast queries like "find all emails from alex@company.com"'
        },
        {
            'name': 'idx_gmail_timestamp',
            'query': 'CREATE INDEX idx_gmail_timestamp IF NOT EXISTS FOR (g:GMAIL) ON (g.timestamp)',
            'description': 'Fast temporal queries (emails in date range)'
        },
        {
            'name': 'idx_gmail_tenant_timestamp',
            'query': 'CREATE INDEX idx_gmail_tenant_timestamp IF NOT EXISTS FOR (g:GMAIL) ON (g.tenant_id, g.timestamp)',
            'description': 'CRITICAL: Multi-tenant queries with time filtering'
        },

        # ========================================================================
        # CRITICAL: Entity Layer Indexes (PERSON, COMPANY)
        # ========================================================================
        {
            'name': 'idx_person_name',
            'query': 'CREATE INDEX idx_person_name IF NOT EXISTS FOR (p:PERSON) ON (p.name)',
            'description': 'Fast lookup by person name (critical for deduplication)'
        },
        {
            'name': 'idx_person_id',
            'query': 'CREATE INDEX idx_person_id IF NOT EXISTS FOR (p:PERSON) ON (p.id)',
            'description': 'Fast lookup by person ID'
        },
        {
            'name': 'idx_company_name',
            'query': 'CREATE INDEX idx_company_name IF NOT EXISTS FOR (c:COMPANY) ON (c.name)',
            'description': 'Fast lookup by company name (critical for deduplication)'
        },
        {
            'name': 'idx_company_id',
            'query': 'CREATE INDEX idx_company_id IF NOT EXISTS FOR (c:COMPANY) ON (c.id)',
            'description': 'Fast lookup by company ID'
        },

        # ========================================================================
        # CRITICAL: Content Layer Indexes (Chunk nodes)
        # ========================================================================
        {
            'name': 'idx_chunk_id',
            'query': 'CREATE INDEX idx_chunk_id IF NOT EXISTS FOR (c:Chunk) ON (c.id)',
            'description': 'Fast lookup by chunk ID'
        },
        {
            'name': 'idx_chunk_ref_doc',
            'query': 'CREATE INDEX idx_chunk_ref_doc IF NOT EXISTS FOR (c:Chunk) ON (c.ref_doc_id)',
            'description': 'Fast lookup of chunks by parent document'
        },
        {
            'name': 'idx_chunk_tenant',
            'query': 'CREATE INDEX idx_chunk_tenant IF NOT EXISTS FOR (c:Chunk) ON (c.tenant_id)',
            'description': 'Fast tenant isolation for chunks'
        },

        # ========================================================================
        # OPTIONAL: Full-text search indexes
        # ========================================================================
        {
            'name': 'idx_gmail_subject_fulltext',
            'query': '''
                CREATE FULLTEXT INDEX idx_gmail_subject_fulltext IF NOT EXISTS
                FOR (g:GMAIL) ON EACH [g.document_name, g.sender_name]
            ''',
            'description': 'Full-text search on email subjects and senders'
        },
        {
            'name': 'idx_person_name_fulltext',
            'query': 'CREATE FULLTEXT INDEX idx_person_name_fulltext IF NOT EXISTS FOR (p:PERSON) ON EACH [p.name]',
            'description': 'Full-text search on person names'
        },
        {
            'name': 'idx_company_name_fulltext',
            'query': 'CREATE FULLTEXT INDEX idx_company_name_fulltext IF NOT EXISTS FOR (c:COMPANY) ON EACH [c.name]',
            'description': 'Full-text search on company names'
        },
    ]

    print("=" * 80)
    print("CREATING PRODUCTION INDEXES")
    print("=" * 80)
    print()

    created_count = 0
    skipped_count = 0
    failed_count = 0

    with driver.session(database=NEO4J_DATABASE) as session:
        for idx in indexes:
            try:
                print(f"Creating: {idx['name']}")
                print(f"  Description: {idx['description']}")

                session.run(idx['query'])
                created_count += 1
                print(f"  ✅ Created")

            except Exception as e:
                error_str = str(e)
                if 'already exists' in error_str.lower() or 'equivalent' in error_str.lower():
                    skipped_count += 1
                    print(f"  ⏭️  Already exists (skipped)")
                else:
                    failed_count += 1
                    print(f"  ❌ Failed: {e}")
            print()

    driver.close()

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Created: {created_count}")
    print(f"Skipped (already exist): {skipped_count}")
    print(f"Failed: {failed_count}")
    print()

    if failed_count > 0:
        print("⚠️  Some indexes failed to create. Check errors above.")
        return False
    else:
        print("✅ All production indexes ready!")
        return True


if __name__ == "__main__":
    success = create_indexes()
    sys.exit(0 if success else 1)
