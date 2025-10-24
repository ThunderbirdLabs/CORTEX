-- Create storage bucket for document files
-- Run this in Supabase SQL Editor

-- Create the 'documents' bucket (if not exists)
INSERT INTO storage.buckets (id, name, public)
VALUES ('documents', 'documents', true)
ON CONFLICT (id) DO NOTHING;

-- Note: Public bucket = files accessible via URL
-- 100MB default file size limit
