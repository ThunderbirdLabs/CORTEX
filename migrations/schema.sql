-- ============================================================================
-- NANGO CONNECTION SERVICE - Database Schema
-- ============================================================================
-- No RLS for testing - add security policies later in production

-- Connections table: Maps tenant_id to Nango connection_id per provider
CREATE TABLE IF NOT EXISTS connections (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, provider_key)
);

CREATE INDEX IF NOT EXISTS idx_connections_tenant ON connections(tenant_id);

-- User cursors table: Stores Microsoft Graph delta links for incremental sync
CREATE TABLE IF NOT EXISTS user_cursors (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_principal_name TEXT NOT NULL,
    delta_link TEXT NOT NULL,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, provider_key, user_id)
);

CREATE INDEX IF NOT EXISTS idx_user_cursors_tenant ON user_cursors(tenant_id);

-- Gmail cursors table: Stores Nango cursors for Gmail incremental sync
CREATE TABLE IF NOT EXISTS gmail_cursors (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    cursor TEXT NOT NULL,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, provider_key)
);

CREATE INDEX IF NOT EXISTS idx_gmail_cursors_tenant ON gmail_cursors(tenant_id);

-- Emails table: Normalized email storage from all providers
CREATE TABLE IF NOT EXISTS emails (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_principal_name TEXT NOT NULL,
    message_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('outlook', 'gmail')),
    subject TEXT,
    sender_name TEXT,
    sender_address TEXT,
    to_addresses JSONB,  -- Array of email addresses
    received_datetime TIMESTAMPTZ,
    web_link TEXT,
    full_body TEXT,  -- Full email body content
    change_key TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(tenant_id, source, message_id)
);

CREATE INDEX IF NOT EXISTS idx_emails_tenant ON emails(tenant_id);
CREATE INDEX IF NOT EXISTS idx_emails_source ON emails(source);
CREATE INDEX IF NOT EXISTS idx_emails_received ON emails(received_datetime DESC);
CREATE INDEX IF NOT EXISTS idx_emails_sender ON emails(sender_address);

-- Optional: GIN index for JSONB to_addresses searches
CREATE INDEX IF NOT EXISTS idx_emails_to_addresses ON emails USING GIN (to_addresses);

-- Comments for documentation
COMMENT ON TABLE connections IS 'Stores Nango OAuth connections per tenant and provider';
COMMENT ON TABLE user_cursors IS 'Stores Microsoft Graph delta links for incremental Outlook sync';
COMMENT ON TABLE gmail_cursors IS 'Stores Nango pagination cursors for incremental Gmail sync';
COMMENT ON TABLE emails IS 'Normalized email storage from Outlook and Gmail';

COMMENT ON COLUMN emails.to_addresses IS 'JSONB array of recipient email addresses';
COMMENT ON COLUMN emails.full_body IS 'Full email body content (HTML or plain text)';
COMMENT ON COLUMN emails.change_key IS 'Microsoft Graph change key for tracking updates';
