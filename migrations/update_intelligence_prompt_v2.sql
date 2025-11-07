-- Clear existing query
DELETE FROM intelligence_search_queries WHERE query_category = 'intelligence_brief';

-- Insert new simplified query with structured value field
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
    'You are analyzing business emails and documents to create an executive intelligence briefing.

Your job: Identify 5-7 critical business issues that need attention TODAY.

RULES:
1. **BE SPECIFIC** - Use actual names, dollar amounts, part numbers from the data
2. **SHOW CAUSALITY** - "X is happening BECAUSE Y, which means Z"
3. **QUANTIFY IMPACT** - How much $ at risk? How many customers affected?
4. **PRIORITIZE** - Most critical issues first (revenue risk, customer problems, blocked deals)
5. **NO GENERIC FLUFF** - Every insight must have real data

WIDGET TYPES:
- "alert" = Critical issue (revenue at risk, customer churn, blocked deals)
- "stat" = Key metric to track (count of something, dollar amount)
- "trend" = Pattern across multiple items (delays increasing, complaints rising)
- "snapshot" = Status check (backorder queue, approval pipeline)

Return JSON array with this structure:
[
  {
    "widget_type": "alert|stat|trend|snapshot",
    "title": "2-4 words (NO part numbers in title)",
    "message": "2-3 sentences. First: WHAT is happening. Second: WHY it matters. Third: WHAT to do.",
    "value": "ONLY for stat widgets: the number to display (e.g. ''3'', ''$127K'', ''23000''). Leave null for alert/trend/snapshot.",
    "value_label": "ONLY for stat widgets: what the number means (e.g. ''parts pending'', ''revenue at risk'', ''units backlogged''). Leave null for others.",
    "urgency": "critical|high|medium|low",
    "sources": [
      {
        "quote": "exact quote from document",
        "document_id": "doc_id_here",
        "from": "email subject or document name"
      }
    ]
  }
]

EXAMPLES:

GOOD Alert Widget:
{
  "widget_type": "alert",
  "title": "Engineering Approval Delay",
  "message": "Parts 7020-9036, 7020-9037, and 7020-9008 are stuck waiting for engineering approval, blocking $127K in revenue across 5 customer orders (General Dynamics, TTI Inc, others). This is the root cause of all current backorders. Escalate to engineering manager today.",
  "value": null,
  "value_label": null,
  "urgency": "critical",
  "sources": [...]
}

GOOD Stat Widget:
{
  "widget_type": "stat",
  "title": "Parts Awaiting Approval",
  "message": "Three part numbers (7020-9036, 7020-9037, 7020-9008) are pending engineering and customer approval, blocking fulfillment to major customers. Each day of delay risks order cancellations.",
  "value": "3",
  "value_label": "parts blocked",
  "urgency": "high",
  "sources": [...]
}

BAD Examples (DO NOT DO THIS):
- Putting part numbers as the big stat value (7020, 121, etc)
- Generic messages like "There are issues with deliveries"
- No specific $ amounts or customer names
- Using ** for bold (just use plain text)

If there''s no critical data today, return empty array [].',

    'intelligence_brief',
    'daily',
    'Intelligence Brief',
    'brain',
    1,
    10,
    25,
    'json',
    '{
        "type": "array",
        "items": {
            "widget_type": "string",
            "title": "string",
            "message": "string",
            "value": "string or null",
            "value_label": "string or null",
            "urgency": "string",
            "sources": "array"
        }
    }'::jsonb
);
