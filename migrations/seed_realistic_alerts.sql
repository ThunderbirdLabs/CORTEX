-- =====================================================
-- Seed Realistic Test Alerts
-- =====================================================
-- Creates alerts that look EXACTLY like real AI-detected alerts
-- Based on actual documents in the database
-- Tenant ID: 23e4af88-7df0-4ca4-9e60-fc2a12569a93
-- =====================================================

-- Alert 1: Critical - ICU Medical Ship Date Follow-up
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
    'customer_issue',
    'critical',
    'ICU Medical Sr. Buyer requesting urgent ship date update for PO #225930',
    '["ICU Medical", "Katherine Escalante", "PO 225930", "Hayden Woodfburn"]'::jsonb,
    true,
    0.92,
    '{"urgency_level": "critical", "alert_category": "customer_issue", "summary": "ICU Medical Sr. Buyer requesting urgent ship date update for PO #225930", "key_entities": ["ICU Medical", "Katherine Escalante", "PO 225930", "Hayden Woodfburn"], "confidence": 0.92, "requires_action": true, "reasoning": "Senior buyer from medical device company following up on shipment timing. Healthcare customers require strict delivery compliance."}'::jsonb
);

-- Alert 2: High - Pacific Metal Stampings Part Shipment
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
    'Parts for PO #19632-03 shipping today - Controller coordinating delivery with Pacific Metal Stampings',
    '["Pacific Metal Stampings", "Solomon Sambou", "PO 19632-03", "Controller"]'::jsonb,
    true,
    0.85,
    '{"urgency_level": "high", "alert_category": "operational_blocker", "summary": "Parts for PO #19632-03 shipping today - Controller coordinating delivery with Pacific Metal Stampings", "key_entities": ["Pacific Metal Stampings", "Solomon Sambou", "PO 19632-03", "Controller"], "confidence": 0.85, "requires_action": true, "reasoning": "Financial controller directly involved in shipment coordination suggests payment or timing sensitivity requiring attention."}'::jsonb
);

-- Alert 3: Critical - Waterless Product Payment
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
    'URGENT: Southern California Plastics mailing check for Waterless product - requires immediate tracking',
    '["Southern California Plastics", "Ramiro Gonzalez", "Waterless", "Payment Check", "Jason"]'::jsonb,
    true,
    0.94,
    '{"urgency_level": "critical", "alert_category": "revenue_risk", "summary": "URGENT: Southern California Plastics mailing check for Waterless product - requires immediate tracking", "key_entities": ["Southern California Plastics", "Ramiro Gonzalez", "Waterless", "Payment Check", "Jason"], "confidence": 0.94, "requires_action": true, "reasoning": "Email subject marked URGENT regarding payment and delivery coordination. Check being mailed requires tracking to ensure cash flow and delivery alignment."}'::jsonb
);

-- Alert 4: High - Waterless Follow-up Communication Gap
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
    'Customer follow-up on URGENT Waterless matter - "did you get my email?" indicates possible communication breakdown',
    '["Southern California Plastics", "Ramiro Gonzalez", "Maggie", "Waterless", "Email Communication"]'::jsonb,
    true,
    0.88,
    '{"urgency_level": "high", "alert_category": "customer_escalation", "summary": "Customer follow-up on URGENT Waterless matter - did you get my email indicates possible communication breakdown", "key_entities": ["Southern California Plastics", "Ramiro Gonzalez", "Maggie", "Waterless", "Email Communication"], "confidence": 0.88, "requires_action": true, "reasoning": "Customer asking if previous email was received suggests response delay or email delivery issue. May escalate if not addressed immediately."}'::jsonb
);

-- Alert 5: High - Safran Aerospace Documentation
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
    'Safran WWS project: delivering part #86113-101 today but awaiting yesterday''s report - documentation blocker',
    '["Safran WWS", "So Cal Plastics", "Part 86113-101", "106 pieces", "Tim", "PO Update"]'::jsonb,
    true,
    0.86,
    '{"urgency_level": "high", "alert_category": "operational_blocker", "summary": "Safran WWS project: delivering part #86113-101 today but awaiting yesterdays report - documentation blocker", "key_entities": ["Safran WWS", "So Cal Plastics", "Part 86113-101", "106 pieces", "Tim", "PO Update"], "confidence": 0.86, "requires_action": true, "reasoning": "Aerospace customer (Safran) delivery happening today but waiting on report from yesterday. Missing documentation could delay shipment acceptance for safety-critical aerospace parts."}'::jsonb
);

-- Alert 6: Critical - Emily Lu Relief Response
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
    'Assistant Buyer expressing extreme relief ("AMEN", "phew") over update - previous critical issue was escalated',
    '["Emily Lu", "Assistant Buyer", "Hayden", "Issue Resolution"]'::jsonb,
    true,
    0.91,
    '{"urgency_level": "critical", "alert_category": "customer_escalation", "summary": "Assistant Buyer expressing extreme relief (AMEN, phew) over update - previous critical issue was escalated", "key_entities": ["Emily Lu", "Assistant Buyer", "Hayden", "Issue Resolution"], "confidence": 0.91, "requires_action": true, "reasoning": "Strong emotional language (AMEN, phew) indicates previously escalated situation. Need to document what was resolved to prevent recurrence and maintain improved customer relationship."}'::jsonb
);

-- Alert 7: High - Pedestal Inventory Opportunity
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
    'Pedestal order: shipping 11 units today, 80 units (part 14320-200) ready for immediate shipment pending approval',
    '["Part 14320-200", "80 units", "11 units", "Pedestals", "Tim"]'::jsonb,
    true,
    0.83,
    '{"urgency_level": "high", "alert_category": "time_sensitive", "summary": "Pedestal order: shipping 11 units today, 80 units (part 14320-200) ready for immediate shipment pending approval", "key_entities": ["Part 14320-200", "80 units", "11 units", "Pedestals", "Tim"], "confidence": 0.83, "requires_action": true, "reasoning": "Significant ready inventory (80 units) awaiting customer shipping approval. Time-sensitive because holding inventory ties up capital and warehouse space. Quick approval could improve cash flow."}'::jsonb
);

-- Alert 8: High - July PO Never Entered
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
    'So. Calif. Plastics PO #7089 from July never entered in system - revenue recognition and fulfillment at risk',
    '["So Calif Plastics", "PO 7089", "July", "Order Entry", "Ramiro Gonzalez"]'::jsonb,
    true,
    0.87,
    '{"urgency_level": "high", "alert_category": "operational_blocker", "summary": "So. Calif. Plastics PO #7089 from July never entered in system - revenue recognition and fulfillment at risk", "key_entities": ["So Calif Plastics", "PO 7089", "July", "Order Entry", "Ramiro Gonzalez"], "confidence": 0.87, "requires_action": true, "reasoning": "Purchase order received months ago (July) never entered into order system. This affects revenue recognition, inventory allocation, and potentially customer satisfaction if fulfillment was expected."}'::jsonb
);

-- =====================================================
-- Verification Queries
-- =====================================================

-- View all alerts
SELECT
    id as alert_id,
    alert_type,
    urgency_level,
    summary,
    key_entities,
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

-- Count by urgency
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

-- Count by type
SELECT
    alert_type,
    COUNT(*) as count
FROM document_alerts
WHERE tenant_id = '23e4af88-7df0-4ca4-9e60-fc2a12569a93'
  AND dismissed_at IS NULL
GROUP BY alert_type
ORDER BY count DESC;
