"""
LlamaIndex Services (Expert Recommended Pattern)

Universal implementation:
- UniversalIngestionPipeline: Ingests ANY document to Qdrant + Neo4j
- HybridQueryEngine: SubQuestionQueryEngine for hybrid retrieval
"""

from .ingestion_pipeline import UniversalIngestionPipeline, create_ingestion_pipeline
from .query_engine import HybridQueryEngine, create_query_engine

__all__ = [
    "UniversalIngestionPipeline",
    "create_ingestion_pipeline",
    "HybridQueryEngine",
    "create_query_engine",
]
