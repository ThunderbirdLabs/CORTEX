"""
Microsoft Graph & Gmail Email Sync Connector
=============================================
Production-grade FastAPI service that syncs Microsoft Graph and Gmail emails via Nango OAuth.

RUN STEPS:
1. pip install -r requirements.txt
2. Create database with schema.sql
3. Set environment variables (see .env.example)
4. Run: uvicorn app:app --host 0.0.0.0 --port $PORT

ROUTES:
- POST /nango/oauth/callback - Saves tenant connection from Nango
- POST /nango/webhook - Triggers background sync on Nango events (Outlook or Gmail)
- GET /sync/once - Manual Outlook sync endpoint for testing
- GET /sync/once/gmail - Manual Gmail sync endpoint for testing
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
import jwt
import psycopg
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import create_client, Client

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

PORT = int(os.getenv("PORT", "8080"))
DATABASE_URL = os.getenv("DATABASE_URL")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
NANGO_SECRET = os.getenv("NANGO_SECRET")

# Outlook/Microsoft Graph configuration
NANGO_PROVIDER_KEY = os.getenv("NANGO_PROVIDER_KEY")  # Backward compatibility
NANGO_PROVIDER_KEY_OUTLOOK = os.getenv("NANGO_PROVIDER_KEY_OUTLOOK", os.getenv("NANGO_PROVIDER_KEY"))
NANGO_CONNECTION_ID = os.getenv("NANGO_CONNECTION_ID")  # Backward compatibility
NANGO_CONNECTION_ID_OUTLOOK = os.getenv("NANGO_CONNECTION_ID_OUTLOOK", os.getenv("NANGO_CONNECTION_ID"))
GRAPH_TENANT_ID = os.getenv("GRAPH_TENANT_ID", "")

# Gmail configuration
NANGO_PROVIDER_KEY_GMAIL = os.getenv("NANGO_PROVIDER_KEY_GMAIL")
NANGO_CONNECTION_ID_GMAIL = os.getenv("NANGO_CONNECTION_ID_GMAIL")

# Debug configuration
SAVE_JSONL = os.getenv("SAVE_JSONL", "false").lower() == "true"

# Validate required config
required_vars = [
    "DATABASE_URL", "SUPABASE_URL", "SUPABASE_ANON_KEY",
    "NANGO_SECRET"
]
for var in required_vars:
    if not os.getenv(var):
        raise RuntimeError(f"Missing required environment variable: {var}")

# Validate at least one provider is configured
if not NANGO_PROVIDER_KEY_OUTLOOK and not NANGO_PROVIDER_KEY_GMAIL:
    raise RuntimeError("At least one provider key must be set: NANGO_PROVIDER_KEY_OUTLOOK or NANGO_PROVIDER_KEY_GMAIL")

# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(title="Microsoft Graph & Gmail Email Sync Connector")

# CORS middleware - allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://connectorfrontend.vercel.app",
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

# HTTP client with retry configuration
http_client: Optional[httpx.AsyncClient] = None

# Security
security = HTTPBearer()


@app.on_event("startup")
async def startup_event():
    """Initialize HTTP client on startup."""
    global http_client

    # Initialize HTTP client
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
    )
    logger.info("HTTP client initialized")
    logger.info("FastAPI application started")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup HTTP client on shutdown."""
    if http_client:
        await http_client.aclose()
    logger.info("FastAPI application shutdown")


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class NangoOAuthCallback(BaseModel):
    """Nango OAuth callback payload."""
    tenantId: str
    providerConfigKey: str
    connectionId: str


class NangoWebhook(BaseModel):
    """
    Nango webhook payload for connection events.
    See: https://docs.nango.dev/integrate/guides/webhooks
    """
    type: str  # Event type: "auth", "sync", "forward"
    connectionId: str  # This is the tenant/user ID
    providerConfigKey: str  # Integration unique key
    environment: str  # "dev" or "prod"
    success: Optional[bool] = None  # For auth events
    model: Optional[str] = None  # For sync events
    responseResults: Optional[Dict[str, Any]] = None  # For sync events

    class Config:
        extra = "allow"  # Allow additional fields from Nango


class SyncResponse(BaseModel):
    """Response for manual sync endpoint."""
    status: str
    tenant_id: str
    users_synced: int
    messages_synced: int
    errors: List[str] = []


# ============================================================================
# AUTHENTICATION
# ============================================================================

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """
    Validate Supabase JWT and extract user UUID.

    Args:
        credentials: HTTP Bearer token from Authorization header

    Returns:
        User's UUID from Supabase auth (used as tenant_id)

    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials

    try:
        # Verify JWT using Supabase client
        response = supabase.auth.get_user(token)

        if not response or not response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication token"
            )

        user = response.user
        user_id = user.id

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="User ID not found in token"
            )

        logger.debug(f"Authenticated user: {user_id} ({user.email})")
        return user_id

    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_db_connection():
    """Get synchronous database connection."""
    return psycopg.connect(DATABASE_URL)


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
    """Get connection_id for a tenant."""
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


# ============================================================================
# RETRY LOGIC
# ============================================================================

async def retry_with_backoff(
    func,
    *args,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    **kwargs
):
    """
    Retry function with exponential backoff.
    Handles 429 rate limits and 5xx server errors.
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            last_exception = e
            if e.response.status_code == 429:
                # Respect Retry-After header
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        delay = delay * 2
                logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
            elif 500 <= e.response.status_code < 600:
                logger.warning(f"Server error {e.response.status_code}, retrying in {delay}s (attempt {attempt + 1}/{max_retries + 1})")
            else:
                # Don't retry on other status codes
                raise

            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                raise last_exception
        except Exception as e:
            logger.error(f"Unexpected error in retry_with_backoff: {e}")
            raise

    raise last_exception


# ============================================================================
# MICROSOFT GRAPH HELPERS
# ============================================================================

async def get_graph_token_via_nango(provider_key: str, connection_id: str) -> str:
    """
    Get Microsoft Graph access token via Nango.

    Args:
        provider_key: Nango provider configuration key
        connection_id: Nango connection ID

    Returns:
        Access token string

    Raises:
        HTTPException: If token retrieval fails
    """
    url = f"https://api.nango.dev/connection/{provider_key}/{connection_id}"
    headers = {"Authorization": f"Bearer {NANGO_SECRET}"}

    try:
        response = await http_client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data["credentials"]["access_token"]
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to get Nango token: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to retrieve access token from Nango")
    except Exception as e:
        logger.error(f"Error getting Nango token: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def list_all_users(access_token: str) -> List[Dict[str, str]]:
    """
    List all users in the tenant using Microsoft Graph.

    Args:
        access_token: Microsoft Graph access token

    Returns:
        List of user dictionaries with 'id' and 'userPrincipalName'
    """
    users = []
    url = "https://graph.microsoft.com/v1.0/users"
    headers = {"Authorization": f"Bearer {access_token}"}

    async def fetch_page(page_url: str):
        response = await http_client.get(page_url, headers=headers)
        response.raise_for_status()
        return response.json()

    try:
        while url:
            data = await retry_with_backoff(fetch_page, url)

            for user in data.get("value", []):
                users.append({
                    "id": user.get("id"),
                    "userPrincipalName": user.get("userPrincipalName")
                })

            # Handle pagination
            url = data.get("@odata.nextLink")

        logger.info(f"Retrieved {len(users)} users from Microsoft Graph")
        return users
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        raise


async def sync_user_mailbox(
    access_token: str,
    tenant_id: str,
    provider_key: str,
    user_id: str,
    user_principal_name: str
) -> List[Dict[str, Any]]:
    """
    Sync a user's mailbox using Microsoft Graph delta API.

    Args:
        access_token: Microsoft Graph access token
        tenant_id: Tenant identifier
        provider_key: Provider configuration key
        user_id: User ID
        user_principal_name: User principal name

    Returns:
        List of raw message dictionaries from Graph API
    """
    messages = []
    headers = {"Authorization": f"Bearer {access_token}"}

    # Check if we have an existing delta link
    delta_link = await get_user_cursor(tenant_id, provider_key, user_id)

    if delta_link:
        url = delta_link
        logger.info(f"Using existing delta link for user {user_principal_name}")
    else:
        # Request full body content via $select parameter
        url = f"https://graph.microsoft.com/v1.0/users/{user_id}/messages/delta?$select=id,subject,from,toRecipients,receivedDateTime,webLink,body,changeKey"
        logger.info(f"Starting initial sync for user {user_principal_name}")

    async def fetch_page(page_url: str):
        response = await http_client.get(page_url, headers=headers)
        response.raise_for_status()
        return response.json()

    try:
        new_delta_link = None

        while url:
            data = await retry_with_backoff(fetch_page, url)

            # Collect messages
            messages.extend(data.get("value", []))

            # Check for next page or delta link
            if "@odata.nextLink" in data:
                url = data["@odata.nextLink"]
            elif "@odata.deltaLink" in data:
                new_delta_link = data["@odata.deltaLink"]
                url = None  # Exit loop
            else:
                url = None

        # Save the new delta link for next sync
        if new_delta_link:
            await save_user_cursor(
                tenant_id,
                provider_key,
                user_id,
                user_principal_name,
                new_delta_link
            )

        logger.info(f"Synced {len(messages)} messages for user {user_principal_name}")
        return messages
    except Exception as e:
        logger.error(f"Error syncing mailbox for user {user_principal_name}: {e}")
        raise


def normalize_message(
    raw_message: Dict[str, Any],
    tenant_id: str,
    user_id: str,
    user_principal_name: str
) -> Dict[str, Any]:
    """
    Normalize a raw Microsoft Graph message into our schema.

    Args:
        raw_message: Raw message dictionary from Graph API
        tenant_id: Tenant identifier
        user_id: User ID
        user_principal_name: User principal name

    Returns:
        Normalized message dictionary
    """
    # Extract sender information
    sender = raw_message.get("from", {}).get("emailAddress", {})
    sender_name = sender.get("name", "")
    sender_address = sender.get("address", "")

    # Extract recipient addresses
    to_recipients = raw_message.get("toRecipients", [])
    to_addresses = [r.get("emailAddress", {}).get("address") for r in to_recipients if r.get("emailAddress")]

    # Parse received datetime
    received_dt = raw_message.get("receivedDateTime")
    if received_dt:
        # Graph returns ISO 8601 format
        try:
            received_datetime = datetime.fromisoformat(received_dt.replace("Z", "+00:00"))
        except Exception:
            received_datetime = None
    else:
        received_datetime = None

    # Extract full body content
    body_obj = raw_message.get("body", {})
    if isinstance(body_obj, dict):
        full_body = body_obj.get("content", "")
    else:
        full_body = ""

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "user_principal_name": user_principal_name,
        "message_id": raw_message.get("id"),
        "source": "outlook",
        "subject": raw_message.get("subject", ""),
        "sender_name": sender_name,
        "sender_address": sender_address,
        "to_addresses": to_addresses,
        "received_datetime": received_datetime.isoformat() if received_datetime else None,
        "web_link": raw_message.get("webLink", ""),
        "full_body": full_body,  # Full email body content (HTML or text)
        "change_key": raw_message.get("changeKey", "")
    }


# ============================================================================
# GMAIL HELPERS
# ============================================================================

async def nango_list_gmail_records(
    provider_key: str,
    connection_id: str,
    cursor: Optional[str] = None,
    limit: int = 100,
    modified_after: Optional[str] = None
) -> Dict[str, Any]:
    """
    List Gmail records from Nango unified API.

    Args:
        provider_key: Nango provider configuration key
        connection_id: Nango connection ID
        cursor: Optional cursor for pagination
        limit: Number of records per page
        modified_after: Optional ISO datetime to filter records

    Returns:
        Dictionary with 'records' list and optional 'next_cursor'

    Raises:
        HTTPException: If request fails
    """
    url = "https://api.nango.dev/v1/emails"
    params = {
        "limit": limit
    }

    if cursor:
        params["cursor"] = cursor
    if modified_after:
        params["modified_after"] = modified_after

    headers = {
        "Authorization": f"Bearer {NANGO_SECRET}",
        "Connection-Id": connection_id,
        "Provider-Config-Key": provider_key
    }

    async def fetch_records():
        response = await http_client.get(url, headers=headers, params=params)
        response.raise_for_status()

        # Log response body for debugging
        response_text = response.text
        logger.info(f"Nango records API response: {response_text[:500]}")

        # Handle empty response
        if not response_text or response_text.strip() == "":
            logger.warning("Nango returned empty response - sync may not have run yet")
            return {"records": [], "next_cursor": None}

        try:
            return response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Nango response as JSON: {e}")
            logger.error(f"Response text: {response_text}")
            return {"records": [], "next_cursor": None}

    try:
        data = await retry_with_backoff(fetch_records)
        return data
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to fetch Gmail records from Nango: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to fetch Gmail records from Nango")
    except Exception as e:
        logger.error(f"Error fetching Gmail records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def normalize_gmail_message(
    gmail_record: Dict[str, Any],
    tenant_id: str
) -> Dict[str, Any]:
    """
    Normalize a Gmail record from Nango into our schema.

    Nango GmailEmail model structure:
    {
        "id": "message_id",
        "sender": "sender@example.com",
        "recipients": ["recipient@example.com"],
        "date": "2024-01-01T00:00:00Z",
        "subject": "Subject line",
        "body": "Email body content",
        "attachments": [...],
        ...
    }

    Args:
        gmail_record: Raw Gmail record from Nango
        tenant_id: Tenant identifier

    Returns:
        Normalized message dictionary
    """
    # Extract sender information
    sender_raw = gmail_record.get("sender", "")
    # Gmail sender can be "Name <email@example.com>" or just "email@example.com"
    if "<" in sender_raw and ">" in sender_raw:
        # Parse "Name <email@example.com>"
        sender_name = sender_raw.split("<")[0].strip()
        sender_address = sender_raw.split("<")[1].split(">")[0].strip()
    else:
        sender_name = ""
        sender_address = sender_raw.strip()

    # Extract recipient addresses
    recipients = gmail_record.get("recipients", [])
    # Ensure recipients is always a list (Nango might send string)
    if isinstance(recipients, str):
        recipients = [recipients]
    elif not isinstance(recipients, list):
        recipients = []

    to_addresses = []
    for recipient in recipients:
        if isinstance(recipient, str):
            # Extract email from "Name <email>" format if present
            if "<" in recipient and ">" in recipient:
                email = recipient.split("<")[1].split(">")[0].strip()
            else:
                email = recipient.strip()
            to_addresses.append(email)

    # Parse date
    date_str = gmail_record.get("date")
    if date_str:
        try:
            received_datetime = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            received_datetime = None
    else:
        received_datetime = None

    # For Gmail, we'll use the sender's email as the user_id and user_principal_name
    # since Gmail doesn't have the same tenant/user structure as Outlook
    user_email = sender_address or "unknown@gmail.com"

    # Get full body (Nango provides full email body in 'body' field)
    full_body = gmail_record.get("body", "")

    return {
        "tenant_id": tenant_id,
        "user_id": user_email,  # Use email as user ID for Gmail
        "user_principal_name": user_email,
        "message_id": gmail_record.get("id"),
        "source": "gmail",
        "subject": gmail_record.get("subject", ""),
        "sender_name": sender_name,
        "sender_address": sender_address,
        "to_addresses": to_addresses,
        "received_datetime": received_datetime.isoformat() if received_datetime else None,
        "web_link": "",  # Gmail records from Nango may not include web link
        "full_body": full_body,  # Full email body content
        "change_key": ""  # Gmail doesn't use change keys
    }


async def persist_email_row(email: Dict[str, Any]):
    """
    Insert email row into Supabase.
    Uses upsert to handle duplicates gracefully based on (tenant_id, source, message_id).

    Args:
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


async def append_jsonl(email: Dict[str, Any]):
    """
    Append normalized email to JSONL file for debugging.

    Args:
        email: Normalized email dictionary
    """
    if not SAVE_JSONL:
        return

    try:
        with open("./outbox.jsonl", "a") as f:
            f.write(json.dumps(email) + "\n")
    except Exception as e:
        logger.error(f"Error writing to JSONL: {e}")


# ============================================================================
# CORE SYNC LOGIC
# ============================================================================

async def run_tenant_sync(tenant_id: str, provider_key: str) -> Dict[str, Any]:
    """
    Run a full sync for a tenant.

    Args:
        tenant_id: Tenant identifier
        provider_key: Provider configuration key

    Returns:
        Dictionary with sync statistics
    """
    logger.info(f"Starting sync for tenant {tenant_id}")

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
        access_token = await get_graph_token_via_nango(provider_key, connection_id)

        # List all users in tenant
        users = await list_all_users(access_token)

        # Sync each user's mailbox
        for user in users:
            user_id = user["id"]
            user_principal_name = user["userPrincipalName"]

            try:
                # Sync mailbox using delta API
                raw_messages = await sync_user_mailbox(
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
                        await persist_email_row(normalized)

                        # Optionally write to JSONL
                        await append_jsonl(normalized)

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

        logger.info(f"Sync completed for tenant {tenant_id}: {users_synced} users, {messages_synced} messages")

        return {
            "status": "success" if not errors else "partial_success",
            "tenant_id": tenant_id,
            "users_synced": users_synced,
            "messages_synced": messages_synced,
            "errors": errors
        }

    except Exception as e:
        error_msg = f"Fatal error during sync: {e}"
        logger.error(error_msg)
        errors.append(error_msg)
        return {
            "status": "error",
            "tenant_id": tenant_id,
            "users_synced": users_synced,
            "messages_synced": messages_synced,
            "errors": errors
        }


async def run_gmail_sync(
    tenant_id: str,
    provider_key: str,
    modified_after: Optional[str] = None
) -> Dict[str, Any]:
    """
    Run a full Gmail sync for a tenant using Nango unified API.

    Args:
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

        # If this is the first sync (no cursor) and no modified_after provided,
        # default to 7 days ago for testing (reduces initial email load)
        if not stored_cursor and not modified_after:
            seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
            # Format as ISO without microseconds, with Z timezone (Nango format)
            modified_after = seven_days_ago.strftime('%Y-%m-%dT%H:%M:%SZ')
            logger.info(f"First sync detected - defaulting to 7 days: {modified_after}")

        # Override with modified_after for manual testing if provided
        if modified_after:
            cursor = None
            logger.info(f"Using modified_after filter: {modified_after}")

        # Paginate through all Gmail records
        has_more = True
        while has_more:
            try:
                # Fetch page of records
                result = await nango_list_gmail_records(
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

                        # Persist to Supabase
                        await persist_email_row(normalized)

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


# ============================================================================
# FASTAPI ROUTES
# ============================================================================

@app.get("/connect/start")
async def connect_start(
    provider: str = Query(..., description="Provider name (microsoft or gmail)"),
    user_id: str = Depends(get_current_user_id)
):
    """
    Initiate OAuth flow by generating Nango OAuth URL with connect session token.
    Returns the authorization URL that frontend should redirect to.

    Requires: Authorization: Bearer <supabase-jwt> header
    """
    logger.info(f"OAuth start requested for provider {provider}, user {user_id}")

    # Map provider name to Nango integration ID
    integration_id = None
    if provider.lower() in ["microsoft", "outlook"]:
        if not NANGO_PROVIDER_KEY_OUTLOOK:
            raise HTTPException(status_code=400, detail="Microsoft/Outlook provider not configured")
        integration_id = "outlook"
    elif provider.lower() == "gmail":
        if not NANGO_PROVIDER_KEY_GMAIL:
            raise HTTPException(status_code=400, detail="Gmail provider not configured")
        integration_id = "google-mail"  # Actual Nango integration ID
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    # Generate connect session token from Nango
    try:
        session_response = await http_client.post(
            "https://api.nango.dev/connect/sessions",
            headers={"Authorization": f"Bearer {NANGO_SECRET}"},
            json={
                "end_user": {
                    "id": user_id,  # Use Supabase UUID
                    "email": f"{user_id}@app.internal",  # Placeholder email (not used)
                    "display_name": user_id[:8]  # First 8 chars of UUID
                },
                "allowed_integrations": [integration_id]
            }
        )
        session_response.raise_for_status()
        session_data = session_response.json()
        session_token = session_data["data"]["token"]  # Access nested data.token field

        logger.info(f"Generated connect session token for user {user_id} with integration {integration_id}")
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to create Nango session: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=500, detail="Failed to create OAuth session")
    except Exception as e:
        logger.error(f"Error creating Nango session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Generate Nango OAuth URL with session token and redirect
    # After OAuth, Nango will redirect user back to the frontend
    redirect_uri = "https://connectorfrontend.vercel.app"
    oauth_url = f"https://api.nango.dev/oauth/connect/{integration_id}?connect_session_token={session_token}&user_scope=&callback_url={redirect_uri}"

    logger.info(f"Generated OAuth URL for {provider}: {oauth_url}")

    return {
        "auth_url": oauth_url,
        "provider": provider,
        "tenant_id": user_id
    }


@app.post("/nango/oauth/callback")
async def nango_oauth_callback(payload: NangoOAuthCallback):
    """
    Handle Nango OAuth callback.
    Saves connection information for the tenant.
    """
    logger.info(f"Received OAuth callback for tenant {payload.tenantId}")

    try:
        await save_connection(
            payload.tenantId,
            payload.providerConfigKey,
            payload.connectionId
        )
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nango/webhook")
async def nango_webhook(payload: NangoWebhook, background_tasks: BackgroundTasks):
    """
    Handle Nango webhook.
    Triggers background sync for the tenant (Outlook or Gmail).

    Webhook is called when:
    - "auth" event: User completes OAuth (saves connection automatically)
    - "sync" event: Nango sync completes (triggers our sync to pull data)

    TODO: Verify Nango signature for security
    """
    nango_connection_id = payload.connectionId  # UUID from Nango

    logger.info(f"Received Nango webhook: type={payload.type}, connection={nango_connection_id}, provider={payload.providerConfigKey}")

    # Handle auth events - get end_user from Nango and save connection
    if payload.type == "auth" and payload.success:
        try:
            # Try to get end_user from the webhook payload first
            logger.info(f"Full webhook payload: {payload.model_dump_json()}")

            # Check if end_user is in the webhook (Nango might send it in some versions)
            if hasattr(payload, 'end_user') and payload.end_user:
                end_user_id = payload.end_user.get("id") if isinstance(payload.end_user, dict) else None
            else:
                end_user_id = None
                logger.error(f"No end_user in webhook payload for connection {nango_connection_id}")

            # If not in webhook, query Nango's connection metadata API
            if not end_user_id:
                logger.info(f"Attempting to fetch end_user from Nango connection metadata")

                # Use the metadata endpoint which should include end_user
                conn_url = f"https://api.nango.dev/connection/{nango_connection_id}?provider_config_key={payload.providerConfigKey}"
                headers = {"Authorization": f"Bearer {NANGO_SECRET}"}

                response = await http_client.get(conn_url, headers=headers)
                response.raise_for_status()
                conn_data = response.json()

                logger.info(f"Nango metadata response: {conn_data}")

                end_user_id = conn_data.get("end_user", {}).get("id") if isinstance(conn_data.get("end_user"), dict) else None

            if not end_user_id:
                logger.error(f"Failed to retrieve end_user for connection {nango_connection_id}")
                return {"status": "error", "message": "Missing end_user information"}

            logger.info(f"OAuth successful for user {end_user_id}, saving connection")

            # Save with user UUID as tenant_id and Nango UUID as connection_id
            await save_connection(end_user_id, payload.providerConfigKey, nango_connection_id)

            return {"status": "connection_saved", "user": end_user_id}

        except Exception as e:
            logger.error(f"Error handling auth webhook: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # Handle sync events or trigger manual sync on auth success
    # For sync events, we need to look up the user email from connection_id
    try:
        # Query Nango to get end_user for this connection
        conn_url = f"https://api.nango.dev/connection/{payload.providerConfigKey}/{nango_connection_id}"
        headers = {"Authorization": f"Bearer {NANGO_SECRET}"}

        response = await http_client.get(conn_url, headers=headers)
        response.raise_for_status()
        conn_data = response.json()

        tenant_id = conn_data.get("end_user", {}).get("id")

        if not tenant_id:
            logger.error(f"No end_user.id found for connection {nango_connection_id}")
            return {"status": "error", "message": "Missing end_user information"}

    except Exception as e:
        logger.error(f"Error fetching end_user from Nango: {e}")
        return {"status": "error", "message": str(e)}

    # Determine which sync function to use based on provider key
    if payload.providerConfigKey == NANGO_PROVIDER_KEY_GMAIL:
        # Gmail sync
        background_tasks.add_task(
            run_gmail_sync,
            tenant_id,
            payload.providerConfigKey
        )
        logger.info(f"Triggered Gmail sync for tenant {tenant_id}")
    else:
        # Outlook/Microsoft Graph sync (default)
        background_tasks.add_task(
            run_tenant_sync,
            tenant_id,
            payload.providerConfigKey
        )
        logger.info(f"Triggered Outlook sync for tenant {tenant_id}")

    # Return immediately
    return {"status": "accepted"}


@app.get("/sync/once", response_model=SyncResponse)
async def sync_once(user_id: str = Depends(get_current_user_id)):
    """
    Manual Outlook sync endpoint for testing.
    Runs sync in-process and returns results.

    Requires: Authorization: Bearer <supabase-jwt> header
    """
    logger.info(f"Manual Outlook sync requested for user {user_id}")

    try:
        # Use configured Outlook provider key
        result = await run_tenant_sync(user_id, NANGO_PROVIDER_KEY_OUTLOOK)

        return SyncResponse(
            status=result["status"],
            tenant_id=result["tenant_id"],
            users_synced=result["users_synced"],
            messages_synced=result["messages_synced"],
            errors=result["errors"]
        )
    except Exception as e:
        logger.error(f"Error in manual Outlook sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sync/once/gmail")
async def sync_once_gmail(
    user_id: str = Depends(get_current_user_id),
    modified_after: Optional[str] = Query(None, description="ISO datetime to filter records (e.g., 2024-01-01T00:00:00Z)")
):
    """
    Manual Gmail sync endpoint for testing.
    Runs sync in-process and returns results.
    Supports optional modified_after parameter for quick testing.

    Requires: Authorization: Bearer <supabase-jwt> header
    """
    logger.info(f"Manual Gmail sync requested for user {user_id}")
    if modified_after:
        logger.info(f"Using modified_after filter: {modified_after}")

    try:
        # Use configured Gmail provider key
        result = await run_gmail_sync(
            user_id,
            NANGO_PROVIDER_KEY_GMAIL,
            modified_after=modified_after
        )

        return {
            "status": result["status"],
            "tenant_id": result["tenant_id"],
            "messages_synced": result["messages_synced"],
            "errors": result["errors"]
        }
    except Exception as e:
        logger.error(f"Error in manual Gmail sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/status")
async def get_status(user_id: str = Depends(get_current_user_id)):
    """
    Get connection status for authenticated user.
    Returns info about configured providers and connections.

    Requires: Authorization: Bearer <supabase-jwt> header
    """
    try:
        # Check Outlook connection
        outlook_connection = await get_connection(user_id, NANGO_PROVIDER_KEY_OUTLOOK) if NANGO_PROVIDER_KEY_OUTLOOK else None

        # Check Gmail connection
        gmail_connection = await get_connection(user_id, NANGO_PROVIDER_KEY_GMAIL) if NANGO_PROVIDER_KEY_GMAIL else None

        return {
            "tenant_id": user_id,
            "providers": {
                "outlook": {
                    "configured": NANGO_PROVIDER_KEY_OUTLOOK is not None,
                    "connected": outlook_connection is not None,
                    "connection_id": outlook_connection if outlook_connection else None
                },
                "gmail": {
                    "configured": NANGO_PROVIDER_KEY_GMAIL is not None,
                    "connected": gmail_connection is not None,
                    "connection_id": gmail_connection if gmail_connection else None
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
        log_level="info"
    )
