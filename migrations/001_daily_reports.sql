-- Daily Reports System - Database Migration
--
-- Run this in your COMPANY Supabase (not master)
--
-- Creates tables for daily business intelligence reports with memory

-- ============================================================================
-- Main reports table (stores generated reports + memory)
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id text NOT NULL,
    report_date date NOT NULL,
    report_type text NOT NULL CHECK (report_type IN ('client_relationships', 'operations')),

    -- The complete report (JSON)
    full_report jsonb NOT NULL,

    -- Memory for next day's context
    summary text NOT NULL,
    key_items jsonb NOT NULL DEFAULT '{}'::jsonb,

    -- Metadata
    generated_at timestamp with time zone DEFAULT now(),
    generation_duration_ms integer,
    total_sources integer,

    -- One report per tenant/date/type
    UNIQUE(tenant_id, report_date, report_type),

    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_daily_reports_tenant_date
ON daily_reports(tenant_id, report_date DESC);

CREATE INDEX IF NOT EXISTS idx_daily_reports_type
ON daily_reports(report_type);

-- RLS (Row Level Security)
ALTER TABLE daily_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view their own reports"
ON daily_reports FOR SELECT
USING (tenant_id = auth.uid()::text);

CREATE POLICY "System can insert reports"
ON daily_reports FOR INSERT
WITH CHECK (true);

CREATE POLICY "System can update reports"
ON daily_reports FOR UPDATE
USING (true);


-- ============================================================================
-- MASTER Supabase tables (run these in MASTER Supabase)
-- ============================================================================

-- Static questions configuration (per company)
CREATE TABLE IF NOT EXISTS company_report_questions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    report_type text NOT NULL CHECK (report_type IN ('client_relationships', 'operations')),

    -- The question
    question_text text NOT NULL,
    question_category text, -- 'communications' | 'issues' | 'updates' | 'follow_ups'
    question_order integer NOT NULL DEFAULT 0,

    -- Control
    is_active boolean DEFAULT true,

    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_company_report_questions_lookup
ON company_report_questions(company_id, report_type, is_active, question_order);


-- Report section templates (per company)
CREATE TABLE IF NOT EXISTS company_report_sections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL,
    report_type text NOT NULL,

    -- Section configuration
    section_title text NOT NULL,
    section_icon text, -- emoji like 💬, 🚨, 📊
    section_order integer NOT NULL,
    section_description text, -- What should go in this section

    is_active boolean DEFAULT true,

    created_at timestamp with time zone DEFAULT now(),
    updated_at timestamp with time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_company_report_sections_lookup
ON company_report_sections(company_id, report_type, is_active, section_order);


-- ============================================================================
-- Example seed data (replace company_id with yours: 2ede0765-6f69-4293-931d-22cc88437e01)
-- ============================================================================

-- Static questions for Client Relationships report
INSERT INTO company_report_questions (company_id, report_type, question_text, question_category, question_order) VALUES
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'Who did we communicate with?', 'communications', 1),
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'What issues or concerns were raised?', 'issues', 2),
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'What updates were shared?', 'updates', 3),
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'What follow-up actions were created?', 'follow_ups', 4)
ON CONFLICT DO NOTHING;

-- Static questions for Operations report
INSERT INTO company_report_questions (company_id, report_type, question_text, question_category, question_order) VALUES
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'What purchase orders were discussed?', 'pos', 1),
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'What production updates were shared?', 'production', 2),
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'What quality issues were mentioned?', 'quality', 3),
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'What shipping or delivery updates occurred?', 'shipping', 4)
ON CONFLICT DO NOTHING;

-- Section templates for Client Relationships
INSERT INTO company_report_sections (company_id, report_type, section_title, section_icon, section_order, section_description) VALUES
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'Top Conversations', '💬', 1, 'Key client communications and discussions'),
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'Issues & Concerns', '🚨', 2, 'Problems or concerns raised by clients'),
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'Updates Shared', '📊', 3, 'Status updates and information shared'),
('2ede0765-6f69-4293-931d-22cc88437e01', 'client_relationships', 'Follow-ups Needed', '⚡', 4, 'Action items and pending follow-ups')
ON CONFLICT DO NOTHING;

-- Section templates for Operations
INSERT INTO company_report_sections (company_id, report_type, section_title, section_icon, section_order, section_description) VALUES
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'Purchase Orders', '📦', 1, 'PO discussions, updates, issues'),
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'Production Status', '🏭', 2, 'Manufacturing updates and progress'),
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'Quality & Issues', '🔍', 3, 'Quality concerns, dimensional issues, approvals'),
('2ede0765-6f69-4293-931d-22cc88437e01', 'operations', 'Shipping & Delivery', '🚛', 4, 'Shipments, tracking, delivery updates')
ON CONFLICT DO NOTHING;


-- ============================================================================
-- Prompts to add to company_prompts table (run in MASTER Supabase)
-- ============================================================================

-- You'll need to manually add these prompts:
--
-- prompt_key: 'daily_report_client_relationships'
-- prompt_key: 'daily_report_operations'
-- prompt_key: 'daily_report_summary_generator'
-- prompt_key: 'daily_report_dynamic_questions'
-- prompt_key: 'daily_report_key_items_extractor'
--
-- I'll create the actual prompt templates in the next files
