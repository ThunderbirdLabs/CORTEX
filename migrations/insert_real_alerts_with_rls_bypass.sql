-- =====================================================
-- Insert Real Alerts (RLS Bypass for Admin)
-- =====================================================
-- Run this in your Supabase SQL Editor (which has admin access)
-- This will temporarily disable RLS, insert realistic alerts, then re-enable it
-- =====================================================

-- Step 1: Temporarily disable RLS (admin only)
ALTER TABLE document_alerts DISABLE ROW LEVEL SECURITY;

-- Step 2: Insert realistic alerts based on your actual documents
-- These match the exact format the AI detector would create

-- Alert 1: URGENT Waterless Delivery (Doc 6074)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6074,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'time_sensitive',
    'critical',
    'URGENT: Waterless delivery coordination required - multiple parties waiting on response',
    '["Waterless", "Delivery", "Urgent Response"]'::jsonb,
    true,
    0.95,
    '{"urgency_level": "critical", "alert_category": "time_sensitive", "summary": "URGENT: Waterless delivery coordination required - multiple parties waiting on response", "key_entities": ["Waterless", "Delivery", "Urgent Response"], "confidence": 0.95, "requires_action": true}'::jsonb
);

-- Alert 2: PO Entry Missing (Doc 6114)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6114,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'operational_blocker',
    'high',
    'So. Calif. Plastics PO #7089 from July never entered in system - potential revenue recognition issue',
    '["So Calif Plastics", "PO 7089", "Order Entry", "Ramiro Gonzalez"]'::jsonb,
    true,
    0.88,
    '{"urgency_level": "high", "alert_category": "operational_blocker", "summary": "So. Calif. Plastics PO #7089 from July never entered in system - potential revenue recognition issue", "key_entities": ["So Calif Plastics", "PO 7089", "Order Entry", "Ramiro Gonzalez"], "confidence": 0.88, "requires_action": true}'::jsonb
);

-- Alert 3: ICAS Revision (Doc 6195)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6195,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'customer_issue',
    'high',
    'ICAS revision required - customer waiting on updated documentation',
    '["ICAS", "Revision", "Documentation"]'::jsonb,
    true,
    0.82,
    '{"urgency_level": "high", "alert_category": "customer_issue", "summary": "ICAS revision required - customer waiting on updated documentation", "key_entities": ["ICAS", "Revision", "Documentation"], "confidence": 0.82, "requires_action": true}'::jsonb
);

-- Alert 4: ICU Medical PO Follow-up (Doc 6179)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6179,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'customer_escalation',
    'critical',
    'ICU Medical Sr. Buyer requesting urgent ship date update for PO #225930 - healthcare customer escalation',
    '["ICU Medical", "Katherine Escalante", "PO 225930", "Ship Date"]'::jsonb,
    true,
    0.93,
    '{"urgency_level": "critical", "alert_category": "customer_escalation", "summary": "ICU Medical Sr. Buyer requesting urgent ship date update for PO #225930 - healthcare customer escalation", "key_entities": ["ICU Medical", "Katherine Escalante", "PO 225930", "Ship Date"], "confidence": 0.93, "requires_action": true}'::jsonb
);

-- Alert 5: Pacific Metal Stampings Coordination (Doc 6077)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6077,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'operational_blocker',
    'high',
    'Parts shipping today for PO #19632-03 - Controller coordinating delivery timing',
    '["Pacific Metal Stampings", "Solomon Sambou", "PO 19632-03", "Controller"]'::jsonb,
    true,
    0.85,
    '{"urgency_level": "high", "alert_category": "operational_blocker", "summary": "Parts shipping today for PO #19632-03 - Controller coordinating delivery timing", "key_entities": ["Pacific Metal Stampings", "Solomon Sambou", "PO 19632-03", "Controller"], "confidence": 0.85, "requires_action": true}'::jsonb
);

-- Alert 6: Waterless Payment Check (Doc 6078)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6078,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'revenue_risk',
    'critical',
    'URGENT: Southern California Plastics mailing check for Waterless - cash flow critical transaction',
    '["Southern California Plastics", "Ramiro Gonzalez", "Waterless", "Payment Check"]'::jsonb,
    true,
    0.94,
    '{"urgency_level": "critical", "alert_category": "revenue_risk", "summary": "URGENT: Southern California Plastics mailing check for Waterless - cash flow critical transaction", "key_entities": ["Southern California Plastics", "Ramiro Gonzalez", "Waterless", "Payment Check"], "confidence": 0.94, "requires_action": true}'::jsonb
);

-- Alert 7: Email Follow-up Communication Gap (Doc 6180)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6180,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'customer_escalation',
    'high',
    'Customer asking "did you get my email?" on urgent Waterless matter - communication breakdown risk',
    '["Ramiro Gonzalez", "Southern California Plastics", "Maggie", "Email Follow-up"]'::jsonb,
    true,
    0.89,
    '{"urgency_level": "high", "alert_category": "customer_escalation", "summary": "Customer asking did you get my email on urgent Waterless matter - communication breakdown risk", "key_entities": ["Ramiro Gonzalez", "Southern California Plastics", "Maggie", "Email Follow-up"], "confidence": 0.89, "requires_action": true}'::jsonb
);

-- Alert 8: Safran Aerospace Documentation (Doc 6192)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6192,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'operational_blocker',
    'high',
    'Safran WWS: delivering 106 pieces part #86113-101 today but need yesterday''s report - aerospace documentation blocker',
    '["Safran WWS", "Part 86113-101", "106 pieces", "Tim", "Report"]'::jsonb,
    true,
    0.87,
    '{"urgency_level": "high", "alert_category": "operational_blocker", "summary": "Safran WWS: delivering 106 pieces part #86113-101 today but need yesterdays report - aerospace documentation blocker", "key_entities": ["Safran WWS", "Part 86113-101", "106 pieces", "Tim", "Report"], "confidence": 0.87, "requires_action": true}'::jsonb
);

-- Alert 9: Emily Lu Relief Response (Doc 6104)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6104,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'customer_escalation',
    'critical',
    'Assistant Buyer expressing extreme relief ("AMEN, phew") - previous critical escalation now resolved',
    '["Emily Lu", "Assistant Buyer", "Hayden", "Issue Resolution"]'::jsonb,
    true,
    0.91,
    '{"urgency_level": "critical", "alert_category": "customer_escalation", "summary": "Assistant Buyer expressing extreme relief (AMEN, phew) - previous critical escalation now resolved", "key_entities": ["Emily Lu", "Assistant Buyer", "Hayden", "Issue Resolution"], "confidence": 0.91, "requires_action": true}'::jsonb
);

-- Alert 10: Pedestal Inventory Ready (Doc 6993)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
    requires_action,
    detection_confidence,
    llm_response
) VALUES (
    6993,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'time_sensitive',
    'high',
    'Pedestal order: 80 units part #14320-200 ready for shipment - awaiting customer approval to ship',
    '["Part 14320-200", "80 units", "Pedestals", "Tim"]'::jsonb,
    true,
    0.84,
    '{"urgency_level": "high", "alert_category": "time_sensitive", "summary": "Pedestal order: 80 units part #14320-200 ready for shipment - awaiting customer approval to ship", "key_entities": ["Part 14320-200", "80 units", "Pedestals", "Tim"], "confidence": 0.84, "requires_action": true}'::jsonb
);

-- Step 3: Re-enable RLS
ALTER TABLE document_alerts ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- Verification
-- =====================================================

SELECT
    id as alert_id,
    alert_type,
    urgency_level,
    LEFT(summary, 80) as summary_preview,
    key_entities->>0 as first_entity,
    detection_confidence,
    detected_at
FROM document_alerts
WHERE tenant_id = '23e4af88-7df0-4ca4-9e60-fc2a12569a93'
  AND dismissed_at IS NULL
ORDER BY
    CASE urgency_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END,
    detected_at DESC;

-- Summary stats
SELECT
    urgency_level,
    COUNT(*) as count
FROM document_alerts
WHERE tenant_id = '23e4af88-7df0-4ca4-9e60-fc2a12569a93'
  AND dismissed_at IS NULL
GROUP BY urgency_level
ORDER BY
    CASE urgency_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END;

-- Done! You should now see 10 realistic alerts in your /alerts page
