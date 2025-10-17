"""
LlamaIndex Services (Expert Recommended Pattern)

Universal implementation:
- UniversalIngestionPipeline: Ingests ANY document to Qdrant + Neo4j
- HybridQueryEngine: SubQuestionQueryEngine for hybrid retrieval
"""

from .ingestion_pipeline import UniversalIngestionPipeline
from .query_engine import HybridQueryEngine

__all__ = [
    "UniversalIngestionPipeline",
    "HybridQueryEngine",
]
