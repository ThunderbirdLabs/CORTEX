-- ============================================================================
-- COMPANY SUPABASE MIGRATION - USER TRACKING FOR OAUTH CONNECTIONS
-- ============================================================================
-- Purpose: Track which user created each OAuth connection
-- Run in: EACH COMPANY's Supabase project (SQL Editor)
-- ============================================================================
--
-- SECURITY FIX: Previously connections were scoped only by tenant_id (company_id),
-- meaning all users in a company shared the same OAuth connections.
-- This prevents proper attribution and multi-user support.
--
-- After this migration:
-- - Each user can have their own OAuth connection per provider
-- - We track who connected what and when
-- - Proper audit trail for OAuth authorization
-- ============================================================================

-- Add user tracking columns
ALTER TABLE connections
ADD COLUMN IF NOT EXISTS user_id TEXT,
ADD COLUMN IF NOT EXISTS user_email TEXT,
ADD COLUMN IF NOT EXISTS connected_at TIMESTAMPTZ DEFAULT NOW();

-- Drop old constraint (tenant + provider)
ALTER TABLE connections DROP CONSTRAINT IF EXISTS connections_tenant_id_provider_key_key;

-- Add new constraint (tenant + provider + user)
-- This allows multiple users in same company to each have their own connection
ALTER TABLE connections ADD CONSTRAINT unique_user_provider_connection
    UNIQUE(tenant_id, provider_key, user_id);

-- Add index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_connections_user ON connections(user_id);
CREATE INDEX IF NOT EXISTS idx_connections_tenant_user ON connections(tenant_id, user_id);

-- Add helpful comments
COMMENT ON COLUMN connections.user_id IS
  'User ID (from Master Supabase auth.users) who created this OAuth connection. Enables per-user connections.';

COMMENT ON COLUMN connections.user_email IS
  'Email of user who created connection (for display/logging). Denormalized for convenience.';

COMMENT ON COLUMN connections.connected_at IS
  'Timestamp when this connection was first established';

-- Verify columns were added
SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'connections'
  AND column_name IN (
    'user_id',
    'user_email',
    'connected_at'
  )
ORDER BY ordinal_position;

-- Show current connections (for backfill planning)
-- Existing connections will have NULL user_id and need to be re-authorized
SELECT
    id,
    tenant_id,
    provider_key,
    connection_id,
    user_id,
    user_email,
    created_at,
    connected_at
FROM connections
ORDER BY created_at DESC;
