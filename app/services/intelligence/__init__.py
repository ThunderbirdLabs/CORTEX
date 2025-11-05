"""
Organizational Intelligence Service
Generates daily, weekly, and monthly aggregated insights
"""
from app.services.intelligence.aggregator import (
    calculate_daily_metrics,
    calculate_weekly_trends,
    calculate_monthly_insights,
    generate_ai_summary
)

__all__ = [
    "calculate_daily_metrics",
    "calculate_weekly_trends",
    "calculate_monthly_insights",
    "generate_ai_summary"
]
