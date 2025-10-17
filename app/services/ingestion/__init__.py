"""
LlamaIndex Universal Ingestion System (Expert Pattern)
IngestionPipeline → Qdrant + Neo4j with SubQuestionQueryEngine
"""
from app.services.ingestion.llamaindex import (
    UniversalIngestionPipeline,
    create_ingestion_pipeline,
    HybridQueryEngine,
    create_query_engine
)

__all__ = [
    "UniversalIngestionPipeline",
    "create_ingestion_pipeline",
    "HybridQueryEngine",
    "create_query_engine"
]
