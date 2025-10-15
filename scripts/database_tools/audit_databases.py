"""
Deep audit of Neo4j and Qdrant databases
Check structure, content, and metadata
"""
import asyncio
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from neo4j import GraphDatabase
import os
import json

load_dotenv()

# Qdrant
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY")
)

# Neo4j
neo4j_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
)

print("\n" + "="*80)
print("DEEP DATABASE AUDIT")
print("="*80)

# ============================================================================
# QDRANT AUDIT
# ============================================================================

print("\n" + "="*80)
print("QDRANT DETAILED AUDIT")
print("="*80 + "\n")

collection_info = qdrant_client.get_collection("cortex_documents")
print(f"Total points: {collection_info.vectors_count}")
print(f"Vector dimensions: {collection_info.config.params.vectors.size}")

# Get sample points with full payload
points = qdrant_client.scroll(
    collection_name="cortex_documents",
    limit=3,
    with_payload=True,
    with_vectors=False
)[0]

print(f"\n📄 DETAILED POINT ANALYSIS (first 3):\n")

for i, point in enumerate(points, 1):
    print(f"\n{'='*80}")
    print(f"POINT {i}")
    print(f"{'='*80}")
    print(f"ID: {point.id}")
    print(f"\nPayload keys: {list(point.payload.keys())}")
    
    # Check for text content
    if '_node_content' in point.payload:
        node_content = json.loads(point.payload['_node_content'])
        print(f"\n_node_content structure:")
        print(f"  Keys: {list(node_content.keys())}")
        print(f"  text field: {node_content.get('text', 'MISSING')[:200]}...")
        print(f"  metadata: {node_content.get('metadata', {})}")
    else:
        print("\n⚠️  NO '_node_content' field found!")
    
    print(f"\nDirect payload fields:")
    for key, value in point.payload.items():
        if key != '_node_content':
            if isinstance(value, str) and len(value) > 100:
                print(f"  {key}: {value[:100]}...")
            else:
                print(f"  {key}: {value}")

# ============================================================================
# NEO4J AUDIT  
# ============================================================================

print("\n" + "="*80)
print("NEO4J DETAILED AUDIT")
print("="*80 + "\n")

with neo4j_driver.session(database="neo4j") as session:
    # Check node types
    result = session.run("""
        MATCH (n)
        RETURN labels(n) as labels, count(*) as count
        ORDER BY count DESC
    """)
    
    print("Node distribution by labels:")
    for record in result:
        print(f"  {record['labels']}: {record['count']}")
    
    # Check __Node__ nodes (document chunks)
    print("\n" + "="*80)
    print("__Node__ NODES (Document Chunks)")
    print("="*80)
    
    result = session.run("""
        MATCH (n:__Node__)
        RETURN n.id as id, n.text as text, keys(n) as properties
        LIMIT 3
    """)
    
    for i, record in enumerate(result, 1):
        print(f"\n__Node__ {i}:")
        print(f"  ID: {record['id']}")
        print(f"  Properties: {record['properties']}")
        print(f"  Text: {record['text'][:200] if record['text'] else 'MISSING'}...")
    
    # Check __Entity__ nodes
    print("\n" + "="*80)
    print("__Entity__ NODES (Extracted Entities)")
    print("="*80)
    
    result = session.run("""
        MATCH (e:__Entity__)
        RETURN labels(e) as labels, e.name as name, e.triplet_source_id as source_id, keys(e) as properties
        LIMIT 5
    """)
    
    for i, record in enumerate(result, 1):
        print(f"\n__Entity__ {i}:")
        print(f"  Labels: {record['labels']}")
        print(f"  Name: {record['name']}")
        print(f"  Source ID: {record['source_id']}")
        print(f"  Properties: {record['properties']}")
    
    # Check relationships
    print("\n" + "="*80)
    print("RELATIONSHIPS")
    print("="*80)
    
    result = session.run("""
        MATCH (a)-[r]->(b)
        RETURN type(r) as rel_type, count(*) as count
        ORDER BY count DESC
        LIMIT 10
    """)
    
    print("\nRelationship distribution:")
    for record in result:
        print(f"  {record['rel_type']}: {record['count']}")

neo4j_driver.close()

print("\n" + "="*80)
print("AUDIT COMPLETE")
print("="*80 + "\n")
