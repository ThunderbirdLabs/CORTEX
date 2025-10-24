"""
Universal Document Ingestion
Normalizes ALL sources (Gmail, Drive, Slack, HubSpot, uploads, etc.) into unified format.

Flow for ANY source (matches Alex's pattern):
1. Extract text (if file provided) → Plain text
2. Check for duplicates (content-based deduplication)
3. Save to documents table → Supabase (SOURCE OF TRUTH)
4. Ingest from documents table → Neo4j + Qdrant
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from supabase import Client

from app.services.ingestion.llamaindex import UniversalIngestionPipeline
from app.services.parsing.file_parser import extract_text_from_file, extract_text_from_bytes
from app.services.deduplication import should_ingest_document

logger = logging.getLogger(__name__)


def strip_null_bytes_from_dict(data: Any) -> Any:
    """
    Recursively strip null bytes from all strings in a dictionary/list.
    PostgreSQL doesn't allow \\u0000 in TEXT/JSONB fields.
    """
    if isinstance(data, dict):
        return {k: strip_null_bytes_from_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [strip_null_bytes_from_dict(item) for item in data]
    elif isinstance(data, str):
        return data.replace('\x00', '')
    else:
        return data


async def ingest_document_universal(
    supabase: Client,
    cortex_pipeline: UniversalIngestionPipeline,
    tenant_id: str,
    source: str,  # 'gmail', 'gdrive', 'slack', 'hubspot', 'outlook', 'upload'
    source_id: str,  # External ID from source system
    document_type: str,  # 'email', 'pdf', 'doc', 'message', 'deal', 'file'

    # Either provide text directly...
    title: Optional[str] = None,
    content: Optional[str] = None,

    # ...or provide file to parse
    file_path: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    file_type: Optional[str] = None,

    # Optional metadata
    raw_data: Optional[Dict] = None,
    source_created_at: Optional[datetime] = None,
    source_modified_at: Optional[datetime] = None,
    metadata: Optional[Dict] = None,
    
    # Parent-child relationships (NEW: for attachments)
    parent_document_id: Optional[int] = None,
    parent_email_content: Optional[str] = None  # Email body to add as context
) -> Dict[str, Any]:
    """
    Universal ingestion function for ANY data source.

    This handles EVERYTHING:
    - Emails (Gmail, Outlook) - plain text
    - Files (Drive, Slack) - PDFs, Word, etc.
    - Messages (Slack, Teams) - plain text
    - Structured data (HubSpot, Salesforce) - JSON → text
    - Uploads - any file type

    Args:
        supabase: Supabase client
        cortex_pipeline: UniversalIngestionPipeline instance
        tenant_id: Tenant/user ID
        source: Source identifier ('gmail', 'gdrive', 'slack', etc.)
        source_id: External ID from source system
        document_type: Type of document
        title: Document title (subject, filename, etc.)
        content: Plain text content (if already extracted)
        file_path: Path to file (for parsing)
        file_bytes: File bytes (for uploads/downloads)
        filename: Original filename
        file_type: MIME type
        raw_data: Original data structure (preserved as JSONB)
        source_created_at: When created in source system
        source_modified_at: When last modified in source
        metadata: Additional source-specific metadata
        parent_document_id: For attachments - ID of parent email/document
        parent_email_content: For attachments - Parent email body for context

    Returns:
        Dict with ingestion results
    """

    logger.info(f"🌊 UNIVERSAL INGESTION: {source}/{document_type}")
    logger.info(f"   Source ID: {source_id}")

    try:
        # ========================================================================
        # STEP 1: Extract Text Content
        # ========================================================================

        parse_metadata = {}

        if not content:
            # Need to extract text from file
            if file_path:
                logger.info(f"   📄 Parsing file: {file_path}")
                content, parse_metadata = extract_text_from_file(file_path, file_type)

            elif file_bytes and filename:
                logger.info(f"   📤 Parsing uploaded file: {filename}")
                content, parse_metadata = extract_text_from_bytes(file_bytes, filename, file_type)

            else:
                raise ValueError("Must provide either 'content', 'file_path', or 'file_bytes + filename'")

        # Ensure we have a title
        if not title:
            title = parse_metadata.get('file_name', filename or f"{source} document")

        # Merge parse metadata into metadata dict
        if metadata is None:
            metadata = {}
        metadata.update(parse_metadata)

        # Get file_type from parse_metadata if not provided
        if not file_type and 'file_type' in parse_metadata:
            file_type = parse_metadata['file_type']

        logger.info(f"   ✅ Text extracted: {len(content)} characters")
        
        # If this is an attachment with parent email content, add it as context!
        if parent_email_content and document_type == "attachment":
            context_prefix = f"\n\n[EMAIL CONTEXT - This file was attached to an email with the following content:]\n{parent_email_content}\n[END EMAIL CONTEXT]\n\n"
            content = context_prefix + content
            logger.info(f"   📎 Added parent email context ({len(parent_email_content)} chars)")
        
        # Strip null bytes (Postgres can't handle them) from ALL text fields
        content = content.replace('\x00', '') if content else ''
        if title:
            title = title.replace('\x00', '')
        
        # Limit content size to prevent runaway processing costs
        MAX_CHARS = 100000  # 100K chars max (~50 pages of text)
        if len(content) > MAX_CHARS:
            logger.warning(f"   ⚠️  Content too large ({len(content)} chars), truncating to {MAX_CHARS}")
            content = content[:MAX_CHARS]

        # ========================================================================
        # STEP 2: Check for duplicates (content-based deduplication)
        # ========================================================================

        should_ingest, content_hash = await should_ingest_document(
            supabase=supabase,
            tenant_id=tenant_id,
            content=content,
            source=source,
            skip_dedupe=True  # TEMPORARY: Skip deduplication for testing
        )

        if not should_ingest:
            logger.info(f"   ⏭️  Skipping duplicate document: {title}")
            return {
                'status': 'skipped',
                'reason': 'duplicate',
                'source': source,
                'source_id': source_id,
                'title': title,
                'content_hash': content_hash
            }

        logger.info(f"   ✅ No duplicate found (hash: {content_hash[:16]}...)")

        # ========================================================================
        # STEP 2.5: Upload Original File to Supabase Storage (Optional)
        # ========================================================================
        
        file_url = None
        file_size_bytes = None
        mime_type = file_type
        
        if file_bytes and filename:
            try:
                # Generate unique storage path: tenant_id/source/year/month/filename
                from datetime import datetime
                import uuid
                
                now = datetime.utcnow()
                # Sanitize filename: Remove special characters that break Supabase Storage
                import re
                safe_filename = re.sub(r'[^\w\s\-\.]', '_', filename)  # Keep alphanumeric, spaces, hyphens, dots
                safe_filename = safe_filename.replace(' ', '_')  # Replace spaces with underscores
                unique_id = str(uuid.uuid4())[:8]
                storage_path = f"{tenant_id}/{source}/{now.year}/{now.month:02d}/{unique_id}_{safe_filename}"
                
                logger.info(f"   📤 Uploading original file to storage: {storage_path}")
                
                # Upload to Supabase Storage (bucket: 'documents')
                upload_result = supabase.storage.from_('documents').upload(
                    path=storage_path,
                    file=file_bytes,
                    file_options={"content-type": mime_type or "application/octet-stream"}
                )
                
                # Get public URL
                file_url = supabase.storage.from_('documents').get_public_url(storage_path)
                file_size_bytes = len(file_bytes)
                
                logger.info(f"   ✅ File uploaded: {file_url[:80]}...")
                
            except Exception as upload_error:
                logger.warning(f"   ⚠️  Failed to upload file to storage: {upload_error}")
                logger.info(f"   💾 Falling back to PostgreSQL binary storage in raw_data...")

                # BACKUP STRATEGY: Store file bytes in raw_data if Supabase Storage fails
                # Base64 encode for safe JSON storage
                import base64
                if not raw_data:
                    raw_data = {}

                # Store file as base64 in raw_data (for small files only, <10MB)
                if len(file_bytes) <= 10 * 1024 * 1024:  # 10MB limit
                    raw_data['_file_backup'] = {
                        'filename': filename,
                        'mime_type': mime_type,
                        'size_bytes': len(file_bytes),
                        'data_base64': base64.b64encode(file_bytes).decode('utf-8'),
                        'note': 'Stored due to Supabase Storage upload failure'
                    }
                    file_size_bytes = len(file_bytes)
                    logger.info(f"   ✅ File backed up to raw_data ({len(file_bytes)} bytes)")
                else:
                    logger.warning(f"   ⚠️  File too large for PostgreSQL backup ({len(file_bytes)} bytes), skipping...")

        # ========================================================================
        # STEP 3: Save to Unified Documents Table (Supabase) - SOURCE OF TRUTH
        # ========================================================================

        logger.info(f"   💾 Saving to documents table (source of truth)...")

        # Strip null bytes from raw_data (PostgreSQL JSONB can't handle \u0000)
        if raw_data:
            raw_data = strip_null_bytes_from_dict(raw_data)
        if metadata:
            metadata = strip_null_bytes_from_dict(metadata)

        document_row = {
            'tenant_id': tenant_id,
            'source': source,
            'source_id': source_id,
            'document_type': document_type,
            'title': title,
            'content': content,
            'content_hash': content_hash,  # Add content hash for deduplication
            'raw_data': raw_data,
            'file_type': file_type,
            'file_size': parse_metadata.get('file_size') or (len(file_bytes) if file_bytes else None),
            'source_created_at': source_created_at.isoformat() if source_created_at else None,
            'source_modified_at': source_modified_at.isoformat() if source_modified_at else None,
            'metadata': metadata,
            # File storage fields (NEW)
            'file_url': file_url,
            'file_size_bytes': file_size_bytes,
            'mime_type': mime_type,
            # Parent-child relationship (NEW: for attachments)
            'parent_document_id': parent_document_id,
        }

        # Upsert to documents table (handles duplicates)
        result = supabase.table('documents').upsert(
            document_row,
            on_conflict='tenant_id,source,source_id'
        ).execute()

        # Get the inserted/updated document with its ID
        inserted_doc = result.data[0] if result.data else None
        if not inserted_doc or 'id' not in inserted_doc:
            raise Exception("Failed to get document ID from Supabase upsert")

        logger.info(f"   ✅ Saved to documents table (id: {inserted_doc['id']})")

        # ========================================================================
        # STEP 4: Ingest to PropertyGraph (Neo4j + Qdrant) - FROM DOCUMENTS TABLE
        # ========================================================================

        logger.info(f"   🕸️  Ingesting to PropertyGraph from documents table...")

        # Use the full document row with ID (CRITICAL: doc_id must be set!)
        cortex_result = await cortex_pipeline.ingest_document(
            document_row=inserted_doc,
            extract_entities=True
        )

        if cortex_result.get('status') != 'success':
            raise Exception(f"PropertyGraph ingestion failed: {cortex_result.get('error')}")

        logger.info(f"   ✅ PropertyGraph ingestion complete")

        # ========================================================================
        # SUCCESS
        # ========================================================================

        logger.info(f"✅ UNIVERSAL INGESTION COMPLETE: {title}")

        return {
            'status': 'success',
            'document_id': inserted_doc['id'],  # Return document ID for parent-child linking
            'source': source,
            'source_id': source_id,
            'document_type': document_type,
            'title': title,
            'characters': len(content),
            'file_type': file_type,
            'cortex_result': cortex_result
        }

    except Exception as e:
        error_msg = f"Universal ingestion failed: {str(e)}"
        logger.error(f"❌ {error_msg}", exc_info=True)

        return {
            'status': 'error',
            'error': error_msg,
            'source': source,
            'source_id': source_id
        }
