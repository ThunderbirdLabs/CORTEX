"""
Email persistence helpers
Handles Supabase storage, JSONL debugging, and Cortex ingestion
"""
import json
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from supabase import Client

from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline
from app.services.universal.ingest import ingest_document_universal
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# SUPABASE PERSISTENCE
# ============================================================================

async def persist_email_row(supabase: Client, email: Dict[str, Any]):
    """
    Insert email row into Supabase.
    Uses upsert to handle duplicates gracefully based on (tenant_id, source, message_id).

    Args:
        supabase: Supabase client instance
        email: Normalized email dictionary
    """
    try:
        # Ensure to_addresses is properly formatted as a list
        # Supabase JSONB fields need explicit list type, not JSON string
        if "to_addresses" in email:
            to_addrs = email["to_addresses"]
            # If it's already a list, ensure all elements are strings
            if isinstance(to_addrs, list):
                email["to_addresses"] = [str(addr) for addr in to_addrs if addr]
            # If it's a string (shouldn't happen, but handle it), convert to list
            elif isinstance(to_addrs, str):
                try:
                    # Try parsing as JSON
                    parsed = json.loads(to_addrs)
                    if isinstance(parsed, list):
                        email["to_addresses"] = [str(addr) for addr in parsed if addr]
                    else:
                        email["to_addresses"] = [to_addrs]
                except json.JSONDecodeError:
                    email["to_addresses"] = [to_addrs] if to_addrs else []
            else:
                email["to_addresses"] = []

        # Supabase insert with upsert on composite unique constraint
        result = supabase.table("emails").upsert(
            email,
            on_conflict="tenant_id,source,message_id"
        ).execute()

        # Check if insert was successful
        if result.data:
            logger.debug(f"Persisted {email.get('source', 'email')} message {email['message_id']}")
    except Exception as e:
        logger.error(f"Error persisting email {email.get('message_id')}: {e}")
        # Don't raise - continue with other messages


# ============================================================================
# JSONL DEBUGGING
# ============================================================================

async def append_jsonl(email: Dict[str, Any]):
    """
    Append normalized email to JSONL file for debugging.

    Args:
        email: Normalized email dictionary
    """
    if not settings.save_jsonl:
        return

    try:
        with open("./outbox.jsonl", "a") as f:
            f.write(json.dumps(email) + "\n")
    except Exception as e:
        logger.error(f"Error writing to JSONL: {e}")


# ============================================================================
# CORTEX INGESTION
# ============================================================================

async def ingest_to_cortex(
    cortex_pipeline: Optional[HybridPropertyGraphPipeline],
    email: Dict[str, Any],
    supabase: Optional[Client] = None
):
    """
    Ingest email using UNIVERSAL INGESTION FLOW.

    This uses the new unified system that:
    1. Normalizes email into universal format
    2. Saves to documents table (Supabase)
    3. Ingests to PropertyGraph (Neo4j + Qdrant)

    Args:
        cortex_pipeline: Cortex pipeline instance (or None if disabled)
        email: Normalized email dictionary
        supabase: Supabase client (for documents table)

    Returns:
        Dict with ingestion results or None if pipeline not initialized/failed
    """
    if not cortex_pipeline:
        logger.debug("Cortex pipeline not initialized, skipping ingestion")
        return None

    if not supabase:
        logger.warning("Supabase client not provided, using old ingestion flow")
        # Fallback to old method
        try:
            result = await cortex_pipeline.ingest_document(
                content=email.get("full_body", ""),
                document_name=email.get("subject", "No Subject"),
                source=email.get("source", "gmail"),
                document_type="email",
                reference_time=email.get("received_datetime"),
                metadata={
                    "message_id": email.get("message_id"),
                    "sender_name": email.get("sender_name", ""),
                    "sender_address": email.get("sender_address", ""),
                    "to_addresses": email.get("to_addresses", []),
                    "tenant_id": email.get("tenant_id"),
                    "user_id": email.get("user_id"),
                    "web_link": email.get("web_link", "")
                }
            )
            return result
        except Exception as e:
            logger.error(f"Error ingesting email: {e}")
            return None

    try:
        logger.info(f"📧 Universal ingestion: {email.get('subject', 'No Subject')[:50]}...")

        # Parse received_datetime
        received_dt = None
        if email.get("received_datetime"):
            try:
                if isinstance(email["received_datetime"], str):
                    received_dt = datetime.fromisoformat(email["received_datetime"].replace('Z', '+00:00'))
                else:
                    received_dt = email["received_datetime"]
            except Exception as e:
                logger.warning(f"Failed to parse received_datetime: {e}")

        # Use universal ingestion function
        result = await ingest_document_universal(
            supabase=supabase,
            cortex_pipeline=cortex_pipeline,
            tenant_id=email.get("tenant_id"),
            source=email.get("source", "gmail"),
            source_id=email.get("message_id"),
            document_type="email",
            title=email.get("subject", "No Subject"),
            content=email.get("full_body", ""),
            raw_data=email,  # Preserve full email structure
            source_created_at=received_dt,
            metadata={
                "sender_name": email.get("sender_name", ""),
                "sender_address": email.get("sender_address", ""),
                "to_addresses": email.get("to_addresses", []),
                "user_id": email.get("user_id"),
                "web_link": email.get("web_link", "")
            }
        )

        if result['status'] == 'success':
            logger.info(f"✅ Universal ingestion successful")
        else:
            logger.error(f"❌ Universal ingestion failed: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"Error in universal ingestion: {e}")
        return None
