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
POSSIBLE_ENTITIES = [
    "PERSON",         # Employees, contacts, account managers, suppliers
    "COMPANY",        # Clients, suppliers, vendors, partners
    "ROLE",           # Job titles: VP Sales, Quality Engineer, Procurement Manager, Account Manager
    "DEAL",           # Orders, quotes, RFQs, sales opportunities
    "TASK",           # Action items, production tasks, follow-ups
    "MEETING",        # Calls, meetings, appointments, conferences
    "PAYMENT",        # Invoices, payments, purchase orders
    "MATERIAL",       # Raw materials: polycarbonate, resins, steel, pellets, components
    "CERTIFICATION",  # ISO certs, material certifications, quality certifications
    "PROJECT"         # Named programs/initiatives: ISO 9001 Audit, Tesla Model Y Program (proper names only)
]

# Relationship Types - Manufacturing-Critical Only
# These are the ONLY relationship types that will be extracted
POSSIBLE_RELATIONS = [
    # Organizational structure
    "WORKS_FOR", "REPORTS_TO", "HAS_ROLE",
    # Business relationships (supply chain critical)
    "CLIENT_OF", "VENDOR_OF", "SUPPLIES", "MANAGES",
    # Work assignments
    "ASSIGNED_TO", "ATTENDED_BY", "WORKS_ON",
    # Manufacturing dependencies (CRITICAL)
    "REQUIRES", "USED_IN", "PART_OF",
    # Certifications
    "HAS_CERTIFICATION",
    # Financial
    "PAID_BY", "PAID_TO",
    # Contact relationships
    "CONTACT_FOR"
]

# Validation Schema - Manufacturing-Critical Relationships Only
# Enforces relationship direction and valid entity connections
# Format: (HEAD_ENTITY, RELATIONSHIP, TAIL_ENTITY)
KG_VALIDATION_SCHEMA = [
    # ============================================
    # ORGANIZATIONAL STRUCTURE (Who works where)
    # ============================================
    ("PERSON", "WORKS_FOR", "COMPANY"),
    ("PERSON", "REPORTS_TO", "PERSON"),
    ("PERSON", "HAS_ROLE", "ROLE"),              # John Smith HAS_ROLE VP of Sales

    # ============================================
    # BUSINESS RELATIONSHIPS (Supply chain critical)
    # ============================================
    ("COMPANY", "CLIENT_OF", "COMPANY"),         # Acme CLIENT_OF Unit Industries
    ("COMPANY", "VENDOR_OF", "COMPANY"),         # Supplier VENDOR_OF Unit Industries
    ("COMPANY", "SUPPLIES", "MATERIAL"),         # Supplier SUPPLIES Polycarbonate PC-1000
    ("PERSON", "MANAGES", "COMPANY"),            # John MANAGES Acme (account manager)
    ("PERSON", "MANAGES", "MATERIAL"),           # Sarah MANAGES Polycarbonate (procurement)

    # ============================================
    # CONTACT RELATIONSHIPS (Who to reach)
    # ============================================
    ("PERSON", "CONTACT_FOR", "COMPANY"),        # John CONTACT_FOR Acme Corp (main contact)
    ("PERSON", "CONTACT_FOR", "DEAL"),           # Sarah CONTACT_FOR Deal #12345 (point person)

    # ============================================
    # WORK ASSIGNMENTS (Who does what)
    # ============================================
    ("DEAL", "ASSIGNED_TO", "PERSON"),           # Deal ASSIGNED_TO sales rep
    ("TASK", "ASSIGNED_TO", "PERSON"),           # Task ASSIGNED_TO engineer
    ("MEETING", "ATTENDED_BY", "PERSON"),        # Meeting ATTENDED_BY attendees
    ("PERSON", "WORKS_ON", "PROJECT"),           # Person WORKS_ON ISO 9001 Project

    # ============================================
    # MANUFACTURING DEPENDENCIES (What requires what)
    # ============================================
    ("DEAL", "REQUIRES", "MATERIAL"),            # Order REQUIRES Polycarbonate
    ("DEAL", "REQUIRES", "CERTIFICATION"),       # Order REQUIRES ISO 9001 cert
    ("TASK", "REQUIRES", "MATERIAL"),            # Production task REQUIRES steel
    ("MATERIAL", "USED_IN", "DEAL"),             # Polycarbonate USED_IN Deal #123
    ("MATERIAL", "USED_IN", "PROJECT"),          # Steel USED_IN Tesla Model Y
    ("DEAL", "PART_OF", "PROJECT"),              # Deal PART_OF customer program
    ("TASK", "PART_OF", "PROJECT"),              # Task PART_OF quality initiative

    # ============================================
    # CERTIFICATIONS (Compliance tracking)
    # ============================================
    ("COMPANY", "HAS_CERTIFICATION", "CERTIFICATION"),    # Supplier HAS_CERTIFICATION ISO 9001
    ("MATERIAL", "HAS_CERTIFICATION", "CERTIFICATION"),   # Material HAS_CERTIFICATION FDA approved
    ("PERSON", "HAS_CERTIFICATION", "CERTIFICATION"),     # Engineer HAS_CERTIFICATION Six Sigma

    # ============================================
    # FINANCIAL (Payments)
    # ============================================
    ("PAYMENT", "PAID_BY", "COMPANY"),           # Payment PAID_BY Unit Industries
    ("PAYMENT", "PAID_TO", "COMPANY"),           # Payment PAID_TO Supplier
    ("PAYMENT", "PART_OF", "DEAL"),              # Payment PART_OF Deal #123
]

# Legacy Literal types (for backward compatibility)
ENTITIES = Literal[
    "PERSON", "COMPANY", "ROLE", "DEAL", "TASK",
    "MEETING", "PAYMENT", "MATERIAL", "CERTIFICATION", "PROJECT"
]

RELATIONS = Literal[
    "WORKS_FOR", "REPORTS_TO", "HAS_ROLE",
    "CLIENT_OF", "VENDOR_OF", "SUPPLIES", "MANAGES",
    "ASSIGNED_TO", "ATTENDED_BY", "WORKS_ON",
    "REQUIRES", "USED_IN", "PART_OF",
    "HAS_CERTIFICATION",
    "PAID_BY", "PAID_TO",
    "CONTACT_FOR"
]

VALIDATION_SCHEMA = KG_VALIDATION_SCHEMA  # Alias for backward compatibility

# ============================================
# INGESTION PIPELINE CONFIGURATION
# ============================================

# Text chunking (per expert guidance)
# Increased to 1024 to handle long attachment metadata (filenames + CID + properties)
CHUNK_SIZE = 1024
CHUNK_OVERLAP = 50

# Vector search
SIMILARITY_TOP_K = 10

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
