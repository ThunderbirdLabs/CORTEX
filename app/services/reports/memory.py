"""
Daily Reports - Memory Management

Handles loading and saving report summaries and key items for context injection.
"""
import logging
from typing import Optional, Dict, Any
from datetime import date, timedelta
from supabase import Client

from app.services.reports.models import ReportMemory, DailyReport

logger = logging.getLogger(__name__)


async def load_previous_report_memory(
    supabase: Client,
    tenant_id: str,
    report_type: str,
    current_date: date
) -> Optional[ReportMemory]:
    """
    Load memory from previous business day's report.

    Handles weekends: If today is Monday, loads Friday's report.

    Args:
        supabase: Supabase client
        tenant_id: Tenant ID
        report_type: Type of report
        current_date: Today's date

    Returns:
        ReportMemory if previous report exists, None otherwise
    """
    # Calculate previous business day
    previous_date = current_date - timedelta(days=1)

    # Handle weekends
    if previous_date.weekday() == 6:  # Sunday
        previous_date = previous_date - timedelta(days=2)  # Friday
    elif previous_date.weekday() == 5:  # Saturday
        previous_date = previous_date - timedelta(days=1)  # Friday

    logger.info(f"📚 Loading memory from {previous_date} ({report_type})")

    try:
        result = supabase.table("daily_reports")\
            .select("summary, key_items, report_date")\
            .eq("tenant_id", tenant_id)\
            .eq("report_type", report_type)\
            .eq("report_date", previous_date.isoformat())\
            .single()\
            .execute()

        if result.data:
            logger.info(f"   ✅ Found memory from {previous_date}")

            return ReportMemory(
                summary=result.data["summary"],
                key_items=result.data["key_items"],
                report_date=previous_date,
                report_type=report_type
            )
        else:
            logger.info(f"   ℹ️  No memory found (first time running or gap in reports)")
            return None

    except Exception as e:
        logger.warning(f"   ⚠️  Failed to load memory: {e}")
        return None


async def save_report_memory(
    supabase: Client,
    report: DailyReport,
    summary: str,
    key_items: Dict
) -> None:
    """
    Save report with memory (summary + key items) for next day.

    Args:
        supabase: Supabase client
        report: The full report
        summary: 2-3 paragraph summary for next day
        key_items: Structured extraction for dynamic questions
    """
    logger.info(f"💾 Saving report memory for {report.report_date}")

    try:
        # Build database record
        db_record = {
            **report.to_db_dict(),
            "summary": summary,
            "key_items": key_items
        }

        # Upsert (handles if report already exists)
        result = supabase.table("daily_reports")\
            .upsert(
                db_record,
                on_conflict="tenant_id,report_date,report_type"
            )\
            .execute()

        logger.info(f"   ✅ Report saved (id: {result.data[0]['id'] if result.data else 'N/A'})")

    except Exception as e:
        logger.error(f"   ❌ Failed to save report: {e}")
        raise


def get_previous_business_day(current_date: date) -> date:
    """
    Get previous business day (handles weekends).

    Monday → Friday
    Tuesday-Friday → Previous day

    Args:
        current_date: Current date

    Returns:
        Previous business day
    """
    previous = current_date - timedelta(days=1)

    # If previous is Sunday, go back to Friday
    if previous.weekday() == 6:
        previous = previous - timedelta(days=2)

    # If previous is Saturday, go back to Friday
    elif previous.weekday() == 5:
        previous = previous - timedelta(days=1)

    return previous
