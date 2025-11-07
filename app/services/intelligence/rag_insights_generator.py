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
    output_format = query_config.get("output_format", "text")
    output_schema = query_config.get("output_schema")

    # Add time context to the query
    time_context = _build_time_context(time_period, insight_date)

    # Build contextualized query with JSON schema enforcement if needed
    if output_format != "text" and output_schema:
        # Structured output: enforce JSON schema
        import json
        schema_str = json.dumps(output_schema, indent=2) if isinstance(output_schema, dict) else str(output_schema)
        contextualized_query = f"""{time_context}

{query_text}

CRITICAL INSTRUCTIONS:
You MUST respond with ONLY valid JSON matching this exact schema. Do not include any text outside the JSON.
Do not use markdown code blocks - return raw JSON only.

Required JSON Schema:
{schema_str}

Response (JSON only):"""
    else:
        # Text output: conversational response
        contextualized_query = f"{time_context}\n\n{query_text}"

    logger.info(f"   🔎 Running: {query_config['display_title']} ({output_format})")

    # Get query engine (initialized if needed)
    engine = get_query_engine()
    if not engine:
        logger.error("Query engine not initialized!")
        return None

    # Run the RAG search
    try:
        # Use the hybrid search (combines vector + keyword + graph)
        response = await engine.query(contextualized_query)

        # Extract AI answer from dict response
        ai_answer = response.get("answer", "No insights found") if response else "No insights found"

        # Extract source documents with scores from dict response
        source_documents = []
        source_nodes = response.get("source_nodes", []) if response else []
        for node in source_nodes[:max_sources]:
            # Safely extract score (handle None values)
            score = 0.0
            if hasattr(node, 'score') and node.score is not None:
                try:
                    score = float(node.score)
                except (TypeError, ValueError):
                    score = 0.0

            source_doc = {
                "node_id": node.node_id if hasattr(node, 'node_id') else None,
                "text": node.text[:500] if hasattr(node, 'text') else "",  # Truncate long text
                "score": score,
                "metadata": node.metadata if hasattr(node, 'metadata') else {}
            }
            source_documents.append(source_doc)

        generation_duration_ms = int((time.time() - start_time) * 1000)

        # Calculate confidence (average of source scores)
        confidence_score = None
        if source_documents:
            avg_score = sum(doc['score'] for doc in source_documents) / len(source_documents)
            confidence_score = round(min(avg_score, 1.0), 2)

        # Parse structured data if JSON format expected
        structured_data = None
        if output_format != "text" and output_schema:
            import json
            import re
            try:
                # Try to extract JSON from response (GPT sometimes adds markdown)
                # First, try direct parse
                try:
                    structured_data = json.loads(ai_answer)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code block
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```', ai_answer, re.DOTALL)
                    if json_match:
                        structured_data = json.loads(json_match.group(1))
                    else:
                        # Try to find any JSON object/array in the text
                        json_match = re.search(r'(\{.*?\}|\[.*?\])', ai_answer, re.DOTALL)
                        if json_match:
                            structured_data = json.loads(json_match.group(1))

                logger.info(f"      ✅ Parsed structured JSON ({output_format})")
            except Exception as e:
                logger.warning(f"      ⚠️  Failed to parse structured JSON: {e}")
                # Keep ai_answer as-is for debugging

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
            "is_stale": False,
            "structured_data": structured_data
        }

        # Upsert (will update if same tenant/date/query exists)
        # Use on_conflict to specify which constraint to check
        result = supabase.table("intelligence_insights")\
            .upsert(
                insight_record,
                on_conflict="tenant_id,insight_date,search_query"
            )\
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


async def generate_drill_down_report(
    supabase: Client,
    tenant_id: str,
    widget_title: str,
    widget_message: str
) -> Dict[str, Any]:
    """
    Generate a detailed drill-down report for a specific widget.
    Re-queries RAG system with focused query to get comprehensive information.

    Args:
        supabase: Supabase client
        tenant_id: Tenant ID
        widget_title: Title of the widget being drilled into
        widget_message: Brief message from the widget

    Returns:
        Detailed report with:
        - Full analysis
        - All related source documents
        - Recommendations
        - Data visualizations
    """
    logger.info(f"🔍 Generating drill-down report for: {widget_title}")

    # Build focused query
    focused_query = f"""You are conducting a deep-dive analysis on the following business issue:

ISSUE: {widget_title}
SUMMARY: {widget_message}

Your task is to provide a COMPREHENSIVE report that includes:

1. **Root Cause Analysis** - What is causing this issue? Connect all the dots from your data.

2. **Impact Assessment** - Quantify the business impact:
   - Dollar amounts at risk
   - Customers affected (with names)
   - Orders/deals blocked (with specific IDs)
   - Timeline urgency

3. **Full Context** - Find ALL related emails, documents, and conversations:
   - Who is involved?
   - What decisions are pending?
   - What has been tried?
   - What communication threads are relevant?

4. **Recommended Actions** - Specific, actionable next steps with:
   - Who should do what
   - When it should be done
   - Expected outcomes

5. **Data & Metrics** - Any relevant numbers, trends, or KPIs related to this issue

Return your analysis in JSON format with this structure:
{{
    "title": "{widget_title}",
    "executive_summary": "2-3 sentence overview of the entire situation",
    "root_cause": {{
        "primary_cause": "string",
        "contributing_factors": ["string"],
        "evidence": ["specific quotes or data points"]
    }},
    "impact": {{
        "financial_impact": "dollar amount or range",
        "customers_affected": ["customer names"],
        "orders_blocked": ["order IDs or numbers"],
        "urgency": "immediate|this-week|this-month",
        "risk_level": "critical|high|medium|low"
    }},
    "timeline": [
        {{
            "date": "YYYY-MM-DD or relative",
            "event": "what happened",
            "source": "who/where this came from"
        }}
    ],
    "key_stakeholders": [
        {{
            "name": "person or company name",
            "role": "their role in this situation",
            "status": "what they're waiting for or what they need"
        }}
    ],
    "recommendations": [
        {{
            "action": "specific action to take",
            "owner": "who should do it",
            "deadline": "when",
            "expected_outcome": "what this will achieve",
            "priority": "1-5"
        }}
    ],
    "metrics": [
        {{
            "metric_name": "string",
            "current_value": "number or string",
            "trend": "up|down|stable",
            "context": "why this matters"
        }}
    ]
}}

CRITICAL: Use ONLY real data from the documents. If you don't have specific information for a field, use "Not found in available data" rather than making something up."""

    # Get query engine
    engine = get_query_engine()
    if not engine:
        logger.error("Query engine not initialized!")
        return {
            "error": "Query engine not available",
            "title": widget_title
        }

    # Run deep RAG search with more sources
    try:
        import time
        start_time = time.time()

        response = await engine.query(focused_query)
        ai_answer = response.get("answer", "No detailed information found") if response else "No detailed information found"

        # Extract and enrich source documents
        source_documents = []
        source_nodes = response.get("source_nodes", []) if response else []

        for node in source_nodes[:15]:  # Get up to 15 sources for drill-down
            score = 0.0
            if hasattr(node, 'score') and node.score is not None:
                try:
                    score = float(node.score)
                except (TypeError, ValueError):
                    score = 0.0

            metadata = node.metadata if hasattr(node, 'metadata') else {}

            # Get actual document ID from metadata, fallback to node_id
            doc_id = metadata.get("document_id")
            if not doc_id:
                # Try to parse from node_id if it's numeric
                node_id_str = str(node.node_id) if hasattr(node, 'node_id') else None
                if node_id_str and node_id_str.isdigit():
                    doc_id = node_id_str
                else:
                    doc_id = None

            source_doc = {
                "document_id": doc_id,
                "text": node.text if hasattr(node, 'text') else "",
                "score": score,
                "from": metadata.get("subject") or metadata.get("title") or metadata.get("file_name") or "Unknown",
                "date": metadata.get("date") or metadata.get("created_at"),
                "type": metadata.get("doc_type") or metadata.get("type"),
                "sender": metadata.get("sender") or metadata.get("from"),
                "metadata": metadata
            }
            source_documents.append(source_doc)

        # Parse JSON response
        import json
        import re

        report_data = None
        try:
            # Try direct JSON parse
            try:
                report_data = json.loads(ai_answer)
            except json.JSONDecodeError:
                # Extract JSON from markdown
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', ai_answer, re.DOTALL)
                if json_match:
                    report_data = json.loads(json_match.group(1))
                else:
                    json_match = re.search(r'(\{.*?\})', ai_answer, re.DOTALL)
                    if json_match:
                        report_data = json.loads(json_match.group(1))

            logger.info(f"✅ Parsed drill-down report JSON")
        except Exception as e:
            logger.warning(f"⚠️ Failed to parse drill-down JSON: {e}")
            # Fallback to text response
            report_data = {
                "title": widget_title,
                "executive_summary": ai_answer[:500],
                "raw_analysis": ai_answer
            }

        # Add sources to report
        report_data["sources"] = source_documents
        report_data["total_sources"] = len(source_documents)
        report_data["generation_time_ms"] = int((time.time() - start_time) * 1000)

        logger.info(f"✅ Generated drill-down report with {len(source_documents)} sources in {report_data['generation_time_ms']}ms")

        return report_data

    except Exception as e:
        logger.error(f"Failed to generate drill-down report: {e}")
        return {
            "error": str(e),
            "title": widget_title,
            "message": "Failed to generate detailed report"
        }
