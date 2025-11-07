-- =====================================================
-- Saved Reports System
-- =====================================================
-- Allows users to save drill-down reports for later access
-- Supports reports from widgets, alerts, and manual queries

CREATE TABLE IF NOT EXISTS saved_reports (
    id BIGSERIAL PRIMARY KEY,

    -- Core references
    tenant_id TEXT NOT NULL,

    -- Report metadata
    title TEXT NOT NULL,
    report_type TEXT NOT NULL, -- 'widget_drilldown', 'alert_investigation', 'manual_query'
    description TEXT, -- User-provided description/notes

    -- Report content (full JSON from drill-down generation)
    report_data JSONB NOT NULL, -- Complete report with executive_summary, impact, root_cause, etc.

    -- Source context (what generated this report)
    source_widget_title TEXT, -- Original widget title if from widget
    source_widget_message TEXT, -- Original widget message
    source_alert_id BIGINT REFERENCES document_alerts(id) ON DELETE SET NULL, -- If from alert investigation
    source_query TEXT, -- If from manual search

    -- User interaction
    is_starred BOOLEAN DEFAULT false, -- User favorite
    tags TEXT[] DEFAULT '{}', -- User-defined tags for organization
    shared_with TEXT[] DEFAULT '{}', -- Tenant IDs this report is shared with

    -- Lifecycle
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_viewed_at TIMESTAMPTZ,
    view_count INTEGER DEFAULT 0

);

-- Indexes for fast queries
CREATE INDEX idx_saved_reports_tenant ON saved_reports(tenant_id);
CREATE INDEX idx_saved_reports_created ON saved_reports(tenant_id, created_at DESC);
CREATE INDEX idx_saved_reports_starred ON saved_reports(tenant_id, is_starred) WHERE is_starred = true;
CREATE INDEX idx_saved_reports_type ON saved_reports(report_type);
CREATE INDEX idx_saved_reports_alert ON saved_reports(source_alert_id) WHERE source_alert_id IS NOT NULL;
CREATE INDEX idx_saved_reports_tags ON saved_reports USING gin(tags); -- For tag-based search

-- Enable RLS for multi-tenancy
ALTER TABLE saved_reports ENABLE ROW LEVEL SECURITY;

-- Policy: users can only see their own tenant's reports (or reports shared with them)
CREATE POLICY tenant_isolation_policy ON saved_reports
    FOR ALL
    USING (
        tenant_id = current_setting('app.current_tenant_id', TRUE)
        OR current_setting('app.current_tenant_id', TRUE) = ANY(shared_with)
    );

-- =====================================================
-- Report Statistics View
-- =====================================================

CREATE OR REPLACE VIEW report_statistics AS
SELECT
    tenant_id,
    report_type,
    COUNT(*) as total_reports,
    COUNT(*) FILTER (WHERE is_starred) as starred_count,
    SUM(view_count) as total_views,
    MAX(created_at) as most_recent_report,
    AVG(view_count) as avg_views_per_report
FROM saved_reports
GROUP BY tenant_id, report_type;

-- =====================================================
-- Function: Save Report
-- =====================================================

CREATE OR REPLACE FUNCTION save_report(
    p_tenant_id TEXT,
    p_title TEXT,
    p_report_type TEXT,
    p_report_data JSONB,
    p_description TEXT DEFAULT NULL,
    p_source_widget_title TEXT DEFAULT NULL,
    p_source_widget_message TEXT DEFAULT NULL,
    p_source_alert_id BIGINT DEFAULT NULL,
    p_source_query TEXT DEFAULT NULL,
    p_tags TEXT[] DEFAULT '{}'
)
RETURNS BIGINT AS $$
DECLARE
    v_report_id BIGINT;
BEGIN
    INSERT INTO saved_reports (
        tenant_id,
        title,
        report_type,
        description,
        report_data,
        source_widget_title,
        source_widget_message,
        source_alert_id,
        source_query,
        tags
    ) VALUES (
        p_tenant_id,
        p_title,
        p_report_type,
        p_description,
        p_report_data,
        p_source_widget_title,
        p_source_widget_message,
        p_source_alert_id,
        p_source_query,
        p_tags
    )
    RETURNING id INTO v_report_id;

    RETURN v_report_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Get User Reports
-- =====================================================

CREATE OR REPLACE FUNCTION get_user_reports(
    p_tenant_id TEXT,
    p_report_type TEXT DEFAULT NULL,
    p_starred_only BOOLEAN DEFAULT false,
    p_limit INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    report_id BIGINT,
    title TEXT,
    report_type TEXT,
    description TEXT,
    created_at TIMESTAMPTZ,
    last_viewed_at TIMESTAMPTZ,
    view_count INTEGER,
    is_starred BOOLEAN,
    tags TEXT[],
    source_widget_title TEXT,
    source_alert_id BIGINT,
    report_summary TEXT -- Extract executive_summary from report_data
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sr.id,
        sr.title,
        sr.report_type,
        sr.description,
        sr.created_at,
        sr.last_viewed_at,
        sr.view_count,
        sr.is_starred,
        sr.tags,
        sr.source_widget_title,
        sr.source_alert_id,
        (sr.report_data->>'executive_summary')::TEXT
    FROM saved_reports sr
    WHERE
        sr.tenant_id = p_tenant_id
        AND (p_report_type IS NULL OR sr.report_type = p_report_type)
        AND (NOT p_starred_only OR sr.is_starred = true)
    ORDER BY sr.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Update Report View
-- =====================================================

CREATE OR REPLACE FUNCTION update_report_view(
    p_report_id BIGINT,
    p_tenant_id TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE saved_reports
    SET
        last_viewed_at = NOW(),
        view_count = view_count + 1,
        updated_at = NOW()
    WHERE
        id = p_report_id
        AND tenant_id = p_tenant_id;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Toggle Star
-- =====================================================

CREATE OR REPLACE FUNCTION toggle_report_star(
    p_report_id BIGINT,
    p_tenant_id TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_new_state BOOLEAN;
BEGIN
    UPDATE saved_reports
    SET
        is_starred = NOT is_starred,
        updated_at = NOW()
    WHERE
        id = p_report_id
        AND tenant_id = p_tenant_id
    RETURNING is_starred INTO v_new_state;

    RETURN v_new_state;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Update Report Tags
-- =====================================================

CREATE OR REPLACE FUNCTION update_report_tags(
    p_report_id BIGINT,
    p_tenant_id TEXT,
    p_tags TEXT[]
)
RETURNS BOOLEAN AS $$
DECLARE
    v_updated INTEGER;
BEGIN
    UPDATE saved_reports
    SET
        tags = p_tags,
        updated_at = NOW()
    WHERE
        id = p_report_id
        AND tenant_id = p_tenant_id;

    GET DIAGNOSTICS v_updated = ROW_COUNT;
    RETURN v_updated > 0;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Delete Report
-- =====================================================

CREATE OR REPLACE FUNCTION delete_report(
    p_report_id BIGINT,
    p_tenant_id TEXT
)
RETURNS BOOLEAN AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM saved_reports
    WHERE
        id = p_report_id
        AND tenant_id = p_tenant_id;

    GET DIAGNOSTICS v_deleted = ROW_COUNT;
    RETURN v_deleted > 0;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Function: Search Reports
-- =====================================================

CREATE OR REPLACE FUNCTION search_reports(
    p_tenant_id TEXT,
    p_search_term TEXT,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    report_id BIGINT,
    title TEXT,
    report_type TEXT,
    description TEXT,
    created_at TIMESTAMPTZ,
    is_starred BOOLEAN,
    tags TEXT[],
    relevance_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sr.id,
        sr.title,
        sr.report_type,
        sr.description,
        sr.created_at,
        sr.is_starred,
        sr.tags,
        -- Simple relevance scoring based on text matching
        CASE
            WHEN sr.title ILIKE '%' || p_search_term || '%' THEN 3.0
            WHEN sr.description ILIKE '%' || p_search_term || '%' THEN 2.0
            WHEN p_search_term = ANY(sr.tags) THEN 2.5
            WHEN (sr.report_data->>'executive_summary')::TEXT ILIKE '%' || p_search_term || '%' THEN 1.5
            ELSE 1.0
        END as score
    FROM saved_reports sr
    WHERE
        sr.tenant_id = p_tenant_id
        AND (
            sr.title ILIKE '%' || p_search_term || '%'
            OR sr.description ILIKE '%' || p_search_term || '%'
            OR p_search_term = ANY(sr.tags)
            OR (sr.report_data->>'executive_summary')::TEXT ILIKE '%' || p_search_term || '%'
        )
    ORDER BY score DESC, sr.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Trigger: Update timestamp on saved_reports changes
-- =====================================================

CREATE OR REPLACE FUNCTION update_saved_reports_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER saved_reports_update_timestamp
    BEFORE UPDATE ON saved_reports
    FOR EACH ROW
    EXECUTE FUNCTION update_saved_reports_timestamp();

COMMENT ON TABLE saved_reports IS 'User-saved drill-down reports for later access';
COMMENT ON COLUMN saved_reports.report_type IS 'Source: widget_drilldown, alert_investigation, manual_query';
COMMENT ON COLUMN saved_reports.report_data IS 'Full JSON report with executive_summary, impact, root_cause, timeline, recommendations, etc.';
COMMENT ON COLUMN saved_reports.tags IS 'User-defined tags for organization (e.g. customer_issues, revenue, operations)';
COMMENT ON COLUMN saved_reports.shared_with IS 'Tenant IDs this report is shared with (for team collaboration)';
