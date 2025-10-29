-- ============================================================================
-- SEED DATA: Unit Industries (Your First Company)
-- ============================================================================
-- Purpose: Migrate existing Unit Industries deployment to master control plane
-- Run this AFTER 001_create_master_tables.sql
-- ============================================================================

-- ============================================================================
-- 1. CREATE YOUR MASTER ADMIN ACCOUNT
-- ============================================================================
-- TODO: Replace with your actual email and generate proper bcrypt hash
-- For now using placeholder - you'll update this with real values

INSERT INTO master_admins (email, name, password_hash, role, can_create_companies, can_delete_companies)
VALUES (
    'nicolas@unit.com',  -- TODO: Replace with your email
    'Nicolas Codet',
    '$2b$12$placeholder',  -- TODO: Replace with bcrypt hash of your password
    'super_admin',
    true,
    true
);

-- ============================================================================
-- 2. CREATE UNIT INDUSTRIES COMPANY RECORD
-- ============================================================================

INSERT INTO companies (
    slug,
    name,
    status,
    plan,
    backend_url,
    frontend_url,
    company_location,
    company_description,
    industries_served,
    key_capabilities,
    primary_contact_email,
    primary_contact_name,
    activated_at
) VALUES (
    'unit-industries',
    'Unit Industries Group, Inc.',
    'active',
    'enterprise',
    'https://nango-connection-only.onrender.com',  -- Your current backend
    'https://connectorfrontend.vercel.app',  -- Your current frontend
    'Santa Ana, CA',
    'Progressive plastic injection molding company specializing in innovative manufacturing solutions.',
    '["Communications", "Medical", "Defense/Aerospace", "Industrial/Semiconductor", "Multimedia", "Automotive", "Clean Technology"]'::jsonb,
    '["Class 100,000 Clean Room (4,800 sq ft)", "End-to-end manufacturing and logistics solutions", "ISO 9001 certified", "Over a century of combined experience"]'::jsonb,
    'anthony@unit.com',
    'Anthony Codet',
    NOW()
);

-- ============================================================================
-- 3. ADD UNIT INDUSTRIES DEPLOYMENT CONFIG
-- ============================================================================
-- TODO: Fill in your actual credentials (you'll do this via setup script)
-- For now, this is a template showing the structure

INSERT INTO company_deployments (
    company_id,
    supabase_url,
    supabase_anon_key,
    supabase_service_key,
    neo4j_uri,
    neo4j_user,
    neo4j_password,
    qdrant_url,
    qdrant_api_key,
    qdrant_collection_name,
    redis_url,
    openai_api_key,
    nango_secret_key,
    nango_public_key,
    nango_provider_key_gmail,
    nango_provider_key_outlook,
    nango_provider_key_google_drive,
    admin_pin_hash
) VALUES (
    (SELECT id FROM companies WHERE slug = 'unit-industries'),
    'https://your-project.supabase.co',  -- TODO: Your actual Supabase URL
    'eyJhbGc...',  -- TODO: Your actual anon key
    'eyJhbGc...',  -- TODO: Your actual service key
    'neo4j+s://your.databases.neo4j.io',  -- TODO: Your actual Neo4j URI
    'neo4j',
    'your-password',  -- TODO: Your actual Neo4j password
    'https://your.qdrant.io',  -- TODO: Your actual Qdrant URL
    'your-api-key',  -- TODO: Your actual Qdrant key
    'cortex',  -- TODO: Your actual collection name
    'redis://your-redis:6379',  -- TODO: Your actual Redis URL
    'sk-...',  -- TODO: Your actual OpenAI key
    'your-nango-secret',  -- TODO: Your actual Nango secret
    'your-nango-public',  -- TODO: Your actual Nango public key
    'gmail',  -- TODO: Your actual provider key
    'microsoft',  -- TODO: Your actual provider key
    'google-drive',  -- TODO: Your actual provider key
    '$2b$12$hashof2525'  -- TODO: bcrypt hash of '2525'
);

-- ============================================================================
-- 4. ADD UNIT INDUSTRIES TEAM MEMBERS
-- ============================================================================

INSERT INTO company_team_members (company_id, name, title, role_description, reports_to) VALUES
    ((SELECT id FROM companies WHERE slug = 'unit-industries'),
     'Anthony Codet', 'President & CEO', 'Primary decision-maker, lead engineer, oversees all operations', NULL),

    ((SELECT id FROM companies WHERE slug = 'unit-industries'),
     'Kevin Trainor', 'VP/Sales', 'Customer relationships, ISO 9001 audits, supervises key employees', 'Anthony Codet'),

    ((SELECT id FROM companies WHERE slug = 'unit-industries'),
     'Sandra', 'Head of QA', 'Works with Ramiro & Hayden, prepares CoC and FOD docs', 'Kevin/Tony/Ramiro/Hayden'),

    ((SELECT id FROM companies WHERE slug = 'unit-industries'),
     'Ramiro', 'Production & Shipping Manager/Material Buyer', 'Oversees production, shipping, procurement for SCP/SMC', 'Anthony Codet'),

    ((SELECT id FROM companies WHERE slug = 'unit-industries'),
     'Paul', 'Head of Accounting & Finance', 'Invoicing, financial reporting, material deliveries', 'Anthony Codet'),

    ((SELECT id FROM companies WHERE slug = 'unit-industries'),
     'Hayden', 'Customer Service Lead/Operations Support', 'Supports all departments, customer comms, production tracking', NULL);

-- ============================================================================
-- 5. DEFAULT SCHEMAS (Empty for now - Unit Industries uses defaults)
-- ============================================================================
-- When you add custom entities via the admin dashboard, they'll be stored here
-- For now, Unit Industries has no custom schemas (uses default PERSON, COMPANY, etc.)

-- Example of what a custom schema would look like:
-- INSERT INTO company_schemas (company_id, override_type, entity_type, description, created_by) VALUES
--     ((SELECT id FROM companies WHERE slug = 'unit-industries'),
--      'entity',
--      'MACHINE',
--      'Injection molding machines and equipment',
--      'nicolas@unit.com');

-- ============================================================================
-- 6. LOG THE SETUP
-- ============================================================================

INSERT INTO audit_log_global (
    company_id,
    admin_id,
    action,
    resource_type,
    resource_id,
    details,
    ip_address
) VALUES (
    (SELECT id FROM companies WHERE slug = 'unit-industries'),
    (SELECT id FROM master_admins WHERE email = 'nicolas@unit.com'),
    'create_company',
    'company',
    (SELECT id::text FROM companies WHERE slug = 'unit-industries'),
    '{"source": "migration", "note": "Initial setup of Unit Industries in master control plane"}'::jsonb,
    '127.0.0.1'
);

-- ============================================================================
-- VERIFICATION QUERIES (Run these to confirm setup)
-- ============================================================================

-- Check company was created
SELECT id, slug, name, status FROM companies WHERE slug = 'unit-industries';

-- Check team members
SELECT name, title FROM company_team_members
WHERE company_id = (SELECT id FROM companies WHERE slug = 'unit-industries');

-- Check admin account
SELECT email, name, role FROM master_admins WHERE email = 'nicolas@unit.com';

-- Check audit log
SELECT action, resource_type, created_at FROM audit_log_global
WHERE company_id = (SELECT id FROM companies WHERE slug = 'unit-industries')
ORDER BY created_at DESC
LIMIT 5;

-- ============================================================================
-- END OF SEED DATA
-- ============================================================================
