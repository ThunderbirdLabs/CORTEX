"""
Saved Reports API

Endpoints for saving, viewing, and managing drill-down reports.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from supabase import Client
from app.core.dependencies import get_supabase
from app.core.security import get_current_user_id

router = APIRouter()
logger = logging.getLogger(__name__)


class SaveReportRequest(BaseModel):
    """Request to save a report."""
    title: str
    report_type: str  # 'widget_drilldown', 'alert_investigation', 'manual_query'
    report_data: Dict[str, Any]  # Full report JSON
    description: Optional[str] = None
    source_widget_title: Optional[str] = None
    source_widget_message: Optional[str] = None
    source_alert_id: Optional[int] = None
    source_query: Optional[str] = None
    tags: Optional[List[str]] = None


class UpdateReportRequest(BaseModel):
    """Request to update report metadata."""
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


@router.post("/save")
async def save_report(
    request: SaveReportRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Save a drill-down report for later access.

    Reports can be from:
    - Widget drill-downs
    - Alert investigations
    - Manual search queries
    """
    try:
        logger.info(f"💾 Saving report: {request.title} for user {user_id}")

        # Use the SQL function
        result = supabase.rpc(
            'save_report',
            {
                'p_tenant_id': user_id,
                'p_title': request.title,
                'p_report_type': request.report_type,
                'p_report_data': request.report_data,
                'p_description': request.description,
                'p_source_widget_title': request.source_widget_title,
                'p_source_widget_message': request.source_widget_message,
                'p_source_alert_id': request.source_alert_id,
                'p_source_query': request.source_query,
                'p_tags': request.tags or []
            }
        ).execute()

        report_id = result.data if result.data else None

        if not report_id:
            raise HTTPException(status_code=500, detail="Failed to save report")

        logger.info(f"✅ Report saved with ID: {report_id}")

        return {
            "success": True,
            "report_id": report_id,
            "message": "Report saved successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_reports(
    report_type: Optional[str] = Query(None, description="Filter by type"),
    starred_only: bool = Query(False, description="Only show starred reports"),
    limit: int = Query(50, ge=1, le=200, description="Max reports to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get list of saved reports for the current user.

    Returns reports ordered by creation date (newest first).
    """
    try:
        result = supabase.rpc(
            'get_user_reports',
            {
                'p_tenant_id': user_id,
                'p_report_type': report_type,
                'p_starred_only': starred_only,
                'p_limit': limit,
                'p_offset': offset
            }
        ).execute()

        reports = result.data or []

        return {
            "total": len(reports),
            "limit": limit,
            "offset": offset,
            "reports": reports
        }

    except Exception as e:
        logger.error(f"Failed to list reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{report_id}")
async def get_report(
    report_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get full details for a specific report.

    Automatically tracks view count and last viewed time.
    """
    try:
        # Update view count
        supabase.rpc(
            'update_report_view',
            {
                'p_report_id': report_id,
                'p_tenant_id': user_id
            }
        ).execute()

        # Fetch full report
        result = supabase.table("saved_reports")\
            .select("*")\
            .eq("id", report_id)\
            .eq("tenant_id", user_id)\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Report not found")

        return {
            "report": result.data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{report_id}/star")
async def toggle_star(
    report_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Toggle star/favorite status for a report.
    """
    try:
        result = supabase.rpc(
            'toggle_report_star',
            {
                'p_report_id': report_id,
                'p_tenant_id': user_id
            }
        ).execute()

        is_starred = result.data if result.data is not None else False

        return {
            "success": True,
            "report_id": report_id,
            "is_starred": is_starred
        }

    except Exception as e:
        logger.error(f"Failed to toggle star: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{report_id}")
async def update_report(
    report_id: int,
    request: UpdateReportRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Update report metadata (title, description, tags).
    """
    try:
        update_data = {}
        if request.title is not None:
            update_data["title"] = request.title
        if request.description is not None:
            update_data["description"] = request.description
        if request.tags is not None:
            # Use the SQL function for tags
            supabase.rpc(
                'update_report_tags',
                {
                    'p_report_id': report_id,
                    'p_tenant_id': user_id,
                    'p_tags': request.tags
                }
            ).execute()

        if update_data:
            result = supabase.table("saved_reports")\
                .update(update_data)\
                .eq("id", report_id)\
                .eq("tenant_id", user_id)\
                .execute()

            if not result.data:
                raise HTTPException(status_code=404, detail="Report not found")

        return {
            "success": True,
            "report_id": report_id,
            "message": "Report updated successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{report_id}")
async def delete_report(
    report_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Delete a saved report.
    """
    try:
        result = supabase.rpc(
            'delete_report',
            {
                'p_report_id': report_id,
                'p_tenant_id': user_id
            }
        ).execute()

        success = result.data if result.data is not None else False

        if not success:
            raise HTTPException(status_code=404, detail="Report not found")

        return {
            "success": True,
            "report_id": report_id,
            "message": "Report deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_reports(
    q: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Search reports by title, description, tags, or content.
    """
    try:
        result = supabase.rpc(
            'search_reports',
            {
                'p_tenant_id': user_id,
                'p_search_term': q,
                'p_limit': limit
            }
        ).execute()

        reports = result.data or []

        return {
            "query": q,
            "total": len(reports),
            "reports": reports
        }

    except Exception as e:
        logger.error(f"Failed to search reports: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_report_stats(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get statistics about saved reports.
    """
    try:
        # Get counts by type
        result = supabase.table("saved_reports")\
            .select("report_type", count="exact")\
            .eq("tenant_id", user_id)\
            .execute()

        total_count = len(result.data) if result.data else 0

        # Count by type
        by_type = {}
        if result.data:
            for report in result.data:
                report_type = report.get("report_type", "unknown")
                by_type[report_type] = by_type.get(report_type, 0) + 1

        # Count starred
        starred_result = supabase.table("saved_reports")\
            .select("id", count="exact")\
            .eq("tenant_id", user_id)\
            .eq("is_starred", True)\
            .execute()

        starred_count = len(starred_result.data) if starred_result.data else 0

        return {
            "total_reports": total_count,
            "starred_count": starred_count,
            "by_type": by_type,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get report stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
