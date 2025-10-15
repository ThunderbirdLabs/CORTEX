"""
LlamaIndex Hybrid Property Graph Configuration
Uses existing schema from app/models/schemas/knowledge_graph.py

Architecture: Hybrid Property Graph (single unified PropertyGraphIndex)
- Recommended official LlamaIndex pattern
- Neo4j PropertyGraphStore + Qdrant VectorStore
- Multi-strategy hybrid retrieval (VectorContext + LLMSynonym)
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
NEO4J_DATABASE = "neo4j"  # Production database

# ============================================
# QDRANT CONFIGURATION
# ============================================

QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")  # Production collection

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
# SCHEMA CONFIGURATION (From knowledge_graph.py)
# ============================================

# Entity types - matches your existing schema
ENTITIES = Literal[
    "PERSON",
    "COMPANY",
    "DEAL",
    "PROJECT",
    "DOCUMENT",
    "MESSAGE",
    "MEETING",
    "PRODUCT",
    "LOCATION",
    "TASK"
]

# Relationship types - matches your existing schema
RELATIONS = Literal[
    "WORKS_FOR",
    "WORKS_ON",
    "MANAGES",
    "REPORTS_TO",
    "COLLABORATES_WITH",
    "WITH_CUSTOMER",
    "PARTNER_WITH",
    "COMPETES_WITH",
    "OWNS_DEAL",
    "ASSOCIATED_WITH",
    "USES_PRODUCT",
    "ATTENDED_MEETING",
    "SENT_EMAIL",
    "RECEIVED_EMAIL",
    "MENTIONED_IN",
    "CREATED_DOCUMENT",
    "REFERENCES",
    "LOCATED_IN"
]

# Validation schema - defines which entities can have which relationships
VALIDATION_SCHEMA = {
    "PERSON": [
        "WORKS_FOR", "WORKS_ON", "MANAGES", "REPORTS_TO",
        "COLLABORATES_WITH", "ATTENDED_MEETING", "CREATED_DOCUMENT",
        "SENT_EMAIL", "RECEIVED_EMAIL", "LOCATED_IN"
    ],
    "COMPANY": [
        "WITH_CUSTOMER", "PARTNER_WITH", "COMPETES_WITH",
        "LOCATED_IN", "USES_PRODUCT"
    ],
    "DEAL": [
        "OWNS_DEAL", "WITH_CUSTOMER", "ASSOCIATED_WITH",
        "MENTIONED_IN", "REFERENCES"
    ],
    "PROJECT": [
        "WORKS_ON", "ASSOCIATED_WITH", "MENTIONED_IN",
        "REFERENCES"
    ],
    "DOCUMENT": [
        "CREATED_DOCUMENT", "REFERENCES", "MENTIONED_IN"
    ],
    "MESSAGE": [
        "SENT_EMAIL", "RECEIVED_EMAIL", "MENTIONED_IN"
    ],
    "MEETING": [
        "ATTENDED_MEETING", "MENTIONED_IN"
    ],
    "PRODUCT": [
        "USES_PRODUCT", "ASSOCIATED_WITH"
    ],
    "LOCATION": [
        "LOCATED_IN"
    ],
    "TASK": [
        "ASSOCIATED_WITH", "WORKS_ON"
    ]
}

# ============================================
# PIPELINE CONFIGURATION
# ============================================

# Vector Pipeline
VECTOR_CHUNK_SIZE = 1000
VECTOR_CHUNK_OVERLAP = 200
VECTOR_SIMILARITY_TOP_K = 10

# PropertyGraph Pipeline
GRAPH_SHOW_PROGRESS = True
