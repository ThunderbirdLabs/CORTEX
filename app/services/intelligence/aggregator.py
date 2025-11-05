"""
Intelligence Aggregation Service
Calculates daily, weekly, and monthly metrics from raw documents and graph data
"""
import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any
from decimal import Decimal

from supabase import Client
from neo4j import AsyncDriver
from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# DAILY INTELLIGENCE CALCULATION
# ============================================================================

async def calculate_daily_metrics(
    supabase: Client,
    neo4j_driver: AsyncDriver,
    tenant_id: str,
    target_date: date
) -> Dict[str, Any]:
    """
    Calculate all metrics for a single day.

    Args:
        supabase: Supabase client for querying documents
        neo4j_driver: Neo4j driver for entity queries
        tenant_id: Tenant ID to calculate for
        target_date: Date to analyze (YYYY-MM-DD)

    Returns:
        Dictionary with all daily metrics ready for database insertion
    """
    start_time = datetime.utcnow()

    # Date range for queries
    date_start = f"{target_date}T00:00:00Z"
    date_end = f"{target_date + timedelta(days=1)}T00:00:00Z"
    unix_start = int(target_date.strftime("%s"))
    unix_end = unix_start + 86400

    logger.info(f"📊 Calculating daily intelligence for {tenant_id} on {target_date}")

    # 1. Query all documents for the day
    documents_result = supabase.table("documents")\
        .select("*")\
        .eq("tenant_id", tenant_id)\
        .gte("source_created_at", date_start)\
        .lt("source_created_at", date_end)\
        .execute()

    documents = documents_result.data
    total_documents = len(documents)

    logger.info(f"   Found {total_documents} documents")

    # 2. Calculate document type breakdown
    document_counts = {}
    for doc in documents:
        doc_type = doc.get("document_type", "unknown")
        document_counts[doc_type] = document_counts.get(doc_type, 0) + 1

    # 3. Calculate QuickBooks financial metrics
    qb_metrics = _calculate_quickbooks_metrics(documents)

    # 4. Extract email communication patterns
    email_patterns = _extract_email_patterns(documents)

    # 5. Query Neo4j for entity activity
    entity_activity = await _query_entity_activity(
        neo4j_driver,
        tenant_id,
        unix_start,
        unix_end
    )

    # 6. Identify new entities (first seen today)
    new_entities = await _identify_new_entities(
        neo4j_driver,
        tenant_id,
        unix_start,
        unix_end
    )

    # 7. Extract key topics (simple keyword frequency for now)
    key_topics = _extract_key_topics(documents)

    # Calculate total duration
    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    logger.info(f"   ✅ Daily metrics calculated in {duration_ms}ms")

    return {
        "tenant_id": tenant_id,
        "date": target_date,
        "total_documents": total_documents,
        "document_counts": document_counts,
        "invoice_total_amount": qb_metrics["invoice_total"],
        "invoice_outstanding_balance": qb_metrics["invoice_outstanding"],
        "bill_total_amount": qb_metrics["bill_total"],
        "payment_total_amount": qb_metrics["payment_total"],
        "most_active_people": entity_activity["people"],
        "most_active_companies": entity_activity["companies"],
        "new_entities": new_entities,
        "email_senders": email_patterns["senders"],
        "email_recipients": email_patterns["recipients"],
        "key_topics": key_topics,
        "ai_summary": None,  # Will be generated separately
        "key_insights": [],
        "computation_duration_ms": duration_ms
    }


# ============================================================================
# WEEKLY INTELLIGENCE CALCULATION
# ============================================================================

async def calculate_weekly_trends(
    supabase: Client,
    neo4j_driver: AsyncDriver,
    tenant_id: str,
    week_start: date
) -> Dict[str, Any]:
    """
    Calculate weekly trends by aggregating daily intelligence.

    Args:
        supabase: Supabase client
        neo4j_driver: Neo4j driver
        tenant_id: Tenant ID
        week_start: Monday of the week to analyze

    Returns:
        Dictionary with weekly trend metrics
    """
    start_time = datetime.utcnow()
    week_end = week_start + timedelta(days=6)  # Sunday

    logger.info(f"📈 Calculating weekly trends for {tenant_id}: {week_start} to {week_end}")

    # 1. Get all daily intelligence records for the week
    daily_records = supabase.table("daily_intelligence")\
        .select("*")\
        .eq("tenant_id", tenant_id)\
        .gte("date", week_start.isoformat())\
        .lte("date", week_end.isoformat())\
        .order("date")\
        .execute()

    daily_data = daily_records.data

    if not daily_data:
        logger.warning(f"   No daily intelligence found for week {week_start}")
        # Fall back to querying documents directly
        return await _calculate_weekly_from_documents(
            supabase, neo4j_driver, tenant_id, week_start, week_end
        )

    # 2. Aggregate weekly totals
    total_documents = sum(d["total_documents"] for d in daily_data)

    # 3. Build daily trend data
    document_trend = {
        d["date"]: d["total_documents"]
        for d in daily_data
    }

    # 4. Calculate week-over-week change
    prev_week_start = week_start - timedelta(days=7)
    prev_week_end = prev_week_start + timedelta(days=6)

    prev_week_result = supabase.table("daily_intelligence")\
        .select("total_documents")\
        .eq("tenant_id", tenant_id)\
        .gte("date", prev_week_start.isoformat())\
        .lte("date", prev_week_end.isoformat())\
        .execute()

    prev_week_total = sum(d["total_documents"] for d in prev_week_result.data) if prev_week_result.data else 0

    wow_change = 0.0
    if prev_week_total > 0:
        wow_change = ((total_documents - prev_week_total) / prev_week_total) * 100

    # 5. Aggregate entity activity
    all_people = {}
    all_companies = {}

    for d in daily_data:
        for person in d.get("most_active_people", []):
            name = person["name"]
            all_people[name] = all_people.get(name, 0) + person.get("mentions", 0)

        for company in d.get("most_active_companies", []):
            name = company["name"]
            all_companies[name] = all_companies.get(name, 0) + company.get("mentions", 0)

    # Sort and format trending entities
    trending_people = [
        {"name": name, "mentions": count, "trend": "up" if count > 10 else "stable"}
        for name, count in sorted(all_people.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    trending_companies = [
        {"name": name, "mentions": count, "trend": "up" if count > 5 else "stable"}
        for name, count in sorted(all_companies.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # 6. Aggregate financial metrics
    weekly_revenue = sum(d.get("invoice_total_amount") or 0 for d in daily_data)
    weekly_expenses = sum(d.get("bill_total_amount") or 0 for d in daily_data)

    revenue_trend = [
        {"date": d["date"], "amount": float(d.get("invoice_total_amount") or 0)}
        for d in daily_data
    ]

    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    logger.info(f"   ✅ Weekly trends calculated in {duration_ms}ms")

    return {
        "tenant_id": tenant_id,
        "week_start": week_start,
        "week_end": week_end,
        "total_documents": total_documents,
        "document_trend": document_trend,
        "wow_change_percent": Decimal(str(round(wow_change, 2))),
        "total_unique_entities": len(all_people) + len(all_companies),
        "new_entities_count": 0,  # TODO: Calculate from daily new_entities
        "new_entities": [],
        "trending_people": trending_people,
        "trending_companies": trending_companies,
        "trending_topics": [],
        "new_relationships": [],
        "collaboration_patterns": [],
        "deals_advancing": [],
        "deals_stalling": [],
        "weekly_revenue": Decimal(str(weekly_revenue)),
        "weekly_expenses": Decimal(str(weekly_expenses)),
        "revenue_trend": revenue_trend,
        "weekly_summary": None,  # Will be generated with LLM
        "key_insights": [],
        "action_items": [],
        "computation_duration_ms": duration_ms
    }


# ============================================================================
# MONTHLY INTELLIGENCE CALCULATION
# ============================================================================

async def calculate_monthly_insights(
    supabase: Client,
    neo4j_driver: AsyncDriver,
    tenant_id: str,
    month: date
) -> Dict[str, Any]:
    """
    Calculate monthly strategic insights.

    Args:
        supabase: Supabase client
        neo4j_driver: Neo4j driver
        tenant_id: Tenant ID
        month: First day of the month (YYYY-MM-01)

    Returns:
        Dictionary with monthly insight metrics
    """
    start_time = datetime.utcnow()

    # Calculate month boundaries
    if month.month == 12:
        month_end = date(month.year + 1, 1, 1) - timedelta(days=1)
    else:
        month_end = date(month.year, month.month + 1, 1) - timedelta(days=1)

    logger.info(f"📊 Calculating monthly insights for {tenant_id}: {month} to {month_end}")

    # 1. Get all weekly intelligence for the month
    weekly_records = supabase.table("weekly_intelligence")\
        .select("*")\
        .eq("tenant_id", tenant_id)\
        .gte("week_start", month.isoformat())\
        .lt("week_start", month_end.isoformat())\
        .execute()

    weekly_data = weekly_records.data

    # 2. Get all documents for the month (for comprehensive metrics)
    month_start_str = f"{month}T00:00:00Z"
    month_end_str = f"{month_end + timedelta(days=1)}T00:00:00Z"

    documents_result = supabase.table("documents")\
        .select("*")\
        .eq("tenant_id", tenant_id)\
        .gte("source_created_at", month_start_str)\
        .lt("source_created_at", month_end_str)\
        .execute()

    documents = documents_result.data

    # 3. Calculate document type counts
    total_emails = sum(1 for d in documents if d.get("document_type") == "email")
    total_invoices = sum(1 for d in documents if d.get("document_type") == "invoice")
    total_bills = sum(1 for d in documents if d.get("document_type") == "bill")
    total_payments = sum(1 for d in documents if d.get("document_type") == "payment")

    # 4. Calculate QuickBooks financial summary
    total_revenue = Decimal('0')
    total_expenses = Decimal('0')
    revenue_by_customer = {}

    for doc in documents:
        if doc.get("document_type") == "invoice" and doc.get("metadata"):
            amount = Decimal(str(doc["metadata"].get("total", 0)))
            total_revenue += amount

            customer = doc["metadata"].get("customer_name", "Unknown")
            revenue_by_customer[customer] = revenue_by_customer.get(customer, Decimal('0')) + amount

        if doc.get("document_type") == "bill" and doc.get("metadata"):
            amount = Decimal(str(doc["metadata"].get("total", 0)))
            total_expenses += amount

    net_income = total_revenue - total_expenses

    # 5. Format revenue by customer
    revenue_list = [
        {"customer": customer, "revenue": float(amount)}
        for customer, amount in sorted(revenue_by_customer.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # 6. Calculate month-over-month changes
    prev_month = month - timedelta(days=month.day)  # Go to last day of previous month
    prev_month = date(prev_month.year, prev_month.month, 1)  # First day of prev month

    prev_month_result = supabase.table("monthly_intelligence")\
        .select("total_documents, total_revenue")\
        .eq("tenant_id", tenant_id)\
        .eq("month", prev_month.isoformat())\
        .execute()

    mom_document_change = 0.0
    mom_revenue_change = 0.0

    if prev_month_result.data:
        prev_data = prev_month_result.data[0]
        prev_docs = prev_data.get("total_documents", 0)
        prev_revenue = Decimal(str(prev_data.get("total_revenue") or 0))

        if prev_docs > 0:
            mom_document_change = ((len(documents) - prev_docs) / prev_docs) * 100

        if prev_revenue > 0:
            mom_revenue_change = float(((total_revenue - prev_revenue) / prev_revenue) * 100)

    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    logger.info(f"   ✅ Monthly insights calculated in {duration_ms}ms")

    return {
        "tenant_id": tenant_id,
        "month": month,
        "total_documents": len(documents),
        "total_emails": total_emails,
        "total_invoices": total_invoices,
        "total_bills": total_bills,
        "total_payments": total_payments,
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "net_income": net_income,
        "revenue_by_customer": revenue_list,
        "expense_by_category": [],  # TODO: Extract from bill metadata
        "total_unique_entities": 0,  # TODO: Query from Neo4j
        "new_entities_this_month": 0,
        "most_active_entities": [],
        "expertise_evolution": [],
        "key_relationships": [],
        "collaboration_networks": [],
        "goal_alignment_score": None,
        "initiative_effectiveness": [],
        "mom_document_change_percent": Decimal(str(round(mom_document_change, 2))),
        "mom_revenue_change_percent": Decimal(str(round(mom_revenue_change, 2))),
        "mom_entity_growth_percent": Decimal('0'),
        "executive_summary": None,  # Will be generated with LLM
        "strategic_insights": [],
        "recommendations": [],
        "communication_health_score": None,
        "financial_health_score": None,
        "growth_momentum_score": None,
        "computation_duration_ms": duration_ms
    }


# ============================================================================
# AI SUMMARY GENERATION
# ============================================================================

async def generate_ai_summary(
    metrics: Dict[str, Any],
    period_type: str,
    openai_client: AsyncOpenAI
) -> str:
    """
    Generate natural language summary using LLM.

    Args:
        metrics: Dictionary of calculated metrics
        period_type: "daily", "weekly", or "monthly"
        openai_client: OpenAI async client

    Returns:
        Natural language summary string
    """
    logger.info(f"🤖 Generating {period_type} AI summary...")

    # Build context for LLM
    if period_type == "daily":
        context = _build_daily_context(metrics)
        prompt = f"""You are an executive assistant summarizing yesterday's business activity.

Context:
{context}

Write a concise 2-3 sentence daily summary highlighting the most important activities and insights. Focus on what matters to executives."""

    elif period_type == "weekly":
        context = _build_weekly_context(metrics)
        prompt = f"""You are an executive assistant summarizing this week's business trends.

Context:
{context}

Write a concise weekly summary (3-4 sentences) highlighting:
1. Key trends and patterns
2. Notable changes from last week
3. Areas requiring attention

Focus on strategic insights, not just numbers."""

    else:  # monthly
        context = _build_monthly_context(metrics)
        prompt = f"""You are an executive assistant creating a monthly strategic summary.

Context:
{context}

Write an executive summary (4-5 sentences) covering:
1. Overall business performance
2. Key accomplishments and challenges
3. Strategic implications
4. Recommended focus areas

This will be read by C-level executives."""

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Fast and cost-effective
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=300
        )

        summary = response.choices[0].message.content.strip()
        logger.info(f"   ✅ AI summary generated ({len(summary)} chars)")
        return summary

    except Exception as e:
        logger.error(f"   ❌ Failed to generate AI summary: {e}")
        return f"Summary generation failed for {period_type} period. Metrics available in structured format."


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _calculate_quickbooks_metrics(documents: List[Dict]) -> Dict[str, Decimal]:
    """Calculate QuickBooks financial metrics from documents."""
    invoice_total = Decimal('0')
    invoice_outstanding = Decimal('0')
    bill_total = Decimal('0')
    payment_total = Decimal('0')

    for doc in documents:
        if doc.get("source") != "quickbooks" or not doc.get("metadata"):
            continue

        doc_type = doc.get("document_type")
        metadata = doc.get("metadata", {})

        if doc_type == "invoice":
            invoice_total += Decimal(str(metadata.get("total", 0)))
            invoice_outstanding += Decimal(str(metadata.get("balance", 0)))
        elif doc_type == "bill":
            bill_total += Decimal(str(metadata.get("total", 0)))
        elif doc_type == "payment":
            payment_total += Decimal(str(metadata.get("total", 0)))

    return {
        "invoice_total": invoice_total,
        "invoice_outstanding": invoice_outstanding,
        "bill_total": bill_total,
        "payment_total": payment_total
    }


def _extract_email_patterns(documents: List[Dict]) -> Dict[str, List[Dict]]:
    """Extract email sender/recipient patterns."""
    senders = {}
    recipients = {}

    for doc in documents:
        if doc.get("document_type") != "email" or not doc.get("metadata"):
            continue

        metadata = doc.get("metadata", {})

        sender = metadata.get("sender_address") or metadata.get("from")
        if sender:
            senders[sender] = senders.get(sender, 0) + 1

        to_addresses = metadata.get("to_addresses", [])
        if isinstance(to_addresses, str):
            to_addresses = [to_addresses]

        for recipient in to_addresses:
            if recipient:
                recipients[recipient] = recipients.get(recipient, 0) + 1

    # Format as list of dicts, sorted by frequency
    senders_list = [
        {"email": email, "count": count}
        for email, count in sorted(senders.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    recipients_list = [
        {"email": email, "count": count}
        for email, count in sorted(recipients.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    return {
        "senders": senders_list,
        "recipients": recipients_list
    }


def _extract_key_topics(documents: List[Dict], top_n: int = 10) -> List[Dict]:
    """
    Extract key topics from document content using simple keyword frequency.
    TODO: Replace with more sophisticated topic modeling (LDA, BERT, etc.)
    """
    from collections import Counter
    import re

    # Simple stopwords
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "up", "about", "into", "through", "during",
        "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "will", "would", "should", "could", "may", "might",
        "this", "that", "these", "those", "i", "you", "he", "she", "it", "we",
        "they", "what", "which", "who", "when", "where", "why", "how"
    }

    word_freq = Counter()

    for doc in documents:
        content = doc.get("content", "") + " " + doc.get("title", "")

        # Extract words (alphanumeric, 3+ chars)
        words = re.findall(r'\b[a-z]{3,}\b', content.lower())

        # Filter stopwords
        words = [w for w in words if w not in stopwords]

        word_freq.update(words)

    # Return top topics
    return [
        {"topic": word, "count": count, "confidence": 0.7}
        for word, count in word_freq.most_common(top_n)
    ]


async def _query_entity_activity(
    neo4j_driver: AsyncDriver,
    tenant_id: str,
    start_timestamp: int,
    end_timestamp: int
) -> Dict[str, List[Dict]]:
    """Query Neo4j for entity mention frequency during time period."""

    query = """
    MATCH (chunk:Chunk)-[:MENTIONS]->(entity)
    WHERE chunk.created_at_timestamp >= $start_ts
      AND chunk.created_at_timestamp < $end_ts
      AND chunk.tenant_id = $tenant_id
    WITH labels(entity)[0] as entity_type, entity.name as name, count(chunk) as mentions
    RETURN entity_type, name, mentions
    ORDER BY mentions DESC
    LIMIT 20
    """

    try:
        async with neo4j_driver.session() as session:
            result = await session.run(
                query,
                tenant_id=tenant_id,
                start_ts=start_timestamp,
                end_ts=end_timestamp
            )

            records = await result.data()

        # Separate by entity type
        people = []
        companies = []

        for record in records:
            entity_type = record["entity_type"]
            entity_data = {
                "name": record["name"],
                "mentions": record["mentions"]
            }

            if entity_type == "PERSON":
                people.append(entity_data)
            elif entity_type == "COMPANY":
                companies.append(entity_data)

        return {
            "people": people[:10],
            "companies": companies[:10]
        }

    except Exception as e:
        logger.error(f"Failed to query Neo4j entity activity: {e}")
        return {"people": [], "companies": []}


async def _identify_new_entities(
    neo4j_driver: AsyncDriver,
    tenant_id: str,
    start_timestamp: int,
    end_timestamp: int
) -> List[Dict]:
    """
    Identify entities first seen during this time period.
    TODO: Track entity first_seen_timestamp in Neo4j for efficiency
    """
    # For now, return empty list
    # Full implementation would require tracking entity creation timestamps
    return []


async def _calculate_weekly_from_documents(
    supabase: Client,
    neo4j_driver: AsyncDriver,
    tenant_id: str,
    week_start: date,
    week_end: date
) -> Dict[str, Any]:
    """Fallback: Calculate weekly metrics directly from documents if daily intelligence missing."""
    logger.info(f"   ⚠️  No daily intelligence found, calculating from raw documents")

    # This is a simplified version - ideally daily intelligence should exist
    week_start_str = f"{week_start}T00:00:00Z"
    week_end_str = f"{week_end + timedelta(days=1)}T00:00:00Z"

    documents_result = supabase.table("documents")\
        .select("*")\
        .eq("tenant_id", tenant_id)\
        .gte("source_created_at", week_start_str)\
        .lt("source_created_at", week_end_str)\
        .execute()

    documents = documents_result.data

    return {
        "tenant_id": tenant_id,
        "week_start": week_start,
        "week_end": week_end,
        "total_documents": len(documents),
        "document_trend": {},
        "wow_change_percent": Decimal('0'),
        "total_unique_entities": 0,
        "new_entities_count": 0,
        "new_entities": [],
        "trending_people": [],
        "trending_companies": [],
        "trending_topics": [],
        "new_relationships": [],
        "collaboration_patterns": [],
        "deals_advancing": [],
        "deals_stalling": [],
        "weekly_revenue": Decimal('0'),
        "weekly_expenses": Decimal('0'),
        "revenue_trend": [],
        "weekly_summary": "Insufficient data - daily intelligence not generated",
        "key_insights": [],
        "action_items": [],
        "computation_duration_ms": 0
    }


def _build_daily_context(metrics: Dict) -> str:
    """Build context string for daily summary LLM prompt."""
    lines = [
        f"Date: {metrics['date']}",
        f"Total Activity: {metrics['total_documents']} documents",
        f"Emails: {metrics['document_counts'].get('email', 0)}",
    ]

    if metrics.get('invoice_total_amount'):
        lines.append(f"Revenue: ${metrics['invoice_total_amount']:,.2f}")

    if metrics.get('most_active_people'):
        people = ", ".join(p['name'] for p in metrics['most_active_people'][:3])
        lines.append(f"Most Active: {people}")

    return "\n".join(lines)


def _build_weekly_context(metrics: Dict) -> str:
    """Build context string for weekly summary LLM prompt."""
    lines = [
        f"Week: {metrics['week_start']} to {metrics['week_end']}",
        f"Total Activity: {metrics['total_documents']} documents",
        f"Change from Last Week: {metrics['wow_change_percent']}%",
    ]

    if metrics.get('weekly_revenue'):
        lines.append(f"Weekly Revenue: ${metrics['weekly_revenue']:,.2f}")

    if metrics.get('trending_people'):
        people = ", ".join(p['name'] for p in metrics['trending_people'][:3])
        lines.append(f"Trending: {people}")

    return "\n".join(lines)


def _build_monthly_context(metrics: Dict) -> str:
    """Build context string for monthly summary LLM prompt."""
    lines = [
        f"Month: {metrics['month'].strftime('%B %Y')}",
        f"Total Activity: {metrics['total_documents']} documents",
        f"Emails: {metrics['total_emails']}, Invoices: {metrics['total_invoices']}",
    ]

    if metrics.get('total_revenue'):
        lines.append(f"Revenue: ${metrics['total_revenue']:,.2f}")
        lines.append(f"Net Income: ${metrics['net_income']:,.2f}")

    if metrics.get('mom_document_change_percent'):
        lines.append(f"Activity Change: {metrics['mom_document_change_percent']}% from last month")

    if metrics.get('revenue_by_customer'):
        top_customer = metrics['revenue_by_customer'][0]
        lines.append(f"Top Customer: {top_customer['customer']} (${top_customer['revenue']:,.2f})")

    return "\n".join(lines)
