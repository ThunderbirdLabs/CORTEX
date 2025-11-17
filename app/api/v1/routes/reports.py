"""
Daily Reports API Routes

Endpoints for generating and fetching evolving daily business intelligence reports.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import date
import logging

from supabase import Client
from app.core.dependencies import get_supabase, get_master_supabase
from app.core.dependencies import query_engine as global_query_engine
from app.core.security import get_current_user_id
from app.core.config_master import master_config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


class GenerateReportRequest(BaseModel):
    """Request to generate a daily report."""
    report_type: str  # 'client_relationships' | 'operations'
    target_date: Optional[str] = None  # YYYY-MM-DD, defaults to yesterday
    force_regenerate: bool = False


@router.post("/daily/generate")
async def generate_daily_report_endpoint(
    request: GenerateReportRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
    master_supabase: Client = Depends(get_master_supabase)
):
    """Generate a daily report."""
    try:
        # Parse target date
        if request.target_date:
            target_date = date.fromisoformat(request.target_date)
        else:
            from app.services.reports.memory import get_previous_business_day
            target_date = get_previous_business_day(date.today())

        # Check existing
        if not request.force_regenerate:
            existing = master_supabase.table("daily_reports")\
                .select("id")\
                .eq("tenant_id", user_id)\
                .eq("report_type", request.report_type)\
                .eq("report_date", target_date.isoformat())\
                .execute()

            if existing.data:
                return {
                    "success": False,
                    "error": f"Report exists for {target_date}. Use force_regenerate=true"
                }

        # Generate
        if not global_query_engine:
            raise HTTPException(503, "Query engine not initialized")

        from app.services.reports.generator import generate_daily_report

        report = await generate_daily_report(
            supabase=supabase,
            master_supabase=master_supabase,
            tenant_id=user_id,
            company_id=master_config.company_id,
            report_type=request.report_type,
            target_date=target_date,
            query_engine=global_query_engine
        )

        return {
            "success": True,
            "report": report.model_dump(mode='json')
        }

    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        return {"success": False, "error": str(e)}


@router.get("/daily/{report_date}")
async def get_daily_report(
    report_date: str,
    report_type: str,
    user_id: str = Depends(get_current_user_id),
    master_supabase: Client = Depends(get_master_supabase)
):
    """Fetch a daily report."""
    try:
        result = master_supabase.table("daily_reports")\
            .select("*")\
            .eq("tenant_id", user_id)\
            .eq("report_type", report_type)\
            .eq("report_date", report_date)\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(404, "Report not found")

        return {"success": True, "report": result.data}

    except Exception as e:
        logger.error(f"Failed to fetch report: {e}")
        raise HTTPException(500, str(e))


@router.get("/daily/latest")
async def get_latest_reports(
    limit: int = 7,
    user_id: str = Depends(get_current_user_id),
    master_supabase: Client = Depends(get_master_supabase)
):
    """Get recent daily reports."""
    try:
        result = master_supabase.table("daily_reports")\
            .select("*")\
            .eq("tenant_id", user_id)\
            .order("report_date", desc=True)\
            .limit(limit * 2)\
            .execute()

        return {
            "success": True,
            "reports": result.data,
            "total": len(result.data)
        }

    except Exception as e:
        logger.error(f"Failed to fetch latest: {e}")
        raise HTTPException(500, str(e))
