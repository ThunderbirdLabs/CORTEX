"""
Daily Reports System

Generates evolving daily business intelligence reports with memory.

Features:
- Morning reports on client relationships and operations
- Memory system: Each report builds on previous days
- Dynamic question generation based on previous findings
- Structured, consistent format with evolution notes

Architecture:
- models.py: Data validation (Pydantic)
- memory.py: Load/save summaries and key items
- questions.py: Generate static + dynamic questions
- generator.py: Core orchestration
- synthesis.py: Combine query results into final report
"""

from app.services.reports.models import (
    DailyReport,
    ReportSection,
    ReportMemory,
    ReportType
)

__all__ = [
    "DailyReport",
    "ReportSection",
    "ReportMemory",
    "ReportType"
]
