-- Helper function to get unique tenant IDs for admin dashboard
CREATE OR REPLACE FUNCTION get_unique_tenant_ids()
RETURNS TABLE (tenant_id TEXT) AS $$
BEGIN
  RETURN QUERY
  SELECT DISTINCT d.tenant_id
  FROM documents d
  ORDER BY d.tenant_id;
END;
$$ LANGUAGE plpgsql;
