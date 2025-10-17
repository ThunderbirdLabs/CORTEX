-- ============================================================================
-- Add content_hash column for deduplication
-- ============================================================================
-- Run this migration on your Supabase database

-- Add content_hash column (stores SHA256 hash of normalized content)
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS content_hash TEXT;

-- Create index for fast duplicate lookups
CREATE INDEX IF NOT EXISTS idx_documents_content_hash 
ON documents(tenant_id, content_hash);

-- Add comment
COMMENT ON COLUMN documents.content_hash IS 'SHA256 hash of normalized content for deduplication';

-- ============================================================================
-- Backfill existing documents (optional - run if you have existing data)
-- ============================================================================
-- This will compute hashes for existing documents
-- WARNING: This can be slow on large tables - run during low traffic

-- Uncomment to backfill:
-- UPDATE documents
-- SET content_hash = encode(digest(lower(regexp_replace(content, '\s+', ' ', 'g')), 'sha256'), 'hex')
-- WHERE content_hash IS NULL;

