-- =====================================================
-- Seed Test Alerts from Real Documents
-- =====================================================
-- Generated from actual documents in the database
-- Tenant ID: 23e4af88-7df0-4ca4-9e60-fc2a12569a93
-- =====================================================

-- 1. Critical - Revenue Risk (ICU Medical Purchase Order)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6179,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'revenue_risk',
    'critical',
    'Major medical device customer (ICU Medical) requesting urgent ship date update for PO #225930 - potential delivery delay risk',
    'Senior Buyer from ICU Medical (major healthcare customer) following up on ship date for Purchase Order #225930. The urgent tone and follow-up nature suggests potential delivery concerns that could impact customer relationship and future orders. Medical device industry has strict delivery requirements.',
    ARRAY['ICU Medical', 'Katherine Escalante', 'PO 225930', 'Ship Date', 'Healthcare Customer'],
    ARRAY['Immediate ship date confirmation to customer', 'Production status check', 'Expedite if possible', 'Proactive communication to prevent escalation'],
    ARRAY['customer_retention', 'order_fulfillment', 'healthcare']
);

-- 2. High - Customer Issue (Pacific Metal Stampings Payment/Delivery)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6077,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'customer_issue',
    'high',
    'Customer (Pacific Metal Stampings) coordination issue on PO #19632-03 - parts shipping today',
    'Customer controller is coordinating part shipment for PO #19632-03. The direct involvement of financial controller in shipment coordination may indicate payment or delivery timing sensitivities. Need to ensure smooth transaction completion.',
    ARRAY['Pacific Metal Stampings', 'Solomon Sambou', 'PO 19632-03', 'Controller'],
    ARRAY['Confirm shipment tracking', 'Ensure invoicing is ready', 'Follow up on receipt confirmation', 'Monitor payment processing'],
    ARRAY['accounts_receivable', 'shipping', 'customer_relations']
);

-- 3. Critical - Revenue Risk (Waterless Product Urgent Payment)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6078,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'revenue_risk',
    'critical',
    'URGENT: Southern California Plastics sending payment check for Waterless product - cash flow sensitive transaction',
    'Subject line marked URGENT regarding Waterless product delivery and payment. Customer (So Cal Plastics) is mailing check copy today. The urgency and payment coordination suggests this is a critical transaction requiring close monitoring to ensure payment receipt and relationship management.',
    ARRAY['Southern California Plastics', 'Ramiro Gonzalez', 'Waterless', 'Payment Check'],
    ARRAY['Confirm check receipt and deposit', 'Track delivery status', 'Ensure product delivery alignment with payment', 'Update accounting immediately'],
    ARRAY['cash_flow', 'accounts_receivable', 'urgent_delivery']
);

-- 4. High - Customer Issue (Follow-up on Urgent Waterless Matter)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6180,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'customer_issue',
    'high',
    'Customer (Ramiro Gonzalez) following up on urgent Waterless delivery - potential communication breakdown',
    'Customer is following up asking "did you get my email?" regarding urgent Waterless delivery matter. This indicates possible email communication issue or delayed response, which could escalate customer frustration. Immediate acknowledgment needed.',
    ARRAY['Ramiro Gonzalez', 'Southern California Plastics', 'Waterless', 'Email Follow-up'],
    ARRAY['Immediate response confirmation', 'Review previous email thread', 'Provide delivery status update', 'Ensure no communication gaps going forward'],
    ARRAY['customer_communication', 'delivery_coordination', 'service_recovery']
);

-- 5. Medium - Operational Coordination (Safran WWS Meeting - Part Delivery)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6192,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'operational_blocker',
    'medium',
    'Safran WWS project coordination - delivering part #86113-101 (106 pcs) today, awaiting yesterday''s report',
    'Customer needs report from yesterday for Safran WWS project. Delivering 106 pieces of part #86113-101 today with PO update needed. Aerospace customer (Safran) requires precise documentation and coordination. Missing report could delay acceptance.',
    ARRAY['Safran WWS', 'So Cal Plastics', 'Part 86113-101', '106 pieces', 'Tim'],
    ARRAY['Provide yesterday''s report immediately', 'Update PO system', 'Confirm delivery acceptance', 'Ensure aerospace quality documentation is complete'],
    ARRAY['aerospace', 'documentation', 'delivery_coordination']
);

-- 6. Medium - Strategic Opportunity (Pedestal Order - Inventory Ready)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6993,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'strategic_opportunity',
    'medium',
    'Ready inventory opportunity - 80 units of part 14320-200 ready to ship, customer approval pending',
    'Customer has 80 pieces of part #14320-200 ready and is inquiring about shipping 11 pieces today with more available in coming weeks. This represents inventory turnover opportunity and potential for increased order volume if customer confirms.',
    ARRAY['Part 14320-200', '80 units ready', 'Pedestals', 'Tim'],
    ARRAY['Get shipping approval for ready inventory', 'Forecast upcoming demand', 'Optimize inventory turnover', 'Explore opportunity for larger order commitment'],
    ARRAY['inventory_management', 'sales_opportunity', 'cash_flow_optimization']
);

-- 7. Low - Internal Documentation (Screen Shot  - Internal Communication)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6070,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'operational_blocker',
    'low',
    'Internal screen shot shared with Brent - potential process or system issue documentation',
    'Screen shot sent from Liz Codet to Brent. The nature of sharing screen shots often indicates system issues, process clarifications, or documentation needs. Low urgency but should be reviewed for context.',
    ARRAY['Liz Codet', 'Brent', 'Screen Shot', 'Internal Communication'],
    ARRAY['Review screen shot context', 'Determine if system issue needs addressing', 'Update process documentation if needed', 'No immediate action required'],
    ARRAY['internal_processes', 'documentation', 'systems']
);

-- 8. Low - Internal Documentation (Another Screen Shot)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6071,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'operational_blocker',
    'low',
    'Second screen shot shared with Brent - ongoing issue or multi-step process documentation',
    'Second screen shot in sequence from Liz Codet to Brent. Multiple screen shots suggest either complex issue or step-by-step process. Monitor for escalation but currently informational.',
    ARRAY['Liz Codet', 'Brent', 'Screen Shot', 'Process Documentation'],
    ARRAY['Review in context with previous screen shot', 'Assess if process improvement needed', 'Archive for reference', 'No urgent action needed'],
    ARRAY['internal_processes', 'documentation', 'continuous_improvement']
);

-- 9. Medium - Customer Acknowledgment (Emily Lu - Update Confirmation)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6104,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'customer_issue',
    'medium',
    'Customer (Emily Lu - Assistant Buyer) expressing relief over update - previous concern successfully resolved',
    'Customer Emily Lu from purchasing department expressing strong relief ("AMEN", "phew") over update from Hayden. This indicates a previously tense situation that has been resolved. Important to understand what issue was resolved to prevent recurrence.',
    ARRAY['Emily Lu', 'Assistant Buyer', 'Hayden', 'Issue Resolution'],
    ARRAY['Document what issue was resolved', 'Ensure root cause is addressed', 'Add to customer satisfaction tracking', 'Prevent similar issues with this customer'],
    ARRAY['customer_satisfaction', 'issue_resolution', 'process_improvement']
);

-- 10. Low - Administrative (PO Entry Request - Backlog Item)
INSERT INTO document_alerts (
    document_id,
    tenant_id,
    alert_type,
    urgency_level,
    summary,
    reasoning,
    key_entities,
    recommended_actions,
    related_topics
) VALUES (
    6114,
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93',
    'operational_blocker',
    'low',
    'Southern California Plastics PO #7089 from July never entered in system - administrative backlog',
    'Purchase order received in July was never entered into order system (OOR). This is an administrative oversight. While marked low urgency due to age, needs to be entered to maintain accurate order records and potentially invoice.',
    ARRAY['So Calif Plastics', 'PO 7089', 'Order Entry', 'Ramiro Gonzalez'],
    ARRAY['Enter PO into system immediately', 'Review other potential missing POs', 'Check if invoicing is pending', 'Improve order entry process to prevent recurrence'],
    ARRAY['order_management', 'administrative_backlog', 'process_compliance']
);

-- =====================================================
-- Verification Query
-- =====================================================
-- Run this to verify the alerts were inserted:

SELECT
    alert_id,
    alert_type,
    urgency_level,
    LEFT(summary, 100) as summary_preview,
    array_length(key_entities, 1) as entity_count,
    detected_at
FROM document_alerts
WHERE tenant_id = '23e4af88-7df0-4ca4-9e60-fc2a12569a93'
ORDER BY detected_at DESC
LIMIT 10;

-- Count by urgency:
SELECT
    urgency_level,
    COUNT(*) as alert_count
FROM document_alerts
WHERE tenant_id = '23e4af88-7df0-4ca4-9e60-fc2a12569a93'
GROUP BY urgency_level
ORDER BY
    CASE urgency_level
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'medium' THEN 3
        WHEN 'low' THEN 4
    END;

-- Count by type:
SELECT
    alert_type,
    COUNT(*) as alert_count
FROM document_alerts
WHERE tenant_id = '23e4af88-7df0-4ca4-9e60-fc2a12569a93'
GROUP BY alert_type
ORDER BY alert_count DESC;
