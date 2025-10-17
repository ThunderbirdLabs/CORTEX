"""
Test script to add Alex's introduction document and see chunk nodes created in Neo4j
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ingestion.llamaindex import UniversalIngestionPipeline

async def main():
    print("🚀 Initializing UniversalIngestionPipeline...")
    pipeline = UniversalIngestionPipeline()

    document_text = """Hello! I wanted to take a moment to introduce myself and share a bit about what we're working on here at Cortex. My name is Alex Kashkarian, and I'm excited about the possibilities that Cortex brings.

At its heart, Cortex is a hybrid RAG (Retrieval-Augmented Generation) search system. What this means is that it combines the power of retrieval-based methods, where relevant information is pulled from a vast knowledge base, with the generative capabilities of large language models. This allows Cortex to not only find accurate information but also to synthesize and present it in a coherent and contextually relevant way. We're building it to be incredibly robust and adaptable, designed to handle complex queries and deliver insightful results across various applications. We believe this approach offers a significant leap forward in how we interact with and extract value from information.

On a more personal note, I also wanted to introduce you to a couple of very important members of the Cortex team – in fact, they were our very first employees! We have Chloe, a very dedicated bomb-sniffing dog, and Sprinkles, a charming cat. They bring a lot of joy and a unique perspective to our daily work, even if most of their contributions involve napping and demanding treats. Chloe, with her professional background, actually serves as a constant reminder of the importance of thorough and accurate "retrieval" in her line of work, which, in a way, mirrors the precision we strive for in Cortex.

We're really looking forward to the journey ahead with Cortex and the positive impact it can make.

Best regards,
Alex Kashkarian"""

    # Create a fake document row (simulating Supabase structure)
    document_row = {
        "id": "test-alex-intro-001",
        "name": "Alex's Introduction to Cortex",
        "mime_type": "text/plain",
        "file_path": "test/alex_intro.txt",
        "content": document_text,
        "document_type": "googledoc",
        "source": "test"
    }

    print("\n" + "="*80)
    print("📄 INGESTING ALEX'S INTRODUCTION")
    print("="*80)
    print(f"Document: {document_row['name']}")
    print(f"Length: {len(document_text)} characters")
    print("="*80 + "\n")

    # Ingest the document with entity extraction enabled
    result = await pipeline.ingest_document(
        document_row=document_row,
        extract_entities=True
    )

    print("\n" + "="*80)
    print("✅ INGESTION COMPLETE")
    print("="*80)
    print(f"Status: {result.get('status')}")
    print(f"Document ID: {result.get('document_id')}")
    print(f"Vector nodes: {result.get('vector_nodes', 0)}")
    print(f"Graph nodes: {result.get('graph_nodes', 0)}")
    print("="*80)

    print("\n🔍 Now run: python3 test_chunk_nodes.py")
    print("   To see the Chunk nodes and MENTIONS relationships in Neo4j!")

if __name__ == "__main__":
    asyncio.run(main())
