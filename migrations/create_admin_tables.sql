-- Admin Dashboard Tables
-- Tracks admin sessions, audit logs, and schema overrides

-- ============================================================================
-- ADMIN SESSIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_token TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    ip_address TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_admin_sessions_token ON admin_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires ON admin_sessions(expires_at);

COMMENT ON TABLE admin_sessions IS 'Admin dashboard session tokens (1 hour expiry)';


-- ============================================================================
-- ADMIN AUDIT LOG
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES admin_sessions(id),
    action TEXT NOT NULL,        -- 'login', 'trigger_sync', 'edit_schema', etc.
    resource_type TEXT,           -- 'connector', 'schema', 'job', etc.
    resource_id TEXT,             -- Job ID, user ID, etc.
    details JSONB,                -- Full action details
    ip_address TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_session ON admin_audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON admin_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON admin_audit_log(action);

COMMENT ON TABLE admin_audit_log IS 'Audit trail for all admin actions';


-- ============================================================================
-- SCHEMA OVERRIDES (For dynamic entity/relationship management)
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_schema_overrides (
    id SERIAL PRIMARY KEY,
    override_type TEXT NOT NULL,  -- 'entity' or 'relation'
    entity_type TEXT,             -- For entities: PERSON, PROJECT, etc.
    relation_type TEXT,           -- For relations: WORKS_FOR, MANAGES, etc.
    from_entity TEXT,             -- For relations: source entity
    to_entity TEXT,               -- For relations: target entity
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,              -- Admin session ID
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_schema_overrides_type ON admin_schema_overrides(override_type);
CREATE INDEX IF NOT EXISTS idx_schema_overrides_active ON admin_schema_overrides(is_active);

COMMENT ON TABLE admin_schema_overrides IS 'Dynamic schema changes without code modification';


-- ============================================================================
-- COMPANY SETTINGS (For prompt generation)
-- ============================================================================

CREATE TABLE IF NOT EXISTS company_settings (
    id SERIAL PRIMARY KEY,
    company_name TEXT,
    company_location TEXT,
    company_description TEXT,
    industries_served JSONB,       -- Array of industries
    key_capabilities JSONB,        -- Array of capabilities
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT                -- Admin session ID
);

-- Insert default settings
INSERT INTO company_settings (company_name, company_location, company_description, industries_served, key_capabilities)
VALUES (
    'Unit Industries Group, Inc.',
    'Santa Ana, CA',
    'Progressive plastic injection molding company specializing in innovative manufacturing solutions.',
    '["Communications", "Medical", "Defense/Aerospace", "Industrial/Semiconductor", "Multimedia", "Automotive", "Clean Technology"]'::jsonb,
    '["Class 100,000 Clean Room (4,800 sq ft)", "End-to-end manufacturing and logistics solutions", "ISO 9001 certified", "Over a century of combined experience"]'::jsonb
)
ON CONFLICT DO NOTHING;

COMMENT ON TABLE company_settings IS 'Company profile used in system prompts';


-- ============================================================================
-- TEAM MEMBERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS team_members (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    role_description TEXT,
    reports_to TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Insert default team
INSERT INTO team_members (name, title, role_description, reports_to)
VALUES
    ('Anthony Codet', 'President & CEO', 'Primary decision-maker, lead engineer, oversees all operations', NULL),
    ('Kevin Trainor', 'VP/Sales', 'Customer relationships, ISO 9001 audits, supervises key employees', 'Anthony Codet'),
    ('Sandra', 'Head of QA', 'Works with Ramiro & Hayden, prepares CoC and FOD docs', 'Kevin/Tony/Ramiro/Hayden'),
    ('Ramiro', 'Production & Shipping Manager/Material Buyer', 'Oversees production, shipping, procurement for SCP/SMC', 'Anthony Codet'),
    ('Paul', 'Head of Accounting & Finance', 'Invoicing, financial reporting, material deliveries', 'Anthony Codet'),
    ('Hayden', 'Customer Service Lead/Operations Support', 'Supports all departments, customer comms, production tracking', NULL)
ON CONFLICT DO NOTHING;

COMMENT ON TABLE team_members IS 'Company team structure used in prompts';


-- ============================================================================
-- PROMPT OVERRIDES (For dynamic prompt management)
-- ============================================================================

CREATE TABLE IF NOT EXISTS company_prompt_overrides (
    id SERIAL PRIMARY KEY,
    prompt_type TEXT NOT NULL,    -- 'ceo_synthesis', 'spam_detection', 'attachment_filter', etc.
    prompt_text TEXT NOT NULL,
    original_prompt TEXT,         -- For comparison/rollback
    version INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,              -- Admin session ID
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_prompt_overrides_type ON company_prompt_overrides(prompt_type);
CREATE INDEX IF NOT EXISTS idx_prompt_overrides_active ON company_prompt_overrides(is_active);

COMMENT ON TABLE company_prompt_overrides IS 'Dynamic prompt updates without code changes';
