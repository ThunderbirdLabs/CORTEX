"""
Real-Time Alerts API

Endpoints for managing urgent document alerts detected by the
real-time intelligence system.
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from supabase import Client
from app.core.dependencies import get_supabase
from app.core.security import get_current_user_id
from app.services.intelligence.realtime_detector import get_alert_summary_stats
from app.services.intelligence.rag_insights_generator import generate_drill_down_report

router = APIRouter()
logger = logging.getLogger(__name__)


class DismissAlertRequest(BaseModel):
    """Request to dismiss an alert."""
    note: Optional[str] = None


@router.get("/active")
async def get_active_alerts(
    urgency_filter: Optional[str] = Query(None, description="Filter by urgency: critical, high, medium, low"),
    limit: int = Query(20, ge=1, le=100, description="Max alerts to return"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get active (undismissed) alerts for the current user.

    Returns alerts ordered by urgency (critical first) and then by detection time (newest first).
    """
    try:
        logger.info(f"Fetching active alerts for user {user_id}")

        # Use the SQL function we created
        result = supabase.rpc(
            'get_active_alerts',
            {
                'p_tenant_id': user_id,
                'p_urgency_filter': urgency_filter,
                'p_limit': limit
            }
        ).execute()

        alerts = result.data or []

        return {
            "total": len(alerts),
            "urgency_filter": urgency_filter,
            "alerts": alerts
        }

    except Exception as e:
        logger.error(f"Failed to fetch active alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_alert_stats(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get alert statistics for the current user.

    Returns counts by urgency level and alert type.
    """
    try:
        stats = get_alert_summary_stats(user_id, supabase)

        return {
            "stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: int,
    request: DismissAlertRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Dismiss an alert (mark as resolved).

    This removes the alert from the active alerts list but keeps it in the database
    for historical tracking.
    """
    try:
        logger.info(f"Dismissing alert {alert_id} for user {user_id}")

        # Use the SQL function
        result = supabase.rpc(
            'dismiss_alert',
            {
                'p_alert_id': alert_id,
                'p_tenant_id': user_id,
                'p_dismissed_by': user_id
            }
        ).execute()

        success = result.data if result.data is not None else False

        if not success:
            raise HTTPException(
                status_code=404,
                detail="Alert not found or already dismissed"
            )

        return {
            "success": True,
            "alert_id": alert_id,
            "dismissed_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to dismiss alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/investigate")
async def investigate_alert(
    alert_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Generate a detailed drill-down report for a specific alert.

    This runs the same RAG analysis as the widget drill-down, but focused on
    the specific issue identified in this alert.
    """
    try:
        logger.info(f"🔍 Investigating alert {alert_id} for user {user_id}")

        # Get the alert details
        alert_result = supabase.table("document_alerts")\
            .select("*, documents!inner(id, title, content, metadata)")\
            .eq("id", alert_id)\
            .eq("tenant_id", user_id)\
            .single()\
            .execute()

        if not alert_result.data:
            raise HTTPException(status_code=404, detail="Alert not found")

        alert = alert_result.data
        document = alert.get("documents", {})

        # Increment investigation counter
        supabase.rpc(
            'increment_investigation_count',
            {
                'p_alert_id': alert_id,
                'p_tenant_id': user_id
            }
        ).execute()

        # Generate drill-down report using the same RAG system
        # Focus on the alert type and key entities
        widget_title = f"{alert['alert_type'].replace('_', ' ').title()}: {alert['summary'][:50]}"
        widget_message = alert['summary']

        report = await generate_drill_down_report(
            supabase=supabase,
            tenant_id=user_id,
            widget_title=widget_title,
            widget_message=widget_message
        )

        # Enhance report with alert-specific context
        report["alert_context"] = {
            "alert_id": alert_id,
            "urgency_level": alert["urgency_level"],
            "alert_type": alert["alert_type"],
            "key_entities": alert.get("key_entities", []),
            "detected_at": alert["detected_at"],
            "source_document": {
                "id": document.get("id"),
                "title": document.get("title"),
                "content_preview": document.get("content", "")[:500]
            }
        }

        return {
            "success": True,
            "alert_id": alert_id,
            "report": report
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to investigate alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{alert_id}")
async def get_alert_details(
    alert_id: int,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get full details for a specific alert.
    """
    try:
        result = supabase.table("document_alerts")\
            .select("*, documents!inner(id, title, content, source, created_at, metadata)")\
            .eq("id", alert_id)\
            .eq("tenant_id", user_id)\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {
            "alert": result.data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alert details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_alert_history(
    days: int = Query(30, ge=1, le=365, description="Number of days of history"),
    include_dismissed: bool = Query(True, description="Include dismissed alerts"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get alert history for the current user.

    Useful for analytics and tracking alert resolution patterns.
    """
    try:
        from datetime import timedelta

        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        query = supabase.table("document_alerts")\
            .select("id, alert_type, urgency_level, summary, detected_at, dismissed_at, investigation_count")\
            .eq("tenant_id", user_id)\
            .gte("detected_at", cutoff_date)

        if not include_dismissed:
            query = query.is_("dismissed_at", "null")

        result = query.order("detected_at", desc=True).execute()

        alerts = result.data or []

        # Calculate some stats
        total_alerts = len(alerts)
        dismissed_count = sum(1 for a in alerts if a.get("dismissed_at"))
        active_count = total_alerts - dismissed_count

        by_urgency = {}
        by_type = {}

        for alert in alerts:
            urgency = alert.get("urgency_level", "unknown")
            alert_type = alert.get("alert_type", "unknown")

            by_urgency[urgency] = by_urgency.get(urgency, 0) + 1
            by_type[alert_type] = by_type.get(alert_type, 0) + 1

        return {
            "total_alerts": total_alerts,
            "active_count": active_count,
            "dismissed_count": dismissed_count,
            "by_urgency": by_urgency,
            "by_type": by_type,
            "alerts": alerts
        }

    except Exception as e:
        logger.error(f"Failed to get alert history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backfill")
async def backfill_urgency_detection(
    limit: int = Query(100, ge=1, le=1000, description="Max documents to analyze"),
    only_recent: bool = Query(True, description="Only analyze documents from last 7 days"),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Trigger urgency detection for existing documents (backfill).

    Useful for:
    - Initial setup (analyze existing documents)
    - Reprocessing documents with improved detection logic
    - Testing

    This queues a background job and returns immediately.
    """
    try:
        from app.services.jobs.alert_tasks import batch_detect_urgency_task

        # Queue the batch job
        batch_detect_urgency_task.send(
            tenant_id=user_id,
            limit=limit,
            only_recent=only_recent
        )

        logger.info(f"Queued batch urgency detection for tenant {user_id} (limit: {limit})")

        return {
            "success": True,
            "message": f"Queued urgency detection for up to {limit} documents",
            "limit": limit,
            "only_recent": only_recent
        }

    except Exception as e:
        logger.error(f"Failed to queue batch urgency detection: {e}")
        raise HTTPException(status_code=500, detail=str(e))
