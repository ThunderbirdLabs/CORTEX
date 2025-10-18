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
    print("💬 Testing CEO Assistant Query")
    print("   Question: 'What is Nick working on?'")
    print("="*80 + "\n")

    # Execute query exactly as the chat endpoint does (line 118 in chat.py)
    result = await engine.query("What is Nick working on?")

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

    # Print sub-questions if available
    if 'metadata' in result and result['metadata']:
        print(f"\n🔍 SUB-QUESTIONS GENERATED:")
        print("-"*80)
        metadata = result['metadata']
        if 'sub_qa' in metadata:
            for i, sub_qa in enumerate(metadata['sub_qa'], 1):
                print(f"\n  {i}. Sub-question: {sub_qa.get('sub_q', {}).get('sub_question', 'N/A')}")
                print(f"     Tool: {sub_qa.get('sub_q', {}).get('tool_name', 'N/A')}")
                print(f"     Answer: {sub_qa.get('answer', 'N/A')[:200]}...")

    print(f"\n📚 ALL SOURCES ({len(sources)} total):")
    print("-"*80)
    for source in sources:
        print(f"\n  {source['index']}. {source['document_name']} ({source['document_type']}, {source['source']})")
        print(f"     Preview: {source['text_preview'][:150]}...")

if __name__ == "__main__":
    asyncio.run(test_production_query())
