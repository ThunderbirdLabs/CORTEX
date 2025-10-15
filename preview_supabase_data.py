"""
Preview Supabase email data
"""
from dotenv import load_dotenv
from supabase import create_client
import os
import json

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

result = supabase.table("emails").select("*").limit(1).execute()

if result.data:
    email = result.data[0]
    print("Sample Email Row:")
    print("=" * 80)
    for key, value in email.items():
        if key == "full_body":
            print(f"{key}: {str(value)[:200]}..." if value else f"{key}: None")
        else:
            print(f"{key}: {value}")
    print("=" * 80)
