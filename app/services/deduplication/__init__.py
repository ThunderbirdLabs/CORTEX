"""
Deduplication Service
Prevents duplicate content from being ingested into RAG
"""
from .dedupe_service import DedupeService, should_ingest_document

__all__ = ["DedupeService", "should_ingest_document"]

