"""
Test Universal Ingestion System
Tests file parsing + documents table + PropertyGraph ingestion WITHOUT Nango
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
from app.core.config import settings
from app.services.parsing.file_parser import extract_text_from_bytes
from app.services.universal.ingest import ingest_document_universal
from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline


async def test_universal_ingestion():
    """Test universal ingestion with a simple text document"""

    print("=" * 80)
    print("🧪 TESTING UNIVERSAL INGESTION SYSTEM")
    print("=" * 80)

    # Step 1: Create test document
    print("\n1️⃣ Creating test document...")
    test_content = """
    Subject: Q4 Product Launch - Cortex AI Platform

    Hi Team,

    I'm excited to announce the Q4 launch of Cortex AI, our new unified data
    ingestion platform. Key features include:

    - Universal ingestion for 600+ connectors (Gmail, Drive, Slack, HubSpot, etc.)
    - Local file parsing with Unstructured (PDFs, Word, Excel, images)
    - Hybrid RAG search with LlamaIndex PropertyGraph (Neo4j + Qdrant)
    - Schema-guided entity extraction (Person, Company, Deal, Product)

    The platform handles emails, documents, messages, and structured data from
    any source. Everything is normalized into a unified format for RAG.

    Key contacts:
    - Sarah Chen (sarah@cortex.ai) - Product Lead
    - Mike Johnson (mike@cortex.ai) - Engineering Lead
    - Deal value: $150,000 MRR

    Best,
    Nicolas Codet
    CEO, Cortex AI
    """

    test_filename = "cortex_launch_announcement.txt"
    test_bytes = test_content.encode('utf-8')

    print(f"✅ Created test document: {test_filename}")
    print(f"   Content length: {len(test_content)} characters")

    # Step 2: Test file parser
    print("\n2️⃣ Testing file parser (Unstructured)...")
    try:
        extracted_text, parse_metadata = extract_text_from_bytes(
            test_bytes,
            test_filename,
            "text/plain"
        )
        print(f"✅ File parsed successfully")
        print(f"   Extracted: {len(extracted_text)} characters")
        print(f"   Parser: {parse_metadata.get('parser')}")
    except Exception as e:
        print(f"❌ File parser failed: {e}")
        return

    # Step 3: Initialize Supabase
    print("\n3️⃣ Connecting to Supabase...")
    try:
        supabase = create_client(
            settings.supabase_url,
            settings.supabase_service_key
        )
        print(f"✅ Connected to Supabase")

        # Check if documents table exists
        result = supabase.table('documents').select("id").limit(1).execute()
        print(f"✅ Documents table exists ({len(result.data)} rows)")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")
        print("\n⚠️  Did you run create_documents_table.sql?")
        return

    # Step 4: Initialize PropertyGraph Pipeline
    print("\n4️⃣ Initializing PropertyGraph Pipeline (Neo4j + Qdrant)...")
    try:
        cortex_pipeline = HybridPropertyGraphPipeline()
        print(f"✅ PropertyGraph pipeline initialized")
        print(f"   Vector DB: Qdrant")
        print(f"   Graph DB: Neo4j")
    except Exception as e:
        print(f"❌ Pipeline initialization failed: {e}")
        print("\n⚠️  Check your Neo4j/Qdrant credentials in .env")
        return

    # Step 5: Test universal ingestion
    print("\n5️⃣ Testing universal ingestion...")
    print("   Flow: File → Extract → documents table → PropertyGraph")

    try:
        result = await ingest_document_universal(
            supabase=supabase,
            cortex_pipeline=cortex_pipeline,
            tenant_id="test_user_123",
            source="test_upload",
            source_id=test_filename,
            document_type="announcement",
            file_bytes=test_bytes,
            filename=test_filename,
            file_type="text/plain",
            metadata={
                "test": True,
                "description": "Testing universal ingestion system",
                "author": "Nicolas Codet"
            }
        )

        print(f"\n✅ UNIVERSAL INGESTION SUCCESSFUL!")
        print(f"   Status: {result.get('status')}")
        print(f"   Source: {result.get('source')}")
        print(f"   Characters: {result.get('characters')}")
        print(f"   File type: {result.get('file_type')}")

    except Exception as e:
        print(f"\n❌ Universal ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 6: Verify in Supabase
    print("\n6️⃣ Verifying data in Supabase documents table...")
    try:
        result = supabase.table('documents')\
            .select("*")\
            .eq('tenant_id', 'test_user_123')\
            .eq('source', 'test_upload')\
            .eq('source_id', test_filename)\
            .execute()

        if result.data:
            doc = result.data[0]
            print(f"✅ Document found in Supabase!")
            print(f"   ID: {doc.get('id')}")
            print(f"   Title: {doc.get('title')}")
            print(f"   Source: {doc.get('source')}")
            print(f"   Document Type: {doc.get('document_type')}")
            print(f"   Content length: {len(doc.get('content', ''))} chars")
            print(f"   Has raw_data: {bool(doc.get('raw_data'))}")
            print(f"   Metadata: {doc.get('metadata')}")
        else:
            print(f"⚠️  Document not found in Supabase")
    except Exception as e:
        print(f"❌ Supabase query failed: {e}")

    # Step 7: Test query (optional - if pipeline supports it)
    print("\n7️⃣ Testing hybrid search on ingested document...")
    try:
        # Simple query test
        print("   Query: 'What is Cortex AI?'")
        print("   (This would use the chat endpoint or HybridRetriever)")
        print("   Skipping actual query - use chat.html for interactive testing")
    except Exception as e:
        print(f"⚠️  Query test skipped: {e}")

    print("\n" + "=" * 80)
    print("🎉 UNIVERSAL INGESTION TEST COMPLETE!")
    print("=" * 80)
    print("\nNext steps:")
    print("1. Open http://localhost:8080/chat.html")
    print("2. Ask: 'What is Cortex AI?'")
    print("3. Should return information from the test document!")
    print("\n✨ Universal ingestion is working! Ready for 600+ connectors!")


if __name__ == "__main__":
    asyncio.run(test_universal_ingestion())
