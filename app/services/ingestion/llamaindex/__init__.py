"""
LlamaIndex Hybrid Property Graph System (Production Architecture)

ARCHITECTURE:
- Single PropertyGraphIndex combining:
  - Neo4j: Graph storage for entities and relationships
  - Qdrant: Vector storage for semantic search
  - Three concurrent retrieval strategies:
    1. VectorContextRetriever: Graph-aware vector similarity search
    2. LLMSynonymRetriever: Query expansion with entity synonyms
    3. CypherTemplateRetriever (optional): Custom graph pattern matching

This is the recommended LlamaIndex pattern for hybrid RAG at scale:
- PropertyGraphIndex unifies graph + vector in single index
- Multiple retrievers run concurrently and merge results
- Best of both worlds: semantic search + relationship traversal

References:
- https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/
- https://docs.llamaindex.ai/en/stable/examples/property_graph/
"""

from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import (
    HybridPropertyGraphPipeline,
    create_hybrid_pipeline
)
from app.services.ingestion.llamaindex.hybrid_retriever import (
    HybridRetriever,
    create_hybrid_retriever
)

__all__ = [
    "HybridPropertyGraphPipeline",
    "create_hybrid_pipeline",
    "HybridRetriever",
    "create_hybrid_retriever"
]
