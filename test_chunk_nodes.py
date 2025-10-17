"""
Test script to verify chunk nodes are created in Neo4j with MENTIONS relationships
"""
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def check_chunk_nodes():
    """Check if Chunk nodes exist in Neo4j"""
    with driver.session() as session:
        # Count all node types
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] as label, count(*) as count
            ORDER BY count DESC
        """)

        print("\n" + "="*80)
        print("NODE TYPES IN NEO4J")
        print("="*80)
        for record in result:
            print(f"  {record['label']}: {record['count']}")

        # Check for Chunk nodes specifically
        chunk_count = session.run("""
            MATCH (c:Chunk)
            RETURN count(c) as count
        """).single()

        print("\n" + "="*80)
        print(f"CHUNK NODES: {chunk_count['count']}")
        print("="*80)

        # Check for MENTIONS relationships
        mentions_count = session.run("""
            MATCH ()-[r:MENTIONS]->()
            RETURN count(r) as count
        """).single()

        print("\n" + "="*80)
        print(f"MENTIONS RELATIONSHIPS: {mentions_count['count']}")
        print("="*80)

        # Show sample Chunk node with MENTIONS
        if chunk_count['count'] > 0:
            sample = session.run("""
                MATCH (c:Chunk)-[m:MENTIONS]->(e)
                RETURN c.node_id as chunk_id,
                       substring(c.text, 0, 100) as text_preview,
                       labels(e)[0] as entity_type,
                       e.name as entity_name
                LIMIT 3
            """)

            print("\n" + "="*80)
            print("SAMPLE CHUNK → MENTIONS → ENTITY")
            print("="*80)
            for record in sample:
                print(f"\nChunk: {record['chunk_id']}")
                print(f"Text: {record['text_preview']}...")
                print(f"  └─[MENTIONS]→ {record['entity_type']}: {record['entity_name']}")

if __name__ == "__main__":
    check_chunk_nodes()
    driver.close()
