from neo4j import GraphDatabase
from qdrant_client import QdrantClient
import os
from dotenv import load_dotenv

load_dotenv()

print("="*80)
print("STORAGE ANALYSIS: Neo4j vs Qdrant")
print("="*80 + "\n")

# Neo4j
driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

with driver.session(database="neo4j") as session:
    # Get Chunk node stats
    result = session.run("""
        MATCH (c:Chunk)
        RETURN 
            count(c) as total_chunks,
            avg(size(c.text)) as avg_text_length,
            max(size(c.text)) as max_text_length,
            min(size(c.text)) as min_text_length
    """)
    
    stats = result.single()
    print("NEO4J CHUNK STORAGE:")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Avg text length: {stats['avg_text_length']:.0f} chars")
    print(f"  Max text length: {stats['max_text_length']} chars")
    print(f"  Min text length: {stats['min_text_length']} chars")
    
    # Sample a few chunks to see actual content
    result = session.run("""
        MATCH (c:Chunk)
        WHERE c.text IS NOT NULL
        RETURN c.id as id, size(c.text) as text_length, 
               size(c.embedding) as embedding_dims,
               c.text as text
        ORDER BY size(c.text) DESC
        LIMIT 3
    """)
    
    print("\n  Sample chunks (by size):")
    for i, record in enumerate(result, 1):
        print(f"\n    Chunk {i}:")
        print(f"      Text length: {record['text_length']} chars")
        print(f"      Embedding dims: {record['embedding_dims']}")
        print(f"      Preview: {record['text'][:150]}...")

driver.close()

# Qdrant
qdrant = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

collection_info = qdrant.get_collection("cortex_documents")
print(f"\n{'='*80}")
print("QDRANT VECTOR STORAGE:")
print(f"  Total points: {collection_info.vectors_count}")
print(f"  Vector dimensions: {collection_info.config.params.vectors.size}")

# Sample points
points = qdrant.scroll(
    collection_name="cortex_documents",
    limit=3,
    with_payload=True,
    with_vectors=False
)[0]

print("\n  Sample points (what's stored):")
for i, point in enumerate(points, 1):
    payload = point.payload
    node_content = eval(payload.get('_node_content', '{}'))
    text = node_content.get('text', 'N/A')
    
    print(f"\n    Point {i}:")
    print(f"      Type: {payload.get('_node_type')}")
    print(f"      Text: {text[:100]}...")
    print(f"      Document: {payload.get('document_name')}")

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80 + "\n")
