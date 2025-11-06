"""
RAG-Powered Intelligence Insights API

Endpoints to fetch AI-generated business insights with source documents.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
import logging

from supabase import Client
from app.core.dependencies import get_supabase, get_current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/daily")
async def get_daily_insights(
    insight_date: Optional[str] = Query(default=None, description="Date in YYYY-MM-DD format (defaults to today)"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get all daily insights for a specific date.
    Returns AI-generated summaries with source documents.
    """
    try:
        # Parse date or default to today
        target_date = date.fromisoformat(insight_date) if insight_date else date.today()

        # Fetch insights with their display config
        result = supabase.rpc(
            'get_insights_for_date',
            {
                'p_tenant_id': user_id,
                'p_date': target_date.isoformat(),
                'p_time_period': 'daily'
            }
        ).execute()

        insights = result.data or []

        return {
            "date": target_date.isoformat(),
            "time_period": "daily",
            "total_insights": len(insights),
            "insights": insights
        }

    except Exception as e:
        logger.error(f"Failed to fetch daily insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weekly")
async def get_weekly_insights(
    week_start: Optional[str] = Query(default=None, description="Week start date (defaults to current week)"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get all weekly insights for a specific week.
    """
    try:
        # Calculate week start (Monday)
        if week_start:
            target_date = date.fromisoformat(week_start)
        else:
            today = date.today()
            target_date = today - timedelta(days=today.weekday())  # Get Monday

        result = supabase.rpc(
            'get_insights_for_date',
            {
                'p_tenant_id': user_id,
                'p_date': target_date.isoformat(),
                'p_time_period': 'weekly'
            }
        ).execute()

        insights = result.data or []

        return {
            "week_start": target_date.isoformat(),
            "time_period": "weekly",
            "total_insights": len(insights),
            "insights": insights
        }

    except Exception as e:
        logger.error(f"Failed to fetch weekly insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monthly")
async def get_monthly_insights(
    month: Optional[str] = Query(default=None, description="Month in YYYY-MM format (defaults to current month)"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get all monthly insights for a specific month.
    """
    try:
        # Parse month or default to current
        if month:
            # Parse YYYY-MM
            year, month_num = month.split('-')
            target_date = date(int(year), int(month_num), 1)
        else:
            today = date.today()
            target_date = date(today.year, today.month, 1)

        result = supabase.rpc(
            'get_insights_for_date',
            {
                'p_tenant_id': user_id,
                'p_date': target_date.isoformat(),
                'p_time_period': 'monthly'
            }
        ).execute()

        insights = result.data or []

        return {
            "month": target_date.strftime('%Y-%m'),
            "time_period": "monthly",
            "total_insights": len(insights),
            "insights": insights
        }

    except Exception as e:
        logger.error(f"Failed to fetch monthly insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/latest")
async def get_latest_insights(
    time_period: str = Query(default="daily", description="Time period: daily, weekly, or monthly"),
    limit: int = Query(default=5, ge=1, le=20),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get the most recent insights for quick dashboard display.
    Useful for showing top 3-5 insights on main dashboard.
    """
    try:
        # Determine date range based on time period
        if time_period == "daily":
            target_date = date.today()
        elif time_period == "weekly":
            today = date.today()
            target_date = today - timedelta(days=today.weekday())
        elif time_period == "monthly":
            today = date.today()
            target_date = date(today.year, today.month, 1)
        else:
            raise HTTPException(status_code=400, detail="Invalid time_period. Must be daily, weekly, or monthly")

        # Fetch insights
        result = supabase.table("intelligence_insights")\
            .select("*, intelligence_search_queries!inner(display_title, display_icon, display_order)")\
            .eq("tenant_id", user_id)\
            .eq("insight_date", target_date.isoformat())\
            .eq("time_period", time_period)\
            .order("intelligence_search_queries(display_order)")\
            .limit(limit)\
            .execute()

        insights = result.data or []

        # Transform to friendly format
        formatted_insights = []
        for insight in insights:
            query_info = insight.get("intelligence_search_queries", {})

            formatted_insights.append({
                "category": insight.get("query_category"),
                "title": query_info.get("display_title", "Insight"),
                "icon": query_info.get("display_icon"),
                "answer": insight.get("ai_answer"),
                "confidence": float(insight.get("confidence_score", 0)) if insight.get("confidence_score") else None,
                "sources": insight.get("source_documents", []),
                "total_sources": insight.get("total_sources", 0),
                "generated_at": insight.get("generated_at")
            })

        return {
            "time_period": time_period,
            "date": target_date.isoformat(),
            "total_insights": len(formatted_insights),
            "insights": formatted_insights
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch latest insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_insights_by_category(
    category: str = Query(..., description="Category: deals, customers, issues, opportunities, summary"),
    time_period: str = Query(default="daily"),
    days: int = Query(default=7, ge=1, le=90),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get insights filtered by category over a time range.
    Useful for dedicated category pages (e.g., "All Deal Insights").
    """
    try:
        start_date = date.today() - timedelta(days=days)

        result = supabase.table("intelligence_insights")\
            .select("*, intelligence_search_queries!inner(display_title, display_icon)")\
            .eq("tenant_id", user_id)\
            .eq("query_category", category)\
            .eq("time_period", time_period)\
            .gte("insight_date", start_date.isoformat())\
            .order("insight_date", desc=True)\
            .execute()

        insights = result.data or []

        # Format for frontend
        formatted = []
        for insight in insights:
            query_info = insight.get("intelligence_search_queries", {})

            formatted.append({
                "date": insight.get("insight_date"),
                "title": query_info.get("display_title"),
                "icon": query_info.get("display_icon"),
                "answer": insight.get("ai_answer"),
                "confidence": float(insight.get("confidence_score", 0)) if insight.get("confidence_score") else None,
                "sources": insight.get("source_documents", []),
                "total_sources": insight.get("total_sources", 0),
                "generated_at": insight.get("generated_at")
            })

        return {
            "category": category,
            "time_period": time_period,
            "days": days,
            "total_insights": len(formatted),
            "insights": formatted
        }

    except Exception as e:
        logger.error(f"Failed to fetch category insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/regenerate")
async def regenerate_insight(
    insight_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Mark an insight as stale and trigger regeneration.
    Useful for "Refresh this insight" buttons.
    """
    try:
        # Mark as stale
        result = supabase.table("intelligence_insights")\
            .update({"is_stale": True})\
            .eq("id", insight_id)\
            .eq("tenant_id", user_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Insight not found")

        # TODO: Trigger background job to regenerate
        # For now, just mark as stale and the nightly job will pick it up

        return {
            "success": True,
            "message": "Insight marked for regeneration. Will be updated on next run.",
            "insight_id": insight_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to regenerate insight: {e}")
        raise HTTPException(status_code=500, detail=str(e))
