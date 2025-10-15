import asyncio
import logging
from dotenv import load_dotenv
import nest_asyncio

nest_asyncio.apply()
load_dotenv()

from app.services.ingestion.llamaindex.hybrid_property_graph_pipeline import HybridPropertyGraphPipeline
from app.services.ingestion.llamaindex.hybrid_retriever import create_hybrid_retriever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_query():
    print("\n" + "="*80)
    print("TESTING HYBRID RETRIEVAL")
    print("="*80 + "\n")
    
    # Initialize pipeline
    pipeline = HybridPropertyGraphPipeline()
    
    # Create retriever
    retriever = create_hybrid_retriever(pipeline, similarity_top_k=5, use_cypher=False)
    
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
        
        result = await retriever.query(question)
        
        print(f"\n✅ Answer:\n{result['answer']}\n")
        print(f"📊 Retrieved {len(result['source_nodes'])} source nodes")
        print()
    
    await pipeline.close()

if __name__ == "__main__":
    asyncio.run(test_query())
