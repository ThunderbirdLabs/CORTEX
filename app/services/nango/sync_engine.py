"""
Email sync orchestration engine
Coordinates Outlook and Gmail sync operations
"""
import logging
from typing import Any, Dict, List, Optional

import httpx
from supabase import Client

from app.services.ingestion.pipeline import HybridRAGPipeline
from app.services.nango.database import get_connection, get_gmail_cursor, set_gmail_cursor
from app.services.connectors.gmail import normalize_gmail_message
from app.services.connectors.microsoft_graph import list_all_users, normalize_message, sync_user_mailbox
from app.services.nango.nango_client import get_graph_token_via_nango, nango_list_gmail_records
from app.services.nango.persistence import append_jsonl, ingest_to_cortex, persist_email_row

logger = logging.getLogger(__name__)


# ============================================================================
# OUTLOOK SYNC
# ============================================================================

async def run_tenant_sync(
    http_client: httpx.AsyncClient,
    supabase: Client,
    cortex_pipeline: Optional[HybridRAGPipeline],
    tenant_id: str,
    provider_key: str
) -> Dict[str, Any]:
    """
    Run a full Outlook sync for a tenant.

    Args:
        http_client: Async HTTP client instance
        supabase: Supabase client instance
        cortex_pipeline: Cortex pipeline instance (or None if disabled)
        tenant_id: Tenant identifier
        provider_key: Provider configuration key

    Returns:
        Dictionary with sync statistics
    """
    logger.info(f"Starting Outlook sync for tenant {tenant_id}")

    users_synced = 0
    messages_synced = 0
    errors = []

    try:
        # Get connection ID
        connection_id = await get_connection(tenant_id, provider_key)
        if not connection_id:
            error_msg = f"No connection found for tenant {tenant_id}"
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "status": "error",
                "tenant_id": tenant_id,
                "users_synced": 0,
                "messages_synced": 0,
                "errors": errors
            }

        # Get Graph access token
        access_token = await get_graph_token_via_nango(http_client, provider_key, connection_id)

        # List all users in tenant
        users = await list_all_users(http_client, access_token)

        # Sync each user's mailbox
        for user in users:
            user_id = user["id"]
            user_principal_name = user["userPrincipalName"]

            try:
                # Sync mailbox using delta API
                raw_messages = await sync_user_mailbox(
                    http_client,
                    access_token,
                    tenant_id,
                    provider_key,
                    user_id,
                    user_principal_name
                )

                # Process and persist messages
                for raw_msg in raw_messages:
                    try:
                        # Skip deleted messages
                        if raw_msg.get("@removed"):
                            continue

                        # Normalize message
                        normalized = normalize_message(
                            raw_msg,
                            tenant_id,
                            user_id,
                            user_principal_name
                        )

                        # Persist to Supabase
                        await persist_email_row(supabase, normalized)

                        # Optionally write to JSONL
                        await append_jsonl(normalized)

                        # Ingest to Cortex (disabled for Outlook in original code)
                        # await ingest_to_cortex(cortex_pipeline, normalized)

                        messages_synced += 1
                    except Exception as e:
                        error_msg = f"Error processing message: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                users_synced += 1

            except Exception as e:
                error_msg = f"Error syncing user {user_principal_name}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        logger.info(f"Outlook sync completed for tenant {tenant_id}: {users_synced} users, {messages_synced} messages")

        return {
            "status": "success" if not errors else "partial_success",
            "tenant_id": tenant_id,
            "users_synced": users_synced,
            "messages_synced": messages_synced,
            "errors": errors
        }

    except Exception as e:
        error_msg = f"Fatal error during Outlook sync: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        return {
            "status": "error",
            "tenant_id": tenant_id,
            "users_synced": users_synced,
            "messages_synced": messages_synced,
            "errors": errors
        }


# ============================================================================
# GMAIL SYNC
# ============================================================================

async def run_gmail_sync(
    http_client: httpx.AsyncClient,
    supabase: Client,
    cortex_pipeline: Optional[HybridRAGPipeline],
    tenant_id: str,
    provider_key: str,
    modified_after: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a full Gmail sync for a tenant using Nango unified API.

    Args:
        http_client: Async HTTP client instance
        supabase: Supabase client instance
        cortex_pipeline: Cortex pipeline instance (or None if disabled)
        tenant_id: Tenant identifier
        provider_key: Nango provider configuration key
        modified_after: Optional ISO datetime to filter records

    Returns:
        Dictionary with sync statistics
    """
    logger.info(f"Starting Gmail sync for tenant {tenant_id}")

    messages_synced = 0
    errors = []

    try:
        # Get connection ID
        connection_id = await get_connection(tenant_id, provider_key)
        if not connection_id:
            error_msg = f"No Gmail connection found for tenant {tenant_id}"
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "status": "error",
                "tenant_id": tenant_id,
                "messages_synced": 0,
                "errors": errors
            }

        # Get stored cursor for incremental sync
        stored_cursor = await get_gmail_cursor(tenant_id, provider_key)
        cursor = stored_cursor

        # Override with modified_after for manual testing if provided
        # Note: modified_after is a FILTER, not a limit - it will still paginate through
        # all emails after that date. For full syncs, don't use modified_after at all.
        if modified_after:
            cursor = None
            logger.info(f"Using modified_after filter: {modified_after}")
        elif not stored_cursor:
            # First sync - sync all emails (no date filter)
            logger.info(f"First sync detected - syncing all emails")

        # Paginate through all Gmail records
        has_more = True
        while has_more:
            try:
                # Fetch page of records
                result = await nango_list_gmail_records(
                    http_client,
                    provider_key,
                    connection_id,
                    cursor=cursor,
                    limit=100,
                    modified_after=modified_after
                )

                records = result.get("records", [])
                next_cursor = result.get("next_cursor")

                logger.info(f"Fetched {len(records)} Gmail records (cursor: {cursor[:20] if cursor else 'none'}...)")

                # Process each record
                for record in records:
                    try:
                        # Normalize Gmail message
                        normalized = normalize_gmail_message(record, tenant_id)

                        # Ingest to Cortex Hybrid RAG system FIRST (to get episode_id)
                        cortex_result = await ingest_to_cortex(cortex_pipeline, normalized)

                        # Add episode_id to email if Cortex ingestion succeeded
                        if cortex_result and cortex_result.get('episode_id'):
                            normalized['episode_id'] = cortex_result['episode_id']

                        # Persist to Supabase (now with episode_id)
                        await persist_email_row(supabase, normalized)

                        # Optionally write to JSONL
                        await append_jsonl(normalized)

                        messages_synced += 1
                    except Exception as e:
                        error_msg = f"Error processing Gmail message: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                # Update cursor for next page
                if next_cursor:
                    cursor = next_cursor
                    # Save cursor after each page for incremental sync
                    await set_gmail_cursor(tenant_id, provider_key, cursor)
                else:
                    has_more = False

            except Exception as e:
                error_msg = f"Error fetching Gmail page: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                has_more = False

        logger.info(f"Gmail sync completed for tenant {tenant_id}: {messages_synced} messages")

        return {
            "status": "success" if not errors else "partial_success",
            "tenant_id": tenant_id,
            "messages_synced": messages_synced,
            "errors": errors
        }

    except Exception as e:
        error_msg = f"Fatal error during Gmail sync: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        return {
            "status": "error",
            "tenant_id": tenant_id,
            "messages_synced": messages_synced,
            "errors": errors
        }
