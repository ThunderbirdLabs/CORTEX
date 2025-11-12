"""
Daily Reports - Question Generation

Loads static questions from Supabase and generates dynamic questions from previous memory.
"""
import logging
from typing import List, Dict, Any, Optional
from supabase import Client

from app.services.reports.models import ReportMemory

logger = logging.getLogger(__name__)


async def load_static_questions(
    supabase: Client,
    company_id: str,
    report_type: str
) -> List[str]:
    """
    Load static questions from Supabase (asked every day).

    Args:
        supabase: Supabase client (MASTER, not company)
        company_id: Company ID
        report_type: 'client_relationships' | 'operations'

    Returns:
        List of question strings

    Raises:
        Exception if no questions found (forces Supabase setup)
    """
    logger.info(f"🔍 Loading static questions for {report_type}")

    try:
        # Connect to MASTER Supabase to get company-specific questions
        # Note: Need to pass master client, not company client
        result = supabase.table("company_report_questions")\
            .select("question_text")\
            .eq("company_id", company_id)\
            .eq("report_type", report_type)\
            .eq("is_active", True)\
            .order("question_order")\
            .execute()

        if not result.data:
            raise Exception(
                f"No static questions found in Supabase for company_id={company_id}, "
                f"report_type={report_type}. Please configure in company_report_questions table."
            )

        questions = [row["question_text"] for row in result.data]

        logger.info(f"   ✅ Loaded {len(questions)} static questions")

        return questions

    except Exception as e:
        logger.error(f"   ❌ Failed to load static questions: {e}")
        raise


async def generate_dynamic_questions(
    previous_memory: Optional[ReportMemory],
    llm,  # OpenAI LLM instance
    max_dynamic_questions: int = 3
) -> List[str]:
    """
    Generate dynamic follow-up questions based on previous day's findings.

    Uses LLM to analyze previous_memory.key_items and create relevant follow-ups.

    Args:
        previous_memory: Memory from previous business day
        llm: LLM instance for generation
        max_dynamic_questions: Max questions to generate (default: 3)

    Returns:
        List of dynamic question strings (empty if no memory)
    """
    if not previous_memory:
        logger.info("   ℹ️  No previous memory - skipping dynamic questions")
        return []

    logger.info(f"🎯 Generating dynamic questions from {previous_memory.report_date}")

    try:
        # Load prompt from Supabase
        from app.services.tenant.context import get_prompt_template

        prompt_template = get_prompt_template('daily_report_dynamic_questions')

        if not prompt_template:
            raise Exception(
                "Missing prompt: daily_report_dynamic_questions in Supabase company_prompts table"
            )

        # Build prompt with previous memory
        import json
        prompt = prompt_template.format(
            previous_summary=previous_memory.summary,
            key_items_json=json.dumps(previous_memory.key_items, indent=2),
            previous_date=previous_memory.report_date.isoformat(),
            max_questions=max_dynamic_questions
        )

        # Call LLM
        response = await llm.acomplete(prompt)
        response_text = str(response).strip()

        # Parse questions (expecting one per line)
        dynamic_questions = [
            q.strip().lstrip('0123456789.-) ')
            for q in response_text.split('\n')
            if q.strip() and not q.strip().startswith('#')
        ][:max_dynamic_questions]

        logger.info(f"   ✅ Generated {len(dynamic_questions)} dynamic questions")
        for i, q in enumerate(dynamic_questions, 1):
            logger.info(f"      {i}. {q}")

        return dynamic_questions

    except Exception as e:
        logger.error(f"   ❌ Failed to generate dynamic questions: {e}")
        # Don't fail the whole report if dynamic questions fail
        return []


async def get_all_questions(
    supabase: Client,
    company_id: str,
    report_type: str,
    previous_memory: Optional[ReportMemory],
    llm
) -> Dict[str, List[str]]:
    """
    Get both static and dynamic questions.

    Args:
        supabase: Supabase client
        company_id: Company ID
        report_type: Report type
        previous_memory: Previous day's memory
        llm: LLM instance

    Returns:
        Dict with 'static' and 'dynamic' question lists
    """
    # Load static (required)
    static_questions = await load_static_questions(supabase, company_id, report_type)

    # Generate dynamic (optional, based on memory)
    dynamic_questions = await generate_dynamic_questions(previous_memory, llm)

    return {
        "static": static_questions,
        "dynamic": dynamic_questions
    }
