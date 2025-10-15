"""
File Upload Routes
Universal file ingestion for PDFs, Word, images, etc.
"""
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from supabase import Client

from app.core.security import get_current_user_id
from app.core.dependencies import get_supabase, get_cortex_pipeline
from app.services.universal.ingest import ingest_document_universal
from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/upload", tags=["upload"])


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
    cortex_pipeline: HybridPropertyGraphPipeline = Depends(get_cortex_pipeline)
):
    """
    Upload and ingest a file.

    Supports:
    - PDFs (application/pdf)
    - Word docs (.docx, .doc)
    - PowerPoint (.pptx)
    - Excel (.xlsx)
    - Images (PNG, JPEG, etc.)
    - Text files (.txt, .md, .html)
    - And 20+ more file types

    Parsing runs 100% locally using Unstructured.

    Flow:
    1. Upload file
    2. Parse with Unstructured (LOCAL)
    3. Save to documents table (Supabase)
    4. Ingest to PropertyGraph (Neo4j + Qdrant)

    Args:
        file: Uploaded file
        user_id: Authenticated user (from JWT)
        supabase: Supabase client
        cortex_pipeline: PropertyGraph pipeline

    Returns:
        Ingestion result
    """
    try:
        # Read file bytes
        file_bytes = await file.read()

        logger.info(f"📤 File upload: {file.filename} ({len(file_bytes)} bytes) from user {user_id}")

        # Universal ingestion
        result = await ingest_document_universal(
            supabase=supabase,
            cortex_pipeline=cortex_pipeline,
            tenant_id=user_id,
            source='upload',
            source_id=file.filename,  # Use filename as source_id for uploads
            document_type='file',
            file_bytes=file_bytes,
            filename=file.filename,
            file_type=file.content_type,
            metadata={
                'uploaded_by': user_id,
                'original_filename': file.filename,
                'content_type': file.content_type,
            }
        )

        if result['status'] == 'error':
            raise HTTPException(
                status_code=500,
                detail=f"Upload failed: {result.get('error')}"
            )

        logger.info(f"✅ File uploaded and ingested: {file.filename}")

        return {
            "success": True,
            "filename": file.filename,
            "file_type": result.get('file_type'),
            "characters": result.get('characters'),
            "message": f"File '{file.filename}' uploaded and ingested successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.post("/files")
async def upload_multiple_files(
    files: list[UploadFile] = File(...),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
    cortex_pipeline: HybridPropertyGraphPipeline = Depends(get_cortex_pipeline)
):
    """
    Upload and ingest multiple files.

    Processes each file independently.

    Args:
        files: List of uploaded files
        user_id: Authenticated user
        supabase: Supabase client
        cortex_pipeline: PropertyGraph pipeline

    Returns:
        List of ingestion results
    """
    results = []

    for file in files:
        try:
            file_bytes = await file.read()

            logger.info(f"📤 Batch upload: {file.filename} ({len(file_bytes)} bytes)")

            result = await ingest_document_universal(
                supabase=supabase,
                cortex_pipeline=cortex_pipeline,
                tenant_id=user_id,
                source='upload',
                source_id=file.filename,
                document_type='file',
                file_bytes=file_bytes,
                filename=file.filename,
                file_type=file.content_type,
                metadata={
                    'uploaded_by': user_id,
                    'original_filename': file.filename,
                }
            )

            results.append({
                "filename": file.filename,
                "status": result['status'],
                "characters": result.get('characters'),
                "error": result.get('error')
            })

        except Exception as e:
            logger.error(f"Failed to process {file.filename}: {e}")
            results.append({
                "filename": file.filename,
                "status": "error",
                "error": str(e)
            })

    # Summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')

    return {
        "success": True,
        "total": len(files),
        "success_count": success_count,
        "error_count": error_count,
        "results": results
    }
