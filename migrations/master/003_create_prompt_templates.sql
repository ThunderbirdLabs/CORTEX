-- ============================================================================
-- PROMPT TEMPLATES TABLE
-- ============================================================================
-- Purpose: Store customizable prompt templates for each company
-- Makes ALL prompts dynamic and editable from the master dashboard
-- ============================================================================

CREATE TABLE company_prompts (
    id SERIAL PRIMARY KEY,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,

    -- Prompt identification
    prompt_key TEXT NOT NULL,  -- "ceo_assistant", "email_classifier", "vision_ocr"
    prompt_name TEXT NOT NULL,  -- "CEO Assistant Response Synthesis"
    prompt_description TEXT,    -- What this prompt does

    -- Prompt template content
    prompt_template TEXT NOT NULL,  -- Full prompt with {{placeholders}}

    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,

    -- Ensure one active prompt per company per key
    UNIQUE(company_id, prompt_key, is_active)
);

CREATE INDEX idx_company_prompts_company ON company_prompts(company_id);
CREATE INDEX idx_company_prompts_key ON company_prompts(prompt_key);
CREATE INDEX idx_company_prompts_active ON company_prompts(is_active);

COMMENT ON TABLE company_prompts IS 'Customizable prompt templates for each company - allows dynamic prompt editing';
COMMENT ON COLUMN company_prompts.prompt_key IS 'Unique identifier for prompt type: ceo_assistant, email_classifier, vision_ocr, etc.';
COMMENT ON COLUMN company_prompts.prompt_template IS 'Full prompt text with {{variable}} placeholders (e.g., {{company_name}}, {{context_str}}, {{query_str}})';

-- Enable RLS
ALTER TABLE company_prompts ENABLE ROW LEVEL SECURITY;

-- Master admins can view/edit all prompts
CREATE POLICY "Master admins full access to prompts"
    ON company_prompts
    FOR ALL
    USING (true);
