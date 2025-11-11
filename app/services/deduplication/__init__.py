"""
DEPRECATED: Use app.services.preprocessing instead

This module has been moved to preprocessing.
All new code should import from app.services.preprocessing
"""

# Re-export content deduplication only (entity deduplication removed with Neo4j)
from app.services.preprocessing.content_deduplication import DedupeService, should_ingest_document

__all__ = ["DedupeService", "should_ingest_document"]

