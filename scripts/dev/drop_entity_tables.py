"""
Drop entity_candidates table from Supabase (cleanup test tables)
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from supabase import create_client
from app.core.config import settings

print("🗑️  Dropping entity_candidates table from Supabase...")

supabase = create_client(settings.supabase_url, settings.supabase_service_key)

# Use RPC to execute raw SQL for dropping table
try:
    # First check if table exists
    result = supabase.rpc('sql', {
        'query': """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'entity_candidates'
        );
        """
    }).execute()

    if result.data:
        print("   Found entity_candidates table, dropping...")

        # Drop the table
        drop_result = supabase.rpc('sql', {
            'query': 'DROP TABLE IF EXISTS entity_candidates CASCADE;'
        }).execute()

        print("✅ Dropped entity_candidates table")
    else:
        print("   Table doesn't exist, nothing to drop")

except Exception as e:
    print(f"⚠️  Error: {e}")
    print("\nAlternative: Drop via Supabase Dashboard:")
    print("1. Go to https://supabase.com/dashboard")
    print("2. Select your project")
    print("3. Go to 'SQL Editor'")
    print("4. Run: DROP TABLE IF EXISTS entity_candidates CASCADE;")
