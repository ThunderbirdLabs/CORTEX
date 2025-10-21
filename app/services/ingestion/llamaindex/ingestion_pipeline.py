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
from datetime import datetime

from llama_index.core import Document, PromptTemplate
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.indices.property_graph import SchemaLLMPathExtractor
from llama_index.llms.openai import OpenAI
from llama_index.core.graph_stores.types import EntityNode, Relation
from qdrant_client import QdrantClient, AsyncQdrantClient

from .config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME,
    OPENAI_API_KEY, EXTRACTION_MODEL, EXTRACTION_TEMPERATURE,
    EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, SHOW_PROGRESS,
    NUM_WORKERS, ENABLE_CACHE, REDIS_HOST, REDIS_PORT, CACHE_COLLECTION,
    POSSIBLE_ENTITIES, POSSIBLE_RELATIONS, KG_VALIDATION_SCHEMA
)

logger = logging.getLogger(__name__)


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

        # Neo4j graph store
        self.graph_store = Neo4jPropertyGraphStore(
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            url=NEO4J_URI,
            database=NEO4J_DATABASE
        )
        logger.info(f"✅ Neo4j Graph Store: {NEO4J_URI} (database: {NEO4J_DATABASE})")

        # Neo4j driver for label reordering (visualization fix)
        from neo4j import GraphDatabase
        self.neo4j_driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )

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

        # Custom extraction prompt for CEO business intelligence
        # The strict validation schema handles relationship rules, so this focuses on context
        extraction_prompt = PromptTemplate(
            """You are extracting a knowledge graph for a CEO of an injection molding manufacturing company.

Your goal is to help the CEO understand:
- Who works where and with whom (employees, teams, organizational structure)
- What deals, orders, and quotes are happening and their requirements
- Which materials are being used, ordered, or discussed
- Communications and key information flows
- Business relationships with clients, vendors, and material suppliers
- Financial transactions, payments, and material purchases
- Events, meetings, and important milestones
- Production tasks and material requirements

Extract entities and relationships that would help answer questions like:
- "Who works for our company?" "Who manages this account/material?"
- "What deals is this person working on?" "What materials does this deal require?"
- "Who sent this email and what is it about?" "What materials are mentioned?"
- "What tasks are assigned to this person?" "What materials do they need?"
- "Which companies are our clients/vendors/suppliers?" "Who supplies which materials?"
- "What topics/materials are being discussed in meetings?"

ENTITY TYPES (11 total):
- PERSON: Any individual mentioned (employees, customers, contacts, account managers)
- COMPANY: Any organization (clients, suppliers, partners, material vendors)
- EMAIL: Specific emails referenced
- DOCUMENT: Files like contracts, reports, invoices, spec sheets, data sheets
- DEAL: Sales opportunities, orders, quotes, RFQs
- TASK: Action items, assignments, production tasks
- MEETING: Specific meetings or calls
- PAYMENT: Invoices, payments, expenses, material purchases
- TOPIC: Subjects, projects, products, concepts
- EVENT: Conferences, launches, deadlines, trade shows
- MATERIAL: Raw materials, supplies, components, parts (e.g., Polycarbonate PC 1000, steel, resin, pellets)

RELATIONSHIP TYPES (26 total):

Organization & People:
- WORKS_FOR: Person works for Company (e.g., "Sarah works for Acme")
- FOUNDED: Person founded Company (e.g., "Alex founded Cortex")
- WORKS_WITH: Person works with Person, Company works with Company
- REPORTS_TO: Person reports to Person
- MANAGES: Person manages Company (account manager), Person manages Material (inventory/procurement)
- CLIENT_OF: Person is contact at client Company, Company is client of Company
- VENDOR_OF: Person is contact at vendor Company, Company is vendor of Company
- SUPPLIES: Company supplies Material (active supplier relationship)

Communication & Authorship:
- SENT_BY: Email/Document/Deal sent by Person/Company
- SENT_TO: Email/Document/Deal sent to Person/Company
- CREATED_BY: Document/Deal/Task/Event/Meeting created by Person

Assignment & Attendance:
- ASSIGNED_TO: Deal/Task assigned to Person
- ATTENDED_BY: Meeting/Event attended by Person

Content & References:
- ABOUT: Email/Document/Deal/Task/Meeting/Event/Payment is about Topic/Person/Company/Deal/Material
- MENTIONS: Email/Document/Deal/Meeting/Event mentions Person/Company/Topic/Material
- RELATES_TO: Email/Document/Deal/Task/Meeting/Event/Payment/Topic/Material relates to Topic/Deal/Material
- ATTACHED_TO: Email/Document attached to Document

Workflow & Dependencies:
- REQUIRES: Task/Deal requires Task/Document/Material (critical for manufacturing orders!)
- FOLLOWS_UP: Email/Deal/Meeting follows up on Email/Meeting
- RESOLVES: Email/Task resolves Task
- USED_IN: Material used in Deal (which materials go into which orders)

Financial:
- PAID_BY: Payment paid by Person/Company
- PAID_TO: Payment paid to Person/Company

MANUFACTURING-SPECIFIC GUIDANCE:
- Extract material names precisely (e.g., "Polycarbonate PC 1000", "ABS resin", "steel alloy")
- Link materials to deals/orders using REQUIRES or USED_IN
- Track supplier relationships with SUPPLIES and VENDOR_OF
- Connect spec sheets and data sheets to materials with ABOUT
- Link production tasks to required materials with REQUIRES
- Track who manages material procurement with MANAGES

The system will validate that relationships are used correctly based on entity types.

Extract up to {max_triplets_per_chunk} relevant entity-relationship triplets.

Text:
{text}
"""
        )

        # Entity extractor (for Person/Company/Deal/etc.)
        # Using SchemaLLMPathExtractor for consistent, validated entity extraction
        # strict=False allows flexibility while guiding toward schema
        self.entity_extractor = SchemaLLMPathExtractor(
            llm=self.extraction_llm,
            max_triplets_per_chunk=10,  # Extract up to 10 entity relationships per chunk
            num_workers=4,
            possible_entities=POSSIBLE_ENTITIES,
            possible_relations=POSSIBLE_RELATIONS,
            kg_validation_schema=KG_VALIDATION_SCHEMA,
            strict=False,  # Guide toward schema but allow exceptions
            extract_prompt=extraction_prompt  # Custom prompt for accurate extraction
        )
        logger.info(f"✅ Entity Extractor: SchemaLLMPathExtractor (validated business schema + custom prompt)")

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

            # Merge in any additional metadata from the row
            if "metadata" in document_row and document_row["metadata"]:
                if isinstance(document_row["metadata"], dict):
                    doc_metadata.update(document_row["metadata"])
                elif isinstance(document_row["metadata"], str):
                    try:
                        doc_metadata.update(json.loads(document_row["metadata"]))
                    except:
                        pass

            # For emails: preserve email-specific fields
            if document_type == "email":
                doc_metadata.update({
                    "sender_name": document_row.get("sender_name", ""),
                    "sender_address": document_row.get("sender_address", ""),
                    "to_addresses": document_row.get("to_addresses", "[]"),
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

            # Step 3: Create Document node in Neo4j
            logger.info(f"   → Creating {document_type.upper()} node in Neo4j...")

            # Determine node label based on document type
            node_label = document_type.upper() if document_type else "DOCUMENT"

            # Build node properties (include all metadata)
            node_properties = {
                "document_id": str(doc_id),
                "source_id": source_id,
                "title": title,
                "content": content,  # Store full text in Neo4j
                "source": source,
                "document_type": document_type,
                "tenant_id": tenant_id,
                "created_at": str(created_at),
            }

            # Add any extra metadata
            node_properties.update(doc_metadata)

            # CRITICAL: Use unique ID to prevent merging documents with same title
            # EntityNode uses 'name' as the node ID, so we must make it unique
            unique_name = f"{title}|{doc_id}"

            document_node = EntityNode(
                label=node_label,
                name=unique_name,
                properties=node_properties
            )

            self.graph_store.upsert_nodes([document_node])
            logger.info(f"   ✅ {node_label} node created: {document_node.id}")

            # Step 4: For emails only - create sender/recipient Person nodes
            email_relationships = []
            if document_type == "email" and "sender_name" in document_row:
                sender_name = document_row.get("sender_name", "Unknown")
                sender_address = document_row.get("sender_address", "")

                sender_person = EntityNode(
                    label="PERSON",
                    name=sender_name,
                    properties={
                        "name": sender_name,
                        "email": sender_address
                    }
                )
                self.graph_store.upsert_nodes([sender_person])

                sent_by_rel = Relation(
                    label="SENT_BY",
                    source_id=document_node.id,
                    target_id=sender_person.id
                )
                self.graph_store.upsert_relations([sent_by_rel])
                email_relationships.append("SENT_BY")
                logger.info(f"   ✅ Created: {node_label} -[SENT_BY]-> {sender_name}")

                # Recipients
                to_addresses_str = document_row.get("to_addresses", "[]")
                try:
                    to_addresses = json.loads(to_addresses_str) if isinstance(to_addresses_str, str) else to_addresses_str
                except:
                    to_addresses = []

                for recipient_email in to_addresses:
                    recipient_name = recipient_email.split('@')[0].replace('.', ' ').title()
                    recipient_person = EntityNode(
                        label="PERSON",
                        name=recipient_name,
                        properties={"name": recipient_name, "email": recipient_email}
                    )
                    self.graph_store.upsert_nodes([recipient_person])

                    sent_to_rel = Relation(
                        label="SENT_TO",
                        source_id=document_node.id,
                        target_id=recipient_person.id
                    )
                    self.graph_store.upsert_relations([sent_to_rel])
                    email_relationships.append("SENT_TO")

                if len(to_addresses) > 0:
                    logger.info(f"   ✅ Created {len(to_addresses)} SENT_TO relationships")

            # Step 5: Extract entities from document content (universal)
            if extract_entities and content:
                logger.info(f"   → Extracting entities from {document_type} content (LLM)...")
                try:
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
                        text=content,
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

                        # 3. Create chunk node (TextNode) for provenance
                        # This is the key fix: we need chunk nodes in Neo4j for MENTIONS relationships
                        from llama_index.core.schema import TextNode
                        chunk_node = EntityNode(
                            label="Chunk",
                            name=llama_node.node_id,  # Required by LlamaIndex (becomes 'id' property)
                            properties={
                                "text": llama_node.text,
                                "document_id": document_row.get("id"),
                                "title": title,
                                "source": source,
                                "document_type": document_type,
                                "created_at_timestamp": created_at_timestamp
                            }
                        )
                        # Embed the chunk for semantic retrieval
                        chunk_node.embedding = await self.embed_model.aget_text_embedding(llama_node.text)
                        self.graph_store.upsert_nodes([chunk_node])
                        total_chunks += 1

                        if entities:
                            # Embed and upsert entities for graph retrieval
                            for entity in entities:
                                # Generate embedding for entity (using name + label for context)
                                entity_text = f"{entity.label}: {entity.name if hasattr(entity, 'name') else entity.id}"
                                entity.embedding = await self.embed_model.aget_text_embedding(entity_text)

                            # Upsert entities with embeddings
                            self.graph_store.upsert_nodes(entities)
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
                                self.graph_store.upsert_relations(mentions_relations)

                        if relations:
                            # Upsert extracted relationships between entities
                            self.graph_store.upsert_relations(relations)
                            total_relations += len(relations)

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
                "nodes_created": [node_label] + email_relationships,
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
        num_workers: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Batch ingestion with parallel processing (3-4x faster than sequential).

        This method processes multiple documents in parallel using LlamaIndex's
        built-in parallel processing capabilities. Ideal for:
        - Initial backfill of large document sets
        - Periodic batch ingestion (e.g., process queue every 10 minutes)
        - Continuous ingestion optimization

        Process:
        1. Create Document objects from Supabase rows
        2. Parallel chunking + embedding → Qdrant (with num_workers)
        3. Extract entities and create Neo4j nodes/relationships for each document

        Args:
            document_rows: List of Supabase document rows (documents or emails table)
            extract_entities: Whether to extract entities (LLM-based, expensive)
            num_workers: Number of parallel workers (default: 4, optimal for most workloads)

        Returns:
            List of ingestion results (one per document)

        Performance:
        - Sequential: ~2-3 documents/second
        - Batch (4 workers): ~6-10 documents/second
        - Recommended batch size: 50-100 documents per call
        """
        if not document_rows:
            return []

        logger.info(f"{'='*80}")
        logger.info(f"🚀 BATCH INGESTION: {len(document_rows)} documents")
        logger.info(f"   Parallel workers: {num_workers}")
        logger.info(f"{'='*80}")

        results = []

        try:
            # Step 1: Create Document objects for Qdrant pipeline
            documents = []
            metadata_list = []  # Store metadata for Neo4j processing

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
                doc_metadata = {
                    "document_id": str(doc_id),
                    "title": title,
                    "source": source,
                    "document_type": document_type,
                    "tenant_id": doc_row.get("tenant_id", ""),
                    "source_id": doc_row.get("source_id") or doc_row.get("message_id", str(doc_id)),
                    "created_at": doc_row.get("source_created_at") or doc_row.get("received_datetime", ""),
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

            # Step 2: Parallel chunking + embedding → Qdrant
            logger.info(f"📦 Processing {len(documents)} documents with {num_workers} workers...")
            nodes = await self.qdrant_pipeline.arun(
                documents=documents,
                num_workers=num_workers
            )
            logger.info(f"✅ Created {len(nodes)} chunks in Qdrant")

            # Step 3: Process each document for Neo4j (entities + relationships)
            # Note: Entity extraction is still sequential (LLM-based, expensive)
            for i, meta in enumerate(metadata_list):
                try:
                    doc_row = meta["doc_row"]
                    result = await self._process_neo4j_graph(
                        doc_row=doc_row,
                        extract_entities=extract_entities
                    )
                    results.append(result)
                except Exception as e:
                    logger.error(f"❌ Neo4j processing failed for doc {meta['doc_id']}: {e}")
                    results.append({
                        "status": "partial_success",
                        "document_id": str(meta["doc_id"]),
                        "title": meta["title"],
                        "error": f"Neo4j processing failed: {str(e)}",
                        "qdrant": "success"
                    })

            # Summary
            success_count = sum(1 for r in results if r.get("status") == "success")
            logger.info(f"{'='*80}")
            logger.info(f"✅ BATCH COMPLETE: {success_count}/{len(document_rows)} successful")
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

        # Create Document node in Neo4j
        node_label = document_type.upper() if document_type else "DOCUMENT"

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
                self.graph_store.upsert_nodes([sender_person])

                sent_by_rel = Relation(
                    label="SENT_BY",
                    source_id=document_node.id,
                    target_id=sender_person.id
                )
                self.graph_store.upsert_relations([sent_by_rel])
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
                    self.graph_store.upsert_nodes([recipient_person])

                    sent_to_rel = Relation(
                        label="SENT_TO",
                        source_id=document_node.id,
                        target_id=recipient_person.id
                    )
                    self.graph_store.upsert_relations([sent_to_rel])
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
