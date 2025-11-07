-- ============================================================================
-- WIDGET-BASED DASHBOARD
-- ============================================================================
-- GPT fills pre-defined widget slots with relevant content
-- Each widget is visual, not text-heavy
-- GPT decides what goes where based on importance/relevance
-- ============================================================================

BEGIN;

-- Clear existing queries
DELETE FROM intelligence_search_queries;

-- Single query that returns widgets to fill
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
) VALUES (
    'Analyze today''s emails and documents for Unit Industries (plastic injection molding).

    Fill 6-8 dashboard widgets with the most relevant insights. Each widget should be:
    - VISUAL (not text-heavy)
    - SCANNABLE (quick to understand)
    - ACTIONABLE (CEO knows what to do)

    Widget types you can use:
    1. ALERT: Red banner for urgent issues (quality, customer complaint, machine down)
    2. STAT: Big number with context ($ amount, count, percentage)
    3. TREND: Small chart showing up/down (quality improving, delays increasing)
    4. SNAPSHOT: Quick status card (customer mood, production status, team activity)
    5. HIGHLIGHT: Good news or win (order closed, problem solved, milestone hit)

    For each widget:
    - Choose the right type based on the content
    - Keep it concise (1-2 sentences max)
    - Include 1-3 source quotes as proof
    - Mark urgency level

    Return widgets ordered by importance (most urgent/relevant first).

    CRITICAL: Only create widgets if there''s actual data. If nothing urgent happened, say "No alerts today" in a snapshot widget. Don''t make up content.',

    'widgets',
    'daily',
    'Dashboard Widgets',
    'layout-dashboard',
    1,
    9,
    15,
    'json',
    '{
        "type": "array",
        "max_items": 8,
        "items": {
            "widget_type": "alert|stat|trend|snapshot|highlight",
            "title": "string (2-4 words)",
            "content": {
                "alert": {
                    "message": "string (1-2 sentences)",
                    "severity": "critical|warning",
                    "action": "string (what to do)"
                },
                "stat": {
                    "value": "string (number or amount)",
                    "label": "string (what this is)",
                    "context": "string (why this matters)",
                    "trend": "up|down|neutral"
                },
                "trend": {
                    "direction": "up|down|flat",
                    "metric": "string (what we are tracking)",
                    "summary": "string (1 sentence)",
                    "data": "array of 3-7 values for mini chart"
                },
                "snapshot": {
                    "status": "good|neutral|concerning|critical",
                    "summary": "string (1-2 sentences)",
                    "details": "array of 2-4 bullet points"
                },
                "highlight": {
                    "message": "string (the good news)",
                    "impact": "string (why this is good)"
                }
            },
            "sources": [
                {
                    "quote": "string (exact quote)",
                    "from": "string (who said it)"
                }
            ],
            "urgency": "critical|high|medium|low"
        }
    }'::jsonb
);

COMMIT;

-- ============================================================================
-- EXAMPLE OUTPUT:
-- ============================================================================
--
-- [
--   {
--     "widget_type": "alert",
--     "title": "Material Shortage",
--     "content": {
--       "alert": {
--         "message": "23K lbs ULTEM resin delayed. Three customer orders blocked.",
--         "severity": "critical",
--         "action": "Expedite supplier shipment or notify customers"
--       }
--     },
--     "sources": [
--       {"quote": "23,000 units past due, material expected by 10/28", "from": "Production Email"},
--       {"quote": "Customer calling daily about NAS501 order", "from": "Sales Team"}
--     ],
--     "urgency": "critical"
--   },
--   {
--     "widget_type": "trend",
--     "title": "Quality Issues Rising",
--     "content": {
--       "trend": {
--         "direction": "up",
--         "metric": "Customer complaints",
--         "summary": "Flash defects reported by 3 different customers this week",
--         "data": [2, 3, 2, 4, 5, 6, 7]
--       }
--     },
--     "sources": [
--       {"quote": "51 pieces rejected due to excess material on locking tab", "from": "QC Report"}
--     ],
--     "urgency": "high"
--   },
--   {
--     "widget_type": "stat",
--     "title": "Revenue Today",
--     "content": {
--       "stat": {
--         "value": "$1,921.50",
--         "label": "Payment Received",
--         "context": "Customer invoice paid",
--         "trend": "neutral"
--       }
--     },
--     "sources": [
--       {"quote": "Payment of $1921.50 received", "from": "Accounting Email"}
--     ],
--     "urgency": "low"
--   },
--   {
--     "widget_type": "snapshot",
--     "title": "Customer Mood",
--     "content": {
--       "snapshot": {
--         "status": "concerning",
--         "summary": "Customer X tone shifted from collaborative to demanding this week",
--         "details": [
--           "Now CC''ing management on emails",
--           "Using phrases like ''need immediate resolution''",
--           "This is 3rd delay complaint"
--         ]
--       }
--     },
--     "sources": [
--       {"quote": "We need immediate resolution or will escalate internally", "from": "Customer X Email"}
--     ],
--     "urgency": "high"
--   },
--   {
--     "widget_type": "highlight",
--     "title": "Production Win",
--     "content": {
--       "highlight": {
--         "message": "All 3 machines ran at 95%+ capacity today",
--         "impact": "Caught up on backlog, ahead of schedule for weekly quota"
--       }
--     },
--     "sources": [
--       {"quote": "Shift 2 exceeded daily target by 400 units", "from": "Production Notes"}
--     ],
--     "urgency": "low"
--   },
--   {
--     "widget_type": "snapshot",
--     "title": "Team Activity",
--     "content": {
--       "snapshot": {
--         "status": "good",
--         "summary": "Production team focused on clearing ULTEM backlog",
--         "details": [
--           "QC doubled inspection on locking tabs",
--           "Maintenance scheduled mold cleaning",
--           "Sales following up with 5 customers"
--         ]
--       }
--     },
--     "sources": [
--       {"quote": "All hands on deck for ULTEM push this week", "from": "Manager Email"}
--     ],
--     "urgency": "medium"
--   }
-- ]
--
-- Dashboard renders these as visual widgets - not a wall of text
-- ============================================================================
