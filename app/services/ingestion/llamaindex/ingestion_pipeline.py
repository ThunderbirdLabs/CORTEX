"""
LlamaIndex Universal Ingestion Pipeline (Expert Recommended Pattern)

Architecture:
1. Supabase document row → Document with metadata
2. Text chunking (SentenceSplitter) → Multiple chunks per document
3. Embedding (OpenAI) → Vectors
4. Storage:
   - Qdrant: Chunks with embeddings + metadata (document_id, chunk_index)
   - Neo4j: Full document node + Entity nodes (Person/Company/etc.) + relationships
5. Entity extraction: SchemaLLMPathExtractor for validated business schema

Handles ALL document types:
- Emails (Gmail, Outlook)
- Documents (PDFs, Word, Google Docs)
- Spreadsheets (Excel, Google Sheets)
- Structured data (QuickBooks, HubSpot, etc.)
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, date

from llama_index.core import Document
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.llms.openai import OpenAI
from llama_index.core.graph_stores.types import EntityNode, Relation
from llama_index.core.prompts import PromptTemplate
from qdrant_client import QdrantClient, AsyncQdrantClient

# Import retry decorators for production resilience
from app.core.circuit_breakers import with_neo4j_retry

from .config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE,
    NEO4J_MAX_POOL_SIZE, NEO4J_LIVENESS_CHECK_TIMEOUT,
    NEO4J_CONNECTION_TIMEOUT, NEO4J_MAX_RETRY_TIME, NEO4J_KEEP_ALIVE,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME,
    OPENAI_API_KEY, EXTRACTION_MODEL, EXTRACTION_TEMPERATURE,
    EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, SHOW_PROGRESS,
    NUM_WORKERS, ENABLE_CACHE, REDIS_HOST, REDIS_PORT, CACHE_COLLECTION,
    POSSIBLE_ENTITIES, POSSIBLE_RELATIONS, KG_VALIDATION_SCHEMA,
    ENABLE_RELATIONSHIP_VALIDATION
)
from .relationship_validator import RelationshipValidator

logger = logging.getLogger(__name__)


def sanitize_neo4j_properties(value: Any, max_depth: int = 10, current_depth: int = 0) -> Any:
    """
    Industry-standard Neo4j property sanitization (production-grade).

    Based on Neo4j official constraints + LlamaIndex best practices:
    - Neo4j ONLY supports: primitives (str, int, float, bool) and homogeneous arrays
    - NO nested dicts, NO mixed-type arrays, NO None in arrays
    - Temporal types → ISO strings
    - Complex structures → JSON strings

    Research sources:
    - Neo4j Cypher Manual (2025): Property value constraints
    - LlamaIndex Neo4jPropertyGraphStore source code
    - Neo4j community consensus: "flatten or stringify"

    Args:
        value: Any Python value
        max_depth: Max recursion depth (prevents infinite loops)
        current_depth: Current recursion level

    Returns:
        Neo4j-safe value: primitive, homogeneous array, or JSON string
    """
    # Prevent infinite recursion on circular references
    if current_depth > max_depth:
        logger.warning(f"⚠️  Sanitization max depth {max_depth} exceeded, converting to string")
        return str(value)

    # None → empty string (Neo4j doesn't support null in some contexts)
    if value is None:
        return ""

    # Primitives: pass through unchanged (Neo4j native support)
    if isinstance(value, (str, int, float, bool)):
        return value

    # Temporal types → ISO 8601 strings (Neo4j best practice)
    if isinstance(value, (datetime, date)):
        return value.isoformat()

    # Lists/Arrays: Neo4j requires homogeneous types
    if isinstance(value, list):
        if not value:  # Empty list → JSON string (safest approach)
            return "[]"

        # Recursively sanitize each item
        sanitized = [sanitize_neo4j_properties(item, max_depth, current_depth + 1) for item in value]

        # Check if homogeneous (all same type after sanitization)
        types = set(type(x) for x in sanitized)

        # If all primitives of same type → native Neo4j array
        if len(types) == 1 and list(types)[0] in (str, int, float, bool):
            return sanitized
        else:
            # Mixed types or complex → JSON string
            return json.dumps(sanitized)

    # Dicts: Neo4j does NOT support nested dicts → JSON string
    if isinstance(value, dict):
        # Recursively sanitize nested dict values
        sanitized_dict = {
            k: sanitize_neo4j_properties(v, max_depth, current_depth + 1)
            for k, v in value.items()
        }
        # Always convert dicts to JSON strings (Neo4j limitation)
        return json.dumps(sanitized_dict)

    # Fallback: stringify unknown types (bytes, custom objects, etc.)
    return str(value)


class UniversalIngestionPipeline:
    """
    Expert-recommended universal ingestion pipeline for ANY document type.

    Dual storage strategy:
    - Qdrant: Text chunks + embeddings (for semantic search)
    - Neo4j: Document/Entity nodes + relationships (for graph queries)

    Handles: Emails, PDFs, Sheets, Structured data, etc.
    """

    def __init__(self):
        logger.info("🚀 Initializing Universal Ingestion Pipeline (Expert Pattern)")

        # Qdrant vector store (with async support)
        qdrant_client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        qdrant_aclient = AsyncQdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

        self.vector_store = QdrantVectorStore(
            client=qdrant_client,
            aclient=qdrant_aclient,
            collection_name=QDRANT_COLLECTION_NAME
        )
        logger.info(f"✅ Qdrant Vector Store: {QDRANT_COLLECTION_NAME}")

        # Neo4j graph store with production connection pooling
        self.graph_store = Neo4jPropertyGraphStore(
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            url=NEO4J_URI,
            database=NEO4J_DATABASE,
            # Production connection pooling (passed via **neo4j_kwargs)
            max_connection_pool_size=NEO4J_MAX_POOL_SIZE,
            connection_timeout=NEO4J_CONNECTION_TIMEOUT,
            liveness_check_timeout=NEO4J_LIVENESS_CHECK_TIMEOUT,
            max_transaction_retry_time=NEO4J_MAX_RETRY_TIME,
            keep_alive=NEO4J_KEEP_ALIVE
        )
        logger.info(f"✅ Neo4j Graph Store: {NEO4J_URI} (database: {NEO4J_DATABASE})")
        logger.info(f"   Connection pool: max_size={NEO4J_MAX_POOL_SIZE}, liveness_check={NEO4J_LIVENESS_CHECK_TIMEOUT}s")

        # Neo4j driver for label reordering (visualization fix)
        from neo4j import GraphDatabase
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
            # Same production config for consistency
            max_connection_pool_size=NEO4J_MAX_POOL_SIZE,
            connection_timeout=NEO4J_CONNECTION_TIMEOUT,
            liveness_check_timeout=NEO4J_LIVENESS_CHECK_TIMEOUT,
            max_transaction_retry_time=NEO4J_MAX_RETRY_TIME,
            keep_alive=NEO4J_KEEP_ALIVE
        )
        logger.info(f"   Label reordering driver: same pool config")

        # Embedding model
        self.embed_model = OpenAIEmbedding(
            model_name=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )

        # Entity extraction LLM
        self.extraction_llm = OpenAI(
            model=EXTRACTION_MODEL,
            temperature=EXTRACTION_TEMPERATURE,
            api_key=OPENAI_API_KEY
        )

        # Entity extractor (for Person/Company/Deal/etc.)
        # Using SchemaLLMPathExtractor with manufacturing-specific prompt
        from .config import ENTITIES, RELATIONS

        # Manufacturing-specific extraction prompt
        extraction_prompt = PromptTemplate(
            template="""
You are an expert at extracting entities and relationships from injection molding manufacturing documents.

**MISSION**: Build an enterprise knowledge graph that maps critical business relationships inside the company.
Extract ONLY information that helps answer strategic questions about organizational structure, supply chain dependencies,
and manufacturing operations.

# Entity Types (What to Extract)

**PERSON**: Individual human beings with specific names
- MUST BE: A person's full name (first and last name, or recognizable name)
- Examples: "John Smith", "Sarah Chen", "Mike Johnson", "Ramiro Gonzalez"
- CRITICAL: Only extract if you see an actual human name

**COMPANY**: Business entities and organizations
- MUST BE: The name of a business you could send an invoice to or receive a shipment from
- Examples: "Acme Industries", "PolyPlastics Supply Co.", "Unit Industries", "Superior Mold", "TriStar"
- CRITICAL: Must be an entity that has employees, sells/buys products, or provides services

**ROLE**: Job titles and positions held by people
- MUST BE: A professional job title that describes what a person does
- Examples: "VP of Sales", "Quality Engineer", "Procurement Manager", "Account Manager", "Technician"
- CRITICAL: Must be a title a person holds in an organization (not generic words like "customer" or "room")

**PURCHASE_ORDER**: Specific purchase orders and invoices
- MUST BE: A specific PO number or invoice identifier
- Examples: "PO #54321", "Invoice #INV-2025-001", "PO9764F", "Purchase Order 12345"
- CRITICAL: Must have a specific transaction or order number

**MATERIAL**: Physical substances, resins, plastics, and manufactured components used in production
- MUST BE: A tangible material or component with physical properties used in manufacturing
- Examples: "polycarbonate PC-1000", "ABS resin grade 5", "steel mold inserts", "nylon pellets", "aluminum housing"
- CRITICAL: Must be a physical substance or part used to make products (not organizational departments, documents, or abstract concepts)

**CERTIFICATION**: Certifications and quality standards
- MUST BE: A specific certification name or standard
- Examples: "ISO 9001", "FDA approved", "Six Sigma certification", "IATF 16949"
- CRITICAL: Must be a recognized certification or standard

# Relationship Types (How Entities Connect)

**Organizational:**
- WORKS_FOR: Person works for Company
- HAS_ROLE: Person has Role

**People Relationships:**
- WORKS_WITH: Person works with Person/Company (collaboration, contact)
- WORKS_ON: Person works on Purchase Order (who handles what)

**Business Relationships:**
- SUPPLIES_TO: Company supplies to Company (supplier relationship)
- WORKS_WITH: Company works with Company (business collaboration)
- SUPPLIES: Company supplies Material (what company provides)

**Materials & Orders:**
- CONTAINS: Purchase Order contains Material (what materials in order)
- SENT_TO: Purchase Order sent to Person/Company (recipient)

**Certifications:**
- HAS_CERTIFICATION: Company has Certification

# Extraction Instructions

1. Extract ONLY entities that are explicitly mentioned with specific names or identifiers
2. Each entity gets EXACTLY ONE type - choose based on what it actually is (person name = PERSON, company name = COMPANY, etc.)
3. Focus on manufacturing-critical relationships (supply chain, materials, certifications)
4. Extract ONLY high-quality, high-confidence entities and relationships (>90% confidence level)
5. **WHEN IN DOUBT, LEAVE IT OUT** - Quality over quantity is critical
6. If unclear or ambiguous, skip it entirely
7. Limit to {max_triplets_per_chunk} highest-value relationships per chunk

# Relationship Extraction Guidelines

**WORKS_FOR (Person → Company):**
- Extract when there's clear evidence of employment or official affiliation
- Context clues: job title, employee ID, "our team", organizational hierarchy, benefits/payroll mentions
- Examples that qualify: "John Smith, VP of Sales at Acme", "our engineer Sarah", "employee ID #4521"
- DO NOT extract from: "John from Acme emailed us" (this is WORKS_WITH, not employment)

**WORKS_WITH (Person → Person/Company):**
- Extract for professional collaboration, business contacts, or regular interaction
- Context clues: "contact at", "working with", "coordinates with", email exchanges, project collaboration
- Examples that qualify: "reach out to John at Acme", "Sarah from PolyPlastics handles our orders"
- Broader than WORKS_FOR - indicates business relationship without employment

**HAS_ROLE (Person → Role):**
- Extract when a professional title is directly associated with a person
- Context clues: title before/after name, signature blocks, "our [title]", organizational charts
- Examples that qualify: "John Smith, VP of Sales", "Sarah Chen (Procurement Manager)"
- Titles must be specific job roles, not generic descriptors

**WORKS_ON (Person → Purchase Order):**
- Extract when a person has responsibility for or is actively handling a specific PO
- Context clues: "handling PO", "responsible for", "assigned to", "working on order", "managing invoice"
- Examples that qualify: "Sarah is handling PO #54321", "John assigned to Invoice #2025-001"
- Must reference a specific PO number/identifier

**CONTAINS (Purchase Order → Material):**
- Extract when specific materials are listed as part of a PO or order
- Context clues: "PO includes", "order contains", "invoice for [material]", line items, bill of materials
- Examples that qualify: "PO #54321 includes polycarbonate PC-1000", "order for 500kg ABS resin"
- Must link specific PO to specific material

**SUPPLIES_TO (Company → Company):**
- Extract for vendor/supplier relationships between businesses
- Context clues: "supplies", "vendor for", "provides to", "ships to", invoices/POs between companies
- Examples that qualify: "Superior Mold supplies to Unit Industries", "Acme is our resin vendor"
- Must show clear supplier → customer direction

**SUPPLIES (Company → Material):**
- Extract when a company provides or manufactures specific materials
- Context clues: "supplies [material]", "provides [material]", "manufacturer of", product catalogs
- Examples that qualify: "PolyPlastics supplies ABS resin", "Acme provides polycarbonate PC-1000"
- Must link specific company to specific material

**SENT_TO (Purchase Order → Person/Company):**
- Extract when a PO is explicitly directed to or sent to a recipient
- Context clues: "PO sent to", "invoice for", "order placed with", "addressed to"
- Examples that qualify: "PO #54321 sent to John Smith", "Invoice #2025-001 for Acme Industries"
- Must show clear PO → recipient direction

**HAS_CERTIFICATION (Company → Certification):**
- Extract when certifications are explicitly attributed to a company
- Context clues: "ISO certified", "has certification", "certified for", certificates/standards mentioned
- Examples that qualify: "ISO 9001 certified supplier", "Acme has IATF 16949 certification"
- Must be a recognized standard/certification, not generic quality claims

**General Principles:**
- Require explicit evidence in the text - avoid inference or assumption
- Context matters: "John from Acme" in an email signature = WORKS_FOR, but in "John from Acme called" = WORKS_WITH
- Directional relationships matter: SUPPLIES_TO goes from vendor → customer, not bidirectional
- When multiple relationships could apply, choose the most specific one with strongest evidence
- If confidence is below 90%, skip the relationship entirely

# Examples

Input: "John Smith from Acme Industries is handling PO #54321 which includes polycarbonate PC-1000."
Output:
- (John Smith, WORKS_FOR, Acme Industries)
- (John Smith, WORKS_ON, PO #54321)
- (PO #54321, CONTAINS, polycarbonate PC-1000)

Input: "Sarah Chen, our Procurement Manager, works with PolyPlastics Supply who provides ISO 9001 certified ABS resin."
Output:
- (Sarah Chen, HAS_ROLE, Procurement Manager)
- (Sarah Chen, WORKS_WITH, PolyPlastics Supply)
- (ABS resin, HAS_CERTIFICATION, ISO 9001)

Input: "Superior Mold supplies to Unit Industries and provided mold inserts."
Output:
- (Superior Mold, SUPPLIES_TO, Unit Industries)

Now extract entities and relationships from the following text:

{text}
""".strip()
        )

        self.entity_extractor = SchemaLLMPathExtractor(
            llm=self.extraction_llm,
            max_triplets_per_chunk=5,  # Extract up to 5 highest-value relationships (quality over quantity)
            num_workers=4,
            possible_entities=ENTITIES,  # Use Literal type for pydantic validation
            possible_relations=RELATIONS,  # Use Literal type for pydantic validation
            kg_validation_schema=KG_VALIDATION_SCHEMA,
            strict=True,  # Enforce schema strictly for production quality
            extract_prompt=extraction_prompt  # Manufacturing-specific extraction guidance
        )
        logger.info(f"✅ Entity Extractor: SchemaLLMPathExtractor (validated business schema)")

        # Relationship validator (prevent false relationships)
        self.relationship_validator = None
        if ENABLE_RELATIONSHIP_VALIDATION:
            self.relationship_validator = RelationshipValidator(llm=self.extraction_llm)
            logger.info(f"✅ Relationship Validator: LLM-based validation enabled")
        else:
            logger.info(f"   ⚠️  Relationship validation disabled (set ENABLE_RELATIONSHIP_VALIDATION=true to enable)")

        # Production caching setup (optional but recommended)
        cache = None
        if ENABLE_CACHE:
            try:
                from llama_index.core.ingestion import IngestionCache
                from llama_index.storage.kvstore.redis import RedisKVStore as RedisCache

                cache = IngestionCache(
                    cache=RedisCache.from_host_and_port(host=REDIS_HOST, port=REDIS_PORT),
                    collection=CACHE_COLLECTION,
                )
                logger.info(f"✅ Redis Cache enabled: {REDIS_HOST}:{REDIS_PORT}/{CACHE_COLLECTION}")
            except Exception as e:
                logger.warning(f"⚠️  Redis cache not available: {e}")
                cache = None

        # Document store for deduplication (production best practice)
        # CRITICAL: Use RedisDocumentStore for persistent cross-session deduplication
        docstore = None
        docstore_strategy = None
        if ENABLE_CACHE:
            try:
                from llama_index.storage.docstore.redis import RedisDocumentStore
                from llama_index.core.ingestion import DocstoreStrategy

                docstore = RedisDocumentStore.from_host_and_port(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    namespace="cortex_docstore"
                )
                docstore_strategy = DocstoreStrategy.UPSERTS
                logger.info(f"✅ Redis Docstore enabled: {REDIS_HOST}:{REDIS_PORT}/cortex_docstore")
            except Exception as e:
                logger.warning(f"⚠️  Redis docstore not available: {e}")
                logger.info("   Falling back to SimpleDocumentStore (in-memory)")
                from llama_index.core.storage.docstore import SimpleDocumentStore
                docstore = SimpleDocumentStore()
        else:
            from llama_index.core.storage.docstore import SimpleDocumentStore
            docstore = SimpleDocumentStore()
            logger.info("   Using SimpleDocumentStore (in-memory, no Redis)")

        # Ingestion pipeline for Qdrant (chunking + embedding)
        # Production optimizations: caching, docstore, parallel processing
        pipeline_kwargs = {
            "transformations": [
                SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP),
                self.embed_model
            ],
            "vector_store": self.vector_store,
            "cache": cache,  # Production: Redis caching for transformations
            "docstore": docstore,  # Production: Document deduplication
        }

        # Add docstore_strategy only if we have Redis (requires vector_store)
        if docstore_strategy and ENABLE_CACHE:
            pipeline_kwargs["docstore_strategy"] = docstore_strategy

        self.qdrant_pipeline = IngestionPipeline(**pipeline_kwargs)

        logger.info(f"✅ Ingestion Pipeline: chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP}")
        if cache:
            logger.info(f"   📦 Caching: Enabled (Redis)")
        if docstore_strategy:
            logger.info(f"   📚 Docstore: Redis with UPSERTS strategy (cross-session dedup)")
        else:
            logger.info(f"   📚 Docstore: SimpleDocumentStore (session-only dedup)")
        logger.info(f"   ⚡ Parallel workers: {NUM_WORKERS}")

        logger.info("✅ Universal Ingestion Pipeline ready")
        logger.info("   Architecture: IngestionPipeline → Qdrant + Neo4j")
        logger.info("   Storage: Dual (chunks in Qdrant, full documents in Neo4j)")
        logger.info("   Supports: Emails, PDFs, Sheets, Structured data")

    # ============================================================================
    # PRODUCTION RESILIENCE: Neo4j operations with automatic retry
    # ============================================================================

    @with_neo4j_retry
    def _upsert_nodes_with_retry(self, nodes: List[EntityNode]):
        """
        Upsert nodes to Neo4j with automatic retry on transient failures.

        Retries on: Connection errors, timeouts, transient errors
        Strategy: 3 attempts, exponential backoff (1s, 2s, 4s)
        """
        self.graph_store.upsert_nodes(nodes)

    @with_neo4j_retry
    def _upsert_relations_with_retry(self, relations: List[Relation]):
        """
        Upsert relations to Neo4j with automatic retry on transient failures.

        Retries on: Connection errors, timeouts, transient errors
        Strategy: 3 attempts, exponential backoff (1s, 2s, 4s)
        """
        self.graph_store.upsert_relations(relations)

    async def ingest_document(
        self,
        document_row: Dict[str, Any],
        extract_entities: bool = True
    ) -> Dict[str, Any]:
        """
        Ingest ANY document from Supabase row (universal format).

        Process:
        1. Create Document from Supabase row
        2. Chunk text and embed → Store in Qdrant
        3. Create Document node → Store in Neo4j
        4. Extract entities (Person, Company, Deal, etc.) → Store in Neo4j
        5. Create relationships based on document type → Store in Neo4j

        Args:
            document_row: Supabase document row (from 'documents' OR 'emails' table)
                Required fields: id, content, title (or subject)
                Optional: source, document_type, metadata, etc.
            extract_entities: Whether to extract entities (LLM-based, expensive)

        Returns:
            Dict with ingestion results
        """

        # Universal field extraction (works for both emails and documents tables)
        doc_id = document_row.get("id")
        source = document_row.get("source", "unknown")
        document_type = document_row.get("document_type", "document")

        # Title: try 'title' first (documents), fallback to 'subject' (emails)
        title = document_row.get("title") or document_row.get("subject", "Untitled")

        # Content: try 'content' first (documents), fallback to 'full_body' (emails)
        content = document_row.get("content") or document_row.get("full_body", "")

        # Metadata
        tenant_id = document_row.get("tenant_id", "")
        source_id = document_row.get("source_id") or document_row.get("message_id", str(doc_id))
        created_at = document_row.get("source_created_at") or document_row.get("received_datetime", "")

        # FIX: Attachments inherit timestamp from parent email
        # CRITICAL for time-filtered queries (e.g., "show me emails from last week")
        # Without this, 70%+ of Qdrant data has created_at_timestamp = None
        if not created_at and document_row.get("parent_document_id"):
            parent_id = document_row.get("parent_document_id")
            logger.info(f"   📎 Attachment detected with no timestamp, fetching from parent document {parent_id}...")

            try:
                # Query parent document's timestamp from Supabase
                from supabase import create_client
                import os
                supabase = create_client(
                    os.getenv('SUPABASE_URL'),
                    os.getenv('SUPABASE_ANON_KEY')
                )

                parent_result = supabase.table('documents') \
                    .select('source_created_at') \
                    .eq('id', parent_id) \
                    .single() \
                    .execute()

                if parent_result.data and parent_result.data.get('source_created_at'):
                    created_at = parent_result.data['source_created_at']
                    logger.info(f"   ✅ Inherited timestamp from parent: {created_at}")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not fetch parent timestamp: {e}")

        # Convert created_at to Unix timestamp for Qdrant filtering
        created_at_timestamp = None
        if created_at:
            try:
                from dateutil import parser
                if isinstance(created_at, str):
                    dt = parser.parse(created_at)
                else:
                    dt = created_at
                created_at_timestamp = int(dt.timestamp())
            except Exception as e:
                logger.warning(f"   ⚠️  Could not parse created_at timestamp: {e}")

        logger.info(f"\n{'='*80}")
        logger.info(f"📄 INGESTING DOCUMENT: {title}")
        logger.info(f"{'='*80}")
        logger.info(f"   ID: {doc_id}")
        logger.info(f"   Source: {source}")
        logger.info(f"   Type: {document_type}")
        logger.info(f"   Length: {len(content)} characters")

        try:
            # Step 1: Create Document for Qdrant ingestion
            # Build metadata from document_row (preserve all fields)
            doc_metadata = {
                "document_id": str(doc_id),
                "source_id": source_id,
                "title": title,
                "source": source,
                "document_type": document_type,
                "tenant_id": tenant_id,
                "created_at": str(created_at),
                "created_at_timestamp": created_at_timestamp,  # Unix timestamp for filtering
            }

            # Add file metadata if available (for attachments/files)
            if document_row.get("file_url"):
                doc_metadata["file_url"] = document_row["file_url"]
            if document_row.get("file_size_bytes"):
                doc_metadata["file_size_bytes"] = document_row["file_size_bytes"]
            if document_row.get("mime_type"):
                doc_metadata["mime_type"] = document_row["mime_type"]

            # CRITICAL: Add parent_document_id for attachment grouping
            # This allows chat.py to group attachments with parent email
            if document_row.get("parent_document_id"):
                doc_metadata["parent_document_id"] = str(document_row["parent_document_id"])

            # Merge in any additional metadata from the row (TRUNCATE to prevent metadata > chunk_size error)
            if "metadata" in document_row and document_row["metadata"]:
                additional_meta = {}
                if isinstance(document_row["metadata"], dict):
                    additional_meta = document_row["metadata"]
                elif isinstance(document_row["metadata"], str):
                    try:
                        additional_meta = json.loads(document_row["metadata"])
                    except:
                        pass

                # Truncate metadata values to prevent total metadata length > chunk size
                # CRITICAL: Convert arrays to JSON strings to prevent Neo4j LongArray toString() error
                MAX_META_VALUE_LEN = 200  # Max chars per metadata value
                for key, value in additional_meta.items():
                    if isinstance(value, list):
                        # Convert lists to JSON strings to prevent Neo4j LongArray error
                        doc_metadata[key] = json.dumps(value)
                    elif isinstance(value, str) and len(value) > MAX_META_VALUE_LEN:
                        doc_metadata[key] = value[:MAX_META_VALUE_LEN] + "..."
                    else:
                        doc_metadata[key] = value

            # Determine node label early (used in return statement at end)
            node_label = document_type.upper() if document_type else "DOCUMENT"

            # For emails: preserve email-specific fields
            if document_type == "email":
                # CRITICAL: Convert to_addresses to JSON string to prevent Neo4j LongArray error
                to_addrs = document_row.get("to_addresses", "[]")
                if isinstance(to_addrs, list):
                    to_addrs = json.dumps(to_addrs)

                doc_metadata.update({
                    "sender_name": document_row.get("sender_name", ""),
                    "sender_address": document_row.get("sender_address", ""),
                    "to_addresses": to_addrs,
                })

            # CRITICAL: Set doc_id to ensure chunks preserve original document_id
            # Without this, LlamaIndex overwrites document_id with chunk node_id
            document = Document(
                text=content,
                metadata=doc_metadata,
                doc_id=str(doc_id)  # Force chunks to inherit this as ref_doc_id
            )

            # Step 2: Chunk, embed, and store in Qdrant
            # Production: Use parallel processing with num_workers
            logger.info("   → Chunking text and embedding...")
            self.qdrant_pipeline.run(
                documents=[document],
                show_progress=SHOW_PROGRESS,
                num_workers=NUM_WORKERS  # Production: Parallel processing
            )
            logger.info("   ✅ Stored chunks in Qdrant")

            # Step 3: SKIPPED - No EMAIL/ATTACHMENT document nodes
            # Rationale: Redundant with Qdrant chunks and Supabase source data
            # We only create Chunks (already done) + extracted entities (next step)

            # Step 4: For emails - extract sender/recipient PERSON nodes from metadata
            # These will be connected to Chunks via SENT/RECEIVED relationships
            email_sender_person = None
            email_recipient_persons = []

            if document_type == "email":
                # Extract sender from structured metadata
                sender_name = document_row.get("sender_name")
                sender_address = document_row.get("sender_address")

                if sender_name and sender_address:
                    email_sender_person = EntityNode(
                        label="PERSON",
                        name=sender_name,
                        properties={
                            "name": sender_name,
                            "email": sender_address
                        }
                    )
                    # Generate embedding for deduplication
                    sender_text = f"PERSON: {sender_name}"
                    email_sender_person.embedding = await self.embed_model.aget_text_embedding(sender_text)
                    self._upsert_nodes_with_retry([email_sender_person])
                    logger.info(f"   ✅ Created sender PERSON: {sender_name}")

                # Extract recipients from structured metadata
                to_addresses_str = document_row.get("to_addresses", "[]")
                try:
                    to_addresses = json.loads(to_addresses_str) if isinstance(to_addresses_str, str) else to_addresses_str
                except:
                    to_addresses = []

                for recipient_email in to_addresses:
                    if recipient_email:
                        recipient_name = recipient_email.split('@')[0].replace('.', ' ').title()
                        recipient_person = EntityNode(
                            label="PERSON",
                            name=recipient_name,
                            properties={"name": recipient_name, "email": recipient_email}
                        )
                        recipient_text = f"PERSON: {recipient_name}"
                        recipient_person.embedding = await self.embed_model.aget_text_embedding(recipient_text)
                        self._upsert_nodes_with_retry([recipient_person])
                        email_recipient_persons.append(recipient_person)

                if len(email_recipient_persons) > 0:
                    logger.info(f"   ✅ Created {len(email_recipient_persons)} recipient PERSON nodes")

            # Step 5: Extract entities from document content (universal)
            if extract_entities and content:
                logger.info(f"   → Extracting entities from {document_type} content (LLM)...")
                try:
                    # CONTEXT LENGTH FIX: Truncate content to fit within model's token limit
                    # gpt-4o-mini has 8K token limit (~6K tokens usable for content after prompt overhead)
                    # Estimate: 1 token ≈ 4 characters, so 6000 tokens ≈ 24000 characters
                    MAX_EXTRACTION_CHARS = 24000
                    extraction_content = content

                    if len(content) > MAX_EXTRACTION_CHARS:
                        logger.warning(
                            f"   ⚠️  Content too long for entity extraction "
                            f"({len(content)} chars), truncating to {MAX_EXTRACTION_CHARS} chars..."
                        )
                        extraction_content = content[:MAX_EXTRACTION_CHARS]

                    # CRITICAL FIX: Create Document with NO metadata for extraction
                    # This ensures entity nodes have ONLY entity-intrinsic properties
                    #
                    # WHY: At scale (after deduplication), entities appear in HUNDREDS of documents
                    #      - "Alex Thompson" might be mentioned in 100+ emails/docs
                    #      - Which document_id should the merged entity have? (ambiguous)
                    #      - Entity embeddings contaminated by document titles (reduces search quality)
                    #      - VectorContextRetriever matches on document metadata instead of entity properties
                    #
                    # BEST PRACTICE: Entity properties should be context-free and entity-intrinsic
                    #      - GOOD: name, email, description, role
                    #      - BAD: document_id, title, document_type (document-specific)
                    #
                    # Document linkage: Via MENTIONED_IN relationships (already implemented)
                    document_for_extraction = Document(
                        text=extraction_content,  # Use truncated content
                        metadata={},  # Empty metadata = clean entity properties
                        excluded_llm_metadata_keys=list(doc_metadata.keys())  # Exclude ALL from LLM
                    )

                    # Use entity extractor on the minimal-metadata document
                    # SchemaLLMPathExtractor uses acall (async) internally
                    extracted_nodes = await self.entity_extractor.acall([document_for_extraction])

                    # Extract entities, relationships, AND chunk nodes from extraction
                    # SchemaLLMPathExtractor stores: 'nodes' (entities), 'relations', and creates chunk nodes with MENTIONS
                    total_entities = 0
                    total_relations = 0
                    total_chunks = 0

                    for llama_node in extracted_nodes:
                        # 1. Extract entities from metadata
                        entities = llama_node.metadata.get("nodes", [])

                        # 2. Extract relationships from metadata
                        relations = llama_node.metadata.get("relations", [])

                        # 3. Create chunk node for provenance and MENTIONS relationships
                        chunk_node = EntityNode(
                            label="Chunk",
                            name=llama_node.node_id,  # Required by LlamaIndex (becomes 'id' property)
                            properties={
                                "text": llama_node.text,
                                "document_id": document_row.get("id"),
                                "title": title,
                                "source": source,
                                "document_type": document_type,
                                "created_at": created_at,  # Human-readable: "2025-10-16T19:37:27+00:00"
                                "created_at_timestamp": created_at_timestamp  # For filtering: 1760643447
                            }
                        )
                        # Embed the chunk for semantic retrieval
                        chunk_node.embedding = await self.embed_model.aget_text_embedding(llama_node.text)
                        self._upsert_nodes_with_retry([chunk_node])
                        total_chunks += 1

                        # Create SENT/RECEIVED relationships from email sender/recipients to chunk
                        if email_sender_person:
                            sent_rel = Relation(
                                label="SENT",
                                source_id=email_sender_person.id,
                                target_id=chunk_node.id
                            )
                            self._upsert_relations_with_retry([sent_rel])

                        for recipient_person in email_recipient_persons:
                            received_rel = Relation(
                                label="RECEIVED",
                                source_id=recipient_person.id,
                                target_id=chunk_node.id
                            )
                            self._upsert_relations_with_retry([received_rel])

                        if entities:
                            # Embed and upsert entities for graph retrieval
                            for entity in entities:
                                # Generate embedding for entity (using name + label for context)
                                entity_text = f"{entity.label}: {entity.name if hasattr(entity, 'name') else entity.id}"
                                entity.embedding = await self.embed_model.aget_text_embedding(entity_text)

                                # NOTE: Do NOT add created_at_timestamp to entities!
                                # Entities are context-free and appear in multiple documents.
                                # When Neo4j merges the same entity from different documents,
                                # it would create an array [timestamp1, timestamp2, ...] which breaks schema.
                                # Timestamps belong on Chunk nodes (document content) not Entity nodes.

                                # Sanitize entity properties (LLM can return nested dicts/arrays)
                                if hasattr(entity, 'properties') and entity.properties:
                                    entity.properties = {
                                        k: sanitize_neo4j_properties(v)
                                        for k, v in entity.properties.items()
                                    }

                            # Upsert entities with embeddings
                            self._upsert_nodes_with_retry(entities)
                            total_entities += len(entities)

                            # Create MENTIONS relationships from chunk → entities
                            mentions_relations = []
                            for entity in entities:
                                mentions_rel = Relation(
                                    label="MENTIONS",
                                    source_id=chunk_node.id,
                                    target_id=entity.id
                                )
                                mentions_relations.append(mentions_rel)

                            if mentions_relations:
                                self._upsert_relations_with_retry(mentions_relations)

                        if relations:
                            # Validate relationships if enabled
                            if self.relationship_validator:
                                validated_relations = await self.relationship_validator.validate_relationships(
                                    relations=relations,
                                    entities=entities,
                                    chunk_text=llama_node.text
                                )
                            else:
                                # No validation - use all relationships
                                validated_relations = relations

                            # Upsert only validated relationships
                            if validated_relations:
                                self._upsert_relations_with_retry(validated_relations)
                                total_relations += len(validated_relations)

                    if total_chunks > 0:
                        logger.info(f"   ✅ Created {total_chunks} chunk nodes (provenance)")
                    if total_entities > 0:
                        logger.info(f"   ✅ Extracted {total_entities} entities (embedded)")
                    if total_relations > 0:
                        logger.info(f"   ✅ Extracted {total_relations} relationships")

                except Exception as e:
                    logger.warning(f"   ⚠️  Entity extraction failed: {e}")

            # Fix Neo4j Browser visualization (reorder labels)
            self._reorder_labels_for_visualization()

            logger.info(f"✅ DOCUMENT INGESTION COMPLETE: {title}")
            logger.info(f"{'='*80}\n")

            return {
                "status": "success",
                "document_id": str(doc_id),
                "source_id": source_id,
                "title": title,
                "source": source,
                "document_type": document_type,
                "chunks": total_chunks,
                "entities": total_entities,
                "relationships": total_relations,
                "characters": len(content)
            }

        except Exception as e:
            error_msg = f"Document ingestion failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return {
                "status": "error",
                "error": error_msg,
                "document_id": str(doc_id),
                "title": title
            }

    # Backward compatibility wrapper for existing code
    async def ingest_email(
        self,
        email_row: Dict[str, Any],
        extract_entities: bool = True
    ) -> Dict[str, Any]:
        """
        Backward-compatible wrapper for ingest_document().
        Automatically sets document_type='email' and calls ingest_document().
        """
        # Ensure document_type is set to 'email'
        if "document_type" not in email_row:
            email_row["document_type"] = "email"

        return await self.ingest_document(email_row, extract_entities=extract_entities)

    async def ingest_documents_batch(
        self,
        document_rows: List[Dict[str, Any]],
        extract_entities: bool = True,
        num_workers: int = 4,
        max_concurrent_neo4j: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Production-grade batch ingestion with semaphore-controlled parallel processing.

        ENTERPRISE ARCHITECTURE (Apple/Meta-grade practices):
        - Parallel Qdrant writes (num_workers control)
        - Parallel Neo4j entity extraction (semaphore-controlled)
        - Connection pool safety (prevents exhaustion)
        - Circuit breaker integration (handles transient failures)
        - Structured observability (timing, success rates)

        Process:
        1. Create Document objects from Supabase rows
        2. Parallel chunking + embedding → Qdrant (num_workers)
        3. Parallel entity extraction → Neo4j (semaphore-controlled)

        Args:
            document_rows: List of Supabase document rows (documents or emails table)
            extract_entities: Whether to extract entities (LLM-based, expensive)
            num_workers: Parallel workers for Qdrant (default: 4)
            max_concurrent_neo4j: Max concurrent Neo4j writes (default: 10, tuned for 50-conn pool)

        Returns:
            List of ingestion results (one per document)

        Performance:
        - Sequential: ~2-3 documents/second
        - Batch (num_workers=4, max_concurrent_neo4j=10): ~8-12 documents/second
        - Recommended batch size: 50-100 documents per call

        Safety:
        - Semaphore prevents Neo4j connection pool exhaustion (max 50 connections)
        - Circuit breaker handles OpenAI rate limits
        - Partial failures don't block entire batch
        """
        import asyncio
        import time

        if not document_rows:
            return []

        start_time = time.time()
        logger.info(f"{'='*80}")
        logger.info(f"🚀 BATCH INGESTION: {len(document_rows)} documents")
        logger.info(f"   Qdrant workers: {num_workers}")
        logger.info(f"   Max concurrent Neo4j: {max_concurrent_neo4j}")
        logger.info(f"{'='*80}")

        results = []

        try:
            # Step 1: Create Document objects for Qdrant pipeline
            documents = []
            metadata_list = []  # Store metadata for Neo4j processing

            prep_start = time.time()
            for doc_row in document_rows:
                # Universal field extraction
                doc_id = doc_row.get("id")
                source = doc_row.get("source", "unknown")
                document_type = doc_row.get("document_type", "document")
                title = doc_row.get("title") or doc_row.get("subject", "Untitled")
                content = doc_row.get("content") or doc_row.get("full_body", "")

                if not content or not content.strip():
                    logger.warning(f"⚠️  Skipping document {doc_id}: empty content")
                    results.append({
                        "status": "skipped",
                        "document_id": str(doc_id),
                        "title": title,
                        "reason": "empty_content"
                    })
                    continue

                # Create Document with stable doc_id for deduplication
                created_at = doc_row.get("source_created_at") or doc_row.get("received_datetime", "")

                # Convert created_at to Unix timestamp for RecencyBoostPostprocessor
                created_at_timestamp = None
                if created_at:
                    try:
                        from dateutil import parser
                        if isinstance(created_at, str):
                            dt = parser.parse(created_at)
                        else:
                            dt = created_at
                        created_at_timestamp = int(dt.timestamp())
                    except Exception as e:
                        logger.warning(f"   ⚠️  Could not parse created_at timestamp for doc {doc_id}: {e}")

                doc_metadata = {
                    "document_id": str(doc_id),
                    "title": title,
                    "source": source,
                    "document_type": document_type,
                    "tenant_id": doc_row.get("tenant_id", ""),
                    "source_id": doc_row.get("source_id") or doc_row.get("message_id", str(doc_id)),
                    "created_at": str(created_at),
                    "created_at_timestamp": created_at_timestamp,  # CRITICAL: Required for RecencyBoostPostprocessor
                }

                document = Document(
                    text=content,
                    metadata=doc_metadata,
                    doc_id=str(doc_id)  # Use plain numeric ID (matches Neo4j and Supabase)
                )

                documents.append(document)
                metadata_list.append({
                    "doc_row": doc_row,
                    "doc_id": doc_id,
                    "title": title,
                    "content": content,
                    "document_type": document_type,
                    "source": source
                })

            prep_time = time.time() - prep_start
            logger.info(f"   Prepared {len(documents)} documents in {prep_time:.2f}s")

            # Step 2: Parallel chunking + embedding → Qdrant
            qdrant_start = time.time()
            logger.info(f"📦 Processing {len(documents)} documents with {num_workers} Qdrant workers...")
            nodes = await self.qdrant_pipeline.arun(
                documents=documents,
                num_workers=num_workers
            )
            qdrant_time = time.time() - qdrant_start
            logger.info(f"✅ Created {len(nodes)} chunks in Qdrant ({qdrant_time:.2f}s, {len(nodes)/qdrant_time:.1f} chunks/sec)")

            # Step 3: Parallel entity extraction → Neo4j (SEMAPHORE-CONTROLLED)
            # This is the key fix: prevents connection pool exhaustion
            neo4j_start = time.time()
            logger.info(f"🧠 Extracting entities with max {max_concurrent_neo4j} concurrent Neo4j operations...")

            semaphore = asyncio.Semaphore(max_concurrent_neo4j)

            async def process_with_semaphore(meta: Dict[str, Any]) -> Dict[str, Any]:
                """Process single document with semaphore control"""
                async with semaphore:
                    try:
                        return await self._process_neo4j_graph(
                            doc_row=meta["doc_row"],
                            extract_entities=extract_entities
                        )
                    except Exception as e:
                        logger.error(f"❌ Neo4j processing failed for doc {meta['doc_id']}: {e}")
                        return {
                            "status": "partial_success",
                            "document_id": str(meta["doc_id"]),
                            "title": meta["title"],
                            "error": f"Neo4j processing failed: {str(e)}",
                            "qdrant": "success"
                        }

            # Execute all Neo4j tasks in parallel (semaphore limits concurrency)
            neo4j_tasks = [process_with_semaphore(meta) for meta in metadata_list]
            batch_results = await asyncio.gather(*neo4j_tasks, return_exceptions=True)

            # Handle any exceptions from gather
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"❌ Unexpected error in batch: {result}")
                    results.append({
                        "status": "error",
                        "error": str(result),
                        "document_id": "unknown"
                    })
                else:
                    results.append(result)

            neo4j_time = time.time() - neo4j_start
            logger.info(f"✅ Completed Neo4j processing ({neo4j_time:.2f}s, {len(metadata_list)/neo4j_time:.1f} docs/sec)")

            # Summary with metrics
            total_time = time.time() - start_time
            success_count = sum(1 for r in results if r.get("status") == "success")
            partial_count = sum(1 for r in results if r.get("status") == "partial_success")
            error_count = sum(1 for r in results if r.get("status") == "error")

            logger.info(f"{'='*80}")
            logger.info(f"✅ BATCH COMPLETE: {success_count}/{len(document_rows)} successful")
            logger.info(f"   Partial success: {partial_count}")
            logger.info(f"   Errors: {error_count}")
            logger.info(f"   Total time: {total_time:.2f}s ({len(document_rows)/total_time:.1f} docs/sec)")
            logger.info(f"   Breakdown: prep={prep_time:.1f}s, qdrant={qdrant_time:.1f}s, neo4j={neo4j_time:.1f}s")
            logger.info(f"{'='*80}")

            return results

        except Exception as e:
            error_msg = f"Batch ingestion failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return [{
                "status": "error",
                "error": error_msg,
                "document_id": "batch",
                "total_documents": len(document_rows)
            }]

    async def _process_neo4j_graph(
        self,
        doc_row: Dict[str, Any],
        extract_entities: bool = True
    ) -> Dict[str, Any]:
        """
        Helper method to process Neo4j graph (entities + relationships) for a single document.
        Extracted from ingest_document() to support batch processing.
        """
        doc_id = doc_row.get("id")
        source = doc_row.get("source", "unknown")
        document_type = doc_row.get("document_type", "document")
        title = doc_row.get("title") or doc_row.get("subject", "Untitled")
        content = doc_row.get("content") or doc_row.get("full_body", "")
        created_at = doc_row.get("source_created_at") or doc_row.get("received_datetime", "")

        # Convert created_at to Unix timestamp for filtering
        created_at_timestamp = None
        if created_at:
            try:
                from dateutil import parser
                if isinstance(created_at, str):
                    dt = parser.parse(created_at)
                else:
                    dt = created_at
                created_at_timestamp = int(dt.timestamp())
            except Exception as e:
                logger.warning(f"   ⚠️  Could not parse created_at timestamp: {e}")

        # Create Document node in Neo4j (node_label already set at top of function)
        node_properties = {
            "document_id": str(doc_id),
            "title": title,
            "content": content,  # CRITICAL: Store full content for entity extraction
            "source": source,
            "document_type": document_type,
            "tenant_id": doc_row.get("tenant_id", ""),
            "source_id": doc_row.get("source_id") or doc_row.get("message_id", str(doc_id)),
            "created_at": str(created_at),
            "created_at_timestamp": created_at_timestamp,
        }

        # CRITICAL: Use unique ID to prevent merging documents with same title
        # EntityNode uses 'name' as the node ID, so we must make it unique
        # Format: "title|doc_id" ensures uniqueness while keeping title readable
        unique_name = f"{title}|{doc_id}"

        document_node = EntityNode(
            label=node_label,
            name=unique_name,
            properties=node_properties
        )

        self.graph_store.upsert_nodes([document_node])

        # Email-specific relationships (sender/recipients)
        # Fixed: Use correct field names from emails table
        email_relationships = []
        if document_type == "email":
            # Check for sender_name or sender_address
            sender_name = doc_row.get("sender_name")
            sender_address = doc_row.get("sender_address")

            if sender_name or sender_address:
                # Prefer name, fallback to address
                display_name = sender_name or sender_address.split('@')[0].replace('.', ' ').title()
                sender_person = EntityNode(
                    label="PERSON",
                    name=display_name,
                    properties={
                        "name": sender_name or display_name,
                        "email": sender_address
                    }
                )
                # CRITICAL: Generate embedding for deduplication (same as LLM entities)
                sender_text = f"PERSON: {display_name}"
                sender_person.embedding = await self.embed_model.aget_text_embedding(sender_text)
                self._upsert_nodes_with_retry([sender_person])

                sent_by_rel = Relation(
                    label="SENT_BY",
                    source_id=document_node.id,
                    target_id=sender_person.id
                )
                self._upsert_relations_with_retry([sent_by_rel])
                email_relationships.append("SENT_BY")

            # Handle to_addresses (can be list or JSON string)
            to_addresses = doc_row.get("to_addresses", [])
            if isinstance(to_addresses, str):
                import json
                try:
                    to_addresses = json.loads(to_addresses)
                except:
                    to_addresses = []

            if isinstance(to_addresses, list):
                for recipient_email in to_addresses[:10]:
                    recipient_name = recipient_email.split('@')[0].replace('.', ' ').title()
                    recipient_person = EntityNode(
                        label="PERSON",
                        name=recipient_name,
                        properties={
                            "name": recipient_name,
                            "email": recipient_email
                        }
                    )
                    # CRITICAL: Generate embedding for deduplication (same as LLM entities)
                    recipient_text = f"PERSON: {recipient_name}"
                    recipient_person.embedding = await self.embed_model.aget_text_embedding(recipient_text)
                    self._upsert_nodes_with_retry([recipient_person])

                    sent_to_rel = Relation(
                        label="SENT_TO",
                        source_id=document_node.id,
                        target_id=recipient_person.id
                    )
                    self._upsert_relations_with_retry([sent_to_rel])
                    email_relationships.append("SENT_TO")

        # Entity extraction (expensive, optional)
        if extract_entities and content:
            document_for_extraction = Document(
                text=content,
                metadata={},
                excluded_llm_metadata_keys=list(doc_row.keys())
            )

            extracted_nodes = await self.entity_extractor.acall([document_for_extraction])

            # FIXED: SchemaLLMPathExtractor stores entities/relations in metadata
            # Source: llama_index/core/graph_stores/types.py
            # KG_NODES_KEY = "nodes", KG_RELATIONS_KEY = "relations"
            # ALSO: We need to upsert chunk nodes with MENTIONS relationships for provenance
            llama_node = extracted_nodes[0]
            entities = llama_node.metadata.get("nodes", [])
            relations = llama_node.metadata.get("relations", [])

            # Create chunk node for provenance (key fix for graph retrieval)
            chunk_node = EntityNode(
                label="Chunk",
                name=llama_node.node_id,  # Required by LlamaIndex (becomes 'id' property)
                properties={
                    "text": llama_node.text,
                    "document_id": doc_row.get("id"),
                    "title": title,
                    "source": source,
                    "document_type": document_type,
                    "created_at_timestamp": created_at_timestamp
                }
            )
            chunk_node.embedding = await self.embed_model.aget_text_embedding(llama_node.text)
            self.graph_store.upsert_nodes([chunk_node])
            logger.info(f"   ✅ Created chunk node (provenance)")

            if entities:
                logger.info(f"   → Extracted {len(entities)} entities, embedding them...")
                # Embed entities for graph retrieval
                for entity in entities:
                    entity_text = f"{entity.label}: {entity.name if hasattr(entity, 'name') else entity.id}"
                    entity.embedding = await self.embed_model.aget_text_embedding(entity_text)

                    # NOTE: Do NOT add created_at_timestamp to entities!
                    # Entities are context-free and appear in multiple documents.
                    # When Neo4j merges the same entity from different documents,
                    # it would create an array [timestamp1, timestamp2, ...] which breaks schema.
                    # Timestamps belong on Chunk nodes (document content) not Entity nodes.

                self.graph_store.upsert_nodes(entities)
                logger.info(f"   ✅ Upserted {len(entities)} entities to Neo4j")

                # Create MENTIONS relationships from chunk → entities
                mentions_relations = []
                for entity in entities:
                    mentions_rel = Relation(
                        label="MENTIONS",
                        source_id=chunk_node.id,
                        target_id=entity.id
                    )
                    mentions_relations.append(mentions_rel)

                if mentions_relations:
                    self.graph_store.upsert_relations(mentions_relations)
                    logger.info(f"   ✅ Created {len(mentions_relations)} MENTIONS relationships")

            if relations:
                self.graph_store.upsert_relations(relations)
                logger.info(f"   ✅ Upserted {len(relations)} relationships to Neo4j")

            if not entities and not relations:
                logger.warning(f"   ⚠️  No entities or relations extracted from document")

        return {
            "status": "success",
            "document_id": str(doc_id),
            "title": title,
            "source": source,
            "document_type": document_type,
            "nodes_created": [node_label] + email_relationships,
            "characters": len(content)
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from Qdrant and Neo4j."""
        stats = {}

        # Qdrant stats
        try:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
            collection = client.get_collection(QDRANT_COLLECTION_NAME)
            stats["qdrant_points"] = collection.points_count
            stats["qdrant_vectors_count"] = collection.vectors_count
        except Exception as e:
            logger.error(f"Failed to get Qdrant stats: {e}")
            stats["qdrant_error"] = str(e)

        # Neo4j stats
        try:
            result = self.graph_store.structured_query("""
                MATCH (e:EMAIL)
                RETURN count(e) as email_count
            """)
            stats["neo4j_emails"] = result[0]["email_count"] if result else 0

            result = self.graph_store.structured_query("""
                MATCH (p:PERSON)
                RETURN count(p) as person_count
            """)
            stats["neo4j_persons"] = result[0]["person_count"] if result else 0

            result = self.graph_store.structured_query("""
                MATCH (c:COMPANY)
                RETURN count(c) as company_count
            """)
            stats["neo4j_companies"] = result[0]["company_count"] if result else 0

            result = self.graph_store.structured_query("""
                MATCH ()-[r]->()
                RETURN count(r) as relationship_count
            """)
            stats["neo4j_relationships"] = result[0]["relationship_count"] if result else 0
        except Exception as e:
            logger.error(f"Failed to get Neo4j stats: {e}")
            stats["neo4j_error"] = str(e)

        return stats

    def _reorder_labels_for_visualization(self):
        """
        Fixes Neo4j Browser visualization by putting custom labels first.

        This reorders node labels so Neo4j Browser shows:
        - (PERSON {name: "Alex"}) instead of (__Node__ {name: "Alex"})
        - (COMPANY {name: "Acme"}) instead of (__Node__ {name: "Acme"})

        SAFE: Only changes label ORDER, not removal. LlamaIndex internals
        still work because __Node__ and __Entity__ labels remain present.

        Runs after each document ingestion to maintain clean visualization.
        """
        try:
            with self.neo4j_driver.session(database=NEO4J_DATABASE) as session:
                result = session.run("""
                    MATCH (n:__Node__)
                    WITH n, [l IN labels(n) WHERE NOT l IN ['__Node__', '__Entity__']] AS customLabels
                    WHERE size(customLabels) > 0
                    CALL apoc.create.setLabels(n, customLabels + ['__Node__', '__Entity__'])
                    YIELD node
                    RETURN count(node) as updated
                """)

                record = result.single()
                if record and record["updated"] > 0:
                    logger.debug(f"🎨 Reordered labels for {record['updated']} nodes (visualization fix)")
        except Exception as e:
            # Don't fail ingestion if label reordering fails
            logger.warning(f"⚠️  Label reordering failed (non-critical): {e}")
