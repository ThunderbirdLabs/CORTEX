"""
RAG-Powered Intelligence Generator

Runs business intelligence queries against the RAG system and stores results.
This is the "nightly job" that generates actual insights using hybrid search.
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import time

from supabase import Client
from app.core.config import settings
from app.core.dependencies import query_engine as global_query_engine

logger = logging.getLogger(__name__)

# Module-level query engine (initialized if running standalone)
_standalone_query_engine = None

def get_query_engine():
    """Get query engine, initializing if needed for standalone use."""
    global _standalone_query_engine

    # Try global first (FastAPI context)
    if global_query_engine:
        return global_query_engine

    # Initialize standalone if needed
    if not _standalone_query_engine:
        logger.info("🔧 Initializing query engine for standalone script...")
        from app.services.rag.query import HybridQueryEngine
        _standalone_query_engine = HybridQueryEngine()
        logger.info("✅ Query engine initialized")

    return _standalone_query_engine


async def generate_rag_insights(
    supabase: Client,
    tenant_id: str,
    time_period: str = "daily",
    target_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Run all active RAG queries for a given time period and store results.

    Args:
        supabase: Supabase client
        tenant_id: Tenant ID to generate insights for
        time_period: 'daily', 'weekly', or 'monthly'
        target_date: Date to generate insights for (defaults to today)

    Returns:
        Summary stats of generation (queries run, successes, failures, etc.)
    """
    if not target_date:
        target_date = date.today()

    start_time = datetime.utcnow()

    logger.info(f"🔍 Generating {time_period} RAG insights for {tenant_id} on {target_date}")

    # 1. Get all active queries for this time period
    queries_result = supabase.table("intelligence_search_queries")\
        .select("*")\
        .eq("time_period", time_period)\
        .eq("is_active", True)\
        .order("display_order")\
        .execute()

    queries = queries_result.data

    if not queries:
        logger.warning(f"No active queries found for time_period={time_period}")
        return {
            "queries_found": 0,
            "queries_run": 0,
            "successes": 0,
            "failures": 0,
            "total_duration_ms": 0
        }

    logger.info(f"   Found {len(queries)} active queries to run")

    # 2. Run each query against RAG system
    results = {
        "queries_found": len(queries),
        "queries_run": 0,
        "successes": 0,
        "failures": 0,
        "insights": []
    }

    for query_config in queries:
        try:
            insight = await _run_single_rag_query(
                supabase=supabase,
                tenant_id=tenant_id,
                query_config=query_config,
                insight_date=target_date,
                time_period=time_period
            )

            results["queries_run"] += 1

            if insight:
                results["successes"] += 1
                results["insights"].append(insight)
                logger.info(f"   ✅ {query_config['display_title']}: {len(insight.get('source_documents', []))} sources")
            else:
                results["failures"] += 1
                logger.warning(f"   ⚠️  {query_config['display_title']}: No results")

        except Exception as e:
            results["failures"] += 1
            logger.error(f"   ❌ {query_config['display_title']}: {e}")

    total_duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
    results["total_duration_ms"] = total_duration

    logger.info(f"✅ Generated {results['successes']}/{results['queries_run']} insights in {total_duration}ms")

    return results


async def _run_single_rag_query(
    supabase: Client,
    tenant_id: str,
    query_config: Dict[str, Any],
    insight_date: date,
    time_period: str
) -> Optional[Dict[str, Any]]:
    """
    Run a single RAG query and store the result.

    Args:
        supabase: Supabase client
        tenant_id: Tenant ID
        query_config: Query configuration from intelligence_search_queries table
        insight_date: Date this insight is for
        time_period: 'daily', 'weekly', 'monthly'

    Returns:
        The stored insight record, or None if query failed
    """
    start_time = time.time()

    query_text = query_config["query_text"]
    query_category = query_config["query_category"]
    max_sources = query_config.get("max_sources", 5)

    # Add time context to the query
    time_context = _build_time_context(time_period, insight_date)
    contextualized_query = f"{time_context}\n\n{query_text}"

    logger.info(f"   🔎 Running: {query_config['display_title']}")

    # Get query engine (initialized if needed)
    engine = get_query_engine()
    if not engine:
        logger.error("Query engine not initialized!")
        return None

    # Run the RAG search
    try:
        # Use the hybrid search (combines vector + keyword + graph)
        response = await engine.query(contextualized_query)

        # Extract AI answer
        ai_answer = str(response.response) if response.response else "No insights found"

        # Extract source documents with scores
        source_documents = []
        if hasattr(response, 'source_nodes') and response.source_nodes:
            for node in response.source_nodes[:max_sources]:
                source_doc = {
                    "node_id": node.node_id if hasattr(node, 'node_id') else None,
                    "text": node.text[:500] if hasattr(node, 'text') else "",  # Truncate long text
                    "score": float(node.score) if hasattr(node, 'score') else 0.0,
                    "metadata": node.metadata if hasattr(node, 'metadata') else {}
                }
                source_documents.append(source_doc)

        generation_duration_ms = int((time.time() - start_time) * 1000)

        # Calculate confidence (average of source scores)
        confidence_score = None
        if source_documents:
            avg_score = sum(doc['score'] for doc in source_documents) / len(source_documents)
            confidence_score = round(min(avg_score, 1.0), 2)

        # Store in database
        insight_record = {
            "tenant_id": tenant_id,
            "insight_date": str(insight_date),
            "time_period": time_period,
            "search_query": query_text,
            "query_category": query_category,
            "ai_answer": ai_answer,
            "confidence_score": confidence_score,
            "source_documents": source_documents,
            "total_sources": len(source_documents),
            "generation_duration_ms": generation_duration_ms,
            "model_used": "gpt-4o-mini",
            "is_stale": False
        }

        # Upsert (will update if same tenant/date/query exists)
        result = supabase.table("intelligence_insights")\
            .upsert(insight_record)\
            .execute()

        # Update last_run_at for the query
        supabase.table("intelligence_search_queries")\
            .update({"last_run_at": datetime.utcnow().isoformat()})\
            .eq("id", query_config["id"])\
            .execute()

        return result.data[0] if result.data else insight_record

    except Exception as e:
        logger.error(f"Failed to run RAG query '{query_text}': {e}")
        import traceback
        traceback.print_exc()
        return None


def _build_time_context(time_period: str, target_date: date) -> str:
    """
    Build contextual time filter for the RAG query.

    Args:
        time_period: 'daily', 'weekly', 'monthly'
        target_date: The date we're analyzing

    Returns:
        Natural language time context to prepend to query
    """
    if time_period == "daily":
        return f"Based on emails and documents from {target_date.strftime('%A, %B %d, %Y')}:"

    elif time_period == "weekly":
        # Get Monday of the week
        week_start = target_date - timedelta(days=target_date.weekday())
        week_end = week_start + timedelta(days=6)
        return f"Based on emails and documents from the week of {week_start.strftime('%B %d')} to {week_end.strftime('%B %d, %Y')}:"

    elif time_period == "monthly":
        month_name = target_date.strftime('%B %Y')
        return f"Based on emails and documents from {month_name}:"

    else:
        return "Based on recent emails and documents:"


# ============================================================================
# MANUAL TRIGGER SCRIPT
# ============================================================================

async def generate_all_insights_for_tenant(
    supabase: Client,
    tenant_id: str,
    target_date: Optional[date] = None
) -> Dict[str, Any]:
    """
    Generate all insights (daily, weekly, monthly) for a tenant.
    Used for manual testing or backfilling.

    Args:
        supabase: Supabase client
        tenant_id: Tenant ID
        target_date: Date to generate for (defaults to today)

    Returns:
        Combined results from all time periods
    """
    if not target_date:
        target_date = date.today()

    logger.info(f"📊 Generating all insights for tenant {tenant_id}")

    results = {
        "tenant_id": tenant_id,
        "target_date": str(target_date),
        "daily": None,
        "weekly": None,
        "monthly": None
    }

    # Generate daily insights
    try:
        results["daily"] = await generate_rag_insights(
            supabase=supabase,
            tenant_id=tenant_id,
            time_period="daily",
            target_date=target_date
        )
    except Exception as e:
        logger.error(f"Failed to generate daily insights: {e}")
        results["daily"] = {"error": str(e)}

    # Generate weekly insights (only on Mondays or manually)
    try:
        results["weekly"] = await generate_rag_insights(
            supabase=supabase,
            tenant_id=tenant_id,
            time_period="weekly",
            target_date=target_date
        )
    except Exception as e:
        logger.error(f"Failed to generate weekly insights: {e}")
        results["weekly"] = {"error": str(e)}

    # Generate monthly insights (only on 1st of month or manually)
    try:
        results["monthly"] = await generate_rag_insights(
            supabase=supabase,
            tenant_id=tenant_id,
            time_period="monthly",
            target_date=target_date
        )
    except Exception as e:
        logger.error(f"Failed to generate monthly insights: {e}")
        results["monthly"] = {"error": str(e)}

    logger.info(f"✅ Completed insight generation for {tenant_id}")

    return results
