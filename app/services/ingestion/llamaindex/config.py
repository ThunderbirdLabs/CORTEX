"""
LlamaIndex Configuration (Expert Recommended Pattern)

Architecture:
- IngestionPipeline → Qdrant (vector store) + Neo4j (knowledge graph)
- Custom Email, Person, Company nodes
- SubQuestionQueryEngine for hybrid retrieval
"""

import os
from typing import Literal
from dotenv import load_dotenv

load_dotenv()

# ============================================
# NEO4J CONFIGURATION
# ============================================

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = "neo4j"

# ============================================
# QDRANT CONFIGURATION
# ============================================

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

# ============================================
# OPENAI CONFIGURATION
# ============================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# LLM for entity extraction
EXTRACTION_MODEL = "gpt-4o-mini"
EXTRACTION_TEMPERATURE = 0.0

# LLM for queries and synthesis
QUERY_MODEL = "gpt-4o-mini"
QUERY_TEMPERATURE = 0.0  # IMPORTANT: 0 for deterministic Cypher generation (Neo4j + OpenAI best practice)

# Embeddings
EMBEDDING_MODEL = "text-embedding-3-small"

# ============================================
# SCHEMA CONFIGURATION (SchemaLLMPathExtractor)
# ============================================

# Entity Types - Injection Molding Manufacturing Focus
# Vector store handles document content - graph maps critical business relationships

# Default entity types (always active)
DEFAULT_ENTITIES = [
    "PERSON",         # Employees, contacts, account managers, suppliers
    "COMPANY",        # Clients, suppliers, vendors, partners
    "ROLE",           # Job titles: VP Sales, Quality Engineer, Procurement Manager, Account Manager
    "PURCHASE_ORDER", # Purchase orders, invoices, PO numbers
    "MATERIAL",       # Raw materials: polycarbonate, resins, steel, pellets, components
    "CERTIFICATION",  # ISO certs, material certifications, quality certifications
]

def _load_custom_entities():
    """
    Load custom entity types from admin_schema_overrides table.
    Called at startup to merge with default entities.
    Returns empty list if DB unavailable or on error.
    """
    try:
        from supabase import create_client
        import os

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            return []  # No DB config, use defaults only

        supabase = create_client(supabase_url, supabase_key)

        # Fetch active entity overrides
        result = supabase.table("admin_schema_overrides")\
            .select("entity_type")\
            .eq("override_type", "entity")\
            .eq("is_active", True)\
            .execute()

        custom_entities = [row["entity_type"] for row in result.data if row.get("entity_type")]

        if custom_entities:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Loaded {len(custom_entities)} custom entity types from database: {custom_entities}")

        return custom_entities

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️  Could not load custom entities from database: {e}. Using defaults only.")
        return []  # Fallback to defaults

def _load_custom_relations():
    """
    Load custom relationship types from admin_schema_overrides table.
    Called at startup to merge with default relationships.
    Returns empty list if DB unavailable or on error.
    """
    try:
        from supabase import create_client
        import os

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            return []

        supabase = create_client(supabase_url, supabase_key)

        # Fetch active relationship overrides
        result = supabase.table("admin_schema_overrides")\
            .select("relation_type")\
            .eq("override_type", "relation")\
            .eq("is_active", True)\
            .execute()

        custom_relations = [row["relation_type"] for row in result.data if row.get("relation_type")]

        if custom_relations:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"✅ Loaded {len(custom_relations)} custom relationship types from database: {custom_relations}")

        return custom_relations

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"⚠️  Could not load custom relationships from database: {e}. Using defaults only.")
        return []

# Merge default + custom entities and relationships
POSSIBLE_ENTITIES = DEFAULT_ENTITIES + _load_custom_entities()

# Relationship Types - Strict, False-Relationship Proof
# Design: Only extract relationships with EXPLICIT evidence, no inference

# Default relationship types (always active)
DEFAULT_RELATIONS = [
    # People relationships
    "WORKS_FOR",          # PERSON → COMPANY (employment)
    "WORKS_WITH",         # PERSON → PERSON/COMPANY (collaboration, contact)
    "HAS_ROLE",           # PERSON → ROLE (job title)
    "WORKS_ON",           # PERSON → PURCHASE_ORDER (who handles what)

    # Business relationships
    "SUPPLIES_TO",        # COMPANY → COMPANY (supplier relationship)
    "SUPPLIES",           # COMPANY → MATERIAL (what company supplies)

    # Materials & orders
    "CONTAINS",           # PURCHASE_ORDER → MATERIAL (what materials in order)
    "SENT_TO",            # PURCHASE_ORDER → PERSON/COMPANY (who receives PO)

    # Certifications
    "HAS_CERTIFICATION",  # COMPANY → CERTIFICATION
]

# Merge default + custom relationships
POSSIBLE_RELATIONS = DEFAULT_RELATIONS + _load_custom_relations()

# Validation Schema - Manufacturing-Critical Relationships Only
# Enforces relationship direction and valid entity connections
# Format: (HEAD_ENTITY, RELATIONSHIP, TAIL_ENTITY)
KG_VALIDATION_SCHEMA = [
    # ============================================
    # PEOPLE RELATIONSHIPS
    # ============================================
    ("PERSON", "WORKS_FOR", "COMPANY"),          # "John works for Acme"
    ("PERSON", "WORKS_WITH", "PERSON"),          # "John works with Sarah"
    ("PERSON", "WORKS_WITH", "COMPANY"),         # "John works with Acme" (contact/collaboration)
    ("PERSON", "HAS_ROLE", "ROLE"),              # "John has role VP of Sales"
    ("PERSON", "WORKS_ON", "PURCHASE_ORDER"),    # "Sarah works on PO #54321"

    # ============================================
    # BUSINESS RELATIONSHIPS
    # ============================================
    ("COMPANY", "SUPPLIES_TO", "COMPANY"),       # "Superior Mold supplies to Unit Industries"
    ("COMPANY", "WORKS_WITH", "COMPANY"),        # "Acme works with PolyPlastics"
    ("COMPANY", "SUPPLIES", "MATERIAL"),         # "Acme supplies polycarbonate"

    # ============================================
    # MATERIALS & ORDERS
    # ============================================
    ("PURCHASE_ORDER", "CONTAINS", "MATERIAL"),  # "PO #54321 contains polycarbonate"
    ("PURCHASE_ORDER", "SENT_TO", "PERSON"),     # "PO #54321 sent to John"
    ("PURCHASE_ORDER", "SENT_TO", "COMPANY"),    # "PO #54321 sent to Acme"

    # ============================================
    # CERTIFICATIONS
    # ============================================
    ("COMPANY", "HAS_CERTIFICATION", "CERTIFICATION"),
]

# Legacy Literal types (for backward compatibility)
ENTITIES = Literal[
    "PERSON", "COMPANY", "ROLE",
    "PURCHASE_ORDER", "MATERIAL", "CERTIFICATION"
]

RELATIONS = Literal[
    "WORKS_FOR", "WORKS_WITH", "HAS_ROLE", "WORKS_ON",
    "SUPPLIES_TO", "SUPPLIES",
    "CONTAINS", "SENT_TO",
    "HAS_CERTIFICATION"
]

VALIDATION_SCHEMA = KG_VALIDATION_SCHEMA  # Alias for backward compatibility

# ============================================
# INGESTION PIPELINE CONFIGURATION
# ============================================

# Text chunking (per expert guidance)
# Increased to 1024 to handle long attachment metadata (filenames + CID + properties)
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 50

# Vector search - Increased to 20 for better reranking performance
# Research: Retrieve more candidates (20) → rerank to final 10 for best accuracy
SIMILARITY_TOP_K = 20

# Progress display
SHOW_PROGRESS = True

# Parallel processing (production optimization)
NUM_WORKERS = 4  # For parallel node processing

# ============================================
# RELATIONSHIP VALIDATION CONFIGURATION
# ============================================

# Enable LLM-based quality filtering for knowledge graph
# Purpose: Keep high-insight relationships, reject low-quality entities
#
# Quality > Quantity for knowledge graphs:
# - Vector store handles generic semantic search
# - Knowledge graph provides PRECISE, ACTIONABLE business intelligence
# - Filters generic entities ("molding", "plastic") that add no insight
# - Prevents false relationships that lead to wrong business decisions
# - Keeps valuable relationships (company supply chains, org structure)
#
# Cost: ~$0.001 per document (~0.1¢)
# Performance: Adds ~200ms per relationship validation
ENABLE_RELATIONSHIP_VALIDATION = os.getenv("ENABLE_RELATIONSHIP_VALIDATION", "true").lower() == "true"

# ============================================
# CACHING CONFIGURATION (Production)
# ============================================

# Redis cache for IngestionPipeline (optional but recommended for production)
# Set to None to disable caching, or provide Redis connection details
REDIS_HOST = os.getenv("REDIS_HOST", None)  # e.g., "127.0.0.1" or "redis.example.com"
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
CACHE_COLLECTION = "cortex_ingestion_cache"

# Enable caching if Redis is configured
ENABLE_CACHE = REDIS_HOST is not None

# ============================================
# NEO4J PRODUCTION CONNECTION POOLING
# ============================================

# Connection pool optimization for Neo4j Aura
# Research: Neo4j best practices recommend 50 connections for production workloads
# https://neo4j.com/docs/operations-manual/current/performance/memory-configuration/#_connection_pool_size
NEO4J_MAX_POOL_SIZE = int(os.getenv("NEO4J_MAX_POOL_SIZE", "50"))

# Liveness check prevents using stale connections (FIXES CONNECTION RESET ERRORS)
# Research: Neo4j recommends 5s for cloud deployments with load balancers
# https://support.neo4j.com/s/article/14249408309395-Neo4j-Driver-Best-Practices
NEO4J_LIVENESS_CHECK_TIMEOUT = float(os.getenv("NEO4J_LIVENESS_CHECK_TIMEOUT", "5.0"))

# Connection timeout for initial TCP connection
NEO4J_CONNECTION_TIMEOUT = float(os.getenv("NEO4J_CONNECTION_TIMEOUT", "30.0"))

# Max time for transaction retries (handles transient failures)
NEO4J_MAX_RETRY_TIME = float(os.getenv("NEO4J_MAX_RETRY_TIME", "30.0"))

# Keep alive prevents idle connection drops
NEO4J_KEEP_ALIVE = os.getenv("NEO4J_KEEP_ALIVE", "true").lower() == "true"
