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
    print("🚀 Starting entity deduplication...")

    try:
        results = run_entity_deduplication(
            neo4j_uri=settings.neo4j_uri,
            neo4j_password=settings.neo4j_password,
            dry_run=False,
            similarity_threshold=settings.dedup_similarity_threshold,
            levenshtein_max_distance=settings.dedup_levenshtein_max_distance,
            hours_lookback=24
        )

        merged_count = results.get("entities_merged", 0)

        if merged_count > 0:
            print(f"✅ Deduplication complete: {merged_count} entities merged")
        else:
            print("✅ Deduplication complete: no duplicates found")

        return 0

    except Exception as e:
        print(f"❌ Deduplication failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
