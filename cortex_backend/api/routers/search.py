"""
Search Endpoints - Hybrid vector + knowledge graph search
"""
from fastapi import APIRouter, HTTPException, Depends
from backend.models.api_models import (
    SearchQuery,
    SearchResponse,
    VectorResult,
    GraphResult
)
from backend.middleware.auth import verify_api_key
from backend.core.search import HybridSearch
from backend.core.query_rewriter import rewrite_query_with_context
from backend.core.response_generator import generate_conversational_response


router = APIRouter(prefix="/api", tags=["search"])

# Global search engine instance (will be injected via dependency)
search_engine = HybridSearch()


@router.post("/search", response_model=SearchResponse)
async def hybrid_search(
    query: SearchQuery,
    api_key: str = Depends(verify_api_key)
):
    """
    Perform hybrid search and generate conversational AI response

    This implements a 3-step RAG pipeline:
    1. Query Rewriting: Convert vague follow-up questions into explicit queries
    2. Hybrid Retrieval: Search both vector DB and knowledge graph
    3. Response Generation: Synthesize natural language answer with LLM

    Args:
        query: Search parameters including query text, limits, and conversation history
        api_key: Validated API key from header

    Returns:
        SearchResponse: AI-generated answer plus vector and graph results
    """
    try:
        # STEP 1: Rewrite vague queries with conversation context
        conversation_hist = [
            msg.dict() for msg in query.conversation_history
        ] if query.conversation_history else []

        rewritten_query = rewrite_query_with_context(query.query, conversation_hist)

        print(f"\n🔍 QUERY REWRITING:")
        print(f"   Original: {query.query}")
        print(f"   Rewritten: {rewritten_query}")

        # STEP 2: Perform hybrid search with rewritten query
        results = await search_engine.hybrid_search(
            query=rewritten_query,  # Use rewritten query for better retrieval
            vector_limit=query.vector_limit,
            graph_limit=query.graph_limit,
            source_filter=query.source_filter
        )

        # Convert results to Pydantic models
        vector_results = [
            VectorResult(
                id=r["id"],
                document_name=r["document_name"],
                source=r["source"],
                document_type=r["document_type"],
                content=r["content"],
                chunk_index=r["chunk_index"],
                episode_id=r["episode_id"],
                similarity=r["similarity"],
                metadata=r.get("metadata")
            )
            for r in results["vector_results"]
        ]

        graph_results = [
            GraphResult(
                type=r["type"],
                relation_name=r["relation_name"],
                fact=r["fact"],
                source_node_id=r["source_node_id"],
                target_node_id=r["target_node_id"],
                valid_at=r.get("valid_at"),
                episodes=r["episodes"]
            )
            for r in results["graph_results"]
        ]

        # STEP 3: Generate conversational AI response
        # Use original query so the answer matches what the user asked
        ai_answer = generate_conversational_response(
            query=query.query,
            vector_results=results["vector_results"],
            graph_results=results["graph_results"],
            conversation_history=conversation_hist
        )

        return SearchResponse(
            success=True,
            query=query.query,  # Return original query for display
            answer=ai_answer,
            vector_results=vector_results,
            graph_results=graph_results,
            num_episodes=results["num_episodes"],
            message=f"Found {len(vector_results)} vector results and {len(graph_results)} graph relationships"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )
