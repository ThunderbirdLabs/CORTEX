"""
Quick test script to query the HybridQueryEngine directly
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.ingestion.llamaindex import HybridQueryEngine

async def main():
    print("🚀 Initializing HybridQueryEngine...")
    engine = HybridQueryEngine()

    print("\n" + "="*80)
    print("💬 Asking: 'Tell me about safety'")
    print("="*80 + "\n")

    result = await engine.query("Tell me about safety")

    print("\n📋 ANSWER:")
    print("-"*80)
    print(result['answer'])
    print("-"*80)

    print(f"\n📚 Sources: {len(result['source_nodes'])} documents retrieved")

if __name__ == "__main__":
    asyncio.run(main())
