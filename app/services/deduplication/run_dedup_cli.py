"""
CLI script for running entity deduplication.
Designed to be called by Render Cron Jobs.

Usage:
    python -m app.services.deduplication.run_dedup_cli
"""
import sys
from app.services.deduplication.entity_deduplication import run_entity_deduplication
from app.core.config import settings
from app.core.config_master import master_config

def main():
    from datetime import datetime, timezone
    import time

    # Initialize master_supabase_client for multi-tenant mode
    if master_config.is_multi_tenant:
        from supabase import create_client
        import app.core.dependencies as deps

        print(f"🏢 Cron job initializing multi-tenant mode (Company ID: {master_config.company_id})")
        deps.master_supabase_client = create_client(
            master_config.master_supabase_url,
            master_config.master_supabase_service_key
        )
        print("✅ Cron job: Master Supabase client initialized")

    start_time = time.time()
    print(f"🚀 Starting deduplication at {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    print(f"   Similarity: {settings.dedup_similarity_threshold} | Levenshtein: {settings.dedup_levenshtein_max_distance} | Lookback: 24h")

    try:
        results = run_entity_deduplication(
            neo4j_uri=settings.neo4j_uri,
            neo4j_password=settings.neo4j_password,
            dry_run=False,
            similarity_threshold=settings.dedup_similarity_threshold,
            levenshtein_max_distance=settings.dedup_levenshtein_max_distance,
            hours_lookback=24,
            openai_api_key=settings.openai_api_key  # For self-healing embedding regeneration
        )

        elapsed = time.time() - start_time
        merged_count = results.get("entities_merged", 0)
        skipped_count = results.get("clusters_skipped", 0)
        embeddings_regen = results.get("embeddings_regenerated", 0)
        examples = results.get("merge_examples", [])

        if merged_count > 0:
            print(f"✅ Merged {merged_count} entities in {elapsed:.1f}s")
            if skipped_count > 0:
                print(f"   ℹ️  Skipped {skipped_count} already-merged clusters")
            if embeddings_regen > 0:
                print(f"   🔧 Regenerated {embeddings_regen} missing embeddings (self-healing)")

            # Show examples of what was merged
            if examples:
                print(f"\n   📋 Examples merged:")
                for i, ex in enumerate(examples[:5], 1):
                    dups = ', '.join(ex['duplicates'])
                    print(f"      {i}. {ex['primary']} ← [{dups}]")
        else:
            print(f"✅ No duplicates found ({elapsed:.1f}s)")

        return 0

    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
