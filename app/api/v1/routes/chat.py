"""
Chat Routes - Simple Query Interface for Hybrid Property Graph System
Uses HybridQueryEngine with SubQuestionQueryEngine (VectorStoreIndex + PropertyGraphIndex)
"""
import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from supabase import Client

from app.services.ingestion.llamaindex import HybridQueryEngine
from app.core.dependencies import get_supabase
from app.core.security import get_current_user_id
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])

# Global hybrid query engine (lazy initialized)
query_engine = None
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
@limiter.limit("20/minute")  # 20 chat requests per minute per IP
async def chat(
    request: Request,
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
        # Initialize query engine (lazy)
        engine = await _initialize_query_engine()

        logger.info(f"💬 Chat query: {message.question}")

        # Create or get chat
        chat_id = message.chat_id
        if not chat_id:
            # Generate iPhone Notes-style title (first 3-5 words)
            words = message.question.strip().split()
            title_words = words[:5] if len(words) > 5 else words
            title = ' '.join(title_words)
            if len(words) > 5:
                title += '...'

            # Create new chat
            chat_result = supabase.table('chats').insert({
                'company_id': user_id,
                'user_email': user_id,
                'title': title
            }).execute()
            chat_id = chat_result.data[0]['id']
            logger.info(f"📝 Created new chat: {chat_id} - '{title}'")

        # Save user message
        supabase.table('chat_messages').insert({
            'chat_id': chat_id,
            'role': 'user',
            'content': message.question
        }).execute()

        # Execute hybrid query
        result = await engine.query(message.question)

        logger.info(f"🔍 Query result keys: {result.keys()}")
        logger.info(f"🔍 Source nodes count: {len(result.get('source_nodes', []))}")

        # Format source nodes - Filter out entity nodes and deduplicate documents
        sources = []
        seen_documents = set()  # Track unique documents by ID or name
        source_index = 1
        
        for node in result.get('source_nodes', []):
            metadata = node.metadata if hasattr(node, 'metadata') else {}

            # Extract document_id for clickable sources - try multiple field names
            document_id = (
                metadata.get('document_id') or
                metadata.get('doc_id') or
                metadata.get('id') or
                None
            )

            # FILTER OUT non-document sources:
            # 1. Entity nodes (PERSON, COMPANY, etc.) - they don't have 'source' field
            # 2. Chunk nodes without proper document metadata
            # 3. Any node without a valid source system
            source_system = metadata.get('source', None)
            
            # Skip if no source system (likely an entity node)
            if not source_system or source_system == 'Unknown':
                logger.debug(f"   ⏭️  Skipping entity/chunk node. Available keys: {list(metadata.keys())}")
                continue
                
            # Skip if no document metadata at all
            has_doc_metadata = any([
                metadata.get('title'),
                metadata.get('document_name'), 
                metadata.get('document_type'),
                metadata.get('created_at'),
                document_id
            ])
            
            if not has_doc_metadata:
                logger.debug(f"   ⏭️  Skipping node without document metadata")
                continue

            # DEDUPLICATE: Create unique key for this document
            doc_name = metadata.get('title', metadata.get('document_name', 'Untitled'))
            unique_key = str(document_id) if document_id else f"{source_system}:{doc_name}"
            
            # Skip if we've already seen this document
            if unique_key in seen_documents:
                logger.debug(f"   🔄 Skipping duplicate document: {doc_name}")
                continue
                
            seen_documents.add(unique_key)

            # This is a valid, unique document source
            source_info = {
                'index': source_index,
                'document_id': str(document_id) if document_id is not None else None,
                'document_name': doc_name,
                'source': source_system,
                'document_type': metadata.get('document_type', 'document'),
                'timestamp': metadata.get('created_at', metadata.get('timestamp', 'Unknown')),
                'text_preview': node.text[:200] if hasattr(node, 'text') else '',
                'score': node.score if hasattr(node, 'score') else None
            }
            sources.append(source_info)
            logger.info(f"   📄 Source {source_index}: {source_info['source']} - {source_info['document_name']}")
            source_index += 1

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


@router.get("/sources/{document_id}")
async def get_source_document(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_supabase)
):
    """
    Get full document details for a source.
    Used when user clicks on a source bubble to see the original content.

    Returns:
        Full document with content, metadata, and context
    """
    try:
        # Fetch document from Supabase
        result = supabase.table('documents')\
            .select('*')\
            .eq('id', document_id)\
            .eq('tenant_id', user_id)\
            .execute()

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Source document not found")

        document = result.data[0]

        return {
            'id': document['id'],
            'title': document['title'],
            'content': document['content'],
            'source': document['source'],
            'document_type': document['document_type'],
            'source_id': document['source_id'],
            'created_at': document.get('source_created_at', document.get('ingested_at')),
            'metadata': document.get('metadata', {}),
            'raw_data': document.get('raw_data', {})
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chat/health")
async def chat_health():
    """Check if hybrid query engine is initialized"""
    return {
        "initialized": _initialized,
        "engine": "HybridQueryEngine" if query_engine else None
    }
