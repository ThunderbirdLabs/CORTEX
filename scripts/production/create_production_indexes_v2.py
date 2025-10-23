"""
Create Production Indexes for Neo4j (Expert Pattern)

Indexes for Email, Person, Company nodes per expert guidance.
Safe to run multiple times (idempotent).
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
    """Create all production indexes for Email, Person, Company nodes."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    indexes = [
        # Email node indexes
        {
            'name': 'idx_email_id',
            'query': 'CREATE INDEX idx_email_id IF NOT EXISTS FOR (e:EMAIL) ON (e.email_id)',
            'description': 'Fast lookup by email_id'
        },
        {
            'name': 'idx_email_subject',
            'query': 'CREATE INDEX idx_email_subject IF NOT EXISTS FOR (e:EMAIL) ON (e.subject)',
            'description': 'Fast lookup by subject'
        },
        {
            'name': 'idx_email_sender',
            'query': 'CREATE INDEX idx_email_sender IF NOT EXISTS FOR (e:EMAIL) ON (e.sender_address)',
            'description': 'Fast queries by sender'
        },
        {
            'name': 'idx_email_tenant_id',
            'query': 'CREATE INDEX idx_email_tenant_id IF NOT EXISTS FOR (e:EMAIL) ON (e.tenant_id)',
            'description': 'Multi-tenant isolation'
        },
        {
            'name': 'idx_email_received',
            'query': 'CREATE INDEX idx_email_received IF NOT EXISTS FOR (e:EMAIL) ON (e.received_datetime)',
            'description': 'Temporal queries'
        },

        # Person node indexes
        {
            'name': 'idx_person_email',
            'query': 'CREATE INDEX idx_person_email IF NOT EXISTS FOR (p:PERSON) ON (p.email)',
            'description': 'Fast lookup by person email (critical for deduplication)'
        },
        {
            'name': 'idx_person_name',
            'query': 'CREATE INDEX idx_person_name IF NOT EXISTS FOR (p:PERSON) ON (p.name)',
            'description': 'Fast lookup by person name'
        },

        # Company node indexes
        {
            'name': 'idx_company_name',
            'query': 'CREATE INDEX idx_company_name IF NOT EXISTS FOR (c:COMPANY) ON (c.name)',
            'description': 'Fast lookup by company name (critical for deduplication)'
        },

        # Full-text search indexes
        {
            'name': 'idx_email_fulltext',
            'query': '''
                CREATE FULLTEXT INDEX idx_email_fulltext IF NOT EXISTS
                FOR (e:EMAIL) ON EACH [e.subject, e.full_body, e.sender_name]
            ''',
            'description': 'Full-text search on email content'
        },
        {
            'name': 'idx_person_fulltext',
            'query': 'CREATE FULLTEXT INDEX idx_person_fulltext IF NOT EXISTS FOR (p:PERSON) ON EACH [p.name, p.email]',
            'description': 'Full-text search on person info'
        },
    ]

    print("=" * 80)
    print("CREATING PRODUCTION INDEXES (Expert Pattern)")
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
