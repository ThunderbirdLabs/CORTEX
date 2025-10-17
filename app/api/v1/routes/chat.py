"""
Chat Routes - Simple Query Interface for Hybrid Property Graph System
Uses HybridPropertyGraphPipeline + HybridRetriever (Single PropertyGraphIndex with Neo4j + Qdrant)
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.services.ingestion.llamaindex import HybridQueryEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Global hybrid query engine (lazy initialized)
query_engine = None
_initialized = False


class ChatMessage(BaseModel):
    """Chat message"""
    question: str
    tenant_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response"""
    question: str
    answer: str
    source_count: int
    sources: List[Dict[str, Any]]


async def _initialize_query_engine():
    """Initialize the hybrid query engine (lazy)"""
    global query_engine, _initialized

    if not _initialized:
        logger.info("🚀 Initializing Hybrid Query Engine...")
        query_engine = HybridQueryEngine()
        _initialized = True
        logger.info("✅ Hybrid Query Engine ready")

    return query_engine


@router.post("/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """
    Simple chat interface for testing the hybrid property graph retrieval.

    Uses:
    - Single PropertyGraphIndex combining Neo4j + Qdrant
    - VectorContextRetriever for graph-aware vector search
    - LLMSynonymRetriever for query expansion with entity synonyms
    - Multi-strategy concurrent retrieval with intelligent result merging

    Args:
        message: User question

    Returns:
        ChatResponse: Answer + sources
    """
    try:
        # Initialize query engine (lazy)
        engine = await _initialize_query_engine()

        logger.info(f"💬 Chat query: {message.question}")

        # Execute hybrid query
        result = await engine.query(message.question)

        # Format source nodes
        sources = []
        for i, node in enumerate(result.get('source_nodes', []), 1):
            metadata = node.metadata if hasattr(node, 'metadata') else {}
            sources.append({
                'index': i,
                'document_name': metadata.get('document_name', 'Unknown'),
                'source': metadata.get('source', 'Unknown'),
                'document_type': metadata.get('document_type', 'Unknown'),
                'timestamp': metadata.get('timestamp', 'Unknown'),
                'text_preview': node.text[:200] if hasattr(node, 'text') else ''
            })

        logger.info(f"✅ Retrieved {len(sources)} sources")

        return ChatResponse(
            question=message.question,
            answer=result['answer'],
            source_count=len(sources),
            sources=sources
        )

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.get("/chat/health")
async def chat_health():
    """Check if hybrid query engine is initialized"""
    return {
        "initialized": _initialized,
        "engine": "HybridQueryEngine" if query_engine else None
    }
