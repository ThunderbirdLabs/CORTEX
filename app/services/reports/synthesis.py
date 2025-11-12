"""
Daily Reports - Report Synthesis

Combines query answers into structured final report using Supabase prompts.
"""
import logging
import json
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from supabase import Client

from app.services.reports.models import (
    DailyReport,
    ReportSection,
    QueryAnswer,
    ReportMemory,
    SourceDocument
)

logger = logging.getLogger(__name__)


async def synthesize_report(
    supabase: Client,
    company_id: str,
    report_type: str,
    report_date: date,
    tenant_id: str,
    query_answers: List[QueryAnswer],
    previous_memory: Optional[ReportMemory],
    llm
) -> DailyReport:
    """
    Synthesize query answers into final structured report.

    Uses Supabase prompt for synthesis with previous memory injection.

    Args:
        supabase: Master Supabase client
        company_id: Company ID
        report_type: Report type
        report_date: Date of report
        tenant_id: Tenant ID
        query_answers: Answers from all RAG queries
        previous_memory: Memory from previous day (optional)
        llm: LLM instance

    Returns:
        Complete DailyReport

    Raises:
        Exception if prompts missing from Supabase
    """
    logger.info(f"🎨 Synthesizing {report_type} report...")

    # Load synthesis prompt from Supabase
    from app.services.tenant.context import get_prompt_template

    prompt_key = f'daily_report_{report_type}'
    prompt_template = get_prompt_template(prompt_key)

    if not prompt_template:
        raise Exception(
            f"Missing prompt in Supabase company_prompts: {prompt_key}"
        )

    # Load section configuration from Supabase
    sections_config = await _load_section_config(supabase, company_id, report_type)

    # Build previous context string
    previous_context = ""
    if previous_memory:
        previous_context = f"""CONTEXT FROM PREVIOUS DAY ({previous_memory.report_date}):
{previous_memory.summary}

KEY ITEMS TO FOLLOW UP ON:
{json.dumps(previous_memory.key_items, indent=2)}
"""

    # Format query answers
    query_answers_str = "\n\n".join([
        f"QUESTION: {qa.question}\nANSWER: {qa.answer}"
        for qa in query_answers
    ])

    # Build synthesis prompt
    synthesis_prompt = prompt_template.format(
        company_name="Unit Industries Group",  # TODO: Load from company context
        report_date=report_date.isoformat(),
        previous_context=previous_context if previous_context else "No previous context (first report)",
        query_answers=query_answers_str,
        sections_config=json.dumps([s for s in sections_config], indent=2)
    )

    # Call LLM for synthesis
    logger.info(f"   Calling LLM for synthesis...")
    response = await llm.acomplete(synthesis_prompt)
    synthesized_content = str(response).strip()

    logger.info(f"   ✅ Synthesis complete ({len(synthesized_content)} chars)")

    # Parse into sections (basic parsing for now)
    # TODO: Make this more robust
    sections = await _parse_into_sections(
        synthesized_content,
        sections_config,
        query_answers
    )

    # Build executive summary (first paragraph or extract)
    executive_summary = synthesized_content.split('\n\n')[0] if synthesized_content else "No summary available"

    # Collect all source documents
    all_sources = []
    for qa in query_answers:
        all_sources.extend(qa.sources)

    # Build final report
    report = DailyReport(
        report_type=report_type,
        report_date=report_date,
        tenant_id=tenant_id,
        executive_summary=executive_summary,
        sections=sections,
        generated_at=datetime.utcnow(),
        generation_duration_ms=0,  # Will be set by generator
        total_sources=len(all_sources),
        sub_questions_asked=[qa.question for qa in query_answers]
    )

    return report


async def _load_section_config(
    supabase: Client,
    company_id: str,
    report_type: str
) -> List[Dict]:
    """Load section configuration from Supabase."""
    result = supabase.table("company_report_sections")\
        .select("*")\
        .eq("company_id", company_id)\
        .eq("report_type", report_type)\
        .eq("is_active", True)\
        .order("section_order")\
        .execute()

    if not result.data:
        raise Exception(
            f"No section config found in Supabase for company_id={company_id}, "
            f"report_type={report_type}. Please configure in company_report_sections table."
        )

    return result.data


async def _parse_into_sections(
    synthesized_content: str,
    sections_config: List[Dict],
    query_answers: List[QueryAnswer]
) -> List[ReportSection]:
    """
    Parse synthesized markdown into structured sections.

    For Phase 1, just create sections from the full content.
    TODO: In Phase 2, parse based on section headers
    """
    sections = []

    # For now, put all content in first section
    # TODO: Smart parsing based on emoji headers
    if sections_config:
        section_config = sections_config[0]

        sections.append(ReportSection(
            title=section_config["section_title"],
            content=synthesized_content,
            sources=[],  # TODO: Map sources to sections
            evolution_note=None,
            order=section_config["section_order"]
        ))

    return sections
