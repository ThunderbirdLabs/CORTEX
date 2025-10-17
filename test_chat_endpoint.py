"""
Production-level test for /api/v1/chat endpoint
Tests the CEO assistant prompt by simulating frontend chat requests
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ingestion.llamaindex import HybridQueryEngine

async def test_production_query():
    """
    Test the query engine the same way the /api/v1/chat endpoint does.
    This simulates exactly what happens when the frontend sends a chat message.
    """
    print("🚀 Initializing HybridQueryEngine (same as /api/v1/chat endpoint)...")
    engine = HybridQueryEngine()

    print("\n" + "="*80)
    print("💬 Testing CEO Assistant Prompt with Document Correlation")
    print("   Question: 'Tell me about Alex Kashkarian and what he's been working on'")
    print("="*80 + "\n")

    # Execute query exactly as the chat endpoint does (line 118 in chat.py)
    result = await engine.query("Tell me about Alex Kashkarian and what he's been working on")

    print("\n📋 ANSWER:")
    print("-"*80)
    print(result['answer'])
    print("-"*80)

    # Format sources exactly as the chat endpoint does (lines 121-131 in chat.py)
    sources = []
    for i, node in enumerate(result.get('source_nodes', []), 1):
        metadata = node.metadata if hasattr(node, 'metadata') else {}
        sources.append({
            'index': i,
            'document_name': metadata.get('document_name', 'Unknown'),
            'source': metadata.get('source', 'Unknown'),
            'document_type': metadata.get('document_type', 'Unknown'),
            'timestamp': metadata.get('timestamp', 'Unknown'),
            'text_preview': node.text[:200] if hasattr(node, 'text') else ''
        })

    print(f"\n📚 Sources: {len(sources)} documents retrieved")
    print("-"*80)
    for source in sources[:3]:  # Show first 3
        print(f"  {source['index']}. {source['document_name']} ({source['document_type']})")
        print(f"     Preview: {source['text_preview'][:100]}...")
        print()

if __name__ == "__main__":
    asyncio.run(test_production_query())
