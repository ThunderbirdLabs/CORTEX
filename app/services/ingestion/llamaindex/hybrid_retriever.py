"""
LlamaIndex Hybrid Retriever (Recommended Architecture)

TRUE HYBRID RETRIEVAL:
- Multiple specialized retrievers working together
- VectorContextRetriever: Graph-aware vector similarity
- LLMSynonymRetriever: Query expansion with synonyms
- CypherTemplateRetriever: Custom graph pattern matching (optional)
- TextToCypherRetriever: LLM-generated Cypher queries (optional)

This replaces SubQuestionQueryEngine with LlamaIndex's recommended
multi-strategy hybrid retrieval for Property Graphs.

References:
- https://docs.llamaindex.ai/en/stable/examples/property_graph/
- Property graphs support vector + symbolic retrieval simultaneously
"""

import logging
from typing import Dict, Any, List, Optional

from llama_index.core.indices.property_graph import (
    VectorContextRetriever,
    LLMSynonymRetriever,
    CypherTemplateRetriever,
    TextToCypherRetriever
)
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.response_synthesizers import get_response_synthesizer
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from pydantic import BaseModel, Field

from .hybrid_property_graph_pipeline import HybridPropertyGraphPipeline
from .config import (
    OPENAI_API_KEY, QUERY_MODEL, QUERY_TEMPERATURE,
    EMBEDDING_MODEL, VECTOR_SIMILARITY_TOP_K
)

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    True hybrid retrieval for Property Graphs.
    
    Combines multiple retrieval strategies:
    1. VectorContextRetriever - Graph-aware vector similarity search
    2. LLMSynonymRetriever - Query expansion with entity synonyms
    3. (Optional) CypherTemplateRetriever - Predefined graph patterns
    4. (Optional) TextToCypherRetriever - LLM-generated Cypher queries
    
    All strategies run concurrently and results are merged intelligently.
    
    This is the recommended LlamaIndex approach for querying Property Graphs.
    """
    
    def __init__(
        self,
        pipeline: HybridPropertyGraphPipeline,
        similarity_top_k: int = VECTOR_SIMILARITY_TOP_K,
        include_text: bool = True,
        use_cypher: bool = False  # Enable custom Cypher queries
    ):
        logger.info("🚀 Initializing Hybrid Retriever (LlamaIndex Recommended)")
        
        self.pipeline = pipeline
        self.index = pipeline.index
        
        # LLM for query processing and synthesis
        self.llm = OpenAI(
            model=QUERY_MODEL,
            temperature=QUERY_TEMPERATURE,
            api_key=OPENAI_API_KEY
        )
        
        # Embedding model for vector similarity
        self.embed_model = OpenAIEmbedding(
            model_name=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )
        
        # Build sub-retrievers
        self.sub_retrievers = []
        
        # 1. Vector Context Retriever
        # Graph-aware vector similarity - uses both graph structure and embeddings
        self.vector_retriever = VectorContextRetriever(
            self.index.property_graph_store,
            vector_store=self.index.vector_store,
            embed_model=self.embed_model,
            similarity_top_k=similarity_top_k,
            path_depth=2,  # Traverse 2 hops in graph from retrieved nodes
            include_text=include_text
        )
        self.sub_retrievers.append(self.vector_retriever)
        logger.info("✅ VectorContextRetriever: Graph-aware vector search (path_depth=2)")
        
        # 2. LLM Synonym Retriever
        # Expands query into synonyms and keywords for better entity matching
        self.synonym_retriever = LLMSynonymRetriever(
            self.index.property_graph_store,
            llm=self.llm,
            include_text=include_text
        )
        self.sub_retrievers.append(self.synonym_retriever)
        logger.info("✅ LLMSynonymRetriever: Query expansion with synonyms")
        
        # 3. (Optional) Cypher Template Retriever
        # For predefined graph patterns (e.g., "find all people working at X")
        if use_cypher:
            self._add_cypher_retrievers()
        
        # Create unified retriever combining all strategies
        self.retriever = self.index.as_retriever(
            sub_retrievers=self.sub_retrievers
        )
        logger.info(f"✅ Hybrid Retriever ready with {len(self.sub_retrievers)} strategies")
        
        # Create query engine with response synthesis
        self.query_engine = RetrieverQueryEngine.from_args(
            retriever=self.retriever,
            llm=self.llm,
            response_synthesizer=get_response_synthesizer(
                llm=self.llm,
                response_mode="compact"
            )
        )
        logger.info("✅ Query Engine ready with hybrid retrieval")
    
    def _add_cypher_retrievers(self):
        """Add Cypher-based retrievers for graph pattern matching."""
        
        # Example: Find people and their work relationships
        class WorkRelationParams(BaseModel):
            """Parameters for work relationship Cypher query."""
            names: List[str] = Field(
                description="Entity names or keywords related to people, companies, or projects"
            )
        
        work_cypher_query = """
            MATCH (person:PERSON)-[r:WORKS_AT|WORKS_ON|WORKS_WITH]->(target)
            WHERE person.name IN $names OR target.name IN $names
            RETURN person.name as person_name, type(r) as relationship, target.name as target_name, target.label as target_type
            LIMIT 20
        """
        
        cypher_template_retriever = CypherTemplateRetriever(
            self.index.property_graph_store,
            WorkRelationParams,
            work_cypher_query,
            llm=self.llm
        )
        self.sub_retrievers.append(cypher_template_retriever)
        logger.info("✅ CypherTemplateRetriever: Predefined work relationship patterns")
        
        # Alternative: Let LLM generate Cypher queries dynamically
        # Uncomment to enable:
        # text_to_cypher_retriever = TextToCypherRetriever(
        #     self.index.property_graph_store,
        #     llm=self.llm
        # )
        # self.sub_retrievers.append(text_to_cypher_retriever)
        # logger.info("✅ TextToCypherRetriever: LLM-generated Cypher queries")
    
    async def query(
        self,
        query_str: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute hybrid query across all retrieval strategies.
        
        Automatically:
        1. Runs vector similarity search (graph-aware)
        2. Expands query with synonyms
        3. (Optional) Executes Cypher patterns
        4. Merges all results intelligently
        5. Synthesizes comprehensive answer
        
        Args:
            query_str: User's question
            filters: Optional metadata filters
        
        Returns:
            Dict with answer, source nodes, and metadata
        """
        
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 HYBRID QUERY: {query_str}")
        logger.info(f"{'='*80}")
        
        # Execute query through all retrieval strategies
        response = await self.query_engine.aquery(query_str)
        
        logger.info(f"✅ QUERY COMPLETE")
        logger.info(f"{'='*80}")
        logger.info(f"   Retrieved {len(response.source_nodes)} source nodes")
        logger.info(f"   Strategies: {len(self.sub_retrievers)} (vector + synonym + ...)")
        
        return {
            'question': query_str,
            'answer': str(response),
            'source_nodes': response.source_nodes,
            'metadata': response.metadata
        }
    
    async def retrieve_only(
        self,
        query_str: str,
        similarity_top_k: Optional[int] = None
    ) -> List[Any]:
        """
        Retrieve relevant nodes without synthesis (for inspection).
        
        Args:
            query_str: Search query
            similarity_top_k: Override default top-k
        
        Returns:
            List of retrieved nodes
        """
        
        if similarity_top_k:
            # Temporarily adjust top-k
            old_k = self.vector_retriever.similarity_top_k
            self.vector_retriever.similarity_top_k = similarity_top_k
            nodes = await self.retriever.aretrieve(query_str)
            self.vector_retriever.similarity_top_k = old_k
        else:
            nodes = await self.retriever.aretrieve(query_str)
        
        logger.info(f"Retrieved {len(nodes)} nodes for: {query_str}")
        return nodes


# ============================================================================
# CONVENIENCE FACTORY
# ============================================================================

def create_hybrid_retriever(
    pipeline: HybridPropertyGraphPipeline,
    similarity_top_k: int = VECTOR_SIMILARITY_TOP_K,
    use_cypher: bool = False
) -> HybridRetriever:
    """
    Factory function to create HybridRetriever.
    
    Args:
        pipeline: Initialized HybridPropertyGraphPipeline
        similarity_top_k: Number of results for vector search
        use_cypher: Enable Cypher-based retrievers
    
    Returns:
        HybridRetriever ready to use
    """
    return HybridRetriever(
        pipeline=pipeline,
        similarity_top_k=similarity_top_k,
        use_cypher=use_cypher
    )
