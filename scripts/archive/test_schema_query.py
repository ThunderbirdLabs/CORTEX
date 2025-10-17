"""
Test query retrieval on SchemaLLMPathExtractor ingested data
"""
import asyncio
import nest_asyncio
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

from app.services.ingestion.llamaindex import HybridQueryEngine

async def test_queries():
    print("="*80)
    print("TESTING QUERY RETRIEVAL ON SCHEMA-INGESTED DATA")
    print("="*80)
    print()

    engine = HybridQueryEngine()

    queries = [
        "What is Cortex?",
        "Who is Alex Thompson?",
        "What companies are mentioned?",
    ]

    for question in queries:
        print("\n" + "="*80)
        print(f"❓ Question: {question}")
        print("="*80)

        result = await engine.query(question)

        print(f"\n✅ Answer:\n{result['answer']}")
        print(f"\n📊 Retrieved {len(result.get('source_nodes', []))} source nodes")
        print()

if __name__ == "__main__":
    asyncio.run(test_queries())
