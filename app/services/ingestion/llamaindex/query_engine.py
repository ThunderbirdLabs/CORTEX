"""
LlamaIndex Query Engine (Expert Recommended Pattern)

Architecture:
- SubQuestionQueryEngine for hybrid retrieval
- VectorStoreIndex for semantic search (Qdrant)
- PropertyGraphIndex for graph queries (Neo4j)
- Intelligent routing and result synthesis
"""

import logging
from typing import Dict, Any, Optional

from llama_index.core import VectorStoreIndex
from llama_index.core.query_engine import SubQuestionQueryEngine
from llama_index.core.tools import QueryEngineTool
from llama_index.core.indices.property_graph import PropertyGraphIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from qdrant_client import QdrantClient, AsyncQdrantClient

from .config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME,
    OPENAI_API_KEY, QUERY_MODEL, QUERY_TEMPERATURE,
    EMBEDDING_MODEL, SIMILARITY_TOP_K
)

logger = logging.getLogger(__name__)


class HybridQueryEngine:
    """
    Hybrid query engine using SubQuestionQueryEngine.

    Combines:
    1. VectorStoreIndex (Qdrant) - Semantic search over document chunks
    2. PropertyGraphIndex (Neo4j) - Graph queries over Document/Person/Company/Entity nodes

    The SubQuestionQueryEngine:
    - Breaks down complex questions
    - Routes sub-questions to appropriate index
    - Synthesizes comprehensive answers
    """

    def __init__(self):
        logger.info("🚀 Initializing Hybrid Query Engine (Expert Pattern)")

        # LLM for query processing and synthesis
        self.llm = OpenAI(
            model=QUERY_MODEL,
            temperature=QUERY_TEMPERATURE,
            api_key=OPENAI_API_KEY,
            system_prompt=(
                "You are an intelligent personal assistant to the CEO. You have access to the entire companies knowledge. "
                "All emails, documents, deals, activities, orders, etc, that go on in this business is in your knowledge bases. "
                "Because of this, you know more about what is happening in the company than anyone. "
                "You can access and uncover unique relationships and patterns that otherwise would go unseen. "
                "Your job is to take all of the information you're given (comes from a vector store and knowledge graph) "
                "and formulate highly informative information for the CEO. "
                "Whenever you have the chance, make cool connections, insightful suggestions, and point the CEO in the right direction. "
                "Your job is to knock the CEO's socks off with how much you know about the business. "
                "Use quotes whenever you can to show you truly see what is happening."
            )
        )

        # Embedding model for vector search
        self.embed_model = OpenAIEmbedding(
            model_name=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )

        # Qdrant vector store (with async client for retrieval)
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        qdrant_aclient = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        vector_store = QdrantVectorStore(
            client=qdrant_client,
            aclient=qdrant_aclient,
            collection_name=QDRANT_COLLECTION_NAME
        )
        logger.info(f"✅ Qdrant Vector Store: {QDRANT_COLLECTION_NAME}")

        # VectorStoreIndex for semantic search
        self.vector_index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=self.embed_model
        )
        logger.info("✅ VectorStoreIndex created for semantic search")

        # Neo4j graph store
        graph_store = Neo4jPropertyGraphStore(
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            url=NEO4J_URI,
            database=NEO4J_DATABASE
        )
        logger.info(f"✅ Neo4j Graph Store: {NEO4J_URI}")

        # PropertyGraphIndex for graph queries
        self.property_graph_index = PropertyGraphIndex.from_existing(
            property_graph_store=graph_store,
            llm=self.llm,
            embed_model=self.embed_model
        )
        logger.info("✅ PropertyGraphIndex created for graph queries")

        # Create query engines
        self.vector_query_engine = self.vector_index.as_query_engine(
            similarity_top_k=SIMILARITY_TOP_K,
            llm=self.llm
        )

        self.graph_query_engine = self.property_graph_index.as_query_engine(
            llm=self.llm,
            include_text=True  # Include node text in retrieval
        )

        # Wrap as tools for SubQuestionQueryEngine
        vector_tool = QueryEngineTool.from_defaults(
            query_engine=self.vector_query_engine,
            name="vector_search",
            description=(
                "Useful for semantic search over document content. "
                "Use this for questions about what was said in documents, "
                "document content, topics discussed, specific information mentioned."
            )
        )

        graph_tool = QueryEngineTool.from_defaults(
            query_engine=self.graph_query_engine,
            name="graph_search",
            description=(
                "Useful for querying relationships between people, companies, and documents. "
                "Use this for questions about who sent what, who works where, "
                "connections between people, organizational structure."
            )
        )

        # SubQuestionQueryEngine (expert recommended)
        self.query_engine = SubQuestionQueryEngine.from_defaults(
            query_engine_tools=[vector_tool, graph_tool],
            llm=self.llm
        )
        logger.info("✅ SubQuestionQueryEngine ready (vector + graph)")

        logger.info("✅ Hybrid Query Engine ready")
        logger.info("   Architecture: SubQuestionQueryEngine")
        logger.info("   Indexes: VectorStoreIndex (Qdrant) + PropertyGraphIndex (Neo4j)")

    async def query(
        self,
        question: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute hybrid query.

        Process:
        1. SubQuestionQueryEngine breaks down the question
        2. Routes sub-questions to vector or graph index
        3. Retrieves relevant information from both sources
        4. Synthesizes comprehensive answer

        Args:
            question: User's question
            filters: Optional metadata filters

        Returns:
            Dict with answer, source nodes, and metadata
        """

        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 HYBRID QUERY: {question}")
        logger.info(f"{'='*80}")

        try:
            # Execute query through SubQuestionQueryEngine
            response = await self.query_engine.aquery(question)

            logger.info(f"✅ QUERY COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"   Answer length: {len(str(response))} characters")
            logger.info(f"   Source nodes: {len(response.source_nodes)}")

            return {
                "question": question,
                "answer": str(response),
                "source_nodes": response.source_nodes,
                "metadata": response.metadata if hasattr(response, "metadata") else {}
            }

        except Exception as e:
            error_msg = f"Query failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return {
                "question": question,
                "answer": "",
                "error": error_msg,
                "source_nodes": []
            }

    async def retrieve_only(
        self,
        question: str,
        use_vector: bool = True,
        use_graph: bool = True
    ):
        """
        Retrieve relevant nodes without synthesis.

        Args:
            question: Search query
            use_vector: Use vector search
            use_graph: Use graph search

        Returns:
            List of retrieved nodes
        """

        nodes = []

        if use_vector:
            try:
                vector_nodes = await self.vector_query_engine.aretrieve(question)
                nodes.extend(vector_nodes)
                logger.info(f"Retrieved {len(vector_nodes)} nodes from vector index")
            except Exception as e:
                logger.error(f"Vector retrieval failed: {e}")

        if use_graph:
            try:
                graph_nodes = await self.graph_query_engine.aretrieve(question)
                nodes.extend(graph_nodes)
                logger.info(f"Retrieved {len(graph_nodes)} nodes from graph index")
            except Exception as e:
                logger.error(f"Graph retrieval failed: {e}")

        return nodes


