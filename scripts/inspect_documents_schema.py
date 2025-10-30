"""
Inspect Supabase documents table schema and sample data
"""
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

# Connect to Supabase
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(supabase_url, supabase_key)

print("=" * 80)
print("DOCUMENTS TABLE INSPECTION")
print("=" * 80)

# Get sample documents
result = supabase.table("documents").select("*").limit(5).execute()

if result.data:
    print(f"\n✅ Found {len(result.data)} sample documents\n")

    # Get all column names from first document
    if result.data:
        columns = list(result.data[0].keys())
        print("📋 COLUMNS:")
        for col in sorted(columns):
            print(f"   - {col}")

        print("\n" + "=" * 80)
        print("SAMPLE DATA (First 3 documents)")
        print("=" * 80)

        for i, doc in enumerate(result.data[:3], 1):
            print(f"\n🗂️  Document {i}:")
            print(f"   ID: {doc.get('id')}")
            print(f"   document_type: {doc.get('document_type')}")
            print(f"   document_name: {doc.get('document_name')}")
            print(f"   source: {doc.get('source')}")
            print(f"   mime_type: {doc.get('mime_type')}")
            print(f"   file_size_bytes: {doc.get('file_size_bytes')}")
            print(f"   created_at: {doc.get('created_at')}")
            print(f"   metadata keys: {list(doc.get('metadata', {}).keys()) if doc.get('metadata') else 'None'}")
else:
    print("❌ No documents found in table")

# Check what document_types exist
print("\n" + "=" * 80)
print("UNIQUE document_type VALUES")
print("=" * 80)

# Get all documents and extract unique types
all_docs = supabase.table("documents").select("document_type").execute()
if all_docs.data:
    unique_types = set(doc['document_type'] for doc in all_docs.data if doc.get('document_type'))
    print(f"\n✅ Found {len(unique_types)} unique document types:")
    for doc_type in sorted(unique_types):
        print(f"   - {doc_type}")
else:
    print("❌ Could not fetch document types")

print("\n" + "=" * 80)
