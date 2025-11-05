"""
Database helper functions for email sync connector
Handles connections, cursors, and email persistence
"""
import logging
from datetime import datetime, timezone
from typing import Optional

import psycopg
from app.core.config import settings

logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE CONNECTION
# ============================================================================

def get_db_connection():
    """Get synchronous database connection.

    Note: Creates a new connection each time. For high-frequency calls,
    consider refactoring to use Supabase client instead.
    """
    return psycopg.connect(settings.database_url, autocommit=False)


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

async def save_connection(tenant_id: str, provider_key: str, connection_id: str):
    """Save or update connection in database."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO connections (tenant_id, provider_key, connection_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (tenant_id, provider_key)
                DO UPDATE SET connection_id = EXCLUDED.connection_id
                """,
                (tenant_id, provider_key, connection_id)
            )
        conn.commit()
        logger.info(f"Saved connection for tenant {tenant_id}")
    finally:
        conn.close()


async def get_connection(tenant_id: str, provider_key: str) -> Optional[str]:
    """Get connection_id for a tenant using Supabase client (avoids connection thrashing)."""
    from app.core.dependencies import supabase_client

    if not supabase_client:
        logger.warning("Supabase client not initialized, falling back to direct psycopg connection")
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT connection_id FROM connections WHERE tenant_id = %s AND provider_key = %s",
                    (tenant_id, provider_key)
                )
                row = cur.fetchone()
                return row[0] if row else None
        finally:
            conn.close()

    result = supabase_client.table("connections").select("connection_id").eq("tenant_id", tenant_id).eq("provider_key", provider_key).limit(1).execute()

    if result.data and len(result.data) > 0:
        return result.data[0]["connection_id"]
    return None


# ============================================================================
# OUTLOOK CURSOR MANAGEMENT
# ============================================================================

async def get_user_cursor(tenant_id: str, provider_key: str, user_id: str) -> Optional[str]:
    """Get delta link for a user."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT delta_link FROM user_cursors WHERE tenant_id = %s AND provider_key = %s AND user_id = %s",
                (tenant_id, provider_key, user_id)
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


async def save_user_cursor(
    tenant_id: str,
    provider_key: str,
    user_id: str,
    user_principal_name: str,
    delta_link: str
):
    """Save or update delta link for a user."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_cursors (tenant_id, provider_key, user_id, user_principal_name, delta_link, last_synced_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, provider_key, user_id)
                DO UPDATE SET
                    delta_link = EXCLUDED.delta_link,
                    last_synced_at = EXCLUDED.last_synced_at,
                    user_principal_name = EXCLUDED.user_principal_name
                """,
                (tenant_id, provider_key, user_id, user_principal_name, delta_link, datetime.now(timezone.utc))
            )
        conn.commit()
        logger.info(f"Saved cursor for user {user_id}")
    finally:
        conn.close()


# ============================================================================
# GMAIL CURSOR MANAGEMENT
# ============================================================================

async def get_gmail_cursor(tenant_id: str, provider_key: str) -> Optional[str]:
    """Get Nango cursor for Gmail sync."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT cursor FROM gmail_cursors WHERE tenant_id = %s AND provider_key = %s",
                (tenant_id, provider_key)
            )
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


async def set_gmail_cursor(tenant_id: str, provider_key: str, cursor: str):
    """Save or update Nango cursor for Gmail sync."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO gmail_cursors (tenant_id, provider_key, cursor, last_synced_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (tenant_id, provider_key)
                DO UPDATE SET
                    cursor = EXCLUDED.cursor,
                    last_synced_at = EXCLUDED.last_synced_at
                """,
                (tenant_id, provider_key, cursor, datetime.now(timezone.utc))
            )
        conn.commit()
        logger.info(f"Saved Gmail cursor for tenant {tenant_id}")
    finally:
        conn.close()
