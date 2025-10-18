"""
Maintenance Routes - Database fixes and health checks
"""
import logging
from fastapi import APIRouter, HTTPException
from qdrant_client import QdrantClient
from qdrant_client.models import PayloadSchemaType

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/maintenance", tags=["maintenance"])


@router.post("/fix-qdrant-indexes")
async def fix_qdrant_indexes():
    """
    Fix Qdrant collection - Add missing payload indexes.
    
    LlamaIndex's IngestionPipeline requires doc_id and ref_doc_id indexes
    for document deduplication. This endpoint adds them if missing.
    
    Safe to run multiple times - idempotent operation.
    
    Returns:
        Status of index creation
    """
    try:
        logger.info("🔧 Fixing Qdrant payload indexes...")
        
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key
        )
        
        collection_name = settings.qdrant_collection_name
        
        # Check collection exists
        try:
            collection = client.get_collection(collection_name)
            logger.info(f"   Collection: {collection_name}")
            logger.info(f"   Points: {collection.points_count}")
        except Exception as e:
            raise HTTPException(
                status_code=404,
                detail=f"Collection not found: {collection_name}"
            )
        
        results = {
            "collection": collection_name,
            "indexes_created": []
        }
        
        # Add doc_id index
        try:
            logger.info("   Creating doc_id keyword index...")
            client.create_payload_index(
                collection_name=collection_name,
                field_name="doc_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            results["indexes_created"].append("doc_id")
            logger.info("   ✅ doc_id index created")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("   ℹ️  doc_id index already exists")
                results["doc_id"] = "already_exists"
            else:
                logger.error(f"   ❌ Failed to create doc_id index: {e}")
                results["doc_id_error"] = str(e)
        
        # Add ref_doc_id index
        try:
            logger.info("   Creating ref_doc_id keyword index...")
            client.create_payload_index(
                collection_name=collection_name,
                field_name="ref_doc_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            results["indexes_created"].append("ref_doc_id")
            logger.info("   ✅ ref_doc_id index created")
        except Exception as e:
            if "already exists" in str(e).lower():
                logger.info("   ℹ️  ref_doc_id index already exists")
                results["ref_doc_id"] = "already_exists"
            else:
                logger.error(f"   ❌ Failed to create ref_doc_id index: {e}")
                results["ref_doc_id_error"] = str(e)
        
        # Verify current schema
        collection = client.get_collection(collection_name)
        if collection.payload_schema:
            results["payload_schema"] = {
                field: str(schema) for field, schema in collection.payload_schema.items()
            }
        
        logger.info("✅ Qdrant indexes fixed")
        
        return {
            "success": True,
            "message": "Qdrant payload indexes have been created/verified",
            "details": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to fix Qdrant indexes: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fix indexes: {str(e)}"
        )


@router.get("/qdrant-status")
async def qdrant_status():
    """
    Get Qdrant collection status and schema information.
    
    Returns:
        Collection stats and payload schema
    """
    try:
        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key
        )
        
        collection_name = settings.qdrant_collection_name
        collection = client.get_collection(collection_name)
        
        payload_schema = {}
        if collection.payload_schema:
            payload_schema = {
                field: str(schema) for field, schema in collection.payload_schema.items()
            }
        
        return {
            "collection": collection_name,
            "points_count": collection.points_count,
            "vectors_count": collection.vectors_count,
            "payload_schema": payload_schema,
            "status": collection.status
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get Qdrant status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )

