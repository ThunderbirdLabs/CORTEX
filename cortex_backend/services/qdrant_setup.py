"""
Qdrant Collection Setup

Creates and configures the Qdrant collection with schema matching
the current Supabase pgvector structure to preserve all metadata
and ensure seamless migration.
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PayloadSchemaType,
    CreateCollection,
    PointStruct
)

load_dotenv()


def create_qdrant_collection():
    """
    Create Qdrant collection matching Supabase schema.

    Supabase columns → Qdrant payload mapping:
    - id (UUID) → id (UUID as string)
    - document_name → payload.document_name
    - source → payload.source
    - document_type → payload.document_type
    - created_at → payload.created_at
    - content → payload.content
    - chunk_index → payload.chunk_index
    - total_chunks → payload.total_chunks
    - embedding (VECTOR) → vector
    - graphiti_episode_id (TEXT) → payload.graphiti_episode_id
    - metadata (JSONB) → payload.metadata
    """

    # Initialize Qdrant client
    client = QdrantClient(
        url=os.getenv("QDRANT_URL"),
        api_key=os.getenv("QDRANT_API_KEY"),
    )

    collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

    print(f"🔧 Setting up Qdrant collection: {collection_name}")
    print(f"   URL: {os.getenv('QDRANT_URL')}\n")

    # Check if collection already exists
    try:
        collections = client.get_collections().collections
        existing_names = [c.name for c in collections]

        if collection_name in existing_names:
            print(f"⚠️  Collection '{collection_name}' already exists!")
            response = input("   Delete and recreate? (yes/no): ").strip().lower()

            if response == "yes":
                client.delete_collection(collection_name)
                print(f"   ✅ Deleted existing collection\n")
            else:
                print(f"   ❌ Aborting. Collection unchanged.\n")
                return
    except Exception as e:
        print(f"   ℹ️  No existing collections found\n")

    # Create collection with vector configuration
    # OpenAI text-embedding-3-small = 1536 dimensions
    # Using Cosine distance (matches pgvector default)
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=1536,
            distance=Distance.COSINE
        )
    )

    print(f"✅ Created collection '{collection_name}'")
    print(f"   Vector dimensions: 1536 (OpenAI text-embedding-3-small)")
    print(f"   Distance metric: Cosine\n")

    # Create payload indexes for efficient filtering
    # These match the columns we frequently filter/search on

    print("🔧 Creating payload indexes for efficient filtering...\n")

    # Index: document_name (for exact match filtering)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_name",
        field_schema=PayloadSchemaType.KEYWORD
    )
    print("   ✅ Indexed: document_name (KEYWORD)")

    # Index: source (gmail, slack, hubspot, etc.)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="source",
        field_schema=PayloadSchemaType.KEYWORD
    )
    print("   ✅ Indexed: source (KEYWORD)")

    # Index: document_type (email, doc, deal, etc.)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="document_type",
        field_schema=PayloadSchemaType.KEYWORD
    )
    print("   ✅ Indexed: document_type (KEYWORD)")

    # Index: graphiti_episode_id (CRITICAL for Neo4j linking!)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="graphiti_episode_id",
        field_schema=PayloadSchemaType.KEYWORD
    )
    print("   ✅ Indexed: graphiti_episode_id (KEYWORD) 🔗 NEO4J LINK")

    # Index: chunk_index (for ordering chunks)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="chunk_index",
        field_schema=PayloadSchemaType.INTEGER
    )
    print("   ✅ Indexed: chunk_index (INTEGER)")

    print("\n" + "="*80)
    print("✅ QDRANT SETUP COMPLETE")
    print("="*80)
    print(f"\nCollection: {collection_name}")
    print(f"Vector Store: Ready for ingestion")
    print(f"Neo4j Linking: graphiti_episode_id indexed for fast filtering")
    print(f"\nNext steps:")
    print(f"  1. Run migration script to copy data from Supabase")
    print(f"  2. Update hybrid_query_engine.py to use Qdrant")
    print(f"  3. Test retrieval with episode_id filtering")
    print("="*80 + "\n")

    # Show collection info
    collection_info = client.get_collection(collection_name)
    print(f"📊 Collection Info:")
    print(f"   Points count: {collection_info.points_count}")
    print(f"   Vectors count: {collection_info.vectors_count}")
    print(f"   Indexed payload fields: {len(collection_info.payload_schema)}")
    print()


if __name__ == "__main__":
    create_qdrant_collection()
