"""
CLI script for running entity deduplication.
Designed to be called by Render Cron Jobs.

Usage:
    python -m app.services.deduplication.run_dedup_cli
"""
import sys
from app.services.deduplication.entity_deduplication import run_entity_deduplication
from app.core.config import settings

def main():
    from datetime import datetime, timezone
    import time

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
            hours_lookback=24
        )

        elapsed = time.time() - start_time
        merged_count = results.get("entities_merged", 0)

        if merged_count > 0:
            print(f"✅ Merged {merged_count} entities in {elapsed:.1f}s")
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
