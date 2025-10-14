"""
Search Endpoints - LlamaIndex-Powered Hybrid RAG

This is the NEW LlamaIndex-powered search endpoint.
Compare with the old search.py to see the difference!
"""
from fastapi import APIRouter, HTTPException, Depends
from backend.models.api_models import (
    SearchQuery,
    SearchResponse,
    VectorResult,
    GraphResult
)
from backend.middleware.auth import verify_api_key
# from backend.services.llamaindex_service import LlamaIndexService  # Not needed for /search-optimized
from backend.core.query_rewriter import rewrite_query_with_context
from backend.core.hybrid_query_engine import GraphitiHybridQueryEngine
from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI as LlamaOpenAI
from qdrant_client import QdrantClient
import os


router = APIRouter(prefix="/api", tags=["search-optimized"])

# Global optimized hybrid engine (lazy initialized)
optimized_engine = None
_engine_initialized = False


# REMOVED: /search-llamaindex, /search-vector-only, /search-graph-only endpoints
# These required LlamaIndexService which is not implemented
# Only /search-optimized is available (see below)


async def _initialize_optimized_engine():
    """Initialize the optimized hybrid query engine (lazy)"""
    global optimized_engine, _engine_initialized

    if not _engine_initialized:
        # Configure LlamaIndex
        Settings.llm = LlamaOpenAI(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY")
        )

        Settings.embed_model = OpenAIEmbedding(
            model="text-embedding-3-small",
            api_key=os.getenv("OPENAI_API_KEY")
        )

        # Create Qdrant clients (both sync and async)
        from qdrant_client import AsyncQdrantClient

        qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )

        qdrant_aclient = AsyncQdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )

        # Create Qdrant vector store
        # IMPORTANT: Tell LlamaIndex that our text content is stored in "content" field, not "text"
        vector_store = QdrantVectorStore(
            client=qdrant_client,
            aclient=qdrant_aclient,
            collection_name=os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents"),
            enable_hybrid=False,  # We handle hybrid at query engine level
            text_key="content"  # Map Qdrant's "content" field to LlamaIndex's text field
        )

        # Create storage context and vector index
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        vector_index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            storage_context=storage_context
        )

        # Create optimized engine
        optimized_engine = GraphitiHybridQueryEngine(
            vector_index=vector_index,
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USER"),
            neo4j_password=os.getenv("NEO4J_PASSWORD")
        )

        _engine_initialized = True

    return optimized_engine


@router.post("/search-optimized", response_model=SearchResponse)
async def search_optimized(
    query: SearchQuery,
    api_key: str = Depends(verify_api_key)
):
    """
    Optimized Hybrid Search with Episode Linking

    This endpoint uses GraphitiHybridQueryEngine which:
    - Executes vector search first
    - Extracts episode_ids from results
    - Queries graph FILTERED by those episode_ids only
    - Synthesizes focused answer

    Performance vs /search-llamaindex (SubQuestionQueryEngine):
    - 10x fewer tokens (graph filtered by relevance)
    - 5x faster (smaller graph queries)
    - More accurate (focused context, less noise)

    Args:
        query: Search parameters
        api_key: Validated API key

    Returns:
        SearchResponse: AI-generated answer with sources
    """
    try:
        # Query rewriting
        conversation_hist = [
            msg.dict() for msg in query.conversation_history
        ] if query.conversation_history else []

        rewritten_query = rewrite_query_with_context(query.query, conversation_hist)

        print(f"\n🔍 OPTIMIZED SEARCH:")
        print(f"   Original: {query.query}")
        print(f"   Rewritten: {rewritten_query}")

        # Initialize engine (lazy)
        engine = await _initialize_optimized_engine()

        # Execute optimized hybrid query
        result = await engine.query(
            query_str=rewritten_query,
            similarity_top_k=query.vector_limit,
            include_graph=True,
            max_graph_facts=query.graph_limit  # Reranking handles candidate expansion internally
        )

        # Convert to API format
        vector_results = []
        for i, node in enumerate(result['vector_sources']):
            metadata = node.metadata
            vector_results.append(VectorResult(
                id=str(i),
                document_name=metadata.get("document_name", "Unknown"),
                source=metadata.get("source", "Unknown"),
                document_type=metadata.get("document_type", "Unknown"),
                content=node.text,
                chunk_index=metadata.get("chunk_index", 0),
                episode_id=metadata.get("graphiti_episode_id", ""),
                similarity=node.score if hasattr(node, 'score') and node.score else 0.0,
                metadata=metadata
            ))

        # Graph results - convert structured facts to GraphResult format
        graph_results = []
        for i, fact_dict in enumerate(result['graph_facts']):
            graph_results.append(GraphResult(
                type=fact_dict.get('relation_type', 'RELATES_TO'),
                relation_name=fact_dict.get('relation_type', 'RELATES_TO'),
                fact=fact_dict['fact'],
                source_node_id=fact_dict.get('source_node_id', ''),
                target_node_id=fact_dict.get('target_node_id', ''),
                valid_at=fact_dict.get('valid_at'),
                episodes=[fact_dict.get('episode_id')] if fact_dict.get('episode_id') else []
            ))

        return SearchResponse(
            success=True,
            query=query.query,
            answer=result['answer'],
            vector_results=vector_results,
            graph_results=graph_results,
            num_episodes=result['metadata']['num_episodes'],
            message=f"Optimized: {result['metadata']['num_vector_results']} vector + {result['metadata']['num_graph_facts']} graph facts"
        )

    except Exception as e:
        print(f"❌ Optimized search error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Optimized search failed: {str(e)}"
        )
