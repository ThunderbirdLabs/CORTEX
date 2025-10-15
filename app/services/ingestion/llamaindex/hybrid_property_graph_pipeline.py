"""
LlamaIndex Hybrid Property Graph Pipeline (Recommended Architecture)

TRUE HYBRID APPROACH:
- Single PropertyGraphIndex that handles BOTH graph structure and vector embeddings
- Graph structure → Neo4j PropertyGraphStore
- Vector embeddings → Qdrant VectorStore  
- Automatic linking between graph nodes and their vector representations
- Multiple extraction strategies (Schema + Implicit)

This replaces the old dual-pipeline (vector_pipeline + graph_pipeline) architecture
with LlamaIndex's recommended unified approach.

References:
- https://docs.llamaindex.ai/en/stable/examples/property_graph/
- Property graphs are designed as superset of vector databases
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from llama_index.core import PropertyGraphIndex, Document, Settings
from llama_index.core.indices.property_graph import (
    SchemaLLMPathExtractor,
    ImplicitPathExtractor
)
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.llms.openai import OpenAI
from llama_index.embeddings.openai import OpenAIEmbedding
from qdrant_client import QdrantClient, AsyncQdrantClient

from .config import (
    NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, NEO4J_DATABASE,
    QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME,
    OPENAI_API_KEY, EXTRACTION_MODEL, EXTRACTION_TEMPERATURE,
    QUERY_MODEL, QUERY_TEMPERATURE, EMBEDDING_MODEL,
    ENTITIES, RELATIONS, VALIDATION_SCHEMA,
    GRAPH_SHOW_PROGRESS, VECTOR_CHUNK_SIZE, VECTOR_CHUNK_OVERLAP
)

logger = logging.getLogger(__name__)


class HybridPropertyGraphPipeline:
    """
    LlamaIndex Hybrid Property Graph Pipeline.
    
    Single unified index that combines:
    1. Graph structure with typed entities and relationships (Neo4j)
    2. Vector embeddings of all nodes (Qdrant)
    3. Automatic document structure relationships (PREVIOUS, NEXT, SOURCE)
    
    Features:
    - Schema-guided entity extraction (your business schema)
    - Implicit path extraction (captures document structure)
    - All graph nodes are automatically embedded
    - Graph and vector stores are linked seamlessly
    - Supports hybrid retrieval (vector + graph + synonyms + cypher)
    
    This is the recommended LlamaIndex architecture for knowledge graphs.
    """
    
    def __init__(self):
        logger.info("🚀 Initializing Hybrid Property Graph Pipeline (LlamaIndex Recommended)")
        
        # Configure LlamaIndex Settings globally
        Settings.llm = OpenAI(
            model=QUERY_MODEL,
            temperature=QUERY_TEMPERATURE,
            api_key=OPENAI_API_KEY
        )
        
        Settings.embed_model = OpenAIEmbedding(
            model_name=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )
        
        Settings.chunk_size = VECTOR_CHUNK_SIZE
        Settings.chunk_overlap = VECTOR_CHUNK_OVERLAP
        
        # Initialize Neo4j Property Graph Store
        self.graph_store = Neo4jPropertyGraphStore(
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD,
            url=NEO4J_URI,
            database=NEO4J_DATABASE
        )
        logger.info(f"✅ Neo4j Property Graph Store: {NEO4J_URI} (database: {NEO4J_DATABASE})")
        
        # Initialize Qdrant Vector Store (with both sync and async clients)
        qdrant_client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )
        qdrant_aclient = AsyncQdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY
        )

        self.vector_store = QdrantVectorStore(
            client=qdrant_client,
            aclient=qdrant_aclient,  # For async operations
            collection_name=QDRANT_COLLECTION_NAME
        )
        logger.info(f"✅ Qdrant Vector Store: {QDRANT_COLLECTION_NAME} (sync + async clients)")
        
        # Initialize Knowledge Graph Extractors
        # Strategy 1: Schema-guided extraction (your business entities/relations)
        self.schema_extractor = SchemaLLMPathExtractor(
            llm=OpenAI(
                model=EXTRACTION_MODEL,
                temperature=EXTRACTION_TEMPERATURE,
                api_key=OPENAI_API_KEY
            ),
            possible_entities=ENTITIES,
            possible_relations=RELATIONS,
            kg_validation_schema=VALIDATION_SCHEMA,
            strict=True,  # Only extract entities/relations in schema
            num_workers=4  # Parallel processing for better performance
        )
        logger.info(f"✅ Schema Extractor: {len(ENTITIES.__args__)} entities, {len(RELATIONS.__args__)} relations (4 workers)")
        
        # Strategy 2: Implicit path extraction (document structure)
        # Captures PREVIOUS, NEXT, SOURCE relationships automatically
        self.implicit_extractor = ImplicitPathExtractor()
        logger.info("✅ Implicit Extractor: Captures document structure relationships")
        
        # Combine extractors
        self.kg_extractors = [
            self.schema_extractor,
            self.implicit_extractor
        ]
        
        # Initialize PropertyGraphIndex (THE CORE HYBRID INDEX)
        try:
            # Try to load existing index
            self.index = PropertyGraphIndex.from_existing(
                property_graph_store=self.graph_store,
                vector_store=self.vector_store,
                embed_kg_nodes=True,  # CRITICAL: Embed graph nodes for vector search
                use_async=True,  # Enable async transformations and embeddings
                llm=Settings.llm,
                embed_model=Settings.embed_model,
                kg_extractors=self.kg_extractors,
                show_progress=GRAPH_SHOW_PROGRESS
            )
            logger.info("✅ Loaded existing PropertyGraphIndex (embed_kg_nodes=True, use_async=True)")
        except Exception as e:
            logger.info(f"Creating new PropertyGraphIndex: {e}")
            # Create new index
            self.index = PropertyGraphIndex(
                nodes=[],
                property_graph_store=self.graph_store,
                vector_store=self.vector_store,
                embed_kg_nodes=True,  # CRITICAL: Embed graph nodes for vector search
                use_async=True,  # Enable async transformations and embeddings
                llm=Settings.llm,
                embed_model=Settings.embed_model,
                kg_extractors=self.kg_extractors,
                show_progress=GRAPH_SHOW_PROGRESS
            )
            logger.info("✅ Created new PropertyGraphIndex (embed_kg_nodes=True, use_async=True)")
        
        logger.info("✅ Hybrid Property Graph Pipeline ready")
        logger.info("   Architecture: Single unified index (Graph + Vector)")
        logger.info("   Graph Store: Neo4j PropertyGraphStore")
        logger.info("   Vector Store: Qdrant VectorStore")
        logger.info("   Extractors: Schema + Implicit")
        logger.info("   All graph nodes are automatically embedded")
    
    async def ingest_document(
        self,
        content: str,
        document_name: str,
        source: str,
        document_type: str,
        reference_time: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        episode_id: Optional[str] = None  # Keep for backward compatibility
    ) -> Dict[str, Any]:
        """
        Ingest document into hybrid property graph.
        
        Single unified ingestion that:
        1. Extracts entities and relationships (schema-guided)
        2. Captures document structure (implicit)
        3. Embeds all nodes automatically
        4. Stores graph in Neo4j, vectors in Qdrant
        5. Links them seamlessly
        
        Args:
            content: Document text
            document_name: Document title
            source: Source system (gmail, slack, etc.)
            document_type: Type (email, doc, deal, etc.)
            reference_time: When document was created
            metadata: Additional metadata
            episode_id: Optional episode ID (for backward compatibility)
        
        Returns:
            Dict with ingestion results
        """
        
        if reference_time is None:
            reference_time = datetime.now()
        
        if metadata is None:
            metadata = {}
        
        # Build document metadata
        doc_metadata = {
            'document_name': document_name,
            'source': source,
            'document_type': document_type,
            'timestamp': reference_time.isoformat(),
            **metadata
        }
        
        if episode_id:
            doc_metadata['episode_id'] = episode_id
        
        logger.info(f"\n{'='*80}")
        logger.info(f"📄 HYBRID PROPERTY GRAPH INGESTION: {document_name}")
        logger.info(f"{'='*80}")
        logger.info(f"   Source: {source}")
        logger.info(f"   Type: {document_type}")
        logger.info(f"   Length: {len(content)} characters")
        
        try:
            # Create LlamaIndex Document
            document = Document(
                text=content,
                metadata=doc_metadata
            )
            
            # Single insert handles EVERYTHING:
            # - Schema extraction (entities/relations)
            # - Implicit extraction (doc structure)
            # - Node embedding
            # - Graph storage (Neo4j)
            # - Vector storage (Qdrant)
            # All done automatically by PropertyGraphIndex!
            await asyncio.to_thread(self.index.insert, document)
            
            logger.info(f"✅ HYBRID INGESTION COMPLETE")
            logger.info(f"{'='*80}")
            logger.info(f"   Document: {document_name}")
            logger.info(f"   Graph nodes + Vector embeddings stored")
            logger.info(f"   Neo4j: Entities & relationships")
            logger.info(f"   Qdrant: Node embeddings")
            
            return {
                'status': 'success',
                'document_name': document_name,
                'source': source,
                'document_type': document_type,
                'metadata': doc_metadata
            }
            
        except Exception as e:
            error_msg = f"Hybrid ingestion failed: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            return {
                'status': 'error',
                'error': error_msg,
                'document_name': document_name
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from graph and vector stores."""
        stats = {}
        
        # Graph stats (Neo4j)
        try:
            result = self.graph_store.structured_query("""
                MATCH (e:__Entity__)
                RETURN count(*) as entity_count
            """)
            stats['entity_count'] = result[0]['entity_count'] if result else 0
            
            result = self.graph_store.structured_query("""
                MATCH ()-[r]->()
                WHERE type(r) <> 'MENTIONS'
                RETURN count(r) as relationship_count
            """)
            stats['relationship_count'] = result[0]['relationship_count'] if result else 0
            
            result = self.graph_store.structured_query("""
                MATCH (doc:__Node__)
                RETURN count(*) as document_count
            """)
            stats['document_count'] = result[0]['document_count'] if result else 0
        except Exception as e:
            logger.error(f"Failed to get Neo4j stats: {e}")
            stats['neo4j_error'] = str(e)
        
        # Vector stats (Qdrant)
        try:
            from qdrant_client import QdrantClient
            qdrant_client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY
            )
            collection_info = qdrant_client.get_collection(QDRANT_COLLECTION_NAME)
            stats['vectors_count'] = collection_info.vectors_count
            stats['points_count'] = collection_info.points_count
        except Exception as e:
            logger.error(f"Failed to get Qdrant stats: {e}")
            stats['qdrant_error'] = str(e)
        
        return stats
    
    async def close(self):
        """Close connections."""
        logger.info("✅ Hybrid Property Graph Pipeline closed")


# ============================================================================
# CONVENIENCE FACTORY
# ============================================================================

def create_hybrid_pipeline() -> HybridPropertyGraphPipeline:
    """
    Factory function to create HybridPropertyGraphPipeline.
    
    Returns:
        HybridPropertyGraphPipeline ready to use
    """
    return HybridPropertyGraphPipeline()
