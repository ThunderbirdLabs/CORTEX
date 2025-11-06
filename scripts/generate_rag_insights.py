#!/usr/bin/env python3
"""
Generate RAG-Powered Intelligence Insights

Runs actual business intelligence searches against your RAG system
and stores the AI-generated answers with source documents.

This replaces the old document-counting approach with real insights!
"""
import os
import sys
import asyncio
from datetime import date
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase import create_client
from app.core.config import settings
from app.services.intelligence.rag_insights_generator import generate_all_insights_for_tenant
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Generate RAG insights for a tenant."""

    logger.info("=" * 80)
    logger.info("RAG Intelligence Generator - Generate Real Business Insights")
    logger.info("=" * 80)

    # Initialize Supabase
    logger.info("📡 Initializing Supabase...")
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    logger.info("✅ Supabase initialized")

    # Get tenant ID from documents (you should have 600 Outlook emails)
    logger.info("\n" + "=" * 80)
    logger.info("Step 1: Finding tenant ID...")
    logger.info("=" * 80)

    result = supabase.table("documents").select("tenant_id").limit(1).execute()

    if not result.data:
        logger.error("❌ No documents found! You need to sync some data first.")
        return

    tenant_id = result.data[0]["tenant_id"]
    logger.info(f"✅ Found tenant ID: {tenant_id}")

    # Check if migration was run
    logger.info("\n" + "=" * 80)
    logger.info("Step 2: Checking database schema...")
    logger.info("=" * 80)

    try:
        # Try to query the new table
        supabase.table("intelligence_insights").select("id").limit(1).execute()
        logger.info("✅ intelligence_insights table exists")
    except Exception as e:
        logger.error("❌ intelligence_insights table doesn't exist!")
        logger.error("   Please run migrations/create_rag_intelligence.sql in Supabase first")
        logger.error(f"   Error: {e}")
        return

    try:
        # Check if seed data exists
        result = supabase.table("intelligence_search_queries")\
            .select("count", count='exact')\
            .execute()
        query_count = result.count if hasattr(result, 'count') else 0
        logger.info(f"✅ Found {query_count} predefined queries")

        if query_count == 0:
            logger.warning("⚠️  No queries found - seed data may not have loaded")

    except Exception as e:
        logger.error(f"❌ intelligence_search_queries table issue: {e}")
        return

    # Generate insights!
    logger.info("\n" + "=" * 80)
    logger.info("Step 3: Running RAG searches and generating insights...")
    logger.info("=" * 80)
    logger.info("")
    logger.info("This will run ~15 searches against your 600 emails:")
    logger.info("  - 5 daily questions (today's activity)")
    logger.info("  - 5 weekly questions (this week's trends)")
    logger.info("  - 5 monthly questions (this month's overview)")
    logger.info("")
    logger.info("Each search uses GPT-4o-mini + hybrid RAG (vector + keyword + graph)")
    logger.info("Results will be stored with source documents for drill-down")
    logger.info("")

    try:
        results = await generate_all_insights_for_tenant(
            supabase=supabase,
            tenant_id=tenant_id,
            target_date=date.today()
        )

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("Generation Results")
        logger.info("=" * 80)

        for period in ["daily", "weekly", "monthly"]:
            period_results = results.get(period, {})

            if isinstance(period_results, dict) and "error" in period_results:
                logger.error(f"❌ {period.capitalize()}: {period_results['error']}")
            elif isinstance(period_results, dict):
                successes = period_results.get("successes", 0)
                failures = period_results.get("failures", 0)
                duration = period_results.get("total_duration_ms", 0)

                if successes > 0:
                    logger.info(f"✅ {period.capitalize()}: {successes} insights generated in {duration}ms")
                    logger.info(f"   Failures: {failures}")
                else:
                    logger.warning(f"⚠️  {period.capitalize()}: No insights generated (check logs above)")

        logger.info("\n" + "=" * 80)
        logger.info("✅ RAG insight generation complete!")
        logger.info("=" * 80)
        logger.info("")
        logger.info("🎯 Next steps:")
        logger.info("   1. Refresh your dashboard in the browser")
        logger.info("   2. You should see real AI-generated business insights")
        logger.info("   3. Click on insights to see source documents")
        logger.info("   4. Run this script nightly via cron to keep dashboard fresh")
        logger.info("")

    except Exception as e:
        logger.error(f"❌ Failed to generate insights: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
