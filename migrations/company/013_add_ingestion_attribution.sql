-- ============================================================================
-- COMPANY SUPABASE MIGRATION - DOCUMENT INGESTION ATTRIBUTION
-- ============================================================================
-- Purpose: Track which user ingested each document
-- Run in: EACH COMPANY's Supabase project (SQL Editor)
-- ============================================================================
--
-- AUDIT & COMPLIANCE: Track who uploads or syncs documents into the system.
-- Enables:
-- - Accountability: Know who brought data into the system
-- - User quotas: Limit uploads per user
-- - Compliance: Data provenance tracking
-- - Security: Audit trail for all data ingestion
-- ============================================================================

-- Add ingestion tracking columns to documents table
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS ingested_by_user_id TEXT,
ADD COLUMN IF NOT EXISTS ingested_by_user_email TEXT,
ADD COLUMN IF NOT EXISTS ingestion_method TEXT;  -- 'oauth_sync', 'manual_upload', 'api', etc.

-- Add index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_documents_ingested_by ON documents(ingested_by_user_id);
CREATE INDEX IF NOT EXISTS idx_documents_tenant_user ON documents(tenant_id, ingested_by_user_id);

-- Add helpful comments
COMMENT ON COLUMN documents.ingested_by_user_id IS
  'User ID (from Master Supabase auth.users) who ingested this document. NULL for system-ingested documents.';

COMMENT ON COLUMN documents.ingested_by_user_email IS
  'Email of user who ingested document (for display/logging). Denormalized for convenience.';

COMMENT ON COLUMN documents.ingestion_method IS
  'How document was ingested: oauth_sync, manual_upload, api, webhook, etc.';

-- Verify columns were added
SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'documents'
  AND column_name IN (
    'ingested_by_user_id',
    'ingested_by_user_email',
    'ingestion_method'
  )
ORDER BY ordinal_position;
