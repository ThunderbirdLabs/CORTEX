# User ID + Company ID Tracking Implementation

**Status:** Phase 1 Complete ✅ | Phase 2 Migrations Ready ⏳

---

## What We Fixed

### The Core Problem
Previously, the system used `company_id` (tenant_id) as Nango's `endUserId`, meaning:
- ❌ All users in a company shared the same OAuth connections
- ❌ No way to track which user authorized what
- ❌ Multiple users couldn't have separate connections for the same provider
- ❌ No user-level attribution for data ingestion or actions

### The Solution
Now the system properly tracks **BOTH** `user_id` and `company_id` everywhere:
- ✅ OAuth connections are per-user (user_id + company_id + provider)
- ✅ Full attribution: know who connected, when, which email
- ✅ Comprehensive logging for debugging
- ✅ Migrations ready for document and sync job tracking

---

## Phase 1: OAuth Connection Attribution ✅ COMPLETE

### Changes Made

#### 1. Database Schema (Migration 012)
**File:** `migrations/company/012_add_user_tracking_to_connections.sql`

Added to `connections` table:
- `user_id TEXT` - User ID from Master Supabase
- `user_email TEXT` - User's email (denormalized for convenience)
- `connected_at TIMESTAMPTZ` - When connection was created

Changed constraint:
- **OLD:** `UNIQUE(tenant_id, provider_key)` - One connection per company per provider
- **NEW:** `UNIQUE(tenant_id, provider_key, user_id)` - One connection per **user** per provider

Indexes added:
- `idx_connections_user` ON `connections(user_id)`
- `idx_connections_tenant_user` ON `connections(tenant_id, user_id)`

#### 2. Database Functions
**File:** `app/services/sync/database.py`

**`save_connection()` function:**
- Now accepts `user_id` and `user_email` parameters
- Saves connections with full user attribution
- **LOGGING:** `[SAVE_CONNECTION]` tag with detailed error tracking

**`get_connection()` function:**
- Now accepts optional `user_id` parameter
- Can query user-specific connections
- Backward compatible (user_id optional during transition)

#### 3. OAuth Flow
**File:** `app/api/v1/routes/oauth.py`

**`/connect/start` endpoint:**
- Changed from `get_current_user_id` → `get_current_user_context`
- Extracts **BOTH** `user_id` and `company_id`
- Passes actual `user_id` to Nango as `endUserId` (NOT company_id!)
- Includes `company_id` in `organization_id` metadata
- **LOGGING:** `[OAUTH_START]` tag with step-by-step tracking

**`/connect/reconnect` endpoint:**
- Also updated to use `get_current_user_context`
- Properly tracks user_id for reconnections

#### 4. Webhook Handler
**File:** `app/api/v1/routes/webhook.py`

**Auth webhook:**
- Extracts `user_id`, `user_email`, and `company_id` from Nango's `endUser`
- Falls back to Nango API if not in payload
- Validates both IDs before saving
- Passes all three to `save_connection()`
- **LOGGING:** `[WEBHOOK_AUTH]` tag with comprehensive tracking

### Comprehensive Error Tracking

All critical functions now log:
- ✅ **Entry:** What parameters were received
- ✅ **Progress:** Each step of the process
- ✅ **Success:** Confirmation with all IDs
- ❌ **Errors:** Detailed context, error type, full traceback

**Log Tags for Grepping:**
```bash
# OAuth flow initiation
grep "\[OAUTH_START\]" logs

# Database connection saves
grep "\[SAVE_CONNECTION\]" logs

# Webhook processing
grep "\[WEBHOOK_AUTH\]" logs

# All errors
grep "❌" logs

# All successes
grep "✅" logs
```

### How to Run Migration 012

**For each company's Supabase database:**

1. Go to Supabase SQL Editor
2. Run: `migrations/company/012_add_user_tracking_to_connections.sql`
3. Verify columns added:
   ```sql
   SELECT column_name, data_type
   FROM information_schema.columns
   WHERE table_name = 'connections'
     AND column_name IN ('user_id', 'user_email', 'connected_at');
   ```

**⚠️ IMPORTANT:** Existing connections will have NULL `user_id` and need re-authorization.
Users must reconnect their OAuth accounts after this migration.

---

## Phase 2: Data Attribution (Migrations Ready ⏳)

### Migration 013: Document Ingestion Attribution
**File:** `migrations/company/013_add_ingestion_attribution.sql`

Adds to `documents` table:
- `ingested_by_user_id TEXT` - Who ingested this document
- `ingested_by_user_email TEXT` - User's email
- `ingestion_method TEXT` - How: oauth_sync, manual_upload, api, webhook

**Benefits:**
- ✅ Accountability: Know who brought data into system
- ✅ User quotas: Limit uploads per user
- ✅ Compliance: Data provenance tracking
- ✅ Security: Audit trail for all ingestion

**Next Steps:**
1. Run migration on each company database
2. Update document insertion code to pass `user_id` and `ingestion_method`
3. Update sync orchestration to include user attribution

### Migration 014: Company Scoping for Sync Jobs
**File:** `migrations/company/014_add_company_to_sync_jobs.sql`

Adds to `sync_jobs` table:
- `tenant_id TEXT` - Company ID (was missing!)

**Benefits:**
- ✅ Efficient company-wide queries
- ✅ Proper multi-tenant isolation
- ✅ Track BOTH who triggered AND which company

**Next Steps:**
1. Run migration on each company database
2. Update sync job creation to include `tenant_id`
3. Backfill `tenant_id` for existing jobs (if deployment knows its company_id)

---

## Phase 3: Cursor Tracking Tables (TODO)

### Need to Add User/Company IDs to:

#### 1. `nango_sync_cursors` table
Currently has:
- provider, sync_name, connection_id, last_cursor

**Should add:**
- `tenant_id TEXT` - Company ID
- `user_id TEXT` - Which user's sync this is
- Indexes on tenant_id

#### 2. `gmail_cursors` table
Currently has:
- tenant_id, provider_key, cursor (ONE per company)

**Should add:**
- `user_id TEXT` - Support multiple users per company
- Change UNIQUE constraint to include user_id

---

## Phase 4: Endpoint Standardization (TODO)

### Current State
- ❌ **~40 endpoints** still use `get_current_user_id` (returns company_id only)
- ✅ **~9 endpoints** use `get_current_user_context` (returns both IDs)

### What Needs Updating

**Pattern to replace:**
```python
# OLD - Only gets company_id
@router.get("/some-endpoint")
async def some_endpoint(
    user_id: str = Depends(get_current_user_id)  # Actually company_id!
):
    # user_id is actually company_id
    # No way to know which user made the request
```

**New pattern:**
```python
# NEW - Gets both user_id and company_id
@router.get("/some-endpoint")
async def some_endpoint(
    user_context: dict = Depends(get_current_user_context)
):
    user_id = user_context["user_id"]        # Actual user
    company_id = user_context["company_id"]  # Company

    # Use company_id for data filtering (maintains current behavior)
    # Use user_id for action attribution (new)
```

**Affected Endpoints:**
- `/api/v1/oauth/*` - OAuth status (already fixed for /connect/start)
- `/api/v1/integrations/*` - Integration data
- `/api/v1/insights/*` - Insights queries
- `/api/v1/dashboard/*` - Dashboard data
- `/api/v1/reports/*` - Report generation
- `/api/v1/analytics/*` - Analytics
- `/api/v1/search` - Search queries
- `/api/v1/intelligence/*` - Intelligence
- `/api/v1/upload/*` - File uploads
- `/api/v1/emails/*` - Email listing
- `/api/v1/alerts/*` - Alert management
- `/api/v1/sync/*` - Sync operations

---

## Testing Checklist

### Multi-User OAuth Testing
- [ ] User A connects Gmail → Creates connection with user_id=A
- [ ] User B (same company) connects Gmail → Creates separate connection with user_id=B
- [ ] Both users can sync independently
- [ ] Connections don't interfere with each other
- [ ] Cursors are properly isolated

### Data Isolation Testing
- [ ] User from Company A can't access Company B's data
- [ ] Users from same company see shared documents
- [ ] User-specific resources (chats, connections) are properly scoped
- [ ] Audit logs show correct user_id + company_id

### Attribution Testing
- [ ] OAuth connections show who connected (user_id, email)
- [ ] Documents show who ingested them (after Phase 2)
- [ ] Sync jobs show who triggered them
- [ ] Audit logs track all actions with user_id

### Error Scenarios
- [ ] Missing user_id → Detailed error logged
- [ ] Missing company_id → Validation fails gracefully
- [ ] Nango API down → Fallback logic works
- [ ] Database errors → Transaction rolled back, logged
- [ ] All errors searchable via log tags

---

## Deployment Instructions

### 1. Deploy CORTEX Backend
```bash
git pull origin main
# Render auto-deploys or trigger manual deployment
```

### 2. Run Migrations (Per Company)

**For EACH company's Supabase:**

```sql
-- Migration 012 (OAuth user tracking) - REQUIRED
\i migrations/company/012_add_user_tracking_to_connections.sql

-- Migration 013 (Document attribution) - OPTIONAL for now
\i migrations/company/013_add_ingestion_attribution.sql

-- Migration 014 (Sync job company scoping) - OPTIONAL for now
\i migrations/company/014_add_company_to_sync_jobs.sql
```

### 3. Notify Users
After migration 012, users must re-authorize OAuth:
- Existing connections have NULL user_id
- OAuth flow now requires proper user_id
- Users will need to click "Connect" again

### 4. Monitor Logs
Watch for these patterns:
```bash
# Successful OAuth flows
grep "\[OAUTH_START\].*SUCCESS" logs

# Successful webhook processing
grep "\[WEBHOOK_AUTH\].*SUCCESS" logs

# Any errors
grep "❌" logs
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ BEFORE: Company-only tracking                               │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ User → JWT → get_current_user_id() → tenant_id (company)   │
│                                                             │
│ ❌ No way to know which user!                              │
│ ❌ All users share connections                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ AFTER: User + Company tracking                              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ User → JWT → get_current_user_context() → {                │
│   user_id: "uuid-123",         # Actual user               │
│   company_id: "uuid-abc"       # Company                   │
│ }                                                           │
│                                                             │
│ ✅ Full attribution                                         │
│ ✅ Per-user connections                                     │
│ ✅ Audit trail                                              │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ OAuth Flow (Corrected)                                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ 1. User clicks "Connect Gmail"                             │
│ 2. CORTEX → get_current_user_context()                     │
│    ├─ user_id: "abc-123"                                   │
│    └─ company_id: "xyz-789"                                │
│ 3. CORTEX → Nango Connect Session:                         │
│    ├─ endUser.id: "abc-123"           ← USER ID!          │
│    └─ endUser.organization_id: "xyz-789"  ← Company       │
│ 4. User completes OAuth with Google/Microsoft              │
│ 5. Nango → Webhook with endUser data                       │
│ 6. CORTEX extracts:                                         │
│    ├─ user_id from endUser.id                              │
│    ├─ company_id from endUser.organization_id              │
│    └─ user_email from endUser.email                        │
│ 7. save_connection(company_id, provider, conn_id,          │
│                     user_id, user_email)                   │
│                                                             │
│ Result: connections table has ALL the data!                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary

**What's Done:**
- ✅ OAuth connections track user_id + company_id
- ✅ Comprehensive error logging everywhere
- ✅ Migrations ready for Phase 2
- ✅ Database functions updated
- ✅ Webhook handler fixed
- ✅ Nango integration corrected

**What's Next:**
1. Run migration 012 on all company databases
2. Test multi-user OAuth scenarios
3. Run migrations 013 & 014 when ready
4. Update document/sync job creation code
5. Standardize remaining endpoints (Phase 4)

**Impact:**
- 🔒 **Security:** Proper user-level authorization
- 📊 **Compliance:** Full audit trail
- 👥 **Multi-user:** Multiple users per company supported
- 🐛 **Debugging:** Comprehensive logging for troubleshooting
- 🎯 **Attribution:** Know who did what, when

---

## Support

If you encounter errors:
1. Check logs with `[TAG]` prefixes
2. Look for ❌ emoji in logs
3. All errors include full context + traceback
4. Each phase is independently deployable

**Log Tags:**
- `[OAUTH_START]` - OAuth flow
- `[SAVE_CONNECTION]` - Database saves
- `[WEBHOOK_AUTH]` - Webhook processing

Good luck! 🚀
