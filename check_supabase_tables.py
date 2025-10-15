"""
Quick script to check Supabase tables and preview data
"""
from dotenv import load_dotenv
from supabase import create_client
import os

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# Try to list tables by querying information_schema
print("Checking for common tables...\n")

tables_to_check = ["emails", "documents", "messages", "deals", "contacts"]

for table in tables_to_check:
    try:
        result = supabase.table(table).select("*").limit(1).execute()
        if result.data:
            print(f"✅ Table '{table}' exists")
            print(f"   Sample row keys: {list(result.data[0].keys())}")
            print(f"   Checking count...")
            count_result = supabase.table(table).select("id", count="exact").execute()
            print(f"   Total rows: {count_result.count}\n")
    except Exception as e:
        print(f"❌ Table '{table}' not found or error: {str(e)[:100]}\n")
