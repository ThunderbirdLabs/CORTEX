-- =====================================================
-- Seed Test Alerts
-- =====================================================
-- Insert 10 realistic test alerts for demo/testing
-- Replace 'YOUR_TENANT_ID' with your actual tenant_id from documents table
-- Replace document_id values with actual document IDs from your database

-- To find your tenant_id:
-- SELECT DISTINCT tenant_id FROM documents LIMIT 1;

-- To find document IDs:
-- SELECT id, title FROM documents WHERE tenant_id = 'YOUR_TENANT_ID' LIMIT 10;

-- =====================================================

-- 1. Critical Revenue Risk - Customer Churn
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
    6179, -- Replace with actual document_id
    '23e4af88-7df0-4ca4-9e60-fc2a12569a93', -- Replace with your tenant_id
    'revenue_risk',
    'critical',
    'Major customer ($2.5M ARR) threatening to cancel contract due to recurring quality issues with product line',
    'Customer email expresses extreme frustration with 3 consecutive defective shipments. Mentions exploring competitor alternatives and contract termination if issues not resolved within 30 days. High-value customer with multi-year relationship at risk.',
    ARRAY['TechCorp Industries', 'Product Quality', 'Contract Cancellation', '$2.5M ARR'],
    ARRAY['Immediate executive call with customer', 'Quality team root cause analysis', 'Expedited replacement shipment', 'Discount/credit negotiation'],
    ARRAY['customer_retention', 'quality_control', 'revenue_protection']
);

-- 2. High Urgency - Operational Blocker
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
    'operational_blocker',
    'high',
    'Production line shutdown - critical supplier failed to deliver raw materials for Q4 manufacturing',
    'Email from supply chain indicates key supplier bankruptcy filing. Affects 60% of production capacity. Alternative suppliers quoted 4-6 week lead time. Current inventory covers only 2 weeks of demand.',
    ARRAY['Acme Plastics Inc', 'Production Line 3', 'Raw Materials', 'Q4 Manufacturing'],
    ARRAY['Emergency supplier sourcing meeting', 'Inventory reallocation analysis', 'Customer delivery timeline communication', 'Expedited shipping arrangements'],
    ARRAY['supply_chain', 'production', 'risk_mitigation']
);

-- 3. High - Customer Issue
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
    'customer_issue',
    'high',
    'Healthcare client reports product safety concern - potential FDA compliance issue',
    'Customer email describes unexpected product behavior in clinical setting. Mentions patient safety monitoring and potential adverse event reporting. References FDA compliance requirements and documentation requests.',
    ARRAY['MedTech Solutions', 'Product Safety', 'FDA Compliance', 'Adverse Events'],
    ARRAY['Immediate quality assurance review', 'Regulatory compliance consultation', 'Customer site visit scheduling', 'Documentation package preparation'],
    ARRAY['regulatory', 'product_safety', 'healthcare']
);

-- 4. Critical - Strategic Opportunity
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
    'strategic_opportunity',
    'critical',
    'Fortune 500 company requesting proposal for $15M multi-year contract - response due in 5 days',
    'RFP received from major enterprise customer. Scope includes complete product line integration across 12 facilities. Competitive bidding process with tight deadline. Represents 25% increase in annual revenue if won.',
    ARRAY['GlobalManu Corp', '$15M Contract', 'RFP Deadline', '12 Facilities'],
    ARRAY['Executive proposal review meeting', 'Pricing strategy session', 'Technical solution design', 'Reference customer coordination'],
    ARRAY['business_development', 'sales', 'strategic_growth']
);

-- 5. High - Competitive Threat
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
    'competitive_threat',
    'high',
    'Competitor launched new product with 40% lower price point targeting our key market segment',
    'Market intelligence email describes competitor new product launch. Features comparable to our mid-tier offering but significantly lower price. Already seeing customer inquiries. Three existing customers mentioned competitor in recent calls.',
    ARRAY['CompetitorX', 'Price Competition', 'Market Share', 'Mid-Tier Segment'],
    ARRAY['Competitive analysis deep-dive', 'Pricing strategy review', 'Product differentiation positioning', 'Customer retention program enhancement'],
    ARRAY['competitive_intelligence', 'pricing', 'market_positioning']
);

-- 6. Medium - Revenue Risk
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
    'medium',
    'Customer payment delayed 60+ days - $450K outstanding balance showing collection risk',
    'Accounts receivable report shows significant overdue balance. Customer has not responded to 3 payment reminders. Previous payment history was consistent. No communication regarding financial difficulties.',
    ARRAY['Industrial Systems LLC', '$450K Outstanding', '60 Days Overdue', 'Collections'],
    ARRAY['Executive-level payment discussion', 'Credit hold consideration', 'Payment plan negotiation', 'Legal counsel consultation if needed'],
    ARRAY['accounts_receivable', 'credit_risk', 'collections']
);

-- 7. Medium - Operational Blocker
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
    'operational_blocker',
    'medium',
    'Key engineering resource resignation - project delivery timeline at risk',
    'Resignation notice from senior engineer leading critical product development initiative. Project is 60% complete with customer delivery deadline in 8 weeks. No immediate replacement identified. Knowledge transfer concerns.',
    ARRAY['Sarah Chen', 'Product Development', 'Project Alpha', 'Knowledge Transfer'],
    ARRAY['Immediate knowledge documentation session', 'Internal talent reallocation review', 'External recruiting acceleration', 'Customer timeline communication plan'],
    ARRAY['talent_retention', 'project_management', 'resource_planning']
);

-- 8. Medium - Customer Issue
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
    'customer_issue',
    'medium',
    'Customer expresses dissatisfaction with support response times - mentions escalation to management',
    'Email from customer technical contact complaining about slow support ticket resolution. 4 open tickets over 7 days with no updates. Customer satisfaction at risk. Relationship is generally positive but showing strain.',
    ARRAY['DataFlow Systems', 'Support Tickets', 'Response Time', 'Customer Satisfaction'],
    ARRAY['Support ticket priority review', 'Direct customer follow-up call', 'Support process improvement analysis', 'Account manager involvement'],
    ARRAY['customer_support', 'service_quality', 'satisfaction']
);

-- 9. Low - Strategic Opportunity
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
    'strategic_opportunity',
    'low',
    'Customer inquiry about new product line - potential for account expansion',
    'Email from existing customer asking about capabilities in adjacent product category. Current account value $200K annually. Customer mentions upcoming project that could leverage expanded offerings. Exploratory stage.',
    ARRAY['Pacific Manufacturing', 'Product Expansion', 'Account Growth', 'New Category'],
    ARRAY['Product capabilities presentation', 'Account planning session', 'Cross-sell opportunity assessment', 'Custom solution feasibility review'],
    ARRAY['account_management', 'cross_selling', 'business_development']
);

-- 10. Low - Competitive Threat
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
    'competitive_threat',
    'low',
    'Competitor mentioned in industry article - monitoring market positioning',
    'Trade publication article mentions competitor product innovation. No immediate customer impact detected. Relevant for ongoing competitive intelligence. Could affect long-term market positioning if trend continues.',
    ARRAY['Industry Insider Magazine', 'Competitor Innovation', 'Market Trends', 'Technology Evolution'],
    ARRAY['Competitive intelligence file update', 'Product roadmap review', 'Market positioning discussion at quarterly planning', 'Technology trends monitoring'],
    ARRAY['market_intelligence', 'product_strategy', 'innovation']
);

-- =====================================================
-- Verification Query
-- =====================================================
-- Run this to verify the alerts were inserted:
-- SELECT
--     alert_id,
--     alert_type,
--     urgency_level,
--     LEFT(summary, 80) as summary_preview,
--     detected_at
-- FROM document_alerts
-- WHERE tenant_id = 'YOUR_TENANT_ID'
-- ORDER BY detected_at DESC
-- LIMIT 10;
