-- ============================================================================
-- MASTER SUPABASE MIGRATION - SYNC PERMISSIONS OVERRIDE
-- ============================================================================
-- Purpose: Create admin sync permission overrides
-- Run in: MASTER Supabase project (SQL Editor)
-- ============================================================================

-- Create sync_permissions table
CREATE TABLE IF NOT EXISTS public.sync_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,

    -- Override control
    can_manual_sync_override BOOLEAN DEFAULT NULL,
    override_reason TEXT,
    override_enabled_at TIMESTAMP WITH TIME ZONE,
    override_enabled_by TEXT,  -- Admin email

    -- Audit fields
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- One override per company
    UNIQUE(company_id)
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_sync_permissions_company
ON public.sync_permissions(company_id);

-- Enable RLS
ALTER TABLE public.sync_permissions ENABLE ROW LEVEL SECURITY;

-- Admin-only access policy
CREATE POLICY "Admins can manage sync permissions"
ON public.sync_permissions
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

-- Add helpful comments
COMMENT ON TABLE public.sync_permissions IS
  'Admin overrides for company sync permissions. Allows HighForce admins to unlock manual sync for troubleshooting.';

COMMENT ON COLUMN public.sync_permissions.can_manual_sync_override IS
  'Override value: NULL = no override (use company default), TRUE = force allow, FALSE = force block';

COMMENT ON COLUMN public.sync_permissions.override_reason IS
  'Why admin enabled this override (e.g., "Customer requested re-sync due to missing emails")';

-- Verify table was created
SELECT
    table_name,
    column_name,
    data_type,
    column_default
FROM information_schema.columns
WHERE table_name = 'sync_permissions'
ORDER BY ordinal_position;

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
