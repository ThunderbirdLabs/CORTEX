-- ============================================================================
-- COMPANY SUPABASE MIGRATION - ADD COMPANY SCOPING TO SYNC JOBS
-- ============================================================================
-- Purpose: Add tenant_id (company_id) to sync_jobs for proper filtering
-- Run in: EACH COMPANY's Supabase project (SQL Editor)
-- ============================================================================
--
-- FIX: sync_jobs table currently has user_id but NO tenant_id/company_id.
-- This makes company-wide queries inefficient and breaks multi-tenant filtering.
--
-- After this migration:
-- - Can efficiently query "all sync jobs for company X"
-- - Proper multi-tenant isolation
-- - Can track both who triggered the sync AND which company it's for
-- ============================================================================

-- Add tenant_id (company_id) column
-- Use DEFAULT to allow existing rows (will be backfilled if needed)
ALTER TABLE sync_jobs
ADD COLUMN IF NOT EXISTS tenant_id TEXT;

-- Add index for fast company queries
CREATE INDEX IF NOT EXISTS idx_sync_jobs_tenant ON sync_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_tenant_user ON sync_jobs(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_tenant_status ON sync_jobs(tenant_id, status);

-- Add helpful comment
COMMENT ON COLUMN sync_jobs.tenant_id IS
  'Company ID (tenant_id) for multi-tenant isolation. Same as company_id in Master Supabase.';

-- Verify column was added
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'sync_jobs'
  AND column_name = 'tenant_id';

-- Show existing sync jobs (for manual backfill if needed)
-- You may need to update tenant_id for existing rows if your deployment knows its company_id
SELECT
    id,
    user_id,
    tenant_id,
    job_type,
    status,
    created_at
FROM sync_jobs
WHERE tenant_id IS NULL
ORDER BY created_at DESC
LIMIT 10;
