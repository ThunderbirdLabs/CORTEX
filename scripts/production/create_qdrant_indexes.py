"""
Create Qdrant payload indexes for faster metadata filtering.

Research: Qdrant payload indexes speed up filtering by 10-100x for time-based queries
https://qdrant.tech/documentation/concepts/indexing/#payload-index

SAFE TO RUN: Indexes are add-only, don't affect ingestion or existing queries
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

load_dotenv()

# Connect to Qdrant
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

print("=" * 80)
print("QDRANT PAYLOAD INDEX CREATION")
print("=" * 80)

# Create indexes for frequently-filtered fields
indexes_to_create = [
    ("document_type", PayloadSchemaType.KEYWORD, "Document type filtering (email/attachment)"),
    ("created_at_timestamp", PayloadSchemaType.INTEGER, "Time-based filtering and recency decay"),
    ("source", PayloadSchemaType.KEYWORD, "Source filtering (outlook, etc.)"),
    ("tenant_id", PayloadSchemaType.KEYWORD, "Multi-tenant isolation"),
]

print(f"\n📊 Collection: {collection_name}")
print(f"🔧 Creating {len(indexes_to_create)} payload indexes...\n")

success_count = 0
for field_name, field_type, description in indexes_to_create:
    try:
        print(f"⚙️  Creating index: {field_name}")
        print(f"   Type: {field_type}")
        print(f"   Purpose: {description}")

        client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=field_type
        )

        print(f"   ✅ Index created successfully\n")
        success_count += 1

    except Exception as e:
        # Index may already exist - check if that's the case
        if "already exists" in str(e).lower():
            print(f"   ⚠️  Index already exists (skipping)\n")
            success_count += 1
        else:
            print(f"   ❌ Error: {e}\n")

print("=" * 80)
print(f"RESULTS: {success_count}/{len(indexes_to_create)} indexes configured")
print("=" * 80)

# Verify indexes
print("\n🔍 Verifying payload indexes...")
try:
    collection_info = client.get_collection(collection_name)
    if collection_info.payload_schema:
        print(f"\n✅ Indexed fields in {collection_name}:")
        for field, schema in collection_info.payload_schema.items():
            print(f"   - {field}: {schema}")
    else:
        print("\n⚠️  No payload schema found (indexes may still be creating)")
except Exception as e:
    print(f"❌ Error verifying indexes: {e}")

print("\n" + "=" * 80)
print("✅ DONE - Qdrant payload indexes configured")
print("📈 Expected impact: 10-100x faster metadata filtering")
print("=" * 80)
