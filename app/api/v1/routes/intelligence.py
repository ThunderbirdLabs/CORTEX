"""
Intelligence API Routes
Endpoints for retrieving pre-computed daily, weekly, and monthly intelligence summaries
"""
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app.core.dependencies import get_supabase
from app.core.security import get_current_user_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# ============================================================================
# DAILY INTELLIGENCE ENDPOINTS
# ============================================================================

@router.get("/daily")
async def get_daily_intelligence(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get pre-computed daily intelligence summary for a specific date.

    Returns activity metrics, entity mentions, AI-generated summary, and key insights.
    """
    # Validate date format
    try:
        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    logger.info(f"📊 Fetching daily intelligence for {user_id} on {date}")

    # Query daily_intelligence table
    result = supabase.table("daily_intelligence")\
        .select("*")\
        .eq("tenant_id", user_id)\
        .eq("date", date)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No intelligence data found for {date}. Daily summaries are generated overnight."
        )

    data = result.data[0]

    # Format response
    return {
        "date": data["date"],
        "tenant_id": data["tenant_id"],
        "metrics": {
            "total_documents": data["total_documents"],
            "document_counts": data["document_counts"],
            "invoice_total_amount": float(data["invoice_total_amount"]) if data["invoice_total_amount"] else None,
            "invoice_outstanding_balance": float(data["invoice_outstanding_balance"]) if data["invoice_outstanding_balance"] else None,
            "bill_total_amount": float(data["bill_total_amount"]) if data["bill_total_amount"] else None,
            "payment_total_amount": float(data["payment_total_amount"]) if data["payment_total_amount"] else None
        },
        "entities": {
            "most_active_people": data["most_active_people"],
            "most_active_companies": data["most_active_companies"],
            "new_entities": data["new_entities"]
        },
        "communication": {
            "email_senders": data["email_senders"],
            "email_recipients": data["email_recipients"]
        },
        "topics": data["key_topics"],
        "ai_summary": data["ai_summary"],
        "key_insights": data["key_insights"],
        "computed_at": data["computed_at"],
        "computation_duration_ms": data["computation_duration_ms"]
    }


@router.get("/daily/latest")
async def get_latest_daily_intelligence(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get the most recent daily intelligence summary.
    """
    logger.info(f"📊 Fetching latest daily intelligence for {user_id}")

    result = supabase.table("daily_intelligence")\
        .select("*")\
        .eq("tenant_id", user_id)\
        .order("date", desc=True)\
        .limit(1)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="No intelligence data found. Daily summaries are generated overnight."
        )

    data = result.data[0]

    return {
        "date": data["date"],
        "metrics": {
            "total_documents": data["total_documents"],
            "document_counts": data["document_counts"]
        },
        "ai_summary": data["ai_summary"],
        "computed_at": data["computed_at"]
    }


# ============================================================================
# WEEKLY INTELLIGENCE ENDPOINTS
# ============================================================================

@router.get("/weekly")
async def get_weekly_intelligence(
    week_start: str = Query(..., description="Monday date in YYYY-MM-DD format"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get pre-computed weekly intelligence summary for a specific week.

    Returns weekly trends, entity activity, WoW changes, and AI-generated insights.
    """
    # Validate date format
    try:
        date_obj = datetime.strptime(week_start, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Ensure it's a Monday
    if date_obj.weekday() != 0:
        raise HTTPException(status_code=400, detail="week_start must be a Monday")

    logger.info(f"📈 Fetching weekly intelligence for {user_id}, week of {week_start}")

    # Query weekly_intelligence table
    result = supabase.table("weekly_intelligence")\
        .select("*")\
        .eq("tenant_id", user_id)\
        .eq("week_start", week_start)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No intelligence data found for week starting {week_start}. Weekly summaries are generated Monday mornings."
        )

    data = result.data[0]

    return {
        "week_start": data["week_start"],
        "week_end": data["week_end"],
        "tenant_id": data["tenant_id"],
        "metrics": {
            "total_documents": data["total_documents"],
            "wow_change_percent": float(data["wow_change_percent"]) if data["wow_change_percent"] else 0,
            "total_unique_entities": data["total_unique_entities"],
            "new_entities_count": data["new_entities_count"]
        },
        "trends": {
            "document_trend": data["document_trend"],
            "trending_people": data["trending_people"],
            "trending_companies": data["trending_companies"],
            "trending_topics": data["trending_topics"]
        },
        "relationships": {
            "new_relationships": data["new_relationships"],
            "collaboration_patterns": data["collaboration_patterns"]
        },
        "business_momentum": {
            "deals_advancing": data["deals_advancing"],
            "deals_stalling": data["deals_stalling"]
        },
        "financial": {
            "weekly_revenue": float(data["weekly_revenue"]) if data["weekly_revenue"] else None,
            "weekly_expenses": float(data["weekly_expenses"]) if data["weekly_expenses"] else None,
            "revenue_trend": data["revenue_trend"]
        },
        "weekly_summary": data["weekly_summary"],
        "key_insights": data["key_insights"],
        "action_items": data["action_items"],
        "computed_at": data["computed_at"],
        "computation_duration_ms": data["computation_duration_ms"]
    }


@router.get("/weekly/latest")
async def get_latest_weekly_intelligence(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get the most recent weekly intelligence summary.
    """
    logger.info(f"📈 Fetching latest weekly intelligence for {user_id}")

    result = supabase.table("weekly_intelligence")\
        .select("*")\
        .eq("tenant_id", user_id)\
        .order("week_start", desc=True)\
        .limit(1)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="No intelligence data found. Weekly summaries are generated Monday mornings."
        )

    data = result.data[0]

    return {
        "week_start": data["week_start"],
        "week_end": data["week_end"],
        "total_documents": data["total_documents"],
        "wow_change_percent": float(data["wow_change_percent"]) if data["wow_change_percent"] else 0,
        "weekly_summary": data["weekly_summary"],
        "computed_at": data["computed_at"]
    }


# ============================================================================
# MONTHLY INTELLIGENCE ENDPOINTS
# ============================================================================

@router.get("/monthly")
async def get_monthly_intelligence(
    month: str = Query(..., description="First day of month in YYYY-MM-01 format"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get pre-computed monthly intelligence summary for a specific month.

    Returns monthly metrics, financial performance, strategic insights, and executive summary.
    """
    # Validate date format
    try:
        date_obj = datetime.strptime(month, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-01")

    # Ensure it's the 1st of the month
    if date_obj.day != 1:
        raise HTTPException(status_code=400, detail="month must be the 1st of a month (YYYY-MM-01)")

    logger.info(f"📊 Fetching monthly intelligence for {user_id}, month {date_obj.strftime('%B %Y')}")

    # Query monthly_intelligence table
    result = supabase.table("monthly_intelligence")\
        .select("*")\
        .eq("tenant_id", user_id)\
        .eq("month", month)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No intelligence data found for {date_obj.strftime('%B %Y')}. Monthly summaries are generated on the 1st of each month."
        )

    data = result.data[0]

    return {
        "month": data["month"],
        "month_name": datetime.strptime(data["month"], "%Y-%m-%d").strftime("%B %Y"),
        "tenant_id": data["tenant_id"],
        "activity_metrics": {
            "total_documents": data["total_documents"],
            "total_emails": data["total_emails"],
            "total_invoices": data["total_invoices"],
            "total_bills": data["total_bills"],
            "total_payments": data["total_payments"]
        },
        "financial_summary": {
            "total_revenue": float(data["total_revenue"]) if data["total_revenue"] else None,
            "total_expenses": float(data["total_expenses"]) if data["total_expenses"] else None,
            "net_income": float(data["net_income"]) if data["net_income"] else None,
            "revenue_by_customer": data["revenue_by_customer"],
            "expense_by_category": data["expense_by_category"]
        },
        "entity_evolution": {
            "total_unique_entities": data["total_unique_entities"],
            "new_entities_this_month": data["new_entities_this_month"],
            "most_active_entities": data["most_active_entities"],
            "expertise_evolution": data["expertise_evolution"]
        },
        "relationships": {
            "key_relationships": data["key_relationships"],
            "collaboration_networks": data["collaboration_networks"]
        },
        "strategic_alignment": {
            "goal_alignment_score": float(data["goal_alignment_score"]) if data["goal_alignment_score"] else None,
            "initiative_effectiveness": data["initiative_effectiveness"]
        },
        "mom_trends": {
            "document_change_percent": float(data["mom_document_change_percent"]) if data["mom_document_change_percent"] else 0,
            "revenue_change_percent": float(data["mom_revenue_change_percent"]) if data["mom_revenue_change_percent"] else 0,
            "entity_growth_percent": float(data["mom_entity_growth_percent"]) if data["mom_entity_growth_percent"] else 0
        },
        "health_scores": {
            "communication_health": float(data["communication_health_score"]) if data["communication_health_score"] else None,
            "financial_health": float(data["financial_health_score"]) if data["financial_health_score"] else None,
            "growth_momentum": float(data["growth_momentum_score"]) if data["growth_momentum_score"] else None
        },
        "executive_summary": data["executive_summary"],
        "strategic_insights": data["strategic_insights"],
        "recommendations": data["recommendations"],
        "computed_at": data["computed_at"],
        "computation_duration_ms": data["computation_duration_ms"]
    }


@router.get("/monthly/latest")
async def get_latest_monthly_intelligence(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get the most recent monthly intelligence summary.
    """
    logger.info(f"📊 Fetching latest monthly intelligence for {user_id}")

    result = supabase.table("monthly_intelligence")\
        .select("*")\
        .eq("tenant_id", user_id)\
        .order("month", desc=True)\
        .limit(1)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="No intelligence data found. Monthly summaries are generated on the 1st of each month."
        )

    data = result.data[0]
    month_obj = datetime.strptime(data["month"], "%Y-%m-%d")

    return {
        "month": data["month"],
        "month_name": month_obj.strftime("%B %Y"),
        "total_documents": data["total_documents"],
        "total_revenue": float(data["total_revenue"]) if data["total_revenue"] else None,
        "net_income": float(data["net_income"]) if data["net_income"] else None,
        "executive_summary": data["executive_summary"],
        "computed_at": data["computed_at"]
    }


# ============================================================================
# TREND ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/trends/daily")
async def get_daily_trends(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to analyze"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get daily activity trends for the past N days.

    Returns time series data suitable for charts and visualizations.
    """
    logger.info(f"📈 Fetching daily trends for {user_id} (past {days} days)")

    # Calculate date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    # Query daily intelligence records
    result = supabase.table("daily_intelligence")\
        .select("date, total_documents, invoice_total_amount, document_counts")\
        .eq("tenant_id", user_id)\
        .gte("date", start_date.isoformat())\
        .lte("date", end_date.isoformat())\
        .order("date")\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No daily intelligence data found for the past {days} days"
        )

    # Format as time series
    return {
        "period": f"past_{days}_days",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "data_points": len(result.data),
        "time_series": [
            {
                "date": record["date"],
                "total_documents": record["total_documents"],
                "invoice_total": float(record["invoice_total_amount"]) if record["invoice_total_amount"] else 0,
                "document_counts": record["document_counts"]
            }
            for record in result.data
        ]
    }


@router.get("/trends/weekly")
async def get_weekly_trends(
    weeks: int = Query(default=12, ge=1, le=52, description="Number of weeks to analyze"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get weekly trends for the past N weeks.
    """
    logger.info(f"📈 Fetching weekly trends for {user_id} (past {weeks} weeks)")

    # Calculate date range
    today = datetime.utcnow().date()
    days_since_monday = (today.weekday() - 0) % 7
    current_monday = today - timedelta(days=days_since_monday)
    start_date = current_monday - timedelta(weeks=weeks)

    # Query weekly intelligence records
    result = supabase.table("weekly_intelligence")\
        .select("week_start, week_end, total_documents, wow_change_percent, weekly_revenue")\
        .eq("tenant_id", user_id)\
        .gte("week_start", start_date.isoformat())\
        .order("week_start")\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No weekly intelligence data found for the past {weeks} weeks"
        )

    return {
        "period": f"past_{weeks}_weeks",
        "start_date": start_date.isoformat(),
        "data_points": len(result.data),
        "time_series": [
            {
                "week_start": record["week_start"],
                "week_end": record["week_end"],
                "total_documents": record["total_documents"],
                "wow_change_percent": float(record["wow_change_percent"]) if record["wow_change_percent"] else 0,
                "weekly_revenue": float(record["weekly_revenue"]) if record["weekly_revenue"] else 0
            }
            for record in result.data
        ]
    }


@router.get("/trends/monthly")
async def get_monthly_trends(
    months: int = Query(default=12, ge=1, le=24, description="Number of months to analyze"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get monthly trends for the past N months.
    """
    logger.info(f"📈 Fetching monthly trends for {user_id} (past {months} months)")

    # Calculate date range (simplified - actual month calculation would be more complex)
    today = datetime.utcnow().date()
    current_month = date(today.year, today.month, 1)

    # Query monthly intelligence records
    result = supabase.table("monthly_intelligence")\
        .select("month, total_documents, total_revenue, net_income, mom_document_change_percent")\
        .eq("tenant_id", user_id)\
        .order("month", desc=True)\
        .limit(months)\
        .execute()

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail=f"No monthly intelligence data found"
        )

    # Reverse to get chronological order
    data = list(reversed(result.data))

    return {
        "period": f"past_{months}_months",
        "data_points": len(data),
        "time_series": [
            {
                "month": record["month"],
                "month_name": datetime.strptime(record["month"], "%Y-%m-%d").strftime("%B %Y"),
                "total_documents": record["total_documents"],
                "total_revenue": float(record["total_revenue"]) if record["total_revenue"] else 0,
                "net_income": float(record["net_income"]) if record["net_income"] else 0,
                "mom_change_percent": float(record["mom_document_change_percent"]) if record["mom_document_change_percent"] else 0
            }
            for record in data
        ]
    }


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def intelligence_health_check(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Check availability of intelligence data for the current user.
    """
    # Check for latest records in each table
    daily_count = supabase.table("daily_intelligence").select("id", count="exact").eq("tenant_id", user_id).execute()
    weekly_count = supabase.table("weekly_intelligence").select("id", count="exact").eq("tenant_id", user_id).execute()
    monthly_count = supabase.table("monthly_intelligence").select("id", count="exact").eq("tenant_id", user_id).execute()

    return {
        "status": "healthy" if daily_count.count > 0 else "no_data",
        "data_availability": {
            "daily_records": daily_count.count,
            "weekly_records": weekly_count.count,
            "monthly_records": monthly_count.count
        },
        "message": "Intelligence system operational" if daily_count.count > 0 else "Awaiting first data generation"
    }
