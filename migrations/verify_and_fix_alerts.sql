-- =====================================================
-- Verify and Fix Alerts System
-- =====================================================
-- Run this in Supabase SQL Editor to check and fix any issues
-- =====================================================

-- Step 1: Check if get_active_alerts function exists
SELECT
    proname as function_name,
    prokind as kind,
    pg_get_functiondef(oid) as definition
FROM pg_proc
WHERE proname = 'get_active_alerts';

-- If the above returns no rows, the function is missing.
-- Run the create_document_alerts.sql migration to create it.

-- Step 2: Check if alerts exist in database
SELECT
    COUNT(*) as total_alerts,
    COUNT(CASE WHEN dismissed_at IS NULL THEN 1 END) as active_alerts,
    COUNT(CASE WHEN urgency_level = 'critical' THEN 1 END) as critical_count,
    COUNT(CASE WHEN urgency_level = 'high' THEN 1 END) as high_count
FROM document_alerts
WHERE tenant_id = '23e4af88-7df0-4ca4-9e60-fc2a12569a93';

-- Step 3: Check RLS status
SELECT
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables
WHERE tablename = 'document_alerts';

-- Step 4: Test the function manually
SELECT * FROM get_active_alerts(
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    NULL,
    10
);

-- Step 5: If function is missing, here's a standalone version:
-- (Copy and run this if the function doesn't exist)

CREATE OR REPLACE FUNCTION get_active_alerts(
    p_tenant_id TEXT,
    p_urgency_filter TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    alert_id BIGINT,
    document_id BIGINT,
    document_title TEXT,
    document_source TEXT,
    alert_type TEXT,
    urgency_level TEXT,
    summary TEXT,
    key_entities JSONB,
    detected_at TIMESTAMPTZ,
    investigation_count INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        da.id,
        da.document_id,
        d.title,
        d.source,
        da.alert_type,
        da.urgency_level,
        da.summary,
        da.key_entities,
        da.detected_at,
        da.investigation_count
    FROM document_alerts da
    JOIN documents d ON da.document_id = d.id
    WHERE da.tenant_id = p_tenant_id
      AND da.dismissed_at IS NULL
      AND (p_urgency_filter IS NULL OR da.urgency_level = p_urgency_filter)
    ORDER BY
        CASE da.urgency_level
            WHEN 'critical' THEN 1
            WHEN 'high' THEN 2
            WHEN 'medium' THEN 3
            WHEN 'low' THEN 4
        END,
        da.detected_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Done! Now try accessing your /alerts page again
