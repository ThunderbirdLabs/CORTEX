-- Add file storage support to documents table
-- Allows storing original file for download even if OCR/parsing fails

ALTER TABLE documents
ADD COLUMN IF NOT EXISTS file_url TEXT,           -- Supabase Storage URL for file (if stored)
ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,  -- Original file size in bytes
ADD COLUMN IF NOT EXISTS mime_type TEXT;          -- Original MIME type (e.g., 'image/png', 'application/pdf')

COMMENT ON COLUMN documents.file_url IS 'Supabase Storage URL for original file (if available)';
COMMENT ON COLUMN documents.file_size_bytes IS 'Original file size in bytes';
COMMENT ON COLUMN documents.mime_type IS 'Original MIME type of the file';

-- Index for file lookups
CREATE INDEX IF NOT EXISTS idx_documents_file_url ON documents(file_url) WHERE file_url IS NOT NULL;

