"""
Email persistence helpers
Handles Supabase storage, JSONL debugging, and Cortex ingestion
"""
import json
import logging
from typing import Any, Dict, Optional

from supabase import Client

from app.services.ingestion.pipeline import HybridRAGPipeline
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
    cortex_pipeline: Optional[HybridRAGPipeline],
    email: Dict[str, Any]
):
    """
    Ingest email into Cortex Hybrid RAG system.

    Processes email through Cortex pipeline:
    1. Chunks the document intelligently
    2. Generates embeddings and stores in Qdrant vector DB
    3. Extracts entities and relationships for Neo4j knowledge graph via Graphiti
    4. Links both systems with a shared episode_id UUID

    Args:
        cortex_pipeline: Cortex pipeline instance (or None if disabled)
        email: Normalized email dictionary

    Returns:
        Dict with ingestion results or None if pipeline not initialized/failed
    """
    if not cortex_pipeline:
        logger.debug("Cortex pipeline not initialized, skipping ingestion")
        return None

    try:
        logger.info(f"Ingesting email to Cortex: {email.get('subject', 'No Subject')[:50]}...")

        # Call Cortex pipeline directly (already in same codebase)
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

        logger.info(f"Cortex ingestion successful: episode_id={result['episode_id']}, chunks={result['num_chunks']}")
        return result

    except Exception as e:
        logger.error(f"Error ingesting email to Cortex: {e}")
        # Don't raise - continue with other messages
        return None
