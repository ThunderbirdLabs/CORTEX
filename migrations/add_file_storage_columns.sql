-- Add file storage support to documents table
-- Allows storing original file for download even if OCR/parsing fails

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS file_url TEXT,           -- Supabase Storage URL for file (if stored)
ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,  -- Original file size in bytes
ADD COLUMN IF NOT EXISTS mime_type TEXT,          -- Original MIME type (e.g., 'image/png', 'application/pdf')
ADD COLUMN IF NOT EXISTS parent_document_id BIGINT REFERENCES documents(id);  -- Link attachments to parent email

COMMENT ON COLUMN documents.file_url IS 'Supabase Storage URL for original file (if available)';
COMMENT ON COLUMN documents.file_size_bytes IS 'Original file size in bytes';
COMMENT ON COLUMN documents.mime_type IS 'Original MIME type of the file';
COMMENT ON COLUMN documents.parent_document_id IS 'For attachments: ID of parent email/document for context';

-- Index for file lookups
CREATE INDEX IF NOT EXISTS idx_documents_file_url ON documents(file_url) WHERE file_url IS NOT NULL;

-- Index for parent-child relationships (find all attachments for an email)
CREATE INDEX IF NOT EXISTS idx_documents_parent_document_id ON documents(parent_document_id) WHERE parent_document_id IS NOT NULL;

