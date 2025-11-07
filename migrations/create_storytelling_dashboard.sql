-- ============================================================================
-- STORYTELLING INTELLIGENCE DASHBOARD
-- ============================================================================
-- One powerful query that tells the business story
-- GPT synthesizes across emails to connect dots and show what matters
-- ============================================================================

BEGIN;

-- Clear existing queries
DELETE FROM intelligence_search_queries;

-- ============================================================================
-- SINGLE STORYTELLING QUERY: Tell me the story of the business today
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
    'You are the CEO''s chief of staff. Analyze today''s emails and documents to create an executive intelligence briefing.

    Your job is to SYNTHESIZE information across multiple threads and CONNECT THE DOTS to tell the business story.

    Return 5-7 intelligence cards that answer: What does the CEO need to know RIGHT NOW to run the business today?

    For each insight:
    1. **SYNTHESIZE across emails** - Don''t just repeat one email. Connect related threads.
    2. **QUANTIFY impact** - Use dollar amounts, customer names, order numbers from the data
    3. **SHOW causality** - "X is happening BECAUSE Y, which means Z"
    4. **PRIORITIZE** - Most critical issues first (revenue at risk, customer churn, blocked deals)
    5. **BE SPECIFIC** - "Part 7020-9036 blocks $127K across 5 orders" not "delivery issues"

    EXAMPLES OF GREAT INSIGHTS:
    - "Engineering approval on Part 7020-9036 pending 14 days is blocking $127K revenue across 5 customer orders (Acme Corp $50K, WidgetCo $30K, others). This is root cause of all 7 backorders."
    - "3 customers (Acme, WidgetCo, GlobalTech) all cited late deliveries in last 2 days. Combined $180K ARR at risk if not resolved this week."
    - "Production team needs urgent decision: expedite material for $8K surcharge OR delay 5 orders. Customer deposits at risk."

    WIDGET TYPES TO USE:
    - "alert" for critical issues (revenue at risk, customer churn risk, blocked deals)
    - "trend" for patterns across multiple emails (delivery delays increasing, customer complaints rising)
    - "snapshot" for status updates (backorder count, approval queue depth)
    - "highlight" for wins (orders closed, problems solved)

    Format each as:
    {
      "widget_type": "alert|trend|snapshot|highlight",
      "title": "2-4 words",
      "message": "2-3 sentences connecting dots with specific numbers/names. First sentence is WHAT. Second is WHY IT MATTERS. Third is WHAT TO DO.",
      "urgency": "critical|high|medium|low",
      "sources": [
        {"quote": "exact quote", "document_id": "doc_id", "from": "email subject"}
      ]
    }

    CRITICAL RULES:
    - NO GENERIC STATEMENTS. Every insight must have specific data ($ amounts, customer names, part numbers)
    - SYNTHESIZE don''t summarize. Connect related emails to show the full picture
    - If there''s no important data today, return empty array
    - Order by business impact (revenue risk first, then customer risk, then operational issues)',

    'intelligence_brief',
    'daily',
    'Intelligence Brief',
    'brain',
    1,
    10,
    25,  -- More sources for synthesis
    'json',
    '{
        "type": "array",
        "items": {
            "widget_type": "alert|trend|snapshot|highlight",
            "title": "string (2-4 words)",
            "message": "string (2-3 sentences with specific $, names, part numbers)",
            "urgency": "critical|high|medium|low",
            "sources": [
                {
                    "quote": "string (exact quote from email)",
                    "document_id": "string",
                    "from": "string (email subject or doc title)"
                }
            ]
        }
    }'::jsonb
);

COMMIT;

-- ============================================================================
-- EXPECTED OUTPUT: 5-7 synthesized intelligence cards
-- Each one tells a story by connecting multiple emails
-- Each one has specific impact ($ or customer names)
-- Each one shows what matters and what to do
-- ============================================================================
