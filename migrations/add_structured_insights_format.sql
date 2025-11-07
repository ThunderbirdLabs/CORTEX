-- ============================================================================
-- ADD STRUCTURED OUTPUT FORMATS FOR INSIGHTS
-- ============================================================================
-- Allows insights to return structured JSON for charts, lists, tables, etc.
-- Frontend can then render the appropriate UI component

-- Add output format configuration to queries
ALTER TABLE intelligence_search_queries
ADD COLUMN IF NOT EXISTS output_format TEXT DEFAULT 'text' CHECK (output_format IN ('text', 'list', 'table', 'chart', 'metric', 'json')),
ADD COLUMN IF NOT EXISTS output_schema JSONB DEFAULT NULL;

-- Add structured_data field to store parsed JSON responses
ALTER TABLE intelligence_insights
ADD COLUMN IF NOT EXISTS structured_data JSONB DEFAULT NULL;

COMMENT ON COLUMN intelligence_search_queries.output_format IS 'Expected output format: text (prose), list (array), table (rows/cols), chart (data points), metric (number), json (custom)';
COMMENT ON COLUMN intelligence_search_queries.output_schema IS 'JSON schema defining expected structure. GPT will be forced to return this exact format.';
COMMENT ON COLUMN intelligence_insights.structured_data IS 'Parsed JSON data when output_format != text. Used for rendering charts/tables/etc.';

-- Example structured query configurations
COMMENT ON COLUMN intelligence_search_queries.output_schema IS 'Example schemas:
-- LIST: {"type": "array", "items": {"title": "string", "priority": "string", "description": "string"}}
-- TABLE: {"columns": ["name", "value", "change"], "rows": [["Q1", 100, "+5%"]]}
-- CHART: {"labels": ["Mon", "Tue"], "datasets": [{"label": "Revenue", "data": [100, 150]}]}
-- METRIC: {"value": 1234, "unit": "$", "change": "+5%", "trend": "up"}
';

-- Update some example queries to use structured formats

-- Top 5 Urgent Items (LIST format)
UPDATE intelligence_search_queries
SET
    output_format = 'list',
    output_schema = '{
        "type": "array",
        "items": {
            "title": "string",
            "priority": "high|medium|low",
            "description": "string",
            "source": "string"
        },
        "max_items": 5
    }'::jsonb
WHERE query_text LIKE '%urgent%' OR query_text LIKE '%issues%' OR query_text LIKE '%concerns%';

-- Financial/Revenue metrics (METRIC format)
UPDATE intelligence_search_queries
SET
    output_format = 'metric',
    output_schema = '{
        "value": "number",
        "unit": "string",
        "label": "string",
        "change_percent": "number",
        "trend": "up|down|flat",
        "comparison": "string"
    }'::jsonb
WHERE query_category = 'financial' OR query_text LIKE '%revenue%' OR query_text LIKE '%sales%';

-- Deal tracking (TABLE format)
UPDATE intelligence_search_queries
SET
    output_format = 'table',
    output_schema = '{
        "columns": ["Deal Name", "Status", "Value", "Next Step"],
        "rows": "array of arrays matching columns"
    }'::jsonb
WHERE query_category = 'deals' AND (query_text LIKE '%progress%' OR query_text LIKE '%stall%');
