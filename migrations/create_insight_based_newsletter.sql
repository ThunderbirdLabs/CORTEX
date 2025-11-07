-- ============================================================================
-- INSIGHT-BASED NEWSLETTER (NOT NUMBERS)
-- ============================================================================
-- Focus on trends, patterns, observations - not exact numbers
-- Every insight must show the exact source emails/docs it came from
-- CEO can click to verify the reasoning
-- ============================================================================

BEGIN;

-- Clear existing queries
DELETE FROM intelligence_search_queries;

-- Single query that returns insights with sources
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
    'You are analyzing emails and documents for Unit Industries (plastic injection molding manufacturer) from today.

    Create a daily intelligence briefing with 5-8 INSIGHTS (not numbers).

    Focus on:
    - TRENDS: "Quality issues seem to be increasing" or "Customer complaints are down"
    - PATTERNS: "Multiple emails mention material shortages" or "Same defect appearing in different parts"
    - OBSERVATIONS: "Customer X is frustrated based on tone" or "Team is waiting on supplier Y"
    - CONTEXT: "This order is urgent because..." or "This issue connects to last week''s problem"
    - RISKS: "If this continues, we might..." or "This could impact..."

    DO NOT:
    - Extract exact numbers unless they are clearly stated (e.g., "Invoice for $5,000")
    - Make up metrics or percentages
    - Be overly confident about things that are unclear

    For each insight, you MUST:
    1. State the insight clearly
    2. Explain your reasoning
    3. Rate your confidence (high/medium/low)
    4. Reference which specific emails/docs led you to this conclusion

    Format each insight as:
    - type: "trend" | "pattern" | "observation" | "risk" | "update"
    - title: Short headline (e.g., "Material Shortage Pattern Detected")
    - insight: The actual observation (2-3 sentences)
    - reasoning: Why you think this (1-2 sentences)
    - confidence: "high" | "medium" | "low"
    - urgency: "critical" | "high" | "medium" | "low"
    - source_snippets: Array of exact quotes from emails that support this

    Return as JSON array of insights.',

    'insights',
    'daily',
    'Daily Intelligence Briefing',
    'brain',
    1,
    9,
    20,
    'json',
    '{
        "type": "array",
        "items": {
            "type": "trend|pattern|observation|risk|update",
            "title": "string (compelling headline)",
            "insight": "string (the observation, 2-3 sentences)",
            "reasoning": "string (why you think this, 1-2 sentences)",
            "confidence": "high|medium|low",
            "urgency": "critical|high|medium|low",
            "source_snippets": [
                {
                    "text": "string (exact quote from email/doc)",
                    "from": "string (sender or doc name)",
                    "date": "string (when this was sent/created)",
                    "context": "string (brief context about this source)"
                }
            ],
            "suggested_action": "string (optional - what CEO should do about this)"
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
--     "type": "pattern",
--     "title": "Multiple Customers Mentioning Same Defect",
--     "insight": "Three different customers this week have reported flash on locking tabs. This is the same defect across different part numbers, suggesting a mold temperature or pressure issue rather than part-specific problems.",
--     "reasoning": "The defect type (flash) and location (locking tabs) are identical in emails from customers A, B, and C. This pattern indicates a systemic process issue.",
--     "confidence": "high",
--     "urgency": "high",
--     "source_snippets": [
--       {
--         "text": "We are rejecting 51 pieces due to excess material on the locking tab",
--         "from": "QC Report - Part XYZ",
--         "date": "Nov 7, 2025",
--         "context": "Internal quality control inspection"
--       },
--       {
--         "text": "Customer complained about flash on tabs, requesting credit",
--         "from": "Email from Sales Rep",
--         "date": "Nov 6, 2025",
--         "context": "Customer complaint forwarded from field"
--       },
--       {
--         "text": "Same issue on part ABC - flash buildup on locking mechanism",
--         "from": "Production Notes",
--         "date": "Nov 5, 2025",
--         "context": "Shift supervisor notes"
--       }
--     ],
--     "suggested_action": "Audit all mold temperature and injection pressure settings. Consider bringing in mold technician to inspect tooling."
--   },
--   {
--     "type": "risk",
--     "title": "ULTEM Material Delay Could Impact November Shipments",
--     "insight": "We are waiting on 23,000 lbs of ULTEM 1000 resin that was supposed to arrive last week. Three customer orders for ULTEM parts are already past due. If material doesn''t arrive by 10/28, we will miss November shipment commitments.",
--     "reasoning": "Multiple emails reference the same material shortage and link it to specific customer orders. Dates mentioned indicate increasing urgency.",
--     "confidence": "high",
--     "urgency": "critical",
--     "source_snippets": [
--       {
--         "text": "23,000 units past due, material expected by 10/28",
--         "from": "Production Planning Email",
--         "date": "Nov 7, 2025",
--         "context": "Production scheduler update"
--       },
--       {
--         "text": "Customer calling daily about NAS501-3-3A order - we need to give them a date",
--         "from": "Sales Team Email",
--         "date": "Nov 6, 2025",
--         "context": "Customer service follow-up"
--       }
--     ],
--     "suggested_action": "Contact supplier for expedited shipping OR notify affected customers of delay with revised ship dates."
--   },
--   {
--     "type": "observation",
--     "title": "Customer Tone Shifting from Neutral to Frustrated",
--     "insight": "Emails from Customer X have become noticeably more terse and demanding over the past week. They are now CC''ing their management and using phrases like ''need immediate resolution'' and ''escalating internally.''",
--     "reasoning": "Comparing email tone from last week (collaborative, understanding) to this week (short, demanding, management copied). This suggests growing frustration.",
--     "confidence": "medium",
--     "urgency": "high",
--     "source_snippets": [
--       {
--         "text": "We need immediate resolution on this quality issue or we will need to escalate internally",
--         "from": "Email from Customer X Buyer",
--         "date": "Nov 7, 2025",
--         "context": "Email CC''ing their VP of Operations"
--       },
--       {
--         "text": "This is the third delay - please provide firm commitment date",
--         "from": "Email from Customer X",
--         "date": "Nov 6, 2025",
--         "context": "Response to our delay notification"
--       }
--     ],
--     "suggested_action": "Schedule call with Customer X to address concerns. Consider offering expedited shipping or credit for delays."
--   },
--   {
--     "type": "trend",
--     "title": "Production Delays Mentioned in 5 of 8 Customer Conversations",
--     "insight": "Over half of customer emails this week reference delivery delays or requests for status updates. This is higher than normal and suggests we are falling behind on commitments.",
--     "reasoning": "Pattern recognition across multiple customer threads - all asking about ship dates or expressing concern about delays.",
--     "confidence": "high",
--     "urgency": "medium",
--     "source_snippets": [
--       {
--         "text": "When can we expect shipment? Original date was last week",
--         "from": "Customer Y Email",
--         "date": "Nov 7, 2025",
--         "context": "Order follow-up"
--       },
--       {
--         "text": "Need updated ETA for PO 12345",
--         "from": "Customer Z Email",
--         "date": "Nov 6, 2025",
--         "context": "Status request"
--       }
--     ],
--     "suggested_action": "Review production schedule and communicate realistic dates to all affected customers proactively."
--   }
-- ]
--
-- KEY DIFFERENCES FROM PREVIOUS APPROACH:
-- - No exact numbers unless clearly stated in source
-- - Focus on "seems to be" / "appears that" / "suggests" language
-- - ALWAYS show source snippets so CEO can verify
-- - Confidence levels are honest (medium/low when uncertain)
-- - Insights are about patterns, not metrics
-- ============================================================================
