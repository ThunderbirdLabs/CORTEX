-- ============================================================================
-- CENTRALIZED AUTH - Company Users Mapping
-- ============================================================================
-- Purpose: Map Supabase auth users to companies for centralized authentication
-- Usage: Run this on MASTER Supabase project
-- ============================================================================

-- ============================================================================
-- COMPANY USERS (Maps auth.users to companies)
-- ============================================================================
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
COMMENT ON COLUMN public.company_users.user_id IS 'User ID from Master Supabase auth.users';
COMMENT ON COLUMN public.company_users.company_id IS 'Company this user belongs to';
COMMENT ON COLUMN public.company_users.email IS 'Denormalized email for quick lookups';
COMMENT ON COLUMN public.company_users.role IS 'User role within this company (owner, admin, user, viewer)';

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================
ALTER TABLE public.company_users ENABLE ROW LEVEL SECURITY;

-- Service role has full access
CREATE POLICY "Service role has full access" ON public.company_users FOR ALL USING (true);

-- Users can view their own company memberships
CREATE POLICY "Users can view their own companies" ON public.company_users
    FOR SELECT
    USING (auth.uid() = user_id);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Get all companies for a user
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

-- Check if user has access to company
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

-- Get user's role in company
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

-- Update last_login_at when user authenticates
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

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
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

-- ============================================================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================================================

-- Example: Add a user to Unit Industries
-- Uncomment and customize after creating users in Master Supabase auth

/*
INSERT INTO public.company_users (user_id, company_id, email, role)
SELECT
    '<user_id_from_auth_users>',
    c.id,
    'user@unitindustries.com',
    'admin'
FROM public.companies c
WHERE c.slug = 'unit-industries';
*/

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
