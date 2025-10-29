-- ============================================================================
-- CORTEX MASTER CONTROL PLANE - Database Schema
-- ============================================================================
-- Purpose: Central management of all company deployments
-- Usage: Run this on your MASTER Supabase project (NOT company Supabase)
-- ============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- COMPANIES
-- ============================================================================
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug TEXT UNIQUE NOT NULL,  -- "unit-industries", "acme-corp"
    name TEXT NOT NULL,          -- "Unit Industries Group, Inc."
    status TEXT DEFAULT 'active',  -- active, suspended, trial, provisioning
    plan TEXT DEFAULT 'enterprise',  -- trial, standard, enterprise

    -- Deployment URLs
    backend_url TEXT,            -- https://cortex-unit.onrender.com
    frontend_url TEXT,           -- https://unit-cortex.vercel.app
    render_service_id TEXT,      -- For programmatic deploys
    vercel_project_id TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    activated_at TIMESTAMP,
    trial_ends_at TIMESTAMP,
    last_sync_at TIMESTAMP,

    -- Company profile (used in prompts)
    company_location TEXT,
    company_description TEXT,
    industries_served JSONB DEFAULT '[]',     -- ["Medical", "Aerospace"]
    key_capabilities JSONB DEFAULT '[]',

    -- Contact info
    primary_contact_email TEXT,
    primary_contact_name TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    CONSTRAINT valid_slug CHECK (slug ~ '^[a-z0-9-]+$'),
    CONSTRAINT valid_status CHECK (status IN ('active', 'suspended', 'trial', 'provisioning', 'deleted'))
);

CREATE INDEX idx_companies_slug ON companies(slug);
CREATE INDEX idx_companies_status ON companies(status);

COMMENT ON TABLE companies IS 'Central registry of all CORTEX company deployments';

-- ============================================================================
-- COMPANY DEPLOYMENTS (Infrastructure Configuration)
-- ============================================================================
CREATE TABLE company_deployments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    -- Supabase (company's operational database)
    supabase_project_ref TEXT,
    supabase_url TEXT NOT NULL,
    supabase_anon_key TEXT NOT NULL,
    supabase_service_key TEXT NOT NULL,  -- TODO: Encrypt in production!

    -- Neo4j (knowledge graph)
    neo4j_uri TEXT NOT NULL,
    neo4j_user TEXT DEFAULT 'neo4j',
    neo4j_password TEXT NOT NULL,  -- TODO: Encrypt in production!
    neo4j_database TEXT DEFAULT 'neo4j',

    -- Qdrant (vector store)
    qdrant_url TEXT NOT NULL,
    qdrant_api_key TEXT,  -- TODO: Encrypt in production!
    qdrant_collection_name TEXT NOT NULL,

    -- Redis (job queue)
    redis_url TEXT NOT NULL,
    redis_db_number INTEGER DEFAULT 0,

    -- OpenAI
    openai_api_key TEXT,  -- TODO: Encrypt in production!

    -- Nango OAuth
    nango_secret_key TEXT,  -- TODO: Encrypt in production!
    nango_public_key TEXT,
    nango_provider_key_gmail TEXT,
    nango_provider_key_outlook TEXT,
    nango_provider_key_google_drive TEXT,
    nango_provider_key_quickbooks TEXT,

    -- Admin
    admin_pin_hash TEXT NOT NULL,  -- bcrypt hash

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    CONSTRAINT unique_company_deployment UNIQUE(company_id)
);

CREATE INDEX idx_deployments_company ON company_deployments(company_id);

COMMENT ON TABLE company_deployments IS 'Infrastructure configuration for each company (credentials, endpoints)';

-- ============================================================================
-- COMPANY SCHEMAS (Centralized Schema Management)
-- ============================================================================
CREATE TABLE company_schemas (
    id SERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    -- Schema definition
    override_type TEXT NOT NULL,  -- 'entity' or 'relation'
    entity_type TEXT,
    relation_type TEXT,
    from_entity TEXT,
    to_entity TEXT,
    description TEXT,

    -- Metadata
    created_by TEXT,  -- Master admin email
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,

    CONSTRAINT valid_override_type CHECK (override_type IN ('entity', 'relation')),
    CONSTRAINT entity_or_relation CHECK (
        (override_type = 'entity' AND entity_type IS NOT NULL) OR
        (override_type = 'relation' AND relation_type IS NOT NULL)
    )
);

CREATE INDEX idx_company_schemas_lookup ON company_schemas(company_id, override_type, is_active);
CREATE INDEX idx_company_schemas_entity ON company_schemas(company_id, entity_type) WHERE entity_type IS NOT NULL;
CREATE INDEX idx_company_schemas_relation ON company_schemas(company_id, relation_type) WHERE relation_type IS NOT NULL;

COMMENT ON TABLE company_schemas IS 'Custom entity types and relationships per company';

-- ============================================================================
-- COMPANY TEAM MEMBERS (Centralized Team Management)
-- ============================================================================
CREATE TABLE company_team_members (
    id SERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    name TEXT NOT NULL,
    title TEXT NOT NULL,
    role_description TEXT,
    reports_to TEXT,
    email TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_team_members_company ON company_team_members(company_id);

COMMENT ON TABLE company_team_members IS 'Team rosters for each company (used in prompts)';

-- ============================================================================
-- MASTER ADMINS (Your Team)
-- ============================================================================
CREATE TABLE master_admins (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,  -- bcrypt
    name TEXT NOT NULL,

    -- Permissions
    role TEXT DEFAULT 'admin',  -- super_admin, admin, viewer
    can_create_companies BOOLEAN DEFAULT false,
    can_delete_companies BOOLEAN DEFAULT false,
    can_view_schemas BOOLEAN DEFAULT true,
    can_edit_schemas BOOLEAN DEFAULT true,
    can_view_deployments BOOLEAN DEFAULT true,
    can_edit_deployments BOOLEAN DEFAULT false,

    -- Security
    last_login_at TIMESTAMP,
    last_login_ip TEXT,
    mfa_enabled BOOLEAN DEFAULT false,
    mfa_secret TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_master_admins_email ON master_admins(email);

COMMENT ON TABLE master_admins IS 'Admin users who manage the master control plane';

-- ============================================================================
-- GLOBAL AUDIT LOG (All Actions Across All Companies)
-- ============================================================================
CREATE TABLE audit_log_global (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES companies(id),  -- NULL for master-level actions
    admin_id UUID REFERENCES master_admins(id),

    action TEXT NOT NULL,  -- 'create_company', 'edit_schema', 'view_dashboard', 'trigger_sync'
    resource_type TEXT,    -- 'company', 'schema', 'team_member', 'deployment'
    resource_id TEXT,
    details JSONB DEFAULT '{}',

    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_company ON audit_log_global(company_id, created_at DESC);
CREATE INDEX idx_audit_admin ON audit_log_global(admin_id, created_at DESC);
CREATE INDEX idx_audit_action ON audit_log_global(action, created_at DESC);

COMMENT ON TABLE audit_log_global IS 'Complete audit trail of all master admin actions';

-- ============================================================================
-- MASTER ADMIN SESSIONS
-- ============================================================================
CREATE TABLE master_admin_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    admin_id UUID REFERENCES master_admins(id) ON DELETE CASCADE,
    session_token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_master_sessions_token ON master_admin_sessions(session_token);
CREATE INDEX idx_master_sessions_expires ON master_admin_sessions(expires_at);

COMMENT ON TABLE master_admin_sessions IS 'Active login sessions for master admins';

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get all schemas for a company (default + custom)
CREATE OR REPLACE FUNCTION get_company_schema(p_company_id UUID)
RETURNS TABLE (
    entity_type TEXT,
    relation_type TEXT,
    override_type TEXT,
    description TEXT,
    is_custom BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        cs.entity_type,
        cs.relation_type,
        cs.override_type,
        cs.description,
        true as is_custom
    FROM company_schemas cs
    WHERE cs.company_id = p_company_id
      AND cs.is_active = true;
END;
$$ LANGUAGE plpgsql;

-- Function to log admin actions
CREATE OR REPLACE FUNCTION log_admin_action(
    p_company_id UUID,
    p_admin_id UUID,
    p_action TEXT,
    p_resource_type TEXT,
    p_resource_id TEXT,
    p_details JSONB,
    p_ip_address TEXT,
    p_user_agent TEXT
) RETURNS UUID AS $$
DECLARE
    v_log_id UUID;
BEGIN
    INSERT INTO audit_log_global (
        company_id, admin_id, action, resource_type,
        resource_id, details, ip_address, user_agent
    ) VALUES (
        p_company_id, p_admin_id, p_action, p_resource_type,
        p_resource_id, p_details, p_ip_address, p_user_agent
    ) RETURNING id INTO v_log_id;

    RETURN v_log_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ROW LEVEL SECURITY (Enable but allow service role full access)
-- ============================================================================

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_schemas ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_team_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE master_admins ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log_global ENABLE ROW LEVEL SECURITY;
ALTER TABLE master_admin_sessions ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (company backends use service role)
CREATE POLICY "Service role has full access" ON companies FOR ALL USING (true);
CREATE POLICY "Service role has full access" ON company_deployments FOR ALL USING (true);
CREATE POLICY "Service role has full access" ON company_schemas FOR ALL USING (true);
CREATE POLICY "Service role has full access" ON company_team_members FOR ALL USING (true);
CREATE POLICY "Service role has full access" ON master_admins FOR ALL USING (true);
CREATE POLICY "Service role has full access" ON audit_log_global FOR ALL USING (true);
CREATE POLICY "Service role has full access" ON master_admin_sessions FOR ALL USING (true);

-- ============================================================================
-- INITIAL DATA (Your first company - Unit Industries)
-- ============================================================================

-- This will be populated when you run the setup script
-- For now, this is just the schema

-- ============================================================================
-- END OF MASTER SCHEMA
-- ============================================================================
