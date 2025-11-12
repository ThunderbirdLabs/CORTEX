-- ============================================================================
-- Add user_id column to audit_log_global table
-- ============================================================================
-- Purpose: Track which user performed each action in audit logs
-- Usage: Run this on MASTER Supabase project
-- ============================================================================

-- Add user_id column (nullable since some actions are admin-only)
ALTER TABLE public.audit_log_global
ADD COLUMN IF NOT EXISTS user_id uuid;

-- Add index for fast user lookups
CREATE INDEX IF NOT EXISTS idx_audit_log_global_user ON public.audit_log_global(user_id);

-- Add comment
COMMENT ON COLUMN public.audit_log_global.user_id IS 'User ID from Master Supabase auth.users (for user actions)';

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
