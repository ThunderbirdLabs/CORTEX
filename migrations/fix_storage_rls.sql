-- Fix Supabase Storage RLS blocking uploads
-- Run this in Supabase SQL Editor

-- Option 1: Disable RLS on storage.objects for 'documents' bucket (easiest for testing)
-- This allows all operations on files in the 'documents' bucket
DROP POLICY IF EXISTS "Allow authenticated uploads" ON storage.objects;
DROP POLICY IF EXISTS "Allow public downloads" ON storage.objects;
DROP POLICY IF EXISTS "Allow authenticated deletes" ON storage.objects;

-- Create permissive policy for documents bucket
CREATE POLICY "Allow all operations on documents bucket"
ON storage.objects
FOR ALL
TO public
USING (bucket_id = 'documents')
WITH CHECK (bucket_id = 'documents');

-- Ensure bucket is public
UPDATE storage.buckets
SET public = true
WHERE id = 'documents';
