"""
Hybrid RAG Pipeline: Vector DB (Qdrant Cloud) + Knowledge Graph (Neo4j/Graphiti)

This pipeline:
1. Takes a document
2. Chunks it intelligently
3. Embeds chunks → Qdrant Cloud
4. Sends full document → Graphiti → Neo4j
5. Links them with matching episode_id UUID
"""
import os
import uuid
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from openai import OpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter
from graphiti_core import Graphiti
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
from dotenv import load_dotenv

load_dotenv()


class HybridRAGPipeline:
    """
    Hybrid RAG pipeline combining vector search (Qdrant Cloud) and knowledge graph (Neo4j/Graphiti)
    """

    def __init__(self):
        # OpenAI client for embeddings
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Qdrant Cloud connection
        self.qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

        # Graphiti (Neo4j knowledge graph)
        self.graphiti = None  # Initialize async

        # Text splitter for chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,  # ~750 tokens
            chunk_overlap=200,  # Overlap for context continuity
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        print("✅ Hybrid RAG Pipeline initialized")
        print(f"   Vector DB: Qdrant Cloud")
        print(f"   Knowledge Graph: Neo4j/Graphiti")

    async def initialize_graphiti(self):
        """Initialize Graphiti connection (async)"""
        if self.graphiti is None:
            self.graphiti = Graphiti(
                uri=os.getenv("NEO4J_URI"),
                user=os.getenv("NEO4J_USER"),
                password=os.getenv("NEO4J_PASSWORD")
            )
            await self.graphiti.build_indices_and_constraints()
        return self.graphiti

    def chunk_document(self, content: str) -> List[str]:
        """
        Split document into chunks using RecursiveCharacterTextSplitter
        """
        chunks = self.text_splitter.split_text(content)
        return chunks

    def get_embedding(self, text: str) -> List[float]:
        """
        Get OpenAI embedding for text
        Uses text-embedding-3-small (1536 dimensions)
        """
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def store_chunks_in_qdrant(
        self,
        chunks: List[str],
        document_name: str,
        source: str,
        document_type: str,
        episode_id: str,
        metadata: Optional[Dict] = None
    ) -> List[str]:
        """
        Store document chunks with embeddings in Qdrant Cloud
        Returns list of point UUIDs
        """
        chunk_ids = []
        total_chunks = len(chunks)
        points = []

        print(f"   📦 Storing {total_chunks} chunks in Qdrant Cloud...")

        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = self.get_embedding(chunk)

            # Generate UUID for this point
            point_id = str(uuid.uuid4())
            chunk_ids.append(point_id)

            # Build payload matching Supabase schema
            payload = {
                "document_name": document_name,
                "source": source,
                "document_type": document_type,
                "content": chunk,
                "chunk_index": i,
                "total_chunks": total_chunks,
                "graphiti_episode_id": episode_id,  # CRITICAL: Neo4j linking!
                "created_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            # Create Qdrant point
            points.append(PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            ))

            if (i + 1) % 5 == 0:
                print(f"      ✓ {i + 1}/{total_chunks} chunks prepared")

        # Upload all points to Qdrant
        self.qdrant_client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True  # Wait for indexing
        )

        print(f"   ✅ All {total_chunks} chunks stored in Qdrant!")
        return chunk_ids

    async def store_in_graphiti(
        self,
        content: str,
        document_name: str,
        source: str,
        reference_time: Optional[datetime] = None,
        episode_id: Optional[str] = None
    ) -> str:
        """
        Store document in Graphiti knowledge graph
        Returns episode UUID
        """
        await self.initialize_graphiti()

        print(f"   🕸️  Processing with Graphiti...")

        # Use provided episode_id or generate new one
        if episode_id is None:
            episode_id = str(uuid.uuid4())

        # Add to knowledge graph
        await self.graphiti.add_episode(
            name=episode_id,  # Use UUID as episode name for linking
            episode_body=content,
            source_description=f"{source}: {document_name}",
            reference_time=reference_time or datetime.now()
        )

        print(f"   ✅ Knowledge graph updated!")
        return episode_id

    async def ingest_document(
        self,
        content: str,
        document_name: str,
        source: str,
        document_type: str,
        reference_time: Optional[datetime] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Main ingestion method: Process document through hybrid pipeline

        Args:
            content: Full document text
            document_name: Name/title of document
            source: Source system (gmail, slack, hubspot, etc.)
            document_type: Type (email, doc, deal, etc.)
            reference_time: When the document was created
            metadata: Additional metadata

        Returns:
            Dict with episode_id, chunk_ids, and stats
        """
        print(f"\n{'='*80}")
        print(f"📄 INGESTING DOCUMENT: {document_name}")
        print(f"{'='*80}")
        print(f"   Source: {source}")
        print(f"   Type: {document_type}")
        print(f"   Length: {len(content)} characters\n")

        # Generate episode UUID (links vector DB and knowledge graph)
        episode_id = str(uuid.uuid4())

        # Step 1: Chunk the document
        print("1️⃣ Chunking document...")
        chunks = self.chunk_document(content)
        print(f"   ✅ Created {len(chunks)} chunks\n")

        # Step 2: Store chunks in Qdrant Cloud with embeddings
        print("2️⃣ Storing in Vector DB (Qdrant Cloud)...")
        chunk_ids = self.store_chunks_in_qdrant(
            chunks=chunks,
            document_name=document_name,
            source=source,
            document_type=document_type,
            episode_id=episode_id,
            metadata=metadata
        )
        print()

        # Step 3: Store full document in Graphiti/Neo4j
        print("3️⃣ Storing in Knowledge Graph (Neo4j/Graphiti)...")
        await self.store_in_graphiti(
            content=content,
            document_name=document_name,
            source=source,
            reference_time=reference_time,
            episode_id=episode_id
        )
        print()

        result = {
            "episode_id": episode_id,
            "document_name": document_name,
            "source": source,
            "document_type": document_type,
            "num_chunks": len(chunks),
            "chunk_ids": chunk_ids,
            "vector_db": "qdrant_cloud",
            "knowledge_graph": "neo4j"
        }

        print(f"{'='*80}")
        print("✅ DOCUMENT INGESTED SUCCESSFULLY")
        print(f"{'='*80}")
        print(f"   Episode ID: {episode_id}")
        print(f"   Chunks stored: {len(chunks)}")
        print(f"   Knowledge graph updated: Yes")
        print(f"\n💡 Both systems linked via episode_id: {episode_id}\n")

        return result

    async def close(self):
        """Close Graphiti connection"""
        if self.graphiti:
            await self.graphiti.close()


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def test_pipeline():
    """Test the hybrid pipeline with sample documents"""

    pipeline = HybridRAGPipeline()

    # Sample document
    test_document = """
    From: sarah.chen@techvision.io
    To: mike.johnson@techvision.io
    Date: October 15, 2025
    Subject: MedTech Deal Update - Ready to Close

    Mike,

    Great news! David Williams from MedTech Solutions just confirmed they've
    completed their security review and are ready to sign the contract.

    Deal Details:
    - Value: $450,000 annually
    - Contract term: 3 years
    - Start date: November 1, 2025
    - 500 user licenses
    - Dedicated support included

    This is our biggest healthcare deal this quarter. The team did an amazing
    job demonstrating our HIPAA compliance and healthcare-specific features.

    Next steps:
    1. Legal to finalize contract by EOD Friday
    2. Schedule kickoff meeting with their IT team
    3. Assign Jennifer Wong as Customer Success Manager

    Let's celebrate this win at Friday's team lunch!

    Sarah Chen
    VP of Sales, TechVision
    """

    try:
        # Ingest the document
        result = await pipeline.ingest_document(
            content=test_document,
            document_name="MedTech Deal Closure Email",
            source="gmail",
            document_type="email",
            reference_time=datetime(2025, 10, 15, 14, 30),
            metadata={
                "from": "sarah.chen@techvision.io",
                "to": "mike.johnson@techvision.io",
                "subject": "MedTech Deal Update - Ready to Close",
                "deal_value": 450000,
                "company": "MedTech Solutions"
            }
        )

        print("\n" + "="*80)
        print("📊 INGESTION RESULT")
        print("="*80)
        for key, value in result.items():
            if key != "chunk_ids":  # Skip chunk IDs for brevity
                print(f"   {key}: {value}")

    finally:
        await pipeline.close()


if __name__ == "__main__":
    asyncio.run(test_pipeline())
