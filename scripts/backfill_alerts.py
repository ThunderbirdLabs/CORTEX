#!/usr/bin/env python3
"""
Backfill Alerts Script

Generates alerts for existing documents in the database.
This is useful for:
- Initial setup (analyze existing documents)
- Testing the alert system
- Reprocessing documents with updated detection logic

Usage:
    python scripts/backfill_alerts.py --tenant-id <tenant_id> --limit 100 --recent

Options:
    --tenant-id: Your tenant/user ID (required)
    --limit: Maximum number of documents to process (default: 100)
    --recent: Only process documents from the last 7 days (default: False)
    --all: Process all documents without recent filter
"""
import argparse
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.jobs.alert_tasks import batch_detect_urgency_task


def main():
    parser = argparse.ArgumentParser(
        description="Backfill alerts for existing documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process last 100 recent documents for a tenant
  python scripts/backfill_alerts.py --tenant-id abc123 --limit 100 --recent

  # Process all documents (up to 1000) for a tenant
  python scripts/backfill_alerts.py --tenant-id abc123 --limit 1000 --all

  # Process last 50 recent documents
  python scripts/backfill_alerts.py --tenant-id abc123 --limit 50 --recent
        """
    )

    parser.add_argument(
        "--tenant-id",
        required=True,
        help="Tenant/User ID to process documents for"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of documents to process (default: 100, max: 1000)"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--recent",
        action="store_true",
        help="Only process documents from the last 7 days (default: False)"
    )

    group.add_argument(
        "--all",
        action="store_true",
        help="Process all documents (no time filter)"
    )

    args = parser.parse_args()

    # Validate limit
    if args.limit < 1 or args.limit > 1000:
        print("❌ Error: --limit must be between 1 and 1000")
        sys.exit(1)

    # Determine only_recent flag
    only_recent = args.recent  # If --recent is specified, True; otherwise False
    if args.all:
        only_recent = False

    print("=" * 60)
    print("🚨 CORTEX Alert Backfill Script")
    print("=" * 60)
    print(f"\nTenant ID: {args.tenant_id}")
    print(f"Document Limit: {args.limit}")
    print(f"Time Filter: {'Last 7 days only' if only_recent else 'All time'}")
    print("\nThis will:")
    print("1. Query documents that don't have urgency detection yet")
    print("2. Analyze each document for urgency signals")
    print("3. Create alerts for documents that require attention")
    print("\n" + "=" * 60)

    # Confirm
    response = input("\nContinue? (y/n): ").strip().lower()
    if response not in ["y", "yes"]:
        print("❌ Aborted by user")
        sys.exit(0)

    print("\n🔄 Starting batch urgency detection...")
    print("This may take a few minutes depending on the number of documents.\n")

    try:
        # Send the task to Dramatiq
        batch_detect_urgency_task.send(
            tenant_id=args.tenant_id,
            limit=args.limit,
            only_recent=only_recent
        )

        print("✅ Task queued successfully!")
        print("\nThe alert detection is running in the background via Dramatiq.")
        print("Check your alerts page or logs to see results.")
        print("\nNote: Make sure Dramatiq workers are running:")
        print("  dramatiq app.services.jobs.alert_tasks")

    except Exception as e:
        print(f"\n❌ Error: Failed to queue task: {e}")
        print("\nMake sure:")
        print("1. Redis is running (Dramatiq message broker)")
        print("2. Environment variables are set (SUPABASE_URL, SUPABASE_SERVICE_KEY)")
        print("3. Dramatiq is configured properly")
        sys.exit(1)


if __name__ == "__main__":
    main()
