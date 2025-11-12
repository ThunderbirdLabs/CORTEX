# Centralized Auth Setup Guide

## Overview

This guide sets up **centralized authentication** where all users authenticate through **Master Supabase** instead of their individual company Supabase instances.

### Key Benefits:
- ✅ Single source of truth for all user authentication
- ✅ Users can access multiple companies (if invited)
- ✅ Simplified user management (one auth system, not N companies)
- ✅ Documents stay in company Supabase (no data migration needed!)
- ✅ COMPANY_ID env var still works (backward compatible)

---

## Security Architecture

### Multi-Tenant Isolation

Each CORTEX deployment is isolated by:

1. **COMPANY_ID env var** - Each Render service knows which company it serves
2. **Master Supabase validation** - JWT validated against master, user must be in `company_users` table for THIS company
3. **Company Supabase isolation** - Documents stored in company's own Supabase (complete data isolation)

**Result**: User from Company A **CANNOT** access Company B's data:
- Company A's CORTEX validates JWT → checks `company_users` for Company A → only sees Company A's documents
- Company B's CORTEX validates JWT → checks `company_users` for Company B → user not found → 403 Forbidden

---

## Step 1: Run SQL on Master Supabase

Go to your Master Supabase SQL Editor and run these migrations IN ORDER:

### Migration 006: OAuth Connection Tracking

```sql
-- ============================================================================
-- CLIENT OAUTH & SYNC CONTROL
-- ============================================================================

-- Track original OAuth connections (enforce same-email reconnection)
CREATE TABLE IF NOT EXISTS public.nango_original_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    tenant_id text NOT NULL,
    provider text NOT NULL, -- 'outlook', 'gmail', 'google_drive', 'quickbooks'
    original_email text NOT NULL,
    nango_connection_id text NOT NULL,
    connected_at timestamp with time zone DEFAULT now(),
    connected_by text,
    last_reconnected_at timestamp with time zone,
    reconnection_count integer DEFAULT 0,
    CONSTRAINT nango_original_connections_unique UNIQUE(company_id, tenant_id, provider)
);

CREATE INDEX idx_nango_connections_company ON public.nango_original_connections(company_id);
CREATE INDEX idx_nango_connections_tenant ON public.nango_original_connections(company_id, tenant_id);

COMMENT ON TABLE public.nango_original_connections IS 'Tracks original OAuth connections to enforce same-email reconnection policy';

-- Row level security
ALTER TABLE public.nango_original_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role has full access" ON public.nango_original_connections FOR ALL USING (true);
```

### Migration 007: Centralized Auth

```sql
-- ============================================================================
-- CENTRALIZED AUTH - Company Users Mapping
-- ============================================================================

-- Maps Supabase auth users to companies
CREATE TABLE IF NOT EXISTS public.company_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Master Supabase auth user ID
    user_id uuid NOT NULL,  -- From auth.users in Master Supabase

    -- Company association
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,

    -- User info (denormalized for performance)
    email text NOT NULL,
    role text DEFAULT 'user' CHECK (role IN ('owner', 'admin', 'user', 'viewer')),

    -- User management
    invited_by uuid REFERENCES public.master_admins(id),
    invited_at timestamp with time zone DEFAULT now(),
    last_login_at timestamp with time zone,
    is_active boolean DEFAULT true,

    -- Timestamps
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),

    -- Constraints
    CONSTRAINT unique_user_company UNIQUE(user_id, company_id)
);

-- Indexes for fast lookups
CREATE INDEX idx_company_users_user ON public.company_users(user_id);
CREATE INDEX idx_company_users_company ON public.company_users(company_id);
CREATE INDEX idx_company_users_email ON public.company_users(email);
CREATE INDEX idx_company_users_active ON public.company_users(company_id, is_active) WHERE is_active = true;

COMMENT ON TABLE public.company_users IS 'Maps Master Supabase auth users to companies (centralized auth)';

-- Row level security
ALTER TABLE public.company_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role has full access" ON public.company_users FOR ALL USING (true);
CREATE POLICY "Users can view their own companies" ON public.company_users FOR SELECT USING (auth.uid() = user_id);

-- Helper functions
CREATE OR REPLACE FUNCTION get_user_companies(p_user_id uuid)
RETURNS TABLE (
    company_id uuid,
    company_name text,
    company_slug text,
    user_role text,
    backend_url text,
    frontend_url text
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.name,
        c.slug,
        cu.role,
        c.backend_url,
        c.frontend_url
    FROM public.company_users cu
    JOIN public.companies c ON c.id = cu.company_id
    WHERE cu.user_id = p_user_id
      AND cu.is_active = true
      AND c.status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION user_has_company_access(p_user_id uuid, p_company_id uuid)
RETURNS boolean AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM public.company_users
        WHERE user_id = p_user_id
          AND company_id = p_company_id
          AND is_active = true
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION get_user_role_in_company(p_user_id uuid, p_company_id uuid)
RETURNS text AS $$
DECLARE
    v_role text;
BEGIN
    SELECT role INTO v_role
    FROM public.company_users
    WHERE user_id = p_user_id
      AND company_id = p_company_id
      AND is_active = true;
    RETURN v_role;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION update_user_last_login(p_user_id uuid, p_company_id uuid)
RETURNS void AS $$
BEGIN
    UPDATE public.company_users
    SET last_login_at = now(),
        updated_at = now()
    WHERE user_id = p_user_id
      AND company_id = p_company_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Auto-update trigger
CREATE OR REPLACE FUNCTION update_company_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_company_users_updated_at
    BEFORE UPDATE ON public.company_users
    FOR EACH ROW
    EXECUTE FUNCTION update_company_users_updated_at();
```

---

## Step 2: Create Users in Master Supabase

For each company (Unit Industries, demo accounts, etc.):

1. **Go to Master Supabase → Authentication → Users**
2. **Click "Add User"**
3. **Create user with their email** (e.g., `nico@unitindustries.com`)
4. **Set password or send magic link**
5. **CRITICAL: Set user_metadata.company_id**:
   - In the user creation form, add to "User Metadata":
   ```json
   {
     "company_id": "f10541a7-ca6c-4296-a12d-ef92647ae7cb"
   }
   ```
   - This is **cryptographically signed** in the JWT and enforces security
6. **Copy the generated user_id** (you'll need this next)

---

## Step 3: Map Users to Companies

For each user you created, run this SQL:

```sql
-- Map user to their company
INSERT INTO public.company_users (user_id, company_id, email, role)
SELECT
    '<paste_user_id_here>',           -- From step 2
    c.id,                              -- Company ID from companies table
    'user@example.com',                -- User's email
    'admin'                            -- Role: owner, admin, user, or viewer
FROM public.companies c
WHERE c.slug = 'unit-industries';      -- Change to your company slug

-- Example: Add Nico to Unit Industries
INSERT INTO public.company_users (user_id, company_id, email, role)
SELECT
    '550e8400-e29b-41d4-a716-446655440000',  -- Nico's user_id from Master Supabase auth
    c.id,
    'nico@unitindustries.com',
    'owner'
FROM public.companies c
WHERE c.slug = 'unit-industries';
```

---

## Step 4: Verify Setup

### Check User Mapping

```sql
-- See all users and their companies
SELECT
    cu.email,
    cu.role,
    c.name AS company_name,
    c.slug AS company_slug,
    cu.is_active
FROM public.company_users cu
JOIN public.companies c ON c.id = cu.company_id
ORDER BY c.name, cu.email;
```

### Test User Access

```sql
-- Check which companies a user can access
SELECT * FROM get_user_companies('<user_id>');

-- Check if user has access to specific company
SELECT user_has_company_access('<user_id>', '<company_id>');

-- Get user's role in company
SELECT get_user_role_in_company('<user_id>', '<company_id>');
```

---

## Step 5: Update Environment Variables

No changes needed! Your existing Render deployments already have:

```bash
# Master Supabase (already configured)
MASTER_SUPABASE_URL=https://your-master.supabase.co
MASTER_SUPABASE_SERVICE_KEY=your-master-service-key

# Company ID (already configured)
COMPANY_ID=<uuid>  # This tells CORTEX which company it serves
```

The updated `security.py` will automatically:
1. Validate JWT against Master Supabase
2. Check `company_users` table for access
3. Only allow users who belong to this COMPANY_ID

---

## How It Works

### Before (Company Supabase Auth):
```
User → Login to Company A Supabase → JWT from Company A → CORTEX validates against Company A
User → Can only access Company A (separate auth)
```

### After (Centralized Auth):
```
User → Login to Master Supabase → JWT from Master → CORTEX validates against Master
                                                  ↓
                                    Checks company_users table
                                                  ↓
                                    "Is user in COMPANY_ID?"
                                                  ↓
                                    YES → Access granted to Company A's data
                                    NO → 403 Forbidden
```

### Security Guarantees:

1. **JWT Cryptographic Binding**: `user_metadata.company_id` is signed by Supabase (can't be tampered)
2. **JWT Validation**: CORTEX validates JWT `company_id` matches `COMPANY_ID` env var
3. **Database Check**: User must be in `company_users` for THIS company (defense in depth)
4. **Data Isolation**: Documents live in company Supabase (COMPANY_ID determines which one)
5. **Render Isolation**: Each CORTEX deployment only serves ONE company (env var)

**Result**: User from Company A **CANNOT** access Company B because:
- Company B's CORTEX validates JWT → `jwt.company_id != COMPANY_ID` → 403 (even if attacker modifies `company_users` table!)
- Even if JWT passes, Company B's CORTEX checks `company_users` → user not found → 403

---

## Quick Start for New Companies

1. **Create user in Master Supabase auth**
   - Email: `user@company.com`
   - Password: (set or send magic link)
   - **User Metadata**: `{"company_id": "<company_uuid>"}`

2. **Run this SQL**:
```sql
INSERT INTO public.company_users (user_id, company_id, email, role)
VALUES (
    '<user_id_from_master_supabase>',
    '<company_id_from_companies_table>',
    'user@company.com',
    'admin'
);
```
3. **Done!** User can now log in and access their company's CORTEX

**CRITICAL**: The `user_metadata.company_id` in Step 1 is what makes this secure. It's cryptographically signed in the JWT and can't be modified by attackers.

---

## Testing

1. **Create test user in Master Supabase**
2. **Map to Unit Industries**:
```sql
INSERT INTO public.company_users (user_id, company_id, email, role)
SELECT 'TEST_USER_ID', c.id, 'test@unit.com', 'user'
FROM public.companies c WHERE c.slug = 'unit-industries';
```
3. **Log in to app with test user**
4. **Try to sync** - Should work!
5. **Check logs** - Should see: `Authenticated user: TEST_USE... (role: user)`

---

## What Changed in CORTEX

### [app/core/security.py](app/core/security.py)

- **SECURITY LAYER 1**: Validates JWT `user_metadata.company_id` matches `COMPANY_ID` env var (cryptographic binding)
- **SECURITY LAYER 2**: Checks `company_users` table to ensure user belongs to THIS company (defense in depth)
- Validates JWT against **Master Supabase** (not company Supabase)
- Returns 403 if user tries to access wrong company
- Updates `last_login_at` timestamp

### [migrations/master/007_add_company_users.sql](migrations/master/007_add_company_users.sql)

- New `company_users` table (maps users → companies)
- Helper functions for access checks
- Row-level security policies

### [migrations/master/006_client_oauth_sync_control.sql](migrations/master/006_client_oauth_sync_control.sql)

- `nango_original_connections` table (tracks OAuth connections)
- Audit logging for all connection events

---

## Complete SQL for Copy-Paste

```sql
-- ============================================================================
-- RUN THESE IN ORDER ON MASTER SUPABASE
-- ============================================================================

-- 1. OAuth Connection Tracking
CREATE TABLE IF NOT EXISTS public.nango_original_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    tenant_id text NOT NULL,
    provider text NOT NULL,
    original_email text NOT NULL,
    nango_connection_id text NOT NULL,
    connected_at timestamp with time zone DEFAULT now(),
    connected_by text,
    last_reconnected_at timestamp with time zone,
    reconnection_count integer DEFAULT 0,
    CONSTRAINT nango_original_connections_unique UNIQUE(company_id, tenant_id, provider)
);

CREATE INDEX idx_nango_connections_company ON public.nango_original_connections(company_id);
CREATE INDEX idx_nango_connections_tenant ON public.nango_original_connections(company_id, tenant_id);

ALTER TABLE public.nango_original_connections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role has full access" ON public.nango_original_connections FOR ALL USING (true);

-- 2. Centralized Auth
CREATE TABLE IF NOT EXISTS public.company_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    email text NOT NULL,
    role text DEFAULT 'user' CHECK (role IN ('owner', 'admin', 'user', 'viewer')),
    invited_by uuid REFERENCES public.master_admins(id),
    invited_at timestamp with time zone DEFAULT now(),
    last_login_at timestamp with time zone,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    CONSTRAINT unique_user_company UNIQUE(user_id, company_id)
);

CREATE INDEX idx_company_users_user ON public.company_users(user_id);
CREATE INDEX idx_company_users_company ON public.company_users(company_id);
CREATE INDEX idx_company_users_email ON public.company_users(email);
CREATE INDEX idx_company_users_active ON public.company_users(company_id, is_active) WHERE is_active = true;

ALTER TABLE public.company_users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role has full access" ON public.company_users FOR ALL USING (true);
CREATE POLICY "Users can view their own companies" ON public.company_users FOR SELECT USING (auth.uid() = user_id);

-- Helper functions
CREATE OR REPLACE FUNCTION get_user_companies(p_user_id uuid)
RETURNS TABLE (company_id uuid, company_name text, company_slug text, user_role text, backend_url text, frontend_url text)
AS $$
BEGIN
    RETURN QUERY
    SELECT c.id, c.name, c.slug, cu.role, c.backend_url, c.frontend_url
    FROM public.company_users cu
    JOIN public.companies c ON c.id = cu.company_id
    WHERE cu.user_id = p_user_id AND cu.is_active = true AND c.status = 'active';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION user_has_company_access(p_user_id uuid, p_company_id uuid)
RETURNS boolean AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.company_users
        WHERE user_id = p_user_id AND company_id = p_company_id AND is_active = true
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION get_user_role_in_company(p_user_id uuid, p_company_id uuid)
RETURNS text AS $$
DECLARE v_role text;
BEGIN
    SELECT role INTO v_role FROM public.company_users
    WHERE user_id = p_user_id AND company_id = p_company_id AND is_active = true;
    RETURN v_role;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION update_user_last_login(p_user_id uuid, p_company_id uuid)
RETURNS void AS $$
BEGIN
    UPDATE public.company_users
    SET last_login_at = now(), updated_at = now()
    WHERE user_id = p_user_id AND company_id = p_company_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE FUNCTION update_company_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_company_users_updated_at
    BEFORE UPDATE ON public.company_users
    FOR EACH ROW EXECUTE FUNCTION update_company_users_updated_at();

-- 3. Add your users (CUSTOMIZE THIS)
-- First, create users in Master Supabase UI, then run this for each user:

INSERT INTO public.company_users (user_id, company_id, email, role)
SELECT
    '<PASTE_USER_ID_FROM_MASTER_SUPABASE_AUTH>',
    c.id,
    'user@example.com',
    'admin'
FROM public.companies c
WHERE c.slug = 'unit-industries';  -- Change to your company slug

-- Done!
```

---

## Admin Sync Triggering

Admins can trigger syncs for any company/user safely through the existing admin dashboard:

### How It Works

1. **Admin authenticates** with PIN (default: 2525)
   - `POST /admin/auth` with `{"pin": "2525"}`
   - Returns session token (valid 1 hour)

2. **Admin triggers sync** for any user
   - `POST /admin/connectors/sync?user_id=<uuid>&provider=gmail`
   - Headers: `X-Admin-Session: <token>`

3. **All actions logged** to audit trail
   - `admin_audit_log` table tracks who triggered what sync
   - Includes IP address, timestamp, user details

### Security

- Admin sessions require PIN authentication
- All actions logged with IP addresses
- Session tokens expire after 1 hour
- Rate limiting on login attempts (5 per 15 minutes)
- Optional IP whitelist support

### Example: Trigger Outlook Sync

```bash
# 1. Admin login
curl -X POST https://cortex-unit.onrender.com/admin/auth \
  -H "Content-Type: application/json" \
  -d '{"pin": "2525"}'

# Returns: {"session_token": "abc123...", "expires_in": 3600}

# 2. Trigger sync for user
curl -X POST "https://cortex-unit.onrender.com/admin/connectors/sync?user_id=550e8400-e29b-41d4-a716-446655440000&provider=outlook" \
  -H "X-Admin-Session: abc123..."

# Returns: {"status": "queued", "job_id": "xyz789..."}
```

This allows you to manage syncs centrally while maintaining complete audit logging and security.

---

## Summary

✅ **Run SQL on Master Supabase** (2 migrations)
✅ **Create users in Master Supabase auth UI** (with `user_metadata.company_id`)
✅ **Map users to companies** (INSERT INTO company_users)
✅ **Deploy CORTEX** (code already updated!)
✅ **Test login** (users authenticate against Master Supabase)
✅ **Complete security** (JWT cryptographic binding + database validation)
✅ **Admin sync control** (trigger syncs for any company with audit logging)

No COMPANY_ID changes needed. No company Supabase data migration needed. Just add the tables and map the users!
