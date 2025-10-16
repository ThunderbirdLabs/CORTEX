-- ============================================================================
-- CHAT HISTORY TABLES
-- ============================================================================
-- Drop chat_uploads if it was created by accident
DROP TABLE IF EXISTS chat_uploads CASCADE;

-- Conversations/Chats
CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id TEXT NOT NULL,
    user_email TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chats_company ON chats(company_id);
CREATE INDEX idx_chats_user ON chats(user_email);
CREATE INDEX idx_chats_updated ON chats(updated_at DESC);

-- Messages within chats
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_id UUID REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    sources JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_chat ON chat_messages(chat_id, created_at);

COMMENT ON TABLE chats IS 'User chat conversations with Cortex AI';
COMMENT ON TABLE chat_messages IS 'Individual messages within chats';

