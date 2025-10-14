"""
Document Ingestion Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from backend.models.api_models import DocumentIngest, DocumentIngestResponse
from backend.middleware.auth import verify_api_key
from backend.core.pipeline import HybridRAGPipeline


router = APIRouter(prefix="/api", tags=["ingestion"])

# Global pipeline instance (will be injected via dependency)
pipeline = HybridRAGPipeline()


@router.post("/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    doc: DocumentIngest,
    api_key: str = Depends(verify_api_key)
):
    """
    Ingest a document into the hybrid RAG system

    This endpoint:
    1. Chunks the document intelligently
    2. Generates embeddings and stores in Supabase vector DB
    3. Extracts entities and relationships for Neo4j knowledge graph
    4. Links both systems with a shared episode_id UUID

    Args:
        doc: Document with content, metadata, and source information
        api_key: Validated API key from header

    Returns:
        DocumentIngestResponse: Success status and ingestion details
    """
    try:
        result = await pipeline.ingest_document(
            content=doc.content,
            document_name=doc.document_name,
            source=doc.source,
            document_type=doc.document_type,
            reference_time=doc.reference_time,
            metadata=doc.metadata
        )

        return DocumentIngestResponse(
            success=True,
            episode_id=result["episode_id"],
            document_name=result["document_name"],
            source=result["source"],
            document_type=result["document_type"],
            num_chunks=result["num_chunks"],
            message=f"Document ingested successfully. {result['num_chunks']} chunks stored."
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}"
        )
