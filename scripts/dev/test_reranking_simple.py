"""
Production-style test: Ask a real question and log every step of retrieval.

Shows:
1. Initial vector similarity scores
2. After reranking scores
3. After recency boost scores
4. Exact position changes at each stage
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Set up detailed logging to see RecencyBoostPostprocessor output
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank
from qdrant_client import QdrantClient

from app.core.config import settings
from app.services.ingestion.llamaindex.recency_postprocessor import RecencyBoostPostprocessor


def main():
    print("=" * 100)
    print("PRODUCTION RERANKING TEST: Full query with detailed logging")
    print("=" * 100)

    embed_model = OpenAIEmbedding(model_name="text-embedding-3-small", api_key=settings.openai_api_key)
    llm = OpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.openai_api_key)

    qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    vector_store = QdrantVectorStore(
        client=qdrant_client,
        collection_name=settings.qdrant_collection_name
    )

    vector_index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model
    )

    query = "Who are our main suppliers for materials?"

    print(f"\n🔍 Question: '{query}'")
    print("=" * 100)

    # Test 1: No postprocessors
    print("\n📊 TEST 1: Baseline (no reranking)")
    engine1 = vector_index.as_query_engine(
        similarity_top_k=10,
        llm=llm,
        node_postprocessors=[]
    )
    response1 = engine1.query(query)
    nodes1 = response1.source_nodes[:10]

    print("Top 5 results:")
    for i, node in enumerate(nodes1[:5], 1):
        title = node.metadata.get('title', 'Unknown')[:50]
        print(f"  {i}. [{node.score:.4f}] {title}")

    # Test 2: With reranking
    print("\n📊 TEST 2: With reranking")
    engine2 = vector_index.as_query_engine(
        similarity_top_k=10,
        llm=llm,
        node_postprocessors=[
            SentenceTransformerRerank(
                model="BAAI/bge-reranker-base",
                top_n=10,
                device="cpu"
            )
        ]
    )
    response2 = engine2.query(query)
    nodes2 = response2.source_nodes[:10]

    print("Top 5 results:")
    for i, node in enumerate(nodes2[:5], 1):
        title = node.metadata.get('title', 'Unknown')[:50]
        # Find original position
        orig_pos = None
        for j, n1 in enumerate(nodes1, 1):
            if n1.node.id_ == node.node.id_:
                orig_pos = j
                break
        movement = f" (was #{orig_pos})" if orig_pos and orig_pos != i else ""
        print(f"  {i}. [{node.score:.4f}] {title}{movement}")

    # Test 3: With reranking + recency
    print("\n📊 TEST 3: With reranking + recency boost")
    engine3 = vector_index.as_query_engine(
        similarity_top_k=10,
        llm=llm,
        node_postprocessors=[
            SentenceTransformerRerank(
                model="BAAI/bge-reranker-base",
                top_n=10,
                device="cpu"
            ),
            RecencyBoostPostprocessor(decay_days=90)
        ]
    )
    response3 = engine3.query(query)
    nodes3 = response3.source_nodes[:10]

    print("Top 5 results:")
    for i, node in enumerate(nodes3[:5], 1):
        title = node.metadata.get('title', 'Unknown')[:50]
        created = node.metadata.get('created_at', '')[:10]
        # Find position after reranking
        rerank_pos = None
        for j, n2 in enumerate(nodes2, 1):
            if n2.node.id_ == node.node.id_:
                rerank_pos = j
                break
        movement = f" (was #{rerank_pos} after rerank)" if rerank_pos and rerank_pos != i else ""
        print(f"  {i}. [{node.score:.4f}] {title} ({created}){movement}")

    # Now do full answer generation to see logs
    print("\n" + "=" * 100)
    print("📝 GENERATING ANSWER (this will show RecencyBoost logs)")
    print("=" * 100)

    full_response = engine3.query(query)

    print("\n" + "=" * 100)
    print("ANSWER FROM LLM:")
    print("=" * 100)
    print(f"\n{full_response.response}\n")

    print("=" * 100)
    print("✅ CHECK LOGS ABOVE:")
    print("   - 'RecencyBoost: Boosted X nodes' means recency ran")
    print("   - Position changes (was #X) means reranking worked")
    print("=" * 100)


if __name__ == "__main__":
    main()
