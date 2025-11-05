-- ============================================================================
-- CROSS-PLATFORM IDENTITY RESOLUTION SYSTEM
-- ============================================================================
-- Creates tables for mapping multiple platform-specific user IDs (Gmail,
-- Outlook, QuickBooks, Slack, HubSpot, etc.) to a single canonical person.
--
-- Use Case: "Hayden Woodburn" might be:
--   - hayden.woodburn@gmail.com (Gmail)
--   - h.woodburn@company.com (Outlook)
--   - Customer "Hayden Woodburn" (QuickBooks)
--   - User U12345 (Slack)
--
-- All these get linked to one canonical identity UUID.
-- ============================================================================

-- ============================================================================
-- CANONICAL IDENTITIES (The "golden record" for each person)
-- ============================================================================

CREATE TABLE IF NOT EXISTS canonical_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id TEXT NOT NULL,

    -- Core identity fields
    canonical_name TEXT NOT NULL,        -- "Hayden Woodburn"
    canonical_email TEXT,                 -- Primary/preferred email address

    -- Team member linking
    is_team_member BOOLEAN DEFAULT false,
    team_member_id INT REFERENCES team_members(id) ON DELETE SET NULL,

    -- Flexible metadata for custom fields
    metadata JSONB DEFAULT '{}',         -- {phone, title, department, etc.}

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_canonical_identities_tenant ON canonical_identities(tenant_id);
CREATE INDEX idx_canonical_identities_email ON canonical_identities(canonical_email) WHERE canonical_email IS NOT NULL;
CREATE INDEX idx_canonical_identities_team_member ON canonical_identities(team_member_id) WHERE team_member_id IS NOT NULL;
CREATE INDEX idx_canonical_identities_name_search ON canonical_identities USING gin(to_tsvector('english', canonical_name));

-- Unique constraint using expression index (case-insensitive canonical name per tenant)
CREATE UNIQUE INDEX idx_canonical_identities_unique_name ON canonical_identities(tenant_id, LOWER(canonical_name));

COMMENT ON TABLE canonical_identities IS 'Golden record for each unique person across all platforms';
COMMENT ON COLUMN canonical_identities.canonical_email IS 'Primary email address (user preference or most frequently used)';
COMMENT ON COLUMN canonical_identities.is_team_member IS 'True if this person is a company employee (linked to team_members table)';
COMMENT ON COLUMN canonical_identities.metadata IS 'Flexible JSONB for phone, title, department, custom fields';


-- ============================================================================
-- PLATFORM IDENTITIES (Platform-specific user IDs)
-- ============================================================================

CREATE TABLE IF NOT EXISTS platform_identities (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    canonical_identity_id UUID NOT NULL REFERENCES canonical_identities(id) ON DELETE CASCADE,

    -- Platform identification
    platform TEXT NOT NULL,              -- 'gmail', 'outlook', 'quickbooks', 'slack', 'hubspot', 'drive'
    platform_user_id TEXT NOT NULL,      -- Platform-specific ID (email, customer ID, user ID, etc.)
    platform_email TEXT,                 -- Email on that platform (if different from platform_user_id)
    display_name TEXT,                   -- How the person's name appears on that platform

    -- Matching confidence
    confidence FLOAT DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),  -- 0.0 = uncertain, 1.0 = verified
    verified BOOLEAN DEFAULT false,      -- Manual verification by admin
    verified_by TEXT,                    -- Admin user who verified
    verified_at TIMESTAMPTZ,

    -- Metadata
    raw_platform_data JSONB,            -- Store original platform user object
    last_seen_at TIMESTAMPTZ,           -- Last time we saw this ID in a sync
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Ensure no duplicate platform identities
    UNIQUE(tenant_id, platform, platform_user_id)
);

CREATE INDEX idx_platform_identities_canonical ON platform_identities(canonical_identity_id);
CREATE INDEX idx_platform_identities_tenant ON platform_identities(tenant_id);
CREATE INDEX idx_platform_identities_platform ON platform_identities(platform);
CREATE INDEX idx_platform_identities_lookup ON platform_identities(tenant_id, platform, platform_user_id);
CREATE INDEX idx_platform_identities_email ON platform_identities(platform_email) WHERE platform_email IS NOT NULL;
CREATE INDEX idx_platform_identities_unverified ON platform_identities(canonical_identity_id) WHERE verified = false;

COMMENT ON TABLE platform_identities IS 'Links platform-specific user IDs to canonical identities';
COMMENT ON COLUMN platform_identities.platform IS 'Source platform: gmail, outlook, quickbooks, slack, hubspot, drive, etc.';
COMMENT ON COLUMN platform_identities.platform_user_id IS 'Platform-specific identifier (email, customer ID, user ID)';
COMMENT ON COLUMN platform_identities.confidence IS 'Matching confidence: 1.0 = exact match, 0.9 = high confidence fuzzy, 0.75 = needs review';
COMMENT ON COLUMN platform_identities.verified IS 'Set to true after manual admin verification of the link';


-- ============================================================================
-- EMAIL ALIASES (All known email addresses for a person)
-- ============================================================================

CREATE TABLE IF NOT EXISTS email_aliases (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    canonical_identity_id UUID NOT NULL REFERENCES canonical_identities(id) ON DELETE CASCADE,

    email_address TEXT NOT NULL,         -- Normalized email (lowercase)
    is_primary BOOLEAN DEFAULT false,    -- Primary email for this person
    source_platform TEXT,                 -- Platform where we first discovered this email

    -- Activity tracking
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    usage_count INT DEFAULT 1            -- How many times we've seen this email
);

-- Indexes
CREATE INDEX idx_email_aliases_canonical ON email_aliases(canonical_identity_id);
CREATE INDEX idx_email_aliases_email_lookup ON email_aliases(tenant_id, LOWER(email_address));
CREATE INDEX idx_email_aliases_primary ON email_aliases(canonical_identity_id) WHERE is_primary = true;
CREATE INDEX idx_email_aliases_platform ON email_aliases(source_platform);

-- Unique constraint: one email = one person (case-insensitive)
CREATE UNIQUE INDEX idx_email_aliases_unique_email ON email_aliases(tenant_id, LOWER(email_address));

COMMENT ON TABLE email_aliases IS 'Tracks all email addresses associated with each canonical identity';
COMMENT ON COLUMN email_aliases.email_address IS 'Email address (stored lowercase for case-insensitive matching)';
COMMENT ON COLUMN email_aliases.is_primary IS 'True for the person''s primary/preferred email address';
COMMENT ON COLUMN email_aliases.usage_count IS 'Number of times we''ve seen this email in documents';


-- ============================================================================
-- IDENTITY MERGE SUGGESTIONS (AI/fuzzy matching suggestions for review)
-- ============================================================================

CREATE TABLE IF NOT EXISTS identity_merge_suggestions (
    id SERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,

    -- Suggested merge
    identity_a_id UUID NOT NULL REFERENCES canonical_identities(id) ON DELETE CASCADE,
    identity_b_id UUID NOT NULL REFERENCES canonical_identities(id) ON DELETE CASCADE,

    -- Matching details
    similarity_score FLOAT NOT NULL CHECK (similarity_score >= 0.0 AND similarity_score <= 1.0),
    matching_reason TEXT,                -- "Same email domain + name similarity 0.95"
    evidence JSONB,                      -- {name_similarity: 0.95, email_domain: "company.com", ...}

    -- Review status
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'merged')),
    reviewed_by TEXT,                    -- Admin user who reviewed
    reviewed_at TIMESTAMPTZ,
    review_notes TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id, identity_a_id, identity_b_id)
);

CREATE INDEX idx_merge_suggestions_pending ON identity_merge_suggestions(tenant_id, status) WHERE status = 'pending';
CREATE INDEX idx_merge_suggestions_identity_a ON identity_merge_suggestions(identity_a_id);
CREATE INDEX idx_merge_suggestions_identity_b ON identity_merge_suggestions(identity_b_id);
CREATE INDEX idx_merge_suggestions_score ON identity_merge_suggestions(similarity_score DESC);

COMMENT ON TABLE identity_merge_suggestions IS 'Stores AI/fuzzy matching suggestions for admin review';
COMMENT ON COLUMN identity_merge_suggestions.similarity_score IS 'Combined matching score (0.0-1.0)';
COMMENT ON COLUMN identity_merge_suggestions.evidence IS 'JSONB with matching details: name similarity, shared domains, etc.';


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to find canonical identity by email
CREATE OR REPLACE FUNCTION get_canonical_identity_by_email(p_tenant_id TEXT, p_email TEXT)
RETURNS UUID AS $$
DECLARE
    v_canonical_id UUID;
BEGIN
    -- Look up via email_aliases table
    SELECT canonical_identity_id INTO v_canonical_id
    FROM email_aliases
    WHERE tenant_id = p_tenant_id
      AND LOWER(email_address) = LOWER(p_email)
    LIMIT 1;

    RETURN v_canonical_id;
END;
$$ LANGUAGE plpgsql;

-- Function to find canonical identity by platform ID
CREATE OR REPLACE FUNCTION get_canonical_identity_by_platform(
    p_tenant_id TEXT,
    p_platform TEXT,
    p_platform_user_id TEXT
)
RETURNS UUID AS $$
DECLARE
    v_canonical_id UUID;
BEGIN
    SELECT canonical_identity_id INTO v_canonical_id
    FROM platform_identities
    WHERE tenant_id = p_tenant_id
      AND platform = p_platform
      AND platform_user_id = p_platform_user_id
    LIMIT 1;

    RETURN v_canonical_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get all emails for a canonical identity
CREATE OR REPLACE FUNCTION get_all_emails_for_identity(p_canonical_id UUID)
RETURNS TABLE (
    email_address TEXT,
    is_primary BOOLEAN,
    source_platform TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ea.email_address,
        ea.is_primary,
        ea.source_platform
    FROM email_aliases ea
    WHERE ea.canonical_identity_id = p_canonical_id
    ORDER BY ea.is_primary DESC, ea.usage_count DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get all platform IDs for a canonical identity
CREATE OR REPLACE FUNCTION get_all_platform_ids_for_identity(p_canonical_id UUID)
RETURNS TABLE (
    platform TEXT,
    platform_user_id TEXT,
    platform_email TEXT,
    display_name TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pi.platform,
        pi.platform_user_id,
        pi.platform_email,
        pi.display_name
    FROM platform_identities pi
    WHERE pi.canonical_identity_id = p_canonical_id
    ORDER BY pi.platform, pi.last_seen_at DESC;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- TRIGGER: Update updated_at timestamp
-- ============================================================================

CREATE OR REPLACE FUNCTION update_canonical_identity_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_canonical_identity_timestamp
BEFORE UPDATE ON canonical_identities
FOR EACH ROW
EXECUTE FUNCTION update_canonical_identity_timestamp();


-- ============================================================================
-- SAMPLE DATA (For testing - remove in production)
-- ============================================================================

-- Insert a sample team member canonical identity
-- INSERT INTO canonical_identities (tenant_id, canonical_name, canonical_email, is_team_member)
-- VALUES ('demo-tenant', 'Hayden Woodburn', 'hayden.woodburn@company.com', true);

-- Insert platform identities for the sample person
-- INSERT INTO platform_identities (tenant_id, canonical_identity_id, platform, platform_user_id, display_name, confidence)
-- VALUES
--     ('demo-tenant', (SELECT id FROM canonical_identities WHERE canonical_email = 'hayden.woodburn@company.com'), 'gmail', 'hayden.woodburn@gmail.com', 'Hayden Woodburn', 1.0),
--     ('demo-tenant', (SELECT id FROM canonical_identities WHERE canonical_email = 'hayden.woodburn@company.com'), 'outlook', 'h.woodburn@company.com', 'H. Woodburn', 0.95),
--     ('demo-tenant', (SELECT id FROM canonical_identities WHERE canonical_email = 'hayden.woodburn@company.com'), 'quickbooks', 'customer-456', 'Hayden Woodburn', 0.90);

-- Insert email aliases
-- INSERT INTO email_aliases (tenant_id, canonical_identity_id, email_address, is_primary, source_platform)
-- VALUES
--     ('demo-tenant', (SELECT id FROM canonical_identities WHERE canonical_email = 'hayden.woodburn@company.com'), 'hayden.woodburn@company.com', true, 'outlook'),
--     ('demo-tenant', (SELECT id FROM canonical_identities WHERE canonical_email = 'hayden.woodburn@company.com'), 'hayden.woodburn@gmail.com', false, 'gmail'),
--     ('demo-tenant', (SELECT id FROM canonical_identities WHERE canonical_email = 'hayden.woodburn@company.com'), 'h.woodburn@company.com', false, 'outlook');


-- ============================================================================
-- GRANTS (Adjust based on your security model)
-- ============================================================================

-- Grant appropriate permissions
-- GRANT SELECT, INSERT, UPDATE, DELETE ON canonical_identities TO authenticated;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON platform_identities TO authenticated;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON email_aliases TO authenticated;
-- GRANT SELECT, INSERT, UPDATE ON identity_merge_suggestions TO authenticated;


-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. Email addresses stored lowercase for case-insensitive matching
-- 2. Unique constraint on (tenant_id, email) ensures one email = one person
-- 3. Cascade deletes: removing canonical identity removes all linked data
-- 4. Confidence scores: 1.0 = exact, 0.9+ = auto-merge, 0.75+ = review queue
-- 5. Helper functions provided for common lookups
-- 6. Indexes optimized for email/platform lookups and admin review queries
-- 7. identity_merge_suggestions table enables human-in-the-loop review
-- ============================================================================
