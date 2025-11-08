"""
Real-Time Urgency Detection Service

Analyzes documents as they arrive to detect urgent issues requiring immediate attention.
Uses GPT-4o-mini for fast, cost-effective classification.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from openai import AsyncOpenAI
from supabase import Client

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = AsyncOpenAI()


URGENCY_DETECTION_PROMPT = """Analyze this business document for urgency and potential issues.

Your job: Quickly identify if this document contains critical business problems that need immediate attention.

DOCUMENT CONTENT:
Title: {title}
Source: {source}
Content: {content}

METADATA:
- Sender: {sender}
- Date: {date}
- Type: {doc_type}

INSTRUCTIONS:
1. Determine urgency level:
   - **critical**: Revenue at immediate risk, angry customer, system down, compliance violation
   - **high**: Order blocked, approval needed today, customer complaint, missed deadline
   - **medium**: Potential issue developing, needs attention this week
   - **low**: FYI, minor concern, monitoring needed

2. Identify alert category (if urgent):
   - **revenue_risk**: Orders blocked, payment issues, contract problems, deal at risk
   - **customer_escalation**: Angry emails, complaints, dissatisfaction, churn signals
   - **operational_issue**: Part delays, engineering blocks, approval bottlenecks, process failures
   - **time_sensitive**: Deadlines approaching, urgent requests, expiring opportunities
   - **financial**: Invoice problems, budget overruns, cash flow issues, unexpected costs
   - **none**: No significant issues detected

3. Extract key entities mentioned (if any):
   - Customer names (e.g., "General Dynamics", "TTI Inc")
   - Part numbers (e.g., "7020-9036", "121-20001")
   - Dollar amounts (e.g., "$127K", "$50,000")
   - Order/PO numbers (e.g., "PO-123456")
   - People names (e.g., "John Smith")

4. Write a ONE SENTENCE summary (if urgent) that answers:
   - WHAT is the problem?
   - WHO is affected?
   - WHY does it matter?

Return ONLY valid JSON (no markdown, no explanation):
{{
  "urgency_level": "critical|high|medium|low",
  "alert_category": "revenue_risk|customer_escalation|operational_issue|time_sensitive|financial|none",
  "summary": "One sentence description of the issue (empty string if low urgency)",
  "key_entities": ["entity1", "entity2", "entity3"],
  "requires_action": true|false,
  "confidence": 0.0-1.0
}}

EXAMPLES:

Email about blocked order:
{{
  "urgency_level": "critical",
  "alert_category": "revenue_risk",
  "summary": "General Dynamics order for $127K blocked waiting for engineering approval on part 7020-9036",
  "key_entities": ["General Dynamics", "7020-9036", "$127K"],
  "requires_action": true,
  "confidence": 0.95
}}

Angry customer email:
{{
  "urgency_level": "high",
  "alert_category": "customer_escalation",
  "summary": "TTI Inc escalating complaint about 2-week delay on 5 orders, threatening to cancel",
  "key_entities": ["TTI Inc"],
  "requires_action": true,
  "confidence": 0.9
}}

Routine status update:
{{
  "urgency_level": "low",
  "alert_category": "none",
  "summary": "",
  "key_entities": [],
  "requires_action": false,
  "confidence": 0.85
}}

Now analyze the document above."""


async def detect_urgency(
    document_id: int,
    title: str,
    content: str,
    metadata: Dict[str, Any],
    source: str,
    tenant_id: str,
    supabase: Client
) -> Optional[Dict[str, Any]]:
    """
    Analyze a document for urgency using GPT-4o-mini.

    Args:
        document_id: Document ID
        title: Document title
        content: Document content (first ~2000 chars for cost efficiency)
        metadata: Document metadata (sender, date, etc.)
        source: Document source (email, drive, etc.)
        tenant_id: Tenant ID
        supabase: Supabase client

    Returns:
        Alert data dict if urgent (high/critical), None otherwise
    """
    try:
        # Prepare document context
        sender = metadata.get("sender") or metadata.get("from") or "Unknown"
        date = metadata.get("date") or metadata.get("created_at") or "Unknown"
        doc_type = metadata.get("doc_type") or source

        # Truncate content for cost efficiency (GPT-4o-mini is cheap but still)
        content_preview = content[:2000] if len(content) > 2000 else content

        # Format prompt
        prompt = URGENCY_DETECTION_PROMPT.format(
            title=title,
            source=source,
            content=content_preview,
            sender=sender,
            date=date,
            doc_type=doc_type
        )

        logger.info(f"🔍 Analyzing document {document_id} for urgency (tenant: {tenant_id})")

        # Call GPT-4o-mini
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a business intelligence analyst that quickly identifies urgent issues in documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Low temperature for consistent classification
            max_tokens=300,
            response_format={"type": "json_object"}
        )

        # Parse response
        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        logger.info(f"📊 Urgency detection result for doc {document_id}: {result['urgency_level']} - {result['alert_category']}")

        # Update document with urgency info
        supabase.table("documents").update({
            "urgency_level": result["urgency_level"],
            "alert_category": result["alert_category"],
            "entity_mentions": result.get("key_entities", []),
            "urgency_detected_at": datetime.utcnow().isoformat()
        }).eq("id", document_id).eq("tenant_id", tenant_id).execute()

        # Only create alert if high or critical
        if result["urgency_level"] in ["high", "critical"] and result["alert_category"] != "none":
            alert_data = {
                "document_id": document_id,
                "tenant_id": tenant_id,
                "alert_type": result["alert_category"],
                "urgency_level": result["urgency_level"],
                "summary": result.get("summary", "Urgent issue detected"),
                "key_entities": result.get("key_entities", []),
                "requires_action": result.get("requires_action", True),
                "detection_confidence": result.get("confidence", 0.8),
                "llm_response": result
            }

            # Insert alert into database
            alert_result = supabase.table("document_alerts").insert(alert_data).execute()
            logger.info(f"🚨 ALERT CREATED: {result['urgency_level'].upper()} - {result['summary'][:100]}")

            return alert_result.data[0] if alert_result.data else None

        return None

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response for document {document_id}: {e}")
        logger.error(f"Response was: {result_text[:500]}")
        return None

    except Exception as e:
        logger.error(f"Error detecting urgency for document {document_id}: {e}", exc_info=True)
        return None


async def batch_detect_urgency(
    documents: List[Dict[str, Any]],
    tenant_id: str,
    supabase: Client
) -> List[Optional[Dict[str, Any]]]:
    """
    Detect urgency for multiple documents (for backfill/testing).

    Args:
        documents: List of document dicts with id, title, content, metadata, source
        tenant_id: Tenant ID
        supabase: Supabase client

    Returns:
        List of alert dicts (None for non-urgent documents)
    """
    import asyncio

    tasks = []
    for doc in documents:
        task = detect_urgency(
            document_id=doc["id"],
            title=doc.get("title", ""),
            content=doc.get("content", ""),
            metadata=doc.get("metadata", {}),
            source=doc.get("source", "unknown"),
            tenant_id=tenant_id,
            supabase=supabase
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter out exceptions and None values
    alerts = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"Batch processing failed for document {documents[i].get('id')}: {result}")
        elif result is not None:
            alerts.append(result)

    return alerts


def get_alert_summary_stats(tenant_id: str, supabase: Client) -> Dict[str, Any]:
    """
    Get summary statistics for alerts.

    Args:
        tenant_id: Tenant ID
        supabase: Supabase client

    Returns:
        Stats dict with counts by urgency level
    """
    try:
        # Get active alerts count by urgency
        result = supabase.table("document_alerts")\
            .select("urgency_level", count="exact")\
            .eq("tenant_id", tenant_id)\
            .is_("dismissed_at", "null")\
            .execute()

        # Count by urgency level
        stats = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "total_active": len(result.data) if result.data else 0
        }

        if result.data:
            for alert in result.data:
                level = alert.get("urgency_level", "low")
                if level in stats:
                    stats[level] += 1

        return stats

    except Exception as e:
        logger.error(f"Error getting alert stats: {e}")
        return {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "total_active": 0,
            "error": str(e)
        }
