-- Add episode_id and metadata columns to emails table
-- This links emails in Supabase to their RAG chunks in Qdrant/Neo4j

-- Add episode_id column (UUID from Cortex RAG ingestion)
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS episode_id UUID;

-- Add metadata column (JSONB for flexible storage)
ALTER TABLE emails
ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

-- Create index on episode_id for fast lookups
CREATE INDEX IF NOT EXISTS idx_emails_episode_id ON emails(episode_id);

-- Create index on metadata for JSON queries
CREATE INDEX IF NOT EXISTS idx_emails_metadata ON emails USING GIN(metadata);

-- Add comment for documentation
COMMENT ON COLUMN emails.episode_id IS 'UUID linking this email to its chunks in Qdrant and entities in Neo4j';
COMMENT ON COLUMN emails.metadata IS 'Flexible JSON storage for additional email metadata (RAG results, classifications, etc.)';
