-- ============================================================================
-- COMPANY SUPABASE MIGRATION - ONE-TIME SYNC TRACKING
-- ============================================================================
-- Purpose: Add sync locking to connections table
-- Run in: EACH COMPANY's Supabase project (SQL Editor)
-- ============================================================================

-- Add sync control columns
ALTER TABLE connections
ADD COLUMN IF NOT EXISTS can_manual_sync BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS initial_sync_completed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS initial_sync_started_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS initial_sync_completed_at TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS sync_lock_reason TEXT;

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_connections_sync_lock
ON connections(tenant_id, provider_key, can_manual_sync);

-- Add helpful comments
COMMENT ON COLUMN connections.can_manual_sync IS
  'Whether user can manually trigger sync. Set to FALSE after first sync. Admin can override via master Supabase.';

COMMENT ON COLUMN connections.initial_sync_completed IS
  'Whether initial 1-year historical sync has completed';

COMMENT ON COLUMN connections.sync_lock_reason IS
  'Why manual sync was locked (e.g., "Initial historical sync completed")';

-- Verify columns were added
SELECT
    column_name,
    data_type,
    column_default,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'connections'
  AND column_name IN (
    'can_manual_sync',
    'initial_sync_completed',
    'initial_sync_started_at',
    'initial_sync_completed_at',
    'sync_lock_reason'
  )
ORDER BY ordinal_position;
