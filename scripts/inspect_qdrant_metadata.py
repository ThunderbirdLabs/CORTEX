"""
Inspect Qdrant collection to see what metadata is stored in vectors
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()

# Connect to Qdrant
qdrant_url = os.getenv("QDRANT_URL")
qdrant_api_key = os.getenv("QDRANT_API_KEY")
collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

print("=" * 80)
print("QDRANT COLLECTION INSPECTION")
print("=" * 80)

# Get collection info
try:
    collection_info = client.get_collection(collection_name)
    print(f"\n✅ Collection: {collection_name}")
    print(f"   Vectors count: {collection_info.points_count}")
    print(f"   Vector size: {collection_info.config.params.vectors.size}")
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

# Scroll through first 5 points to see metadata
print("\n" + "=" * 80)
print("SAMPLE VECTOR METADATA (First 3 points)")
print("=" * 80)

try:
    points, _ = client.scroll(
        collection_name=collection_name,
        limit=3,
        with_payload=True,
        with_vectors=False
    )

    for i, point in enumerate(points, 1):
        print(f"\n🔢 Point {i} (ID: {point.id}):")
        payload = point.payload or {}

        # Show key metadata fields
        print(f"   document_type: {payload.get('document_type', 'N/A')}")
        print(f"   document_name: {payload.get('document_name', 'N/A')}")
        print(f"   source: {payload.get('source', 'N/A')}")
        print(f"   created_at_timestamp: {payload.get('created_at_timestamp', 'N/A')}")
        print(f"   chunk_index: {payload.get('chunk_index', 'N/A')}")

        # Show all payload keys
        print(f"\n   All payload keys:")
        for key in sorted(payload.keys()):
            value = payload[key]
            # Truncate long values
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"      - {key}: {value}")

except Exception as e:
    print(f"❌ Error scrolling points: {e}")

# Check indexed fields
print("\n" + "=" * 80)
print("PAYLOAD INDEXES")
print("=" * 80)

try:
    collection_info = client.get_collection(collection_name)
    if collection_info.payload_schema:
        print(f"\n✅ Indexed fields:")
        for field, schema in collection_info.payload_schema.items():
            print(f"   - {field}: {schema}")
    else:
        print("\n⚠️  No payload indexes configured")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 80)
