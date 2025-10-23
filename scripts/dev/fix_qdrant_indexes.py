"""
Fix Qdrant Collection - Add Missing doc_id Index

This script adds the required payload index for doc_id field.
LlamaIndex's IngestionPipeline requires this index for document deduplication.

Safe to run on production - only adds missing index, doesn't modify data.
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

load_dotenv()

def main():
    print("="*80)
    print("FIX QDRANT COLLECTION - ADD doc_id INDEX")
    print("="*80)
    
    # Connect to Qdrant
    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")
    
    if not qdrant_url or not qdrant_api_key:
        print("❌ Error: QDRANT_URL and QDRANT_API_KEY must be set")
        return
    
    print(f"\n📡 Connecting to Qdrant...")
    print(f"   URL: {qdrant_url}")
    print(f"   Collection: {collection_name}")
    
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
    
    try:
        # Check if collection exists
        collection = client.get_collection(collection_name)
        print(f"\n✅ Collection exists")
        print(f"   Points: {collection.points_count}")
        print(f"   Vectors: {collection.vectors_count}")
        
        # Check current indexes
        print(f"\n🔍 Current payload schema:")
        if collection.payload_schema:
            for field, schema in collection.payload_schema.items():
                print(f"   - {field}: {schema}")
        else:
            print("   (No payload schema defined)")
        
        # Add doc_id index
        print(f"\n🔧 Creating doc_id keyword index...")
        client.create_payload_index(
            collection_name=collection_name,
            field_name="doc_id",
            field_schema=PayloadSchemaType.KEYWORD
        )
        print("   ✅ Index created successfully!")
        
        # Also add ref_doc_id index (LlamaIndex uses both)
        print(f"\n🔧 Creating ref_doc_id keyword index...")
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name="ref_doc_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            print("   ✅ Index created successfully!")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("   ℹ️  Index already exists")
            else:
                print(f"   ⚠️  Warning: {e}")
        
        # Verify indexes
        print(f"\n✅ Verification - Updated payload schema:")
        collection = client.get_collection(collection_name)
        if collection.payload_schema:
            for field, schema in collection.payload_schema.items():
                print(f"   - {field}: {schema}")
        
        print(f"\n" + "="*80)
        print("✅ QDRANT INDEXES FIXED!")
        print("="*80)
        print("\n💡 You can now sync Google Drive without errors!")
        print("   Try running: GET /sync/once/drive")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == "__main__":
    main()

