-- Add Nango cursor tracking table
-- This stores cursors locally so we can recover if Nango goes down
-- Based on Nango's recommendation to store cursors in your own database

CREATE TABLE IF NOT EXISTS nango_sync_cursors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    sync_name VARCHAR(100) NOT NULL,
    connection_id VARCHAR(255) NOT NULL,
    last_cursor TEXT,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    records_synced INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(provider, sync_name, connection_id)
);

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_nango_cursors_provider_sync ON nango_sync_cursors(provider, sync_name);
CREATE INDEX IF NOT EXISTS idx_nango_cursors_connection ON nango_sync_cursors(connection_id);

-- Add comments
COMMENT ON TABLE nango_sync_cursors IS 'Stores Nango sync cursors locally for recovery if Nango goes down';
COMMENT ON COLUMN nango_sync_cursors.last_cursor IS 'The cursor from the last successfully synced record (_nango_metadata.cursor)';
COMMENT ON COLUMN nango_sync_cursors.last_sync_at IS 'Timestamp of last successful sync';
COMMENT ON COLUMN nango_sync_cursors.records_synced IS 'Total number of records synced';
