"""
Create Qdrant indexes for thread deduplication
Makes thread_id filtering instant instead of full collection scan
"""
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

QDRANT_URL = "https://548c56e8-4540-4adc-9c27-311c37dfd84c.us-west-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.9YR8jyKOwa7f3-xf61Yuv-iEiGT_K33sdMOvyRP7Z5Q"
COLLECTION_NAME = "cortex_documents"

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

print("="*100)
print("CREATING QDRANT INDEXES FOR THREAD DEDUPLICATION")
print("="*100)
print()

# Check current indexes
collection = client.get_collection(COLLECTION_NAME)
print(f"Collection: {COLLECTION_NAME}")
print(f"Total points: {collection.points_count:,}")
print()

# Create index on thread_id (keyword type for exact matching)
print("Creating index on 'thread_id' field...")
try:
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="thread_id",
        field_schema=PayloadSchemaType.KEYWORD
    )
    print("  ✅ thread_id index created")
except Exception as e:
    if "already exists" in str(e).lower():
        print("  ℹ️  thread_id index already exists")
    else:
        print(f"  ❌ Error: {e}")

print()

# Also create index on message_id (useful for exact lookups)
print("Creating index on 'message_id' field...")
try:
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="message_id",
        field_schema=PayloadSchemaType.KEYWORD
    )
    print("  ✅ message_id index created")
except Exception as e:
    if "already exists" in str(e).lower():
        print("  ℹ️  message_id index already exists")
    else:
        print(f"  ❌ Error: {e}")

print()

# Verify indexes exist
print("="*100)
print("VERIFYING INDEXES")
print("="*100)
print()

collection_info = client.get_collection(COLLECTION_NAME)
print("Payload indexes:")
if hasattr(collection_info.config, 'params') and hasattr(collection_info.config.params, 'payload_schema'):
    for field, schema in collection_info.config.params.payload_schema.items():
        print(f"  {field}: {schema}")
else:
    print("  (Unable to retrieve - check Qdrant dashboard)")

print()
print("="*100)
print("DONE - Thread dedup will now be instant")
print("="*100)
