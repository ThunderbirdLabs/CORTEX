"""
Production Ingestion Script: Supabase → Hybrid Property Graph Pipeline

Fetches emails/documents from Supabase and ingests them into:
- Neo4j PropertyGraphStore (entities, relationships, graph structure)
- Qdrant VectorStore (embeddings of all graph nodes)
- Unified PropertyGraphIndex with seamless linking

Usage:
    python ingest_from_supabase.py --table emails --limit 25
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
import argparse

from dotenv import load_dotenv
from supabase import create_client

from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline
from app.core.config import settings

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def ingest_from_supabase(
    table_name: str = "emails",
    limit: int = 25,
    tenant_id: str = None
):
    """
    Fetch rows from Supabase and ingest into hybrid property graph pipeline.

    Args:
        table_name: Supabase table to fetch from (emails, documents, messages, etc.)
        limit: Maximum number of rows to process
        tenant_id: Optional tenant filter
    """
    
    logger.info("="*80)
    logger.info("PRODUCTION INGESTION: Supabase → Hybrid Property Graph")
    logger.info("="*80)
    logger.info(f"Table: {table_name}")
    logger.info(f"Limit: {limit}")
    if tenant_id:
        logger.info(f"Tenant: {tenant_id}")
    logger.info("="*80 + "\n")

    # Initialize Supabase client
    supabase = create_client(settings.supabase_url, settings.supabase_anon_key)
    logger.info("✅ Supabase client initialized")

    # Initialize Hybrid Property Graph Pipeline
    pipeline = HybridPropertyGraphPipeline()
    logger.info("✅ Hybrid Property Graph Pipeline initialized\n")
    
    try:
        # Fetch rows from Supabase
        logger.info(f"📥 Fetching rows from '{table_name}' table...")
        
        query = supabase.table(table_name).select("*")
        
        if tenant_id:
            query = query.eq("tenant_id", tenant_id)
        
        result = query.limit(limit).execute()
        
        rows = result.data if result.data else []
        logger.info(f"✅ Fetched {len(rows)} rows\n")
        
        if not rows:
            logger.warning("No rows found. Exiting.")
            return
        
        # Ingest each row
        success_count = 0
        error_count = 0
        
        for i, row in enumerate(rows, 1):
            try:
                logger.info(f"\n{'='*80}")
                logger.info(f"Processing {i}/{len(rows)}")
                logger.info(f"{'='*80}")
                
                # Extract fields based on table type
                if table_name == "emails":
                    content = row.get("full_body", row.get("body", ""))
                    doc_name = row.get("subject", "No Subject")
                    source = row.get("source", "email")
                    doc_type = "email"
                    ref_time = row.get("received_datetime")
                    
                elif table_name == "documents":
                    content = row.get("content", "")
                    doc_name = row.get("title", "Untitled")
                    source = row.get("source", "document")
                    doc_type = "document"
                    ref_time = row.get("created_at")
                    
                elif table_name == "messages":
                    content = row.get("text", "")
                    doc_name = row.get("channel", "Direct Message")
                    source = row.get("source", "message")
                    doc_type = "message"
                    ref_time = row.get("timestamp")
                    
                else:
                    # Generic handling
                    content = row.get("content", row.get("body", str(row)))
                    doc_name = row.get("name", row.get("title", f"Row {i}"))
                    source = row.get("source", table_name)
                    doc_type = table_name.rstrip('s')  # emails -> email
                    ref_time = row.get("created_at")
                
                # Parse reference time
                if ref_time and isinstance(ref_time, str):
                    try:
                        ref_time = datetime.fromisoformat(ref_time.replace('Z', '+00:00'))
                    except:
                        ref_time = datetime.now()
                elif not ref_time:
                    ref_time = datetime.now()
                
                # Skip if no content
                if not content or len(content.strip()) < 10:
                    logger.warning(f"Skipping row {i}: insufficient content")
                    continue
                
                # Build metadata
                metadata = {
                    "supabase_id": row.get("id"),
                    "tenant_id": row.get("tenant_id"),
                    "user_id": row.get("user_id"),
                }
                
                # Add table-specific metadata
                if table_name == "emails":
                    metadata.update({
                        "message_id": row.get("message_id"),
                        "sender_name": row.get("sender_name"),
                        "sender_address": row.get("sender_address"),
                        "to_addresses": row.get("to_addresses", []),
                        "web_link": row.get("web_link")
                    })
                
                # Ingest into hybrid property graph pipeline
                result = await pipeline.ingest_document(
                    content=content,
                    document_name=doc_name,
                    source=source,
                    document_type=doc_type,
                    reference_time=ref_time,
                    metadata=metadata
                )

                if result['status'] == 'error':
                    logger.warning(f"⚠️  Ingestion failed: {result.get('error')}")
                    error_count += 1
                else:
                    logger.info(f"✅ Success! Document: {result['document_name']}")
                    success_count += 1

                    # TODO: Optionally update Supabase row with metadata
                    # Note: Hybrid system doesn't use episode_id the same way
                    # Data is linked through PropertyGraphIndex automatically
                
            except Exception as e:
                logger.error(f"❌ Failed to process row {i}: {e}", exc_info=True)
                error_count += 1
                continue
        
        # Summary
        logger.info(f"\n{'='*80}")
        logger.info("📊 INGESTION SUMMARY")
        logger.info(f"{'='*80}")
        logger.info(f"Total rows processed: {len(rows)}")
        logger.info(f"Successful: {success_count}")
        logger.info(f"Errors: {error_count}")
        logger.info(f"{'='*80}\n")
        
        # Get pipeline stats
        stats = pipeline.get_stats()
        logger.info("📊 PIPELINE STATISTICS")
        logger.info(f"{'='*80}")
        logger.info(f"Vector Store (Qdrant):")
        for key, value in stats['vector'].items():
            logger.info(f"  {key}: {value}")
        logger.info(f"\nKnowledge Graph (Neo4j):")
        for key, value in stats['graph'].items():
            logger.info(f"  {key}: {value}")
        logger.info(f"{'='*80}\n")
        
    finally:
        await pipeline.close()
        logger.info("✅ Pipeline closed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Supabase data into Hybrid Property Graph Pipeline")
    parser.add_argument("--table", default="emails", help="Supabase table name (default: emails)")
    parser.add_argument("--limit", type=int, default=25, help="Max rows to process (default: 25)")
    parser.add_argument("--tenant", help="Filter by tenant_id (optional)")
    
    args = parser.parse_args()
    
    asyncio.run(ingest_from_supabase(
        table_name=args.table,
        limit=args.limit,
        tenant_id=args.tenant
    ))
