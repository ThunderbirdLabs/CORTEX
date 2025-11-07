-- ============================================================================
-- 3 BUSINESS INTELLIGENCE QUESTIONS (3 widgets each = 9 total)
-- ============================================================================
-- Clean, simple widget approach with clickable sources
-- ============================================================================

BEGIN;

-- Clear existing queries
DELETE FROM intelligence_search_queries;

-- ============================================================================
-- QUESTION 1: Most Urgent Issues (returns 3 widgets)
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
) VALUES (
    'What are the 3 most urgent issues that came up in communications today that need leadership attention?

    Return exactly 3 widgets highlighting fires that need putting out, emerging problems, or operational stress points.

    IMPORTANT - Mix visualization types for visual variety:
    - First widget: Use "alert" widget_type (critical issues with severity bars)
    - Second widget: Use "snapshot" widget_type (status update with circular progress)
    - Third widget: Use "trend" widget_type (pattern with bar chart)

    For each widget:
    - Keep title short (2-4 words)
    - Keep message concise (1-2 sentences)
    - Include 1-2 source quotes with document IDs
    - Mark urgency: critical, high, medium, or low

    CRITICAL: Only create widgets if real issues exist in the data.',

    'urgent_issues',
    'daily',
    'Urgent Issues',
    'alert-triangle',
    1,
    10,
    15,
    'json',
    '{
        "type": "array",
        "items": {
            "widget_type": "alert|stat|trend|snapshot|highlight",
            "title": "string (2-4 words)",
            "message": "string (1-2 sentences)",
            "urgency": "critical|high|medium|low",
            "sources": [
                {
                    "quote": "string",
                    "document_id": "string",
                    "from": "string (email subject or doc title)"
                }
            ]
        }
    }'::jsonb
);

-- ============================================================================
-- QUESTION 2: Deal & Project Momentum (returns 3 widgets)
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
) VALUES (
    'Which deals, projects, or initiatives moved forward or backward today, and what caused the change?

    Return exactly 3 widgets showing business momentum, pipeline health, and what''s driving results.

    IMPORTANT - Mix visualization types:
    - First widget: Use "stat" widget_type (big numbers like revenue, deal count)
    - Second widget: Use "highlight" widget_type (wins with sparkline chart)
    - Third widget: Use "snapshot" widget_type (status with circular progress)

    For each widget:
    - Keep title short (2-4 words)
    - Keep message concise (1-2 sentences)
    - Include 1-2 source quotes with document IDs
    - Mark urgency based on business impact

    CRITICAL: Only create widgets if real deal/project activity exists.',

    'momentum',
    'daily',
    'Deals & Projects',
    'trending-up',
    2,
    9,
    15,
    'json',
    '{
        "type": "array",
        "items": {
            "widget_type": "alert|stat|trend|snapshot|highlight",
            "title": "string (2-4 words)",
            "message": "string (1-2 sentences)",
            "urgency": "critical|high|medium|low",
            "sources": [
                {
                    "quote": "string",
                    "document_id": "string",
                    "from": "string"
                }
            ]
        }
    }'::jsonb
);

-- ============================================================================
-- QUESTION 3: Bottlenecks & Blockers (returns 3 widgets)
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
) VALUES (
    'What decisions are people waiting on, and what information do they need to move forward?

    Return exactly 3 widgets revealing bottlenecks, leadership needs, and information gaps.

    IMPORTANT - Mix visualization types:
    - First widget: Use "trend" widget_type (patterns in blockers with bar chart)
    - Second widget: Use "alert" widget_type (critical blocker needing attention)
    - Third widget: Use "snapshot" widget_type (current status with progress ring)

    For each widget:
    - Keep title short (2-4 words)
    - Keep message concise (1-2 sentences)
    - Include 1-2 source quotes with document IDs
    - Mark urgency based on blocker severity

    CRITICAL: Only create widgets if real blockers exist in communications.',

    'bottlenecks',
    'daily',
    'Bottlenecks',
    'alert-circle',
    3,
    8,
    15,
    'json',
    '{
        "type": "array",
        "items": {
            "widget_type": "alert|stat|trend|snapshot|highlight",
            "title": "string (2-4 words)",
            "message": "string (1-2 sentences)",
            "urgency": "critical|high|medium|low",
            "sources": [
                {
                    "quote": "string",
                    "document_id": "string",
                    "from": "string"
                }
            ]
        }
    }'::jsonb
);

COMMIT;

-- ============================================================================
-- EXPECTED OUTPUT: 9 widgets total (3 per query)
-- ============================================================================
