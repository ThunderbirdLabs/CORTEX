-- Sync Jobs Table
-- Tracks background sync job status for Gmail, Drive, Outlook
-- Allows users to check progress of long-running operations

CREATE TABLE IF NOT EXISTS sync_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    job_type TEXT NOT NULL, -- 'gmail', 'drive', 'outlook'
    status TEXT NOT NULL DEFAULT 'queued', -- 'queued', 'running', 'completed', 'failed'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    result JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_sync_jobs_user ON sync_jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_status ON sync_jobs(status);
CREATE INDEX IF NOT EXISTS idx_sync_jobs_created ON sync_jobs(created_at DESC);

-- Comments for documentation
COMMENT ON TABLE sync_jobs IS 'Background sync job tracking for async operations';
COMMENT ON COLUMN sync_jobs.job_type IS 'Type of sync: gmail, drive, outlook';
COMMENT ON COLUMN sync_jobs.status IS 'Job status: queued, running, completed, failed';
COMMENT ON COLUMN sync_jobs.result IS 'JSON result from completed job (messages_synced, errors, etc)';

