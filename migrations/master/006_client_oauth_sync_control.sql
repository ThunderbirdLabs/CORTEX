-- ============================================================================
-- Migration 006: Client OAuth + HighForce Sync Control
-- ============================================================================
-- Run this on MASTER Supabase
--
-- Purpose:
-- - Enable clients to reconnect OAuth connections (same email enforcement)
-- - HighForce controls historic sync execution via drag-drop scripts
-- - Complete audit trail for all connection/sync events
-- ============================================================================

-- 1. Track original OAuth connections (enforce same email on reconnect)
CREATE TABLE IF NOT EXISTS public.nango_original_connections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    tenant_id text NOT NULL,
    provider text NOT NULL, -- 'outlook', 'gmail', 'google_drive', 'quickbooks'
    original_email text NOT NULL,
    nango_connection_id text NOT NULL,
    connected_at timestamp with time zone DEFAULT now(),
    connected_by text, -- Admin email or 'client_self_service'
    last_reconnected_at timestamp with time zone,
    reconnection_count integer DEFAULT 0,
    CONSTRAINT nango_original_connections_unique UNIQUE(company_id, tenant_id, provider)
);

CREATE INDEX IF NOT EXISTS idx_nango_connections_lookup ON public.nango_original_connections(company_id, provider);
CREATE INDEX IF NOT EXISTS idx_nango_connections_nango_id ON public.nango_original_connections(nango_connection_id);

COMMENT ON TABLE public.nango_original_connections IS 'Tracks original OAuth email to enforce same-email reconnection policy';
COMMENT ON COLUMN public.nango_original_connections.original_email IS 'Email used during initial OAuth - reconnections must use same email';

-- 2. Historic sync jobs (scripts + execution tracking)
CREATE TABLE IF NOT EXISTS public.historic_sync_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    tenant_id text NOT NULL,
    provider text NOT NULL,

    -- Script
    script_name text NOT NULL,
    sync_script text NOT NULL, -- Python code to execute
    script_version integer DEFAULT 1,
    backfill_days integer,
    sync_config jsonb DEFAULT '{}'::jsonb, -- Additional config params

    -- Execution
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'queued', 'running', 'completed', 'failed', 'cancelled', 'timeout')),
    triggered_by text NOT NULL, -- Admin email who triggered it
    triggered_at timestamp with time zone DEFAULT now(),
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    duration_seconds integer, -- Calculated: completed_at - started_at

    -- Results
    items_synced integer,
    items_failed integer DEFAULT 0,
    items_skipped integer DEFAULT 0,
    error_message text,
    error_traceback text,

    -- Logs & Monitoring
    logs jsonb DEFAULT '[]'::jsonb, -- [{"timestamp": "...", "level": "info", "message": "..."}]
    progress_percentage integer DEFAULT 0 CHECK (progress_percentage BETWEEN 0 AND 100),
    last_progress_update timestamp with time zone,

    -- Completion Email
    completion_email_sent boolean DEFAULT false,
    completion_email_sent_at timestamp with time zone,

    -- Metadata
    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now(),
    metadata jsonb DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_historic_sync_jobs_company ON public.historic_sync_jobs(company_id, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_historic_sync_jobs_status ON public.historic_sync_jobs(status, triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_historic_sync_jobs_active ON public.historic_sync_jobs(company_id, status) WHERE status IN ('pending', 'queued', 'running');
CREATE INDEX IF NOT EXISTS idx_historic_sync_jobs_pending_email ON public.historic_sync_jobs(company_id) WHERE status = 'completed' AND completion_email_sent = false;

COMMENT ON TABLE public.historic_sync_jobs IS 'HighForce-controlled historic sync scripts with execution tracking and client notifications';
COMMENT ON COLUMN public.historic_sync_jobs.sync_script IS 'Python code executed by historic_sync_executor';
COMMENT ON COLUMN public.historic_sync_jobs.logs IS 'JSONB array of log entries with timestamps';

-- 3. Add client API key to company_deployments (for client apps to authenticate)
ALTER TABLE public.company_deployments
ADD COLUMN IF NOT EXISTS client_portal_api_key text;

COMMENT ON COLUMN public.company_deployments.client_portal_api_key IS 'API key for client apps to access managed connection portal (scoped to reconnect only)';

-- 4. Document new audit_log_global event types (no schema changes needed)
COMMENT ON COLUMN public.audit_log_global.action IS 'Event type - see migration 006 for connection/sync events: connection_created, connection_reconnected, connection_failed, historic_sync_triggered, historic_sync_completed, historic_sync_failed, connection_alert_sent';

-- ============================================================================
-- Example seed data (optional - for testing)
-- ============================================================================
-- Replace company_id with your actual company UUID

-- Example: Track an existing Outlook connection
-- INSERT INTO public.nango_original_connections (company_id, tenant_id, provider, original_email, nango_connection_id, connected_by)
-- VALUES ('2ede0765-6f69-4293-931d-22cc88437e01', 'user-123', 'outlook', 'john@company.com', 'nango-conn-456', 'admin@highforce.ai');

-- Example: Generate client API key for a company
-- UPDATE public.company_deployments
-- SET client_portal_api_key = 'hf_' || encode(gen_random_bytes(32), 'hex')
-- WHERE company_id = '2ede0765-6f69-4293-931d-22cc88437e01';
