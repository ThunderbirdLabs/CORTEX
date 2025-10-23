-- Create user_cursors table for storing Microsoft Graph delta tokens
-- This enables incremental email sync (only fetch new/updated emails)

-- First, drop the incorrect table if it exists
DROP TABLE IF EXISTS user_cursors;

-- Create the correct table schema
CREATE TABLE user_cursors (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    user_principal_name TEXT NOT NULL,
    delta_link TEXT NOT NULL,
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, provider_key, user_id)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_user_cursors_lookup ON user_cursors(tenant_id, provider_key, user_id);

-- Add comment
COMMENT ON TABLE user_cursors IS 'Stores Microsoft Graph delta tokens for incremental email sync per user';

