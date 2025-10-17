"""
Test Universal Ingestion Pipeline with both Email and Document examples
"""
import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.services.ingestion.llamaindex import UniversalIngestionPipeline


async def test_universal_ingestion():
    """Test with email and Google Sheet examples from user."""

    print("="*80)
    print("UNIVERSAL INGESTION PIPELINE TEST")
    print("="*80)
    print()

    # Initialize pipeline
    print("Initializing UniversalIngestionPipeline...")
    pipeline = UniversalIngestionPipeline()
    print()

    # ========================================================================
    # TEST 1: Email (from user's example)
    # ========================================================================

    email_example = {
        "idx": 0,
        "id": 6166,
        "tenant_id": "3d2cb80d-e82c-4256-aa6c-9bf53afd0d07",
        "user_id": "nick@thunderbird-labs.com",
        "user_principal_name": "nick@thunderbird-labs.com",
        "message_id": "199e581bf250811e",
        "source": "gmail",
        "subject": "Welcome to Cortex!",
        "sender_name": "Alex Thompson",
        "sender_address": "nick@thunderbird-labs.com",
        "to_addresses": "[\"wecare@thunderbird-labs.com\"]",
        "received_datetime": "2025-10-15 01:35:07+00",
        "web_link": "",
        "change_key": "",
        "created_at": "2025-10-15 02:35:17.644981+00",
        "full_body": "Hi Emma,\n\nI hope this message finds you well! I'm thrilled to welcome you and the Acme Corp team to the Cortex family...",
        "episode_id": "1e7b1d5b-5d2b-45f8-b670-39527ea37cbd",
        "metadata": "{}",
        "document_type": "email"  # Add document_type
    }

    print("="*80)
    print("TEST 1: Email Ingestion")
    print("="*80)
    print()

    result1 = await pipeline.ingest_document(email_example, extract_entities=True)

    print("\nResult:")
    print(json.dumps(result1, indent=2))
    print()

    # ========================================================================
    # TEST 2: Google Sheet (from user's example)
    # ========================================================================

    document_example = {
        "idx": 0,
        "id": 2,
        "tenant_id": "23e4af88-7df0-4ca4-9e60-fc2a12569a93",
        "source": "googledrive",
        "source_id": "1RTp_DZwEcVm9s4GWe1z7-wWumuGAZIifzhwV98QK-1Q",
        "document_type": "googlesheet",
        "title": "miso financials",
        "content": "\"Category,Quarter,Revenue ($),Expenses ($),Net Profit ($),Notes\"\r\n\"Basketball Analytics,Q1,125000,89000,36000,New player data system launched\"\r\n\"Shiba Inu Research,Q1,68000,42000,26000,Behavioral modeling trials\"...",
        "raw_data": "{\"id\": \"1RTp_DZwEcVm9s4GWe1z7-wWumuGAZIifzhwV98QK-1Q\", \"name\": \"miso financials\", ...}",
        "file_type": "text/csv",
        "file_size": 1022,
        "file_url": None,
        "source_created_at": "2025-10-16 18:58:43.22+00",
        "source_modified_at": "2025-10-16 19:00:26.408+00",
        "ingested_at": "2025-10-16 19:02:12.560594+00",
        "metadata": "{\"parser\": \"unstructured\", \"file_name\": \"tmp4ohfripv.bin\", \"file_size\": 1022, ...}",
        "content_hash": "e75faaf24f204b3237ce34b4830abfafa1c0db7de09b450b1511b579b1e962b2"
    }

    print("="*80)
    print("TEST 2: Google Sheet Ingestion")
    print("="*80)
    print()

    result2 = await pipeline.ingest_document(document_example, extract_entities=True)

    print("\nResult:")
    print(json.dumps(result2, indent=2))
    print()

    # ========================================================================
    # SUMMARY
    # ========================================================================

    print("="*80)
    print("TEST SUMMARY")
    print("="*80)
    print()

    print(f"Email ingestion: {'✅ SUCCESS' if result1['status'] == 'success' else '❌ FAILED'}")
    print(f"Document ingestion: {'✅ SUCCESS' if result2['status'] == 'success' else '❌ FAILED'}")
    print()

    # Pipeline stats
    stats = pipeline.get_stats()
    print("Pipeline Statistics:")
    print(json.dumps(stats, indent=2))
    print()

    print("="*80)
    print("TEST COMPLETE")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(test_universal_ingestion())
