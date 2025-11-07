-- ============================================================================
-- SMART NEWSLETTER APPROACH
-- ============================================================================
-- Instead of asking specific questions, ask GPT to curate what matters
-- GPT decides what's relevant and formats each insight as a visual element
-- ============================================================================

BEGIN;

-- Clear existing queries
DELETE FROM intelligence_search_queries;

-- Single smart query that returns a curated newsletter
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
    'Analyze all my emails and documents from today for Unit Industries (plastic injection molding manufacturer).

    You are curating a daily executive newsletter. Extract 4-8 insights that actually matter to the CEO.

    For each insight, determine the best visual format:
    - STAT: A single important number (revenue, units produced, defect rate, etc) with context
    - ALERT: Something urgent that needs attention (quality issue, customer complaint, machine down)
    - TREND: A pattern or change over time (use if you have data from multiple days)
    - LIST: Multiple related items (top customers, pending orders, upcoming deadlines)
    - SUMMARY: Important context that doesn''t fit other formats

    CRITICAL: Only include insights if there''s actual data. If there''s no production data today, don''t make up a "Production Summary". If there are no quality issues, skip that section entirely.

    Each insight must have:
    - type: "stat" | "alert" | "trend" | "list" | "summary"
    - title: Short, compelling headline (e.g., "Material Shortage Blocking Production")
    - content: The actual data/information
    - priority: "high" | "medium" | "low" (high = needs immediate action)
    - sources: Which emails/docs this came from

    Format your response as JSON array of insights, ordered by priority.',

    'newsletter',
    'daily',
    'Daily Intelligence',
    'newspaper',
    1,
    9,
    20,
    'json',
    '{
        "type": "array",
        "items": {
            "type": "stat|alert|trend|list|summary",
            "title": "string (compelling headline)",
            "priority": "high|medium|low",
            "content": {
                "stat": {
                    "value": "number or string",
                    "unit": "string (optional)",
                    "context": "string (what this means)",
                    "change": "string (vs yesterday/last week)",
                    "trend": "up|down|flat"
                },
                "alert": {
                    "severity": "critical|warning|info",
                    "description": "string",
                    "impact": "string (who/what is affected)",
                    "action_needed": "string"
                },
                "trend": {
                    "metric": "string (what we are tracking)",
                    "direction": "up|down|flat",
                    "data_points": "array of {date, value}",
                    "insight": "string (what the trend means)"
                },
                "list": {
                    "items": "array of {label, value, detail}",
                    "total": "number (optional)"
                },
                "summary": {
                    "text": "string (2-3 sentences max)"
                }
            },
            "source_count": "number",
            "confidence": "number (0.0-1.0)"
        }
    }'::jsonb
);

COMMIT;

-- ============================================================================
-- EXAMPLE OUTPUT GPT WOULD RETURN:
-- ============================================================================
--
-- [
--   {
--     "type": "alert",
--     "title": "Material Shortage Delaying ULTEM Parts",
--     "priority": "high",
--     "content": {
--       "alert": {
--         "severity": "warning",
--         "description": "23,000 ULTEM 1000 units are past due. Material expected by 10/28.",
--         "impact": "NAS501-3-3A production blocked, customer shipment at risk",
--         "action_needed": "Expedite material order or notify customer of delay"
--       }
--     },
--     "source_count": 3,
--     "confidence": 0.89
--   },
--   {
--     "type": "stat",
--     "title": "Revenue Received Today",
--     "priority": "medium",
--     "content": {
--       "stat": {
--         "value": 1921.50,
--         "unit": "$",
--         "context": "Payment received from customer",
--         "change": null,
--         "trend": null
--       }
--     },
--     "source_count": 1,
--     "confidence": 1.0
--   },
--   {
--     "type": "alert",
--     "title": "Quality Rejection: Locking Tab Defect",
--     "priority": "high",
--     "content": {
--       "alert": {
--         "severity": "critical",
--         "description": "51 pieces rejected due to excess material on locking tab",
--         "impact": "Production yield reduced, scrap cost ~$X",
--         "action_needed": "Root cause analysis required, adjust mold parameters"
--       }
--     },
--     "source_count": 2,
--     "confidence": 0.92
--   },
--   {
--     "type": "list",
--     "title": "Top Material Costs Today",
--     "priority": "low",
--     "content": {
--       "list": {
--         "items": [
--           {"label": "COV-PRTHD (MERLIN)", "value": "$6,140", "detail": "Raw material"},
--           {"label": "MAIN_TRAY (MERLIN)", "value": "$22.82/unit", "detail": "Quoted price"}
--         ],
--         "total": 2
--       }
--     },
--     "source_count": 2,
--     "confidence": 0.85
--   }
-- ]
--
-- GPT decides what matters, formats it visually, skips irrelevant stuff.
-- Frontend renders each based on type: stat cards, alert banners, trend charts, lists.
-- ============================================================================
