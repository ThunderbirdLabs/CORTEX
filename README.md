# Nango Connection Service

Stripped-down FastAPI service for syncing Gmail and Outlook emails via Nango OAuth to Supabase.

## What This Does

- ✅ Nango OAuth (Microsoft Graph + Gmail)
- ✅ Full email sync to Supabase PostgreSQL
- ✅ Webhook-driven sync on Nango events
- ✅ Manual sync endpoints for testing
- ❌ NO embedding/vector storage
- ❌ NO LlamaIndex/Qdrant/OpenAI

**This is just the connection layer.** Your friend can import the sync functions and add their processing logic on top.

## Database Schema

Run `schema.sql` in your Supabase SQL editor to create:
- `connections` - Nango OAuth connections per tenant
- `user_cursors` - Microsoft Graph delta links for incremental sync
- `gmail_cursors` - Nango cursors for Gmail pagination
- `emails` - Normalized email storage with **full body content**

**Email format:**
```json
{
  "tenant_id": "user-uuid",
  "user_id": "user@example.com",
  "message_id": "unique-msg-id",
  "source": "gmail|outlook",
  "subject": "Email subject",
  "sender_name": "John Doe",
  "sender_address": "john@example.com",
  "to_addresses": ["recipient@example.com"],
  "received_datetime": "2024-01-01T00:00:00+00:00",
  "web_link": "https://...",
  "full_body": "Complete HTML or text email body",
  "change_key": "..."
}
```

## Environment Variables

Copy `.env.example` and fill in:
- `DATABASE_URL` - Supabase PostgreSQL connection string
- `SUPABASE_URL` + `SUPABASE_ANON_KEY` - For auth
- `NANGO_SECRET` - Your Nango API key
- `NANGO_PROVIDER_KEY_OUTLOOK` / `NANGO_PROVIDER_KEY_GMAIL` - Provider config keys
- `NANGO_CONNECTION_ID_OUTLOOK` / `NANGO_CONNECTION_ID_GMAIL` - After OAuth

## Deployment on Render

1. **Create Web Service** (not Background Worker)
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. **Environment**: Add all variables from `.env.example`
5. **Python Version**: 3.12.8 (from `runtime.txt`)

## Using in Your Friend's Code

Your friend can import the sync functions:

```python
from app import run_gmail_sync, run_tenant_sync, normalize_gmail_message

# In their processing pipeline:
async def process_emails(tenant_id, provider_key):
    # This syncs emails to Supabase
    result = await run_gmail_sync(tenant_id, provider_key)

    # Then query Supabase and do their processing
    emails = supabase.table("emails").select("*").eq("tenant_id", tenant_id).execute()

    for email in emails.data:
        # Their custom logic here
        full_body = email["full_body"]
        # ... extract entities, index to graph, etc
```

## API Endpoints

All routes require `Authorization: Bearer <supabase-jwt>` header (except webhooks):

- `GET /connect/start?provider=gmail|microsoft` - Initiate OAuth
- `POST /nango/oauth/callback` - OAuth callback handler
- `POST /nango/webhook` - Nango webhook receiver (no auth)
- `GET /sync/once` - Manual Outlook sync (for testing)
- `GET /sync/once/gmail` - Manual Gmail sync (for testing)
- `GET /health` - Health check
- `GET /status` - Connection status

## Nango Configuration

In your Nango dashboard:
1. Set up integrations for `outlook` and `google-mail`
2. Configure webhooks to point to `https://your-service.onrender.com/nango/webhook`
3. Copy provider keys to environment variables

## Testing

After deployment:

1. **Test OAuth**: `GET /connect/start?provider=gmail`
2. **Manual Sync**: `GET /sync/once/gmail?modified_after=2024-01-01T00:00:00Z`
3. **Check Supabase**: Query `emails` table for synced data

## Notes

- First sync defaults to last 30 days to save on processing
- Incremental sync uses cursors (delta links for Outlook, Nango cursors for Gmail)
- Emails are upserted by `(tenant_id, source, message_id)` to avoid duplicates
- No RLS in schema - add security policies in production!

## Merging with Your Friend's Code

Your friend's pipeline can either:
1. **Import functions** from this codebase and call them
2. **Deploy this as separate service** and query the shared Supabase database
3. **Add their logic** directly to `run_gmail_sync()` / `run_tenant_sync()` after email persistence
