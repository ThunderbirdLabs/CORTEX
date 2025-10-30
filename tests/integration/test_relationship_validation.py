#!/usr/bin/env python3
"""
Test Relationship Validation

Quick test to verify relationship validation is working correctly.
Tests with a single document to see validation in action.
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import os
from dotenv import load_dotenv
from supabase import create_client
from app.services.ingestion.llamaindex import UniversalIngestionPipeline

load_dotenv()

async def main():
    print("=" * 80)
    print("RELATIONSHIP VALIDATION TEST")
    print("=" * 80)

    # Get a single document from Supabase
    supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
    result = supabase.table("documents").select("*").limit(1).execute()

    if not result.data:
        print("❌ No documents found in database")
        return

    document = result.data[0]
    print(f"\nTesting with document:")
    print(f"  ID: {document['id']}")
    print(f"  Title: {document.get('title', 'N/A')}")
    print(f"  Type: {document.get('document_type', 'N/A')}")

    # Initialize pipeline (should see validation enabled message)
    print(f"\n{'='*80}")
    print("INITIALIZING PIPELINE")
    print("=" * 80)
    pipeline = UniversalIngestionPipeline()

    # Ingest document with validation
    print(f"\n{'='*80}")
    print("INGESTING DOCUMENT (with validation)")
    print("=" * 80)
    result = await pipeline.ingest_document(
        document_row=document,
        extract_entities=True
    )

    print(f"\n{'='*80}")
    print("RESULTS")
    print("=" * 80)
    print(f"Status: {result.get('status')}")
    print(f"Relationships extracted: {result.get('relationships', 0)}")

    if result.get('status') == 'success':
        print("\n✅ Test successful!")
        print("\nLook for validation messages in the output above:")
        print("  - '✅ Relationship Validator: LLM-based validation enabled'")
        print("  - '🔍 Relationship validation: X approved, Y rejected'")
    else:
        print(f"\n❌ Test failed: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())
