"""
Chat Routes - Simple Query Interface for Hybrid Property Graph System
Uses HybridPropertyGraphPipeline + HybridRetriever (Single PropertyGraphIndex with Neo4j + Qdrant)
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import Client

from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline
from app.services.ingestion.llamaindex.hybrid_retriever import create_hybrid_retriever
from app.core.dependencies import get_supabase
from app.core.security import get_current_user_id

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
    chat_id: Optional[str] = None


class ChatResponse(BaseModel):
    """Chat response"""
    question: str
    answer: str
    source_count: int
    sources: List[Dict[str, Any]]
    chat_id: str


class CreateChatRequest(BaseModel):
    """Create new chat"""
    title: Optional[str] = None


class ChatHistoryItem(BaseModel):
    """Chat history item"""
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int


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
async def chat(
    message: ChatMessage,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Simple chat interface for testing the hybrid property graph retrieval.
    Now saves chat history to Supabase!

    Uses:
    - Single PropertyGraphIndex combining Neo4j + Qdrant
    - VectorContextRetriever for graph-aware vector search
    - LLMSynonymRetriever for query expansion with entity synonyms
    - Multi-strategy concurrent retrieval with intelligent result merging

    Args:
        message: User question
        user_id: Authenticated user
        supabase: Supabase client

    Returns:
        ChatResponse: Answer + sources
    """
    try:
        # Initialize retriever (lazy)
        retriever = await _initialize_hybrid_retriever()

        logger.info(f"💬 Chat query: {message.question}")

        # Create or get chat
        chat_id = message.chat_id
        if not chat_id:
            # Create new chat
            chat_result = supabase.table('chats').insert({
                'company_id': user_id,
                'user_email': user_id,
                'title': message.question[:100]  # First 100 chars as title
            }).execute()
            chat_id = chat_result.data[0]['id']
            logger.info(f"📝 Created new chat: {chat_id}")

        # Save user message
        supabase.table('chat_messages').insert({
            'chat_id': chat_id,
            'role': 'user',
            'content': message.question
        }).execute()

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

        # Save assistant message
        supabase.table('chat_messages').insert({
            'chat_id': chat_id,
            'role': 'assistant',
            'content': result['answer'],
            'sources': sources
        }).execute()

        # Update chat timestamp
        supabase.table('chats').update({
            'updated_at': datetime.utcnow().isoformat()
        }).eq('id', chat_id).execute()

        logger.info(f"✅ Retrieved {len(sources)} sources, saved to chat {chat_id}")

        return ChatResponse(
            question=message.question,
            answer=result['answer'],
            source_count=len(sources),
            sources=sources,
            chat_id=chat_id
        )

    except Exception as e:
        logger.error(f"Chat error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.get("/chats")
async def list_chats(
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase),
    limit: int = 50
):
    """
    Get user's chat history.
    
    Returns list of chats ordered by most recent.
    """
    try:
        # Get chats
        result = supabase.table('chats')\
            .select('id, title, created_at, updated_at')\
            .eq('user_email', user_id)\
            .order('updated_at', desc=True)\
            .limit(limit)\
            .execute()

        chats = []
        for chat in result.data:
            # Get message count
            msg_result = supabase.table('chat_messages')\
                .select('id', count='exact')\
                .eq('chat_id', chat['id'])\
                .execute()
            
            chats.append({
                'id': chat['id'],
                'title': chat['title'],
                'created_at': chat['created_at'],
                'updated_at': chat['updated_at'],
                'message_count': msg_result.count or 0
            })

        return {'chats': chats}

    except Exception as e:
        logger.error(f"Failed to list chats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chats/{chat_id}/messages")
async def get_chat_messages(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get all messages in a chat.
    
    Returns messages in chronological order.
    """
    try:
        # Verify chat belongs to user
        chat_result = supabase.table('chats')\
            .select('id')\
            .eq('id', chat_id)\
            .eq('user_email', user_id)\
            .execute()

        if not chat_result.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        # Get messages
        result = supabase.table('chat_messages')\
            .select('*')\
            .eq('chat_id', chat_id)\
            .order('created_at', desc=False)\
            .execute()

        return {'messages': result.data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chats")
async def create_chat(
    request: CreateChatRequest,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Create a new empty chat.
    
    Returns the new chat ID.
    """
    try:
        result = supabase.table('chats').insert({
            'company_id': user_id,
            'user_email': user_id,
            'title': request.title or 'New Chat'
        }).execute()

        return {'chat_id': result.data[0]['id']}

    except Exception as e:
        logger.error(f"Failed to create chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chats/{chat_id}")
async def delete_chat(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Delete a chat and all its messages.
    
    Messages are automatically deleted via CASCADE.
    """
    try:
        # Verify ownership and delete
        result = supabase.table('chats')\
            .delete()\
            .eq('id', chat_id)\
            .eq('user_email', user_id)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Chat not found")

        return {'success': True}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/health")
async def chat_health():
    """Check if hybrid property graph system is initialized"""
    return {
        "initialized": _initialized,
        "pipeline": "HybridPropertyGraphPipeline" if hybrid_pipeline else None,
        "retriever": "HybridRetriever" if hybrid_retriever else None
    }
