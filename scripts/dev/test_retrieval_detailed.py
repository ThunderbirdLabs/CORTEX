"""
Test detailed retrieval from both Qdrant and Neo4j
Shows exactly what's being pulled from each source
"""
import asyncio
import nest_asyncio
from dotenv import load_dotenv

nest_asyncio.apply()
load_dotenv()

from app.services.ingestion.llamaindex import HybridQueryEngine

async def test_detailed_retrieval():
    print("="*80)
    print("DETAILED RETRIEVAL TEST - See exactly what's pulled from Qdrant & Neo4j")
    print("="*80)
    print()

    engine = HybridQueryEngine()

    question = "Who is Alex Thompson?"

    print(f"Question: {question}\n")
    print("="*80)

    # 1. Vector retrieval (Qdrant)
    print("\n🔷 VECTOR RETRIEVAL (Qdrant - Email Chunks)")
    print("="*80)
    vector_nodes = await engine.vector_query_engine.aretrieve(question)

    for i, node in enumerate(vector_nodes[:3], 1):  # Show top 3
        print(f"\n📄 Vector Node {i}:")
        print(f"   Score: {node.score:.4f}")
        print(f"   Text: {node.text[:200]}...")
        if node.metadata:
            print(f"   Metadata: {node.metadata}")

    # 2. Graph retrieval (Neo4j)
    print("\n\n🔶 GRAPH RETRIEVAL (Neo4j - Entities & Relationships)")
    print("="*80)
    graph_nodes = await engine.graph_query_engine.aretrieve(question)

    for i, node in enumerate(graph_nodes[:5], 1):  # Show top 5
        print(f"\n🔗 Graph Node {i}:")
        print(f"   Score: {node.score:.4f}")
        print(f"   Text: {node.text}")
        if node.metadata:
            print(f"   Metadata: {node.metadata}")

    # 3. Full hybrid query
    print("\n\n🔵 FULL HYBRID QUERY (Combined)")
    print("="*80)
    result = await engine.query(question)

    print(f"\n✅ Answer: {result['answer']}")
    print(f"\n📊 Total source nodes: {len(result['source_nodes'])}")

    # Show breakdown by source
    vector_count = sum(1 for n in result['source_nodes'] if 'vector' in str(n.node_id).lower() or hasattr(n, 'score'))
    graph_count = len(result['source_nodes']) - vector_count

    print(f"   - Vector nodes: {vector_count}")
    print(f"   - Graph nodes: {graph_count}")

if __name__ == "__main__":
    asyncio.run(test_detailed_retrieval())
