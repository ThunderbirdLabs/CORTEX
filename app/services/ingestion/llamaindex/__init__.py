"""
LlamaIndex Hybrid Property Graph System
Official LlamaIndex recommended architecture

Architecture:
- Single unified PropertyGraphIndex
- Graph storage: Neo4j PropertyGraphStore (entities, relationships)
- Vector storage: Qdrant VectorStore (embedded graph nodes + document chunks)
- Extraction: SchemaLLMPathExtractor + ImplicitPathExtractor
- Retrieval: VectorContextRetriever + LLMSynonymRetriever (multi-strategy hybrid)

This follows the official LlamaIndex patterns:
https://docs.llamaindex.ai/en/stable/module_guides/indexing/lpg_index_guide/
"""
