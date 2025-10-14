"""
Hybrid Search: Query both Vector DB (Qdrant Cloud) and Knowledge Graph (Neo4j/Graphiti)

Search strategies:
1. Vector search - semantic similarity in Qdrant Cloud
2. Knowledge graph search - entity relationships in Neo4j
3. Hybrid fusion - combine results from both
"""
import os
import asyncio
from typing import List, Dict, Optional
from openai import OpenAI
from qdrant_client import QdrantClient
from graphiti_core import Graphiti
from dotenv import load_dotenv

load_dotenv()


class HybridSearch:
    """
    Hybrid search combining vector similarity and knowledge graph traversal
    """

    def __init__(self):
        # OpenAI for embeddings
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Qdrant Cloud connection
        self.qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "cortex_documents")

        # Graphiti for knowledge graph
        self.graphiti = None

        print("✅ Hybrid Search initialized")

    async def initialize_graphiti(self):
        """Initialize Graphiti connection"""
        if self.graphiti is None:
            self.graphiti = Graphiti(
                uri=os.getenv("NEO4J_URI"),
                user=os.getenv("NEO4J_USER"),
                password=os.getenv("NEO4J_PASSWORD")
            )
        return self.graphiti

    def get_embedding(self, text: str) -> List[float]:
        """Get OpenAI embedding for query"""
        response = self.openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    def vector_search(
        self,
        query: str,
        limit: int = 5,
        source_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        Search Qdrant Cloud for semantically similar chunks
        """
        print(f"\n🔍 Vector Search (Qdrant Cloud)...")

        # Get query embedding
        query_embedding = self.get_embedding(query)

        # Build filter if source specified
        query_filter = None
        if source_filter:
            query_filter = {
                "must": [
                    {"key": "source", "match": {"value": source_filter}}
                ]
            }

        # Search Qdrant
        search_results = self.qdrant_client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=limit,
            query_filter=query_filter
        )

        # Format results
        results = []
        for hit in search_results:
            results.append({
                "id": hit.id,
                "document_name": hit.payload.get("document_name"),
                "source": hit.payload.get("source"),
                "document_type": hit.payload.get("document_type"),
                "content": hit.payload.get("content"),
                "chunk_index": hit.payload.get("chunk_index"),
                "episode_id": hit.payload.get("graphiti_episode_id"),
                "metadata": hit.payload.get("metadata"),
                "similarity": hit.score
            })

        print(f"   ✅ Found {len(results)} relevant chunks")
        return results

    async def knowledge_graph_search(
        self,
        query: str,
        limit: int = 5
    ) -> List[Dict]:
        """
        Search Neo4j knowledge graph for related entities and relationships
        """
        print(f"\n🕸️  Knowledge Graph Search (Neo4j)...")

        await self.initialize_graphiti()

        # Search Graphiti
        results = await self.graphiti.search(query=query)

        # Format results
        formatted_results = []
        for edge in results[:limit]:
            formatted_results.append({
                "type": "relationship",
                "relation_name": edge.name,
                "fact": edge.fact,
                "source_node_id": edge.source_node_uuid,
                "target_node_id": edge.target_node_uuid,
                "valid_at": str(edge.valid_at) if edge.valid_at else None,
                "episodes": edge.episodes
            })

        print(f"   ✅ Found {len(formatted_results)} relevant relationships")
        return formatted_results

    async def hybrid_search(
        self,
        query: str,
        vector_limit: int = 5,
        graph_limit: int = 5,
        source_filter: Optional[str] = None
    ) -> Dict:
        """
        Combined search: Vector DB + Knowledge Graph
        Returns both sets of results with episode_id linking
        """
        print(f"\n{'='*80}")
        print(f"🔍 HYBRID SEARCH: {query}")
        print(f"{'='*80}")

        # Search vector DB
        vector_results = self.vector_search(
            query=query,
            limit=vector_limit,
            source_filter=source_filter
        )

        # Search knowledge graph
        graph_results = await self.knowledge_graph_search(
            query=query,
            limit=graph_limit
        )

        # Link results by episode_id
        episode_ids = set()
        for result in vector_results:
            if result.get("episode_id"):
                episode_ids.add(result["episode_id"])

        # Get knowledge graph facts for these episodes
        related_graph_facts = []
        for graph_result in graph_results:
            if any(ep_id in episode_ids for ep_id in graph_result.get("episodes", [])):
                related_graph_facts.append(graph_result)

        return {
            "query": query,
            "vector_results": vector_results,
            "graph_results": graph_results,
            "linked_facts": related_graph_facts,
            "num_episodes": len(episode_ids)
        }

    def get_context_for_episode(self, episode_id: str) -> Dict:
        """
        Get all context (vector chunks + graph facts) for a specific episode
        """
        print(f"\n📋 Getting context for episode: {episode_id}")

        # Query Qdrant for all chunks with this episode_id
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        search_result = self.qdrant_client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="graphiti_episode_id",
                        match=MatchValue(value=episode_id)
                    )
                ]
            ),
            limit=100
        )

        chunks = []
        for point in search_result[0]:
            chunks.append({
                "id": point.id,
                "document_name": point.payload.get("document_name"),
                "source": point.payload.get("source"),
                "content": point.payload.get("content"),
                "chunk_index": point.payload.get("chunk_index"),
                "total_chunks": point.payload.get("total_chunks"),
                "metadata": point.payload.get("metadata")
            })

        # Sort by chunk_index
        chunks.sort(key=lambda x: x["chunk_index"])

        print(f"   ✅ Found {len(chunks)} chunks")

        return {
            "episode_id": episode_id,
            "chunks": chunks,
            "total_chunks": len(chunks)
        }

    async def close(self):
        """Close connections"""
        if self.graphiti:
            await self.graphiti.close()


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

async def test_hybrid_search():
    """Test hybrid search with example queries"""

    search = HybridSearch()

    test_queries = [
        "MedTech Solutions deal details",
        "healthcare contracts and pricing",
        "Sarah Chen deals and partnerships"
    ]

    try:
        for query in test_queries:
            # Perform hybrid search
            results = await search.hybrid_search(
                query=query,
                vector_limit=3,
                graph_limit=5
            )

            # Display results
            print(f"\n{'='*80}")
            print(f"📊 RESULTS FOR: {query}")
            print(f"{'='*80}")

            print(f"\n📄 Vector Search Results ({len(results['vector_results'])} chunks):")
            for i, result in enumerate(results['vector_results'], 1):
                print(f"\n   {i}. {result['document_name']} ({result['source']})")
                print(f"      Similarity: {result['similarity']:.3f}")
                print(f"      Content: {result['content'][:150]}...")
                print(f"      Episode ID: {result['episode_id']}")

            print(f"\n🕸️  Knowledge Graph Results ({len(results['graph_results'])} relationships):")
            for i, result in enumerate(results['graph_results'], 1):
                print(f"\n   {i}. [{result['relation_name']}]")
                print(f"      Fact: {result['fact'][:150]}...")

            if results['linked_facts']:
                print(f"\n🔗 Linked Facts ({len(results['linked_facts'])} relationships linked to vector results):")
                for i, fact in enumerate(results['linked_facts'], 1):
                    print(f"   {i}. {fact['fact'][:100]}...")

            print(f"\n📊 Summary:")
            print(f"   Vector chunks found: {len(results['vector_results'])}")
            print(f"   Graph relationships found: {len(results['graph_results'])}")
            print(f"   Unique episodes: {results['num_episodes']}")
            print(f"   Linked facts: {len(results['linked_facts'])}")

        # Test episode context retrieval
        if results['vector_results']:
            episode_id = results['vector_results'][0]['episode_id']
            context = search.get_context_for_episode(episode_id)

            print(f"\n{'='*80}")
            print(f"📋 EPISODE CONTEXT")
            print(f"{'='*80}")
            print(f"   Episode ID: {context['episode_id']}")
            print(f"   Total chunks: {context['total_chunks']}")
            for chunk in context['chunks']:
                print(f"\n   Chunk {chunk['chunk_index'] + 1}/{chunk['total_chunks']}:")
                print(f"   {chunk['content'][:200]}...")

    finally:
        await search.close()


if __name__ == "__main__":
    asyncio.run(test_hybrid_search())
