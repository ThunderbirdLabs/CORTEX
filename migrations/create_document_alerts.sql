-- =====================================================
-- Real-Time Document Alerts System
-- =====================================================
-- This table stores urgent issues detected in documents
-- as they arrive, enabling real-time notifications and
-- faster response to critical business problems.

CREATE TABLE IF NOT EXISTS document_alerts (
    id BIGSERIAL PRIMARY KEY,

    -- Core references
    document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tenant_id TEXT NOT NULL,

    -- Alert classification
    alert_type TEXT NOT NULL, -- 'revenue_risk', 'customer_escalation', 'operational_issue', 'time_sensitive', 'financial'
    urgency_level TEXT NOT NULL, -- 'critical', 'high', 'medium', 'low'

    -- Alert content
    summary TEXT NOT NULL, -- One-sentence description of the issue
    key_entities JSONB DEFAULT '[]'::jsonb, -- Array of mentioned entities: customers, parts, amounts
    requires_action BOOLEAN DEFAULT true,

    -- Lifecycle tracking
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    dismissed_at TIMESTAMPTZ,
    dismissed_by TEXT,
    investigation_count INTEGER DEFAULT 0, -- How many times "Investigate" was clicked

    -- Metadata
    detection_confidence FLOAT, -- 0.0 - 1.0 confidence score from LLM
    llm_response JSONB, -- Full LLM response for debugging

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for fast queries
CREATE INDEX idx_document_alerts_tenant ON document_alerts(tenant_id);
CREATE INDEX idx_document_alerts_document ON document_alerts(document_id);
CREATE INDEX idx_document_alerts_urgency ON document_alerts(urgency_level) WHERE dismissed_at IS NULL;
CREATE INDEX idx_document_alerts_active ON document_alerts(tenant_id, detected_at DESC) WHERE dismissed_at IS NULL;
CREATE INDEX idx_document_alerts_type ON document_alerts(alert_type);

-- Enable RLS for multi-tenancy
ALTER TABLE document_alerts ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their own tenant's alerts
CREATE POLICY tenant_isolation_policy ON document_alerts
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE));

-- =====================================================
-- Enhance documents table with urgency fields
-- =====================================================

-- Add urgency tracking to documents table
ALTER TABLE documents
ADD COLUMN IF NOT EXISTS urgency_level TEXT,
ADD COLUMN IF NOT EXISTS alert_category TEXT,
ADD COLUMN IF NOT EXISTS entity_mentions JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS urgency_detected_at TIMESTAMPTZ;

-- Index for querying urgent documents
CREATE INDEX IF NOT EXISTS idx_documents_urgency ON documents(urgency_level) WHERE urgency_level IN ('critical', 'high');

-- =====================================================
-- Alert Statistics View
-- =====================================================

CREATE OR REPLACE VIEW alert_statistics AS
SELECT
    tenant_id,
    urgency_level,
    alert_type,
    COUNT(*) as total_alerts,
    COUNT(*) FILTER (WHERE dismissed_at IS NULL) as active_alerts,
    COUNT(*) FILTER (WHERE dismissed_at IS NOT NULL) as dismissed_alerts,
    AVG(EXTRACT(EPOCH FROM (COALESCE(dismissed_at, NOW()) - detected_at))) as avg_resolution_time_seconds,
    MAX(detected_at) as most_recent_alert
FROM document_alerts
GROUP BY tenant_id, urgency_level, alert_type;

-- =====================================================
-- Function: Get Active Alerts for Tenant
-- =====================================================

CREATE OR REPLACE FUNCTION get_active_alerts(
    p_tenant_id TEXT,
    p_urgency_filter TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    alert_id BIGINT,
    document_id BIGINT,
    document_title TEXT,
    document_source TEXT,
    alert_type TEXT,
    urgency_level TEXT,
    summary TEXT,
    key_entities JSONB,
    detected_at TIMESTAMPTZ,
    investigation_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        da.id,
        da.document_id,
        d.title,
        d.source,
        da.alert_type,
        da.urgency_level,
        da.summary,
        da.key_entities,
        da.detected_at,
        da.investigation_count
    FROM document_alerts da
    JOIN documents d ON da.document_id = d.id
    WHERE
        da.tenant_id = p_tenant_id
        AND da.dismissed_at IS NULL
        AND (p_urgency_filter IS NULL OR da.urgency_level = p_urgency_filter)
    ORDER BY
        CASE da.urgency_level
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
        END,
        da.detected_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Dismiss Alert
-- =====================================================

CREATE OR REPLACE FUNCTION dismiss_alert(
    p_alert_id BIGINT,
    p_tenant_id TEXT,
    p_dismissed_by TEXT DEFAULT NULL
)
RETURNS BOOLEAN AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE document_alerts
    SET
        dismissed_at = NOW(),
        dismissed_by = p_dismissed_by,
        updated_at = NOW()
    WHERE
        id = p_alert_id
        AND tenant_id = p_tenant_id
        AND dismissed_at IS NULL;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Increment Investigation Counter
-- =====================================================

CREATE OR REPLACE FUNCTION increment_investigation_count(
    p_alert_id BIGINT,
    p_tenant_id TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE document_alerts
    SET
        investigation_count = investigation_count + 1,
        updated_at = NOW()
    WHERE
        id = p_alert_id
        AND tenant_id = p_tenant_id;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Trigger: Update timestamp on document_alerts changes
-- =====================================================

CREATE OR REPLACE FUNCTION update_document_alerts_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER document_alerts_update_timestamp
    BEFORE UPDATE ON document_alerts
    FOR EACH ROW
    EXECUTE FUNCTION update_document_alerts_timestamp();

COMMENT ON TABLE document_alerts IS 'Real-time alerts for urgent issues detected in documents';
COMMENT ON COLUMN document_alerts.alert_type IS 'Category of alert: revenue_risk, customer_escalation, operational_issue, time_sensitive, financial';
COMMENT ON COLUMN document_alerts.urgency_level IS 'Severity: critical (immediate action), high (today), medium (this week), low (monitor)';
COMMENT ON COLUMN document_alerts.summary IS 'One-sentence description of the issue for dashboard display';
COMMENT ON COLUMN document_alerts.key_entities IS 'JSON array of extracted entities: customer names, part numbers, dollar amounts';
