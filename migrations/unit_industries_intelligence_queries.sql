-- ============================================================================
-- UNIT INDUSTRIES - MANUFACTURING-SPECIFIC INTELLIGENCE QUERIES
-- ============================================================================
-- Replaces generic business queries with manufacturing-focused insights
-- Adds structured JSON outputs for charts, tables, lists, and metrics
-- ============================================================================

-- First, run the structured insights migration if not already done
-- This adds output_format and output_schema columns
\i migrations/add_structured_insights_format.sql

-- ============================================================================
-- CLEAR EXISTING GENERIC QUERIES
-- ============================================================================

DELETE FROM intelligence_search_queries WHERE query_category IN ('deals', 'customers', 'issues', 'opportunities', 'summary', 'people', 'trends', 'recommendations');

-- ============================================================================
-- UNIT INDUSTRIES DAILY INTELLIGENCE (Manufacturing Operations Focus)
-- ============================================================================

INSERT INTO intelligence_search_queries (
    query_text,
    query_category,
    time_period,
    display_title,
    display_icon,
    display_order,
    priority,
    max_sources,
    output_format,
    output_schema
) VALUES

-- 1. Daily Production Summary (TEXT format - conversational overview)
(
    'Summarize today''s production activity for our plastic injection molding operations. Focus on: mold runs, machine issues, part quality, cycle times, material usage, and any production delays or shutdowns.',
    'production',
    'daily',
    'Production Summary',
    'package',
    1,
    8,
    8,
    'text',
    NULL
),

-- 2. Urgent Quality Issues (LIST format - prioritized list)
(
    'List the top 5 most urgent quality issues or defects in plastic parts mentioned today. Focus on: flash, short shots, sink marks, warpage, color inconsistency, dimensional issues, surface defects, or contamination. Include: defect type, which part/mold, which customer, severity, and root cause if known.',
    'quality',
    'daily',
    'Quality Alerts',
    'alert-triangle',
    2,
    9,
    6,
    'list',
    '{
        "type": "array",
        "max_items": 5,
        "items": {
            "title": "string (defect type - e.g., Flash on housing part)",
            "priority": "high|medium|low",
            "description": "string (what is defective and why)",
            "affected": "string (customer name and part number)",
            "source": "string (who found it - QC, customer, production)"
        }
    }'::jsonb
),

-- 3. Critical Machine Issues (LIST format - equipment problems)
(
    'List any injection molding machine failures, breakdowns, maintenance issues, or tooling problems mentioned today. For each: machine number, problem description, parts affected, downtime estimate, and repair status.',
    'machines',
    'daily',
    'Machine Issues',
    'tool',
    3,
    9,
    5,
    'list',
    '{
        "type": "array",
        "max_items": 10,
        "items": {
            "machine": "string (machine ID/number)",
            "problem": "string (what failed or malfunctioned)",
            "impact": "string (which parts/customers affected)",
            "downtime": "string (hours/days of downtime)",
            "status": "down|repairing|fixed|scheduled"
        }
    }'::jsonb
),

-- 4. Financial Metrics (METRIC format - money numbers)
(
    'Extract key financial information from today: revenue from shipments, invoice amounts, payment received, accounts receivable, material costs, or any quoted prices. Report actual dollar amounts mentioned.',
    'financials',
    'daily',
    'Financial Summary',
    'dollar-sign',
    4,
    8,
    6,
    'metric',
    '{
        "metrics": [
            {
                "label": "string (e.g., Invoices Sent, Payments Received)",
                "value": "number (actual dollar amount)",
                "unit": "$",
                "trend": "up|down|flat|unknown",
                "change": "string (vs last period if known)"
            }
        ]
    }'::jsonb
),

-- 5. Urgent Customer Issues (LIST format - customer complaints/demands)
(
    'List urgent customer issues, complaints, rush orders, or escalations mentioned today. For each: customer name, issue type, description, urgency, and required action.',
    'customers',
    'daily',
    'Customer Urgencies',
    'alert-circle',
    5,
    9,
    5,
    'list',
    '{
        "type": "array",
        "max_items": 8,
        "items": {
            "customer": "string",
            "issue_type": "complaint|rush_order|quality_issue|payment|other",
            "description": "string",
            "urgency": "critical|high|medium",
            "action_required": "string"
        }
    }'::jsonb
),

-- 6. Material/Resin Issues (LIST format - raw material problems)
(
    'List any issues with plastic resin, raw materials, or material shortages mentioned today. Include: material type, supplier, problem, affected parts, and status.',
    'materials',
    'daily',
    'Material Issues',
    'package',
    6,
    8,
    5,
    'list',
    '{
        "type": "array",
        "max_items": 8,
        "items": {
            "material": "string (resin type/color)",
            "supplier": "string",
            "problem": "string (shortage, quality, price, delivery)",
            "impact": "string (which parts affected)",
            "status": "string"
        }
    }'::jsonb
);

-- ============================================================================
-- UNIT INDUSTRIES WEEKLY INTELLIGENCE (Trends & Analysis)
-- ============================================================================

INSERT INTO intelligence_search_queries (
    query_text,
    query_category,
    time_period,
    display_title,
    display_icon,
    display_order,
    priority,
    max_sources,
    output_format,
    output_schema
) VALUES

-- 1. Weekly Production Trend (CHART format - daily production over week)
(
    'Track daily production activity this week. For each day, estimate production volume, quality issues count, and customer orders received. Format as time series data for charting.',
    'production',
    'weekly',
    'Weekly Production Trend',
    'trending-up',
    1,
    9,
    10,
    'chart',
    '{
        "chart_type": "line",
        "x_axis": {
            "type": "date",
            "label": "Day"
        },
        "y_axes": [
            {
                "type": "number",
                "label": "Activity Level"
            }
        ],
        "datasets": [
            {
                "label": "Production Activity",
                "data": "array of {date: YYYY-MM-DD, value: number}",
                "color": "#3b82f6"
            },
            {
                "label": "Quality Issues",
                "data": "array of {date: YYYY-MM-DD, value: number}",
                "color": "#ef4444"
            },
            {
                "label": "New Orders",
                "data": "array of {date: YYYY-MM-DD, value: number}",
                "color": "#10b981"
            }
        ]
    }'::jsonb
),

-- 2. Top Quality Concerns (LIST with severity)
(
    'What are the recurring quality issues or patterns this week? List top issues with: issue type, frequency (how many times mentioned), severity, affected products, and recommended actions.',
    'quality',
    'weekly',
    'Recurring Quality Issues',
    'alert-circle',
    2,
    9,
    8,
    'list',
    '{
        "type": "array",
        "max_items": 7,
        "items": {
            "issue_type": "string",
            "frequency": "number (how many times this week)",
            "severity": "critical|high|medium|low",
            "affected_products": "string",
            "recommendation": "string"
        }
    }'::jsonb
),

-- 3. Customer Activity Summary (TABLE with metrics)
(
    'Summarize customer activity this week. For each active customer: name, number of orders, total value (if mentioned), issues raised, and relationship status (improving/stable/declining).',
    'customers',
    'weekly',
    'Customer Activity',
    'briefcase',
    3,
    8,
    8,
    'table',
    '{
        "columns": ["Customer", "Orders", "Value", "Issues", "Trend"],
        "column_types": ["text", "number", "currency", "number", "badge"],
        "sortable": true,
        "rows": "array of arrays"
    }'::jsonb
),

-- 4. On-Time Delivery Performance (METRIC with breakdown)
(
    'What is our on-time delivery performance this week? Report: percentage of orders shipped on time, number of delayed orders, main delay reasons, and comparison to last week.',
    'logistics',
    'weekly',
    'Delivery Performance',
    'truck',
    4,
    8,
    6,
    'metric',
    '{
        "primary_metric": {
            "label": "On-Time Delivery Rate",
            "value": "number (percentage)",
            "unit": "%",
            "trend": "up|down|flat",
            "change": "string (vs last week)"
        },
        "secondary_metrics": [
            {
                "label": "Delayed Orders",
                "value": "number"
            },
            {
                "label": "Main Delay Reason",
                "value": "string"
            }
        ]
    }'::jsonb
),

-- 5. Wins & Successes (LIST of positive developments)
(
    'What went well this week? List production wins, new customer orders, quality improvements, efficiency gains, or positive feedback.',
    'wins',
    'weekly',
    'Wins This Week',
    'check-circle',
    5,
    7,
    8,
    'list',
    '{
        "type": "array",
        "max_items": 10,
        "items": {
            "title": "string",
            "description": "string",
            "impact": "string",
            "category": "production|quality|customer|efficiency"
        }
    }'::jsonb
);

-- ============================================================================
-- UNIT INDUSTRIES MONTHLY INTELLIGENCE (Strategic Overview)
-- ============================================================================

INSERT INTO intelligence_search_queries (
    query_text,
    query_category,
    time_period,
    display_title,
    display_icon,
    display_order,
    priority,
    max_sources,
    output_format,
    output_schema
) VALUES

-- 1. Monthly Executive Summary (TEXT format)
(
    'Provide a comprehensive executive summary of this month''s manufacturing operations. Cover: production volume, quality performance, customer satisfaction, major issues resolved, and key strategic developments.',
    'summary',
    'monthly',
    'Executive Summary',
    'file-text',
    1,
    9,
    15,
    'text',
    NULL
),

-- 2. Top Customers by Activity (TABLE ranked)
(
    'Rank customers by activity level this month. For each: customer name, number of orders, estimated total value, quality issues count, and overall relationship health (excellent/good/concerning).',
    'customers',
    'monthly',
    'Top Customers',
    'star',
    2,
    8,
    10,
    'table',
    '{
        "columns": ["Rank", "Customer", "Orders", "Est. Value", "Issues", "Health"],
        "column_types": ["number", "text", "number", "currency", "number", "badge"],
        "sortable": true,
        "rows": "array of arrays ranked by activity"
    }'::jsonb
),

-- 3. Quality Metrics Trend (CHART showing improvement/decline)
(
    'Track monthly quality metrics. Show: scrap rate, defect rate, customer complaints, and rework hours as a trend over the past 3 months (if data available).',
    'quality',
    'monthly',
    'Quality Metrics',
    'bar-chart',
    3,
    9,
    12,
    'chart',
    '{
        "chart_type": "bar",
        "x_axis": {
            "type": "category",
            "label": "Month",
            "categories": "array of month names"
        },
        "y_axes": [
            {
                "type": "percentage",
                "label": "Rate (%)"
            }
        ],
        "datasets": [
            {
                "label": "Scrap Rate",
                "data": "array of numbers",
                "color": "#ef4444"
            },
            {
                "label": "Defect Rate",
                "data": "array of numbers",
                "color": "#f59e0b"
            },
            {
                "label": "Rework %",
                "data": "array of numbers",
                "color": "#eab308"
            }
        ]
    }'::jsonb
),

-- 4. Production Efficiency Metrics (METRIC dashboard)
(
    'Report key production efficiency metrics for this month: overall equipment effectiveness (OEE), capacity utilization, cycle time improvements, and cost per unit (if mentioned).',
    'efficiency',
    'monthly',
    'Efficiency Metrics',
    'zap',
    4,
    8,
    8,
    'metric',
    '{
        "metrics": [
            {
                "label": "OEE",
                "value": "number",
                "unit": "%",
                "trend": "up|down|flat",
                "target": "number (target value)"
            },
            {
                "label": "Capacity Utilization",
                "value": "number",
                "unit": "%",
                "trend": "up|down|flat"
            },
            {
                "label": "Avg Cycle Time",
                "value": "number",
                "unit": "hours|days",
                "trend": "up|down|flat",
                "change": "string"
            }
        ]
    }'::jsonb
),

-- 5. Strategic Focus Areas (LIST of priorities)
(
    'Based on this month''s operations, what should be the top 5 focus areas for next month? List: focus area, rationale, expected impact, and suggested actions.',
    'strategy',
    'monthly',
    'Next Month Priorities',
    'target',
    5,
    9,
    10,
    'list',
    '{
        "type": "array",
        "max_items": 5,
        "items": {
            "focus_area": "string",
            "rationale": "string (why this is important)",
            "expected_impact": "string",
            "suggested_actions": "string"
        }
    }'::jsonb
),

-- 6. Major Supplier Performance (TABLE)
(
    'Evaluate supplier performance this month. For each major supplier: name, on-time delivery rate, quality issues count, lead time, and overall rating.',
    'suppliers',
    'monthly',
    'Supplier Performance',
    'package',
    6,
    8,
    8,
    'table',
    '{
        "columns": ["Supplier", "On-Time %", "Quality Issues", "Lead Time", "Rating"],
        "column_types": ["text", "percentage", "number", "text", "badge"],
        "sortable": true,
        "rows": "array of arrays"
    }'::jsonb
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_search_queries_output_format ON intelligence_search_queries(output_format);
CREATE INDEX IF NOT EXISTS idx_insights_structured ON intelligence_insights(tenant_id, time_period) WHERE structured_data IS NOT NULL;

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON COLUMN intelligence_search_queries.output_format IS 'Format type: text (prose), list (array), table (rows/cols), chart (time series/bar), metric (KPI dashboard)';
COMMENT ON COLUMN intelligence_search_queries.output_schema IS 'JSON schema defining exact structure GPT must return. Query prompt enforces this.';
COMMENT ON COLUMN intelligence_insights.structured_data IS 'Parsed JSON matching output_schema. Frontend renders based on output_format.';

-- ============================================================================
-- NOTES FOR UNIT INDUSTRIES
-- ============================================================================
--
-- This migration creates manufacturing-specific intelligence queries with:
--
-- 1. DAILY INSIGHTS (6 queries):
--    - Production Summary (text)
--    - Quality Alerts (list with priority)
--    - Active Orders (table with status)
--    - Production Metrics (KPI numbers)
--    - Supplier Issues (list)
--    - Team Activity (list)
--
-- 2. WEEKLY INSIGHTS (5 queries):
--    - Production Trend Chart (line chart)
--    - Recurring Quality Issues (prioritized list)
--    - Customer Activity Table (sortable)
--    - Delivery Performance (KPI with breakdown)
--    - Wins This Week (positive highlights)
--
-- 3. MONTHLY INSIGHTS (6 queries):
--    - Executive Summary (prose)
--    - Top Customers (ranked table)
--    - Quality Metrics Chart (trend over 3 months)
--    - Efficiency Metrics (KPI dashboard)
--    - Next Month Priorities (strategic focus)
--    - Supplier Performance (scorecard table)
--
-- TOTAL: 17 manufacturing-specific intelligence queries
--
-- Each query specifies exact JSON schema that GPT must follow.
-- Frontend can then render:
--   - Lists with badges/priorities
--   - Sortable tables
--   - Line/bar charts
--   - KPI metric cards
--   - Prose text
--
-- ============================================================================
