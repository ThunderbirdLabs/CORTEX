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
    "EVENT",       # Catch-all: conferences, launches, deadlines, milestones
    "MATERIAL"     # Raw materials, supplies, components, parts used in manufacturing/operations
]

# Relationship Types - Natural language for LLM understanding
# These are the ONLY relationship types that will be extracted
POSSIBLE_RELATIONS = [
    # Who did what
    "SENT_BY", "SENT_TO", "CREATED_BY", "ASSIGNED_TO", "ATTENDED_BY",
    # Organization
    "WORKS_FOR", "WORKS_WITH", "REPORTS_TO", "FOUNDED", "MANAGES",
    # Business relationships
    "CLIENT_OF", "VENDOR_OF", "SUPPLIES",
    # Content connections
    "ABOUT", "MENTIONS", "RELATES_TO", "ATTACHED_TO",
    # Status & actions
    "REQUIRES", "FOLLOWS_UP", "RESOLVES", "USED_IN",
    # Financial
    "PAID_BY", "PAID_TO"
]

# Validation Schema - Strict triple format (source, relation, target)
# Enforces relationship direction and valid entity connections
# Format: (HEAD_ENTITY, RELATIONSHIP, TAIL_ENTITY)
KG_VALIDATION_SCHEMA = [
    # Employment & Organization (PERSON relationships)
    ("PERSON", "WORKS_FOR", "COMPANY"),
    ("PERSON", "FOUNDED", "COMPANY"),      # Founder/creator relationship
    ("PERSON", "WORKS_WITH", "PERSON"),
    ("PERSON", "REPORTS_TO", "PERSON"),
    ("PERSON", "MANAGES", "COMPANY"),      # Account manager, relationship owner
    ("PERSON", "CLIENT_OF", "COMPANY"),    # Person is contact at client company
    ("PERSON", "VENDOR_OF", "COMPANY"),    # Person is contact at vendor company

    # Company relationships (business to business)
    ("COMPANY", "CLIENT_OF", "COMPANY"),
    ("COMPANY", "VENDOR_OF", "COMPANY"),
    ("COMPANY", "WORKS_WITH", "COMPANY"),  # Partnerships/collaborations

    # Communication - Who sent what
    ("EMAIL", "SENT_BY", "PERSON"),
    ("EMAIL", "SENT_BY", "COMPANY"),
    ("EMAIL", "SENT_TO", "PERSON"),
    ("EMAIL", "SENT_TO", "COMPANY"),
    ("DOCUMENT", "SENT_BY", "PERSON"),
    ("DOCUMENT", "SENT_BY", "COMPANY"),
    ("DOCUMENT", "SENT_TO", "PERSON"),
    ("DOCUMENT", "SENT_TO", "COMPANY"),

    # Creation & Authorship
    ("DOCUMENT", "CREATED_BY", "PERSON"),
    ("DEAL", "CREATED_BY", "PERSON"),
    ("TASK", "CREATED_BY", "PERSON"),
    ("EVENT", "CREATED_BY", "PERSON"),
    ("MEETING", "CREATED_BY", "PERSON"),

    # Assignment & Responsibility
    ("DEAL", "ASSIGNED_TO", "PERSON"),
    ("TASK", "ASSIGNED_TO", "PERSON"),

    # Attendance
    ("MEETING", "ATTENDED_BY", "PERSON"),
    ("EVENT", "ATTENDED_BY", "PERSON"),

    # Financial
    ("PERSON", "PAID_BY", "PAYMENT"),
    ("COMPANY", "PAID_BY", "PAYMENT"),
    ("PERSON", "PAID_TO", "PAYMENT"),
    ("COMPANY", "PAID_TO", "PAYMENT"),

    # Content relationships - What is about/mentions what
    # Emails
    ("EMAIL", "ABOUT", "TOPIC"),
    ("EMAIL", "ABOUT", "PERSON"),
    ("EMAIL", "ABOUT", "COMPANY"),
    ("EMAIL", "ABOUT", "DEAL"),
    ("EMAIL", "MENTIONS", "PERSON"),
    ("EMAIL", "MENTIONS", "COMPANY"),
    ("EMAIL", "MENTIONS", "TOPIC"),
    ("EMAIL", "RELATES_TO", "TOPIC"),
    ("EMAIL", "RELATES_TO", "DEAL"),
    ("EMAIL", "RELATES_TO", "TASK"),

    # Documents
    ("DOCUMENT", "ABOUT", "TOPIC"),
    ("DOCUMENT", "ABOUT", "PERSON"),
    ("DOCUMENT", "ABOUT", "COMPANY"),
    ("DOCUMENT", "MENTIONS", "PERSON"),
    ("DOCUMENT", "MENTIONS", "COMPANY"),
    ("DOCUMENT", "MENTIONS", "TOPIC"),
    ("DOCUMENT", "RELATES_TO", "TOPIC"),
    ("DOCUMENT", "RELATES_TO", "DEAL"),

    # Deals
    ("DEAL", "ABOUT", "TOPIC"),
    ("DEAL", "ABOUT", "COMPANY"),
    ("DEAL", "MENTIONS", "PERSON"),
    ("DEAL", "MENTIONS", "COMPANY"),
    ("DEAL", "RELATES_TO", "TOPIC"),
    ("DEAL", "SENT_BY", "COMPANY"),         # Company sent the RFQ/order
    ("DEAL", "SENT_TO", "COMPANY"),         # Company received the quote

    # Tasks
    ("TASK", "ABOUT", "TOPIC"),
    ("TASK", "ABOUT", "PERSON"),
    ("TASK", "RELATES_TO", "TOPIC"),
    ("TASK", "RELATES_TO", "DEAL"),

    # Meetings
    ("MEETING", "ABOUT", "TOPIC"),
    ("MEETING", "ABOUT", "DEAL"),
    ("MEETING", "MENTIONS", "PERSON"),
    ("MEETING", "MENTIONS", "COMPANY"),
    ("MEETING", "RELATES_TO", "TOPIC"),
    ("MEETING", "RELATES_TO", "DEAL"),

    # Events
    ("EVENT", "ABOUT", "TOPIC"),
    ("EVENT", "ABOUT", "COMPANY"),
    ("EVENT", "ABOUT", "DEAL"),
    ("EVENT", "MENTIONS", "PERSON"),
    ("EVENT", "RELATES_TO", "TOPIC"),
    ("EVENT", "RELATES_TO", "DEAL"),

    # Payments
    ("PAYMENT", "ABOUT", "DEAL"),
    ("PAYMENT", "RELATES_TO", "TOPIC"),

    # Topics (general connections)
    ("TOPIC", "RELATES_TO", "TOPIC"),

    # Materials (manufacturing/operations)
    ("MATERIAL", "RELATES_TO", "TOPIC"),        # Material relates to a topic/project
    ("MATERIAL", "USED_IN", "DEAL"),            # Material is used in this order/quote
    ("DOCUMENT", "MENTIONS", "MATERIAL"),       # Document mentions a material
    ("DOCUMENT", "ABOUT", "MATERIAL"),          # Spec sheets, data sheets, inspection reports
    ("EMAIL", "MENTIONS", "MATERIAL"),          # Email mentions a material
    ("TASK", "ABOUT", "MATERIAL"),              # Task is about a specific material
    ("TASK", "REQUIRES", "MATERIAL"),           # Production task requires material
    ("DEAL", "ABOUT", "MATERIAL"),              # Deal involves a material
    ("DEAL", "REQUIRES", "MATERIAL"),           # Order specifies material requirements
    ("MEETING", "ABOUT", "MATERIAL"),           # Meeting discusses a material
    ("PAYMENT", "RELATES_TO", "MATERIAL"),      # Material purchase payments
    ("COMPANY", "VENDOR_OF", "MATERIAL"),       # Company is vendor of material (passive)
    ("COMPANY", "SUPPLIES", "MATERIAL"),        # Company supplies material (active)
    ("PERSON", "MANAGES", "MATERIAL"),          # Person manages material inventory/procurement

    # Attachments
    ("EMAIL", "ATTACHED_TO", "DOCUMENT"),
    ("DOCUMENT", "ATTACHED_TO", "DOCUMENT"),

    # Workflow & Dependencies
    ("TASK", "REQUIRES", "TASK"),
    ("TASK", "REQUIRES", "DOCUMENT"),
    ("DEAL", "REQUIRES", "TASK"),
    ("DEAL", "REQUIRES", "DOCUMENT"),
    ("EMAIL", "FOLLOWS_UP", "EMAIL"),
    ("EMAIL", "FOLLOWS_UP", "MEETING"),
    ("DEAL", "FOLLOWS_UP", "MEETING"),
    ("MEETING", "FOLLOWS_UP", "MEETING"),
    ("EMAIL", "RESOLVES", "TASK"),
    ("TASK", "RESOLVES", "TASK"),
]

# Legacy Literal types (for backward compatibility)
ENTITIES = Literal[
    "PERSON", "COMPANY", "EMAIL", "DOCUMENT", "DEAL", "TASK",
    "MEETING", "PAYMENT", "TOPIC", "EVENT", "MATERIAL"
]

RELATIONS = Literal[
    "SENT_BY", "SENT_TO", "CREATED_BY", "ASSIGNED_TO", "ATTENDED_BY",
    "WORKS_FOR", "WORKS_WITH", "REPORTS_TO", "FOUNDED", "MANAGES",
    "CLIENT_OF", "VENDOR_OF", "SUPPLIES",
    "ABOUT", "MENTIONS", "RELATES_TO", "ATTACHED_TO",
    "REQUIRES", "FOLLOWS_UP", "RESOLVES", "USED_IN",
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
