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
QUERY_TEMPERATURE = 0.3

# Embeddings
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# ============================================
# SCHEMA CONFIGURATION (SchemaLLMPathExtractor)
# ============================================

# Entity Types - Optimized for CEO business intelligence
# These are the ONLY entity types that will be extracted
POSSIBLE_ENTITIES = [
    "PERSON",      # Anyone: employees, customers, vendors, contacts
    "COMPANY",     # Any business: clients, suppliers, competitors, departments
    "EMAIL",       # Email messages (extracted from content, not document nodes)
    "DOCUMENT",    # Files: contracts, invoices, reports, PDFs (extracted from content)
    "DEAL",        # Opportunities, sales, orders, quotes
    "TASK",        # Action items, follow-ups, requests
    "MEETING",     # Calls, meetings, appointments
    "PAYMENT",     # Invoices, payments, expenses, POs
    "TOPIC",       # Subjects, projects, products, issues
    "EVENT"        # Catch-all: conferences, launches, deadlines, milestones
]

# Relationship Types - Natural language for LLM understanding
# These are the ONLY relationship types that will be extracted
POSSIBLE_RELATIONS = [
    # Who did what
    "SENT_BY", "SENT_TO", "CREATED_BY", "ASSIGNED_TO", "ATTENDED_BY",
    # Organization
    "WORKS_FOR", "WORKS_WITH", "REPORTS_TO",
    # Business relationships
    "CLIENT_OF", "VENDOR_OF",
    # Content connections
    "ABOUT", "MENTIONS", "RELATES_TO", "ATTACHED_TO",
    # Status & actions
    "REQUIRES", "FOLLOWS_UP", "RESOLVES",
    # Financial
    "PAID_BY", "PAID_TO"
]

# Validation Schema - Defines which entities can have which relationships
# SchemaLLMPathExtractor uses this to validate extracted relationships
KG_VALIDATION_SCHEMA = {
    "PERSON": [
        "SENT_BY", "SENT_TO", "CREATED_BY", "ASSIGNED_TO", "ATTENDED_BY",
        "WORKS_FOR", "WORKS_WITH", "REPORTS_TO",
        "PAID_BY", "PAID_TO",
        "MENTIONS", "RELATES_TO", "ABOUT"
    ],
    "COMPANY": [
        "SENT_BY", "SENT_TO",
        "WORKS_FOR", "CLIENT_OF", "VENDOR_OF",
        "PAID_BY", "PAID_TO",
        "MENTIONS", "RELATES_TO", "ABOUT"
    ],
    "EMAIL": [
        "SENT_BY", "SENT_TO",
        "ABOUT", "MENTIONS", "RELATES_TO", "ATTACHED_TO",
        "FOLLOWS_UP", "RESOLVES"
    ],
    "DOCUMENT": [
        "SENT_BY", "CREATED_BY",
        "ABOUT", "MENTIONS", "RELATES_TO", "ATTACHED_TO"
    ],
    "DEAL": [
        "CREATED_BY", "ASSIGNED_TO",
        "ABOUT", "MENTIONS", "RELATES_TO",
        "REQUIRES", "FOLLOWS_UP"
    ],
    "TASK": [
        "CREATED_BY", "ASSIGNED_TO",
        "ABOUT", "RELATES_TO",
        "REQUIRES", "RESOLVES"
    ],
    "MEETING": [
        "ATTENDED_BY",
        "ABOUT", "MENTIONS", "RELATES_TO",
        "FOLLOWS_UP"
    ],
    "PAYMENT": [
        "PAID_BY", "PAID_TO",
        "RELATES_TO", "ABOUT"
    ],
    "TOPIC": [
        "ABOUT", "MENTIONS", "RELATES_TO"
    ],
    "EVENT": [
        "CREATED_BY", "ATTENDED_BY",
        "ABOUT", "MENTIONS", "RELATES_TO"
    ]
}

# Legacy Literal types (for backward compatibility)
ENTITIES = Literal[
    "PERSON", "COMPANY", "EMAIL", "DOCUMENT", "DEAL", "TASK",
    "MEETING", "PAYMENT", "TOPIC", "EVENT"
]

RELATIONS = Literal[
    "SENT_BY", "SENT_TO", "CREATED_BY", "ASSIGNED_TO", "ATTENDED_BY",
    "WORKS_FOR", "WORKS_WITH", "REPORTS_TO",
    "CLIENT_OF", "VENDOR_OF",
    "ABOUT", "MENTIONS", "RELATES_TO", "ATTACHED_TO",
    "REQUIRES", "FOLLOWS_UP", "RESOLVES",
    "PAID_BY", "PAID_TO"
]

VALIDATION_SCHEMA = KG_VALIDATION_SCHEMA  # Alias for backward compatibility

# ============================================
# INGESTION PIPELINE CONFIGURATION
# ============================================

# Text chunking (per expert guidance)
CHUNK_SIZE = 512
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
