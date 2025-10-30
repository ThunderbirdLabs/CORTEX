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

# Entity Types - Loaded from Master Supabase
# Vector store handles document content - graph maps critical business relationships

# NOTE: Default entities moved to master Supabase (company_schemas table)
# Each company can have their own entity types stored in master
# Backend loads at startup based on COMPANY_ID
DEFAULT_ENTITIES = []  # Empty - all entities loaded from master Supabase

def _load_custom_entities():
    """
    Load entity types from master Supabase and convert to Pydantic Enum type.
    MULTI-TENANT: Loads from master Supabase (company_schemas table, schema_type='entities')
    Called at startup. Returns None if DB unavailable or on error.

    Returns:
        Enum type for LlamaIndex SchemaLLMPathExtractor, or None if failed
    """
    try:
        from supabase import create_client
        from enum import Enum
        import os
        import logging
        import json
        logger = logging.getLogger(__name__)

        # Check for multi-tenant mode
        company_id = os.getenv("COMPANY_ID")
        master_url = os.getenv("MASTER_SUPABASE_URL")
        master_key = os.getenv("MASTER_SUPABASE_SERVICE_KEY")

        if not company_id or not master_url or not master_key:
            logger.warning("⚠️  Missing COMPANY_ID or master Supabase credentials. No entities loaded.")
            return None

        # MULTI-TENANT MODE: Load from master Supabase (JSON FORMAT)
        logger.info(f"🏢 Loading entities from MASTER Supabase (Company ID: {company_id})")

        master = create_client(master_url, master_key)

        # Fetch THIS company's entities (JSON array)
        result = master.table("company_schemas")\
            .select("schema_content")\
            .eq("company_id", company_id)\
            .eq("schema_type", "entities")\
            .eq("is_active", True)\
            .execute()

        if result.data:
            # Parse JSON array from schema_content
            schema_content = result.data[0]["schema_content"]
            entity_list = json.loads(schema_content)

            # Convert to Enum type for LlamaIndex (Pydantic 2 requirement)
            # Creates: EntityType = Enum('EntityType', {PERSON: PERSON, COMPANY: COMPANY, ...})
            entity_enum = Enum('EntityType', {name: name for name in entity_list})

            logger.info(f"✅ Loaded {len(entity_list)} entities from master: {entity_list}")
            return entity_enum
        else:
            logger.error("❌ No entities found in master for this company! Graph extraction will fail.")
            return None

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Failed to load entities: {e}")
        return None

def _load_custom_relations():
    """
    Load relationship types from master Supabase and convert to Pydantic Enum type.
    MULTI-TENANT: Loads from master Supabase (company_schemas table, schema_type='relations')
    Called at startup. Returns None if DB unavailable or on error.

    Returns:
        Enum type for LlamaIndex SchemaLLMPathExtractor, or None if failed
    """
    try:
        from supabase import create_client
        from enum import Enum
        import os
        import logging
        import json
        logger = logging.getLogger(__name__)

        # Check for multi-tenant mode
        company_id = os.getenv("COMPANY_ID")
        master_url = os.getenv("MASTER_SUPABASE_URL")
        master_key = os.getenv("MASTER_SUPABASE_SERVICE_KEY")

        if not company_id or not master_url or not master_key:
            logger.warning("⚠️  Missing COMPANY_ID or master Supabase credentials. No relations loaded.")
            return None

        # MULTI-TENANT MODE: Load from master Supabase (JSON FORMAT)
        logger.info(f"🏢 Loading relations from MASTER Supabase (Company ID: {company_id})")

        master = create_client(master_url, master_key)

        # Fetch THIS company's relations (JSON array)
        result = master.table("company_schemas")\
            .select("schema_content")\
            .eq("company_id", company_id)\
            .eq("schema_type", "relations")\
            .eq("is_active", True)\
            .execute()

        if result.data:
            # Parse JSON array from schema_content
            schema_content = result.data[0]["schema_content"]
            relation_list = json.loads(schema_content)

            # Convert to Enum type for LlamaIndex (Pydantic 2 requirement)
            relation_enum = Enum('RelationType', {name: name for name in relation_list})

            logger.info(f"✅ Loaded {len(relation_list)} relations from master: {relation_list}")
            return relation_enum
        else:
            logger.error("❌ No relations found in master for this company! Graph extraction will fail.")
            return None

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Failed to load relations: {e}")
        return None

def _load_validation_schema():
    """
    Load validation schema (allowed triplets) from master Supabase (NEW: JSON nested array format).
    MULTI-TENANT: Loads from master Supabase (company_schemas table, schema_type='validation_schema')
    Returns list of tuples like [("PERSON", "WORKS_FOR", "COMPANY"), ...].
    Returns empty list if DB unavailable or on error.
    """
    try:
        from supabase import create_client
        import os
        import logging
        import json
        logger = logging.getLogger(__name__)

        # Check for multi-tenant mode
        company_id = os.getenv("COMPANY_ID")
        master_url = os.getenv("MASTER_SUPABASE_URL")
        master_key = os.getenv("MASTER_SUPABASE_SERVICE_KEY")

        if not company_id or not master_url or not master_key:
            logger.warning("⚠️  Missing COMPANY_ID or master Supabase credentials. No validation schema loaded.")
            return []

        # MULTI-TENANT MODE: Load from master Supabase (JSON FORMAT)
        logger.info(f"🏢 Loading validation schema from MASTER Supabase (Company ID: {company_id})")

        master = create_client(master_url, master_key)

        # Fetch THIS company's validation schema (nested JSON array)
        result = master.table("company_schemas")\
            .select("schema_content")\
            .eq("company_id", company_id)\
            .eq("schema_type", "validation_schema")\
            .eq("is_active", True)\
            .execute()

        if result.data:
            # Parse nested JSON array and convert to tuples
            schema_content = result.data[0]["schema_content"]
            nested_arrays = json.loads(schema_content)
            validation_tuples = [tuple(item) for item in nested_arrays]

            logger.info(f"✅ Loaded {len(validation_tuples)} validation triplets from master")
            return validation_tuples
        else:
            logger.error("❌ No validation schema found in master for this company! Graph extraction will fail.")
            return []

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Failed to load validation schema: {e}")
        return []

def _load_quality_rules():
    """
    Load entity quality rules from master Supabase (NEW: JSON object format).
    MULTI-TENANT: Loads from master Supabase (company_schemas table, schema_type='entity_quality_rules')
    Returns dict like {"PERSON": {"min_words": 2, "reject_if_contains": [...]}, ...}.
    Returns empty dict if DB unavailable or on error.
    """
    try:
        from supabase import create_client
        import os
        import logging
        import json
        logger = logging.getLogger(__name__)

        # Check for multi-tenant mode
        company_id = os.getenv("COMPANY_ID")
        master_url = os.getenv("MASTER_SUPABASE_URL")
        master_key = os.getenv("MASTER_SUPABASE_SERVICE_KEY")

        if not company_id or not master_url or not master_key:
            logger.warning("⚠️  Missing COMPANY_ID or master Supabase credentials. No quality rules loaded.")
            return {}

        # MULTI-TENANT MODE: Load from master Supabase (JSON FORMAT)
        logger.info(f"🏢 Loading entity quality rules from MASTER Supabase (Company ID: {company_id})")

        master = create_client(master_url, master_key)

        # Fetch THIS company's quality rules (JSON object)
        result = master.table("company_schemas")\
            .select("schema_content")\
            .eq("company_id", company_id)\
            .eq("schema_type", "entity_quality_rules")\
            .eq("is_active", True)\
            .execute()

        if result.data:
            # Parse JSON object from schema_content
            schema_content = result.data[0]["schema_content"]
            quality_rules = json.loads(schema_content)

            logger.info(f"✅ Loaded quality rules for {len(quality_rules)} entity types from master")
            return quality_rules
        else:
            logger.error("❌ No entity quality rules found in master for this company! Entity filtering may not work properly.")
            return {}

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"❌ Failed to load entity quality rules: {e}")
        return {}


# ============================================
# LOAD ALL SCHEMAS FROM MASTER SUPABASE
# ============================================
# Multi-tenant: Each company gets its own schema based on COMPANY_ID env var
# All schemas loaded dynamically from master Supabase at startup

POSSIBLE_ENTITIES = _load_custom_entities()
POSSIBLE_RELATIONS = _load_custom_relations()
KG_VALIDATION_SCHEMA = _load_validation_schema()
ENTITY_QUALITY_RULES = _load_quality_rules()

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
