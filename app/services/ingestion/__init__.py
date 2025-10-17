"""
LlamaIndex Universal Ingestion System (Expert Pattern)
IngestionPipeline → Qdrant + Neo4j with SubQuestionQueryEngine
"""
from app.services.ingestion.llamaindex import (
    UniversalIngestionPipeline,
    HybridQueryEngine
)

__all__ = [
    "UniversalIngestionPipeline",
    "HybridQueryEngine"
]
