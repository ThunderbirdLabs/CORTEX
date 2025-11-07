-- Fix permissions for get_active_alerts function
-- Run this if alerts API returns empty even though function exists

-- Grant execute permission to anon and authenticated roles
GRANT EXECUTE ON FUNCTION get_active_alerts(TEXT, TEXT, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION get_active_alerts(TEXT, TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION get_active_alerts(TEXT, TEXT, INTEGER) TO service_role;

-- Verify the function exists and has correct signature
SELECT
    proname as function_name,
    pg_get_function_arguments(oid) as arguments,
    prokind as kind,
    prosecdef as security_definer
FROM pg_proc
WHERE proname = 'get_active_alerts';

-- Test the function with your tenant_id
SELECT * FROM get_active_alerts('23e4af88-7df0-4ca4-9e60-fc2a12569a93', NULL, 10);
