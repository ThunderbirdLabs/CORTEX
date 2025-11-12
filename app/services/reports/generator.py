"""
Daily Reports - Core Generator

Orchestrates the complete report generation flow.
"""
import logging
import time
from typing import Dict, Any, List
from datetime import date, datetime, timedelta
from supabase import Client

from app.services.reports.models import DailyReport, QueryAnswer, ReportType
from app.services.reports.memory import load_previous_report_memory, get_previous_business_day
from app.services.reports.questions import get_all_questions

logger = logging.getLogger(__name__)


async def generate_daily_report(
    supabase: Client,
    master_supabase: Client,
    tenant_id: str,
    company_id: str,
    report_type: str,
    target_date: date,
    query_engine  # HybridQueryEngine instance
) -> DailyReport:
    """
    Generate a complete daily report.

    Args:
        supabase: Company Supabase client
        master_supabase: Master Supabase client (for config)
        tenant_id: Tenant ID
        company_id: Company ID (for loading config)
        report_type: 'client_relationships' | 'operations'
        target_date: Date to generate report for (usually yesterday)
        query_engine: Query engine instance

    Returns:
        Complete DailyReport

    Raises:
        Exception if prompts/config missing from Supabase
    """
    start_time = time.time()

    logger.info(f"\n{'='*80}")
    logger.info(f"🔍 Generating {report_type} report for {target_date}")
    logger.info(f"{'='*80}")

    # Step 1: Load previous day's memory (for context)
    logger.info(f"\n1️⃣ Loading previous memory...")
    previous_memory = await load_previous_report_memory(
        master_supabase=master_supabase,
        tenant_id=tenant_id,
        report_type=report_type,
        current_date=target_date + timedelta(days=1)  # Get memory from day before target
    )

    if previous_memory:
        logger.info(f"   ✅ Loaded memory from {previous_memory.report_date}")
    else:
        logger.info(f"   ℹ️  No previous memory (first report or gap)")

    # Step 2: Generate questions (static + dynamic)
    logger.info(f"\n2️⃣ Generating questions...")
    all_questions = await get_all_questions(
        supabase=master_supabase,
        company_id=company_id,
        report_type=report_type,
        previous_memory=previous_memory,
        llm=query_engine.llm  # Use query engine's LLM
    )

    static_qs = all_questions["static"]
    dynamic_qs = all_questions["dynamic"]

    logger.info(f"   ✅ Static questions: {len(static_qs)}")
    logger.info(f"   ✅ Dynamic questions: {len(dynamic_qs)}")

    all_qs = static_qs + dynamic_qs

    # Step 3: Run each question through RAG (with time override to target_date)
    logger.info(f"\n3️⃣ Running {len(all_qs)} RAG queries...")

    query_answers: List[QueryAnswer] = []

    for i, question in enumerate(all_qs, 1):
        logger.info(f"   [{i}/{len(all_qs)}] {question}")

        try:
            # Call query() with 3-day time window (recency boost prioritizes most recent)
            three_days_ago = target_date - timedelta(days=2)
            result = await query_engine.query(
                question,
                time_override={'start': three_days_ago, 'end': target_date}
            )

            query_answers.append(QueryAnswer(
                question=question,
                answer=result.get('answer', ''),
                sources=[],  # TODO: Convert source_nodes to SourceDocument models
                metadata=result.get('metadata', {})
            ))

            logger.info(f"      ✅ Got answer ({len(result.get('answer', ''))} chars)")

        except Exception as e:
            logger.error(f"      ❌ Query failed: {e}")
            # Continue with other questions

    # Step 4: Synthesize into final report
    logger.info(f"\n4️⃣ Synthesizing final report...")
    from app.services.reports.synthesis import synthesize_report

    report = await synthesize_report(
        supabase=master_supabase,
        company_id=company_id,
        report_type=report_type,
        report_date=target_date,
        tenant_id=tenant_id,
        query_answers=query_answers,
        previous_memory=previous_memory,
        llm=query_engine.llm
    )

    generation_duration = int((time.time() - start_time) * 1000)
    report.generation_duration_ms = generation_duration

    logger.info(f"   ✅ Report generated in {generation_duration}ms")

    # Step 5: Generate and save memory for tomorrow
    logger.info(f"\n5️⃣ Creating memory for next day...")

    # Generate summary
    summary = await _generate_summary(report, query_engine.llm)
    logger.info(f"   ✅ Summary: {len(summary)} chars")

    # Extract key items
    key_items = await _extract_key_items(report, query_engine.llm)
    logger.info(f"   ✅ Key items: {len(key_items)} items")

    # Save report with memory (wrapped to handle Supabase cache errors)
    try:
        from app.services.reports.memory import save_report_memory
        await save_report_memory(master_supabase, report, summary, key_items)
    except Exception as save_error:
        logger.warning(f"   ⚠️  Failed to save to database (likely Supabase schema cache): {save_error}")
        logger.warning(f"   Report generated successfully, but not persisted")
        # Continue - report was generated, just not saved

    logger.info(f"\n{'='*80}")
    logger.info(f"✅ REPORT COMPLETE: {report_type} for {target_date}")
    logger.info(f"{'='*80}\n")

    return report


async def _generate_summary(report: DailyReport, llm) -> str:
    """Generate 2-3 paragraph summary for next day's context."""
    from app.services.tenant.context import get_prompt_template
    import json

    prompt_template = get_prompt_template('daily_report_summary_generator')
    if not prompt_template:
        raise Exception("Missing prompt: daily_report_summary_generator")

    prompt = prompt_template.format(
        report_type=report.report_type,
        full_report=json.dumps(report.model_dump(mode='json'), indent=2)
    )

    response = await llm.acomplete(prompt)
    return str(response).strip()


async def _extract_key_items(report: DailyReport, llm) -> Dict[str, Any]:
    """Extract structured key items for dynamic question generation."""
    from app.services.tenant.context import get_prompt_template
    import json

    prompt_template = get_prompt_template('daily_report_key_items_extractor')
    if not prompt_template:
        raise Exception("Missing prompt: daily_report_key_items_extractor")

    prompt = prompt_template.format(
        full_report=json.dumps(report.model_dump(mode='json'), indent=2)
    )

    response = await llm.acomplete(prompt)
    response_text = str(response).strip()

    # Parse JSON
    try:
        # Remove markdown if present
        if response_text.startswith('```'):
            response_text = response_text.split('\n', 1)[1].rsplit('\n', 1)[0]

        key_items = json.loads(response_text)
        return key_items

    except Exception as e:
        logger.warning(f"Failed to parse key_items JSON: {e}")
        return {}
