#!/usr/bin/env python3
"""
Synchronous Alert Backfill Script

Generates alerts for existing documents IMMEDIATELY (no background queue).
Use this for quick testing or when you don't have Dramatiq workers running.

For production, use backfill_alerts.py with Dramatiq workers instead.

Usage:
    python scripts/backfill_alerts_sync.py --tenant-id <tenant_id> --limit 100
"""
import argparse
import sys
import os
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from app.services.intelligence.realtime_detector import detect_urgency


async def backfill_alerts_sync(tenant_id: str, limit: int, only_recent: bool):
    """
    Synchronously process documents and generate alerts.

    Args:
        tenant_id: Tenant ID to process
        limit: Max documents to process
        only_recent: Only process last 7 days
    """
    print(f"🔄 Connecting to Supabase...")

    # Create Supabase client
    supabase = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_ANON_KEY")
    )

    print(f"📄 Querying documents for tenant {tenant_id}...")

    # Fetch documents that don't have urgency detected yet
    query = supabase.table("documents")\
        .select("id, title, content, metadata, source")\
        .eq("tenant_id", tenant_id)\
        .is_("urgency_level", "null")\
        .limit(limit)

    result = query.execute()
    documents = result.data or []

    print(f"\n📊 Found {len(documents)} documents to analyze\n")

    if not documents:
        print("✅ No documents to process")
        return

    # Process documents one by one
    alerts_created = 0
    processed = 0

    for i, doc in enumerate(documents, 1):
        doc_id = doc["id"]
        doc_title = doc.get("title", "Untitled")[:50]

        try:
            print(f"[{i}/{len(documents)}] Analyzing: {doc_title}...")

            alert = await detect_urgency(
                document_id=doc_id,
                title=doc.get("title", ""),
                content=doc.get("content", ""),
                metadata=doc.get("metadata", {}),
                source=doc.get("source", "unknown"),
                tenant_id=tenant_id,
                supabase=supabase
            )

            processed += 1

            if alert:
                alerts_created += 1
                urgency = alert.get("urgency_level", "unknown")
                alert_type = alert.get("alert_type", "unknown")
                print(f"  ✅ Alert created: {urgency} - {alert_type}")
            else:
                print(f"  ✓ No alert needed")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            continue

    print("\n" + "=" * 60)
    print(f"✅ Processing complete!")
    print(f"   Processed: {processed}/{len(documents)} documents")
    print(f"   Alerts created: {alerts_created}")
    print(f"   Success rate: {(processed/len(documents)*100):.1f}%")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Synchronously backfill alerts for existing documents (no Dramatiq required)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process last 100 recent documents
  python scripts/backfill_alerts_sync.py --tenant-id abc123 --limit 100 --recent

  # Process all documents (up to 50)
  python scripts/backfill_alerts_sync.py --tenant-id abc123 --limit 50

  # Quick test with 10 documents
  python scripts/backfill_alerts_sync.py --tenant-id abc123 --limit 10 --recent
        """
    )

    parser.add_argument(
        "--tenant-id",
        required=False,
        default=None,
        help="Tenant/User ID to process documents for (auto-detected if not provided)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of documents to process (default: 100)"
    )

    parser.add_argument(
        "--recent",
        action="store_true",
        help="Only process documents from the last 7 days"
    )

    args = parser.parse_args()

    # Validate limit
    if args.limit < 1 or args.limit > 1000:
        print("❌ Error: --limit must be between 1 and 1000")
        sys.exit(1)

    # Auto-detect tenant_id if not provided
    tenant_id = args.tenant_id
    if not tenant_id:
        print("🔍 Auto-detecting tenant ID...")
        try:
            supabase = create_client(
                os.getenv("SUPABASE_URL"),
                os.getenv("SUPABASE_ANON_KEY")
            )
            result = supabase.table("documents").select("tenant_id").limit(1).execute()
            if result.data:
                tenant_id = result.data[0]["tenant_id"]
                print(f"✅ Detected tenant ID: {tenant_id}\n")
            else:
                print("❌ No documents found in database. Cannot auto-detect tenant ID.")
                sys.exit(1)
        except Exception as e:
            print(f"❌ Failed to auto-detect tenant ID: {e}")
            print("Please provide --tenant-id manually")
            sys.exit(1)

    print("=" * 60)
    print("🚨 CORTEX Synchronous Alert Backfill")
    print("=" * 60)
    print(f"\nTenant ID: {tenant_id}")
    print(f"Document Limit: {args.limit}")
    print(f"Time Filter: {'Last 7 days only' if args.recent else 'All time'}")
    print("\n⚠️  NOTE: This runs synchronously (may take a while)")
    print("For production, use backfill_alerts.py with Dramatiq workers")
    print("\n" + "=" * 60)

    # Confirm
    response = input("\nContinue? (y/n): ").strip().lower()
    if response not in ["y", "yes"]:
        print("❌ Aborted by user")
        sys.exit(0)

    print()

    try:
        # Run the async function
        asyncio.run(
            backfill_alerts_sync(
                tenant_id=tenant_id,
                limit=args.limit,
                only_recent=args.recent
            )
        )

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
