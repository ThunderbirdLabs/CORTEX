-- ============================================================================
-- UNIFIED DOCUMENTS TABLE - Universal ingestion layer for ALL sources
-- ============================================================================
-- This table normalizes ALL data sources (Gmail, Drive, Slack, HubSpot, etc.)
-- into a unified format for RAG ingestion (Qdrant + Neo4j PropertyGraph)

-- Drop existing table if you want to recreate (BE CAREFUL in production!)
-- DROP TABLE IF EXISTS documents CASCADE;

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,

    -- Source metadata
    source TEXT NOT NULL,  -- 'gmail', 'gdrive', 'slack', 'hubspot', 'outlook', 'upload', etc.
    source_id TEXT NOT NULL,  -- External ID from source system
    document_type TEXT NOT NULL,  -- 'email', 'pdf', 'doc', 'message', 'deal', 'file', 'attachment'

    -- Unified content (for RAG ingestion)
    title TEXT NOT NULL,
    content TEXT NOT NULL,  -- Extracted plain text for embedding

    -- Original data (preserved as JSONB)
    raw_data JSONB,  -- Full original structure from source

    -- File metadata (for file-based sources)
    file_type TEXT,  -- MIME type: 'application/pdf', 'image/png', etc.
    file_size BIGINT,  -- File size in bytes
    file_url TEXT,  -- URL to file (S3, Supabase Storage, etc.)

    -- Timestamps
    source_created_at TIMESTAMPTZ,  -- When created in source system
    source_modified_at TIMESTAMPTZ,  -- When last modified in source
    ingested_at TIMESTAMPTZ DEFAULT NOW(),  -- When ingested to our system

    -- Flexible metadata
    metadata JSONB DEFAULT '{}',  -- Source-specific fields

    -- Prevent duplicates per tenant/source/source_id
    UNIQUE(tenant_id, source, source_id)
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- Primary lookup indexes
CREATE INDEX IF NOT EXISTS idx_documents_tenant ON documents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source);
CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source, document_type);

-- Timestamp indexes for temporal queries
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(source_created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_ingested ON documents(ingested_at DESC);

-- JSONB indexes for metadata queries
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN(metadata);
CREATE INDEX IF NOT EXISTS idx_documents_raw_data ON documents USING GIN(raw_data);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE documents IS 'Unified document storage for all sources (Gmail, Drive, Slack, HubSpot, etc.). All data flows through here before RAG ingestion.';

COMMENT ON COLUMN documents.source IS 'Source system identifier (gmail, gdrive, slack, hubspot, outlook, upload)';
COMMENT ON COLUMN documents.source_id IS 'Unique identifier in the source system (message_id, file_id, etc.)';
COMMENT ON COLUMN documents.document_type IS 'Type of document (email, pdf, doc, message, deal, file, attachment)';
COMMENT ON COLUMN documents.title IS 'Document title (subject, filename, deal name, etc.)';
COMMENT ON COLUMN documents.content IS 'Extracted plain text for RAG embedding and ingestion';
COMMENT ON COLUMN documents.raw_data IS 'Full original data structure from source (preserved as JSONB)';
COMMENT ON COLUMN documents.metadata IS 'Source-specific metadata (flexible JSONB storage)';

-- ============================================================================
-- SAMPLE QUERIES
-- ============================================================================

-- Get all Gmail emails for a tenant
-- SELECT * FROM documents WHERE tenant_id = 'user123' AND source = 'gmail' ORDER BY source_created_at DESC;

-- Get all PDFs from Google Drive
-- SELECT * FROM documents WHERE source = 'gdrive' AND file_type = 'application/pdf';

-- Search documents by title
-- SELECT * FROM documents WHERE title ILIKE '%quarterly report%';

-- Count documents by source
-- SELECT source, COUNT(*) FROM documents GROUP BY source;

-- Get recent documents across all sources
-- SELECT source, document_type, title, source_created_at
-- FROM documents
-- WHERE tenant_id = 'user123'
-- ORDER BY source_created_at DESC
-- LIMIT 100;
