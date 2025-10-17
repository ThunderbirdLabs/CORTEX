"""
Universal Document Ingestion
Normalizes ALL sources (Gmail, Drive, Slack, HubSpot, uploads, etc.) into unified format.

Flow for ANY source:
1. Extract text (if file provided) → Plain text
2. Check for duplicates (content-based deduplication)
3. Save to documents table → Supabase
4. Ingest to PropertyGraph → Neo4j + Qdrant
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from supabase import Client

from app.services.ingestion.llamaindex import UniversalIngestionPipeline
from app.services.parsing.file_parser import extract_text_from_file, extract_text_from_bytes
from app.services.deduplication import should_ingest_document

logger = logging.getLogger(__name__)


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
    metadata: Optional[Dict] = None
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
        cortex_pipeline: HybridPropertyGraphPipeline instance
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
        
        # Strip null bytes (Postgres can't handle them)
        content = content.replace('\x00', '')
        
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
            source=source
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
        # STEP 3: Ingest to PropertyGraph (Neo4j + Qdrant)
        # ========================================================================

        logger.info(f"   🕸️  Ingesting to PropertyGraph...")

        # Construct document_row in Supabase format for UniversalIngestionPipeline
        document_row_for_ingestion = {
            'id': source_id,  # Use source_id as document ID
            'title': title,
            'content': content,
            'source': source,
            'document_type': document_type,
            'tenant_id': tenant_id,
            'source_id': source_id,
            'source_created_at': source_created_at.isoformat() if source_created_at else None,
            'metadata': metadata or {}
        }

        cortex_result = await cortex_pipeline.ingest_document(
            document_row=document_row_for_ingestion,
            extract_entities=True
        )

        if cortex_result.get('status') != 'success':
            raise Exception(f"PropertyGraph ingestion failed: {cortex_result.get('error')}")

        logger.info(f"   ✅ PropertyGraph ingestion complete")

        # ========================================================================
        # STEP 4: Save to Unified Documents Table (Supabase)
        # ========================================================================

        logger.info(f"   💾 Saving to documents table...")

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
        }

        # Upsert to documents table (handles duplicates)
        supabase.table('documents').upsert(
            document_row,
            on_conflict='tenant_id,source,source_id'
        ).execute()

        logger.info(f"   ✅ Saved to documents table")

        # ========================================================================
        # SUCCESS
        # ========================================================================

        logger.info(f"✅ UNIVERSAL INGESTION COMPLETE: {title}")

        return {
            'status': 'success',
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
