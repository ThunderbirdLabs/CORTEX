#!/usr/bin/env python3
"""
Manual Dashboard Data Generator
================================
Generates intelligence summaries and processes documents for dashboard widgets.

Usage:
    python scripts/generate_dashboard_data.py

What it does:
1. Generates daily intelligence for today (Activity Pulse, Intelligence Feed)
2. Generates weekly intelligence (Trends)
3. Checks if documents are processed in Neo4j (Entities, Deals)
4. Reports what data is available for each widget

This should populate all the dashboard widgets with real data.
"""
import os
import sys
import asyncio
from datetime import datetime, date, timedelta
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Now import app modules
from supabase import create_client, Client
from app.services.intelligence.aggregator import (
    calculate_daily_metrics,
    calculate_weekly_trends,
    calculate_monthly_insights
)
from app.core.config import settings
from neo4j import AsyncGraphDatabase

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    """Main execution function."""
    logger.info("=" * 80)
    logger.info("Dashboard Data Generator - Manual Intelligence Generation")
    logger.info("=" * 80)

    # Initialize clients
    logger.info("📡 Initializing Supabase and Neo4j clients...")
    supabase: Client = create_client(
        settings.supabase_url,
        settings.supabase_anon_key
    )

    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password)
    )

    logger.info("✅ Clients initialized")

    # Step 1: Get tenant ID (first user in the system)
    logger.info("\n" + "=" * 80)
    logger.info("Step 1: Finding tenant ID...")
    logger.info("=" * 80)

    # Query for a document to get tenant_id
    result = supabase.table("documents").select("tenant_id").limit(1).execute()

    if not result.data:
        logger.error("❌ No documents found! Sync some data first.")
        return

    tenant_id = result.data[0]["tenant_id"]
    logger.info(f"✅ Found tenant ID: {tenant_id}")

    # Step 2: Check document counts
    logger.info("\n" + "=" * 80)
    logger.info("Step 2: Analyzing documents...")
    logger.info("=" * 80)

    # Get document stats
    docs = supabase.table("documents").select("*").eq("tenant_id", tenant_id).execute()
    total_docs = len(docs.data)

    # Group by source
    sources = {}
    for doc in docs.data:
        source = doc.get("source", "unknown")
        sources[source] = sources.get(source, 0) + 1

    logger.info(f"📊 Total documents: {total_docs}")
    for source, count in sources.items():
        logger.info(f"   - {source}: {count} documents")

    # Step 3: Check Neo4j entities
    logger.info("\n" + "=" * 80)
    logger.info("Step 3: Checking Neo4j knowledge graph...")
    logger.info("=" * 80)

    async with neo4j_driver.session() as session:
        # Count PERSON nodes
        result = await session.run(
            "MATCH (p:PERSON) WHERE p.tenant_id = $tenant_id RETURN count(p) as count",
            tenant_id=tenant_id
        )
        person_count = (await result.single())["count"]

        # Count COMPANY nodes
        result = await session.run(
            "MATCH (c:COMPANY) WHERE c.tenant_id = $tenant_id RETURN count(c) as count",
            tenant_id=tenant_id
        )
        company_count = (await result.single())["count"]

        # Count PURCHASE_ORDER nodes
        result = await session.run(
            "MATCH (po:PURCHASE_ORDER) WHERE po.tenant_id = $tenant_id RETURN count(po) as count",
            tenant_id=tenant_id
        )
        po_count = (await result.single())["count"]

    logger.info(f"👥 PERSON entities: {person_count}")
    logger.info(f"🏢 COMPANY entities: {company_count}")
    logger.info(f"📝 PURCHASE_ORDER entities: {po_count}")

    if person_count == 0 and company_count == 0:
        logger.warning("⚠️  No entities found in Neo4j!")
        logger.warning("   Documents exist but haven't been processed through RAG pipeline.")
        logger.warning("   You may need to re-sync or manually trigger entity extraction.")

    # Step 4: Generate daily intelligence
    logger.info("\n" + "=" * 80)
    logger.info("Step 4: Generating daily intelligence...")
    logger.info("=" * 80)

    today = date.today()
    logger.info(f"📅 Generating for date: {today}")

    try:
        daily_data = await calculate_daily_metrics(
            supabase=supabase,
            neo4j_driver=neo4j_driver,
            tenant_id=tenant_id,
            target_date=today
        )

        # Insert into daily_intelligence table
        supabase.table("daily_intelligence").upsert({
            "tenant_id": tenant_id,
            "date": str(today),
            **daily_data
        }).execute()

        logger.info("✅ Daily intelligence generated successfully!")
        logger.info(f"   Total documents: {daily_data.get('total_documents', 0)}")
        logger.info(f"   AI summary: {daily_data.get('ai_summary', 'N/A')[:100]}...")

    except Exception as e:
        logger.error(f"❌ Failed to generate daily intelligence: {e}")
        import traceback
        traceback.print_exc()

    # Step 5: Generate weekly intelligence
    logger.info("\n" + "=" * 80)
    logger.info("Step 5: Generating weekly intelligence...")
    logger.info("=" * 80)

    # Get Monday of current week
    week_start = today - timedelta(days=today.weekday())
    logger.info(f"📅 Generating for week starting: {week_start}")

    try:
        weekly_data = await calculate_weekly_trends(
            supabase=supabase,
            neo4j_driver=neo4j_driver,
            tenant_id=tenant_id,
            week_start=week_start
        )

        # Insert into weekly_intelligence table
        supabase.table("weekly_intelligence").upsert({
            "tenant_id": tenant_id,
            "week_start": str(week_start),
            "week_end": str(week_start + timedelta(days=6)),
            **weekly_data
        }).execute()

        logger.info("✅ Weekly intelligence generated successfully!")
        logger.info(f"   Total documents: {weekly_data.get('total_documents', 0)}")
        logger.info(f"   WoW change: {weekly_data.get('wow_change_percent', 0)}%")

    except Exception as e:
        logger.error(f"❌ Failed to generate weekly intelligence: {e}")
        import traceback
        traceback.print_exc()

    # Step 6: Generate monthly intelligence
    logger.info("\n" + "=" * 80)
    logger.info("Step 6: Generating monthly intelligence...")
    logger.info("=" * 80)

    # First day of current month
    month_start = today.replace(day=1)
    logger.info(f"📅 Generating for month: {month_start}")

    try:
        monthly_data = await calculate_monthly_insights(
            supabase=supabase,
            neo4j_driver=neo4j_driver,
            tenant_id=tenant_id,
            month=month_start
        )

        # Insert into monthly_intelligence table
        supabase.table("monthly_intelligence").upsert({
            "tenant_id": tenant_id,
            "month": str(month_start),
            **monthly_data
        }).execute()

        logger.info("✅ Monthly intelligence generated successfully!")
        logger.info(f"   Total documents: {monthly_data.get('total_documents', 0)}")
        logger.info(f"   Total revenue: ${monthly_data.get('total_revenue', 0):,.2f}")

    except Exception as e:
        logger.error(f"❌ Failed to generate monthly intelligence: {e}")
        import traceback
        traceback.print_exc()

    # Step 7: Summary report
    logger.info("\n" + "=" * 80)
    logger.info("Dashboard Widget Status Report")
    logger.info("=" * 80)

    widgets = [
        ("Activity Pulse", "daily_intelligence table populated" if daily_data else "❌ Failed"),
        ("Intelligence Feed", "daily + weekly intelligence generated" if daily_data and weekly_data else "❌ Failed"),
        ("Trending Entities", f"✅ {person_count} people, {company_count} companies" if person_count > 0 else "❌ No entities in Neo4j"),
        ("Deal Momentum", f"✅ {po_count} purchase orders tracked" if po_count > 0 else "❌ No deals in Neo4j"),
        ("Sentiment Alerts", f"✅ {total_docs} documents available for analysis"),
        ("Communication Patterns", f"✅ {sources.get('gmail', 0) + sources.get('outlook', 0)} emails available"),
    ]

    logger.info("\n📊 Widget Readiness:")
    for widget_name, status in widgets:
        logger.info(f"   {widget_name:25s} → {status}")

    # Close connections
    await neo4j_driver.close()

    logger.info("\n" + "=" * 80)
    logger.info("✅ Dashboard data generation complete!")
    logger.info("=" * 80)
    logger.info("\n🎯 Next steps:")
    logger.info("   1. Refresh your dashboard in the browser")
    logger.info("   2. Check that Activity Pulse and Intelligence Feed now show data")
    logger.info("   3. If Trending Entities still empty, documents need RAG processing")
    logger.info("   4. Run this script again tomorrow to generate more historical data")
    logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
