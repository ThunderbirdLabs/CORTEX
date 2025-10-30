"""
DEPRECATED: Use app.services.preprocessing instead

This module has been moved to preprocessing.
All new code should import from app.services.preprocessing
"""

# Re-export everything from new location for backward compatibility
from app.services.preprocessing.content_deduplication import DedupeService, should_ingest_document
from app.services.preprocessing.entity_deduplication import EntityDeduplicationService, run_entity_deduplication

__all__ = ["DedupeService", "should_ingest_document", "EntityDeduplicationService", "run_entity_deduplication"]

