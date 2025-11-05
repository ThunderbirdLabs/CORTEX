-- ============================================================================
-- MULTI-TIERED ORGANIZATIONAL INTELLIGENCE SYSTEM
-- ============================================================================
-- Creates tables for storing pre-computed daily, weekly, and monthly
-- aggregations to provide time-based context layers for search and analytics.
--
-- Philosophy: Store raw data in documents table, pre-compute temporal
-- aggregations for fast retrieval and strategic insights.
-- ============================================================================

-- ============================================================================
-- DAILY INTELLIGENCE (24-hour activity snapshots)
-- ============================================================================
-- Generated nightly at midnight via cron job
-- Captures: document counts, entity activity, key events, AI summary

CREATE TABLE IF NOT EXISTS daily_intelligence (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    date DATE NOT NULL,

    -- Document activity metrics
    total_documents INTEGER DEFAULT 0,
    document_counts JSONB DEFAULT '{}',  -- {"email": 45, "invoice": 12, "bill": 3}

    -- QuickBooks financial metrics (if applicable)
    invoice_total_amount DECIMAL(12,2),
    invoice_outstanding_balance DECIMAL(12,2),
    bill_total_amount DECIMAL(12,2),
    payment_total_amount DECIMAL(12,2),

    -- Entity activity (top entities mentioned)
    most_active_people JSONB DEFAULT '[]',  -- [{"name": "Alex", "mentions": 15}, ...]
    most_active_companies JSONB DEFAULT '[]',  -- [{"name": "Acme Corp", "mentions": 8}, ...]
    new_entities JSONB DEFAULT '[]',  -- Entities first seen today

    -- Communication patterns
    email_senders JSONB DEFAULT '[]',  -- Top email senders
    email_recipients JSONB DEFAULT '[]',  -- Top email recipients

    -- Key topics/themes (extracted from content)
    key_topics JSONB DEFAULT '[]',  -- [{"topic": "pricing negotiation", "count": 5}, ...]

    -- AI-generated summary
    ai_summary TEXT,  -- Natural language daily summary
    key_insights JSONB DEFAULT '[]',  -- [{"insight": "...", "confidence": 0.9}, ...]

    -- Metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_duration_ms INTEGER,  -- Performance tracking

    UNIQUE(tenant_id, date)
);

CREATE INDEX idx_daily_intelligence_tenant ON daily_intelligence(tenant_id);
CREATE INDEX idx_daily_intelligence_date ON daily_intelligence(date DESC);
CREATE INDEX idx_daily_intelligence_tenant_date ON daily_intelligence(tenant_id, date DESC);

COMMENT ON TABLE daily_intelligence IS 'Pre-computed daily activity snapshots for fast retrieval and trend analysis';
COMMENT ON COLUMN daily_intelligence.document_counts IS 'Document type breakdown: {"email": 45, "invoice": 12, "pdf": 3}';
COMMENT ON COLUMN daily_intelligence.most_active_people IS 'Top 10 people by mention count with metadata';
COMMENT ON COLUMN daily_intelligence.key_topics IS 'Extracted themes/topics from content';


-- ============================================================================
-- WEEKLY INTELLIGENCE (7-day trend analysis)
-- ============================================================================
-- Generated every Monday at 1am via cron job
-- Captures: weekly trends, pattern recognition, momentum indicators

CREATE TABLE IF NOT EXISTS weekly_intelligence (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    week_start DATE NOT NULL,  -- Monday of the week
    week_end DATE NOT NULL,  -- Sunday of the week

    -- Activity trends (week-over-week comparison)
    total_documents INTEGER DEFAULT 0,
    document_trend JSONB DEFAULT '{}',  -- Daily counts: {"2025-11-04": 23, "2025-11-05": 47, ...}
    wow_change_percent DECIMAL(5,2),  -- Week-over-week % change

    -- Entity growth and evolution
    total_unique_entities INTEGER DEFAULT 0,
    new_entities_count INTEGER DEFAULT 0,
    new_entities JSONB DEFAULT '[]',  -- Entities discovered this week

    -- Trending entities (increasing mentions)
    trending_people JSONB DEFAULT '[]',  -- [{"name": "Sarah", "mentions": 25, "trend": "up"}, ...]
    trending_companies JSONB DEFAULT '[]',  -- Companies gaining attention
    trending_topics JSONB DEFAULT '[]',  -- Topics/keywords trending up

    -- Relationship evolution
    new_relationships JSONB DEFAULT '[]',  -- [{"from": "Person A", "to": "Company B", "type": "WORKS_FOR"}, ...]
    collaboration_patterns JSONB DEFAULT '[]',  -- [{"people": ["A", "B"], "frequency": 5}, ...]

    -- Business momentum indicators
    deals_advancing JSONB DEFAULT '[]',  -- Deals/projects progressing
    deals_stalling JSONB DEFAULT '[]',  -- Deals/projects losing momentum

    -- Financial trends (if QuickBooks connected)
    weekly_revenue DECIMAL(12,2),
    weekly_expenses DECIMAL(12,2),
    revenue_trend JSONB DEFAULT '[]',  -- Daily revenue: [{"date": "2025-11-04", "amount": 5000}, ...]

    -- AI-generated analysis
    weekly_summary TEXT,  -- Natural language weekly summary
    key_insights JSONB DEFAULT '[]',  -- Strategic insights
    action_items JSONB DEFAULT '[]',  -- Recommended actions

    -- Metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_duration_ms INTEGER,

    UNIQUE(tenant_id, week_start)
);

CREATE INDEX idx_weekly_intelligence_tenant ON weekly_intelligence(tenant_id);
CREATE INDEX idx_weekly_intelligence_week ON weekly_intelligence(week_start DESC);
CREATE INDEX idx_weekly_intelligence_tenant_week ON weekly_intelligence(tenant_id, week_start DESC);

COMMENT ON TABLE weekly_intelligence IS 'Pre-computed weekly trend analysis and pattern recognition';
COMMENT ON COLUMN weekly_intelligence.wow_change_percent IS 'Week-over-week percentage change in activity';
COMMENT ON COLUMN weekly_intelligence.trending_people IS 'People with increasing mention frequency';
COMMENT ON COLUMN weekly_intelligence.deals_advancing IS 'Opportunities/projects showing positive momentum';


-- ============================================================================
-- MONTHLY INTELLIGENCE (30-day strategic insights)
-- ============================================================================
-- Generated on 1st of each month at 2am via cron job
-- Captures: strategic metrics, expertise evolution, goal alignment

CREATE TABLE IF NOT EXISTS monthly_intelligence (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    month DATE NOT NULL,  -- First day of month (e.g., 2025-11-01)

    -- Monthly activity summary
    total_documents INTEGER DEFAULT 0,
    total_emails INTEGER DEFAULT 0,
    total_invoices INTEGER DEFAULT 0,
    total_bills INTEGER DEFAULT 0,
    total_payments INTEGER DEFAULT 0,

    -- Financial summary (QuickBooks)
    total_revenue DECIMAL(12,2),
    total_expenses DECIMAL(12,2),
    net_income DECIMAL(12,2),
    revenue_by_customer JSONB DEFAULT '[]',  -- [{"customer": "Acme", "revenue": 50000}, ...]
    expense_by_category JSONB DEFAULT '[]',  -- [{"category": "Materials", "amount": 25000}, ...]

    -- Entity evolution
    total_unique_entities INTEGER DEFAULT 0,
    new_entities_this_month INTEGER DEFAULT 0,
    most_active_entities JSONB DEFAULT '[]',  -- Top 20 entities by mention count

    -- Expertise development (who's becoming expert in what)
    expertise_evolution JSONB DEFAULT '[]',  -- [{"person": "Sarah", "domain": "Quality Control", "activity_level": "high"}, ...]

    -- Relationship health
    key_relationships JSONB DEFAULT '[]',  -- [{"from": "Person", "to": "Company", "strength": 0.9}, ...]
    collaboration_networks JSONB DEFAULT '[]',  -- Team collaboration patterns

    -- Strategic alignment
    goal_alignment_score DECIMAL(3,2),  -- 0.0 to 1.0 score
    initiative_effectiveness JSONB DEFAULT '[]',  -- [{"initiative": "Manufacturing Expansion", "status": "on_track"}, ...]

    -- Month-over-month trends
    mom_document_change_percent DECIMAL(5,2),
    mom_revenue_change_percent DECIMAL(5,2),
    mom_entity_growth_percent DECIMAL(5,2),

    -- AI-generated executive summary
    executive_summary TEXT,  -- High-level monthly summary for executives
    strategic_insights JSONB DEFAULT '[]',  -- [{"insight": "...", "priority": "high"}, ...]
    recommendations JSONB DEFAULT '[]',  -- [{"recommendation": "...", "rationale": "..."}, ...]

    -- Organizational health indicators
    communication_health_score DECIMAL(3,2),  -- Email/collab activity score
    financial_health_score DECIMAL(3,2),  -- Revenue/expense health
    growth_momentum_score DECIMAL(3,2),  -- Overall growth indicator

    -- Metadata
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    computation_duration_ms INTEGER,

    UNIQUE(tenant_id, month)
);

CREATE INDEX idx_monthly_intelligence_tenant ON monthly_intelligence(tenant_id);
CREATE INDEX idx_monthly_intelligence_month ON monthly_intelligence(month DESC);
CREATE INDEX idx_monthly_intelligence_tenant_month ON monthly_intelligence(tenant_id, month DESC);

COMMENT ON TABLE monthly_intelligence IS 'Pre-computed monthly strategic insights and executive summaries';
COMMENT ON COLUMN monthly_intelligence.expertise_evolution IS 'Tracks who is becoming expert in which domains based on activity';
COMMENT ON COLUMN monthly_intelligence.goal_alignment_score IS 'Score indicating how well daily activities align with strategic goals';
COMMENT ON COLUMN monthly_intelligence.executive_summary IS 'AI-generated high-level summary for executives';


-- ============================================================================
-- HELPER FUNCTIONS (Optional - for easier querying)
-- ============================================================================

-- Function to get latest daily intelligence for a tenant
CREATE OR REPLACE FUNCTION get_latest_daily_intelligence(p_tenant_id TEXT)
RETURNS TABLE (
    date DATE,
    total_documents INTEGER,
    ai_summary TEXT,
    computed_at TIMESTAMPTZ
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        di.date,
        di.total_documents,
        di.ai_summary,
        di.computed_at
    FROM daily_intelligence di
    WHERE di.tenant_id = p_tenant_id
    ORDER BY di.date DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to get trend data for past N days
CREATE OR REPLACE FUNCTION get_daily_trend(p_tenant_id TEXT, p_days INTEGER DEFAULT 30)
RETURNS TABLE (
    date DATE,
    total_documents INTEGER,
    invoice_total DECIMAL(12,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        di.date,
        di.total_documents,
        di.invoice_total_amount
    FROM daily_intelligence di
    WHERE di.tenant_id = p_tenant_id
        AND di.date >= CURRENT_DATE - p_days
    ORDER BY di.date DESC;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- GRANTS (Adjust based on your security model)
-- ============================================================================

-- Grant appropriate permissions (modify based on your RLS policy)
-- GRANT SELECT, INSERT, UPDATE ON daily_intelligence TO authenticated;
-- GRANT SELECT, INSERT, UPDATE ON weekly_intelligence TO authenticated;
-- GRANT SELECT, INSERT, UPDATE ON monthly_intelligence TO authenticated;


-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. All JSONB columns use default '{}' or '[]' to avoid NULL handling
-- 2. Multi-tenant isolation via tenant_id (add RLS policies if needed)
-- 3. Indexes optimized for common query patterns (tenant + date DESC)
-- 4. Computation duration tracking for performance monitoring
-- 5. Helper functions provided for common queries
-- 6. Foreign key to documents table NOT added (denormalized for speed)
-- 7. No cascading deletes (intelligence data independent of raw documents)
-- ============================================================================
