# One-Time Sync Locking Setup Guide

## Overview
This implements one-time historical sync with admin override capability. Users can sync once (1 year backfill), then the button is locked forever - unless admin enables override.

---

## STEP 1: Run SQL Migrations

### **Company Supabase** (Run for EACH company)

**Where:** Company Supabase SQL Editor
**File:** `migrations/010_one_time_sync_tracking.sql`

```sql
-- Add sync control columns
ALTER TABLE connections
ADD COLUMN IF NOT EXISTS can_manual_sync BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS initial_sync_completed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS initial_sync_started_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS initial_sync_completed_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS sync_lock_reason TEXT;

-- Create index
CREATE INDEX IF NOT EXISTS idx_connections_sync_lock
ON connections(tenant_id, provider_key, can_manual_sync);

-- Verify
SELECT column_name, data_type, column_default
FROM information_schema.columns
WHERE table_name = 'connections'
  AND column_name IN ('can_manual_sync', 'initial_sync_completed');
```

---

### **Master Supabase** (Run ONCE in master project)

**Where:** Master Supabase SQL Editor
**File:** `migrations/master/010_sync_permissions_override.sql`

```sql
-- Create admin override table
CREATE TABLE IF NOT EXISTS public.sync_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,

    can_manual_sync_override BOOLEAN DEFAULT NULL,
    override_reason TEXT,
    override_enabled_at TIMESTAMP WITH TIME ZONE,
    override_enabled_by TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(company_id)
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_sync_permissions_company
ON public.sync_permissions(company_id);

-- Enable RLS
ALTER TABLE public.sync_permissions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Admins can manage sync permissions"
ON public.sync_permissions FOR ALL TO authenticated
USING (true) WITH CHECK (true);

-- Verify
SELECT * FROM information_schema.columns
WHERE table_name = 'sync_permissions'
ORDER BY ordinal_position;
```

---

## STEP 2: Test the Flow

### User Flow (CEO)

**1. Connect Provider:**
```
CEO → /connections → Clicks "Connect Outlook"
→ OAuth flow completes
→ Connection saved to connections table
```

**2. Trigger Initial Sync:**
```bash
# Call new endpoint
POST /sync/initial/outlook
Headers: Authorization: Bearer <jwt_token>

# Response:
{
  "status": "started",
  "job_id": "uuid",
  "provider": "outlook",
  "backfill_days": 365,
  "locked": true,
  "message": "Historical sync started. Manual sync is now locked..."
}
```

**3. Verify Lock:**
```sql
-- Run in Company Supabase
SELECT
    provider_key,
    can_manual_sync,
    initial_sync_started_at,
    sync_lock_reason
FROM connections
WHERE tenant_id = '<user_id>';

-- Expected: can_manual_sync = FALSE
```

**4. Try to Sync Again:**
```bash
POST /sync/initial/outlook
# Should get 403 error: "Manual sync is locked..."
```

---

### Admin Override Flow

**1. Admin Enables Override:**
```sql
-- Run in MASTER Supabase
INSERT INTO sync_permissions (
    company_id,
    can_manual_sync_override,
    override_reason,
    override_enabled_by
)
VALUES (
    '<company_id>',
    TRUE,
    'Customer needs re-sync due to missing emails',
    'admin@highforce.com'
)
ON CONFLICT (company_id)
DO UPDATE SET
    can_manual_sync_override = TRUE,
    override_reason = 'Customer needs re-sync due to missing emails',
    override_enabled_at = NOW(),
    override_enabled_by = 'admin@highforce.com';
```

**2. User Can Now Sync:**
```bash
# User tries again
POST /sync/initial/outlook
# Success! Sync runs again
```

**3. Override Auto-Removed:**
```sql
-- Check in MASTER Supabase after sync
SELECT * FROM sync_permissions WHERE company_id = '<company_id>';
-- Expected: can_manual_sync_override = NULL (removed after use)
```

---

## STEP 3: Deploy Changes

### Backend

Changes committed in: `027004f`

**Files Changed:**
- ✅ `migrations/010_one_time_sync_tracking.sql` - Company DB schema
- ✅ `migrations/master/010_sync_permissions_override.sql` - Master DB schema
- ✅ `app/api/v1/routes/sync.py` - New endpoint + override logic

**Deploy:**
```bash
cd "/Users/nicolascodet/Desktop/CORTEX OFFICAL/CORTEX"
git push origin main

# Deploy to Render (auto-deploy should trigger)
# Or manually trigger deploy in Render dashboard
```

---

## STEP 4: Update Frontend (Next Steps)

### Add Initial Sync Modal

**File:** `connectorfrontend/app/connections/page.tsx`

**Add modal that shows:**
- ⚠️ "About to sync 1 year of data"
- ⏱ "Will take 4-8 hours"
- 📧 "You'll get email when complete"
- 🔒 "This is ONE-TIME, button will disappear"
- 📞 "Need more? Contact sales"

**Button logic:**
```tsx
{!connection.can_manual_sync ? (
  // Locked - show status
  <div className="text-green-600">
    ✓ Initial sync complete • Auto-sync enabled
  </div>
) : (
  // Can sync - show button
  <button onClick={() => showSyncModal(provider)}>
    Sync Now (1 Year - One Time)
  </button>
)}
```

---

## How It Works

### Flow Diagram

```
User clicks "Sync Now"
  ↓
Backend checks:
  1. Local: can_manual_sync in connections (company DB)
  2. Override: can_manual_sync_override in sync_permissions (master DB)
  ↓
Decision:
  - Local TRUE OR Override TRUE → Allow sync
  - Both FALSE → Block (403 error)
  ↓
If allowed:
  1. Set can_manual_sync = FALSE (LOCK)
  2. Start sync job (1 year backfill)
  3. If override was used, remove it (NULL)
  ↓
Button disappears forever (unless admin re-enables)
```

---

## Admin Dashboard (Future)

### Quick SQL Queries for Monitoring

**See all locked syncs:**
```sql
-- Run in Company Supabase
SELECT
    tenant_id,
    provider_key,
    can_manual_sync,
    initial_sync_completed,
    sync_lock_reason,
    initial_sync_started_at
FROM connections
WHERE can_manual_sync = FALSE
ORDER BY initial_sync_started_at DESC;
```

**See all active overrides:**
```sql
-- Run in Master Supabase
SELECT
    c.name AS company_name,
    sp.can_manual_sync_override,
    sp.override_reason,
    sp.override_enabled_by,
    sp.override_enabled_at
FROM sync_permissions sp
JOIN companies c ON c.id = sp.company_id
WHERE sp.can_manual_sync_override IS NOT NULL;
```

---

## Troubleshooting

### Problem: "Manual sync is locked" but user needs to re-sync

**Solution:** Admin enables override:
```sql
-- Master Supabase
INSERT INTO sync_permissions (company_id, can_manual_sync_override, override_reason, override_enabled_by)
VALUES ('<company_id>', TRUE, 'Support request #1234', 'admin@highforce.com')
ON CONFLICT (company_id) DO UPDATE SET can_manual_sync_override = TRUE;
```

### Problem: User synced but button didn't lock

**Solution:** Check if migration ran:
```sql
-- Company Supabase
SELECT column_name FROM information_schema.columns
WHERE table_name = 'connections' AND column_name = 'can_manual_sync';
-- Should return row, otherwise migration didn't run
```

### Problem: Override not working

**Solution:** Check master config:
```bash
# Verify environment variables
echo $COMPANY_ID
echo $MASTER_SUPABASE_URL
echo $MASTER_SUPABASE_SERVICE_KEY

# Check logs
# Should see: "🔓 Admin override for <company_id>: true"
```

---

## Summary

✅ **Company Supabase**: Tracks local sync lock (`can_manual_sync`)
✅ **Master Supabase**: Admin overrides (`sync_permissions`)
✅ **Backend**: Checks both, locks after first sync
✅ **Frontend**: TBD - needs modal + button logic
✅ **Admin**: Can unlock via SQL (UI coming later)

**Total Code:** ~250 lines
**Migration Time:** 5 min
**Deploy Time:** 10 min

Next: Build frontend modal and admin dashboard UI.
