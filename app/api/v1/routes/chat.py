"""
Chat Routes - Simple Query Interface for Hybrid Property Graph System
Uses HybridPropertyGraphPipeline + HybridRetriever (Single PropertyGraphIndex with Neo4j + Qdrant)
"""
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline
from app.services.ingestion.llamaindex.hybrid_retriever import create_hybrid_retriever

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Global hybrid property graph pipeline and retriever (lazy initialized)
hybrid_pipeline = None
hybrid_retriever = None
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


async def _initialize_hybrid_retriever():
    """Initialize the hybrid retriever (lazy)"""
    global hybrid_pipeline, hybrid_retriever, _initialized

    if not _initialized:
        logger.info("🚀 Initializing Hybrid PropertyGraph System...")

        # Initialize hybrid property graph pipeline (Single PropertyGraphIndex with Neo4j + Qdrant)
        hybrid_pipeline = HybridPropertyGraphPipeline()

        # Create hybrid retriever with 3 strategies:
        # 1. VectorContextRetriever - Graph-aware vector search
        # 2. LLMSynonymRetriever - Query expansion
        # 3. (Optional) CypherTemplateRetriever - Graph patterns
        hybrid_retriever = create_hybrid_retriever(
            pipeline=hybrid_pipeline,
            similarity_top_k=5,
            use_cypher=False  # Enable if you want Cypher templates
        )

        _initialized = True
        logger.info("✅ Hybrid Retriever ready (VectorContext + LLMSynonym)")

    return hybrid_retriever


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
        # Initialize retriever (lazy)
        retriever = await _initialize_hybrid_retriever()

        logger.info(f"💬 Chat query: {message.question}")

        # Execute hybrid query
        result = await retriever.query(message.question)

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
    """Check if hybrid property graph system is initialized"""
    return {
        "initialized": _initialized,
        "pipeline": "HybridPropertyGraphPipeline" if hybrid_pipeline else None,
        "retriever": "HybridRetriever" if hybrid_retriever else None
    }
