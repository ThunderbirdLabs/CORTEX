"""
Deduplication Service
Prevents duplicate content from being ingested into RAG
"""
from .dedupe_service import DedupeService, should_ingest_document
from .entity_deduplication import EntityDeduplicationService, run_entity_deduplication

__all__ = ["DedupeService", "should_ingest_document", "EntityDeduplicationService", "run_entity_deduplication"]

