-- ============================================================================
-- USER DASHBOARD PREFERENCES
-- ============================================================================
-- Allows each user to customize their dashboard with specific insights they care about
-- CEO can say: "Show me daily quality issues, weekly financials, top customer concerns"
-- System auto-generates these insights daily and renders custom sections
-- ============================================================================

-- User's custom dashboard configuration
CREATE TABLE IF NOT EXISTS user_dashboard_preferences (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,

    -- Dashboard metadata
    dashboard_name TEXT DEFAULT 'My Dashboard',
    description TEXT,

    -- Sections/widgets configuration
    sections JSONB NOT NULL DEFAULT '[]',
    -- Example structure:
    -- [
    --   {
    --     "id": "quality-alerts",
    --     "title": "Quality Issues",
    --     "position": 1,
    --     "size": "full",  // full, half, third
    --     "query_id": 123,  // references intelligence_search_queries
    --     "refresh_schedule": "daily_6am",
    --     "display_format": "list"  // list, table, chart, metric, text
    --   }
    -- ]

    -- Layout preferences
    layout_type TEXT DEFAULT 'grid', -- grid, list, kanban
    theme TEXT DEFAULT 'light',

    -- Scheduling
    auto_refresh_enabled BOOLEAN DEFAULT TRUE,
    refresh_time TIME DEFAULT '06:00:00',  -- 6 AM daily
    timezone TEXT DEFAULT 'America/Los_Angeles',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(tenant_id)
);

CREATE INDEX idx_dashboard_prefs_tenant ON user_dashboard_preferences(tenant_id);
CREATE INDEX idx_dashboard_prefs_refresh ON user_dashboard_preferences(auto_refresh_enabled, refresh_time) WHERE auto_refresh_enabled = true;

COMMENT ON TABLE user_dashboard_preferences IS 'User-customizable dashboard configuration. CEO defines what insights they want to see.';
COMMENT ON COLUMN user_dashboard_preferences.sections IS 'Array of dashboard sections/widgets. Each section links to a RAG query.';
COMMENT ON COLUMN user_dashboard_preferences.refresh_time IS 'What time daily to auto-generate insights (in tenant timezone)';


-- ============================================================================
-- CUSTOM DASHBOARD QUERIES
-- ============================================================================
-- User can create custom queries in natural language
-- System converts to RAG searches and stores structured results

CREATE TABLE IF NOT EXISTS user_custom_queries (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,

    -- The question the user wants answered
    query_text TEXT NOT NULL,
    display_title TEXT NOT NULL,

    -- How often to run it
    schedule TEXT NOT NULL, -- 'daily', 'weekly', 'monthly', 'hourly', 'on_demand'
    time_period TEXT DEFAULT 'daily', -- affects time context in RAG query

    -- How to display the answer
    output_format TEXT DEFAULT 'text', -- text, list, table, chart, metric
    output_schema JSONB,  -- JSON schema for structured outputs

    -- Query behavior
    priority INTEGER DEFAULT 5,
    max_sources INTEGER DEFAULT 5,
    is_active BOOLEAN DEFAULT TRUE,

    -- Icon and styling
    icon TEXT,
    color TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_run_at TIMESTAMPTZ,

    -- Link to query template (optional - if NULL, it's fully custom)
    template_id BIGINT REFERENCES intelligence_search_queries(id)
);

CREATE INDEX idx_custom_queries_tenant ON user_custom_queries(tenant_id);
CREATE INDEX idx_custom_queries_schedule ON user_custom_queries(schedule, is_active) WHERE is_active = true;

COMMENT ON TABLE user_custom_queries IS 'User-created custom queries. CEO asks questions in natural language, system runs them daily.';
COMMENT ON COLUMN user_custom_queries.query_text IS 'Natural language question. e.g., "What quality issues came up today?"';
COMMENT ON COLUMN user_custom_queries.output_format IS 'How to render the answer: text (prose), list (bullets), table, chart, metric (KPI)';


-- ============================================================================
-- INSIGHT SUBSCRIPTIONS
-- ============================================================================
-- Maps which insights appear on which dashboard sections

CREATE TABLE IF NOT EXISTS dashboard_insight_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,

    -- Which section of the dashboard
    section_id TEXT NOT NULL, -- e.g., "quality-alerts", "financial-summary"
    section_title TEXT NOT NULL,
    section_position INTEGER DEFAULT 0,
    section_size TEXT DEFAULT 'full', -- full, half, third

    -- Which query/insight to show
    query_id BIGINT REFERENCES intelligence_search_queries(id),
    custom_query_id BIGINT REFERENCES user_custom_queries(id),

    -- Display preferences for this section
    display_format TEXT DEFAULT 'auto', -- auto (use query's format), or override
    show_sources BOOLEAN DEFAULT TRUE,
    show_confidence BOOLEAN DEFAULT TRUE,
    expand_by_default BOOLEAN DEFAULT FALSE,

    -- Visibility
    is_visible BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- One of query_id or custom_query_id must be set
    CHECK (
        (query_id IS NOT NULL AND custom_query_id IS NULL) OR
        (query_id IS NULL AND custom_query_id IS NOT NULL)
    )
);

CREATE INDEX idx_subscriptions_tenant ON dashboard_insight_subscriptions(tenant_id);
CREATE INDEX idx_subscriptions_section ON dashboard_insight_subscriptions(tenant_id, section_id);
CREATE INDEX idx_subscriptions_position ON dashboard_insight_subscriptions(tenant_id, section_position);

COMMENT ON TABLE dashboard_insight_subscriptions IS 'Maps insights to dashboard sections. Defines which queries appear where on the dashboard.';


-- ============================================================================
-- DEFAULT DASHBOARD SETUP
-- ============================================================================
-- Give every new user a sensible default dashboard they can customize

-- Function to initialize default dashboard for new users
CREATE OR REPLACE FUNCTION create_default_dashboard(p_tenant_id TEXT)
RETURNS void AS $$
BEGIN
    -- Create default dashboard preferences
    INSERT INTO user_dashboard_preferences (tenant_id, dashboard_name, description, sections)
    VALUES (
        p_tenant_id,
        'Manufacturing Intelligence Dashboard',
        'Daily operations overview for plastic injection molding',
        '[
            {"id": "production", "title": "Production Summary", "position": 1, "size": "full"},
            {"id": "quality", "title": "Quality Alerts", "position": 2, "size": "half"},
            {"id": "financials", "title": "Financial Summary", "position": 3, "size": "half"},
            {"id": "machines", "title": "Machine Issues", "position": 4, "size": "half"},
            {"id": "customers", "title": "Customer Urgencies", "position": 5, "size": "half"}
        ]'::jsonb
    )
    ON CONFLICT (tenant_id) DO NOTHING;

    -- Subscribe to default daily insights
    -- Production Summary
    INSERT INTO dashboard_insight_subscriptions (
        tenant_id, section_id, section_title, section_position, section_size,
        query_id, is_visible
    )
    SELECT
        p_tenant_id, 'production', 'Production Summary', 1, 'full',
        id, true
    FROM intelligence_search_queries
    WHERE display_title = 'Production Summary' AND time_period = 'daily'
    ON CONFLICT DO NOTHING;

    -- Quality Alerts
    INSERT INTO dashboard_insight_subscriptions (
        tenant_id, section_id, section_title, section_position, section_size,
        query_id, is_visible
    )
    SELECT
        p_tenant_id, 'quality', 'Quality Alerts', 2, 'half',
        id, true
    FROM intelligence_search_queries
    WHERE display_title = 'Quality Alerts' AND time_period = 'daily'
    ON CONFLICT DO NOTHING;

    -- Financial Summary
    INSERT INTO dashboard_insight_subscriptions (
        tenant_id, section_id, section_title, section_position, section_size,
        query_id, is_visible
    )
    SELECT
        p_tenant_id, 'financials', 'Financial Summary', 3, 'half',
        id, true
    FROM intelligence_search_queries
    WHERE display_title = 'Financial Summary' AND time_period = 'daily'
    ON CONFLICT DO NOTHING;

    -- Machine Issues
    INSERT INTO dashboard_insight_subscriptions (
        tenant_id, section_id, section_title, section_position, section_size,
        query_id, is_visible
    )
    SELECT
        p_tenant_id, 'machines', 'Machine Issues', 4, 'half',
        id, true
    FROM intelligence_search_queries
    WHERE display_title = 'Machine Issues' AND time_period = 'daily'
    ON CONFLICT DO NOTHING;

    -- Customer Urgencies
    INSERT INTO dashboard_insight_subscriptions (
        tenant_id, section_id, section_title, section_position, section_size,
        query_id, is_visible
    )
    SELECT
        p_tenant_id, 'customers', 'Customer Urgencies', 5, 'half',
        id, true
    FROM intelligence_search_queries
    WHERE display_title = 'Customer Urgencies' AND time_period = 'daily'
    ON CONFLICT DO NOTHING;

END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION create_default_dashboard IS 'Initialize sensible default dashboard for new users';


-- ============================================================================
-- SCHEDULED REFRESH LOG
-- ============================================================================
-- Track when dashboards were auto-refreshed

CREATE TABLE IF NOT EXISTS dashboard_refresh_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,

    refresh_date DATE NOT NULL,
    refresh_time TIMESTAMPTZ DEFAULT NOW(),

    queries_run INTEGER DEFAULT 0,
    queries_succeeded INTEGER DEFAULT 0,
    queries_failed INTEGER DEFAULT 0,

    total_duration_ms INTEGER,

    status TEXT DEFAULT 'running', -- running, completed, failed
    error_message TEXT
);

CREATE INDEX idx_refresh_log_tenant ON dashboard_refresh_log(tenant_id, refresh_date DESC);
CREATE INDEX idx_refresh_log_status ON dashboard_refresh_log(status, refresh_time) WHERE status = 'running';

COMMENT ON TABLE dashboard_refresh_log IS 'Log of automated dashboard refresh runs (cron job history)';


-- ============================================================================
-- NOTES
-- ============================================================================
--
-- USER WORKFLOW:
--
-- 1. CEO logs in, sees default dashboard
-- 2. CEO clicks "Customize Dashboard" button
-- 3. Modal shows:
--    - "What do you want to see on your dashboard?"
--    - Text area: "Daily quality issues for plastic parts"
--    - Dropdown: "How often? Daily / Weekly / Monthly"
--    - Dropdown: "Display as: List / Table / Chart / Metric / Text"
-- 4. CEO adds multiple custom queries
-- 5. Drag/drop to reorder sections
-- 6. Set refresh time: "6:00 AM Pacific"
-- 7. Save
--
-- SYSTEM BEHAVIOR:
--
-- 1. Cron job runs daily at user's specified time
-- 2. Fetches all active queries for users scheduled at this hour
-- 3. Runs RAG searches for each query
-- 4. Stores structured results in intelligence_insights
-- 5. Dashboard auto-updates when user refreshes page
--
-- CEO sees exactly what they asked for, formatted how they want, updated automatically.
--
-- ============================================================================
