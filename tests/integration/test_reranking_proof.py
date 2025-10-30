"""
Test to PROVE reranking and recency boost are actually reordering results.

This script:
1. Runs the same query 3 times with different configurations
2. Shows the order of results changes based on postprocessors
3. Prints before/after scores and positions to prove reordering works
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.postprocessor.sbert_rerank import SentenceTransformerRerank
from qdrant_client import QdrantClient, AsyncQdrantClient

from app.core.config import settings
from app.services.ingestion.llamaindex.recency_postprocessor import RecencyBoostPostprocessor


def main():
    print("=" * 80)
    print("RERANKING + RECENCY BOOST PROOF TEST")
    print("=" * 80)

    # Setup
    embed_model = OpenAIEmbedding(model_name="text-embedding-3-small", api_key=settings.openai_api_key)
    llm = OpenAI(model="gpt-4o-mini", temperature=0.0, api_key=settings.openai_api_key)

    qdrant_client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    qdrant_aclient = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    vector_store = QdrantVectorStore(
        client=qdrant_client,
        aclient=qdrant_aclient,
        collection_name=settings.qdrant_collection_name
    )

    vector_index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model
    )

    # Test query
    query = "What materials do we use for manufacturing?"

    print(f"\n🔍 Test Query: '{query}'")
    print(f"   Fetching top 10 results...\n")

    # ============================================
    # TEST 1: No postprocessors (baseline)
    # ============================================
    print("=" * 80)
    print("TEST 1: NO POSTPROCESSORS (Baseline - pure vector similarity)")
    print("=" * 80)

    query_engine_baseline = vector_index.as_query_engine(
        similarity_top_k=10,
        llm=llm,
        node_postprocessors=[]  # NO postprocessors
    )

    nodes_baseline = query_engine_baseline.retrieve(query)

    print(f"\nTop 10 results (ordered by vector similarity):\n")
    for i, node in enumerate(nodes_baseline[:10], 1):
        title = node.metadata.get('title', 'Unknown')[:60]
        created_at = node.metadata.get('created_at', 'Unknown')
        score = node.score
        print(f"{i:2d}. [{score:.4f}] {title} ({created_at})")

    # ============================================
    # TEST 2: With SentenceTransformerRerank
    # ============================================
    print("\n" + "=" * 80)
    print("TEST 2: WITH RERANKING (Semantic relevance scoring)")
    print("=" * 80)

    query_engine_rerank = vector_index.as_query_engine(
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

    nodes_rerank = query_engine_rerank.retrieve(query)

    print(f"\nTop 10 results (reranked by semantic relevance):\n")
    for i, node in enumerate(nodes_rerank[:10], 1):
        title = node.metadata.get('title', 'Unknown')[:60]
        created_at = node.metadata.get('created_at', 'Unknown')
        score = node.score

        # Find original position in baseline
        original_pos = None
        for j, baseline_node in enumerate(nodes_baseline, 1):
            if baseline_node.node.id_ == node.node.id_:
                original_pos = j
                break

        movement = f"(moved from #{original_pos})" if original_pos and original_pos != i else ""
        print(f"{i:2d}. [{score:.4f}] {title} ({created_at}) {movement}")

    # ============================================
    # TEST 3: With Reranking + Recency Boost
    # ============================================
    print("\n" + "=" * 80)
    print("TEST 3: WITH RERANKING + RECENCY BOOST (Full pipeline)")
    print("=" * 80)

    query_engine_full = vector_index.as_query_engine(
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

    nodes_full = query_engine_full.retrieve(query)

    print(f"\nTop 10 results (reranked + recency boosted):\n")
    for i, node in enumerate(nodes_full[:10], 1):
        title = node.metadata.get('title', 'Unknown')[:60]
        created_at = node.metadata.get('created_at', 'Unknown')
        score = node.score

        # Find position after reranking (before recency boost)
        rerank_pos = None
        for j, rerank_node in enumerate(nodes_rerank, 1):
            if rerank_node.node.id_ == node.node.id_:
                rerank_pos = j
                break

        movement = f"(moved from #{rerank_pos} after rerank)" if rerank_pos and rerank_pos != i else ""
        print(f"{i:2d}. [{score:.4f}] {title} ({created_at}) {movement}")

    # ============================================
    # Summary: Show what changed
    # ============================================
    print("\n" + "=" * 80)
    print("SUMMARY: Position Changes")
    print("=" * 80)

    print("\n📊 Top 5 comparison:\n")
    print(f"{'Rank':<6} {'Baseline':<25} {'+ Rerank':<25} {'+ Recency':<25}")
    print("-" * 80)

    for rank in range(1, 6):
        baseline_title = nodes_baseline[rank-1].metadata.get('title', 'Unknown')[:22] if rank <= len(nodes_baseline) else 'N/A'
        rerank_title = nodes_rerank[rank-1].metadata.get('title', 'Unknown')[:22] if rank <= len(nodes_rerank) else 'N/A'
        full_title = nodes_full[rank-1].metadata.get('title', 'Unknown')[:22] if rank <= len(nodes_full) else 'N/A'

        print(f"#{rank:<5} {baseline_title:<25} {rerank_title:<25} {full_title:<25}")

    print("\n✅ If positions changed, reranking and recency boost are WORKING!")
    print("=" * 80)


if __name__ == "__main__":
    main()
