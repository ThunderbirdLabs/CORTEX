import asyncio
import logging
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

from app.services.ingestion.llamaindex import HybridQueryEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_query():
    print("\n" + "="*80)
    print("TESTING HYBRID QUERY ENGINE")
    print("="*80 + "\n")

    # Initialize query engine
    engine = HybridQueryEngine()

    # Test queries
    queries = [
        "What is Cortex?",
        "Who works at TechVision?",
        "What meetings have been scheduled?"
    ]

    for question in queries:
        print(f"\n{'='*80}")
        print(f"❓ Question: {question}")
        print(f"{'='*80}")

        result = await engine.query(question)

        print(f"\n✅ Answer:\n{result['answer']}\n")
        print(f"📊 Retrieved {len(result.get('source_nodes', []))} source nodes")
        print()

if __name__ == "__main__":
    asyncio.run(test_query())
