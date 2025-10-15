"""
Universal ingestion services.
Handles normalization and ingestion from ALL sources.
"""
from app.services.universal.ingest import ingest_document_universal

__all__ = ["ingest_document_universal"]
